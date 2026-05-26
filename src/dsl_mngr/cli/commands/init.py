from __future__ import annotations

from pathlib import Path

from dsl_mngr.core.logging_setup import log_event
from dsl_mngr.core.workspace import initialize_workspace


def run_init_command(args: object) -> int:
    workspace = Path(getattr(args, "workspace"))
    result = initialize_workspace(workspace)
    log_event(
        result.workspace_dir / "logs" / "app.jsonl",
        level="INFO",
        event="workspace_initialized",
        message=f"Workspace initialized at {result.workspace_dir}",
    )
    print(f"Initialized workspace: {result.workspace_dir}")
    return 0
