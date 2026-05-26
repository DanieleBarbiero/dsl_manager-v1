from __future__ import annotations

import sys
from pathlib import Path

from dsl_mngr.core.config import load_config
from dsl_mngr.core.database import (
    DatabaseConfigurationError,
    WorkspaceNotInitializedError,
    resolve_workspace_path,
)
from dsl_mngr.core.logging_setup import log_event
from dsl_mngr.core.migrations import MigrationError, migrate_workspace_database


def run_db_init_command(args: object) -> int:
    workspace = Path(getattr(args, "workspace"))
    try:
        result = migrate_workspace_database(workspace)
    except (DatabaseConfigurationError, MigrationError, WorkspaceNotInitializedError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    log_path = _resolve_app_log_path(result.settings.workspace_dir)
    if result.database_created:
        event = "database_initialized"
    elif result.applied_count:
        event = "database_migrated"
    else:
        event = "database_migrations_checked"
    log_event(
        log_path,
        level="INFO",
        event=event,
        message=(
            f"Database ready at {result.database_path}; "
            f"applied={result.applied_count}; skipped={result.skipped_count}"
        ),
    )

    print(f"Database: {result.database_path}")
    print(f"Migrations applied: {result.applied_count}")
    print(f"Migrations skipped: {result.skipped_count}")
    return 0


def _resolve_app_log_path(workspace_dir: Path) -> Path:
    config = load_config(workspace_dir)
    logging_config = config.get("logging", {})
    configured_path = logging_config.get("app_log_path", "logs/app.jsonl")
    return resolve_workspace_path(workspace_dir, configured_path)
