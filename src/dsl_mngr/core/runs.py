from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from dsl_mngr.core.config import dump_simple_yaml, load_config
from dsl_mngr.core.database import DatabaseSettings, open_database, resolve_database_settings
from dsl_mngr.core.logging_setup import log_event
from dsl_mngr.core.migrations import MIGRATIONS


Clock = Callable[[], datetime]

RUN_TYPES = {
    "scan",
    "register",
    "normalize",
    "chunk",
    "parse_ddl",
    "ai_package",
    "candidate_import",
    "candidate_validation",
    "merge",
    "dsl_render",
    "dsl_diff",
    "gexf_export",
    "batch",
    "log_table",
    "test",
}

RUN_STATUSES = {"running", "completed", "failed"}


class RunLifecycleError(RuntimeError):
    """Raised when a run cannot be created or updated safely."""


class DatabaseNotReadyError(RunLifecycleError):
    """Raised when the workspace database is missing or not migrated."""


@dataclass(frozen=True)
class RunArtifactPaths:
    workspace_dir: Path
    artifact_dir: Path

    @property
    def input_path(self) -> Path:
        return self.artifact_dir / "input.json"

    @property
    def output_path(self) -> Path:
        return self.artifact_dir / "output.json"

    @property
    def process_report_path(self) -> Path:
        return self.artifact_dir / "process_report.json"

    @property
    def resolved_config_path(self) -> Path:
        return self.artifact_dir / "resolved_config.yaml"

    @property
    def config_hash_path(self) -> Path:
        return self.artifact_dir / "config_hash.txt"

    @property
    def log_path(self) -> Path:
        return self.artifact_dir / "log.jsonl"

    @property
    def artifact_dir_relative(self) -> str:
        return relative_workspace_path(self.workspace_dir, self.artifact_dir)

    @property
    def input_path_relative(self) -> str:
        return relative_workspace_path(self.workspace_dir, self.input_path)

    @property
    def output_path_relative(self) -> str:
        return relative_workspace_path(self.workspace_dir, self.output_path)

    @property
    def process_report_path_relative(self) -> str:
        return relative_workspace_path(self.workspace_dir, self.process_report_path)

    @property
    def log_path_relative(self) -> str:
        return relative_workspace_path(self.workspace_dir, self.log_path)


@dataclass(frozen=True)
class RunRecord:
    run_id: str
    run_type: str
    status: str
    started_at: str
    finished_at: str | None
    parent_run_id: str | None
    input_json: str | None
    output_json: str | None
    created_at: str
    updated_at: str
    artifact_dir: str


@dataclass(frozen=True)
class StartedRun:
    record: RunRecord
    artifacts: RunArtifactPaths
    config_hash: str


def start_run(
    workspace_dir: str | Path,
    *,
    run_type: str,
    parent_run_id: str | None = None,
    input_payload: dict[str, Any] | None = None,
    cli_options: dict[str, Any] | None = None,
    clock: Clock | None = None,
) -> StartedRun:
    if run_type not in RUN_TYPES:
        raise RunLifecycleError(
            f"Unsupported run type: {run_type}. Expected one of: {', '.join(sorted(RUN_TYPES))}."
        )

    settings = resolve_database_settings(workspace_dir)
    ensure_workspace_database_ready(settings)
    timestamp = timestamp_now(clock)

    connection = open_database(settings.database_path, enable_wal=settings.wal_enabled)
    try:
        validate_database_migrations(connection)
        if parent_run_id is not None:
            validate_parent_run(connection, parent_run_id)

        run_id = next_id(connection, "runs", "run_id", "RUN")
        artifacts = run_artifact_paths(settings.workspace_dir, run_id)
        artifacts.artifact_dir.mkdir(parents=True, exist_ok=True)

        resolved_config_yaml = dump_simple_yaml(load_config(settings.workspace_dir, cli_options=cli_options))
        config_hash = hashlib.sha256(resolved_config_yaml.encode("utf-8")).hexdigest()

        input_document = {
            "artifact_dir": artifacts.artifact_dir_relative,
            "parameters": input_payload or {},
            "parent_run_id": parent_run_id,
            "run_id": run_id,
            "run_type": run_type,
        }
        input_json = canonical_json(input_document)
        process_report = base_process_report(
            run_id=run_id,
            run_type=run_type,
            status="running",
            started_at=timestamp,
            finished_at=None,
            artifact_dir=artifacts.artifact_dir_relative,
            config_hash=config_hash,
        )

        artifacts.resolved_config_path.write_text(resolved_config_yaml, encoding="utf-8", newline="\n")
        artifacts.config_hash_path.write_text(config_hash + "\n", encoding="utf-8", newline="\n")
        artifacts.input_path.write_text(input_json, encoding="utf-8", newline="\n")
        write_process_report(artifacts.process_report_path, process_report)
        artifacts.log_path.touch(exist_ok=True)

        connection.execute("BEGIN")
        try:
            connection.execute(
                """
                INSERT INTO runs (
                    run_id,
                    run_type,
                    status,
                    started_at,
                    finished_at,
                    parent_run_id,
                    input_json,
                    output_json,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, NULL, ?, ?, NULL, ?, ?)
                """,
                (
                    run_id,
                    run_type,
                    "running",
                    timestamp,
                    parent_run_id,
                    input_json,
                    timestamp,
                    timestamp,
                ),
            )
        except Exception:
            connection.rollback()
            raise
        else:
            connection.commit()

        log_event(
            artifacts.log_path,
            level="INFO",
            event="run_started",
            message=f"Run {run_id} started.",
            run_id=run_id,
            clock=clock,
        )
        record = get_run_record_from_connection(connection, settings.workspace_dir, run_id)
        return StartedRun(record=record, artifacts=artifacts, config_hash=config_hash)
    finally:
        connection.close()


def complete_run(
    workspace_dir: str | Path,
    run_id: str,
    *,
    output_payload: dict[str, Any] | None = None,
    clock: Clock | None = None,
) -> RunRecord:
    settings = resolve_database_settings(workspace_dir)
    ensure_workspace_database_ready(settings)
    timestamp = timestamp_now(clock)
    output_payload = output_payload or {}
    output_json = canonical_json(output_payload)
    artifacts = run_artifact_paths(settings.workspace_dir, run_id)

    connection = open_database(settings.database_path, enable_wal=settings.wal_enabled)
    try:
        validate_database_migrations(connection)
        record = get_run_record_from_connection(connection, settings.workspace_dir, run_id)
        if record.status != "running":
            raise RunLifecycleError(f"Run {run_id} is not running; current status is {record.status}.")

        artifacts.output_path.write_text(output_json, encoding="utf-8", newline="\n")
        connection.execute("BEGIN")
        try:
            mark_run_completed(connection, run_id, output_json=output_json, finished_at=timestamp)
        except Exception:
            connection.rollback()
            raise
        else:
            connection.commit()

        report = base_process_report(
            run_id=run_id,
            run_type=record.run_type,
            status="completed",
            started_at=record.started_at,
            finished_at=timestamp,
            artifact_dir=record.artifact_dir,
            config_hash=read_config_hash(artifacts),
        )
        write_process_report(artifacts.process_report_path, report)
        log_event(
            artifacts.log_path,
            level="INFO",
            event="run_completed",
            message=f"Run {run_id} completed.",
            run_id=run_id,
            clock=clock,
        )
        return get_run_record_from_connection(connection, settings.workspace_dir, run_id)
    finally:
        connection.close()


def fail_run(
    workspace_dir: str | Path,
    run_id: str,
    *,
    error: str,
    output_payload: dict[str, Any] | None = None,
    clock: Clock | None = None,
) -> RunRecord:
    settings = resolve_database_settings(workspace_dir)
    ensure_workspace_database_ready(settings)
    timestamp = timestamp_now(clock)
    artifacts = run_artifact_paths(settings.workspace_dir, run_id)
    output_json = canonical_json(output_payload) if output_payload is not None else None

    connection = open_database(settings.database_path, enable_wal=settings.wal_enabled)
    try:
        validate_database_migrations(connection)
        record = get_run_record_from_connection(connection, settings.workspace_dir, run_id)
        if record.status != "running":
            raise RunLifecycleError(f"Run {run_id} is not running; current status is {record.status}.")

        if output_json is not None:
            artifacts.output_path.write_text(output_json, encoding="utf-8", newline="\n")
        connection.execute("BEGIN")
        try:
            mark_run_failed(connection, run_id, finished_at=timestamp, output_json=output_json)
        except Exception:
            connection.rollback()
            raise
        else:
            connection.commit()

        report = base_process_report(
            run_id=run_id,
            run_type=record.run_type,
            status="failed",
            started_at=record.started_at,
            finished_at=timestamp,
            artifact_dir=record.artifact_dir,
            config_hash=read_config_hash(artifacts),
            error=error,
        )
        write_process_report(artifacts.process_report_path, report)
        log_event(
            artifacts.log_path,
            level="ERROR",
            event="run_failed",
            message=f"Run {run_id} failed: {error}",
            run_id=run_id,
            clock=clock,
        )
        return get_run_record_from_connection(connection, settings.workspace_dir, run_id)
    finally:
        connection.close()


def get_run_status(workspace_dir: str | Path, run_id: str) -> RunRecord:
    settings = resolve_database_settings(workspace_dir)
    ensure_workspace_database_ready(settings)
    connection = open_database(settings.database_path, enable_wal=settings.wal_enabled)
    try:
        validate_database_migrations(connection)
        return get_run_record_from_connection(connection, settings.workspace_dir, run_id)
    finally:
        connection.close()


def update_run_input(
    connection: sqlite3.Connection,
    *,
    workspace_dir: Path,
    run_id: str,
    input_payload: dict[str, Any],
    updated_at: str,
) -> str:
    input_json = canonical_json(input_payload)
    artifacts = run_artifact_paths(workspace_dir, run_id)
    artifacts.input_path.write_text(input_json, encoding="utf-8", newline="\n")
    connection.execute(
        """
        UPDATE runs
        SET input_json = ?,
            updated_at = ?
        WHERE run_id = ?
        """,
        (input_json, updated_at, run_id),
    )
    return input_json


def mark_run_completed(
    connection: sqlite3.Connection,
    run_id: str,
    *,
    output_json: str,
    finished_at: str,
) -> None:
    connection.execute(
        """
        UPDATE runs
        SET status = ?,
            finished_at = ?,
            output_json = ?,
            updated_at = ?
        WHERE run_id = ?
        """,
        ("completed", finished_at, output_json, finished_at, run_id),
    )


def mark_run_failed(
    connection: sqlite3.Connection,
    run_id: str,
    *,
    finished_at: str,
    output_json: str | None = None,
) -> None:
    connection.execute(
        """
        UPDATE runs
        SET status = ?,
            finished_at = ?,
            output_json = ?,
            updated_at = ?
        WHERE run_id = ?
        """,
        ("failed", finished_at, output_json, finished_at, run_id),
    )


def get_run_record_from_connection(
    connection: sqlite3.Connection,
    workspace_dir: Path,
    run_id: str,
) -> RunRecord:
    row = connection.execute(
        """
        SELECT
            run_id,
            run_type,
            status,
            started_at,
            finished_at,
            parent_run_id,
            input_json,
            output_json,
            created_at,
            updated_at
        FROM runs
        WHERE run_id = ?
        """,
        (run_id,),
    ).fetchone()
    if row is None:
        raise RunLifecycleError(f"Run not found: {run_id}.")
    return run_record_from_row(row, workspace_dir)


def run_record_from_row(row: sqlite3.Row, workspace_dir: Path) -> RunRecord:
    return RunRecord(
        run_id=row["run_id"],
        run_type=row["run_type"],
        status=row["status"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        parent_run_id=row["parent_run_id"],
        input_json=row["input_json"],
        output_json=row["output_json"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        artifact_dir=run_artifact_paths(workspace_dir, row["run_id"]).artifact_dir_relative,
    )


def ensure_workspace_database_ready(settings: DatabaseSettings) -> None:
    if not settings.database_path.is_file():
        raise DatabaseNotReadyError(
            f"Database is not initialized: {settings.database_path}. "
            "Run 'dsl-manager db init <workspace>' before 'dsl-manager run'."
        )


def validate_database_migrations(connection: sqlite3.Connection) -> None:
    schema_row = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'schema_migrations'"
    ).fetchone()
    if schema_row is None:
        raise DatabaseNotReadyError(
            "Database schema is not initialized. "
            "Run 'dsl-manager db init <workspace>' before 'dsl-manager run'."
        )

    rows = connection.execute("SELECT version, name, checksum FROM schema_migrations").fetchall()
    applied = {int(row["version"]): row for row in rows}
    for migration in MIGRATIONS:
        row = applied.get(migration.version)
        if row is None:
            raise DatabaseNotReadyError(
                "Database has pending migrations. "
                "Run 'dsl-manager db init <workspace>' before 'dsl-manager run'."
            )
        if row["name"] != migration.name or row["checksum"] != migration.checksum:
            raise DatabaseNotReadyError(
                f"Database migration {migration.version} does not match this application version."
            )


def validate_parent_run(connection: sqlite3.Connection, parent_run_id: str) -> None:
    row = connection.execute(
        "SELECT run_id FROM runs WHERE run_id = ?",
        (parent_run_id,),
    ).fetchone()
    if row is None:
        raise RunLifecycleError(f"Parent run not found: {parent_run_id}.")


def run_artifact_paths(workspace_dir: str | Path, run_id: str) -> RunArtifactPaths:
    workspace_path = Path(workspace_dir).resolve()
    return RunArtifactPaths(
        workspace_dir=workspace_path,
        artifact_dir=workspace_path / "artifacts" / "runs" / run_id,
    )


def base_process_report(
    *,
    run_id: str,
    run_type: str,
    status: str,
    started_at: str,
    finished_at: str | None,
    artifact_dir: str,
    config_hash: str,
    error: str | None = None,
    workers: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "artifact_dir": artifact_dir,
        "config_hash": config_hash,
        "error": error,
        "finished_at": finished_at,
        "run_id": run_id,
        "run_type": run_type,
        "started_at": started_at,
        "status": status,
        "workers": workers or [],
    }
    return report


def write_process_report(path: str | Path, report: dict[str, Any]) -> None:
    Path(path).write_text(canonical_json(report), encoding="utf-8", newline="\n")


def read_config_hash(artifacts: RunArtifactPaths) -> str:
    if not artifacts.config_hash_path.exists():
        return ""
    return artifacts.config_hash_path.read_text(encoding="utf-8").strip()


def canonical_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def next_id(connection: sqlite3.Connection, table: str, column: str, prefix: str) -> str:
    rows = connection.execute(
        f"SELECT {column} FROM {table} WHERE {column} LIKE ?",
        (f"{prefix}_%",),
    ).fetchall()
    next_number = 1
    for row in rows:
        raw_id = row[column]
        try:
            number = int(str(raw_id).rsplit("_", 1)[1])
        except (IndexError, ValueError):
            continue
        next_number = max(next_number, number + 1)
    return f"{prefix}_{next_number:06d}"


def relative_workspace_path(workspace_dir: str | Path, path: str | Path) -> str:
    return Path(path).resolve().relative_to(Path(workspace_dir).resolve()).as_posix()


def timestamp_now(clock: Clock | None) -> str:
    now = clock() if clock else datetime.now().astimezone()
    return now.isoformat(timespec="seconds")
