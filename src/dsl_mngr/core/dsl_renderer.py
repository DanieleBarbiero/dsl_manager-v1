from __future__ import annotations

import copy
import hashlib
import json
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from dsl_mngr.core.database import (
    DatabaseConfigurationError,
    DatabaseSettings,
    open_database,
    resolve_database_settings,
    resolve_workspace_path,
)
from dsl_mngr.core.runs import (
    DatabaseNotReadyError,
    canonical_json,
    next_id,
    relative_workspace_path,
    run_artifact_paths,
    timestamp_now,
    validate_database_migrations,
    write_process_report,
)


Clock = Callable[[], datetime]

INCLUDED_FACT_STATUSES = ("active", "inferred", "pending_review", "conflicted")


class DslRenderError(RuntimeError):
    """Raised when a DSL snapshot cannot be rendered."""


class DslRenderDatabaseNotReadyError(DslRenderError):
    """Raised when DSL rendering needs a migrated database."""


@dataclass(frozen=True)
class DslRenderResult:
    run_id: str
    snapshot_id: str
    dsl_hash: str
    registry_hash: str
    entity_count: int
    fact_count: int
    relation_count: int
    conflict_count: int
    output_dir: str
    json_path: str
    yaml_path: str
    markdown_path: str

    def to_artifact_payload(self) -> dict[str, Any]:
        return {
            "conflict_count": self.conflict_count,
            "dsl_hash": self.dsl_hash,
            "entity_count": self.entity_count,
            "fact_count": self.fact_count,
            "json_path": self.json_path,
            "markdown_path": self.markdown_path,
            "output_dir": self.output_dir,
            "registry_hash": self.registry_hash,
            "relation_count": self.relation_count,
            "run_id": self.run_id,
            "snapshot_id": self.snapshot_id,
            "yaml_path": self.yaml_path,
        }


@dataclass(frozen=True)
class _RegistryView:
    facts: list[dict[str, Any]]
    relations: list[dict[str, Any]]
    conflicts: list[dict[str, Any]]
    fact_traceability: dict[str, list[dict[str, Any]]]
    relation_traceability: dict[str, list[dict[str, Any]]]
    registry_payload: dict[str, Any]


@dataclass(frozen=True)
class _SnapshotPaths:
    json_file: Path
    yaml_file: Path
    markdown_file: Path
    json_path: str
    yaml_path: str
    markdown_path: str


def ensure_dsl_render_database_ready(workspace_dir: str | Path) -> DatabaseSettings:
    settings = resolve_database_settings(workspace_dir)
    if not settings.database_path.is_file():
        raise DslRenderDatabaseNotReadyError(
            f"Database is not initialized: {settings.database_path}. "
            "Run 'dsl-manager db init <workspace>' before 'dsl-manager dsl render'."
        )

    connection = open_database(settings.database_path, enable_wal=settings.wal_enabled)
    try:
        try:
            validate_database_migrations(connection)
        except DatabaseNotReadyError as exc:
            message = str(exc).replace("dsl-manager run", "dsl-manager dsl render")
            raise DslRenderDatabaseNotReadyError(message) from exc
    finally:
        connection.close()
    return settings


def render_dsl_snapshot(
    workspace_dir: str | Path,
    *,
    run_id: str,
    output_dir: str | Path | None = None,
    clock: Clock | None = None,
) -> DslRenderResult:
    settings = ensure_dsl_render_database_ready(workspace_dir)
    export_dir = _resolve_output_dir(settings.workspace_dir, output_dir)
    timestamp = timestamp_now(clock)

    connection = open_database(settings.database_path, enable_wal=settings.wal_enabled)
    try:
        validate_database_migrations(connection)
        registry = _load_registry_view(connection)
        registry_hash = _stable_json_hash(registry.registry_payload)

        snapshot_id = next_id(connection, "dsl_snapshots", "snapshot_id", "DSL")
        paths = _snapshot_paths(settings.workspace_dir, export_dir, snapshot_id)

        content_without_hash = _build_dsl_content(registry, registry_hash=registry_hash)
        dsl_hash = _hash_dsl_content(content_without_hash)
        content = _with_dsl_hash(content_without_hash, dsl_hash)
        content_json = canonical_json(content)

        export_dir.mkdir(parents=True, exist_ok=True)
        paths.json_file.write_text(content_json, encoding="utf-8", newline="\n")
        paths.yaml_file.write_text(dump_dsl_yaml(content), encoding="utf-8", newline="\n")
        paths.markdown_file.write_text(render_dsl_markdown(content), encoding="utf-8", newline="\n")

        connection.execute("BEGIN")
        try:
            connection.execute(
                """
                INSERT INTO dsl_snapshots (
                    snapshot_id,
                    run_id,
                    dsl_hash,
                    registry_hash,
                    content_json,
                    json_path,
                    yaml_path,
                    markdown_path,
                    fact_count,
                    relation_count,
                    conflict_count,
                    status,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot_id,
                    run_id,
                    dsl_hash,
                    registry_hash,
                    content_json,
                    paths.json_path,
                    paths.yaml_path,
                    paths.markdown_path,
                    _count_facts(content),
                    len(content["relations"]),
                    len(content["conflicts"]),
                    "completed",
                    timestamp,
                ),
            )
        except Exception:
            connection.rollback()
            raise
        else:
            connection.commit()

        return DslRenderResult(
            run_id=run_id,
            snapshot_id=snapshot_id,
            dsl_hash=dsl_hash,
            registry_hash=registry_hash,
            entity_count=len(content["entities"]),
            fact_count=_count_facts(content),
            relation_count=len(content["relations"]),
            conflict_count=len(content["conflicts"]),
            output_dir=relative_workspace_path(settings.workspace_dir, export_dir),
            json_path=paths.json_path,
            yaml_path=paths.yaml_path,
            markdown_path=paths.markdown_path,
        )
    finally:
        connection.close()


def write_dsl_render_artifacts(workspace_dir: str | Path, result: DslRenderResult) -> None:
    artifacts = run_artifact_paths(workspace_dir, result.run_id)
    payload = result.to_artifact_payload()
    input_document = {
        "artifact_dir": artifacts.artifact_dir_relative,
        "parameters": {"output_dir": result.output_dir},
        "run_id": result.run_id,
        "run_type": "dsl_render",
        **payload,
    }
    artifacts.input_path.write_text(canonical_json(input_document), encoding="utf-8", newline="\n")

    report = json.loads(artifacts.process_report_path.read_text(encoding="utf-8"))
    report.update(payload)
    write_process_report(artifacts.process_report_path, report)


def dump_dsl_yaml(payload: Any) -> str:
    return "\n".join(_yaml_lines(payload, 0)) + "\n"


def render_dsl_markdown(content: dict[str, Any]) -> str:
    metadata = content["metadata"]
    counts = metadata["counts"]
    lines = [
        "# DSL",
        "",
        "## Metadata",
        f"- schema_version: `{metadata['schema_version']}`",
        f"- dsl_hash: `{metadata['dsl_hash']}`",
        f"- registry_hash: `{metadata['registry_hash']}`",
        (
            "- counts: "
            f"entities `{counts['entities']}`, facts `{counts['facts']}`, "
            f"relations `{counts['relations']}`, conflicts `{counts['conflicts']}`"
        ),
        "",
        "## Entities",
    ]

    if content["entities"]:
        for entity in content["entities"]:
            lines.extend(["", f"### {entity['name']}"])
            for fact in entity["facts"]:
                lines.append(
                    "- "
                    f"`{fact['fact_id']}` {fact['property_name']}: "
                    f"{fact['property_value']} "
                    f"(type `{fact['fact_type']}`, assertion `{fact['assertion_type']}`, "
                    f"confidence `{fact['confidence']}`, status `{fact['status']}`)"
                )
    else:
        lines.append("- none")

    lines.extend(["", "## Relations"])
    if content["relations"]:
        for relation in content["relations"]:
            lines.append(
                "- "
                f"`{relation['relation_id']}` {relation['source_entity']} "
                f"-[{relation['relation_type']}]-> {relation['target_entity']} "
                f"(assertion `{relation['assertion_type']}`, "
                f"confidence `{relation['confidence']}`, status `{relation['status']}`)"
            )
    else:
        lines.append("- none")

    lines.extend(["", "## Conflicts"])
    if content["conflicts"]:
        for conflict in content["conflicts"]:
            lines.append(
                "- "
                f"`{conflict['conflict_id']}` {conflict['conflict_type']} "
                f"on {conflict['entity_name']}.{conflict['property_name']}: "
                f"`{conflict['left_value']}` vs `{conflict['right_value']}` "
                f"(status `{conflict['status']}`)"
            )
    else:
        lines.append("- none")

    lines.extend(["", "## Traceability", "", "### Facts"])
    fact_traceability = content["traceability"]["facts"]
    if fact_traceability:
        for fact_id, evidence_items in fact_traceability.items():
            lines.extend(["", f"#### {fact_id}"])
            _append_evidence_markdown(lines, evidence_items)
    else:
        lines.append("- none")

    lines.extend(["", "### Relations"])
    relation_traceability = content["traceability"]["relations"]
    if relation_traceability:
        for relation_id, evidence_items in relation_traceability.items():
            lines.extend(["", f"#### {relation_id}"])
            _append_evidence_markdown(lines, evidence_items)
    else:
        lines.append("- none")

    return "\n".join(lines) + "\n"


def _resolve_output_dir(workspace_dir: Path, output_dir: str | Path | None) -> Path:
    configured = "exports/dsl" if output_dir is None else output_dir
    try:
        return resolve_workspace_path(workspace_dir, configured)
    except DatabaseConfigurationError as exc:
        raise DslRenderError(f"Output path escapes the workspace: {output_dir}") from exc


def _snapshot_paths(workspace_dir: Path, output_dir: Path, snapshot_id: str) -> _SnapshotPaths:
    json_file = output_dir / f"{snapshot_id}.json"
    yaml_file = output_dir / f"{snapshot_id}.yaml"
    markdown_file = output_dir / f"{snapshot_id}.md"
    return _SnapshotPaths(
        json_file=json_file,
        yaml_file=yaml_file,
        markdown_file=markdown_file,
        json_path=relative_workspace_path(workspace_dir, json_file),
        yaml_path=relative_workspace_path(workspace_dir, yaml_file),
        markdown_path=relative_workspace_path(workspace_dir, markdown_file),
    )


def _load_registry_view(connection: sqlite3.Connection) -> _RegistryView:
    facts = [_fact_payload(row) for row in _load_fact_rows(connection)]
    relations = [_relation_payload(row) for row in _load_relation_rows(connection)]
    conflicts = [_conflict_payload(row) for row in _load_conflict_rows(connection)]

    fact_ids = [fact["fact_id"] for fact in facts]
    relation_ids = [relation["relation_id"] for relation in relations]
    fact_evidence_rows = _load_fact_evidence_rows(connection, fact_ids)
    relation_evidence_rows = _load_relation_evidence_rows(connection, relation_ids)

    fact_traceability = _traceability_by_owner(fact_evidence_rows, "fact_id")
    relation_traceability = _traceability_by_owner(relation_evidence_rows, "relation_id")
    sources, source_revisions = _source_payloads([*fact_evidence_rows, *relation_evidence_rows])

    registry_payload = {
        "conflicts": conflicts,
        "fact_evidence": [
            _evidence_registry_payload(row, "fact_id") for row in fact_evidence_rows
        ],
        "facts": facts,
        "relation_evidence": [
            _evidence_registry_payload(row, "relation_id") for row in relation_evidence_rows
        ],
        "relations": relations,
        "source_revisions": source_revisions,
        "sources": sources,
    }

    return _RegistryView(
        facts=facts,
        relations=relations,
        conflicts=conflicts,
        fact_traceability=fact_traceability,
        relation_traceability=relation_traceability,
        registry_payload=registry_payload,
    )


def _load_fact_rows(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    return connection.execute(
        """
        SELECT
            fact_id,
            fact_identity_hash,
            fact_type,
            entity_name,
            canonical_entity_name,
            property_name,
            property_value,
            normalized_property_value,
            assertion_type,
            confidence,
            status,
            first_candidate_record_id
        FROM facts
        WHERE status IN (?, ?, ?, ?)
        ORDER BY canonical_entity_name, property_name, normalized_property_value, fact_id
        """,
        INCLUDED_FACT_STATUSES,
    ).fetchall()


def _load_relation_rows(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    return connection.execute(
        """
        SELECT
            relation_id,
            relation_identity_hash,
            source_entity,
            canonical_source_entity,
            relation_type,
            target_entity,
            canonical_target_entity,
            assertion_type,
            confidence,
            status,
            first_candidate_record_id
        FROM relations
        ORDER BY canonical_source_entity, relation_type, canonical_target_entity, relation_id
        """
    ).fetchall()


def _load_conflict_rows(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    return connection.execute(
        """
        SELECT
            conflict_id,
            conflict_key_hash,
            conflict_type,
            entity_name,
            canonical_entity_name,
            property_name,
            left_fact_id,
            right_fact_id,
            left_value,
            right_value,
            status
        FROM conflicts
        ORDER BY conflict_id
        """
    ).fetchall()


def _load_fact_evidence_rows(
    connection: sqlite3.Connection,
    fact_ids: list[str],
) -> list[sqlite3.Row]:
    if not fact_ids:
        return []
    return connection.execute(
        f"""
        SELECT
            fe.fact_id AS owner_id,
            fe.fact_id,
            fe.candidate_record_id,
            fe.source_revision_id,
            fe.chunk_id,
            fe.fragment_id,
            fe.evidence_text_hash,
            sr.source_id,
            sr.revision_number,
            sr.content_hash,
            sr.normalized_hash,
            sr.file_path,
            sr.file_size,
            sr.status AS source_revision_status,
            s.logical_name,
            s.source_type,
            s.source_subtype,
            s.authority_level,
            s.current_revision_id,
            s.status AS source_status
        FROM fact_evidence fe
        JOIN source_revisions sr
            ON sr.source_revision_id = fe.source_revision_id
        JOIN sources s
            ON s.source_id = sr.source_id
        WHERE fe.fact_id IN ({_placeholders(fact_ids)})
        ORDER BY fe.fact_id, fe.candidate_record_id
        """,
        fact_ids,
    ).fetchall()


def _load_relation_evidence_rows(
    connection: sqlite3.Connection,
    relation_ids: list[str],
) -> list[sqlite3.Row]:
    if not relation_ids:
        return []
    return connection.execute(
        f"""
        SELECT
            re.relation_id AS owner_id,
            re.relation_id,
            re.candidate_record_id,
            re.source_revision_id,
            re.chunk_id,
            re.fragment_id,
            re.evidence_text_hash,
            sr.source_id,
            sr.revision_number,
            sr.content_hash,
            sr.normalized_hash,
            sr.file_path,
            sr.file_size,
            sr.status AS source_revision_status,
            s.logical_name,
            s.source_type,
            s.source_subtype,
            s.authority_level,
            s.current_revision_id,
            s.status AS source_status
        FROM relation_evidence re
        JOIN source_revisions sr
            ON sr.source_revision_id = re.source_revision_id
        JOIN sources s
            ON s.source_id = sr.source_id
        WHERE re.relation_id IN ({_placeholders(relation_ids)})
        ORDER BY re.relation_id, re.candidate_record_id
        """,
        relation_ids,
    ).fetchall()


def _fact_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "assertion_type": row["assertion_type"],
        "canonical_entity_name": row["canonical_entity_name"],
        "confidence": row["confidence"],
        "entity_name": row["entity_name"],
        "fact_id": row["fact_id"],
        "fact_identity_hash": row["fact_identity_hash"],
        "fact_type": row["fact_type"],
        "first_candidate_record_id": row["first_candidate_record_id"],
        "normalized_property_value": row["normalized_property_value"],
        "property_name": row["property_name"],
        "property_value": row["property_value"],
        "status": row["status"],
    }


def _relation_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "assertion_type": row["assertion_type"],
        "canonical_source_entity": row["canonical_source_entity"],
        "canonical_target_entity": row["canonical_target_entity"],
        "confidence": row["confidence"],
        "first_candidate_record_id": row["first_candidate_record_id"],
        "relation_id": row["relation_id"],
        "relation_identity_hash": row["relation_identity_hash"],
        "relation_type": row["relation_type"],
        "source_entity": row["source_entity"],
        "status": row["status"],
        "target_entity": row["target_entity"],
    }


def _conflict_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "canonical_entity_name": row["canonical_entity_name"],
        "conflict_id": row["conflict_id"],
        "conflict_key_hash": row["conflict_key_hash"],
        "conflict_type": row["conflict_type"],
        "entity_name": row["entity_name"],
        "left_fact_id": row["left_fact_id"],
        "left_value": row["left_value"],
        "property_name": row["property_name"],
        "right_fact_id": row["right_fact_id"],
        "right_value": row["right_value"],
        "status": row["status"],
    }


def _build_dsl_content(registry: _RegistryView, *, registry_hash: str) -> dict[str, Any]:
    entities_by_canonical: dict[str, dict[str, Any]] = {}
    for fact in registry.facts:
        entity = entities_by_canonical.setdefault(
            fact["canonical_entity_name"],
            {
                "name": fact["entity_name"],
                "canonical_name": fact["canonical_entity_name"],
                "facts": [],
            },
        )
        entity["facts"].append(
            {
                "assertion_type": fact["assertion_type"],
                "confidence": fact["confidence"],
                "fact_id": fact["fact_id"],
                "fact_type": fact["fact_type"],
                "property_name": fact["property_name"],
                "property_value": fact["property_value"],
                "status": fact["status"],
            }
        )

    relations = [
        {
            "assertion_type": relation["assertion_type"],
            "canonical_source_entity": relation["canonical_source_entity"],
            "canonical_target_entity": relation["canonical_target_entity"],
            "confidence": relation["confidence"],
            "relation_id": relation["relation_id"],
            "relation_type": relation["relation_type"],
            "source_entity": relation["source_entity"],
            "status": relation["status"],
            "target_entity": relation["target_entity"],
        }
        for relation in registry.relations
    ]
    conflicts = [
        {
            "canonical_entity_name": conflict["canonical_entity_name"],
            "conflict_id": conflict["conflict_id"],
            "conflict_type": conflict["conflict_type"],
            "entity_name": conflict["entity_name"],
            "left_fact_id": conflict["left_fact_id"],
            "left_value": conflict["left_value"],
            "property_name": conflict["property_name"],
            "right_fact_id": conflict["right_fact_id"],
            "right_value": conflict["right_value"],
            "status": conflict["status"],
        }
        for conflict in registry.conflicts
    ]
    entities = list(entities_by_canonical.values())
    fact_traceability = {
        fact["fact_id"]: registry.fact_traceability.get(fact["fact_id"], [])
        for fact in registry.facts
    }
    relation_traceability = {
        relation["relation_id"]: registry.relation_traceability.get(relation["relation_id"], [])
        for relation in registry.relations
    }

    return {
        "metadata": {
            "schema_version": "1",
            "registry_hash": registry_hash,
            "counts": {
                "conflicts": len(conflicts),
                "entities": len(entities),
                "facts": len(registry.facts),
                "relations": len(relations),
            },
        },
        "entities": entities,
        "relations": relations,
        "conflicts": conflicts,
        "traceability": {
            "facts": fact_traceability,
            "relations": relation_traceability,
        },
    }


def _with_dsl_hash(content: dict[str, Any], dsl_hash: str) -> dict[str, Any]:
    content_with_hash = copy.deepcopy(content)
    metadata = content_with_hash["metadata"]
    content_with_hash["metadata"] = {
        "schema_version": metadata["schema_version"],
        "dsl_hash": dsl_hash,
        "registry_hash": metadata["registry_hash"],
        "counts": metadata["counts"],
    }
    return content_with_hash


def _hash_dsl_content(content: dict[str, Any]) -> str:
    content_for_hash = copy.deepcopy(content)
    content_for_hash.get("metadata", {}).pop("dsl_hash", None)
    return _stable_json_hash(content_for_hash)


def _stable_json_hash(payload: Any) -> str:
    text = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _traceability_by_owner(
    rows: list[sqlite3.Row],
    owner_column: str,
) -> dict[str, list[dict[str, Any]]]:
    traceability: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        traceability.setdefault(row[owner_column], []).append(_traceability_payload(row))
    return traceability


def _traceability_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "candidate_record_id": row["candidate_record_id"],
        "source_revision_id": row["source_revision_id"],
        "source_id": row["source_id"],
        "file_path": row["file_path"],
        "chunk_id": row["chunk_id"],
        "fragment_id": row["fragment_id"],
        "evidence_text_hash": row["evidence_text_hash"],
    }


def _evidence_registry_payload(row: sqlite3.Row, owner_column: str) -> dict[str, Any]:
    return {
        owner_column: row[owner_column],
        "candidate_record_id": row["candidate_record_id"],
        "chunk_id": row["chunk_id"],
        "evidence_text_hash": row["evidence_text_hash"],
        "fragment_id": row["fragment_id"],
        "source_revision_id": row["source_revision_id"],
    }


def _source_payloads(rows: list[sqlite3.Row]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    sources_by_id: dict[str, dict[str, Any]] = {}
    revisions_by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        sources_by_id[row["source_id"]] = {
            "authority_level": row["authority_level"],
            "current_revision_id": row["current_revision_id"],
            "logical_name": row["logical_name"],
            "source_id": row["source_id"],
            "source_status": row["source_status"],
            "source_subtype": row["source_subtype"],
            "source_type": row["source_type"],
        }
        revisions_by_id[row["source_revision_id"]] = {
            "content_hash": row["content_hash"],
            "file_path": row["file_path"],
            "file_size": row["file_size"],
            "normalized_hash": row["normalized_hash"],
            "revision_number": row["revision_number"],
            "source_id": row["source_id"],
            "source_revision_id": row["source_revision_id"],
            "source_revision_status": row["source_revision_status"],
        }

    return (
        [sources_by_id[source_id] for source_id in sorted(sources_by_id)],
        [revisions_by_id[revision_id] for revision_id in sorted(revisions_by_id)],
    )


def _placeholders(values: list[str]) -> str:
    return ", ".join("?" for _ in values)


def _count_facts(content: dict[str, Any]) -> int:
    return sum(len(entity["facts"]) for entity in content["entities"])


def _yaml_lines(value: Any, indent: int) -> list[str]:
    prefix = " " * indent
    if isinstance(value, dict):
        if not value:
            return [prefix + "{}"]
        lines: list[str] = []
        for key, child in value.items():
            if _yaml_inline(child):
                lines.append(f"{prefix}{key}: {_yaml_scalar(child)}")
            else:
                lines.append(f"{prefix}{key}:")
                lines.extend(_yaml_lines(child, indent + 2))
        return lines
    if isinstance(value, list):
        if not value:
            return [prefix + "[]"]
        lines = []
        for item in value:
            if _yaml_inline(item):
                lines.append(f"{prefix}- {_yaml_scalar(item)}")
            else:
                lines.append(f"{prefix}-")
                lines.extend(_yaml_lines(item, indent + 2))
        return lines
    return [prefix + _yaml_scalar(value)]


def _yaml_inline(value: Any) -> bool:
    return not isinstance(value, (dict, list)) or value in ({}, [])


def _yaml_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if value == {}:
        return "{}"
    if value == []:
        return "[]"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(str(value), ensure_ascii=False)


def _append_evidence_markdown(lines: list[str], evidence_items: list[dict[str, Any]]) -> None:
    if not evidence_items:
        lines.append("- none")
        return
    for evidence in evidence_items:
        fragment_id = evidence["fragment_id"] if evidence["fragment_id"] is not None else "null"
        chunk_id = evidence["chunk_id"] if evidence["chunk_id"] is not None else "null"
        lines.append(
            "- "
            f"`{evidence['candidate_record_id']}` revision `{evidence['source_revision_id']}`, "
            f"source `{evidence['source_id']}`, path `{evidence['file_path']}`, "
            f"chunk `{chunk_id}`, fragment `{fragment_id}`, "
            f"evidence `{evidence['evidence_text_hash']}`"
        )
