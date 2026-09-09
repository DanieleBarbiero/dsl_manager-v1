from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from tests.slice_26_test_support import ready_workspace_with_interval


def test_slice_26_cli_help_and_entrypoints(tmp_path):
    executable = Path(sys.executable).with_name("dsl-manager.exe")
    dsl_help = subprocess.run(
        [str(executable), "dsl", "render", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    graph_help = subprocess.run(
        [sys.executable, "-m", "dsl_mngr", "graph", "export", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert dsl_help.returncode == 0
    assert dsl_help.stderr == ""
    assert "--schema-version {1,2}" in dsl_help.stdout
    assert "--allow-incomplete" in dsl_help.stdout
    assert graph_help.returncode == 0
    assert graph_help.stderr == ""
    assert "--snapshot-id SNAPSHOT_ID, --snapshot SNAPSHOT_ID" in graph_help.stdout
    assert "--dynamic" in graph_help.stdout
    assert "--timeformat {date,dateTime}" in graph_help.stdout

    workspace, _ = ready_workspace_with_interval(tmp_path)
    rendered = subprocess.run(
        [
            str(executable),
            "dsl",
            "render",
            str(workspace),
            "--schema-version",
            "2",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert rendered.returncode == 0
    assert rendered.stderr == ""
    assert "Snapshot: DSL_000001" in rendered.stdout
    exported = subprocess.run(
        [
            sys.executable,
            "-m",
            "dsl_mngr",
            "graph",
            "export",
            str(workspace),
            "--snapshot-id",
            "DSL_000001",
            "--dynamic",
            "--timeformat",
            "date",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert exported.returncode == 0
    assert exported.stderr == ""
    assert "Format: gexf" in exported.stdout
    assert "GEXF: exports/graph/DSL_000001.gexf" in exported.stdout


def test_slice_26_cli_expected_errors_have_no_traceback(tmp_path):
    executable = Path(sys.executable).with_name("dsl-manager.exe")
    workspace, _ = ready_workspace_with_interval(tmp_path)
    invalid_render = subprocess.run(
        [
            str(executable),
            "dsl",
            "render",
            str(workspace),
            "--allow-incomplete",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert invalid_render.returncode == 2
    assert "supported only for DSL schema 2" in invalid_render.stderr
    assert "Traceback" not in invalid_render.stderr

    valid_v1 = subprocess.run(
        [sys.executable, "-m", "dsl_mngr", "dsl", "render", str(workspace)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert valid_v1.returncode == 0
    invalid_export = subprocess.run(
        [
            str(executable),
            "graph",
            "export",
            str(workspace),
            "--snapshot-id",
            "DSL_000001",
            "--dynamic",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert invalid_export.returncode == 2
    assert "requires a DSL schema 2 snapshot" in invalid_export.stderr
    assert "Traceback" not in invalid_export.stderr
