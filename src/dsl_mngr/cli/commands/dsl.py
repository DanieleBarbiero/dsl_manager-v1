from __future__ import annotations

import sys
from pathlib import Path

from dsl_mngr.core.config import load_config
from dsl_mngr.core.database import (
    DatabaseConfigurationError,
    WorkspaceNotInitializedError,
    resolve_workspace_path,
)
from dsl_mngr.core.dsl_renderer import (
    DslRenderDatabaseNotReadyError,
    DslRenderError,
    DslRenderResult,
    ensure_dsl_render_database_ready,
    render_dsl_snapshot,
    write_dsl_render_artifacts,
)
from dsl_mngr.core.logging_setup import log_event
from dsl_mngr.core.runs import (
    DatabaseNotReadyError,
    RunLifecycleError,
    complete_run,
    fail_run,
    start_run,
)


def run_dsl_render_command(args: object) -> int:
    workspace = Path(getattr(args, "workspace"))
    output_dir = getattr(args, "output_dir", None)

    try:
        ensure_dsl_render_database_ready(workspace)
        started = start_run(
            workspace,
            run_type="dsl_render",
            input_payload={"output_dir": output_dir or "exports/dsl"},
        )
    except (
        DatabaseConfigurationError,
        DatabaseNotReadyError,
        DslRenderDatabaseNotReadyError,
        DslRenderError,
        RunLifecycleError,
        WorkspaceNotInitializedError,
    ) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    try:
        result = render_dsl_snapshot(
            workspace,
            run_id=started.record.run_id,
            output_dir=output_dir,
        )
        complete_run(
            workspace,
            started.record.run_id,
            output_payload=result.to_artifact_payload(),
        )
        write_dsl_render_artifacts(workspace, result)
    except (
        DatabaseConfigurationError,
        DatabaseNotReadyError,
        DslRenderDatabaseNotReadyError,
        DslRenderError,
        RunLifecycleError,
        WorkspaceNotInitializedError,
    ) as exc:
        _mark_started_run_failed(workspace, started.record.run_id, str(exc))
        _log_render_failed(started.artifacts.workspace_dir, started.record.run_id, str(exc))
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    _log_render_completed(started.artifacts.workspace_dir, result)

    print(f"Run: {result.run_id}")
    print(f"Snapshot: {result.snapshot_id}")
    print(f"DSL hash: {result.dsl_hash}")
    print(f"Facts: {result.fact_count}")
    print(f"Relations: {result.relation_count}")
    print(f"Conflicts: {result.conflict_count}")
    print(f"JSON: {result.json_path}")
    print(f"YAML: {result.yaml_path}")
    print(f"Markdown: {result.markdown_path}")
    return 0


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


def _log_render_completed(workspace_dir: Path, result: DslRenderResult) -> None:
    try:
        log_path = _resolve_app_log_path(workspace_dir)
    except (DatabaseConfigurationError, WorkspaceNotInitializedError):
        return

    log_event(
        log_path,
        level="INFO",
        event="dsl_render_completed",
        message=(
            f"DSL render completed; snapshot={result.snapshot_id}; "
            f"facts={result.fact_count}; relations={result.relation_count}; "
            f"conflicts={result.conflict_count}"
        ),
        run_id=result.run_id,
    )


def _log_render_failed(workspace_dir: Path, run_id: str, error: str) -> None:
    try:
        log_path = _resolve_app_log_path(workspace_dir)
    except (DatabaseConfigurationError, WorkspaceNotInitializedError):
        return

    log_event(
        log_path,
        level="ERROR",
        event="dsl_render_failed",
        message=f"DSL render failed; error={error}",
        run_id=run_id,
    )


def _resolve_app_log_path(workspace_dir: Path) -> Path:
    config = load_config(workspace_dir)
    logging_config = config.get("logging", {})
    configured_path = logging_config.get("app_log_path", "logs/app.jsonl")
    return resolve_workspace_path(workspace_dir, configured_path)
