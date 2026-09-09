from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from dsl_mngr.core.candidate_import import CandidateImportResult, import_candidate_file
from dsl_mngr.core.canonical import (
    canonical_json_artifact_v1,
    canonical_json_v1,
    canonical_sha256_v1,
)
from dsl_mngr.core.database import (
    DatabaseConfigurationError,
    open_database,
    resolve_database_settings,
    resolve_workspace_path,
)
from dsl_mngr.core.runs import (
    next_id,
    relative_workspace_path,
    run_artifact_paths,
    timestamp_now,
    validate_database_migrations,
)
from dsl_mngr.core.workbook_regions import (
    CellRange,
    WorkbookRegionError,
    parse_cell_range,
    parse_cell_reference,
)


RULE_ID = "ddl_table_fact"
RULE_VERSION = "1"
RULE_NAME = f"{RULE_ID}/{RULE_VERSION}"


@dataclass(frozen=True)
class DerivationRule:
    rule_id: str
    rule_version: str
    parser_kind: str
    input_fragment_type: str
    input_schema: str
    candidate_record_type: str
    assertion_type: str
    evidence_locator: str
    automatic_review_allowed: bool
    automatic_review_policy: str
    default_review_state: str = "pending"


def _rule(
    name: str,
    parser: str,
    fragment_type: str,
    record_type: str,
    assertion: str,
    *,
    policy: str,
    automatic_review_allowed: bool = True,
    evidence_locator: str = (
        "source_revision_id+fragment_id+path_or_selector+line_start+line_end"
    ),
) -> DerivationRule:
    rule_id, rule_version = name.split("/", 1)
    return DerivationRule(
        rule_id=rule_id,
        rule_version=rule_version,
        parser_kind=parser,
        input_fragment_type=fragment_type,
        input_schema=f"source_fragment/{fragment_type}/1",
        candidate_record_type=record_type,
        assertion_type=assertion,
        evidence_locator=evidence_locator,
        automatic_review_allowed=automatic_review_allowed,
        automatic_review_policy=policy,
    )


DERIVATION_RULE_CATALOG: dict[str, DerivationRule] = {
    RULE_NAME: _rule(
        RULE_NAME,
        "ddl",
        "ddl_table",
        "candidate_fact",
        "explicit",
        policy="explicit_ddl_table_only/1",
    ),
    "ddl_column_fact/1": _rule(
        "ddl_column_fact/1", "ddl", "ddl_column", "candidate_fact", "explicit",
        policy="explicit_ddl_column_only/1",
    ),
    "ddl_fk_relation/1": _rule(
        "ddl_fk_relation/1", "ddl", "ddl_constraint", "candidate_relation", "explicit",
        policy="explicit_resolved_ddl_fk_only/1",
    ),
    "xml_form_structure/1": _rule(
        "xml_form_structure/1", "xml_form", "xml_form|xml_field|xml_button", "candidate_fact", "explicit",
        policy="explicit_xml_form_structure_only/1",
    ),
    "xml_table_usage/1": _rule(
        "xml_table_usage/1", "xml_form", "xml_form", "candidate_relation", "explicit",
        policy="explicit_xml_operation_only/1",
    ),
    "db_code_unit/1": _rule(
        "db_code_unit/1", "db_code", "sql_function|sql_procedure|sql_trigger", "candidate_fact", "explicit",
        policy="explicit_db_code_unit_only/1",
    ),
    "db_code_dependency/1": _rule(
        "db_code_dependency/1", "db_code", "sql_function|sql_procedure|sql_trigger", "candidate_relation", "observed",
        policy="observed_db_code_dependency_only/1",
    ),
    "log_event_observation/1": _rule(
        "log_event_observation/1", "log", "log_event", "candidate_fact", "observed",
        policy="named_explicit_log_policy_required/1",
    ),
}


EXCEL_DERIVATION_RULE_CATALOG: dict[str, DerivationRule] = {
    "excel_workbook_fact/1": _rule(
        "excel_workbook_fact/1",
        "workbook_manifest",
        "excel_region",
        "candidate_fact",
        "explicit",
        policy="explicit_excel_workbook_only/1",
        evidence_locator=(
            "source_revision_id+fragment_id+manifest_id+sheet_name+coordinate+part_name"
        ),
    ),
    "excel_sheet_fact/1": _rule(
        "excel_sheet_fact/1",
        "workbook_manifest",
        "excel_region",
        "candidate_fact",
        "explicit",
        policy="explicit_excel_sheet_only/1",
        evidence_locator=(
            "source_revision_id+fragment_id+manifest_id+sheet_name+coordinate+part_name"
        ),
    ),
    "excel_region_fact/1": _rule(
        "excel_region_fact/1",
        "workbook_manifest",
        "excel_region",
        "candidate_fact",
        "explicit",
        policy="explicit_excel_region_only/1",
        evidence_locator=(
            "source_revision_id+fragment_id+manifest_id+sheet_name+coordinate+part_name"
        ),
    ),
    "excel_named_range_fact/1": _rule(
        "excel_named_range_fact/1",
        "workbook_manifest",
        "excel_region",
        "candidate_fact",
        "explicit",
        policy="explicit_excel_named_range_only/1",
        evidence_locator=(
            "source_revision_id+fragment_id+manifest_id+sheet_name+coordinate+part_name"
        ),
    ),
    "excel_table_fact/1": _rule(
        "excel_table_fact/1",
        "workbook_manifest",
        "excel_region",
        "candidate_fact",
        "explicit",
        policy="explicit_excel_table_only/1",
        evidence_locator=(
            "source_revision_id+fragment_id+manifest_id+sheet_name+coordinate+part_name"
        ),
    ),
    "excel_explicit_reference/1": _rule(
        "excel_explicit_reference/1",
        "workbook_manifest",
        "excel_region",
        "candidate_relation",
        "explicit",
        policy="explicit_excel_reference_pending/1",
        automatic_review_allowed=False,
        evidence_locator=(
            "source_revision_id+fragment_id+manifest_id+sheet_name+coordinate+part_name"
        ),
    ),
}


ALL_DERIVATION_RULE_CATALOG: dict[str, DerivationRule] = {
    **DERIVATION_RULE_CATALOG,
    **EXCEL_DERIVATION_RULE_CATALOG,
}


class CandidateDerivationError(RuntimeError):
    def __init__(self, message: str, *, reason: str = "candidate_derivation_failed") -> None:
        super().__init__(message)
        self.reason = reason
        self.exit_code = 2


@dataclass(frozen=True)
class CandidateDerivationResult:
    run_id: str
    derivation_id: str
    batch_id: str
    rule_set_version: str
    rule: str
    source_revision_id: str | None
    input_count: int
    produced: int
    rejected: int
    deduplicated: int
    candidates_path: str
    report_path: str
    candidate_ids: tuple[str, ...]
    rejection_details: tuple[dict[str, str], ...]
    payload_hashes: tuple[str, ...]
    semantic_report_hash: str

    def to_payload(self) -> dict[str, Any]:
        reason = (
            "derivation_insufficient_evidence"
            if any(item["reason"] == "derivation_insufficient_evidence" for item in self.rejection_details)
            else "success_with_rejections"
            if self.rejection_details
            else "success"
        )
        contract = ALL_DERIVATION_RULE_CATALOG[self.rule]
        return {
            "artifact_paths": [self.candidates_path, self.report_path],
            "batch_id": self.batch_id,
            "candidate_ids": list(self.candidate_ids),
            "catalog_version": "result_catalog_v1",
            "condition": "candidate_derivation",
            "counters": {
                "auto_confirmed": 0,
                "deduplicated": self.deduplicated,
                "input_fragments": self.input_count,
                "pending": self.produced,
                "produced": self.produced,
                "rejected": self.rejected,
            },
            "derivation_id": self.derivation_id,
            "derivation_rejections": list(self.rejection_details),
            "exit_code": 0,
            "mutations": True,
            "outcome": "pending",
            "payload_hashes": list(self.payload_hashes),
            "reason": reason,
            "retryable": False,
            "rule": self.rule,
            "rule_contract": {
                "assertion_type": contract.assertion_type,
                "automatic_review_allowed": contract.automatic_review_allowed,
                "automatic_review_policy": contract.automatic_review_policy,
                "candidate_record_type": contract.candidate_record_type,
                "default_review_state": contract.default_review_state,
                "evidence_locator": contract.evidence_locator,
                "input_schema": contract.input_schema,
                "parser_kind": contract.parser_kind,
                "rule_id": contract.rule_id,
                "rule_version": contract.rule_version,
            },
            "rule_counts": {
                self.rule: {
                    "auto_confirmed": 0,
                    "deduplicated": self.deduplicated,
                    "input_fragments": self.input_count,
                    "pending": self.produced,
                    "produced": self.produced,
                    "rejected": self.rejected,
                }
            },
            "rule_set_version": self.rule_set_version,
            "run_id": self.run_id,
            "schema_version": "1",
            "semantic_report_hash": self.semantic_report_hash,
            "severity": "warning" if self.rejection_details else "info",
            "source_revision_id": self.source_revision_id,
            "status": "completed",
            "subject_ids": list(self.candidate_ids),
        }


@dataclass(frozen=True)
class DerivationIssue:
    fragment_id: str
    message: str
    reason: str = "derivation_insufficient_evidence"

    def to_payload(self) -> dict[str, str]:
        return {"fragment_id": self.fragment_id, "message": self.message, "reason": self.reason}


def derive_candidates(
    workspace_dir: str | Path,
    *,
    run_id: str,
    source_revision_id: str | None = None,
    rule: str = RULE_NAME,
    rule_set_version: str = "1",
    clock: Any = None,
) -> CandidateDerivationResult:
    contract = ALL_DERIVATION_RULE_CATALOG.get(rule)
    if contract is None:
        available = ", ".join(ALL_DERIVATION_RULE_CATALOG)
        raise CandidateDerivationError(
            f"Unsupported derivation rule: {rule}. Available rules: {available}.",
            reason="derivation_rule_unsupported",
        )
    settings = resolve_database_settings(workspace_dir)
    timestamp = timestamp_now(clock)
    artifacts = run_artifact_paths(settings.workspace_dir, run_id)
    candidates_file = artifacts.artifact_dir / "derived_candidates.jsonl"
    report_file = artifacts.artifact_dir / "derive_report.json"
    candidates_path = relative_workspace_path(settings.workspace_dir, candidates_file)
    report_path = relative_workspace_path(settings.workspace_dir, report_file)

    connection = open_database(settings.database_path, enable_wal=settings.wal_enabled)
    try:
        validate_database_migrations(connection)
        if source_revision_id is not None and connection.execute(
            "SELECT 1 FROM source_revisions WHERE source_revision_id = ?", (source_revision_id,)
        ).fetchone() is None:
            raise CandidateDerivationError(
                f"Source revision not found: {source_revision_id}.", reason="source_revision_not_found"
            )
        derivation_id = next_id(connection, "candidate_derivation_runs", "derivation_id", "DERIVE")
        fragments = _load_rule_fragments(
            connection,
            contract,
            source_revision_id,
            settings.workspace_dir,
        )
        context = _load_context(connection)
        connection.execute(
            """
            INSERT INTO candidate_derivation_runs (
                derivation_id, run_id, rule_set_version, source_revision_id,
                batch_id, status, counters_json, report_path, created_at, completed_at
            ) VALUES (?, ?, ?, ?, NULL, 'running', '{}', ?, ?, NULL)
            """,
            (derivation_id, run_id, rule_set_version, source_revision_id, report_path, timestamp),
        )
        connection.commit()
    finally:
        connection.close()

    candidates, issues, deduplicated = _derive_rule_records_with_stats(
        rule, fragments, context=context
    )
    candidates_file.write_text(
        "".join(canonical_json_v1(candidate) + "\n" for candidate in candidates),
        encoding="utf-8", newline="\n",
    )
    try:
        imported = import_candidate_file(
            settings.workspace_dir,
            run_id=run_id,
            input_path=candidates_file,
            origin_type="deterministic_derivation",
            origin_ref=f"derive://{derivation_id}",
            clock=clock,
        )
    except Exception:
        _mark_derivation_failed(settings, derivation_id, timestamp)
        raise

    result = _complete_derivation(
        settings,
        run_id=run_id,
        derivation_id=derivation_id,
        imported=imported,
        source_revision_id=source_revision_id,
        rule=rule,
        rule_set_version=rule_set_version,
        candidates_path=candidates_path,
        report_path=report_path,
        candidates=candidates,
        deduplicated=deduplicated,
        input_count=len(fragments),
        derivation_rejections=tuple(issue.to_payload() for issue in issues),
        timestamp=timestamp,
    )
    report_file.write_text(canonical_json_artifact_v1(result.to_payload()), encoding="utf-8", newline="\n")
    return result


def derive_rule_records(
    rule: str,
    fragments: Iterable[Mapping[str, Any]],
    *,
    context: Mapping[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[DerivationIssue]]:
    candidates, issues, _deduplicated = _derive_rule_records_with_stats(
        rule, fragments, context=context
    )
    return candidates, issues


def _derive_rule_records_with_stats(
    rule: str,
    fragments: Iterable[Mapping[str, Any]],
    *,
    context: Mapping[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[DerivationIssue], int]:
    if rule not in ALL_DERIVATION_RULE_CATALOG:
        raise CandidateDerivationError(f"Unsupported derivation rule: {rule}.", reason="derivation_rule_unsupported")
    producer = _RULE_PRODUCERS[rule]
    derived: list[dict[str, Any]] = []
    issues: list[DerivationIssue] = []
    for fragment in sorted(fragments, key=_fragment_sort_key):
        try:
            locator = _evidence_locator(fragment)
            metadata = _fragment_metadata(fragment)
            records, fragment_issues = producer(fragment, metadata, locator, context or {})
            derived.extend(records)
            issues.extend(fragment_issues)
        except CandidateDerivationError as exc:
            issues.append(DerivationIssue(_value(fragment, "fragment_id"), str(exc), exc.reason))

    unique: dict[str, dict[str, Any]] = {}
    deduplicated = 0
    for candidate in derived:
        candidate_id = str(candidate["candidate_id"])
        canonical = canonical_json_v1(candidate)
        existing = unique.get(candidate_id)
        if existing is not None and canonical_json_v1(existing) != canonical:
            raise CandidateDerivationError(
                f"Candidate id collision for {candidate_id}.", reason="candidate_identity_collision"
            )
        if existing is not None:
            deduplicated += 1
        else:
            unique[candidate_id] = candidate
    ordered = list(unique.values())
    issues.sort(key=lambda item: (item.fragment_id, item.reason, item.message))
    return ordered, issues, deduplicated


def _load_rule_fragments(
    connection,
    rule: DerivationRule,
    source_revision_id: str | None,
    workspace_dir: Path,
):
    if rule.parser_kind == "workbook_manifest":
        return _load_excel_rule_inputs(
            connection,
            rule,
            source_revision_id,
            workspace_dir,
        )
    fragment_types = tuple(rule.input_fragment_type.split("|"))
    placeholders = ", ".join("?" for _ in fragment_types)
    query = f"""
        SELECT sf.*, sr.content_hash
        FROM source_fragments sf
        JOIN source_revisions sr ON sr.source_revision_id = sf.source_revision_id
        WHERE sf.status = 'active' AND sf.fragment_type IN ({placeholders})
    """
    parameters: list[Any] = list(fragment_types)
    if source_revision_id is not None:
        query += " AND sf.source_revision_id = ?"
        parameters.append(source_revision_id)
    query += " ORDER BY sf.source_revision_id, sf.path_or_selector, sf.fragment_id"
    return connection.execute(query, tuple(parameters)).fetchall()


def _load_excel_rule_inputs(
    connection,
    rule: DerivationRule,
    source_revision_id: str | None,
    workspace_dir: Path,
) -> list[dict[str, Any]]:
    query = """
        SELECT wm.manifest_id, wm.source_revision_id, wm.manifest_hash,
               wm.artifact_path, sr.content_hash
        FROM workbook_manifests wm
        JOIN source_revisions sr
          ON sr.source_revision_id = wm.source_revision_id
        WHERE wm.status IN ('completed', 'partial')
    """
    parameters: tuple[Any, ...] = ()
    if source_revision_id is not None:
        query += " AND wm.source_revision_id = ?"
        parameters = (source_revision_id,)
    query += " ORDER BY wm.source_revision_id, wm.manifest_id"

    rule_kind = {
        "excel_workbook_fact": "workbook",
        "excel_sheet_fact": "sheet",
        "excel_region_fact": "region",
        "excel_named_range_fact": "named_range",
        "excel_table_fact": "table",
        "excel_explicit_reference": "explicit_reference",
    }[rule.rule_id]
    inputs: list[dict[str, Any]] = []
    for row in connection.execute(query, parameters).fetchall():
        manifest = _load_registered_manifest(workspace_dir, row)
        revision_id = str(row["source_revision_id"])
        fragment_rows = {
            str(fragment["fragment_id"]): dict(fragment)
            for fragment in connection.execute(
                """
                SELECT sf.*, sr.content_hash
                FROM source_fragments sf
                JOIN source_revisions sr
                  ON sr.source_revision_id = sf.source_revision_id
                WHERE sf.source_revision_id = ?
                  AND sf.fragment_type = 'excel_region'
                  AND sf.status = 'active'
                ORDER BY sf.sequence, sf.fragment_id
                """,
                (revision_id,),
            ).fetchall()
        }
        objects = _excel_manifest_objects(
            manifest,
            manifest_id=str(row["manifest_id"]),
            fragment_rows=fragment_rows,
        )
        inputs.extend(item for item in objects if item["excel_kind"] == rule_kind)
    return sorted(inputs, key=lambda item: str(item["derivation_sort_key"]))


def _load_registered_manifest(workspace_dir: Path, row: Mapping[str, Any]) -> dict[str, Any]:
    try:
        artifact_path = resolve_workspace_path(workspace_dir, str(row["artifact_path"]))
        data = artifact_path.read_bytes()
        manifest = json.loads(data.decode("utf-8"))
    except (DatabaseConfigurationError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CandidateDerivationError(
            f"Registered workbook manifest cannot be read: {row['artifact_path']}.",
            reason="workbook_manifest_invalid",
        ) from exc
    if (
        not isinstance(manifest, dict)
        or hashlib.sha256(data).hexdigest() != str(row["manifest_hash"])
        or data.decode("utf-8") != canonical_json_artifact_v1(manifest)
    ):
        raise CandidateDerivationError(
            f"Registered workbook manifest is not canonical or does not match its hash: {row['manifest_id']}.",
            reason="workbook_manifest_invalid",
        )
    revision = manifest.get("source_revision")
    if (
        manifest.get("schema_version") != "1"
        or not isinstance(revision, dict)
        or revision.get("id") != row["source_revision_id"]
        or revision.get("content_hash") != row["content_hash"]
    ):
        raise CandidateDerivationError(
            f"Registered workbook manifest identity is inconsistent: {row['manifest_id']}.",
            reason="workbook_manifest_invalid",
        )
    return manifest


def _excel_manifest_objects(
    manifest: Mapping[str, Any],
    *,
    manifest_id: str,
    fragment_rows: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    revision = manifest.get("source_revision")
    workbook = manifest.get("workbook")
    sheets = manifest.get("sheets")
    named_ranges = manifest.get("named_ranges")
    tables = manifest.get("tables", [])
    if (
        not isinstance(revision, dict)
        or not isinstance(workbook, dict)
        or not isinstance(sheets, list)
        or not isinstance(named_ranges, list)
        or not isinstance(tables, list)
    ):
        raise CandidateDerivationError(
            f"Workbook manifest structure is invalid: {manifest_id}.",
            reason="workbook_manifest_invalid",
        )
    content_hash = _clean_text(revision.get("content_hash"))
    if content_hash is None:
        raise CandidateDerivationError(
            f"Workbook manifest lacks its content hash: {manifest_id}.",
            reason="workbook_manifest_invalid",
        )
    workbook_entity = f"excel_workbook:{content_hash}"
    anchors: list[dict[str, Any]] = []
    for sheet in sheets:
        if not isinstance(sheet, dict) or not isinstance(sheet.get("regions"), list):
            raise CandidateDerivationError(
                f"Workbook manifest sheet structure is invalid: {manifest_id}.",
                reason="workbook_manifest_invalid",
            )
        for region in sheet["regions"]:
            if not isinstance(region, dict):
                continue
            fragment_id = _clean_text(region.get("fragment_id"))
            fragment = fragment_rows.get(fragment_id or "")
            if fragment is None:
                raise CandidateDerivationError(
                    f"Workbook region references missing active evidence: {fragment_id or '-'}.",
                    reason="workbook_evidence_missing",
                )
            try:
                bounds = parse_cell_range(_region_reference(region))
            except WorkbookRegionError as exc:
                raise CandidateDerivationError(
                    f"Workbook region has invalid coordinates: {fragment_id}.",
                    reason="workbook_manifest_invalid",
                ) from exc
            anchors.append(
                {
                    "bounds": bounds,
                    "fragment": fragment,
                    "region": region,
                    "sheet": sheet,
                }
            )
    anchors.sort(key=_excel_anchor_sort_key)
    if not anchors:
        return []

    result: list[dict[str, Any]] = []
    first_anchor = anchors[0]
    result.append(
        _excel_input(
            first_anchor,
            manifest_id=manifest_id,
            excel_kind="workbook",
            coordinate=_region_reference(first_anchor["region"]),
            sort_key=("workbook", workbook_entity),
            payload={
                "entity_name": workbook_entity,
                "technical_attributes": {
                    "calculation_properties": workbook.get("calculation_properties", {}),
                    "date_system": workbook.get("date_system"),
                    "macro_presence": workbook.get("macro_presence"),
                    "package_content_type": revision.get("package_content_type"),
                    "part_name": workbook.get("part_name"),
                    "source_extension": revision.get("extension"),
                },
            },
        )
    )

    anchors_by_sheet: dict[int, list[dict[str, Any]]] = {}
    for anchor in anchors:
        anchors_by_sheet.setdefault(int(anchor["sheet"]["index"]), []).append(anchor)
    for sheet in sheets:
        if not isinstance(sheet, dict):
            continue
        sheet_index = int(sheet["index"])
        sheet_anchors = anchors_by_sheet.get(sheet_index, [])
        if not sheet_anchors:
            continue
        sheet_entity = _excel_sheet_entity(workbook_entity, sheet_index)
        result.append(
            _excel_input(
                sheet_anchors[0],
                manifest_id=manifest_id,
                excel_kind="sheet",
                coordinate=_region_reference(sheet_anchors[0]["region"]),
                sort_key=("sheet", sheet_index),
                payload={
                    "entity_name": sheet_entity,
                    "technical_attributes": {
                        "dimensions": sheet.get("dimensions", {}),
                        "part_name": sheet.get("part_name"),
                        "relationship_id": sheet.get("relationship_id"),
                        "sheet_index": sheet_index,
                        "sheet_name": sheet.get("name"),
                        "visibility": sheet.get("visibility"),
                    },
                },
            )
        )
        for anchor in sheet_anchors:
            region = anchor["region"]
            reference = _region_reference(region)
            result.append(
                _excel_input(
                    anchor,
                    manifest_id=manifest_id,
                    excel_kind="region",
                    coordinate=reference,
                    sort_key=("region", sheet_index, reference, region.get("ordinal")),
                    payload={
                        "entity_name": _excel_region_entity(sheet_entity, reference),
                        "technical_attributes": {
                            "cell_attributes": region.get("cells", []),
                            "detector": region.get("detector"),
                            "end_cell": region.get("end_cell"),
                            "region_hash": region.get("region_hash"),
                            "region_kind": region.get("region_kind"),
                            "sheet_index": sheet_index,
                            "sheet_name": sheet.get("name"),
                            "start_cell": region.get("start_cell"),
                        },
                    },
                )
            )

    named_objects: list[dict[str, Any]] = []
    for named_range in named_ranges:
        if not isinstance(named_range, dict):
            continue
        resolved = _resolved_manifest_range(named_range.get("refers_to"), named_range.get("sheet_name"))
        if resolved is None:
            continue
        sheet_name, reference = resolved
        anchor = _anchor_for_range(anchors, sheet_name, reference)
        if anchor is None:
            continue
        scope = _clean_text(named_range.get("scope")) or "workbook"
        name = _clean_text(named_range.get("name"))
        if name is None:
            continue
        entity_name = (
            f"{workbook_entity}/named_range:{scope}:"
            f"{sheet_name if scope == 'sheet' else '*'}:{name}"
        )
        named_object = {
            "anchor": anchor,
            "entity_name": entity_name,
            "name": name,
            "reference": reference,
            "scope": scope,
            "sheet_name": sheet_name,
        }
        named_objects.append(named_object)
        result.append(
            _excel_input(
                anchor,
                manifest_id=manifest_id,
                excel_kind="named_range",
                coordinate=reference,
                sort_key=("named_range", scope, sheet_name, name, reference),
                payload={
                    "entity_name": entity_name,
                    "technical_attributes": {
                        "name": name,
                        "refers_to": named_range.get("refers_to"),
                        "scope": scope,
                        "sheet_name": sheet_name,
                    },
                },
            )
        )

    table_objects: list[dict[str, Any]] = []
    for table in tables:
        if not isinstance(table, dict):
            continue
        sheet_name = _clean_text(table.get("sheet_name"))
        reference = _clean_text(table.get("refers_to"))
        display_name = _clean_text(table.get("display_name"))
        if sheet_name is None or reference is None or display_name is None:
            continue
        anchor = _anchor_for_range(anchors, sheet_name, reference)
        if anchor is None:
            continue
        sheet_entity = _excel_sheet_entity(workbook_entity, int(table["sheet_index"]))
        entity_name = f"{sheet_entity}/table:{display_name}"
        table_object = {
            "anchor": anchor,
            "display_name": display_name,
            "entity_name": entity_name,
            "name": _clean_text(table.get("name")) or display_name,
            "reference": reference,
            "sheet_name": sheet_name,
        }
        table_objects.append(table_object)
        result.append(
            _excel_input(
                anchor,
                manifest_id=manifest_id,
                excel_kind="table",
                coordinate=reference,
                sort_key=("table", int(table["sheet_index"]), reference, display_name),
                payload={
                    "entity_name": entity_name,
                    "technical_attributes": {
                        "columns": table.get("columns", []),
                        "display_name": display_name,
                        "name": table.get("name"),
                        "part_name": table.get("part_name"),
                        "refers_to": reference,
                        "relationship_id": table.get("relationship_id"),
                        "sheet_name": sheet_name,
                    },
                },
            )
        )

    result.extend(
        _excel_reference_inputs(
            anchors,
            named_objects=named_objects,
            table_objects=table_objects,
            workbook_entity=workbook_entity,
            manifest_id=manifest_id,
        )
    )
    return result


def _excel_reference_inputs(
    anchors: Sequence[Mapping[str, Any]],
    *,
    named_objects: Sequence[Mapping[str, Any]],
    table_objects: Sequence[Mapping[str, Any]],
    workbook_entity: str,
    manifest_id: str,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for anchor in anchors:
        sheet = anchor["sheet"]
        region = anchor["region"]
        sheet_name = str(sheet["name"])
        sheet_entity = _excel_sheet_entity(workbook_entity, int(sheet["index"]))
        source_entity = _excel_region_entity(sheet_entity, _region_reference(region))
        cells = region.get("cells", [])
        if not isinstance(cells, list):
            continue
        for cell in cells:
            if not isinstance(cell, dict):
                continue
            formula = _clean_text(cell.get("formula"))
            coordinate = _clean_text(cell.get("coordinate"))
            if formula is None or coordinate is None or _formula_is_external(formula):
                continue
            targets: dict[tuple[str, str], tuple[str, str]] = {}
            for table in table_objects:
                for name in {str(table["name"]), str(table["display_name"])}:
                    if re.search(rf"(?i)(?<![A-Z0-9_.]){re.escape(name)}\s*\[", formula):
                        targets[("table", str(table["entity_name"]))] = ("table", name)
            named_by_name: dict[str, list[Mapping[str, Any]]] = {}
            for named in named_objects:
                named_by_name.setdefault(str(named["name"]).casefold(), []).append(named)
            for folded_name, matches in named_by_name.items():
                name = str(matches[0]["name"])
                if re.search(rf"(?i)(?<![A-Z0-9_.]){re.escape(name)}(?![A-Z0-9_.])", formula) is None:
                    continue
                scoped = [
                    item
                    for item in matches
                    if item["scope"] == "sheet" and item["sheet_name"] == sheet_name
                ]
                selected = scoped or [item for item in matches if item["scope"] == "workbook"]
                if selected:
                    target = sorted(selected, key=lambda item: str(item["entity_name"]))[0]
                    targets[("named_range", str(target["entity_name"]))] = (
                        "named_range",
                        str(target["name"]),
                    )
            for match in _SHEET_REFERENCE.finditer(formula):
                target_sheet = (match.group("quoted") or match.group("plain") or "").replace("''", "'")
                target_coordinate = f"{match.group('column')}{match.group('row')}"
                target_anchor = _anchor_for_coordinate(anchors, target_sheet, target_coordinate)
                if target_anchor is None:
                    continue
                target_sheet_entity = _excel_sheet_entity(
                    workbook_entity, int(target_anchor["sheet"]["index"])
                )
                target_entity = _excel_region_entity(
                    target_sheet_entity,
                    _region_reference(target_anchor["region"]),
                )
                targets[("region", target_entity)] = ("region", match.group(0))
            for (reference_kind, target_entity), (_, explicit_token) in sorted(targets.items()):
                result.append(
                    _excel_input(
                        anchor,
                        manifest_id=manifest_id,
                        excel_kind="explicit_reference",
                        coordinate=coordinate,
                        sort_key=(
                            "explicit_reference",
                            int(sheet["index"]),
                            coordinate,
                            reference_kind,
                            target_entity,
                        ),
                        payload={
                            "relation_type": "references",
                            "source_entity": source_entity,
                            "target_entity": target_entity,
                            "technical_attributes": {
                                "formula": formula,
                                "reference_kind": reference_kind,
                                "reference_token": explicit_token,
                                "sheet_name": sheet_name,
                                "source_coordinate": coordinate,
                            },
                        },
                    )
                )
    return result


def _excel_input(
    anchor: Mapping[str, Any],
    *,
    manifest_id: str,
    excel_kind: str,
    coordinate: str,
    sort_key: Sequence[Any],
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    fragment = dict(anchor["fragment"])
    sheet = anchor["sheet"]
    fragment["derivation_sort_key"] = canonical_json_v1(list(sort_key))
    fragment["evidence_locator"] = {
        "coordinate": coordinate,
        "fragment_id": str(fragment["fragment_id"]),
        "manifest_id": manifest_id,
        "part_name": str(sheet["part_name"]),
        "path_or_selector": str(fragment["path_or_selector"]),
        "sheet_name": str(sheet["name"]),
        "source_revision_id": str(fragment["source_revision_id"]),
    }
    fragment["excel_kind"] = excel_kind
    fragment["metadata_json"] = {
        "excel_kind": excel_kind,
        "manifest_id": manifest_id,
        **payload,
    }
    fragment["parser_kind"] = "workbook_manifest"
    return fragment


def _resolved_manifest_range(value: Any, default_sheet: Any) -> tuple[str, str] | None:
    text = _clean_text(value)
    if text is None or _formula_is_external(text) or "," in text:
        return None
    match = _MANIFEST_RANGE.fullmatch(text.lstrip("=").strip())
    if match is None:
        return None
    sheet_name = (match.group("quoted") or match.group("plain") or _clean_text(default_sheet))
    if sheet_name is None:
        return None
    sheet_name = sheet_name.replace("''", "'")
    try:
        reference = parse_cell_range(match.group("range").replace("$", "")).reference
    except WorkbookRegionError:
        return None
    return sheet_name, reference


def _anchor_for_range(
    anchors: Sequence[Mapping[str, Any]], sheet_name: str, reference: str
) -> Mapping[str, Any] | None:
    try:
        bounds = parse_cell_range(reference)
    except WorkbookRegionError:
        return None
    matches = [
        anchor
        for anchor in anchors
        if anchor["sheet"]["name"] == sheet_name
        and _ranges_overlap(anchor["bounds"], bounds)
    ]
    return min(matches, key=_excel_anchor_sort_key) if matches else None


def _anchor_for_coordinate(
    anchors: Sequence[Mapping[str, Any]], sheet_name: str, coordinate: str
) -> Mapping[str, Any] | None:
    try:
        position = parse_cell_reference(coordinate.replace("$", ""))
    except WorkbookRegionError:
        return None
    matches = [
        anchor
        for anchor in anchors
        if anchor["sheet"]["name"] == sheet_name and anchor["bounds"].contains(position)
    ]
    return min(matches, key=_excel_anchor_sort_key) if matches else None


def _ranges_overlap(left: CellRange, right: CellRange) -> bool:
    return not (
        left.end.row < right.start.row
        or right.end.row < left.start.row
        or left.end.column < right.start.column
        or right.end.column < left.start.column
    )


def _excel_anchor_sort_key(anchor: Mapping[str, Any]) -> tuple[int, int, int, int, str]:
    bounds = anchor["bounds"]
    return (
        int(anchor["sheet"]["index"]),
        bounds.start.row,
        bounds.start.column,
        bounds.end.row,
        str(anchor["fragment"]["fragment_id"]),
    )


def _region_reference(region: Mapping[str, Any]) -> str:
    start = str(region["start_cell"])
    end = str(region["end_cell"])
    return start if start == end else f"{start}:{end}"


def _excel_sheet_entity(workbook_entity: str, sheet_index: int) -> str:
    return f"{workbook_entity}/sheet:{sheet_index}"


def _excel_region_entity(sheet_entity: str, reference: str) -> str:
    return f"{sheet_entity}/region:{reference}"


def _formula_is_external(formula: str) -> bool:
    folded = formula.casefold()
    return (
        "://" in folded
        or "file:" in folded
        or re.search(r"(?i)\[[^\]]+\.(?:xls|xlsx|xlsm|xlsb)\]", formula) is not None
    )


_MANIFEST_RANGE = re.compile(
    r"(?:(?:'(?P<quoted>(?:[^']|'')+)'|(?P<plain>[^'!,]+))!)?"
    r"(?P<range>\$?[A-Za-z]{1,3}\$?[1-9][0-9]*(?::\$?[A-Za-z]{1,3}\$?[1-9][0-9]*)?)"
)
_SHEET_REFERENCE = re.compile(
    r"(?:'(?P<quoted>(?:[^']|'')+)'|(?P<plain>[A-Za-z0-9_. -]+))!"
    r"\$?(?P<column>[A-Za-z]{1,3})\$?(?P<row>[1-9][0-9]*)"
)


def _load_context(connection) -> dict[str, Any]:
    query = "SELECT metadata_json FROM source_fragments WHERE status = 'active' AND fragment_type = 'ddl_table'"
    tables: set[str] = set()
    for row in connection.execute(query).fetchall():
        try:
            metadata = json.loads(row["metadata_json"] or "{}")
        except json.JSONDecodeError:
            continue
        table_name = _clean_text(metadata.get("table_name"))
        if table_name:
            tables.add(table_name.casefold())
    return {"ddl_tables": frozenset(tables)}


Producer = Callable[
    [Mapping[str, Any], Mapping[str, Any], Mapping[str, Any], Mapping[str, Any]],
    tuple[list[dict[str, Any]], list[DerivationIssue]],
]


def _ddl_table_records(fragment, metadata, locator, context):
    del context
    table_name = _required_metadata_text(fragment, metadata, "table_name")
    return [
        _fact_candidate(
            "ddl_table_fact/1",
            fragment,
            locator,
            signal={"table_name": table_name},
            fact_type="database_table",
            entity_name=table_name,
            property_name="object_type",
            property_value="database_table",
        )
    ], []


def _ddl_column_records(fragment, metadata, locator, context):
    del context
    table_name = _required_metadata_text(fragment, metadata, "table_name")
    column_name = _required_metadata_text(fragment, metadata, "column_name")
    data_type = _required_metadata_text(fragment, metadata, "data_type")
    return [
        _fact_candidate(
            "ddl_column_fact/1",
            fragment,
            locator,
            signal={"column_name": column_name, "data_type": data_type, "table_name": table_name},
            fact_type="database_column",
            entity_name=f"{table_name}.{column_name}",
            property_name="data_type",
            property_value=data_type,
            column_name=column_name,
            nullable=metadata.get("nullable"),
            table_name=table_name,
        )
    ], []


def _ddl_fk_records(fragment, metadata, locator, context):
    constraint_kind = _clean_text(metadata.get("constraint_kind"))
    if not constraint_kind or constraint_kind.casefold() != "foreign_key":
        return [], []
    source = _required_metadata_text(fragment, metadata, "table_name")
    target = _required_metadata_text(fragment, metadata, "references_table")
    if target.casefold() not in context.get("ddl_tables", frozenset()):
        return [], [
            _issue(
                fragment,
                f"Foreign-key target is not resolved by an active ddl_table fragment: {target}.",
            )
        ]
    columns = _text_list(metadata.get("columns"))
    referenced_columns = _text_list(metadata.get("references_columns"))
    if not columns or not referenced_columns:
        return [], [_issue(fragment, "Foreign-key columns or referenced columns are not explicit.")]
    signal = {
        "columns": columns,
        "references_columns": referenced_columns,
        "source": source,
        "target": target,
    }
    return [
        _relation_candidate(
            "ddl_fk_relation/1",
            fragment,
            locator,
            signal=signal,
            source_entity=source,
            relation_type="references",
            target_entity=target,
            columns=columns,
            constraint_name=_clean_text(metadata.get("constraint_name")),
            referenced_columns=referenced_columns,
        )
    ], []


def _xml_form_structure_records(fragment, metadata, locator, context):
    del context
    fragment_type = _value(fragment, "fragment_type")
    form_name = _required_metadata_text(fragment, metadata, "form_name")
    if fragment_type == "xml_form":
        return [
            _fact_candidate(
                "xml_form_structure/1",
                fragment,
                locator,
                signal={"form_name": form_name, "structure_type": "form"},
                fact_type="xml_form",
                entity_name=form_name,
                property_name="object_type",
                property_value="form",
            )
        ], []
    if fragment_type == "xml_field":
        field_name = _required_metadata_text(fragment, metadata, "field_name")
        return [
            _fact_candidate(
                "xml_form_structure/1",
                fragment,
                locator,
                signal={"field_name": field_name, "form_name": form_name, "structure_type": "field"},
                fact_type="xml_form_field",
                entity_name=f"{form_name}.{field_name}",
                property_name="object_type",
                property_value="field",
            )
        ], []
    if fragment_type == "xml_button":
        button_name = _required_metadata_text(fragment, metadata, "button_name")
        return [
            _fact_candidate(
                "xml_form_structure/1",
                fragment,
                locator,
                signal={"button_name": button_name, "form_name": form_name, "structure_type": "button"},
                fact_type="xml_form_button",
                entity_name=f"{form_name}.{button_name}",
                property_name="object_type",
                property_value="button",
            )
        ], []
    return [], [_issue(fragment, f"Unsupported XML structure fragment type: {fragment_type}.")]


def _xml_table_usage_records(fragment, metadata, locator, context):
    del context
    form_name = _required_metadata_text(fragment, metadata, "form_name")
    raw_relations = metadata.get("edit_relations")
    if raw_relations is None:
        raw_relations = metadata.get("table_usage_relations", [])
    if not isinstance(raw_relations, list):
        return [], [_issue(fragment, "XML table usage relation list is invalid.")]

    records: list[dict[str, Any]] = []
    explicit_targets: set[str] = set()
    issues: list[DerivationIssue] = []
    operation_map = {
        "edit": "writes_to",
        "edits": "writes_to",
        "write": "writes_to",
        "writes": "writes_to",
        "writes_to": "writes_to",
        "read": "reads_from",
        "reads": "reads_from",
        "reads_from": "reads_from",
    }
    for index, relation in enumerate(raw_relations):
        if not isinstance(relation, dict):
            issues.append(_issue(fragment, f"XML table usage entry {index} is invalid."))
            continue
        target = _clean_text(relation.get("target_table"))
        raw_operation = _clean_text(relation.get("relation_type"))
        relation_type = operation_map.get(raw_operation.casefold() if raw_operation else "")
        if not target or relation_type is None:
            issues.append(
                _issue(
                    fragment,
                    f"XML table usage entry {index} lacks an explicit read/write operation or target.",
                )
            )
            continue
        explicit_targets.add(target.casefold())
        signal = {"form_name": form_name, "relation_type": relation_type, "target_table": target}
        records.append(
            _relation_candidate(
                "xml_table_usage/1",
                fragment,
                locator,
                signal=signal,
                source_entity=form_name,
                relation_type=relation_type,
                target_entity=target,
                field_names=_text_list(relation.get("field_names")),
            )
        )
    for target in _text_list(metadata.get("table_references")):
        if target.casefold() not in explicit_targets:
            issues.append(_issue(fragment, f"XML table reference has no explicit read/write operation: {target}."))
    return records, issues


def _db_code_unit_records(fragment, metadata, locator, context):
    del context
    fragment_type = _value(fragment, "fragment_type")
    if fragment_type == "sql_procedure":
        unit_name = _required_metadata_text(fragment, metadata, "procedure_name")
        unit_type = "procedure"
    elif fragment_type == "sql_function":
        unit_name = _required_metadata_text(fragment, metadata, "function_name")
        unit_type = "function"
    elif fragment_type == "sql_trigger":
        unit_name = _required_metadata_text(fragment, metadata, "trigger_name")
        unit_type = "trigger"
    else:
        return [], [_issue(fragment, f"Unsupported database-code unit fragment type: {fragment_type}.")]
    return [
        _fact_candidate(
            "db_code_unit/1",
            fragment,
            locator,
            signal={"unit_name": unit_name, "unit_type": unit_type},
            fact_type="database_code_unit",
            entity_name=unit_name,
            property_name="unit_type",
            property_value=unit_type,
        )
    ], []


def _db_code_dependency_records(fragment, metadata, locator, context):
    del context
    fragment_type = _value(fragment, "fragment_type")
    name_key = {
        "sql_function": "function_name",
        "sql_procedure": "procedure_name",
        "sql_trigger": "trigger_name",
    }.get(fragment_type)
    if name_key is None:
        return [], [_issue(fragment, f"Unsupported database-code dependency fragment type: {fragment_type}.")]
    source = _required_metadata_text(fragment, metadata, name_key)
    parameters = {item.casefold() for item in _text_list(metadata.get("parameters"))}
    records: list[dict[str, Any]] = []
    issues: list[DerivationIssue] = []
    for metadata_key, relation_type in (
        ("reads", "reads_from"),
        ("writes", "writes_to"),
        ("calls", "calls"),
    ):
        raw_targets = metadata.get(metadata_key, [])
        if not isinstance(raw_targets, list):
            issues.append(_issue(fragment, f"Database-code {metadata_key} signal is invalid."))
            continue
        for target in _text_list(raw_targets):
            if target.upper().startswith(("NEW.", "OLD.")) or target.casefold() in parameters:
                continue
            records.append(
                _relation_candidate(
                    "db_code_dependency/1",
                    fragment,
                    locator,
                    signal={"relation_type": relation_type, "source": source, "target": target},
                    source_entity=source,
                    relation_type=relation_type,
                    target_entity=target,
                )
            )
    return records, issues


def _log_event_records(fragment, metadata, locator, context):
    del context
    component = _required_metadata_text(fragment, metadata, "component")
    event_kind = _required_metadata_text(fragment, metadata, "event_kind")
    return [
        _fact_candidate(
            "log_event_observation/1",
            fragment,
            locator,
            signal={"component": component, "event_kind": event_kind},
            fact_type="log_event",
            entity_name=component,
            property_name="event_kind",
            property_value=event_kind,
            level=_clean_text(metadata.get("level")),
            observed_identifiers=_observed_identifiers(metadata.get("observed_identifiers")),
            observation_timestamp=_clean_text(metadata.get("timestamp")),
        )
    ], []


def _excel_fact_records(
    fragment,
    metadata,
    locator,
    context,
    *,
    expected_kind: str,
    rule_name: str,
):
    del context
    excel_kind = _required_metadata_text(fragment, metadata, "excel_kind")
    entity_name = _required_metadata_text(fragment, metadata, "entity_name")
    if excel_kind != expected_kind:
        return [], [
            _issue(
                fragment,
                f"Excel input kind {excel_kind} does not match rule {rule_name}.",
            )
        ]
    technical_attributes = metadata.get("technical_attributes", {})
    if not isinstance(technical_attributes, dict):
        return [], [_issue(fragment, "Excel technical attributes are invalid.")]
    fact_type = f"excel_{excel_kind}"
    return [
        _fact_candidate(
            rule_name,
            fragment,
            locator,
            signal={
                "entity_name": entity_name,
                "technical_attributes": technical_attributes,
            },
            fact_type=fact_type,
            entity_name=entity_name,
            property_name="object_type",
            property_value=fact_type,
            manifest_id=metadata.get("manifest_id"),
            technical_attributes=technical_attributes,
        )
    ], []


def _excel_workbook_records(fragment, metadata, locator, context):
    return _excel_fact_records(
        fragment,
        metadata,
        locator,
        context,
        expected_kind="workbook",
        rule_name="excel_workbook_fact/1",
    )


def _excel_sheet_records(fragment, metadata, locator, context):
    return _excel_fact_records(
        fragment,
        metadata,
        locator,
        context,
        expected_kind="sheet",
        rule_name="excel_sheet_fact/1",
    )


def _excel_region_records(fragment, metadata, locator, context):
    return _excel_fact_records(
        fragment,
        metadata,
        locator,
        context,
        expected_kind="region",
        rule_name="excel_region_fact/1",
    )


def _excel_named_range_records(fragment, metadata, locator, context):
    return _excel_fact_records(
        fragment,
        metadata,
        locator,
        context,
        expected_kind="named_range",
        rule_name="excel_named_range_fact/1",
    )


def _excel_table_records(fragment, metadata, locator, context):
    return _excel_fact_records(
        fragment,
        metadata,
        locator,
        context,
        expected_kind="table",
        rule_name="excel_table_fact/1",
    )


def _excel_reference_records(fragment, metadata, locator, context):
    del context
    excel_kind = _required_metadata_text(fragment, metadata, "excel_kind")
    if excel_kind != "explicit_reference":
        return [], [
            _issue(
                fragment,
                "Excel input kind does not match rule excel_explicit_reference/1.",
            )
        ]
    source_entity = _required_metadata_text(fragment, metadata, "source_entity")
    target_entity = _required_metadata_text(fragment, metadata, "target_entity")
    relation_type = _required_metadata_text(fragment, metadata, "relation_type")
    technical_attributes = metadata.get("technical_attributes", {})
    if not isinstance(technical_attributes, dict):
        return [], [_issue(fragment, "Excel reference attributes are invalid.")]
    return [
        _relation_candidate(
            "excel_explicit_reference/1",
            fragment,
            locator,
            signal={
                "relation_type": relation_type,
                "source_entity": source_entity,
                "target_entity": target_entity,
                "technical_attributes": technical_attributes,
            },
            source_entity=source_entity,
            relation_type=relation_type,
            target_entity=target_entity,
            manifest_id=metadata.get("manifest_id"),
            technical_attributes=technical_attributes,
        )
    ], []


_RULE_PRODUCERS: dict[str, Producer] = {
    "ddl_table_fact/1": _ddl_table_records,
    "ddl_column_fact/1": _ddl_column_records,
    "ddl_fk_relation/1": _ddl_fk_records,
    "xml_form_structure/1": _xml_form_structure_records,
    "xml_table_usage/1": _xml_table_usage_records,
    "db_code_unit/1": _db_code_unit_records,
    "db_code_dependency/1": _db_code_dependency_records,
    "log_event_observation/1": _log_event_records,
    "excel_workbook_fact/1": _excel_workbook_records,
    "excel_sheet_fact/1": _excel_sheet_records,
    "excel_region_fact/1": _excel_region_records,
    "excel_named_range_fact/1": _excel_named_range_records,
    "excel_table_fact/1": _excel_table_records,
    "excel_explicit_reference/1": _excel_reference_records,
}


def _fact_candidate(
    rule: str,
    fragment: Mapping[str, Any],
    locator: Mapping[str, Any],
    *,
    signal: Mapping[str, Any],
    fact_type: str,
    entity_name: str,
    property_name: str,
    property_value: Any,
    **details: Any,
) -> dict[str, Any]:
    return _candidate(
        rule,
        fragment,
        locator,
        signal=signal,
        semantic={
            "entity_name": entity_name,
            "fact_type": fact_type,
            "property_name": property_name,
            "property_value": property_value,
        },
        details=details,
    )


def _relation_candidate(
    rule: str,
    fragment: Mapping[str, Any],
    locator: Mapping[str, Any],
    *,
    signal: Mapping[str, Any],
    source_entity: str,
    relation_type: str,
    target_entity: str,
    **details: Any,
) -> dict[str, Any]:
    return _candidate(
        rule,
        fragment,
        locator,
        signal=signal,
        semantic={
            "relation_type": relation_type,
            "source_entity": source_entity,
            "target_entity": target_entity,
        },
        details=details,
    )


def _candidate(
    rule_name: str,
    fragment: Mapping[str, Any],
    locator: Mapping[str, Any],
    *,
    signal: Mapping[str, Any],
    semantic: Mapping[str, Any],
    details: Mapping[str, Any],
) -> dict[str, Any]:
    contract = ALL_DERIVATION_RULE_CATALOG[rule_name]
    identity = canonical_sha256_v1(
        {
            "fragment_id": _value(fragment, "fragment_id"),
            "rule_id": contract.rule_id,
            "rule_version": contract.rule_version,
            "signal": signal,
            "source_revision_id": _value(fragment, "source_revision_id"),
        }
    )
    prefix = contract.rule_id.upper()
    candidate: dict[str, Any] = {
        "assertion_type": contract.assertion_type,
        "candidate_id": f"{prefix}_{identity[:16].upper()}",
        "confidence": "high",
        "evidence_locator": dict(locator),
        "evidence_text": _value(fragment, "text"),
        "fragment_id": _value(fragment, "fragment_id"),
        "producer_type": "deterministic_rule",
        "record_type": contract.candidate_record_type,
        "rule_id": contract.rule_id,
        "rule_version": contract.rule_version,
        "source_revision_id": _value(fragment, "source_revision_id"),
    }
    candidate.update(semantic)
    candidate.update({key: value for key, value in details.items() if value is not None})
    return candidate


def _evidence_locator(fragment: Mapping[str, Any]) -> dict[str, Any]:
    supplied = _raw_value(fragment, "evidence_locator")
    if isinstance(supplied, dict):
        required = (
            "coordinate",
            "fragment_id",
            "manifest_id",
            "part_name",
            "sheet_name",
            "source_revision_id",
        )
        missing = [key for key in required if _clean_text(supplied.get(key)) is None]
        text = _raw_value(fragment, "text")
        if not isinstance(text, str) or not text.strip():
            missing.append("text")
        if missing:
            raise CandidateDerivationError(
                f"Fragment evidence locator is incomplete ({', '.join(missing)}).",
                reason="derivation_insufficient_evidence",
            )
        return {key: supplied[key] for key in sorted(supplied)}

    fragment_id = _clean_text(_raw_value(fragment, "fragment_id"))
    source_revision_id = _clean_text(_raw_value(fragment, "source_revision_id"))
    path = _clean_text(_raw_value(fragment, "path_or_selector"))
    text = _raw_value(fragment, "text")
    line_start = _raw_value(fragment, "line_start")
    line_end = _raw_value(fragment, "line_end")
    missing: list[str] = []
    if not fragment_id:
        missing.append("fragment_id")
    if not source_revision_id:
        missing.append("source_revision_id")
    if not path:
        missing.append("path_or_selector")
    if not isinstance(line_start, int) or isinstance(line_start, bool) or line_start < 1:
        missing.append("line_start")
    valid_line_start = isinstance(line_start, int) and not isinstance(line_start, bool)
    if (
        not isinstance(line_end, int)
        or isinstance(line_end, bool)
        or line_end < 1
        or (valid_line_start and line_end < line_start)
    ):
        missing.append("line_end")
    if not isinstance(text, str) or not text.strip():
        missing.append("text")
    if missing:
        raise CandidateDerivationError(
            f"Fragment evidence locator is incomplete ({', '.join(missing)}).",
            reason="derivation_insufficient_evidence",
        )
    return {
        "fragment_id": fragment_id,
        "line_end": line_end,
        "line_start": line_start,
        "path_or_selector": path,
        "source_revision_id": source_revision_id,
    }


def _fragment_metadata(fragment: Mapping[str, Any]) -> Mapping[str, Any]:
    raw = _raw_value(fragment, "metadata_json")
    if isinstance(raw, dict):
        return raw
    try:
        metadata = json.loads(raw or "{}")
    except (json.JSONDecodeError, TypeError) as exc:
        raise CandidateDerivationError(
            f"Invalid fragment metadata: {_value(fragment, 'fragment_id')}.",
            reason="derivation_fragment_invalid",
        ) from exc
    if not isinstance(metadata, dict):
        raise CandidateDerivationError(
            f"Fragment metadata is not an object: {_value(fragment, 'fragment_id')}.",
            reason="derivation_fragment_invalid",
        )
    return metadata


def _required_metadata_text(
    fragment: Mapping[str, Any], metadata: Mapping[str, Any], key: str
) -> str:
    value = _clean_text(metadata.get(key))
    if value is None:
        raise CandidateDerivationError(
            f"Fragment {_value(fragment, 'fragment_id')} lacks explicit {key}.",
            reason="derivation_insufficient_evidence",
        )
    return value


def _issue(fragment: Mapping[str, Any], message: str) -> DerivationIssue:
    return DerivationIssue(_value(fragment, "fragment_id"), message)


def _fragment_sort_key(fragment: Mapping[str, Any]) -> tuple[str, str, str, str, str]:
    return (
        _value(fragment, "source_revision_id"),
        _value(fragment, "parser_kind"),
        _value(fragment, "derivation_sort_key"),
        _value(fragment, "path_or_selector"),
        _value(fragment, "fragment_id"),
    )


def _raw_value(fragment: Mapping[str, Any], key: str) -> Any:
    try:
        return fragment[key]
    except (KeyError, IndexError, TypeError):
        return None


def _value(fragment: Mapping[str, Any], key: str) -> str:
    value = _raw_value(fragment, key)
    return "" if value is None else str(value)


def _clean_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _text_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return sorted(
        {_clean_text(item) for item in value if _clean_text(item) is not None},
        key=lambda item: (item.casefold(), item),
    )


def _observed_identifiers(value: Any) -> dict[str, str] | list[str]:
    if isinstance(value, dict):
        return {
            str(key): str(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            if _clean_text(str(key)) is not None and _clean_text(str(item)) is not None
        }
    return _text_list(value)


def _complete_derivation(
    settings,
    *,
    run_id: str,
    derivation_id: str,
    imported: CandidateImportResult,
    source_revision_id: str | None,
    rule: str,
    rule_set_version: str,
    candidates_path: str,
    report_path: str,
    candidates: Sequence[Mapping[str, Any]],
    deduplicated: int,
    input_count: int,
    derivation_rejections: tuple[dict[str, str], ...],
    timestamp: str,
) -> CandidateDerivationResult:
    connection = open_database(settings.database_path, enable_wal=settings.wal_enabled)
    try:
        import_rejections = tuple(
            {
                "fragment_id": "",
                "message": str(row["message"] or "Candidate import rejected the record."),
                "reason": str(row["reason"]),
            }
            for row in connection.execute(
                """
                SELECT reason, message FROM rejected_candidates
                WHERE batch_id = ? ORDER BY line_number, rejected_candidate_id
                """,
                (imported.batch_id,),
            ).fetchall()
        )
        rejection_details = derivation_rejections + import_rejections
        candidate_ids = tuple(str(candidate["candidate_id"]) for candidate in candidates)
        payload_hashes = tuple(canonical_sha256_v1(candidate) for candidate in candidates)
        semantic_report_hash = canonical_sha256_v1(
            {
                "candidate_ids": candidate_ids,
                "counts": {
                    "deduplicated": deduplicated,
                    "input_fragments": input_count,
                    "produced": imported.accepted_count,
                    "rejected": len(rejection_details),
                },
                "payload_hashes": payload_hashes,
                "rejections": rejection_details,
                "rule": rule,
                "rule_set_version": rule_set_version,
                "source_revision_id": source_revision_id,
            }
        )
        result = CandidateDerivationResult(
            run_id=run_id,
            derivation_id=derivation_id,
            batch_id=imported.batch_id,
            rule_set_version=rule_set_version,
            rule=rule,
            source_revision_id=source_revision_id,
            input_count=input_count,
            produced=imported.accepted_count,
            rejected=len(rejection_details),
            deduplicated=deduplicated,
            candidates_path=candidates_path,
            report_path=report_path,
            candidate_ids=candidate_ids,
            rejection_details=rejection_details,
            payload_hashes=payload_hashes,
            semantic_report_hash=semantic_report_hash,
        )
        connection.execute(
            """
            UPDATE candidate_derivation_runs
            SET batch_id = ?, status = 'completed', counters_json = ?, completed_at = ?
            WHERE derivation_id = ?
            """,
            (
                imported.batch_id,
                canonical_json_v1(result.to_payload()["counters"]),
                timestamp,
                derivation_id,
            ),
        )
        connection.commit()
    finally:
        connection.close()
    return result


def _mark_derivation_failed(settings, derivation_id: str, timestamp: str) -> None:
    connection = open_database(settings.database_path, enable_wal=settings.wal_enabled)
    try:
        connection.execute(
            """
            UPDATE candidate_derivation_runs SET status = 'failed', completed_at = ?
            WHERE derivation_id = ?
            """,
            (timestamp, derivation_id),
        )
        connection.commit()
    finally:
        connection.close()
