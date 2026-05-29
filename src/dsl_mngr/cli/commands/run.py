from __future__ import annotations

import sys
from pathlib import Path

from dsl_mngr.core.database import (
    DatabaseConfigurationError,
    WorkspaceNotInitializedError,
)
from dsl_mngr.core.runs import DatabaseNotReadyError, RunLifecycleError, get_run_status, start_run


def run_start_command(args: object) -> int:
    workspace = Path(getattr(args, "workspace"))
    run_type = getattr(args, "run_type")
    parent_run_id = getattr(args, "parent_run_id", None)

    try:
        result = start_run(
            workspace,
            run_type=run_type,
            parent_run_id=parent_run_id,
        )
    except (
        DatabaseConfigurationError,
        DatabaseNotReadyError,
        RunLifecycleError,
        WorkspaceNotInitializedError,
    ) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print(f"Run: {result.record.run_id}")
    print(f"Type: {result.record.run_type}")
    print(f"Status: {result.record.status}")
    print(f"Started: {result.record.started_at}")
    print(f"Finished: {result.record.finished_at or ''}")
    print(f"Artifact directory: {result.record.artifact_dir}")
    return 0


def run_status_command(args: object) -> int:
    workspace_or_run_id = getattr(args, "workspace_or_run_id")
    requested_run_id = getattr(args, "run_id", None)
    if requested_run_id is None:
        workspace = Path(".")
        run_id = workspace_or_run_id
    else:
        workspace = Path(workspace_or_run_id)
        run_id = requested_run_id

    try:
        record = get_run_status(workspace, run_id)
    except (
        DatabaseConfigurationError,
        DatabaseNotReadyError,
        RunLifecycleError,
        WorkspaceNotInitializedError,
    ) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print(f"Run: {record.run_id}")
    print(f"Type: {record.run_type}")
    print(f"Status: {record.status}")
    print(f"Started: {record.started_at}")
    print(f"Finished: {record.finished_at or ''}")
    print(f"Artifact directory: {record.artifact_dir}")
    return 0
