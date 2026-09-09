from __future__ import annotations

import json

import pytest

from dsl_mngr.cli.app import main
from dsl_mngr.core.dsl_diff import DslDiffError, diff_dsl_snapshots
from dsl_mngr.core.dsl_renderer import render_dsl_snapshot
from tests.slice_26_test_support import connect, ready_workspace_with_interval


def test_slice_27_cross_schema_diff_is_explicit_and_categorized(tmp_path, capsys):
    workspace, _ = ready_workspace_with_interval(tmp_path)
    with connect(workspace) as connection:
        run_id = str(connection.execute("SELECT run_id FROM runs ORDER BY run_id DESC LIMIT 1").fetchone()[0])
    v1 = render_dsl_snapshot(workspace, run_id=run_id, schema_version="1")
    v2 = render_dsl_snapshot(workspace, run_id=run_id, schema_version="2")

    with pytest.raises(DslDiffError, match="--cross-schema"):
        diff_dsl_snapshots(
            workspace,
            run_id=run_id,
            from_snapshot_id=v1.snapshot_id,
            to_snapshot_id=v2.snapshot_id,
        )

    result = diff_dsl_snapshots(
        workspace,
        run_id=run_id,
        from_snapshot_id=v1.snapshot_id,
        to_snapshot_id=v2.snapshot_id,
        cross_schema=True,
    )
    payload = json.loads((workspace / result.json_path).read_text(encoding="utf-8"))
    assert payload["metadata"]["schema_version"] == "cross"
    assert payload["metadata"]["cross_schema"] is True
    assert payload["summary"]["categories"] == {
        "governance": 1,
        "structural": 0,
        "temporal": 1,
    }
    assert [change["category"] for change in payload["changes"]] == [
        "governance",
        "temporal",
    ]
    assert all(change["causes"] for change in payload["changes"])

    assert main(
        [
            "dsl",
            "diff",
            str(workspace),
            "--from",
            v1.snapshot_id,
            "--to",
            v2.snapshot_id,
            "--cross-schema",
            "--output-dir",
            "exports/cross_cli",
        ]
    ) == 0
    captured = capsys.readouterr()
    assert "Traceback" not in captured.err
    assert "Changes:" in captured.out
