from __future__ import annotations

import sys
from pathlib import Path

from dsl_mngr.core.canonical import canonical_json_artifact_v1
from dsl_mngr.core.batch import BatchError, batch_cli_lines, facts_merge_batch
from dsl_mngr.core.config import load_config
from dsl_mngr.core.database import (
    DatabaseConfigurationError,
    WorkspaceNotInitializedError,
    resolve_workspace_path,
)
from dsl_mngr.core.logging_setup import log_event
from dsl_mngr.core.merge import (
    MergeDatabaseNotReadyError,
    MergeError,
    MergeResult,
    load_merge_batch_info,
    merge_candidate_batch,
    write_merge_artifacts,
)
from dsl_mngr.core.reconciliation import ReconciliationError, reconcile_required
from dsl_mngr.core.runs import (
    DatabaseNotReadyError,
    RunLifecycleError,
    complete_run,
    fail_run,
    start_run,
)


def run_facts_merge_command(args: object) -> int:
    workspace = Path(getattr(args, "workspace"))
    batch_id = str(getattr(args, "batch_id"))
    strict_review = bool(getattr(args, "strict_review", False))

    try:
        result = merge_facts_candidate_batch(
            workspace, batch_id=batch_id, strict_review=strict_review
        )
    except (
        DatabaseConfigurationError,
        DatabaseNotReadyError,
        MergeDatabaseNotReadyError,
        MergeError,
        RunLifecycleError,
        WorkspaceNotInitializedError,
    ) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return int(getattr(exc, "exit_code", 2))

    print(f"Run: {result.run_id}")
    print(f"Batch: {result.batch_id}")
    print(f"Candidate records: {result.candidate_record_count}")
    print(f"Facts created: {result.facts_created}")
    print(f"Facts existing: {result.facts_existing}")
    print(f"Relations created: {result.relations_created}")
    print(f"Relations existing: {result.relations_existing}")
    print(f"Conflicts created: {result.conflicts_created}")
    print(f"Conflicts existing: {result.conflicts_existing}")
    print(f"Skipped: {result.skipped_records}")
    print(f"Skipped pending: {result.skipped_pending}")
    print(f"Skipped rejected: {result.skipped_rejected}")
    print(f"Skipped superseded: {result.skipped_superseded}")
    print(f"Skipped non-leaf: {result.skipped_non_leaf}")
    return 0


def run_facts_reconcile_command(args: object) -> int:
    workspace = Path(getattr(args, "workspace"))
    reconciliation_id = getattr(args, "reconciliation_id", None)
    strict = bool(getattr(args, "strict", False))
    try:
        started = start_run(
            workspace,
            run_type="reconciliation",
            input_payload={
                "reconciliation_id": reconciliation_id,
                "strict": strict,
            },
        )
        result = reconcile_required(
            workspace,
            run_id=started.record.run_id,
            reconciliation_id=reconciliation_id,
            strict=strict,
        )
        payload = result.to_payload()
        complete_run(workspace, started.record.run_id, output_payload=payload)
    except (
        DatabaseConfigurationError,
        DatabaseNotReadyError,
        ReconciliationError,
        RunLifecycleError,
        WorkspaceNotInitializedError,
    ) as exc:
        if "started" in locals():
            _mark_started_run_failed(workspace, started.record.run_id, str(exc))
        print(f"Error: {exc}", file=sys.stderr)
        return int(getattr(exc, "exit_code", 2))
    print(canonical_json_artifact_v1(payload), end="")
    return int(payload["exit_code"])


def run_facts_merge_batch_command(args: object) -> int:
    workspace = Path(getattr(args, "workspace"))
    batch_ids = tuple(getattr(args, "batch_id", None) or ())
    stop_on_error = bool(getattr(args, "stop_on_error", False))

    try:
        result = facts_merge_batch(
            workspace,
            batch_ids=batch_ids,
            stop_on_error=stop_on_error,
        )
    except (
        BatchError,
        DatabaseConfigurationError,
        DatabaseNotReadyError,
        MergeDatabaseNotReadyError,
        MergeError,
        RunLifecycleError,
        WorkspaceNotInitializedError,
    ) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print("\n".join(batch_cli_lines(result)))
    return 2 if result.summary["failed"] else 0


def merge_facts_candidate_batch(
    workspace_dir: str | Path,
    *,
    batch_id: str,
    strict_review: bool = False,
    parent_run_id: str | None = None,
) -> MergeResult:
    workspace = Path(workspace_dir)
    batch_info = load_merge_batch_info(workspace, batch_id)
    started = start_run(
        workspace,
        run_type="merge",
        parent_run_id=parent_run_id,
        input_payload=batch_info.to_initial_payload(),
    )

    try:
        result = merge_candidate_batch(
            workspace,
            run_id=started.record.run_id,
            batch_id=batch_id,
            strict_review=strict_review,
        )
        complete_run(
            workspace,
            started.record.run_id,
            output_payload=result.to_artifact_payload(),
        )
        write_merge_artifacts(workspace, result)
    except (
        DatabaseConfigurationError,
        DatabaseNotReadyError,
        MergeDatabaseNotReadyError,
        MergeError,
        RunLifecycleError,
        WorkspaceNotInitializedError,
    ) as exc:
        _mark_started_run_failed(workspace, started.record.run_id, str(exc))
        _log_merge_failed(started.artifacts.workspace_dir, started.record.run_id, batch_id, str(exc))
        raise

    _log_merge_completed(started.artifacts.workspace_dir, result)
    return result


def _mark_started_run_failed(workspace: Path, run_id: str, error: str) -> None:
    try:
        fail_run(
            workspace,
            run_id,
            error=error,
            output_payload={"error": error},
        )
    except (
        DatabaseConfigurationError,
        DatabaseNotReadyError,
        RunLifecycleError,
        WorkspaceNotInitializedError,
    ):
        return


def _log_merge_completed(workspace_dir: Path, result: MergeResult) -> None:
    try:
        log_path = _resolve_app_log_path(workspace_dir)
    except (DatabaseConfigurationError, WorkspaceNotInitializedError):
        return

    log_event(
        log_path,
        level="INFO",
        event="facts_merge_completed",
        message=(
            f"Facts merge completed; batch={result.batch_id}; "
            f"records={result.candidate_record_count}; "
            f"facts_created={result.facts_created}; "
            f"relations_created={result.relations_created}; "
            f"conflicts_created={result.conflicts_created}; "
            f"skipped={result.skipped_records}"
        ),
        run_id=result.run_id,
    )


def _log_merge_failed(workspace_dir: Path, run_id: str, batch_id: str, error: str) -> None:
    try:
        log_path = _resolve_app_log_path(workspace_dir)
    except (DatabaseConfigurationError, WorkspaceNotInitializedError):
        return

    log_event(
        log_path,
        level="ERROR",
        event="facts_merge_failed",
        message=f"Facts merge failed; batch={batch_id}; error={error}",
        run_id=run_id,
    )


def _resolve_app_log_path(workspace_dir: Path) -> Path:
    config = load_config(workspace_dir)
    logging_config = config.get("logging", {})
    configured_path = logging_config.get("app_log_path", "logs/app.jsonl")
    return resolve_workspace_path(workspace_dir, configured_path)
