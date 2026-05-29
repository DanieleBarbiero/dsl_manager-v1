from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

from dsl_mngr.cli.app import main
from dsl_mngr.core.migrations import migrate_workspace_database
from dsl_mngr.core.workspace import initialize_workspace


def test_scan_initial_corpus(tmp_path, capsys):
    workspace = _ready_workspace(tmp_path)
    manual = workspace / "corpus" / "active" / "docs" / "manual.txt"
    ddl = workspace / "corpus" / "active" / "ddl" / "schema.sql"
    manual.parent.mkdir(parents=True)
    ddl.parent.mkdir(parents=True)
    manual.write_bytes(b"manuale clienti\r\n")
    ddl.write_bytes(b"CREATE TABLE T (ID INTEGER);\n")

    assert main(["corpus", "scan", str(workspace)]) == 0

    output = capsys.readouterr().out
    assert "Added: 2" in output
    assert "Modified: 0" in output
    assert "Deleted: 0" in output
    assert "Unchanged: 0" in output

    with _connect(workspace) as connection:
        sources = connection.execute(
            "SELECT * FROM sources ORDER BY logical_name"
        ).fetchall()
        revisions = connection.execute(
            "SELECT * FROM source_revisions ORDER BY file_path"
        ).fetchall()
        events = connection.execute(
            "SELECT * FROM source_events ORDER BY source_event_id"
        ).fetchall()

    assert [row["source_id"] for row in sources] == ["SRC_000001", "SRC_000002"]
    assert [row["logical_name"] for row in sources] == [
        "corpus/active/ddl/schema.sql",
        "corpus/active/docs/manual.txt",
    ]
    for source in sources:
        assert source["source_type"] == "unknown"
        assert source["source_subtype"] is None
        assert source["authority_level"] == "unknown"
        assert source["status"] == "active"
        assert source["current_revision_id"].startswith("REV_")

    revision_by_path = {row["file_path"]: row for row in revisions}
    assert revision_by_path["corpus/active/docs/manual.txt"]["content_hash"] == _sha256(
        b"manuale clienti\r\n"
    )
    assert revision_by_path["corpus/active/docs/manual.txt"]["file_size"] == len(
        b"manuale clienti\r\n"
    )
    assert revision_by_path["corpus/active/ddl/schema.sql"]["content_hash"] == _sha256(
        b"CREATE TABLE T (ID INTEGER);\n"
    )
    assert {row["revision_number"] for row in revisions} == {1}
    assert {row["status"] for row in revisions} == {"active"}
    assert all(Path(row["file_path"]).is_absolute() is False for row in revisions)
    assert all("\\" not in row["file_path"] for row in revisions)

    assert [row["source_revision_id"] for row in revisions] == ["REV_000001", "REV_000002"]
    source_current_revisions = {row["current_revision_id"] for row in sources}
    assert source_current_revisions == {row["source_revision_id"] for row in revisions}
    assert [row["event_type"] for row in events] == ["source_added", "source_added"]
    assert all(row["run_id"] is None for row in events)


def test_source_modified_cascade_minimal(tmp_path, capsys):
    workspace = _ready_workspace(tmp_path)
    source_file = workspace / "corpus" / "active" / "manual.txt"
    source_file.write_bytes(b"version one\n")
    assert main(["corpus", "scan", str(workspace)]) == 0
    capsys.readouterr()

    source_file.write_bytes(b"version two\n")
    assert main(["corpus", "scan", str(workspace)]) == 0

    output = capsys.readouterr().out
    assert "Added: 0" in output
    assert "Modified: 1" in output
    assert "Deleted: 0" in output
    assert "Unchanged: 0" in output

    with _connect(workspace) as connection:
        source = connection.execute("SELECT * FROM sources").fetchone()
        revisions = connection.execute(
            "SELECT * FROM source_revisions ORDER BY revision_number"
        ).fetchall()
        event_types = [
            row["event_type"]
            for row in connection.execute(
                "SELECT event_type FROM source_events ORDER BY source_event_id"
            ).fetchall()
        ]

    assert source["current_revision_id"] == "REV_000002"
    assert [row["revision_number"] for row in revisions] == [1, 2]
    assert [row["status"] for row in revisions] == ["superseded", "active"]
    assert revisions[0]["content_hash"] == _sha256(b"version one\n")
    assert revisions[1]["content_hash"] == _sha256(b"version two\n")
    assert event_types == ["source_added", "source_modified"]


def test_source_deleted_event(tmp_path, capsys):
    workspace = _ready_workspace(tmp_path)
    source_file = workspace / "corpus" / "active" / "manual.txt"
    source_file.write_bytes(b"to be removed\n")
    assert main(["corpus", "scan", str(workspace)]) == 0
    capsys.readouterr()

    source_file.unlink()
    assert main(["corpus", "scan", str(workspace)]) == 0

    output = capsys.readouterr().out
    assert "Added: 0" in output
    assert "Modified: 0" in output
    assert "Deleted: 1" in output
    assert "Unchanged: 0" in output

    with _connect(workspace) as connection:
        source = connection.execute("SELECT * FROM sources").fetchone()
        revision = connection.execute("SELECT * FROM source_revisions").fetchone()
        event_types = [
            row["event_type"]
            for row in connection.execute(
                "SELECT event_type FROM source_events ORDER BY source_event_id"
            ).fetchall()
        ]

    assert source["status"] == "deleted_from_corpus"
    assert source["current_revision_id"] == revision["source_revision_id"]
    assert revision["status"] == "deleted"
    assert event_types == ["source_added", "source_deleted"]


def test_scan_unchanged_does_not_duplicate_events(tmp_path, capsys):
    workspace = _ready_workspace(tmp_path)
    source_file = workspace / "corpus" / "active" / "manual.txt"
    source_file.write_bytes(b"stable\n")
    assert main(["corpus", "scan", str(workspace)]) == 0
    capsys.readouterr()

    assert main(["corpus", "scan", str(workspace)]) == 0

    output = capsys.readouterr().out
    assert "Added: 0" in output
    assert "Modified: 0" in output
    assert "Deleted: 0" in output
    assert "Unchanged: 1" in output

    with _connect(workspace) as connection:
        revision_count = connection.execute("SELECT COUNT(*) FROM source_revisions").fetchone()[0]
        event_count = connection.execute("SELECT COUNT(*) FROM source_events").fetchone()[0]

    assert revision_count == 1
    assert event_count == 1


def test_scan_rejects_path_traversal_outside_workspace(tmp_path, capsys):
    workspace = _ready_workspace(tmp_path)

    assert main(["corpus", "scan", str(workspace), "--path", ".."]) == 2

    captured = capsys.readouterr()
    assert "Corpus path escapes the workspace" in captured.err


def test_scan_fails_when_workspace_is_not_initialized(tmp_path, capsys):
    workspace = tmp_path / "missing-workspace"

    assert main(["corpus", "scan", str(workspace)]) == 2

    captured = capsys.readouterr()
    assert "Workspace is not initialized" in captured.err
    assert "dsl-manager init" in captured.err


def test_scan_fails_when_database_is_not_initialized(tmp_path, capsys):
    workspace = tmp_path / "workspace"
    initialize_workspace(workspace)

    assert main(["corpus", "scan", str(workspace)]) == 2

    captured = capsys.readouterr()
    assert "Database is not initialized" in captured.err
    assert "dsl-manager db init" in captured.err


def _ready_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    initialize_workspace(workspace)
    migrate_workspace_database(workspace)
    return workspace


def _connect(workspace: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(workspace / "workspace.sqlite")
    connection.row_factory = sqlite3.Row
    return connection


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()
