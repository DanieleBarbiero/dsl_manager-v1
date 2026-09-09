from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from dsl_mngr.core.migrations import migrate_workspace_database
from dsl_mngr.core.runs import start_run
from dsl_mngr.core.source_registry import scan_corpus
from dsl_mngr.core.workspace import initialize_workspace


FIXED_TIME = datetime(2026, 9, 4, 10, 11, 12, tzinfo=timezone.utc)


def registered_workspace(
    root: Path,
    files: dict[str, bytes | str],
) -> tuple[Path, str, dict[str, str]]:
    workspace = root / "workspace"
    initialize_workspace(workspace)
    migrate_workspace_database(workspace, clock=lambda: FIXED_TIME)
    for name, value in files.items():
        path = workspace / "corpus" / "active" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(value, bytes):
            path.write_bytes(value)
        else:
            path.write_text(value, encoding="utf-8", newline="\n")
    scan_corpus(workspace, clock=lambda: FIXED_TIME)
    started = start_run(
        workspace,
        run_type="test",
        input_payload={"slice": 27},
        clock=lambda: FIXED_TIME,
    )
    with connect(workspace) as connection:
        rows = connection.execute(
            "SELECT file_path, source_revision_id FROM source_revisions ORDER BY file_path"
        ).fetchall()
    return workspace, started.record.run_id, {
        Path(str(row["file_path"])).name: str(row["source_revision_id"])
        for row in rows
    }


def connect(workspace: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(workspace / "workspace.sqlite")
    connection.row_factory = sqlite3.Row
    return connection
