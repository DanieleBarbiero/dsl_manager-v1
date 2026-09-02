from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from dsl_mngr.cli.app import main
from dsl_mngr.core.migrations import migrate_workspace_database
from dsl_mngr.core.runs import RunLifecycleError, complete_run, fail_run, start_run
from dsl_mngr.core.worker_runner import run_worker
from dsl_mngr.core.workspace import initialize_workspace


FIXED_TIME = datetime(2026, 5, 29, 12, 0, tzinfo=timezone.utc)
WORKERS_DIR = Path(__file__).parent / "fixtures" / "workers"


def test_run_lifecycle(tmp_path):
    workspace = _ready_workspace(tmp_path)

    started = start_run(
        workspace,
        run_type="test",
        input_payload={"b": 2, "a": 1},
        clock=lambda: FIXED_TIME,
    )

    assert started.record.run_id == "RUN_000001"
    assert started.record.status == "running"
    assert started.record.started_at == "2026-05-29T12:00:00+00:00"
    assert started.artifacts.artifact_dir.is_dir()

    completed = complete_run(
        workspace,
        "RUN_000001",
        output_payload={"z": 3, "a": 1},
        clock=lambda: FIXED_TIME,
    )
    assert completed.status == "completed"
    assert completed.finished_at == "2026-05-29T12:00:00+00:00"

    failed_started = start_run(
        workspace,
        run_type="test",
        parent_run_id="RUN_000001",
        clock=lambda: FIXED_TIME,
    )
    assert failed_started.record.run_id == "RUN_000002"
    assert failed_started.record.parent_run_id == "RUN_000001"

    failed = fail_run(
        workspace,
        "RUN_000002",
        error="deterministic failure",
        clock=lambda: FIXED_TIME,
    )
    assert failed.status == "failed"

    with pytest.raises(RunLifecycleError, match="Parent run not found"):
        start_run(workspace, run_type="test", parent_run_id="RUN_999999")

    with _connect(workspace) as connection:
        rows = connection.execute("SELECT run_id, status FROM runs ORDER BY run_id").fetchall()
    assert [(row["run_id"], row["status"]) for row in rows] == [
        ("RUN_000001", "completed"),
        ("RUN_000002", "failed"),
    ]


def test_run_start_and_status_cli_smoke(tmp_path, capsys):
    workspace = _ready_workspace(tmp_path)

    assert main(["run", "start", str(workspace), "--type", "test"]) == 0
    start_output = capsys.readouterr().out
    assert "Run: RUN_000001" in start_output
    assert "Type: test" in start_output
    assert "Status: running" in start_output
    assert "Artifact directory: artifacts/runs/RUN_000001" in start_output

    completed = subprocess.run(
        [sys.executable, "-m", "dsl_mngr", "run", "status", str(workspace), "RUN_000001"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "Run: RUN_000001" in completed.stdout
    assert "Status: running" in completed.stdout
    assert "Started:" in completed.stdout
    assert "Finished:" in completed.stdout


def test_worker_success_report(tmp_path):
    workspace = _ready_workspace(tmp_path)
    started = start_run(workspace, run_type="test", clock=lambda: FIXED_TIME)

    result = run_worker(
        workspace,
        run_id=started.record.run_id,
        worker_name="success_worker",
        worker_path=WORKERS_DIR / "success_worker.py",
        worker_version="1.0",
        input_payload={"fixture": True},
        clock=lambda: FIXED_TIME,
    )

    assert result.status == "completed"
    assert result.exit_code == 0
    assert result.output is not None
    assert result.output["run_id"] == "RUN_000001"
    assert result.output["worker_name"] == "success_worker"

    artifacts = started.artifacts
    report = json.loads(artifacts.process_report_path.read_text(encoding="utf-8"))
    assert report["status"] == "completed"
    assert report["workers"][0]["worker_run_id"] == "WRK_000001"
    assert report["workers"][0]["stdout"] == "success worker completed\n"
    assert report["workers"][0]["stderr"] == ""

    with _connect(workspace) as connection:
        run = connection.execute("SELECT * FROM runs WHERE run_id = 'RUN_000001'").fetchone()
        worker_run = connection.execute("SELECT * FROM worker_runs").fetchone()

    assert run["status"] == "completed"
    assert json.loads(run["output_json"]) == result.output
    assert worker_run["status"] == "completed"
    assert worker_run["input_path"] == "artifacts/runs/RUN_000001/input.json"
    assert worker_run["output_path"] == "artifacts/runs/RUN_000001/output.json"
    assert worker_run["report_path"] == "artifacts/runs/RUN_000001/process_report.json"
    assert worker_run["log_path"] == "artifacts/runs/RUN_000001/log.jsonl"
    assert "\\" not in worker_run["input_path"]
    assert not Path(worker_run["input_path"]).is_absolute()

    log_records = [
        json.loads(line)
        for line in artifacts.log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert all(record["run_id"] == "RUN_000001" for record in log_records)
    assert any(record.get("worker") == "success_worker" for record in log_records)


def test_worker_failure_does_not_mutate_db(tmp_path):
    workspace = _ready_workspace(tmp_path)
    failing_run = start_run(workspace, run_type="test", clock=lambda: FIXED_TIME)
    mutation_called = False

    def should_not_run(connection: sqlite3.Connection, output: dict[str, object]) -> None:
        nonlocal mutation_called
        mutation_called = True
        _insert_source_mutation(connection)

    failed_process = run_worker(
        workspace,
        run_id=failing_run.record.run_id,
        worker_name="failure_worker",
        worker_path=WORKERS_DIR / "failure_worker.py",
        apply_mutations=should_not_run,
        clock=lambda: FIXED_TIME,
    )

    assert failed_process.status == "failed"
    assert failed_process.exit_code == 7
    assert mutation_called is False

    rollback_run = start_run(workspace, run_type="test", clock=lambda: FIXED_TIME)

    def insert_then_fail(connection: sqlite3.Connection, output: dict[str, object]) -> None:
        _insert_source_mutation(connection)
        raise RuntimeError("mutation exploded")

    failed_mutation = run_worker(
        workspace,
        run_id=rollback_run.record.run_id,
        worker_name="success_worker",
        worker_path=WORKERS_DIR / "success_worker.py",
        apply_mutations=insert_then_fail,
        clock=lambda: FIXED_TIME,
    )

    assert failed_mutation.status == "failed"
    assert "Failed to apply worker mutations" in str(failed_mutation.error)

    with _connect(workspace) as connection:
        source_count = connection.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
        run_statuses = [
            row["status"]
            for row in connection.execute("SELECT status FROM runs ORDER BY run_id").fetchall()
        ]
        worker_statuses = [
            row["status"]
            for row in connection.execute("SELECT status FROM worker_runs ORDER BY worker_run_id").fetchall()
        ]

    assert source_count == 0
    assert run_statuses == ["failed", "failed"]
    assert worker_statuses == ["failed", "failed"]


def test_worker_invalid_output_marks_run_failed(tmp_path):
    workspace = _ready_workspace(tmp_path)
    started = start_run(workspace, run_type="test", clock=lambda: FIXED_TIME)
    mutation_called = False

    def should_not_run(connection: sqlite3.Connection, output: dict[str, object]) -> None:
        nonlocal mutation_called
        mutation_called = True
        _insert_source_mutation(connection)

    result = run_worker(
        workspace,
        run_id=started.record.run_id,
        worker_name="invalid_output_worker",
        worker_path=WORKERS_DIR / "invalid_output_worker.py",
        apply_mutations=should_not_run,
        clock=lambda: FIXED_TIME,
    )

    assert result.status == "failed"
    assert "incoherent" in str(result.error)
    assert mutation_called is False
    assert started.artifacts.output_path.is_file()

    report = json.loads(started.artifacts.process_report_path.read_text(encoding="utf-8"))
    assert report["status"] == "failed"
    assert "incoherent" in report["error"]

    with _connect(workspace) as connection:
        run = connection.execute("SELECT * FROM runs WHERE run_id = 'RUN_000001'").fetchone()
        worker = connection.execute("SELECT * FROM worker_runs").fetchone()
        source_count = connection.execute("SELECT COUNT(*) FROM sources").fetchone()[0]

    assert run["status"] == "failed"
    assert run["output_json"] is None
    assert worker["status"] == "failed"
    assert source_count == 0


def test_run_artifacts_are_relative_and_deterministic(tmp_path):
    workspace = _ready_workspace(tmp_path)
    started = start_run(
        workspace,
        run_type="test",
        input_payload={"z": 0, "a": 1},
        clock=lambda: FIXED_TIME,
    )

    expected_input = (
        "{\n"
        '  "artifact_dir": "artifacts/runs/RUN_000001",\n'
        '  "parameters": {\n'
        '    "a": 1,\n'
        '    "z": 0\n'
        "  },\n"
        '  "parent_run_id": null,\n'
        '  "run_id": "RUN_000001",\n'
        '  "run_type": "test"\n'
        "}\n"
    )
    assert started.artifacts.input_path.read_text(encoding="utf-8") == expected_input

    resolved_config = started.artifacts.resolved_config_path.read_text(encoding="utf-8")
    expected_hash = hashlib.sha256(resolved_config.encode("utf-8")).hexdigest()
    assert started.artifacts.config_hash_path.read_text(encoding="utf-8") == expected_hash + "\n"

    completed = complete_run(
        workspace,
        "RUN_000001",
        output_payload={"z": 2, "a": 1},
        clock=lambda: FIXED_TIME,
    )
    expected_output = "{\n" '  "a": 1,\n' '  "z": 2\n' "}\n"
    assert started.artifacts.output_path.read_text(encoding="utf-8") == expected_output

    with _connect(workspace) as connection:
        row = connection.execute("SELECT input_json, output_json FROM runs").fetchone()

    assert row["input_json"] == expected_input
    assert row["output_json"] == expected_output
    assert completed.artifact_dir == "artifacts/runs/RUN_000001"
    assert Path(completed.artifact_dir).is_absolute() is False
    assert "\\" not in completed.artifact_dir


def _ready_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    initialize_workspace(workspace)
    migrate_workspace_database(workspace)
    return workspace


def _connect(workspace: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(workspace / "workspace.sqlite")
    connection.row_factory = sqlite3.Row
    return connection


def _insert_source_mutation(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        INSERT INTO sources (
            source_id,
            logical_name,
            source_type,
            source_subtype,
            authority_level,
            first_seen_at,
            last_seen_at,
            current_revision_id,
            status,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, NULL, ?, ?, ?, NULL, ?, ?, ?)
        """,
        (
            "SRC_999999",
            "mutated.txt",
            "unknown",
            "unknown",
            "2026-05-29T12:00:00+00:00",
            "2026-05-29T12:00:00+00:00",
            "active",
            "2026-05-29T12:00:00+00:00",
            "2026-05-29T12:00:00+00:00",
        ),
    )
