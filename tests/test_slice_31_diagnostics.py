from __future__ import annotations

import hashlib
import json
import sqlite3

from dsl_mngr.cli.app import build_parser, main


def test_slice_31_controlled_partial_diagnostic_is_bounded_and_non_mutating(tmp_path, capsys):
    workspace = tmp_path / "workspace"
    assert main(["init", str(workspace)]) == 0
    assert main(["db", "init", str(workspace)]) == 0
    source = workspace / "corpus" / "active" / "diagnostic.txt"
    source.write_text("controlled input\n", encoding="utf-8", newline="\n")
    assert main(["corpus", "scan", str(workspace)]) == 0
    capsys.readouterr()
    with sqlite3.connect(workspace / "workspace.sqlite") as connection:
        revision_id = str(connection.execute("SELECT source_revision_id FROM source_revisions").fetchone()[0])
        before = _production_state(connection)

    exit_code = main(
        [
            "diagnostics",
            "normalization",
            "run",
            str(workspace),
            "--revision",
            revision_id,
            "--scenario",
            "controlled_partial_success/1",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == payload["exit_code"] == payload["worker_exit_code"] == 6
    assert payload["status"] == "partial"
    assert payload["controlled_simulation"] is True
    assert payload["input_hash"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert payload["reasons"]
    prefix = f"artifacts/runs/{payload['run_id']}/diagnostics/normalization/"
    assert payload["artifact_paths"]
    assert all(path.startswith(prefix) for path in payload["artifact_paths"])
    assert all((workspace / path).is_file() for path in payload["artifact_paths"])
    assert not (workspace / "normalized" / "SRC_000001" / revision_id).exists()
    with sqlite3.connect(workspace / "workspace.sqlite") as connection:
        assert _production_state(connection) == before
        assert connection.execute(
            "SELECT status FROM runs WHERE run_id = ?", (payload["run_id"],)
        ).fetchone()[0] == "partial"
        assert connection.execute(
            "SELECT status FROM worker_runs WHERE run_id = ?", (payload["run_id"],)
        ).fetchone()[0] == "partial"

    option_strings = {
        option
        for action in build_parser()._subparsers._group_actions[0]
        .choices["diagnostics"]
        ._subparsers._group_actions[0]
        .choices["normalization"]
        ._subparsers._group_actions[0]
        .choices["run"]
        ._actions
        for option in action.option_strings
    }
    assert not option_strings.intersection(
        {"--worker", "--module", "--command", "--path", "--shell", "--payload"}
    )


def _production_state(connection: sqlite3.Connection) -> tuple[object, ...]:
    return (
        connection.execute("SELECT normalized_hash FROM source_revisions").fetchall(),
        connection.execute("SELECT COUNT(*) FROM workbook_manifests").fetchone()[0],
        connection.execute("SELECT COUNT(*) FROM source_fragments").fetchone()[0],
        connection.execute("SELECT COUNT(*) FROM chunks").fetchone()[0],
        connection.execute("SELECT COUNT(*) FROM candidate_records").fetchone()[0],
        connection.execute("SELECT COUNT(*) FROM facts").fetchone()[0],
        connection.execute("SELECT COUNT(*) FROM relations").fetchone()[0],
    )
