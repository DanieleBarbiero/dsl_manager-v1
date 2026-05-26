from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dsl_mngr.core.config import load_config


class WorkspaceNotInitializedError(RuntimeError):
    """Raised when a command needs a workspace created by dsl-manager init."""


class DatabaseConfigurationError(RuntimeError):
    """Raised when database configuration cannot be resolved safely."""


@dataclass(frozen=True)
class DatabaseSettings:
    workspace_dir: Path
    database_path: Path
    wal_enabled: bool


def ensure_workspace_initialized(workspace_dir: str | Path) -> Path:
    workspace_path = Path(workspace_dir).resolve()
    missing = [
        marker
        for marker in (".env", "configs/project.yaml", "logs/app.jsonl")
        if not (workspace_path / marker).exists()
    ]
    if missing:
        raise WorkspaceNotInitializedError(
            f"Workspace is not initialized: {workspace_path}. "
            "Run 'dsl-manager init <workspace>' before 'dsl-manager db init'."
        )
    return workspace_path


def resolve_database_settings(
    workspace_dir: str | Path,
    cli_options: dict[str, Any] | None = None,
) -> DatabaseSettings:
    workspace_path = ensure_workspace_initialized(workspace_dir)
    config = load_config(workspace_path, cli_options=cli_options)
    database_config = config.get("database", {})

    configured_path = database_config.get("path", "workspace.sqlite")
    database_path = resolve_database_path(workspace_path, configured_path)
    wal_enabled = bool(database_config.get("wal", False))

    return DatabaseSettings(
        workspace_dir=workspace_path,
        database_path=database_path,
        wal_enabled=wal_enabled,
    )


def resolve_database_path(workspace_dir: str | Path, configured_path: str | Path) -> Path:
    try:
        return resolve_workspace_path(workspace_dir, configured_path)
    except DatabaseConfigurationError as exc:
        raise DatabaseConfigurationError(
            f"Database path escapes the workspace: {configured_path}"
        ) from exc


def resolve_workspace_path(workspace_dir: str | Path, configured_path: str | Path) -> Path:
    workspace_path = Path(workspace_dir).resolve()
    raw_path = Path(str(configured_path)).expanduser()
    if raw_path.is_absolute():
        resolved_path = raw_path.resolve()
    else:
        resolved_path = (workspace_path / raw_path).resolve()
    try:
        resolved_path.relative_to(workspace_path)
    except ValueError as exc:
        raise DatabaseConfigurationError(
            f"Configured path escapes the workspace: {configured_path}"
        ) from exc
    return resolved_path


def connect_workspace_database(
    workspace_dir: str | Path,
    cli_options: dict[str, Any] | None = None,
) -> sqlite3.Connection:
    settings = resolve_database_settings(workspace_dir, cli_options=cli_options)
    return open_database(settings.database_path, enable_wal=settings.wal_enabled)


def open_database(database_path: str | Path, *, enable_wal: bool = False) -> sqlite3.Connection:
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    if enable_wal:
        connection.execute("PRAGMA journal_mode = WAL")
    return connection
