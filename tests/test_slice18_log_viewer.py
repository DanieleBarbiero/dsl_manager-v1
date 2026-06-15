from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from dsl_mngr.cli.app import main
from dsl_mngr.core.workspace import initialize_workspace


def test_log_table_render(tmp_path):
    workspace = tmp_path / "workspace"
    initialize_workspace(workspace)
    run_dir = workspace / "artifacts" / "runs" / "RUN_000001"
    run_dir.mkdir(parents=True)
    (run_dir / "process_report.json").write_text('{"run_id":"RUN_000001"}\n', encoding="utf-8")
    _write_jsonl(
        run_dir / "log.jsonl",
        [
            {
                "timestamp": "2026-01-01T08:00:00+00:00",
                "level": "INFO",
                "run_id": "RUN_000001",
                "worker": "worker_a",
                "event": "run_specific",
                "message": "Run specific message",
            }
        ],
    )
    _write_jsonl(
        workspace / "logs" / "app.jsonl",
        [
            {
                "timestamp": "2026-01-02T10:00:00+00:00",
                "level": "ERROR",
                "event": "later_event",
                "message": "Later message",
            },
            {
                "timestamp": "2026-01-01T09:00:00+00:00",
                "level": "INFO",
                "run_id": "RUN_000001",
                "worker": "worker_a",
                "event": "special_event",
                "source_id": "SRC_000001",
                "source_revision_id": "REV_000001",
                "message": 'Special <tag> & "quoted"',
                "duration_ms": 42,
                "exit_code": 0,
            },
        ],
    )

    assert (
        main(
            [
                "log",
                "table",
                str(workspace),
                "--format",
                "html",
                "--output",
                "exports/logs/app_log.html",
            ]
        )
        == 0
    )
    app_html = (workspace / "exports" / "logs" / "app_log.html").read_text(encoding="utf-8")
    assert '<input type="search" data-log-filter' in app_html
    assert "Special &lt;tag&gt; &amp; &quot;quoted&quot;" in app_html
    assert "../../artifacts/runs/RUN_000001/process_report.json" in app_html
    assert "../../artifacts/runs/RUN_000001/log.jsonl" in app_html
    assert app_html.index("Special &lt;tag&gt;") < app_html.index("Later message")

    assert (
        main(
            [
                "log",
                "table",
                str(run_dir / "log.jsonl"),
                "--output",
                "exports/logs/RUN_000001_log_table.html",
            ]
        )
        == 0
    )
    run_html_path = workspace / "exports" / "logs" / "RUN_000001_log_table.html"
    run_html = run_html_path.read_text(encoding="utf-8")
    assert '<input type="search" data-log-filter' in run_html
    assert "Run specific message" in run_html
    assert "../../artifacts/runs/RUN_000001/log.jsonl" in run_html

    completed = subprocess.run(
        [sys.executable, "-m", "dsl_mngr", "log", "table", str(workspace)],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert "special_event" in completed.stdout
    assert 'Special <tag> & "quoted"' in completed.stdout


def test_log_csv_render(tmp_path, capsys):
    workspace = tmp_path / "workspace"
    initialize_workspace(workspace)
    app_log = workspace / "logs" / "app.jsonl"
    _write_jsonl(
        app_log,
        [
            {
                "timestamp": "2026-01-02T10:00:00+00:00",
                "level": "ERROR",
                "event": "second_event",
                "message": "Second message",
            },
            {
                "timestamp": "2026-01-01T10:00:00+00:00",
                "level": "WARNING",
                "run_id": "RUN_000002",
                "worker": "worker_b",
                "event_type": "first_event_type",
                "source_id": "SRC_000002",
                "source_revision_id": "REV_000002",
                "message": "First message",
                "duration_ms": 7,
                "exit_code": 5,
            },
        ],
    )

    assert main(["log", "csv", str(app_log), "--output", "exports/logs/app.csv"]) == 0
    csv_path = workspace / "exports" / "logs" / "app.csv"
    csv_bytes = csv_path.read_bytes()
    csv_output = csv_bytes.decode("utf-8")
    assert b"\r\n" not in csv_bytes
    assert csv_output.startswith(
        "timestamp,level,run_id,worker,event,source_id,source_revision_id,message,duration_ms,exit_code\n"
    )
    assert csv_output.index("first_event_type") < csv_output.index("second_event")
    assert "SRC_000002" in csv_output
    assert ",7,5\n" in csv_output

    legacy_csv_path = tmp_path / "legacy.csv"
    assert (
        main(
            [
                "log",
                "table",
                str(workspace),
                "--format",
                "csv",
                "--output",
                str(legacy_csv_path),
            ]
        )
        == 0
    )
    legacy_output = legacy_csv_path.read_text(encoding="utf-8")
    assert legacy_output.startswith("timestamp,level,event,message,run_id,worker\n")
    assert "first_event_type" not in legacy_output

    bad_log = workspace / "logs" / "bad.jsonl"
    bad_log.write_text('{"timestamp":"2026-01-01T00:00:00+00:00"}\n{bad}\n', encoding="utf-8")
    assert main(["log", "csv", str(bad_log), "--output", str(tmp_path / "bad.csv")]) == 1
    captured = capsys.readouterr()
    assert "Invalid JSONL record at line 2" in captured.err
    assert "logs/bad.jsonl" in captured.err


def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records)
    path.write_text(content, encoding="utf-8", newline="\n")
