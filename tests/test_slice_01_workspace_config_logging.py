from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone

from dsl_mngr.cli.app import main
from dsl_mngr.core.config import load_config
from dsl_mngr.core.logging_setup import log_event
from dsl_mngr.core.workspace import WORKSPACE_DIRS, initialize_workspace


def test_init_workspace(tmp_path):
    workspace = tmp_path / "workspace"

    result = initialize_workspace(workspace)

    assert result.workspace_dir == workspace.resolve()
    assert (workspace / ".env").is_file()
    assert (workspace / "configs" / "project.yaml").is_file()
    assert (workspace / "logs" / "app.jsonl").is_file()
    for relative_dir in WORKSPACE_DIRS:
        assert (workspace / relative_dir).is_dir()

    project_config = (workspace / "configs" / "project.yaml").read_text(encoding="utf-8")
    assert "project:" in project_config
    assert "ai_handoff:" in project_config


def test_load_config_precedence(tmp_path):
    workspace = tmp_path / "workspace"
    initialize_workspace(workspace)
    (workspace / "configs" / "project.yaml").write_text(
        "\n".join(
            [
                "project:",
                "  name: from-project",
                "  timezone: UTC",
                "database:",
                "  path: from-project.sqlite",
                "  wal: false",
                "logging:",
                "  level: ERROR",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (workspace / ".env").write_text(
        "\n".join(
            [
                "MDW_DB_PATH=from-env.sqlite",
                "MDW_LOG_LEVEL=WARNING",
                "MDW_ENABLE_WAL=true",
                "",
            ]
        ),
        encoding="utf-8",
    )

    config = load_config(
        workspace,
        cli_options={
            "project": {"name": "from-cli"},
            "logging": {"level": "DEBUG"},
        },
    )

    assert config["project"]["name"] == "from-cli"
    assert config["project"]["timezone"] == "UTC"
    assert config["database"]["path"] == "from-env.sqlite"
    assert config["database"]["wal"] is True
    assert config["logging"]["level"] == "DEBUG"


def test_jsonl_log_record(tmp_path):
    log_path = tmp_path / "logs" / "app.jsonl"
    fixed_time = datetime(2026, 5, 26, 10, 30, tzinfo=timezone.utc)

    record = log_event(
        log_path,
        level="info",
        event="slice_test",
        message="A deterministic record",
        run_id="RUN_000001",
        worker="test_worker",
        clock=lambda: fixed_time,
    )

    saved = json.loads(log_path.read_text(encoding="utf-8").strip())
    assert saved == record
    assert saved["timestamp"] == "2026-05-26T10:30:00+00:00"
    assert saved["level"] == "INFO"
    assert saved["event"] == "slice_test"
    assert saved["message"] == "A deterministic record"
    assert saved["run_id"] == "RUN_000001"
    assert saved["worker"] == "test_worker"


def test_python_module_init_smoke(tmp_path):
    workspace = tmp_path / "module-workspace"

    completed = subprocess.run(
        [sys.executable, "-m", "dsl_mngr", "init", str(workspace)],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Initialized workspace:" in completed.stdout
    assert (workspace / "configs" / "project.yaml").is_file()
    assert (workspace / "logs" / "app.jsonl").is_file()
    records = [
        json.loads(line)
        for line in (workspace / "logs" / "app.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert records[-1]["event"] == "workspace_initialized"


def test_log_table_and_csv_export(tmp_path, capsys):
    workspace = tmp_path / "workspace"
    initialize_workspace(workspace)
    log_event(
        workspace / "logs" / "app.jsonl",
        level="INFO",
        event="first_event",
        message="First message",
    )

    assert main(["log", "table", str(workspace)]) == 0
    output = capsys.readouterr().out
    assert "timestamp" in output
    assert "first_event" in output
    assert "First message" in output

    csv_path = tmp_path / "logs.csv"
    assert main(["log", "table", str(workspace), "--format", "csv", "--output", str(csv_path)]) == 0
    csv_output = csv_path.read_text(encoding="utf-8")
    assert csv_output.startswith("timestamp,level,event,message,run_id,worker\n")
    assert "first_event" in csv_output
