from __future__ import annotations

import copy
import json
import sqlite3
from dataclasses import dataclass
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
    relative_workspace_path,
    run_artifact_paths,
    validate_database_migrations,
    write_process_report,
)


CHANGE_TYPE_ORDER = (
    "added_entity",
    "removed_entity",
    "added_fact",
    "removed_fact",
    "modified_fact",
    "added_relation",
    "removed_relation",
    "modified_relation",
    "added_conflict",
    "removed_conflict",
    "modified_conflict",
)
CHANGE_TYPE_INDEX = {change_type: index for index, change_type in enumerate(CHANGE_TYPE_ORDER)}

FACT_COMPARE_FIELDS = ("property_value", "assertion_type", "confidence", "status")
RELATION_COMPARE_FIELDS = ("assertion_type", "confidence", "status")
CONFLICT_COMPARE_FIELDS = ("left_value", "right_value", "status")

CAUSE_REQUIRED_FIELDS = (
    "candidate_record_id",
    "source_revision_id",
    "source_id",
    "file_path",
    "evidence_text_hash",
)
CAUSE_ALL_FIELDS = (
    "owner_type",
    "owner_id",
    "candidate_record_id",
    "source_revision_id",
    "source_id",
    "file_path",
    "chunk_id",
    "fragment_id",
    "evidence_text_hash",
)


class DslDiffError(RuntimeError):
    """Raised when two DSL snapshots cannot be compared safely."""


class DslDiffDatabaseNotReadyError(DslDiffError):
    """Raised when DSL diff needs a migrated database."""


class MissingTraceabilityError(DslDiffError):
    """Raised when a semantic change cannot be traced back to evidence."""


@dataclass(frozen=True)
class DslDiffResult:
    run_id: str
    from_snapshot_id: str
    to_snapshot_id: str
    from_dsl_hash: str
    to_dsl_hash: str
    from_registry_hash: str
    to_registry_hash: str
    total_changes: int
    added_count: int
    removed_count: int
    modified_count: int
    output_dir: str
    json_path: str
    markdown_path: str

    def to_artifact_payload(self) -> dict[str, Any]:
        return {
            "added_count": self.added_count,
            "from_dsl_hash": self.from_dsl_hash,
            "from_registry_hash": self.from_registry_hash,
            "from_snapshot_id": self.from_snapshot_id,
            "json_path": self.json_path,
            "markdown_path": self.markdown_path,
            "modified_count": self.modified_count,
            "output_dir": self.output_dir,
            "removed_count": self.removed_count,
            "run_id": self.run_id,
            "to_dsl_hash": self.to_dsl_hash,
            "to_registry_hash": self.to_registry_hash,
            "to_snapshot_id": self.to_snapshot_id,
            "total_changes": self.total_changes,
        }


@dataclass(frozen=True)
class _Snapshot:
    snapshot_id: str
    dsl_hash: str
    registry_hash: str
    content: dict[str, Any]


@dataclass(frozen=True)
class _DiffPaths:
    json_file: Path
    markdown_file: Path
    json_path: str
    markdown_path: str


def ensure_dsl_diff_database_ready(workspace_dir: str | Path) -> DatabaseSettings:
    settings = resolve_database_settings(workspace_dir)
    if not settings.database_path.is_file():
        raise DslDiffDatabaseNotReadyError(
            f"Database is not initialized: {settings.database_path}. "
            "Run 'dsl-manager db init <workspace>' before 'dsl-manager dsl diff'."
        )

    connection = open_database(settings.database_path, enable_wal=settings.wal_enabled)
    try:
        try:
            validate_database_migrations(connection)
        except DatabaseNotReadyError as exc:
            message = str(exc).replace("dsl-manager run", "dsl-manager dsl diff")
            raise DslDiffDatabaseNotReadyError(message) from exc
    finally:
        connection.close()
    return settings


def diff_dsl_snapshots(
    workspace_dir: str | Path,
    *,
    run_id: str,
    from_snapshot_id: str,
    to_snapshot_id: str,
    output_dir: str | Path | None = None,
) -> DslDiffResult:
    settings = ensure_dsl_diff_database_ready(workspace_dir)
    export_dir = _resolve_output_dir(settings.workspace_dir, output_dir)
    paths = _diff_paths(settings.workspace_dir, export_dir, from_snapshot_id, to_snapshot_id)

    connection = open_database(settings.database_path, enable_wal=settings.wal_enabled)
    try:
        validate_database_migrations(connection)
        from_snapshot = _load_snapshot(connection, from_snapshot_id)
        to_snapshot = _load_snapshot(connection, to_snapshot_id)
    finally:
        connection.close()

    diff_payload = build_dsl_diff(from_snapshot, to_snapshot)
    markdown = render_dsl_diff_markdown(diff_payload)

    export_dir.mkdir(parents=True, exist_ok=True)
    paths.json_file.write_text(canonical_json(diff_payload), encoding="utf-8", newline="\n")
    paths.markdown_file.write_text(markdown, encoding="utf-8", newline="\n")

    summary = diff_payload["summary"]
    return DslDiffResult(
        run_id=run_id,
        from_snapshot_id=from_snapshot.snapshot_id,
        to_snapshot_id=to_snapshot.snapshot_id,
        from_dsl_hash=from_snapshot.dsl_hash,
        to_dsl_hash=to_snapshot.dsl_hash,
        from_registry_hash=from_snapshot.registry_hash,
        to_registry_hash=to_snapshot.registry_hash,
        total_changes=summary["total_changes"],
        added_count=summary["added"],
        removed_count=summary["removed"],
        modified_count=summary["modified"],
        output_dir=relative_workspace_path(settings.workspace_dir, export_dir),
        json_path=paths.json_path,
        markdown_path=paths.markdown_path,
    )


def build_dsl_diff(from_snapshot: _Snapshot, to_snapshot: _Snapshot) -> dict[str, Any]:
    from_entities = _entities_by_key(from_snapshot.content)
    to_entities = _entities_by_key(to_snapshot.content)

    if from_snapshot.dsl_hash == to_snapshot.dsl_hash:
        raw_changes: list[dict[str, Any]] = []
    else:
        raw_changes = []
        raw_changes.extend(_diff_entities(from_snapshot, to_snapshot, from_entities, to_entities))
        common_entity_keys = sorted(set(from_entities).intersection(to_entities))
        raw_changes.extend(_diff_facts(from_snapshot, to_snapshot, common_entity_keys))
        raw_changes.extend(_diff_relations(from_snapshot, to_snapshot))
        raw_changes.extend(_diff_conflicts(from_snapshot, to_snapshot))

    summary = _build_summary(raw_changes)
    changes = _finalize_changes(raw_changes)
    return {
        "metadata": {
            "schema_version": "1",
            "from_snapshot_id": from_snapshot.snapshot_id,
            "to_snapshot_id": to_snapshot.snapshot_id,
            "from_dsl_hash": from_snapshot.dsl_hash,
            "to_dsl_hash": to_snapshot.dsl_hash,
            "from_registry_hash": from_snapshot.registry_hash,
            "to_registry_hash": to_snapshot.registry_hash,
            "has_changes": bool(changes),
        },
        "summary": summary,
        "changes": changes,
    }


def write_dsl_diff_artifacts(workspace_dir: str | Path, result: DslDiffResult) -> None:
    artifacts = run_artifact_paths(workspace_dir, result.run_id)
    payload = result.to_artifact_payload()
    input_document = {
        "artifact_dir": artifacts.artifact_dir_relative,
        "parameters": {
            "from_snapshot_id": result.from_snapshot_id,
            "output_dir": result.output_dir,
            "to_snapshot_id": result.to_snapshot_id,
        },
        "run_id": result.run_id,
        "run_type": "dsl_diff",
        **payload,
    }
    artifacts.input_path.write_text(canonical_json(input_document), encoding="utf-8", newline="\n")

    report = json.loads(artifacts.process_report_path.read_text(encoding="utf-8"))
    report.update(payload)
    write_process_report(artifacts.process_report_path, report)


def render_dsl_diff_markdown(diff_payload: dict[str, Any]) -> str:
    metadata = diff_payload["metadata"]
    summary = diff_payload["summary"]
    lines = [
        "# DSL Diff",
        "",
        "## Snapshots",
        f"- from: `{metadata['from_snapshot_id']}` (`{metadata['from_dsl_hash']}`)",
        f"- to: `{metadata['to_snapshot_id']}` (`{metadata['to_dsl_hash']}`)",
        f"- from_registry_hash: `{metadata['from_registry_hash']}`",
        f"- to_registry_hash: `{metadata['to_registry_hash']}`",
        f"- has_changes: `{str(metadata['has_changes']).lower()}`",
        "",
        "## Summary",
        f"- total_changes: `{summary['total_changes']}`",
        f"- added: `{summary['added']}`",
        f"- removed: `{summary['removed']}`",
        f"- modified: `{summary['modified']}`",
        (
            "- entities: "
            f"added `{summary['entities']['added']}`, "
            f"removed `{summary['entities']['removed']}`, "
            f"modified `{summary['entities']['modified']}`"
        ),
        (
            "- facts: "
            f"added `{summary['facts']['added']}`, "
            f"removed `{summary['facts']['removed']}`, "
            f"modified `{summary['facts']['modified']}`"
        ),
        (
            "- relations: "
            f"added `{summary['relations']['added']}`, "
            f"removed `{summary['relations']['removed']}`, "
            f"modified `{summary['relations']['modified']}`"
        ),
        (
            "- conflicts: "
            f"added `{summary['conflicts']['added']}`, "
            f"removed `{summary['conflicts']['removed']}`, "
            f"modified `{summary['conflicts']['modified']}`"
        ),
        "",
        "## Changes",
    ]

    changes = diff_payload["changes"]
    if not changes:
        lines.append("- none")
        return "\n".join(lines) + "\n"

    changes_by_type: dict[str, list[dict[str, Any]]] = {
        change_type: [] for change_type in CHANGE_TYPE_ORDER
    }
    for change in changes:
        changes_by_type.setdefault(change["change_type"], []).append(change)

    for change_type in CHANGE_TYPE_ORDER:
        typed_changes = changes_by_type.get(change_type, [])
        if not typed_changes:
            continue
        lines.extend(["", f"### {change_type}"])
        for change in typed_changes:
            lines.extend(["", f"#### {change['change_id']} {change['path']}"])
            lines.append(f"- before: {_markdown_json_value(change['before'])}")
            lines.append(f"- after: {_markdown_json_value(change['after'])}")
            lines.append("- causes:")
            for cause in change["causes"]:
                chunk_id = "null" if cause["chunk_id"] is None else cause["chunk_id"]
                fragment_id = "null" if cause["fragment_id"] is None else cause["fragment_id"]
                lines.append(
                    "  - "
                    f"{cause['side']} {cause['owner_type']} `{cause['owner_id']}`, "
                    f"candidate `{cause['candidate_record_id']}`, "
                    f"revision `{cause['source_revision_id']}`, "
                    f"source `{cause['source_id']}`, "
                    f"path `{cause['file_path']}`, "
                    f"chunk `{chunk_id}`, fragment `{fragment_id}`, "
                    f"evidence `{cause['evidence_text_hash']}`"
                )

    return "\n".join(lines) + "\n"


def _resolve_output_dir(workspace_dir: Path, output_dir: str | Path | None) -> Path:
    configured = "exports/dsl_diff" if output_dir is None else output_dir
    try:
        return resolve_workspace_path(workspace_dir, configured)
    except DatabaseConfigurationError as exc:
        raise DslDiffError(f"Output path escapes the workspace: {output_dir}") from exc


def _diff_paths(
    workspace_dir: Path,
    output_dir: Path,
    from_snapshot_id: str,
    to_snapshot_id: str,
) -> _DiffPaths:
    file_stem = f"{from_snapshot_id}__{to_snapshot_id}"
    json_file = output_dir / f"{file_stem}.json"
    markdown_file = output_dir / f"{file_stem}.md"
    return _DiffPaths(
        json_file=json_file,
        markdown_file=markdown_file,
        json_path=relative_workspace_path(workspace_dir, json_file),
        markdown_path=relative_workspace_path(workspace_dir, markdown_file),
    )


def _load_snapshot(connection: sqlite3.Connection, snapshot_id: str) -> _Snapshot:
    row = connection.execute(
        """
        SELECT snapshot_id, dsl_hash, content_json
        FROM dsl_snapshots
        WHERE snapshot_id = ?
        """,
        (snapshot_id,),
    ).fetchone()
    if row is None:
        raise DslDiffError(f"Snapshot not found: {snapshot_id}.")

    try:
        content = json.loads(row["content_json"])
    except json.JSONDecodeError as exc:
        raise DslDiffError(f"Snapshot {snapshot_id} content_json is not valid JSON.") from exc
    if not isinstance(content, dict):
        raise DslDiffError(f"Snapshot {snapshot_id} content_json must be a JSON object.")

    metadata = content.get("metadata")
    if not isinstance(metadata, dict):
        raise DslDiffError(f"Snapshot {snapshot_id} is missing metadata.")

    metadata_dsl_hash = metadata.get("dsl_hash")
    if metadata_dsl_hash != row["dsl_hash"]:
        raise DslDiffError(
            f"Snapshot {snapshot_id} metadata.dsl_hash does not match dsl_snapshots.dsl_hash."
        )

    registry_hash = metadata.get("registry_hash")
    if not isinstance(registry_hash, str):
        raise DslDiffError(f"Snapshot {snapshot_id} metadata.registry_hash is missing.")

    _validate_dsl_sections(snapshot_id, content)
    return _Snapshot(
        snapshot_id=row["snapshot_id"],
        dsl_hash=row["dsl_hash"],
        registry_hash=registry_hash,
        content=content,
    )


def _validate_dsl_sections(snapshot_id: str, content: dict[str, Any]) -> None:
    for section_name in ("entities", "relations", "conflicts"):
        if not isinstance(content.get(section_name), list):
            raise DslDiffError(f"Snapshot {snapshot_id} section {section_name} must be a list.")
    traceability = content.get("traceability")
    if not isinstance(traceability, dict):
        raise DslDiffError(f"Snapshot {snapshot_id} is missing traceability.")
    for section_name in ("facts", "relations"):
        if not isinstance(traceability.get(section_name), dict):
            raise DslDiffError(
                f"Snapshot {snapshot_id} traceability.{section_name} must be an object."
            )


def _diff_entities(
    from_snapshot: _Snapshot,
    to_snapshot: _Snapshot,
    from_entities: dict[str, dict[str, Any]],
    to_entities: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    for canonical_name in sorted(set(to_entities) - set(from_entities)):
        entity = to_entities[canonical_name]
        change = {
            "change_type": "added_entity",
            "path": _entity_path(canonical_name),
            "before": None,
            "after": _entity_identity(entity),
            "causes": _causes_for_entity(to_snapshot, "after", entity),
            "_facts_added": len(entity["facts"]),
            "_stable_id": canonical_name,
        }
        _require_causes(change)
        changes.append(change)

    for canonical_name in sorted(set(from_entities) - set(to_entities)):
        entity = from_entities[canonical_name]
        change = {
            "change_type": "removed_entity",
            "path": _entity_path(canonical_name),
            "before": _entity_identity(entity),
            "after": None,
            "causes": _causes_for_entity(from_snapshot, "before", entity),
            "_facts_removed": len(entity["facts"]),
            "_stable_id": canonical_name,
        }
        _require_causes(change)
        changes.append(change)
    return changes


def _diff_facts(
    from_snapshot: _Snapshot,
    to_snapshot: _Snapshot,
    common_entity_keys: list[str],
) -> list[dict[str, Any]]:
    from_facts = _facts_by_key(from_snapshot.content, common_entity_keys)
    to_facts = _facts_by_key(to_snapshot.content, common_entity_keys)
    changes: list[dict[str, Any]] = []

    for key in sorted(set(from_facts).union(to_facts)):
        before_group = _sort_facts(from_facts.get(key, []))
        after_group = _sort_facts(to_facts.get(key, []))
        path = _fact_path(key)

        if not before_group:
            for fact in after_group:
                changes.append(_added_fact_change(to_snapshot, key, path, fact))
            continue
        if not after_group:
            for fact in before_group:
                changes.append(_removed_fact_change(from_snapshot, key, path, fact))
            continue
        if len(before_group) == 1 and len(after_group) == 1:
            before_fact = before_group[0]
            after_fact = after_group[0]
            if _changed(before_fact, after_fact, FACT_COMPARE_FIELDS):
                change = {
                    "change_type": "modified_fact",
                    "path": path,
                    "before": _fact_output(key[0], before_fact),
                    "after": _fact_output(key[0], after_fact),
                    "causes": [
                        *_causes_for_fact(from_snapshot, "before", before_fact),
                        *_causes_for_fact(to_snapshot, "after", after_fact),
                    ],
                    "_stable_id": f"{before_fact['fact_id']}->{after_fact['fact_id']}",
                }
                _require_causes(change)
                changes.append(change)
            continue

        if _semantic_signatures(before_group, FACT_COMPARE_FIELDS) == _semantic_signatures(
            after_group,
            FACT_COMPARE_FIELDS,
        ):
            continue
        for fact in before_group:
            changes.append(_removed_fact_change(from_snapshot, key, path, fact))
        for fact in after_group:
            changes.append(_added_fact_change(to_snapshot, key, path, fact))

    return changes


def _diff_relations(from_snapshot: _Snapshot, to_snapshot: _Snapshot) -> list[dict[str, Any]]:
    from_relations = _relations_by_key(from_snapshot.content)
    to_relations = _relations_by_key(to_snapshot.content)
    changes: list[dict[str, Any]] = []

    for key in sorted(set(from_relations).union(to_relations)):
        before_group = _sort_relations(from_relations.get(key, []))
        after_group = _sort_relations(to_relations.get(key, []))
        path = _relation_path(key)

        if not before_group:
            for relation in after_group:
                changes.append(_added_relation_change(to_snapshot, path, relation))
            continue
        if not after_group:
            for relation in before_group:
                changes.append(_removed_relation_change(from_snapshot, path, relation))
            continue
        if len(before_group) == 1 and len(after_group) == 1:
            before_relation = before_group[0]
            after_relation = after_group[0]
            if _changed(before_relation, after_relation, RELATION_COMPARE_FIELDS):
                change = {
                    "change_type": "modified_relation",
                    "path": path,
                    "before": _public_copy(before_relation),
                    "after": _public_copy(after_relation),
                    "causes": [
                        *_causes_for_relation(from_snapshot, "before", before_relation),
                        *_causes_for_relation(to_snapshot, "after", after_relation),
                    ],
                    "_stable_id": (
                        f"{before_relation['relation_id']}->{after_relation['relation_id']}"
                    ),
                }
                _require_causes(change)
                changes.append(change)
            continue

        if _semantic_signatures(before_group, RELATION_COMPARE_FIELDS) == _semantic_signatures(
            after_group,
            RELATION_COMPARE_FIELDS,
        ):
            continue
        for relation in before_group:
            changes.append(_removed_relation_change(from_snapshot, path, relation))
        for relation in after_group:
            changes.append(_added_relation_change(to_snapshot, path, relation))

    return changes


def _diff_conflicts(from_snapshot: _Snapshot, to_snapshot: _Snapshot) -> list[dict[str, Any]]:
    from_conflicts = _conflicts_by_key(from_snapshot.content)
    to_conflicts = _conflicts_by_key(to_snapshot.content)
    changes: list[dict[str, Any]] = []

    for key in sorted(set(from_conflicts).union(to_conflicts)):
        before_group = _sort_conflicts(from_conflicts.get(key, []))
        after_group = _sort_conflicts(to_conflicts.get(key, []))
        path = _conflict_path(key)

        if not before_group:
            for conflict in after_group:
                changes.append(_added_conflict_change(to_snapshot, path, conflict))
            continue
        if not after_group:
            for conflict in before_group:
                changes.append(_removed_conflict_change(from_snapshot, path, conflict))
            continue
        if len(before_group) == 1 and len(after_group) == 1:
            before_conflict = before_group[0]
            after_conflict = after_group[0]
            if _changed(before_conflict, after_conflict, CONFLICT_COMPARE_FIELDS):
                change = {
                    "change_type": "modified_conflict",
                    "path": path,
                    "before": _public_copy(before_conflict),
                    "after": _public_copy(after_conflict),
                    "causes": [
                        *_causes_for_conflict(from_snapshot, "before", before_conflict),
                        *_causes_for_conflict(to_snapshot, "after", after_conflict),
                    ],
                    "_stable_id": (
                        f"{before_conflict['conflict_id']}->{after_conflict['conflict_id']}"
                    ),
                }
                _require_causes(change)
                changes.append(change)
            continue

        if _semantic_signatures(before_group, CONFLICT_COMPARE_FIELDS) == _semantic_signatures(
            after_group,
            CONFLICT_COMPARE_FIELDS,
        ):
            continue
        for conflict in before_group:
            changes.append(_removed_conflict_change(from_snapshot, path, conflict))
        for conflict in after_group:
            changes.append(_added_conflict_change(to_snapshot, path, conflict))

    return changes


def _added_fact_change(
    snapshot: _Snapshot,
    key: tuple[str, str, str],
    path: str,
    fact: dict[str, Any],
) -> dict[str, Any]:
    change = {
        "change_type": "added_fact",
        "path": _path_with_owner(path, fact["fact_id"]),
        "before": None,
        "after": _fact_output(key[0], fact),
        "causes": _causes_for_fact(snapshot, "after", fact),
        "_stable_id": fact["fact_id"],
    }
    _require_causes(change)
    return change


def _removed_fact_change(
    snapshot: _Snapshot,
    key: tuple[str, str, str],
    path: str,
    fact: dict[str, Any],
) -> dict[str, Any]:
    change = {
        "change_type": "removed_fact",
        "path": _path_with_owner(path, fact["fact_id"]),
        "before": _fact_output(key[0], fact),
        "after": None,
        "causes": _causes_for_fact(snapshot, "before", fact),
        "_stable_id": fact["fact_id"],
    }
    _require_causes(change)
    return change


def _added_relation_change(
    snapshot: _Snapshot,
    path: str,
    relation: dict[str, Any],
) -> dict[str, Any]:
    change = {
        "change_type": "added_relation",
        "path": _path_with_owner(path, relation["relation_id"]),
        "before": None,
        "after": _public_copy(relation),
        "causes": _causes_for_relation(snapshot, "after", relation),
        "_stable_id": relation["relation_id"],
    }
    _require_causes(change)
    return change


def _removed_relation_change(
    snapshot: _Snapshot,
    path: str,
    relation: dict[str, Any],
) -> dict[str, Any]:
    change = {
        "change_type": "removed_relation",
        "path": _path_with_owner(path, relation["relation_id"]),
        "before": _public_copy(relation),
        "after": None,
        "causes": _causes_for_relation(snapshot, "before", relation),
        "_stable_id": relation["relation_id"],
    }
    _require_causes(change)
    return change


def _added_conflict_change(
    snapshot: _Snapshot,
    path: str,
    conflict: dict[str, Any],
) -> dict[str, Any]:
    change = {
        "change_type": "added_conflict",
        "path": _path_with_owner(path, conflict["conflict_id"]),
        "before": None,
        "after": _public_copy(conflict),
        "causes": _causes_for_conflict(snapshot, "after", conflict),
        "_stable_id": conflict["conflict_id"],
    }
    _require_causes(change)
    return change


def _removed_conflict_change(
    snapshot: _Snapshot,
    path: str,
    conflict: dict[str, Any],
) -> dict[str, Any]:
    change = {
        "change_type": "removed_conflict",
        "path": _path_with_owner(path, conflict["conflict_id"]),
        "before": _public_copy(conflict),
        "after": None,
        "causes": _causes_for_conflict(snapshot, "before", conflict),
        "_stable_id": conflict["conflict_id"],
    }
    _require_causes(change)
    return change


def _entities_by_key(content: dict[str, Any]) -> dict[str, dict[str, Any]]:
    entities: dict[str, dict[str, Any]] = {}
    for raw_entity in content["entities"]:
        if not isinstance(raw_entity, dict):
            raise DslDiffError("DSL entity items must be objects.")
        canonical_name = _required_string(raw_entity, "canonical_name", "entity")
        facts = raw_entity.get("facts", [])
        if not isinstance(facts, list):
            raise DslDiffError(f"Entity {canonical_name} facts must be a list.")
        entity = copy.deepcopy(raw_entity)
        entity["facts"] = facts
        entities[canonical_name] = entity
    return entities


def _facts_by_key(
    content: dict[str, Any],
    allowed_entity_keys: list[str],
) -> dict[tuple[str, str, str], list[dict[str, Any]]]:
    allowed = set(allowed_entity_keys)
    facts: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for entity in _entities_by_key(content).values():
        canonical_entity = entity["canonical_name"]
        if canonical_entity not in allowed:
            continue
        for raw_fact in entity["facts"]:
            if not isinstance(raw_fact, dict):
                raise DslDiffError(f"Entity {canonical_entity} fact items must be objects.")
            key = (
                canonical_entity,
                _required_string(raw_fact, "fact_type", "fact"),
                _required_string(raw_fact, "property_name", "fact"),
            )
            facts.setdefault(key, []).append(copy.deepcopy(raw_fact))
    return facts


def _relations_by_key(content: dict[str, Any]) -> dict[tuple[str, str, str], list[dict[str, Any]]]:
    relations: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for raw_relation in content["relations"]:
        if not isinstance(raw_relation, dict):
            raise DslDiffError("DSL relation items must be objects.")
        key = (
            _required_string(raw_relation, "canonical_source_entity", "relation"),
            _required_string(raw_relation, "relation_type", "relation"),
            _required_string(raw_relation, "canonical_target_entity", "relation"),
        )
        relations.setdefault(key, []).append(copy.deepcopy(raw_relation))
    return relations


def _conflicts_by_key(
    content: dict[str, Any],
) -> dict[tuple[str, str, str, str, str], list[dict[str, Any]]]:
    conflicts: dict[tuple[str, str, str, str, str], list[dict[str, Any]]] = {}
    for raw_conflict in content["conflicts"]:
        if not isinstance(raw_conflict, dict):
            raise DslDiffError("DSL conflict items must be objects.")
        key = (
            _required_string(raw_conflict, "conflict_type", "conflict"),
            _required_string(raw_conflict, "canonical_entity_name", "conflict"),
            _required_string(raw_conflict, "property_name", "conflict"),
            _required_string(raw_conflict, "left_fact_id", "conflict"),
            _required_string(raw_conflict, "right_fact_id", "conflict"),
        )
        conflicts.setdefault(key, []).append(copy.deepcopy(raw_conflict))
    return conflicts


def _causes_for_entity(
    snapshot: _Snapshot,
    side: str,
    entity: dict[str, Any],
) -> list[dict[str, Any]]:
    causes: list[dict[str, Any]] = []
    for fact in _sort_facts(entity["facts"]):
        causes.extend(_causes_for_fact(snapshot, side, fact))
    return _sort_causes(causes)


def _causes_for_fact(
    snapshot: _Snapshot,
    side: str,
    fact: dict[str, Any],
) -> list[dict[str, Any]]:
    fact_id = _required_string(fact, "fact_id", "fact")
    evidence_items = snapshot.content["traceability"]["facts"].get(fact_id, [])
    if not isinstance(evidence_items, list):
        raise MissingTraceabilityError(
            f"missing_traceability: traceability.facts[{fact_id}] must be a list."
        )
    return _sort_causes(
        [_cause(side, "fact", fact_id, evidence) for evidence in evidence_items]
    )


def _causes_for_relation(
    snapshot: _Snapshot,
    side: str,
    relation: dict[str, Any],
) -> list[dict[str, Any]]:
    relation_id = _required_string(relation, "relation_id", "relation")
    evidence_items = snapshot.content["traceability"]["relations"].get(relation_id, [])
    if not isinstance(evidence_items, list):
        raise MissingTraceabilityError(
            f"missing_traceability: traceability.relations[{relation_id}] must be a list."
        )
    return _sort_causes(
        [_cause(side, "relation", relation_id, evidence) for evidence in evidence_items]
    )


def _causes_for_conflict(
    snapshot: _Snapshot,
    side: str,
    conflict: dict[str, Any],
) -> list[dict[str, Any]]:
    causes: list[dict[str, Any]] = []
    seen_fact_ids: set[str] = set()
    for key in ("left_fact_id", "right_fact_id"):
        fact_id = _required_string(conflict, key, "conflict")
        if fact_id in seen_fact_ids:
            continue
        seen_fact_ids.add(fact_id)
        evidence_items = snapshot.content["traceability"]["facts"].get(fact_id, [])
        if not isinstance(evidence_items, list):
            raise MissingTraceabilityError(
                f"missing_traceability: traceability.facts[{fact_id}] must be a list."
            )
        causes.extend(_cause(side, "fact", fact_id, evidence) for evidence in evidence_items)
    return _sort_causes(causes)


def _cause(
    side: str,
    owner_type: str,
    owner_id: str,
    evidence: Any,
) -> dict[str, Any]:
    if not isinstance(evidence, dict):
        raise MissingTraceabilityError(
            f"missing_traceability: {side} {owner_type} {owner_id} evidence must be an object."
        )
    for field in CAUSE_REQUIRED_FIELDS:
        if evidence.get(field) in (None, ""):
            raise MissingTraceabilityError(
                f"missing_traceability: {side} {owner_type} {owner_id} evidence "
                f"is missing {field}."
            )
    cause = {
        "side": side,
        "owner_type": owner_type,
        "owner_id": owner_id,
        "candidate_record_id": evidence["candidate_record_id"],
        "source_revision_id": evidence["source_revision_id"],
        "source_id": evidence["source_id"],
        "file_path": evidence["file_path"],
        "chunk_id": evidence.get("chunk_id"),
        "fragment_id": evidence.get("fragment_id"),
        "evidence_text_hash": evidence["evidence_text_hash"],
    }
    for field in CAUSE_ALL_FIELDS:
        if field not in cause:
            raise MissingTraceabilityError(
                f"missing_traceability: {side} {owner_type} {owner_id} cause "
                f"is missing {field}."
            )
    return cause


def _require_causes(change: dict[str, Any]) -> None:
    causes = _sort_causes(change.get("causes", []))
    if not causes:
        raise MissingTraceabilityError(
            f"missing_traceability: {change['change_type']} at {change['path']} "
            "has no traceability causes."
        )
    change["causes"] = causes


def _build_summary(changes: list[dict[str, Any]]) -> dict[str, Any]:
    summary = {
        "total_changes": len(changes),
        "added": 0,
        "removed": 0,
        "modified": 0,
        "entities": {"added": 0, "removed": 0, "modified": 0},
        "facts": {"added": 0, "removed": 0, "modified": 0},
        "relations": {"added": 0, "removed": 0, "modified": 0},
        "conflicts": {"added": 0, "removed": 0, "modified": 0},
    }

    for change in changes:
        action, area = change["change_type"].split("_", 1)
        summary[action] += 1
        if area == "entity":
            summary["entities"][action] += 1
            summary["facts"]["added"] += change.get("_facts_added", 0)
            summary["facts"]["removed"] += change.get("_facts_removed", 0)
        elif area == "fact":
            summary["facts"][action] += 1
        elif area == "relation":
            summary["relations"][action] += 1
        elif area == "conflict":
            summary["conflicts"][action] += 1
    return summary


def _finalize_changes(changes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sorted_changes = sorted(
        changes,
        key=lambda change: (
            CHANGE_TYPE_INDEX.get(change["change_type"], len(CHANGE_TYPE_ORDER)),
            change["path"],
            change.get("_stable_id", ""),
        ),
    )
    final_changes: list[dict[str, Any]] = []
    for index, change in enumerate(sorted_changes, start=1):
        public_change = {
            key: value for key, value in change.items() if not key.startswith("_")
        }
        public_change["causes"] = _sort_causes(public_change["causes"])
        public_change = {
            "change_id": f"CHG_{index:06d}",
            "change_type": public_change["change_type"],
            "path": public_change["path"],
            "before": public_change["before"],
            "after": public_change["after"],
            "causes": public_change["causes"],
        }
        final_changes.append(public_change)
    return final_changes


def _sort_causes(causes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    side_order = {"before": 0, "after": 1}
    return sorted(
        causes,
        key=lambda cause: (
            side_order.get(cause.get("side"), 9),
            cause.get("owner_type") or "",
            cause.get("owner_id") or "",
            cause.get("candidate_record_id") or "",
            cause.get("source_revision_id") or "",
            cause.get("source_id") or "",
            cause.get("file_path") or "",
            cause.get("chunk_id") or "",
            cause.get("fragment_id") or "",
            cause.get("evidence_text_hash") or "",
        ),
    )


def _entity_identity(entity: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": _required_string(entity, "name", "entity"),
        "canonical_name": _required_string(entity, "canonical_name", "entity"),
    }


def _fact_output(canonical_entity_name: str, fact: dict[str, Any]) -> dict[str, Any]:
    output = _public_copy(fact)
    output["canonical_entity_name"] = canonical_entity_name
    return output


def _public_copy(value: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(value)


def _changed(before: dict[str, Any], after: dict[str, Any], fields: tuple[str, ...]) -> bool:
    return any(before.get(field) != after.get(field) for field in fields)


def _semantic_signatures(
    values: list[dict[str, Any]],
    compare_fields: tuple[str, ...],
) -> list[tuple[Any, ...]]:
    return sorted(tuple(value.get(field) for field in compare_fields) for value in values)


def _sort_facts(facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        facts,
        key=lambda fact: (
            fact.get("fact_type") or "",
            fact.get("property_name") or "",
            fact.get("property_value") or "",
            fact.get("assertion_type") or "",
            fact.get("confidence") or "",
            fact.get("status") or "",
            fact.get("fact_id") or "",
        ),
    )


def _sort_relations(relations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        relations,
        key=lambda relation: (
            relation.get("canonical_source_entity") or "",
            relation.get("relation_type") or "",
            relation.get("canonical_target_entity") or "",
            relation.get("assertion_type") or "",
            relation.get("confidence") or "",
            relation.get("status") or "",
            relation.get("relation_id") or "",
        ),
    )


def _sort_conflicts(conflicts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        conflicts,
        key=lambda conflict: (
            conflict.get("conflict_type") or "",
            conflict.get("canonical_entity_name") or "",
            conflict.get("property_name") or "",
            conflict.get("left_fact_id") or "",
            conflict.get("right_fact_id") or "",
            conflict.get("status") or "",
            conflict.get("conflict_id") or "",
        ),
    )


def _entity_path(canonical_name: str) -> str:
    return f"entities[{canonical_name}]"


def _fact_path(key: tuple[str, str, str]) -> str:
    canonical_entity, fact_type, property_name = key
    return f"entities[{canonical_entity}].facts[{fact_type}.{property_name}]"


def _relation_path(key: tuple[str, str, str]) -> str:
    source_entity, relation_type, target_entity = key
    return f"relations[{source_entity}.{relation_type}.{target_entity}]"


def _conflict_path(key: tuple[str, str, str, str, str]) -> str:
    conflict_type, canonical_entity, property_name, left_fact_id, right_fact_id = key
    return (
        f"conflicts[{conflict_type}.{canonical_entity}.{property_name}."
        f"{left_fact_id}.{right_fact_id}]"
    )


def _path_with_owner(path: str, owner_id: str) -> str:
    return f"{path}#{owner_id}"


def _required_string(value: dict[str, Any], key: str, context: str) -> str:
    raw_value = value.get(key)
    if not isinstance(raw_value, str) or raw_value == "":
        raise DslDiffError(f"DSL {context} is missing {key}.")
    return raw_value


def _markdown_json_value(value: Any) -> str:
    if value is None:
        return "`null`"
    return "`" + json.dumps(value, ensure_ascii=False, sort_keys=True) + "`"
