from __future__ import annotations

import json
import sys
from pathlib import Path

from dsl_mngr.core.batch import BatchError, batch_cli_lines, candidates_validate_batch
from dsl_mngr.core.candidate_import import (
    CandidateImportError,
    ensure_candidate_database_ready,
    import_candidate_file,
    prepare_candidate_input_file,
    write_candidate_process_report,
)
from dsl_mngr.core.candidate_derivation import (
    CandidateDerivationError,
    derive_candidates,
)
from dsl_mngr.core.candidate_review import (
    CandidateReviewError,
    CandidateReviewService,
    write_review_report,
)
from dsl_mngr.core.canonical import canonical_json_artifact_v1
from dsl_mngr.core.config import load_config
from dsl_mngr.core.database import (
    DatabaseConfigurationError,
    WorkspaceNotInitializedError,
    resolve_workspace_path,
)
from dsl_mngr.core.logging_setup import log_event
from dsl_mngr.core.runs import (
    DatabaseNotReadyError,
    RunLifecycleError,
    complete_run,
    fail_run,
    start_run,
)


def run_candidates_validate_command(args: object) -> int:
    workspace = Path(getattr(args, "workspace"))
    input_path = Path(getattr(args, "input_path"))

    try:
        result = validate_candidate_file(workspace, input_path=input_path)
    except (
        CandidateImportError,
        DatabaseConfigurationError,
        DatabaseNotReadyError,
        RunLifecycleError,
        WorkspaceNotInitializedError,
    ) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print(f"Run: {result.run_id}")
    print(f"Batch: {result.batch_id}")
    print(f"Total: {result.total_records}")
    print(f"Accepted: {result.accepted_count}")
    print(f"Rejected: {result.rejected_count}")
    return 0


def run_candidates_validate_batch_command(args: object) -> int:
    workspace = Path(getattr(args, "workspace"))
    input_dir = getattr(args, "input_dir", "ai/inbox")
    pattern = getattr(args, "pattern", "*.jsonl")
    stop_on_error = bool(getattr(args, "stop_on_error", False))

    try:
        result = candidates_validate_batch(
            workspace,
            input_dir=input_dir,
            pattern=pattern,
            stop_on_error=stop_on_error,
        )
    except (
        BatchError,
        CandidateImportError,
        DatabaseConfigurationError,
        DatabaseNotReadyError,
        RunLifecycleError,
        WorkspaceNotInitializedError,
    ) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print("\n".join(batch_cli_lines(result)))
    return 2 if result.summary["failed"] else 0


def run_candidates_review_list_command(args: object) -> int:
    workspace = Path(getattr(args, "workspace"))
    outcome = str(getattr(args, "outcome", "pending"))
    try:
        rows = CandidateReviewService(workspace).list_candidates(outcome=outcome)
    except (CandidateReviewError, DatabaseNotReadyError, WorkspaceNotInitializedError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return int(getattr(exc, "exit_code", 2))
    payload = {
        "artifact_paths": [],
        "candidates": rows,
        "catalog_version": "result_catalog_v1",
        "condition": "review_list",
        "count": len(rows),
        "counters": {"candidates": len(rows)},
        "exit_code": 0,
        "mutations": False,
        "outcome": outcome,
        "reason": "success",
        "retryable": False,
        "run_id": None,
        "schema_version": "1",
        "severity": "info",
        "status": "completed",
        "subject_ids": [row["candidate_record_id"] for row in rows],
    }
    print(canonical_json_artifact_v1(payload), end="")
    return 0


def run_candidates_review_show_command(args: object) -> int:
    workspace = Path(getattr(args, "workspace"))
    candidate_record_id = str(getattr(args, "candidate_record_id"))
    try:
        detail = CandidateReviewService(workspace).show_candidate(candidate_record_id)
    except (CandidateReviewError, DatabaseNotReadyError, WorkspaceNotInitializedError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return int(getattr(exc, "exit_code", 2))
    payload = {
        **detail,
        "artifact_paths": [],
        "catalog_version": "result_catalog_v1",
        "condition": "review_show",
        "counters": {
            "decisions": len(detail["decisions"]),
            "supports": sum(int(value) for value in detail["support"].values()),
        },
        "exit_code": 0,
        "mutations": False,
        "outcome": (
            detail["decisions"][-1]["outcome"] if detail["decisions"] else "pending"
        ),
        "reason": "success",
        "retryable": False,
        "run_id": None,
        "schema_version": "1",
        "severity": "info",
        "status": "completed",
        "subject_ids": [candidate_record_id],
    }
    print(canonical_json_artifact_v1(payload), end="")
    return 0


def run_candidates_review_confirm_command(args: object) -> int:
    return _run_review_mutation(args, operation="confirm")


def run_candidates_review_reject_command(args: object) -> int:
    return _run_review_mutation(args, operation="reject")


def run_candidates_review_correct_command(args: object) -> int:
    return _run_review_mutation(args, operation="correct")


def run_candidates_derive_command(args: object) -> int:
    workspace = Path(getattr(args, "workspace"))
    source_revision_id = getattr(args, "source_revision_id", None)
    rule = str(getattr(args, "rule", "ddl_table_fact/1"))
    try:
        ensure_candidate_database_ready(workspace)
        config = load_config(workspace)
        rule_set_version = str(config.get("derive", {}).get("rule_set_version", "1"))
        started = start_run(
            workspace,
            run_type="candidate_derivation",
            input_payload={
                "rule": rule,
                "rule_set_version": rule_set_version,
                "source_revision_id": source_revision_id,
            },
        )
        result = derive_candidates(
            workspace,
            run_id=started.record.run_id,
            source_revision_id=source_revision_id,
            rule=rule,
            rule_set_version=rule_set_version,
        )
        payload = result.to_payload()
        complete_run(workspace, started.record.run_id, output_payload=payload)
    except (
        CandidateDerivationError,
        CandidateImportError,
        DatabaseConfigurationError,
        DatabaseNotReadyError,
        RunLifecycleError,
        WorkspaceNotInitializedError,
    ) as exc:
        if "started" in locals():
            _mark_started_run_failed(workspace, started.record.run_id, str(exc))
        print(f"Error: {exc}", file=sys.stderr)
        return int(getattr(exc, "exit_code", 2))
    print(canonical_json_artifact_v1(payload), end="")
    return 0


def _run_review_mutation(args: object, *, operation: str) -> int:
    workspace = Path(getattr(args, "workspace"))
    candidate_record_id = str(getattr(args, "candidate_record_id"))
    try:
        actor_id = _review_actor_id(workspace, getattr(args, "actor_id", None))
        reason = getattr(args, "reason", None)
        expected_head = getattr(args, "expected_head_decision_id", None)
        idempotency_key = getattr(args, "idempotency_key", None)
        evidence_refs = tuple(getattr(args, "evidence_ref", None) or ())
        corrected_payload = None
        if operation == "correct":
            corrected_payload = _load_corrected_payload(
                workspace, str(getattr(args, "payload"))
            )
        started = start_run(
            workspace,
            run_type=("candidate_correction" if operation == "correct" else "candidate_review"),
            input_payload={
                "candidate_record_id": candidate_record_id,
                "operation": operation,
            },
        )
        service = CandidateReviewService(workspace)
        if operation == "confirm":
            result = service.confirm(
                candidate_record_id,
                actor_id=actor_id,
                reason=reason,
                expected_head_decision_id=expected_head,
                idempotency_key=idempotency_key,
                run_id=started.record.run_id,
            )
        elif operation == "reject":
            result = service.reject(
                candidate_record_id,
                actor_id=actor_id,
                reason=reason,
                expected_head_decision_id=expected_head,
                idempotency_key=idempotency_key,
                run_id=started.record.run_id,
            )
        else:
            result = service.correct(
                candidate_record_id,
                corrected_payload=corrected_payload or {},
                actor_id=actor_id,
                reason=reason,
                expected_head_decision_id=expected_head,
                idempotency_key=idempotency_key,
                evidence_refs=evidence_refs,
                run_id=started.record.run_id,
            )
        payload = result.to_payload(run_id=started.record.run_id)
        report_path = started.artifacts.artifact_dir / "review_report.json"
        payload["artifact_paths"] = [
            report_path.relative_to(started.artifacts.workspace_dir).as_posix()
        ]
        write_review_report(report_path, payload)
        complete_run(workspace, started.record.run_id, output_payload=payload)
    except (
        CandidateReviewError,
        DatabaseConfigurationError,
        DatabaseNotReadyError,
        json.JSONDecodeError,
        RunLifecycleError,
        WorkspaceNotInitializedError,
    ) as exc:
        if "started" in locals():
            _mark_started_run_failed(workspace, started.record.run_id, str(exc))
        print(f"Error: {exc}", file=sys.stderr)
        return int(getattr(exc, "exit_code", 2))
    print(canonical_json_artifact_v1(payload), end="")
    return 0


def _review_actor_id(workspace: Path, supplied: str | None) -> str:
    actor_id = str(supplied or "").strip()
    if not actor_id:
        actor_id = str(load_config(workspace).get("review", {}).get("default_actor_id", "")).strip()
    if not actor_id:
        raise CandidateReviewError(
            "review_actor_required: use --actor-id or review.default_actor_id.",
            reason="review_actor_required",
        )
    return actor_id


def _load_corrected_payload(workspace: Path, value: str) -> dict[str, object]:
    raw = value.strip()
    if raw.startswith("{"):
        payload = json.loads(raw)
    else:
        path = resolve_workspace_path(workspace, raw)
        if not path.is_file():
            raise CandidateReviewError(
                f"Correction payload file not found: {raw}.",
                reason="correction_payload_not_found",
            )
        payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise CandidateReviewError(
            "Correction payload must be a JSON object.",
            reason="candidate_schema_invalid",
            exit_code=3,
        )
    return payload


def validate_candidate_file(
    workspace_dir: str | Path,
    *,
    input_path: str | Path,
    parent_run_id: str | None = None,
):
    workspace = Path(workspace_dir)
    ensure_candidate_database_ready(workspace)
    input_file = prepare_candidate_input_file(workspace, input_path)
    started = start_run(
        workspace,
        run_type="candidate_validation",
        parent_run_id=parent_run_id,
        input_payload={"input_path": input_file.relative_path},
    )

    try:
        result = import_candidate_file(
            workspace,
            run_id=started.record.run_id,
            input_path=input_file.path,
        )
        complete_run(
            workspace,
            started.record.run_id,
            output_payload=result.to_output_payload(),
        )
        write_candidate_process_report(workspace, result)
    except (CandidateImportError, DatabaseConfigurationError, RunLifecycleError) as exc:
        _mark_started_run_failed(workspace, started.record.run_id, str(exc))
        raise

    log_event(
        _resolve_app_log_path(started.artifacts.workspace_dir),
        level="INFO",
        event="candidate_validation_completed",
        message=(
            f"Candidate validation completed; batch={result.batch_id}; "
            f"total={result.total_records}; accepted={result.accepted_count}; "
            f"rejected={result.rejected_count}"
        ),
        run_id=result.run_id,
    )
    return result


def _mark_started_run_failed(workspace: Path, run_id: str, error: str) -> None:
    try:
        fail_run(
            workspace,
            run_id,
            error=error,
            output_payload={"error": error},
        )
    except (DatabaseConfigurationError, DatabaseNotReadyError, RunLifecycleError, WorkspaceNotInitializedError):
        return


def _resolve_app_log_path(workspace_dir: Path) -> Path:
    config = load_config(workspace_dir)
    logging_config = config.get("logging", {})
    configured_path = logging_config.get("app_log_path", "logs/app.jsonl")
    return resolve_workspace_path(workspace_dir, configured_path)
