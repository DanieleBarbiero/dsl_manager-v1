from __future__ import annotations

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
