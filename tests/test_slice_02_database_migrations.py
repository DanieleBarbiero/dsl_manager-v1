from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone

from dsl_mngr.cli.app import main
from dsl_mngr.core.database import connect_workspace_database
from dsl_mngr.core.migrations import MIGRATIONS, migrate_workspace_database
from dsl_mngr.core.workspace import initialize_workspace


REQUIRED_TABLES = {
    "schema_migrations",
    "sources",
    "source_revisions",
    "source_events",
    "runs",
    "worker_runs",
}


def test_database_init(tmp_path, capsys):
    workspace = tmp_path / "workspace"
    initialize_workspace(workspace)

    assert main(["db", "init", str(workspace)]) == 0

    output = capsys.readouterr().out
    database_path = workspace / "workspace.sqlite"
    assert database_path.is_file()
    assert f"Database: {database_path.resolve()}" in output
    assert f"Migrations applied: {len(MIGRATIONS)}" in output
    assert "Migrations skipped: 0" in output

    records = [
        json.loads(line)
        for line in (workspace / "logs" / "app.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert records[-1]["event"] == "database_initialized"
    assert "applied=" in records[-1]["message"]


def test_migrations_idempotent(tmp_path):
    workspace = tmp_path / "workspace"
    initialize_workspace(workspace)
    fixed_time = datetime(2026, 5, 26, 10, 30, tzinfo=timezone.utc)

    first = migrate_workspace_database(workspace, clock=lambda: fixed_time)
    second = migrate_workspace_database(workspace, clock=lambda: fixed_time)

    assert first.applied_count == len(MIGRATIONS)
    assert first.skipped_count == 0
    assert second.applied_count == 0
    assert second.skipped_count == len(MIGRATIONS)

    with sqlite3.connect(first.database_path) as connection:
        row_count = connection.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
    assert row_count == len(MIGRATIONS)


def test_database_path_uses_env_override(tmp_path):
    workspace = tmp_path / "workspace"
    initialize_workspace(workspace)
    (workspace / ".env").write_text(
        "\n".join(
            [
                "MDW_DB_PATH=data/custom.sqlite",
                "MDW_ENABLE_WAL=false",
                "",
            ]
        ),
        encoding="utf-8",
    )

    result = migrate_workspace_database(workspace)

    assert result.database_path == (workspace / "data" / "custom.sqlite").resolve()
    assert result.database_path.is_file()


def test_wal_config(tmp_path):
    workspace = tmp_path / "workspace"
    initialize_workspace(workspace)

    result = migrate_workspace_database(workspace)

    with sqlite3.connect(result.database_path) as connection:
        journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
    assert journal_mode.lower() == "wal"


def test_foreign_keys_enabled(tmp_path):
    workspace = tmp_path / "workspace"
    initialize_workspace(workspace)
    migrate_workspace_database(workspace)

    connection = connect_workspace_database(workspace)
    try:
        enabled = connection.execute("PRAGMA foreign_keys").fetchone()[0]
    finally:
        connection.close()

    assert enabled == 1


def test_db_init_cli_smoke(tmp_path):
    workspace = tmp_path / "workspace"
    initialize_workspace(workspace)

    completed = subprocess.run(
        [sys.executable, "-m", "dsl_mngr", "db", "init", str(workspace)],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Database:" in completed.stdout
    assert "Migrations applied:" in completed.stdout
    assert (workspace / "workspace.sqlite").is_file()


def test_minimal_tables_exist(tmp_path):
    workspace = tmp_path / "workspace"
    initialize_workspace(workspace)
    result = migrate_workspace_database(workspace)

    with sqlite3.connect(result.database_path) as connection:
        table_names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }

    assert REQUIRED_TABLES.issubset(table_names)


def test_db_init_fails_readably_when_workspace_not_initialized(tmp_path, capsys):
    workspace = tmp_path / "not-initialized"

    assert main(["db", "init", str(workspace)]) == 2

    captured = capsys.readouterr()
    assert "Workspace is not initialized" in captured.err
    assert "dsl-manager init" in captured.err
    assert not (workspace / "workspace.sqlite").exists()
