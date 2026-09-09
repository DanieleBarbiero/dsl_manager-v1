from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from dsl_mngr.core.batch import BatchResult, process_dir
from dsl_mngr.core.candidate_derivation import (
    ALL_DERIVATION_RULE_CATALOG,
    derive_candidates,
)
from dsl_mngr.core.candidate_review import CandidateReviewService
from dsl_mngr.core.canonical import (
    canonical_json_artifact_v1,
    canonical_sha256_v1,
)
from dsl_mngr.core.config import load_config
from dsl_mngr.core.database import (
    DatabaseSettings,
    open_database,
    resolve_database_settings,
)
from dsl_mngr.core.merge import merge_candidate_batches
from dsl_mngr.core.reconciliation import reconcile_required
from dsl_mngr.core.runs import (
    complete_run,
    fail_run,
    get_run_status,
    relative_workspace_path,
    run_artifact_paths,
    start_run,
    validate_database_migrations,
)
from dsl_mngr.core.temporal_consolidation import (
    consolidate_temporal_evidence,
    extract_temporal_evidence,
)


PHASES = ("parse", "derive", "review", "merge", "reconcile")
_PARSER_RULES = {
    "parse_ddl": ("ddl_table_fact/1", "ddl_column_fact/1", "ddl_fk_relation/1"),
    "parse_xml_form": ("xml_form_structure/1", "xml_table_usage/1"),
    "parse_db_code": ("db_code_unit/1", "db_code_dependency/1"),
    "parse_log": ("log_event_observation/1",),
    "normalize_excel": (
        "excel_workbook_fact/1",
        "excel_sheet_fact/1",
        "excel_region_fact/1",
        "excel_named_range_fact/1",
        "excel_table_fact/1",
        "excel_explicit_reference/1",
    ),
}

FaultHook = Callable[[str], None]


class BatchConsolidationError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        reason: str = "batch_consolidation_failed",
        exit_code: int = 2,
    ) -> None:
        super().__init__(message)
        self.reason = reason
        self.exit_code = exit_code


def consolidate_batch(
    workspace_dir: str | Path,
    *,
    corpus_path: str | Path = "corpus/active",
    strict_review: bool = False,
    reconcile: bool = False,
    stop_on_error: bool = False,
    resume_run_id: str | None = None,
    fault_hook: FaultHook | None = None,
) -> dict[str, Any]:
    """Run or resume the Slice 22 governed batch pipeline.

    Checkpoints are published after every phase.  A retry reuses completed
    derive batches and their candidate records, so it cannot add duplicate
    semantic support merely because the orchestrator was restarted.
    """

    settings = _require_ready(workspace_dir)
    config = load_config(settings.workspace_dir)
    automatic_policies = tuple(sorted(set(config["review"]["automatic_policies"])))
    rule_set_version = str(config["derive"]["rule_set_version"])
    options = {
        "automatic_policies": list(automatic_policies),
        "corpus_path": _relative_corpus_path(settings.workspace_dir, corpus_path),
        "reconcile": bool(reconcile),
        "rule_set_version": rule_set_version,
        "stop_on_error": bool(stop_on_error),
        "strict_review": bool(strict_review),
    }
    run_id, checkpoint, checkpoint_path = _prepare_run(
        settings,
        options=options,
        resume_run_id=resume_run_id,
    )
    options = dict(checkpoint["options"])
    report_path = run_artifact_paths(settings.workspace_dir, run_id).artifact_dir / "batch_report.json"

    try:
        if _phase_needs_run(checkpoint, "parse"):
            _begin_phase(checkpoint, checkpoint_path, "parse")
            parsed = process_dir(
                settings.workspace_dir,
                corpus_path=options["corpus_path"],
                stop_on_error=bool(options["stop_on_error"]),
                parent_run_id=run_id,
            )
            parse_payload = _parse_payload(parsed)
            _finish_phase(checkpoint, checkpoint_path, "parse", parse_payload)
        _fault(fault_hook, "after_parse")

        if checkpoint["phases"]["parse"]["status"] == "failed":
            _skip_remaining(checkpoint, checkpoint_path, after="parse", reason="parse_failed")
        else:
            if _phase_needs_run(checkpoint, "derive"):
                _begin_phase(checkpoint, checkpoint_path, "derive")
                derive_payload = _derive_phase(
                    settings,
                    run_id=run_id,
                    parse_payload=checkpoint["phases"]["parse"]["result"],
                    rule_set_version=str(options["rule_set_version"]),
                )
                _finish_phase(checkpoint, checkpoint_path, "derive", derive_payload)
            _fault(fault_hook, "after_derive")

            if _phase_needs_run(checkpoint, "review"):
                _begin_phase(checkpoint, checkpoint_path, "review")
                review_payload = _review_phase(
                    settings,
                    run_id=run_id,
                    derive_payload=checkpoint["phases"]["derive"]["result"],
                    automatic_policies=tuple(options["automatic_policies"]),
                )
                _finish_phase(checkpoint, checkpoint_path, "review", review_payload)
            _fault(fault_hook, "after_review")

            if _phase_needs_run(checkpoint, "merge"):
                _begin_phase(checkpoint, checkpoint_path, "merge")
                merge_payload = _merge_phase(
                    settings,
                    run_id=run_id,
                    derive_payload=checkpoint["phases"]["derive"]["result"],
                    strict_review=bool(options["strict_review"]),
                )
                _finish_phase(checkpoint, checkpoint_path, "merge", merge_payload)
            _fault(fault_hook, "after_merge")

            merge_status = checkpoint["phases"]["merge"]["status"]
            if bool(options["reconcile"]) and merge_status == "completed":
                if _phase_needs_run(checkpoint, "reconcile"):
                    _begin_phase(checkpoint, checkpoint_path, "reconcile")
                    reconcile_payload = _reconcile_phase(settings, run_id=run_id)
                    _finish_phase(
                        checkpoint,
                        checkpoint_path,
                        "reconcile",
                        reconcile_payload,
                    )
            elif checkpoint["phases"]["reconcile"]["status"] == "pending":
                reason = "not_configured" if not options["reconcile"] else "merge_not_completed"
                _skip_phase(checkpoint, checkpoint_path, "reconcile", reason=reason)
            _fault(fault_hook, "after_reconcile")
    except Exception as exc:
        _record_running_phase_failure(checkpoint, checkpoint_path, exc)
        payload = _result_payload(
            settings,
            checkpoint,
            run_id=run_id,
            checkpoint_path=checkpoint_path,
            report_path=report_path,
            forced_failure=exc,
        )
        _publish_report(report_path, payload)
        checkpoint["status"] = "failed"
        checkpoint["result"] = payload
        _write_checkpoint(checkpoint_path, checkpoint)
        _fail_parent(settings.workspace_dir, run_id, str(exc), payload)
        if isinstance(exc, BatchConsolidationError):
            raise
        raise BatchConsolidationError(str(exc)) from exc

    payload = _result_payload(
        settings,
        checkpoint,
        run_id=run_id,
        checkpoint_path=checkpoint_path,
        report_path=report_path,
    )
    _publish_report(report_path, payload)
    checkpoint["status"] = payload["status"]
    checkpoint["result"] = payload
    _write_checkpoint(checkpoint_path, checkpoint)
    _finish_parent(settings.workspace_dir, run_id, payload)
    return payload


def _prepare_run(
    settings: DatabaseSettings,
    *,
    options: dict[str, Any],
    resume_run_id: str | None,
) -> tuple[str, dict[str, Any], Path]:
    if resume_run_id is None:
        started = start_run(
            settings.workspace_dir,
            run_type="batch",
            input_payload={"batch_command": "consolidate", "options": options},
            cli_options={
                "review": {"automatic_policies": options["automatic_policies"]},
                "derive": {"rule_set_version": options["rule_set_version"]},
            },
        )
        checkpoint_path = started.artifacts.artifact_dir / "batch_checkpoint.json"
        checkpoint = {
            "batch_command": "consolidate",
            "catalog_version": "result_catalog_v1",
            "options": options,
            "phases": {
                phase: {
                    "attempts": 0,
                    "result": None,
                    "status": "pending",
                    "transitions": [],
                }
                for phase in PHASES
            },
            "retry_of": None,
            "run_id": started.record.run_id,
            "schema_version": "2",
            "status": "running",
        }
        _write_checkpoint(checkpoint_path, checkpoint)
        return started.record.run_id, checkpoint, checkpoint_path

    prior_record = get_run_status(settings.workspace_dir, resume_run_id)
    prior_path = run_artifact_paths(settings.workspace_dir, resume_run_id).artifact_dir / "batch_checkpoint.json"
    checkpoint = _load_checkpoint(prior_path)
    if checkpoint.get("batch_command") != "consolidate":
        raise BatchConsolidationError(
            f"Run {resume_run_id} is not a consolidated batch.",
            reason="batch_resume_invalid",
        )

    if prior_record.status == "running":
        return resume_run_id, checkpoint, prior_path

    retry_options = dict(checkpoint["options"])
    retry_options["automatic_policies"] = options["automatic_policies"]
    started = start_run(
        settings.workspace_dir,
        run_type="batch",
        parent_run_id=resume_run_id,
        input_payload={
            "batch_command": "consolidate",
            "options": retry_options,
            "retry_of": resume_run_id,
        },
        cli_options={
            "review": {"automatic_policies": retry_options["automatic_policies"]},
            "derive": {"rule_set_version": retry_options["rule_set_version"]},
        },
    )
    checkpoint = json.loads(json.dumps(checkpoint))
    checkpoint["run_id"] = started.record.run_id
    checkpoint["retry_of"] = resume_run_id
    checkpoint["options"] = retry_options
    checkpoint["status"] = "running"
    checkpoint["result"] = None
    _reset_retry_phases(checkpoint)
    checkpoint_path = started.artifacts.artifact_dir / "batch_checkpoint.json"
    _write_checkpoint(checkpoint_path, checkpoint)
    return started.record.run_id, checkpoint, checkpoint_path


def _reset_retry_phases(checkpoint: dict[str, Any]) -> None:
    statuses = {phase: checkpoint["phases"][phase]["status"] for phase in PHASES}
    if statuses["parse"] != "completed":
        start = 0
    elif statuses["derive"] != "completed":
        start = 1
    elif statuses["review"] != "completed":
        start = 2
    elif statuses["merge"] == "pending":
        start = 3
    elif statuses["merge"] != "completed":
        start = 2
    elif statuses["reconcile"] not in {"completed", "skipped"}:
        start = 4
    else:
        return
    for phase in PHASES[start:]:
        previous_status = checkpoint["phases"][phase]["status"]
        transitions = checkpoint["phases"][phase].get("transitions", [])
        if previous_status != "pending":
            transitions.append(
                {"from": previous_status, "reason": "retry", "to": "pending"}
            )
        checkpoint["phases"][phase] = {
            "attempts": checkpoint["phases"][phase].get("attempts", 0),
            "result": None,
            "status": "pending",
            "transitions": transitions,
        }


def _parse_payload(result: BatchResult) -> dict[str, Any]:
    structured: list[dict[str, str]] = []
    revision_ids: set[str] = set()
    for item in result.items:
        kind = str(item["kind"])
        if kind == "normalize" and item.get("outputs", {}).get("is_excel") is True:
            kind = "normalize_excel"
        if item["status"] == "completed" and item.get("source_revision_id"):
            revision_ids.add(str(item["source_revision_id"]))
        if (
            item["status"] == "completed"
            and kind in _PARSER_RULES
            and item.get("source_revision_id")
        ):
            structured.append(
                {
                    "kind": kind,
                    "source_revision_id": str(item["source_revision_id"]),
                }
            )
    return {
        "condition": "batch_parse",
        "counters": dict(result.summary),
        "exit_code": 2 if result.status == "failed" else 0,
        "items": list(result.items),
        "reason": "batch_parse_failed" if result.status == "failed" else "success",
        "report_path": result.report_path,
        "run_id": result.run_id,
        "status": result.status,
        "structured_sources": sorted(
            structured,
            key=lambda item: (item["source_revision_id"], item["kind"]),
        ),
        "source_revision_ids": sorted(revision_ids),
    }


def _derive_phase(
    settings: DatabaseSettings,
    *,
    run_id: str,
    parse_payload: Mapping[str, Any],
    rule_set_version: str,
) -> dict[str, Any]:
    work: set[tuple[str, str]] = set()
    for item in parse_payload.get("structured_sources", []):
        revision_id = str(item["source_revision_id"])
        for rule in _PARSER_RULES.get(str(item["kind"]), ()):
            work.add((revision_id, rule))

    items: list[dict[str, Any]] = []
    for revision_id, rule in sorted(work):
        started = start_run(
            settings.workspace_dir,
            run_type="candidate_derivation",
            parent_run_id=run_id,
            input_payload={
                "rule": rule,
                "rule_set_version": rule_set_version,
                "source_revision_id": revision_id,
            },
        )
        try:
            result = derive_candidates(
                settings.workspace_dir,
                run_id=started.record.run_id,
                source_revision_id=revision_id,
                rule=rule,
                rule_set_version=rule_set_version,
            )
            payload = result.to_payload()
            complete_run(settings.workspace_dir, started.record.run_id, output_payload=payload)
        except Exception as exc:
            _fail_parent(settings.workspace_dir, started.record.run_id, str(exc), {"error": str(exc)})
            raise
        items.append(
            {
                "batch_id": result.batch_id,
                "candidate_ids": list(result.candidate_ids),
                "candidates_path": result.candidates_path,
                "counters": payload["counters"],
                "payload_hashes": list(result.payload_hashes),
                "report_path": result.report_path,
                "rule": rule,
                "run_id": result.run_id,
                "semantic_report_hash": result.semantic_report_hash,
                "source_revision_id": revision_id,
                "status": "completed",
            }
        )

    temporal_items, temporal_extracted = _derive_temporal_candidates(
        settings,
        run_id=run_id,
        source_revision_ids=tuple(parse_payload.get("source_revision_ids", ())),
    )

    produced = sum(int(item["counters"]["produced"]) for item in items) + len(
        temporal_items
    )
    rejected = sum(int(item["counters"]["rejected"]) for item in items)
    return {
        "condition": "candidate_derivation",
        "counters": {
            "batches": len(items) + len(temporal_items),
            "deduplicated": sum(int(item["counters"]["deduplicated"]) for item in items),
            "input_fragments": sum(int(item["counters"]["input_fragments"]) for item in items),
            "produced": produced,
            "rejected": rejected,
            "zero_candidate_batches": sum(
                1 for item in items if int(item["counters"]["produced"]) == 0
            ),
            "temporal_candidates": len(temporal_items),
            "temporal_evidence_extracted": temporal_extracted,
        },
        "exit_code": 0,
        "items": items,
        "temporal_items": temporal_items,
        "reason": "success_with_rejections" if rejected else "success",
        "rule_set_version": rule_set_version,
        "status": "completed",
    }


def _derive_temporal_candidates(
    settings: DatabaseSettings,
    *,
    run_id: str,
    source_revision_ids: tuple[Any, ...],
) -> tuple[list[dict[str, Any]], int]:
    candidate_methods = {
        "declared_content_temporality",
        "html_declared_temporality",
        "ooxml_embedded_metadata",
        "pdf_embedded_metadata",
    }
    temporal_items: list[dict[str, Any]] = []
    extracted_count = 0
    for revision_id in sorted(set(str(value) for value in source_revision_ids)):
        evidence = extract_temporal_evidence(
            settings.workspace_dir,
            source_revision_id=revision_id,
        )
        extracted_count += len(evidence.evidence_ids)
        connection = open_database(settings.database_path, enable_wal=settings.wal_enabled)
        try:
            candidate_worthy = bool(
                connection.execute(
                    f"""
                    SELECT EXISTS(
                        SELECT 1 FROM raw_temporal_evidence
                        WHERE source_revision_id = ?
                          AND target_subject_type = 'source_revision'
                          AND target_subject_id = ?
                          AND extraction_method IN ({','.join('?' for _ in candidate_methods)})
                    )
                    """,
                    (revision_id, revision_id, *sorted(candidate_methods)),
                ).fetchone()[0]
            )
        finally:
            connection.close()
        if not candidate_worthy:
            continue
        consolidated = consolidate_temporal_evidence(
            settings.workspace_dir,
            run_id=run_id,
            target_subject_type="source_revision",
            target_subject_id=revision_id,
        )
        connection = open_database(settings.database_path, enable_wal=settings.wal_enabled)
        try:
            for candidate_id in consolidated.candidate_record_ids:
                row = connection.execute(
                    "SELECT batch_id FROM candidate_records WHERE candidate_record_id = ?",
                    (candidate_id,),
                ).fetchone()
                temporal_items.append(
                    {
                        "assessment": consolidated.assessment,
                        "batch_id": str(row["batch_id"]),
                        "candidate_ids": [candidate_id],
                        "counters": {"produced": 1, "rejected": 0},
                        "group_hash": consolidated.group_hash,
                        "rule": "temporal_consolidation/1",
                        "source_revision_id": revision_id,
                        "status": "completed",
                    }
                )
        finally:
            connection.close()
    return sorted(
        temporal_items,
        key=lambda item: (item["source_revision_id"], item["group_hash"], item["candidate_ids"]),
    ), extracted_count


def _review_phase(
    settings: DatabaseSettings,
    *,
    run_id: str,
    derive_payload: Mapping[str, Any],
    automatic_policies: tuple[str, ...],
) -> dict[str, Any]:
    batch_ids = _derived_batch_ids(derive_payload)
    started = start_run(
        settings.workspace_dir,
        run_type="candidate_review",
        parent_run_id=run_id,
        input_payload={
            "automatic_policies": list(automatic_policies),
            "batch_ids": list(batch_ids),
        },
    )
    service = CandidateReviewService(settings.workspace_dir)
    items: list[dict[str, Any]] = []
    try:
        for row in _candidate_rows(settings, batch_ids):
            candidate_record_id = str(row["candidate_record_id"])
            if row["decision_id"] is not None:
                items.append(
                    {
                        "action": "existing",
                        "candidate_record_id": candidate_record_id,
                        "decision_id": row["decision_id"],
                        "outcome": row["outcome"],
                        "reason": "existing_review_head",
                    }
                )
                continue

            payload = _json_object(row["payload_json"])
            rule_name = f"{payload.get('rule_id', '')}/{payload.get('rule_version', '')}"
            contract = ALL_DERIVATION_RULE_CATALOG.get(rule_name)
            configured_policy = contract.automatic_review_policy if contract else ""
            if (
                contract is not None
                and contract.automatic_review_allowed
                and configured_policy in automatic_policies
            ):
                policy_id, policy_version = configured_policy.rsplit("/", 1)
                decision = service.confirm(
                    candidate_record_id,
                    actor_id=f"policy:{policy_id}",
                    actor_type="automatic",
                    policy_id=policy_id,
                    policy_version=policy_version,
                    expected_head_decision_id=None,
                    run_id=started.record.run_id,
                )
                items.append(
                    {
                        "action": decision.action,
                        "candidate_record_id": candidate_record_id,
                        "decision_id": decision.decision_id,
                        "outcome": decision.outcome,
                        "policy": configured_policy,
                        "reason": decision.to_payload()["reason"],
                    }
                )
                continue

            expected_policy_id = configured_policy.rsplit("/", 1)[0] if "/" in configured_policy else ""
            version_mismatch = any(
                policy.rsplit("/", 1)[0] == expected_policy_id
                for policy in automatic_policies
                if "/" in policy and expected_policy_id
            )
            items.append(
                {
                    "action": "skipped",
                    "candidate_record_id": candidate_record_id,
                    "decision_id": None,
                    "outcome": "pending",
                    "reason": (
                        "automatic_review_not_allowed"
                        if contract is not None and not contract.automatic_review_allowed
                        else "automatic_policy_version_mismatch"
                        if version_mismatch
                        else "automatic_policy_not_enabled"
                    ),
                }
            )

        final_rows = _candidate_rows(settings, batch_ids)
        counters = _review_counters(final_rows, items)
        payload = {
            "artifact_paths": [],
            "automatic_policies": list(automatic_policies),
            "batch_ids": list(batch_ids),
            "catalog_version": "result_catalog_v1",
            "condition": "automatic_review",
            "counters": counters,
            "exit_code": 0,
            "items": sorted(items, key=lambda item: item["candidate_record_id"]),
            "mutations": counters["auto_confirmed"] > 0,
            "outcome": None,
            "reason": "success",
            "retryable": False,
            "run_id": started.record.run_id,
            "schema_version": "1",
            "severity": "info",
            "status": "completed",
            "subject_ids": sorted(str(row["candidate_record_id"]) for row in final_rows),
        }
        report_path = started.artifacts.artifact_dir / "review_report.json"
        payload["artifact_paths"] = [
            relative_workspace_path(settings.workspace_dir, report_path)
        ]
        _publish_report(report_path, payload)
        complete_run(settings.workspace_dir, started.record.run_id, output_payload=payload)
        return payload
    except Exception as exc:
        _fail_parent(settings.workspace_dir, started.record.run_id, str(exc), {"error": str(exc)})
        raise


def _merge_phase(
    settings: DatabaseSettings,
    *,
    run_id: str,
    derive_payload: Mapping[str, Any],
    strict_review: bool,
) -> dict[str, Any]:
    batch_ids = _derived_batch_ids(derive_payload)
    started = start_run(
        settings.workspace_dir,
        run_type="merge",
        parent_run_id=run_id,
        input_payload={"batch_ids": list(batch_ids), "strict_review": strict_review},
    )
    try:
        result = merge_candidate_batches(
            settings.workspace_dir,
            run_id=started.record.run_id,
            batch_ids=batch_ids,
            strict_review=strict_review,
        )
        payload = result.to_artifact_payload()
        report_path = started.artifacts.artifact_dir / "merge_report.json"
        payload["artifact_paths"] = [
            relative_workspace_path(settings.workspace_dir, report_path)
        ]
        _publish_report(report_path, payload)
        if result.exit_code == 0:
            complete_run(settings.workspace_dir, started.record.run_id, output_payload=payload)
        else:
            fail_run(
                settings.workspace_dir,
                started.record.run_id,
                error=result.reason,
                output_payload=payload,
            )
        return payload
    except Exception as exc:
        _fail_parent(settings.workspace_dir, started.record.run_id, str(exc), {"error": str(exc)})
        raise


def _reconcile_phase(settings: DatabaseSettings, *, run_id: str) -> dict[str, Any]:
    started = start_run(
        settings.workspace_dir,
        run_type="reconciliation",
        parent_run_id=run_id,
        input_payload={"reconciliation_id": None, "strict": False},
    )
    try:
        result = reconcile_required(
            settings.workspace_dir,
            run_id=started.record.run_id,
            strict=False,
        )
        payload = result.to_payload()
        report_path = started.artifacts.artifact_dir / "reconcile_report.json"
        payload["artifact_paths"] = [
            relative_workspace_path(settings.workspace_dir, report_path)
        ]
        _publish_report(report_path, payload)
        complete_run(settings.workspace_dir, started.record.run_id, output_payload=payload)
        return payload
    except Exception as exc:
        _fail_parent(settings.workspace_dir, started.record.run_id, str(exc), {"error": str(exc)})
        raise


def effective_registry_hashes(workspace_dir: str | Path) -> dict[str, Any]:
    """Return stable hashes of effective facts, relations, and their governed support."""

    settings = _require_ready(workspace_dir)
    connection = open_database(settings.database_path, enable_wal=settings.wal_enabled)
    try:
        facts = [dict(row) for row in connection.execute(
            """
            SELECT fact_identity_hash, fact_type, canonical_entity_name,
                   property_name, normalized_property_value, assertion_type,
                   confidence, status
            FROM effective_facts
            ORDER BY fact_identity_hash
            """
        ).fetchall()]
        relations = [dict(row) for row in connection.execute(
            """
            SELECT relation_identity_hash, canonical_source_entity, relation_type,
                   canonical_target_entity, assertion_type, confidence, status
            FROM effective_relations
            ORDER BY relation_identity_hash
            """
        ).fetchall()]
        fact_supports = _effective_supports(connection, kind="fact")
        relation_supports = _effective_supports(connection, kind="relation")
    finally:
        connection.close()
    fact_payload = {"objects": facts, "supports": fact_supports}
    relation_payload = {"objects": relations, "supports": relation_supports}
    return {
        "effective_fact_count": len(facts),
        "effective_fact_hash": canonical_sha256_v1(fact_payload),
        "effective_fact_support_count": len(fact_supports),
        "effective_registry_hash": canonical_sha256_v1(
            {"facts": fact_payload, "relations": relation_payload}
        ),
        "effective_relation_count": len(relations),
        "effective_relation_hash": canonical_sha256_v1(relation_payload),
        "effective_relation_support_count": len(relation_supports),
    }


def _effective_supports(connection: sqlite3.Connection, *, kind: str) -> list[dict[str, Any]]:
    if kind == "fact":
        view = "effective_fact_evidence"
        owner_table = "facts"
        owner_column = "fact_id"
        identity_column = "fact_identity_hash"
    else:
        view = "effective_relation_evidence"
        owner_table = "relations"
        owner_column = "relation_id"
        identity_column = "relation_identity_hash"
    rows = connection.execute(
        f"""
        SELECT owner.{identity_column} AS owner_identity_hash,
               sr.content_hash AS source_content_hash,
               evidence.evidence_text_hash,
               evidence.review_policy_id, evidence.review_policy_version,
               candidate.payload_json
        FROM {view} evidence
        JOIN {owner_table} owner ON owner.{owner_column} = evidence.{owner_column}
        JOIN source_revisions sr
          ON sr.source_revision_id = evidence.source_revision_id
        JOIN candidate_records candidate
          ON candidate.candidate_record_id = evidence.candidate_record_id
        ORDER BY owner.{identity_column}, sr.content_hash,
                 evidence.evidence_text_hash, candidate.payload_json,
                 evidence.review_policy_id, evidence.review_policy_version
        """
    ).fetchall()
    return [
        {
            "candidate_payload_hash": canonical_sha256_v1(_json_object(row["payload_json"])),
            "evidence_text_hash": row["evidence_text_hash"],
            "owner_identity_hash": row["owner_identity_hash"],
            "review_policy_id": row["review_policy_id"],
            "review_policy_version": row["review_policy_version"],
            "source_content_hash": row["source_content_hash"],
        }
        for row in rows
    ]


def _result_payload(
    settings: DatabaseSettings,
    checkpoint: Mapping[str, Any],
    *,
    run_id: str,
    checkpoint_path: Path,
    report_path: Path,
    forced_failure: Exception | None = None,
) -> dict[str, Any]:
    phases = checkpoint["phases"]
    merge = phases["merge"].get("result") or {}
    reconciliation = phases["reconcile"].get("result") or {}
    parse = phases["parse"].get("result") or {}
    derive = phases["derive"].get("result") or {}
    review = phases["review"].get("result") or {}

    if forced_failure is not None or phases["parse"]["status"] == "failed":
        status, reason, exit_code, severity, retryable = (
            "failed",
            getattr(forced_failure, "reason", None) or parse.get("reason", "batch_phase_failed"),
            int(getattr(forced_failure, "exit_code", 2)),
            "error",
            True,
        )
    elif phases["merge"]["status"] in {"blocked", "failed"}:
        status = str(merge.get("status", phases["merge"]["status"]))
        reason = str(merge.get("reason", "no_merge_eligible_candidates"))
        exit_code = int(merge.get("exit_code", 4))
        severity, retryable = "warning", True
    elif phases["reconcile"]["status"] == "pending":
        status, reason, exit_code, severity, retryable = (
            "pending",
            str(reconciliation.get("reason", "replacement_merge_pending")),
            int(reconciliation.get("exit_code", 4)),
            "warning",
            True,
        )
    else:
        status, exit_code, severity, retryable = "completed", 0, "info", False
        reason = str(merge.get("reason", "success"))

    counters = _aggregate_counters(parse, derive, review, merge, reconciliation)
    effective_hashes = effective_registry_hashes(settings.workspace_dir)
    semantic_report_hash = canonical_sha256_v1(
        {
            "counters": counters,
            "effective_hashes": effective_hashes,
            "options": checkpoint["options"],
            "reason": reason,
            "status": status,
        }
    )
    subject_ids = sorted(
        str(item["candidate_record_id"])
        for item in review.get("items", [])
        if item.get("candidate_record_id")
    )
    return {
        "artifact_paths": [
            relative_workspace_path(settings.workspace_dir, checkpoint_path),
            relative_workspace_path(settings.workspace_dir, report_path),
        ],
        "batch_command": "consolidate",
        "catalog_version": "result_catalog_v1",
        "condition": "batch_consolidation",
        "counters": counters,
        "effective_hashes": effective_hashes,
        "exit_code": exit_code,
        "mutations": bool(merge.get("mutations") or reconciliation.get("mutations")),
        "options": checkpoint["options"],
        "outcome": None,
        "phases": [
            {
                "attempts": int(phases[name]["attempts"]),
                "name": name,
                "result": phases[name]["result"],
                "status": phases[name]["status"],
                "transitions": phases[name]["transitions"],
            }
            for name in PHASES
        ],
        "reason": reason,
        "retry_of": checkpoint.get("retry_of"),
        "retryable": retryable,
        "run_id": run_id,
        "schema_version": "2",
        "semantic_report_hash": semantic_report_hash,
        "severity": severity,
        "status": status,
        "subject_ids": subject_ids,
    }


def _aggregate_counters(
    parse: Mapping[str, Any],
    derive: Mapping[str, Any],
    review: Mapping[str, Any],
    merge: Mapping[str, Any],
    reconciliation: Mapping[str, Any],
) -> dict[str, int]:
    parse_counters = parse.get("counters", {})
    derive_counters = derive.get("counters", {})
    review_counters = review.get("counters", {})
    merge_counters = merge.get("counters", {})
    reconcile_counters = reconciliation.get("counters", {})
    return {
        "auto_confirmed": int(review_counters.get("auto_confirmed", 0)),
        "auto_replayed": int(review_counters.get("auto_replayed", 0)),
        "candidate_batches": int(derive_counters.get("batches", 0)),
        "candidates_produced": int(derive_counters.get("produced", 0)),
        "candidates_rejected": int(derive_counters.get("rejected", 0)),
        "facts_created": int(merge_counters.get("facts_created", 0)),
        "facts_existing": int(merge_counters.get("facts_existing", 0)),
        "merged_candidates": int(merge_counters.get("merged_candidates", 0)),
        "parse_completed": int(parse_counters.get("completed", 0)),
        "parse_failed": int(parse_counters.get("failed", 0)),
        "parse_skipped": int(parse_counters.get("skipped", 0)),
        "policy_skipped_absent": int(review_counters.get("policy_skipped_absent", 0)),
        "policy_skipped_version": int(review_counters.get("policy_skipped_version", 0)),
        "reconciliation_closed": int(reconcile_counters.get("closed", 0)),
        "reconciliation_pending": int(reconcile_counters.get("pending", 0)),
        "relations_created": int(merge_counters.get("relations_created", 0)),
        "relations_existing": int(merge_counters.get("relations_existing", 0)),
        "review_confirmed": int(review_counters.get("confirmed", 0)),
        "review_non_leaf": int(review_counters.get("non_leaf", 0)),
        "review_pending": int(review_counters.get("pending", 0)),
        "review_rejected": int(review_counters.get("rejected", 0)),
        "review_superseded": int(review_counters.get("superseded", 0)),
        "skipped_no_positive_head": int(merge_counters.get("skipped_no_positive_head", 0)),
        "skipped_non_leaf": int(merge_counters.get("skipped_non_leaf", 0)),
        "skipped_pending": int(merge_counters.get("skipped_pending", 0)),
        "skipped_records": int(merge_counters.get("skipped_records", 0)),
        "skipped_rejected": int(merge_counters.get("skipped_rejected", 0)),
        "skipped_superseded": int(merge_counters.get("skipped_superseded", 0)),
        "temporal_candidates": int(derive_counters.get("temporal_candidates", 0)),
        "temporal_evidence_extracted": int(
            derive_counters.get("temporal_evidence_extracted", 0)
        ),
        "zero_candidate_batches": int(derive_counters.get("zero_candidate_batches", 0)),
    }


def _candidate_rows(settings: DatabaseSettings, batch_ids: tuple[str, ...]) -> list[sqlite3.Row]:
    if not batch_ids:
        return []
    placeholders = ",".join("?" for _ in batch_ids)
    connection = open_database(settings.database_path, enable_wal=settings.wal_enabled)
    try:
        return connection.execute(
            f"""
            SELECT cr.candidate_record_id, cr.batch_id, cr.payload_json,
                   rd.decision_id, rd.outcome,
                   EXISTS (
                       SELECT 1 FROM candidate_lineage child
                       WHERE child.parent_candidate_record_id = cr.candidate_record_id
                   ) AS is_non_leaf
            FROM candidate_records cr
            LEFT JOIN review_subject_heads head
              ON head.subject_type = 'candidate_record'
             AND head.subject_id = cr.candidate_record_id
            LEFT JOIN review_decisions rd ON rd.decision_id = head.decision_id
            WHERE cr.batch_id IN ({placeholders})
            ORDER BY cr.batch_id, cr.line_number, cr.candidate_record_id
            """,
            batch_ids,
        ).fetchall()
    finally:
        connection.close()


def _review_counters(rows: list[sqlite3.Row], items: list[dict[str, Any]]) -> dict[str, int]:
    counters = {
        "auto_confirmed": sum(1 for item in items if item["action"] == "created"),
        "auto_replayed": sum(1 for item in items if item["action"] == "replayed"),
        "confirmed": 0,
        "non_leaf": 0,
        "pending": 0,
        "policy_skipped_absent": sum(
            1 for item in items if item["reason"] == "automatic_policy_not_enabled"
        ),
        "policy_skipped_version": sum(
            1 for item in items if item["reason"] == "automatic_policy_version_mismatch"
        ),
        "rejected": 0,
        "superseded": 0,
        "total": len(rows),
    }
    for row in rows:
        if bool(row["is_non_leaf"]):
            counters["non_leaf"] += 1
        outcome = row["outcome"]
        if outcome in {"confirmed", "rejected", "superseded"}:
            counters[str(outcome)] += 1
        else:
            counters["pending"] += 1
    return counters


def _derived_batch_ids(payload: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(
        sorted(
            str(item["batch_id"])
            for item in (*payload.get("items", []), *payload.get("temporal_items", []))
        )
    )


def _begin_phase(checkpoint: dict[str, Any], path: Path, phase: str) -> None:
    entry = checkpoint["phases"][phase]
    previous = entry["status"]
    entry["attempts"] = int(entry.get("attempts", 0)) + 1
    entry["status"] = "running"
    entry["transitions"].append({"from": previous, "to": "running"})
    _write_checkpoint(path, checkpoint)


def _finish_phase(
    checkpoint: dict[str, Any],
    path: Path,
    phase: str,
    result: dict[str, Any],
) -> None:
    entry = checkpoint["phases"][phase]
    previous = entry["status"]
    status = str(result.get("status", "completed"))
    if status not in {"completed", "blocked", "failed", "pending"}:
        status = "completed"
    entry["result"] = result
    entry["status"] = status
    entry["transitions"].append({"from": previous, "to": status})
    _write_checkpoint(path, checkpoint)


def _skip_phase(checkpoint: dict[str, Any], path: Path, phase: str, *, reason: str) -> None:
    entry = checkpoint["phases"][phase]
    previous = entry["status"]
    entry["status"] = "skipped"
    entry["result"] = {"reason": reason, "status": "skipped"}
    entry["transitions"].append({"from": previous, "to": "skipped"})
    _write_checkpoint(path, checkpoint)


def _skip_remaining(
    checkpoint: dict[str, Any], path: Path, *, after: str, reason: str
) -> None:
    start = PHASES.index(after) + 1
    for phase in PHASES[start:]:
        if checkpoint["phases"][phase]["status"] == "pending":
            _skip_phase(checkpoint, path, phase, reason=reason)


def _phase_needs_run(checkpoint: Mapping[str, Any], phase: str) -> bool:
    return checkpoint["phases"][phase]["status"] not in {"completed", "skipped"}


def _record_running_phase_failure(
    checkpoint: dict[str, Any], path: Path, exc: Exception
) -> None:
    for phase in PHASES:
        entry = checkpoint["phases"][phase]
        if entry["status"] == "running":
            entry["result"] = {
                "error": str(exc),
                "exit_code": int(getattr(exc, "exit_code", 2)),
                "reason": str(getattr(exc, "reason", "batch_phase_failed")),
                "status": "failed",
            }
            entry["status"] = "failed"
            entry["transitions"].append({"from": "running", "to": "failed"})
            _skip_remaining(checkpoint, path, after=phase, reason="previous_phase_failed")
            break
    _write_checkpoint(path, checkpoint)


def _write_checkpoint(path: Path, payload: Mapping[str, Any]) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(canonical_json_artifact_v1(payload), encoding="utf-8", newline="\n")
    temporary.replace(path)


def _load_checkpoint(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise BatchConsolidationError(
            f"Consolidated batch checkpoint not found: {path.name}.",
            reason="batch_checkpoint_missing",
        )
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("phases"), dict):
        raise BatchConsolidationError(
            "Consolidated batch checkpoint is invalid.",
            reason="batch_checkpoint_invalid",
        )
    return payload


def _publish_report(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(canonical_json_artifact_v1(payload), encoding="utf-8", newline="\n")


def _finish_parent(workspace: Path, run_id: str, payload: dict[str, Any]) -> None:
    record = get_run_status(workspace, run_id)
    if record.status != "running":
        return
    if int(payload["exit_code"]) == 0:
        complete_run(workspace, run_id, output_payload=payload)
    else:
        fail_run(workspace, run_id, error=str(payload["reason"]), output_payload=payload)


def _fail_parent(workspace: Path, run_id: str, error: str, payload: dict[str, Any]) -> None:
    try:
        record = get_run_status(workspace, run_id)
        if record.status == "running":
            fail_run(workspace, run_id, error=error, output_payload=payload)
    except Exception:
        return


def _require_ready(workspace_dir: str | Path) -> DatabaseSettings:
    settings = resolve_database_settings(workspace_dir)
    if not settings.database_path.is_file():
        raise BatchConsolidationError(
            f"Database is not initialized: {settings.database_path}.",
            reason="database_not_initialized",
        )
    connection = open_database(settings.database_path, enable_wal=settings.wal_enabled)
    try:
        validate_database_migrations(connection)
    finally:
        connection.close()
    return settings


def _relative_corpus_path(workspace: Path, corpus_path: str | Path) -> str:
    path = Path(corpus_path)
    resolved = path.resolve() if path.is_absolute() else (workspace / path).resolve()
    try:
        return relative_workspace_path(workspace, resolved)
    except ValueError as exc:
        raise BatchConsolidationError(
            f"Corpus path escapes the workspace: {corpus_path}.",
            reason="batch_input_invalid",
        ) from exc


def _json_object(raw: Any) -> dict[str, Any]:
    try:
        payload = json.loads(str(raw))
    except json.JSONDecodeError as exc:
        raise BatchConsolidationError(
            "Candidate payload is invalid JSON.", reason="candidate_payload_invalid"
        ) from exc
    if not isinstance(payload, dict):
        raise BatchConsolidationError(
            "Candidate payload is not an object.", reason="candidate_payload_invalid"
        )
    return payload


def _fault(hook: FaultHook | None, point: str) -> None:
    if hook is not None:
        hook(point)


__all__ = [
    "BatchConsolidationError",
    "PHASES",
    "consolidate_batch",
    "effective_registry_hashes",
]
