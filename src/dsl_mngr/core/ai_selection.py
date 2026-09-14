from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from dsl_mngr.core.ai_package import parse_ai_package_options
from dsl_mngr.core.candidate_derivation import ALL_DERIVATION_RULE_CATALOG
from dsl_mngr.core.canonical import (
    canonical_json_artifact_v1,
    canonical_json_v1,
    canonical_sha256_v1,
)
from dsl_mngr.core.config import (
    AI_SELECTION_HARD_MAXIMA,
    WorkerProfileError,
    load_config,
    load_worker_profile,
    parse_simple_yaml,
)
from dsl_mngr.core.database import DatabaseSettings, open_database, resolve_database_settings
from dsl_mngr.core.runs import (
    complete_run,
    fail_run,
    next_id,
    relative_workspace_path,
    run_artifact_paths,
    start_run,
    timestamp_now,
    validate_database_migrations,
)


ROUTES = {
    "technical_extraction",
    "domain_interpretation",
    "mapping_discovery",
    "conflict_analysis",
    "question_generation",
    "temporal_interpretation",
}
COVERAGE_STATES = {
    "no_rule_applicable",
    "applicable_no_candidate",
    "pending",
    "confirmed",
    "rejected",
    "superseded_non_leaf",
}
POLICY_SECTIONS = {"policy", "criteria", "ranking", "budget"}
POLICY_KEYS = {
    "policy_id",
    "policy_version",
    "route_id",
    "route_version",
    "description",
}
CRITERIA_KEYS = {
    "evidence_kinds",
    "source_types",
    "source_subtypes",
    "extensions",
    "authority_levels",
    "fragment_types",
    "producers",
    "producer_versions",
    "evidence_statuses",
    "source_statuses",
    "revision_statuses",
    "current_revisions_only",
    "require_complete_locator",
    "excluded_coverage_states",
}
RANKING_KEYS = {"preferences"}
BUDGET_KEYS = set(AI_SELECTION_HARD_MAXIMA)
RANKING_FIELDS = {
    "source_type",
    "source_subtype",
    "extension",
    "authority_level",
    "evidence_kind",
    "fragment_type",
    "producer",
    "producer_version",
    "coverage_state",
    "status",
    "current_revision",
    "locator_complete",
}
REASON_ORDER = (
    "included_by_policy",
    "inactive_source",
    "not_current_revision",
    "inactive_evidence",
    "invalid_evidence_metadata",
    "source_type_excluded",
    "source_subtype_excluded",
    "extension_excluded",
    "authority_level_excluded",
    "evidence_kind_excluded",
    "fragment_type_excluded",
    "producer_excluded",
    "producer_version_excluded",
    "incomplete_locator",
    "deterministic_coverage_excluded",
    "coverage_state_excluded",
    "lower_rank",
    "selection_item_budget_exceeded",
    "selection_char_budget_exceeded",
)
REASON_CATALOG_VERSION = "1"
SELECTION_REASON_CODES = frozenset(
    {
        *REASON_ORDER,
        "selection_plan_stale",
        "no_ai_eligible_evidence",
        "invalid_selection_policy",
        "selection_profile_conflict",
    }
)


class AiSelectionError(RuntimeError):
    def __init__(self, message: str, *, reason: str = "selection_invalid", exit_code: int = 2):
        super().__init__(message)
        self.reason = reason
        self.exit_code = exit_code


class AiSelectionStaleError(AiSelectionError):
    def __init__(self, plan_id: str, expected: str, actual: str):
        super().__init__(
            f"Selection plan {plan_id} is stale: relevant state changed "
            f"({expected} -> {actual}).",
            reason="selection_plan_stale",
            exit_code=4,
        )


class AiSelectionEmptyError(AiSelectionError):
    def __init__(self, plan_id: str):
        super().__init__(
            f"Selection plan {plan_id} contains no included evidence; no package was created.",
            reason="no_ai_eligible_evidence",
            exit_code=4,
        )


@dataclass(frozen=True)
class SelectionPolicy:
    name: str
    version: str
    route: str
    route_version: str
    description: str
    criteria: dict[str, Any]
    preferences: tuple[tuple[str, str], ...]
    budget: dict[str, int]
    resolved: dict[str, Any]
    config_hash: str


@dataclass(frozen=True)
class SelectionPlanResult:
    selection_plan_id: str
    run_id: str
    policy_name: str
    policy_version: str
    route: str
    route_version: str
    profile_name: str
    policy_config_hash: str
    resolved_config_hash: str
    relevant_state_hash: str
    plan_hash: str
    examined_count: int
    included_count: int
    excluded_count: int
    selected_chars: int
    reason_summary: dict[str, int]
    report_path: str


@dataclass(frozen=True)
class PreparedSelectionPackage:
    selection_plan_id: str
    selection_plan: dict[str, Any]
    source_revisions: list[dict[str, Any]]
    chunks: list[dict[str, Any]]
    fragments: list[dict[str, Any]]
    evidence_order: list[dict[str, Any]]


def load_selection_policy(workspace_dir: str | Path, policy_name: str) -> SelectionPolicy:
    if not _safe_name(policy_name):
        raise AiSelectionError(
            f"Invalid AI selection policy name: {policy_name}.",
            reason="invalid_selection_policy",
        )
    policy_dir = (Path(workspace_dir) / "configs" / "ai_selection").resolve()
    path = (policy_dir / f"{policy_name}.yaml").resolve()
    try:
        path.relative_to(policy_dir)
    except ValueError as exc:
        raise AiSelectionError(
            f"AI selection policy path escapes configs/ai_selection: {policy_name}.",
            reason="invalid_selection_policy",
        ) from exc
    if not path.is_file():
        raise AiSelectionError(
            f"AI selection policy not found: configs/ai_selection/{policy_name}.yaml.",
            reason="invalid_selection_policy",
        )
    raw = parse_simple_yaml(path.read_text(encoding="utf-8"))
    _reject_unknown(raw, POLICY_SECTIONS, "policy section")
    for section in POLICY_SECTIONS:
        if not isinstance(raw.get(section), dict):
            raise AiSelectionError(
                f"AI selection policy {policy_name} is missing section: {section}.",
                reason="invalid_selection_policy",
            )
    policy = dict(raw["policy"])
    criteria = dict(raw["criteria"])
    ranking = dict(raw["ranking"])
    budget = dict(raw["budget"])
    _reject_unknown(policy, POLICY_KEYS, "policy key")
    _reject_unknown(criteria, CRITERIA_KEYS, "criteria key")
    _reject_unknown(ranking, RANKING_KEYS, "ranking key")
    _reject_unknown(budget, BUDGET_KEYS, "budget key")

    actual_name = _required_text(policy, "policy_id")
    if actual_name != policy_name:
        raise AiSelectionError(
            f"Policy filename/name mismatch: {policy_name} != {actual_name}.",
            reason="invalid_selection_policy",
        )
    version = _required_text(policy, "policy_version")
    route = _required_text(policy, "route_id")
    route_version = _required_text(policy, "route_version")
    if route not in ROUTES:
        raise AiSelectionError(
            f"Unsupported AI selection route: {route}.",
            reason="invalid_selection_policy",
        )
    description = policy.get("description", "")
    if not isinstance(description, str):
        raise AiSelectionError(
            "policy.description must be a string.", reason="invalid_selection_policy"
        )

    resolved_criteria: dict[str, Any] = {}
    for key in CRITERIA_KEYS - {"current_revisions_only", "require_complete_locator"}:
        resolved_criteria[key] = _string_list(criteria.get(key, []), f"criteria.{key}")
    resolved_criteria["current_revisions_only"] = _boolean(
        criteria.get("current_revisions_only", True), "criteria.current_revisions_only"
    )
    resolved_criteria["require_complete_locator"] = _boolean(
        criteria.get("require_complete_locator", False), "criteria.require_complete_locator"
    )
    kinds = resolved_criteria["evidence_kinds"]
    if any(item not in {"chunk", "fragment"} for item in kinds):
        raise AiSelectionError(
            "criteria.evidence_kinds accepts only chunk and fragment.",
            reason="invalid_selection_policy",
        )
    invalid_coverage = sorted(
        set(resolved_criteria["excluded_coverage_states"]) - COVERAGE_STATES
    )
    if invalid_coverage:
        raise AiSelectionError(
            f"Unsupported coverage state: {invalid_coverage[0]}.",
            reason="invalid_selection_policy",
        )

    preference_values = _string_list(ranking.get("preferences", []), "ranking.preferences")
    preferences: list[tuple[str, str]] = []
    for value in preference_values:
        if "=" not in value:
            raise AiSelectionError(
                f"Invalid ranking preference: {value}.", reason="invalid_selection_policy"
            )
        field, preferred = value.split("=", 1)
        field, preferred = field.strip(), preferred.strip()
        if field not in RANKING_FIELDS or not preferred:
            raise AiSelectionError(
                f"Invalid ranking preference: {value}.", reason="invalid_selection_policy"
            )
        if field in {"current_revision", "locator_complete"} and preferred not in {
            "true",
            "false",
        }:
            raise AiSelectionError(
                f"Ranking preference {field} must use true or false.",
                reason="invalid_selection_policy",
            )
        if field == "coverage_state" and preferred not in COVERAGE_STATES:
            raise AiSelectionError(
                f"Unsupported coverage state in ranking: {preferred}.",
                reason="invalid_selection_policy",
            )
        preferences.append((field, preferred))

    resolved_budget: dict[str, int] = {}
    for key, hard_maximum in AI_SELECTION_HARD_MAXIMA.items():
        value = budget.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise AiSelectionError(
                f"budget.{key} must be a positive integer.",
                reason="invalid_selection_policy",
            )
        if value > hard_maximum:
            raise AiSelectionError(
                f"budget.{key} exceeds the hard maximum of {hard_maximum}.",
                reason="selection_budget_hard_limit",
            )
        resolved_budget[key] = value

    resolved = {
        "budget": resolved_budget,
        "criteria": resolved_criteria,
        "empty_list_semantics": "no_restriction",
        "policy": {
            "description": description,
            "policy_id": actual_name,
            "policy_version": version,
            "route_id": route,
            "route_version": route_version,
        },
        "ranking": {
            "preferences": [f"{field}={value}" for field, value in preferences]
        },
    }
    return SelectionPolicy(
        name=actual_name,
        version=version,
        route=route,
        route_version=route_version,
        description=description,
        criteria=resolved_criteria,
        preferences=tuple(preferences),
        budget=resolved_budget,
        resolved=resolved,
        config_hash=canonical_sha256_v1(resolved),
    )


def create_selection_plan(
    workspace_dir: str | Path,
    *,
    policy_name: str,
    revision_ids: tuple[str, ...] = (),
    profile_name: str = "ai_package.default",
) -> SelectionPlanResult:
    settings = resolve_database_settings(workspace_dir)
    policy = load_selection_policy(settings.workspace_dir, policy_name)
    project_config = load_config(settings.workspace_dir)
    profile = load_worker_profile(
        settings.workspace_dir,
        profile_name,
        required_sections=("worker", "ai_package"),
    )
    worker_config = dict(profile["worker"])
    ai_package_options = dict(profile["ai_package"])
    package_options = parse_ai_package_options(ai_package_options)
    _validate_policy_profile(policy, package_options)
    profile_snapshot = {"ai_package": ai_package_options, "worker": worker_config}
    profile_hash = canonical_sha256_v1(profile_snapshot)
    _validate_policy_budgets(policy, dict(project_config["ai_selection"]))

    connection = open_database(settings.database_path, enable_wal=settings.wal_enabled)
    try:
        validate_database_migrations(connection)
        scope = _resolve_scope(connection, revision_ids)
        evidence = _load_evidence(connection, scope)
        if len(evidence) > policy.budget["max_examined_evidence"]:
            raise AiSelectionError(
                "Examined-evidence budget exceeded before selection: "
                f"{len(evidence)} > {policy.budget['max_examined_evidence']}.",
                reason="selection_examined_budget_exceeded",
                exit_code=4,
            )
        coverage = _load_coverage(connection, evidence)
        relevant_state = _relevant_state(scope, evidence, coverage)
    finally:
        connection.close()

    relevant_state_hash = canonical_sha256_v1(relevant_state)
    items = _select_items(
        evidence,
        coverage,
        policy=policy,
        max_evidence_chars=package_options.max_evidence_chars,
    )
    included_count = sum(item["outcome"] == "included" for item in items)
    selected_chars = sum(
        item["package_char_count"] for item in items if item["outcome"] == "included"
    )
    reason_summary = dict(
        sorted(
            Counter(
                reason
                for item in items
                for reason in item["reason_codes"]
            ).items()
        )
    )
    resolved_config = {
        "character_accounting": (
            "len(text with CRLF/CR normalized to LF), capped per evidence by "
            "profile.ai_package.max_evidence_chars"
        ),
        "policy": policy.resolved,
        "profile": {"config": profile_snapshot, "name": profile_name},
        "reason_catalog_version": REASON_CATALOG_VERSION,
    }
    resolved_config_hash = canonical_sha256_v1(resolved_config)
    plan_projection = {
        "items": [
            {
                "coverage_state": item["coverage_state"],
                "evidence_id": item["evidence_id"],
                "evidence_kind": item["evidence_kind"],
                "outcome": item["outcome"],
                "package_char_count": item["package_char_count"],
                "rank": item["rank"],
                "reason_codes": item["reason_codes"],
                "matched_criteria": item["matched_criteria"],
                "sort_key": item["sort_key"],
                "source_revision_id": item["source_revision_id"],
            }
            for item in _items_for_artifact(items)
        ],
        "policy": {
            "config_hash": policy.config_hash,
            "policy_id": policy.name,
            "policy_version": policy.version,
        },
        "profile": {"config_hash": profile_hash, "name": profile_name},
        "relevant_state_hash": relevant_state_hash,
        "resolved_config_hash": resolved_config_hash,
        "resolved_config": resolved_config,
        "route": {"route_id": policy.route, "route_version": policy.route_version},
        "schema_version": 1,
        "scope": scope,
    }
    plan_hash = canonical_sha256_v1(plan_projection)

    started = start_run(
        settings.workspace_dir,
        run_type="ai_evidence_selection",
        input_payload={
            "policy": policy.name,
            "profile": profile_name,
            "revision_ids": list(scope["revision_ids"]),
            "scope_mode": scope["mode"],
        },
        cli_options={"ai_selection": project_config["ai_selection"]},
    )
    try:
        result = _persist_selection_plan(
            settings,
            run_id=started.record.run_id,
            policy=policy,
            profile_name=profile_name,
            profile_hash=profile_hash,
            resolved_config_hash=resolved_config_hash,
            scope=scope,
            resolved_config=resolved_config,
            relevant_state=relevant_state,
            relevant_state_hash=relevant_state_hash,
            plan_hash=plan_hash,
            items=items,
            selected_chars=selected_chars,
            reason_summary=reason_summary,
        )
        complete_run(settings.workspace_dir, started.record.run_id, output_payload=_result_payload(result))
        return result
    except Exception as exc:
        try:
            fail_run(settings.workspace_dir, started.record.run_id, error=str(exc))
        except Exception:
            pass
        raise


def list_selection_items(
    workspace_dir: str | Path,
    plan_id: str,
    *,
    outcome: str | None = None,
) -> list[dict[str, Any]]:
    if outcome not in {None, "included", "excluded"}:
        raise AiSelectionError(f"Unsupported selection outcome: {outcome}.")
    settings = resolve_database_settings(workspace_dir)
    connection = open_database(settings.database_path, enable_wal=settings.wal_enabled)
    try:
        validate_database_migrations(connection)
        _require_plan(connection, plan_id)
        where = "AND outcome = ?" if outcome else ""
        parameters: tuple[Any, ...] = (plan_id, outcome) if outcome else (plan_id,)
        rows = connection.execute(
            f"""
            SELECT *
            FROM ai_evidence_selection_items
            WHERE selection_plan_id = ? {where}
            ORDER BY outcome, COALESCE(selection_rank, 2147483647), evidence_id
            """,
            parameters,
        ).fetchall()
        return [_item_row(row) for row in rows]
    finally:
        connection.close()


def explain_selection_item(
    workspace_dir: str | Path,
    plan_id: str,
    evidence_id: str,
) -> dict[str, Any]:
    settings = resolve_database_settings(workspace_dir)
    connection = open_database(settings.database_path, enable_wal=settings.wal_enabled)
    try:
        validate_database_migrations(connection)
        plan = _require_plan(connection, plan_id)
        rows = connection.execute(
            """
            SELECT * FROM ai_evidence_selection_items
            WHERE selection_plan_id = ? AND evidence_id = ?
            ORDER BY evidence_kind
            """,
            (plan_id, evidence_id),
        ).fetchall()
        if not rows:
            raise AiSelectionError(
                f"Evidence {evidence_id} is not present in selection plan {plan_id}.",
                reason="selection_evidence_not_found",
            )
        if len(rows) != 1:
            raise AiSelectionError(f"Evidence id is ambiguous in plan {plan_id}: {evidence_id}.")
        return {
            "plan": _plan_header(plan),
            "item": _item_row(rows[0]),
        }
    finally:
        connection.close()


def prepare_selection_package(
    workspace_dir: str | Path,
    *,
    plan_id: str,
    profile_name: str,
) -> PreparedSelectionPackage:
    settings = resolve_database_settings(workspace_dir)
    profile = load_worker_profile(
        settings.workspace_dir,
        profile_name,
        required_sections=("worker", "ai_package"),
    )
    current_profile_hash = canonical_sha256_v1(
        {"ai_package": dict(profile["ai_package"]), "worker": dict(profile["worker"])}
    )
    options = parse_ai_package_options(dict(profile["ai_package"]))
    connection = open_database(settings.database_path, enable_wal=settings.wal_enabled)
    try:
        validate_database_migrations(connection)
        plan = _require_plan(connection, plan_id)
        if plan["profile_name"] != profile_name or plan["profile_config_hash"] != current_profile_hash:
            raise AiSelectionError(
                "Selection plan/profile mismatch; reuse the exact profile snapshot used by the plan.",
                reason="selection_profile_conflict",
            )
        scope = _json_object(plan["scope_json"], "scope_json")
        current_evidence = _load_evidence(connection, scope)
        current_coverage = _load_coverage(connection, current_evidence)
        current_state_hash = canonical_sha256_v1(
            _relevant_state(scope, current_evidence, current_coverage)
        )
        if current_state_hash != plan["relevant_state_hash"]:
            raise AiSelectionStaleError(
                plan_id,
                str(plan["relevant_state_hash"]),
                current_state_hash,
            )
        item_rows = connection.execute(
            """
            SELECT * FROM ai_evidence_selection_items
            WHERE selection_plan_id = ? AND outcome = 'included'
            ORDER BY selection_rank
            """,
            (plan_id,),
        ).fetchall()
        if not item_rows:
            raise AiSelectionEmptyError(plan_id)
        if any(row["evidence_kind"] == "chunk" for row in item_rows) and not options.include_chunks:
            raise AiSelectionError(
                "Selection includes chunks but the package profile disables chunks.",
                reason="selection_profile_conflict",
            )
        if any(row["evidence_kind"] == "fragment" for row in item_rows) and not options.include_fragments:
            raise AiSelectionError(
                "Selection includes fragments but the package profile disables fragments.",
                reason="selection_profile_conflict",
            )
        chunks, fragments, order = _load_selected_evidence(connection, item_rows)
        source_revisions = _load_selected_revisions(connection, item_rows)
        all_items = connection.execute(
            """
            SELECT * FROM ai_evidence_selection_items
            WHERE selection_plan_id = ?
            ORDER BY outcome, COALESCE(selection_rank, 2147483647), evidence_id
            """,
            (plan_id,),
        ).fetchall()
        artifact = {
            **_plan_header(plan),
            "items": [_item_row(row) for row in all_items],
            "schema_version": 1,
        }
        return PreparedSelectionPackage(
            selection_plan_id=plan_id,
            selection_plan=artifact,
            source_revisions=source_revisions,
            chunks=chunks,
            fragments=fragments,
            evidence_order=order,
        )
    finally:
        connection.close()


def _persist_selection_plan(
    settings: DatabaseSettings,
    *,
    run_id: str,
    policy: SelectionPolicy,
    profile_name: str,
    profile_hash: str,
    resolved_config_hash: str,
    scope: dict[str, Any],
    resolved_config: dict[str, Any],
    relevant_state: dict[str, Any],
    relevant_state_hash: str,
    plan_hash: str,
    items: list[dict[str, Any]],
    selected_chars: int,
    reason_summary: dict[str, int],
) -> SelectionPlanResult:
    connection = open_database(settings.database_path, enable_wal=settings.wal_enabled)
    try:
        validate_database_migrations(connection)
        connection.execute("BEGIN")
        plan_id = next_id(
            connection,
            "ai_evidence_selection_plans",
            "selection_plan_id",
            "AISEL",
        )
        created_at = timestamp_now(None)
        report_file = run_artifact_paths(settings.workspace_dir, run_id).artifact_dir / (
            "selection_plan_report.json"
        )
        report_path = relative_workspace_path(settings.workspace_dir, report_file)
        included = sum(item["outcome"] == "included" for item in items)
        result = SelectionPlanResult(
            selection_plan_id=plan_id,
            run_id=run_id,
            policy_name=policy.name,
            policy_version=policy.version,
            route=policy.route,
            route_version=policy.route_version,
            profile_name=profile_name,
            policy_config_hash=policy.config_hash,
            resolved_config_hash=resolved_config_hash,
            relevant_state_hash=relevant_state_hash,
            plan_hash=plan_hash,
            examined_count=len(items),
            included_count=included,
            excluded_count=len(items) - included,
            selected_chars=selected_chars,
            reason_summary=reason_summary,
            report_path=report_path,
        )
        report = {
            **_result_payload(result),
            "character_accounting": resolved_config["character_accounting"],
            "items": _items_for_artifact(items),
            "resolved_config": resolved_config,
            "schema_version": 1,
            "scope": scope,
        }
        report_file.write_text(
            canonical_json_artifact_v1(report), encoding="utf-8", newline="\n"
        )
        connection.execute(
            """
            INSERT INTO ai_evidence_selection_plans (
                selection_plan_id, run_id, policy_id, policy_version, route_id,
                route_version, profile_name, policy_config_hash, profile_config_hash,
                resolved_config_hash, relevant_state_hash, selection_plan_hash,
                scope_json, resolved_config_json,
                relevant_state_json, examined_count, included_count, excluded_count,
                selected_chars, reason_summary_json, report_path, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'completed', ?)
            """,
            (
                plan_id,
                run_id,
                policy.name,
                policy.version,
                policy.route,
                policy.route_version,
                profile_name,
                policy.config_hash,
                profile_hash,
                resolved_config_hash,
                relevant_state_hash,
                plan_hash,
                canonical_json_v1(scope),
                canonical_json_v1(resolved_config),
                canonical_json_v1(relevant_state),
                len(items),
                included,
                len(items) - included,
                selected_chars,
                canonical_json_v1(reason_summary),
                report_path,
                created_at,
            ),
        )
        for item in items:
            connection.execute(
                """
                INSERT INTO ai_evidence_selection_items (
                    selection_plan_id, evidence_kind, evidence_id, source_revision_id,
                    sequence, outcome, selection_rank, normalized_char_count,
                    package_char_count, coverage_state, reason_codes_json,
                    matched_criteria_json, coverage_refs_json, sort_key_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    plan_id,
                    item["evidence_kind"],
                    item["evidence_id"],
                    item["source_revision_id"],
                    item["sequence"],
                    item["outcome"],
                    item["rank"],
                    item["normalized_char_count"],
                    item["package_char_count"],
                    item["coverage_state"],
                    canonical_json_v1(item["reason_codes"]),
                    canonical_json_v1(item["matched_criteria"]),
                    canonical_json_v1(item["coverage_refs"]),
                    canonical_json_v1(item["sort_key"]),
                ),
            )
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _resolve_scope(
    connection: sqlite3.Connection, revision_ids: tuple[str, ...]
) -> dict[str, Any]:
    requested = tuple(sorted(dict.fromkeys(revision_ids)))
    if requested:
        placeholders = ",".join("?" for _ in requested)
        rows = connection.execute(
            f"SELECT source_revision_id FROM source_revisions "
            f"WHERE source_revision_id IN ({placeholders})",
            requested,
        ).fetchall()
        found = {str(row["source_revision_id"]) for row in rows}
        missing = [revision for revision in requested if revision not in found]
        if missing:
            raise AiSelectionError(
                "Source revision was not found: " + ", ".join(missing) + ".",
                reason="selection_revision_not_found",
            )
        return {"mode": "explicit_revisions", "revision_ids": list(requested)}
    return {"mode": "all_registered_evidence", "revision_ids": []}


def _load_evidence(
    connection: sqlite3.Connection, scope: dict[str, Any]
) -> list[dict[str, Any]]:
    revision_ids = tuple(scope.get("revision_ids", []))
    where = ""
    parameters: tuple[Any, ...] = ()
    if revision_ids:
        placeholders = ",".join("?" for _ in revision_ids)
        where = f"WHERE e.source_revision_id IN ({placeholders})"
        parameters = revision_ids
    common = """
        e.source_revision_id, e.sequence, e.text, e.text_hash,
        e.metadata_json, e.status AS evidence_status,
        sr.source_id, sr.content_hash, sr.file_path,
        sr.status AS revision_status, s.logical_name, s.source_type,
        s.source_subtype, s.authority_level, s.current_revision_id,
        s.status AS source_status
    """
    chunks = connection.execute(
        f"""
        SELECT 'chunk' AS evidence_kind, e.chunk_id AS evidence_id,
               NULL AS fragment_type, NULL AS path_or_selector,
               NULL AS line_start, NULL AS line_end,
               NULL AS char_start, NULL AS char_end, {common}
        FROM chunks e
        JOIN source_revisions sr ON sr.source_revision_id = e.source_revision_id
        JOIN sources s ON s.source_id = sr.source_id
        {where}
        ORDER BY e.source_revision_id, e.sequence, e.chunk_id
        """,
        parameters,
    ).fetchall()
    fragments = connection.execute(
        f"""
        SELECT 'fragment' AS evidence_kind, e.fragment_id AS evidence_id,
               e.fragment_type, e.path_or_selector,
               e.line_start, e.line_end, e.char_start, e.char_end, {common}
        FROM source_fragments e
        JOIN source_revisions sr ON sr.source_revision_id = e.source_revision_id
        JOIN sources s ON s.source_id = sr.source_id
        {where}
        ORDER BY e.source_revision_id, e.sequence, e.fragment_id
        """,
        parameters,
    ).fetchall()
    evidence: list[dict[str, Any]] = []
    for row in (*chunks, *fragments):
        metadata, metadata_valid = _evidence_metadata(row["metadata_json"])
        text = _normalize_newlines(str(row["text"]))
        kind = str(row["evidence_kind"])
        producer = metadata.get("chunker") if kind == "chunk" else metadata.get("parser")
        producer_version = (
            metadata.get("chunker_version") if kind == "chunk" else metadata.get("parser_version")
        )
        locator_complete = _locator_complete(row, metadata)
        evidence.append(
            {
                "authority_level": str(row["authority_level"]),
                "char_end": row["char_end"],
                "char_start": row["char_start"],
                "content_hash": str(row["content_hash"]),
                "current_revision": row["current_revision_id"] == row["source_revision_id"],
                "current_revision_id": row["current_revision_id"],
                "evidence_id": str(row["evidence_id"]),
                "evidence_kind": kind,
                "extension": Path(str(row["file_path"])).suffix.casefold(),
                "file_path": str(row["file_path"]),
                "fragment_type": row["fragment_type"],
                "line_end": row["line_end"],
                "line_start": row["line_start"],
                "locator_complete": locator_complete,
                "logical_name": str(row["logical_name"]),
                "metadata": metadata,
                "metadata_valid": metadata_valid,
                "path_or_selector": row["path_or_selector"],
                "producer": "" if producer is None else str(producer),
                "producer_version": "" if producer_version is None else str(producer_version),
                "revision_status": str(row["revision_status"]),
                "sequence": int(row["sequence"]),
                "source_id": str(row["source_id"]),
                "source_revision_id": str(row["source_revision_id"]),
                "source_status": str(row["source_status"]),
                "source_subtype": "" if row["source_subtype"] is None else str(row["source_subtype"]),
                "source_type": str(row["source_type"]),
                "status": str(row["evidence_status"]),
                "text": text,
                "text_hash": row["text_hash"] or hashlib.sha256(text.encode("utf-8")).hexdigest(),
            }
        )
    evidence.sort(key=_tie_break)
    return evidence


def _load_coverage(
    connection: sqlite3.Connection, evidence: list[dict[str, Any]]
) -> dict[tuple[str, str], dict[str, Any]]:
    keys = {(item["evidence_kind"], item["evidence_id"]) for item in evidence}
    applicable_by_key: dict[tuple[str, str], list[str]] = {}
    for item in evidence:
        applicable_by_key[(item["evidence_kind"], item["evidence_id"])] = (
            _applicable_rules(item) if item["evidence_kind"] == "fragment" else []
        )
    references: dict[tuple[str, str], list[dict[str, Any]]] = {key: [] for key in keys}
    rows = connection.execute(
        """
        SELECT
            root.candidate_record_id AS root_candidate_record_id,
            root.chunk_id AS root_chunk_id,
            root.fragment_id AS root_fragment_id,
            root.payload_json AS root_payload_json,
            node.candidate_record_id,
            node.payload_json,
            CASE WHEN EXISTS (
                SELECT 1 FROM candidate_lineage child
                WHERE child.parent_candidate_record_id = node.candidate_record_id
            ) THEN 0 ELSE 1 END AS is_leaf,
            head.decision_id,
            decision.outcome AS review_outcome,
            decision.semantic_payload_hash AS decision_hash
        FROM candidate_records root
        JOIN candidate_batches batch ON batch.batch_id = root.batch_id
        JOIN candidate_lineage lineage
          ON lineage.root_candidate_record_id = root.candidate_record_id
        JOIN candidate_records node
          ON node.candidate_record_id = lineage.candidate_record_id
        LEFT JOIN review_subject_heads head
          ON head.subject_type = 'candidate_record'
         AND head.subject_id = node.candidate_record_id
        LEFT JOIN review_decisions decision ON decision.decision_id = head.decision_id
        WHERE batch.origin_type = 'deterministic_derivation'
          AND root.supersedes_candidate_record_id IS NULL
        ORDER BY root.candidate_record_id, node.candidate_record_id
        """
    ).fetchall()
    for row in rows:
        kind = "chunk" if row["root_chunk_id"] is not None else "fragment"
        evidence_id = row["root_chunk_id"] or row["root_fragment_id"]
        key = (kind, str(evidence_id))
        if key not in references:
            continue
        root_payload = _json_object(row["root_payload_json"], "candidate payload")
        rule_id = str(root_payload.get("rule_id", ""))
        rule_version = str(root_payload.get("rule_version", ""))
        rule = f"{rule_id}/{rule_version}" if rule_id and rule_version else ""
        if rule not in applicable_by_key[key]:
            continue
        references[key].append(
            {
                "candidate_record_id": str(row["candidate_record_id"]),
                "current_decision_id": row["decision_id"],
                "current_outcome": row["review_outcome"] or "pending",
                "decision_hash": row["decision_hash"],
                "is_leaf": bool(row["is_leaf"]),
                "root_candidate_record_id": str(row["root_candidate_record_id"]),
                "rule": rule,
            }
        )
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for key in sorted(keys):
        applicable = applicable_by_key[key]
        refs = references[key]
        if not applicable:
            state = "no_rule_applicable"
        elif not refs:
            state = "applicable_no_candidate"
        else:
            leaves = [ref for ref in refs if ref["is_leaf"]]
            outcomes = {str(ref["current_outcome"]) for ref in leaves}
            if "confirmed" in outcomes:
                state = "confirmed"
            elif leaves and outcomes == {"rejected"}:
                state = "rejected"
            elif any(not ref["is_leaf"] for ref in refs) or "superseded" in outcomes:
                state = "superseded_non_leaf"
            elif "pending" in outcomes:
                state = "pending"
            else:
                state = "superseded_non_leaf"
        result[key] = {
            "applicable_rules": applicable,
            "references": refs,
            "state": state,
        }
    return result


def _select_items(
    evidence: list[dict[str, Any]],
    coverage: dict[tuple[str, str], dict[str, Any]],
    *,
    policy: SelectionPolicy,
    max_evidence_chars: int,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    eligible: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    for source in evidence:
        covered = coverage[(source["evidence_kind"], source["evidence_id"])]
        attributes = {**source, "coverage_state": covered["state"]}
        reasons, matched = _eligibility(attributes, policy.criteria)
        sort_key = _ranking_key(attributes, policy.preferences)
        item = {
            "coverage_refs": {
                "applicable_rules": covered["applicable_rules"],
                "references": covered["references"],
            },
            "coverage_state": covered["state"],
            "evidence_id": source["evidence_id"],
            "evidence_kind": source["evidence_kind"],
            "matched_criteria": matched
            + [
                f"ranking:{field}={value}"
                for field, value in policy.preferences
                if _rank_value(attributes, field) == value
            ],
            "normalized_char_count": len(source["text"]),
            "outcome": "excluded" if reasons else "eligible",
            "package_char_count": min(len(source["text"]), max_evidence_chars),
            "rank": None,
            "reason_codes": _ordered_reasons(reasons),
            "sequence": source["sequence"],
            "sort_key": list(sort_key),
            "source_revision_id": source["source_revision_id"],
        }
        items.append(item)
        if not reasons:
            eligible.append((sort_key, item))

    selected_count = 0
    selected_chars = 0
    for _, item in sorted(eligible, key=lambda pair: pair[0]):
        reasons: list[str] = []
        if selected_count >= policy.budget["max_selected_evidence"]:
            reasons.extend(("lower_rank", "selection_item_budget_exceeded"))
        elif selected_chars + item["package_char_count"] > policy.budget["max_selected_chars"]:
            reasons.extend(("lower_rank", "selection_char_budget_exceeded"))
        if reasons:
            item["outcome"] = "excluded"
            item["reason_codes"] = _ordered_reasons(reasons)
            continue
        selected_count += 1
        selected_chars += item["package_char_count"]
        item["outcome"] = "included"
        item["rank"] = selected_count
        item["reason_codes"] = ["included_by_policy"]

    items.sort(key=lambda item: (item["evidence_kind"], item["evidence_id"]))
    return items


def _eligibility(
    item: dict[str, Any], criteria: dict[str, Any]
) -> tuple[list[str], list[str]]:
    reasons: list[str] = []
    matched: list[str] = []
    if not item["metadata_valid"]:
        reasons.append("invalid_evidence_metadata")
    if criteria["source_statuses"] and item["source_status"] not in criteria["source_statuses"]:
        reasons.append("inactive_source")
    else:
        matched.append(f"source_status={item['source_status']}")
    if criteria["revision_statuses"] and item["revision_status"] not in criteria["revision_statuses"]:
        reasons.append("inactive_source")
    else:
        matched.append(f"revision_status={item['revision_status']}")
    if criteria["current_revisions_only"] and not item["current_revision"]:
        reasons.append("not_current_revision")
    elif item["current_revision"]:
        matched.append("current_revision=true")
    if criteria["evidence_statuses"] and item["status"] not in criteria["evidence_statuses"]:
        reasons.append("inactive_evidence")
    else:
        matched.append(f"evidence_status={item['status']}")
    checks = (
        ("source_types", "source_type", "source_type_excluded"),
        ("source_subtypes", "source_subtype", "source_subtype_excluded"),
        ("extensions", "extension", "extension_excluded"),
        ("authority_levels", "authority_level", "authority_level_excluded"),
        ("evidence_kinds", "evidence_kind", "evidence_kind_excluded"),
        ("fragment_types", "fragment_type", "fragment_type_excluded"),
        ("producers", "producer", "producer_excluded"),
        ("producer_versions", "producer_version", "producer_version_excluded"),
    )
    for config_key, item_key, reason in checks:
        if config_key == "fragment_types" and item["evidence_kind"] != "fragment":
            continue
        allowed = criteria[config_key]
        if allowed and item[item_key] not in allowed:
            reasons.append(reason)
        elif allowed:
            matched.append(f"{item_key}={item[item_key]}")
    if criteria["require_complete_locator"] and not item["locator_complete"]:
        reasons.append("incomplete_locator")
    elif item["locator_complete"]:
        matched.append("locator_complete=true")
    if item["coverage_state"] in criteria["excluded_coverage_states"]:
        reasons.append(
            "deterministic_coverage_excluded"
        )
    else:
        matched.append(f"coverage_state={item['coverage_state']}")
    return reasons, matched


def _ranking_key(
    item: dict[str, Any], preferences: tuple[tuple[str, str], ...]
) -> tuple[Any, ...]:
    preference_key = tuple(
        0 if _rank_value(item, field) == preferred else 1
        for field, preferred in preferences
    )
    return (*preference_key, *_tie_break(item))


def _rank_value(item: dict[str, Any], field: str) -> str:
    if field in {"current_revision", "locator_complete"}:
        return "true" if item[field] else "false"
    if field == "status":
        return str(item["status"])
    value = item.get(field)
    return "" if value is None else str(value)


def _tie_break(item: dict[str, Any]) -> tuple[str, str, int, str]:
    return (
        str(item["source_revision_id"]),
        str(item["evidence_kind"]),
        int(item["sequence"]),
        str(item["evidence_id"]),
    )


def _relevant_state(
    scope: dict[str, Any],
    evidence: list[dict[str, Any]],
    coverage: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any]:
    projections = []
    for item in evidence:
        covered = coverage[(item["evidence_kind"], item["evidence_id"])]
        projections.append(
            {
                "authority_level": item["authority_level"],
                "content_hash": item["content_hash"],
                "coverage": covered,
                "current_revision_id": item["current_revision_id"],
                "evidence_id": item["evidence_id"],
                "evidence_kind": item["evidence_kind"],
                "extension": item["extension"],
                "file_path": item["file_path"],
                "fragment_type": item["fragment_type"],
                "locator": {
                    "char_end": item["char_end"],
                    "char_start": item["char_start"],
                    "complete": item["locator_complete"],
                    "line_end": item["line_end"],
                    "line_start": item["line_start"],
                    "path_or_selector": item["path_or_selector"],
                },
                "metadata": item["metadata"],
                "metadata_valid": item["metadata_valid"],
                "producer": item["producer"],
                "producer_version": item["producer_version"],
                "revision_status": item["revision_status"],
                "sequence": item["sequence"],
                "source_id": item["source_id"],
                "source_revision_id": item["source_revision_id"],
                "source_status": item["source_status"],
                "source_subtype": item["source_subtype"],
                "source_type": item["source_type"],
                "status": item["status"],
                "text_hash": item["text_hash"],
            }
        )
    return {"evidence": projections, "schema_version": 1, "scope": scope}


def _load_selected_evidence(
    connection: sqlite3.Connection, rows: Iterable[sqlite3.Row]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    chunks: list[dict[str, Any]] = []
    fragments: list[dict[str, Any]] = []
    order: list[dict[str, Any]] = []
    for row in rows:
        kind = str(row["evidence_kind"])
        evidence_id = str(row["evidence_id"])
        if kind == "chunk":
            current = connection.execute(
                """
                SELECT chunk_id, source_revision_id, sequence, text, text_hash, status
                FROM chunks WHERE chunk_id = ?
                """,
                (evidence_id,),
            ).fetchone()
            if current is None:
                raise AiSelectionStaleError(str(row["selection_plan_id"]), "present", "missing")
            chunks.append(
                {
                    "chunk_id": current["chunk_id"],
                    "sequence": int(current["sequence"]),
                    "source_revision_id": current["source_revision_id"],
                    "status": current["status"],
                    "text": _normalize_newlines(current["text"]),
                    "text_hash": current["text_hash"],
                }
            )
        else:
            current = connection.execute(
                """
                SELECT fragment_id, source_revision_id, fragment_type, sequence,
                       path_or_selector, text, text_hash, status
                FROM source_fragments WHERE fragment_id = ?
                """,
                (evidence_id,),
            ).fetchone()
            if current is None:
                raise AiSelectionStaleError(str(row["selection_plan_id"]), "present", "missing")
            fragments.append(
                {
                    "fragment_id": current["fragment_id"],
                    "fragment_type": current["fragment_type"],
                    "path_or_selector": current["path_or_selector"],
                    "sequence": int(current["sequence"]),
                    "source_revision_id": current["source_revision_id"],
                    "status": current["status"],
                    "text": _normalize_newlines(current["text"]),
                    "text_hash": current["text_hash"],
                }
            )
        order.append({"evidence_id": evidence_id, "evidence_kind": kind, "rank": row["selection_rank"]})
    return chunks, fragments, order


def _load_selected_revisions(
    connection: sqlite3.Connection, rows: Iterable[sqlite3.Row]
) -> list[dict[str, Any]]:
    revision_ids = tuple(sorted({str(row["source_revision_id"]) for row in rows}))
    placeholders = ",".join("?" for _ in revision_ids)
    found = connection.execute(
        f"""
        SELECT sr.source_revision_id, sr.source_id, sr.content_hash, sr.file_path,
               sr.status AS revision_status, s.current_revision_id, s.source_type,
               s.source_subtype, s.authority_level
        FROM source_revisions sr
        JOIN sources s ON s.source_id = sr.source_id
        WHERE sr.source_revision_id IN ({placeholders})
        ORDER BY sr.source_revision_id
        """,
        revision_ids,
    ).fetchall()
    return [
        {
            "authority_level": row["authority_level"],
            "content_hash": row["content_hash"],
            "current_revision_id": row["current_revision_id"],
            "file_path": _relative_manifest_path(row["file_path"]),
            "revision_status": row["revision_status"],
            "source_id": row["source_id"],
            "source_revision_id": row["source_revision_id"],
            "source_subtype": row["source_subtype"],
            "source_type": row["source_type"],
        }
        for row in found
    ]


def _plan_header(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "counts": {
            "examined": int(row["examined_count"]),
            "excluded": int(row["excluded_count"]),
            "included": int(row["included_count"]),
            "selected_chars": int(row["selected_chars"]),
        },
        "created_at": row["created_at"],
        "config_hash": row["resolved_config_hash"],
        "selection_plan_hash": row["selection_plan_hash"],
        "policy": {
            "config_hash": row["policy_config_hash"],
            "policy_id": row["policy_id"],
            "policy_version": row["policy_version"],
        },
        "profile": {
            "config_hash": row["profile_config_hash"],
            "name": row["profile_name"],
        },
        "reason_summary": _json_object(row["reason_summary_json"], "reason_summary_json"),
        "relevant_state_hash": row["relevant_state_hash"],
        "report_path": row["report_path"],
        "reason_catalog_version": REASON_CATALOG_VERSION,
        "route": {
            "route_id": row["route_id"],
            "route_version": row["route_version"],
        },
        "run_id": row["run_id"],
        "selection_plan_id": row["selection_plan_id"],
        "status": row["status"],
    }


def _item_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "coverage_refs": _json_value(row["coverage_refs_json"], "coverage_refs_json"),
        "coverage_state": row["coverage_state"],
        "evidence_id": row["evidence_id"],
        "evidence_kind": row["evidence_kind"],
        "matched_criteria": _json_value(row["matched_criteria_json"], "matched_criteria_json"),
        "normalized_char_count": int(row["normalized_char_count"]),
        "outcome": row["outcome"],
        "package_char_count": int(row["package_char_count"]),
        "rank": row["selection_rank"],
        "reason_codes": _json_value(row["reason_codes_json"], "reason_codes_json"),
        "sequence": int(row["sequence"]),
        "sort_key": _json_value(row["sort_key_json"], "sort_key_json"),
        "source_revision_id": row["source_revision_id"],
    }


def _require_plan(connection: sqlite3.Connection, plan_id: str) -> sqlite3.Row:
    row = connection.execute(
        "SELECT * FROM ai_evidence_selection_plans WHERE selection_plan_id = ?",
        (plan_id,),
    ).fetchone()
    if row is None:
        raise AiSelectionError(
            f"Selection plan not found: {plan_id}.", reason="selection_plan_not_found"
        )
    return row


def _result_payload(result: SelectionPlanResult) -> dict[str, Any]:
    return {
        "counts": {
            "examined": result.examined_count,
            "excluded": result.excluded_count,
            "included": result.included_count,
            "selected_chars": result.selected_chars,
        },
        "config_hash": result.resolved_config_hash,
        "selection_plan_hash": result.plan_hash,
        "policy": {
            "config_hash": result.policy_config_hash,
            "policy_id": result.policy_name,
            "policy_version": result.policy_version,
        },
        "profile": result.profile_name,
        "reason_summary": result.reason_summary,
        "relevant_state_hash": result.relevant_state_hash,
        "report_path": result.report_path,
        "reason_catalog_version": REASON_CATALOG_VERSION,
        "route": {"route_id": result.route, "route_version": result.route_version},
        "run_id": result.run_id,
        "selection_plan_id": result.selection_plan_id,
    }


def _items_for_artifact(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        items,
        key=lambda item: (
            item["outcome"],
            item["rank"] if item["rank"] is not None else 2147483647,
            item["evidence_id"],
        ),
    )


def _applicable_rules(item: dict[str, Any]) -> list[str]:
    fragment_type = str(item.get("fragment_type") or "")
    return sorted(
        name
        for name, rule in ALL_DERIVATION_RULE_CATALOG.items()
        if fragment_type in rule.input_fragment_type.split("|")
    )


def _locator_complete(row: sqlite3.Row, metadata: dict[str, Any]) -> bool:
    if str(row["evidence_kind"]) == "chunk":
        start, end = metadata.get("start_char"), metadata.get("end_char")
        return _valid_bounds(start, end)
    if isinstance(row["path_or_selector"], str) and row["path_or_selector"].strip():
        if _valid_bounds(row["line_start"], row["line_end"]):
            return True
        if _valid_bounds(row["char_start"], row["char_end"]):
            return True
    locator = metadata.get("evidence_locator")
    return isinstance(locator, dict) and bool(locator)


def _valid_bounds(start: Any, end: Any) -> bool:
    return (
        isinstance(start, int)
        and not isinstance(start, bool)
        and isinstance(end, int)
        and not isinstance(end, bool)
        and start >= 0
        and end >= start
    )


def _validate_policy_budgets(policy: SelectionPolicy, project_caps: dict[str, Any]) -> None:
    for key, value in policy.budget.items():
        cap = project_caps[key]
        if value > cap:
            raise AiSelectionError(
                f"Policy budget.{key} exceeds project ai_selection.{key} ({cap}).",
                reason="selection_budget_project_limit",
            )


def _validate_policy_profile(policy: SelectionPolicy, package_options: Any) -> None:
    kinds = set(policy.criteria["evidence_kinds"] or ("chunk", "fragment"))
    if "chunk" in kinds and not package_options.include_chunks:
        raise AiSelectionError(
            "Selection policy can include chunks but the package profile disables chunks.",
            reason="selection_profile_conflict",
        )
    if "fragment" in kinds and not package_options.include_fragments:
        raise AiSelectionError(
            "Selection policy can include fragments but the package profile disables fragments.",
            reason="selection_profile_conflict",
        )


def _safe_name(value: str) -> bool:
    return bool(re.fullmatch(r"[a-z][a-z0-9_]*(?:\.[a-z0-9_]+)*", value or ""))


def _reject_unknown(mapping: dict[str, Any], allowed: set[str], label: str) -> None:
    unknown = sorted(set(mapping) - allowed)
    if unknown:
        raise AiSelectionError(
            f"Unsupported AI selection {label}: {unknown[0]}.",
            reason="invalid_selection_policy",
        )


def _required_text(mapping: dict[str, Any], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise AiSelectionError(
            f"policy.{key} must be a non-empty string.",
            reason="invalid_selection_policy",
        )
    return value.strip()


def _string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise AiSelectionError(
            f"{label} must be a list of non-empty strings.",
            reason="invalid_selection_policy",
        )
    return list(dict.fromkeys(item.strip() for item in value))


def _boolean(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise AiSelectionError(
            f"{label} must be boolean.", reason="invalid_selection_policy"
        )
    return value


def _ordered_reasons(reasons: Iterable[str]) -> list[str]:
    unique = set(reasons)
    return [reason for reason in REASON_ORDER if reason in unique]


def _json_object(value: str, label: str) -> dict[str, Any]:
    parsed = _json_value(value, label)
    if not isinstance(parsed, dict):
        raise AiSelectionError(f"{label} must contain a JSON object.")
    return parsed


def _evidence_metadata(value: Any) -> tuple[dict[str, Any], bool]:
    if value is None or value == "":
        return {}, True
    try:
        parsed = json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return {}, False
    if not isinstance(parsed, dict):
        return {}, False
    return parsed, True


def _json_value(value: str, label: str) -> Any:
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError) as exc:
        raise AiSelectionError(f"Invalid JSON in {label}.") from exc


def _relative_manifest_path(value: str) -> str:
    path = Path(str(value))
    if path.is_absolute() or "\\" in str(value) or ".." in path.parts:
        raise AiSelectionError(f"Source file path is not workspace-relative: {value}.")
    return path.as_posix()


def _normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")
