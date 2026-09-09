from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dsl_mngr.core.database import open_database, resolve_database_settings
from dsl_mngr.core.logging_setup import log_event
from dsl_mngr.core.runs import (
    Clock,
    RunLifecycleError,
    base_process_report,
    canonical_json,
    ensure_workspace_database_ready,
    get_run_record_from_connection,
    mark_run_completed,
    mark_run_failed,
    next_id,
    read_config_hash,
    relative_workspace_path,
    run_artifact_paths,
    timestamp_now,
    update_run_input,
    validate_database_migrations,
    write_process_report,
)


MutationApplier = Callable[[sqlite3.Connection, dict[str, Any]], None]


class WorkerRunnerError(RuntimeError):
    """Raised when a worker cannot be prepared or executed."""


class WorkerOutputError(WorkerRunnerError):
    """Raised when a worker output file is missing or invalid."""


@dataclass(frozen=True)
class WorkerRunResult:
    run_id: str
    worker_run_id: str
    worker_name: str
    status: str
    exit_code: int | None
    duration_ms: int
    output: dict[str, Any] | None
    error: str | None
    report_path: Path


@dataclass(frozen=True)
class _ProcessExecution:
    exit_code: int | None
    stdout: str
    stderr: str
    error: str | None
    resource_limits: dict[str, Any]


def run_worker(
    workspace_dir: str | Path,
    *,
    run_id: str,
    worker_name: str,
    worker_path: str | Path,
    worker_version: str | None = None,
    input_payload: dict[str, Any] | None = None,
    apply_mutations: MutationApplier | None = None,
    clock: Clock | None = None,
    timeout_seconds: float | None = None,
    max_output_bytes: int | None = None,
    memory_limit_bytes: int | None = None,
    accepted_exit_codes: tuple[int, ...] = (0,),
) -> WorkerRunResult:
    settings = resolve_database_settings(workspace_dir)
    ensure_workspace_database_ready(settings)
    worker_script = Path(worker_path).resolve()
    if not worker_script.is_file():
        raise WorkerRunnerError(f"Worker script not found: {worker_script}.")

    artifacts = run_artifact_paths(settings.workspace_dir, run_id)
    connection = open_database(settings.database_path, enable_wal=settings.wal_enabled)
    try:
        validate_database_migrations(connection)
        run_record = get_run_record_from_connection(connection, settings.workspace_dir, run_id)
        if run_record.status != "running":
            raise WorkerRunnerError(
                f"Run {run_id} is not running; current status is {run_record.status}."
            )

        worker_run_id = next_id(connection, "worker_runs", "worker_run_id", "WRK")
        started_at = timestamp_now(clock)
        worker_parameters = input_payload or {}
        worker_input = {
            **worker_parameters,
            "artifact_dir": artifacts.artifact_dir_relative,
            "input": worker_parameters,
            "run_id": run_id,
            "run_type": run_record.run_type,
            "worker_name": worker_name,
            "worker_version": worker_version,
        }

        connection.execute("BEGIN")
        try:
            update_run_input(
                connection,
                workspace_dir=settings.workspace_dir,
                run_id=run_id,
                input_payload=worker_input,
                updated_at=started_at,
            )
            connection.execute(
                """
                INSERT INTO worker_runs (
                    worker_run_id,
                    run_id,
                    worker_name,
                    worker_version,
                    status,
                    input_path,
                    output_path,
                    report_path,
                    log_path,
                    exit_code,
                    duration_ms,
                    started_at,
                    finished_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, NULL)
                """,
                (
                    worker_run_id,
                    run_id,
                    worker_name,
                    worker_version,
                    "running",
                    artifacts.input_path_relative,
                    artifacts.output_path_relative,
                    artifacts.process_report_path_relative,
                    artifacts.log_path_relative,
                    started_at,
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
            event="worker_started",
            message=f"Worker {worker_name} started.",
            run_id=run_id,
            worker=worker_name,
            clock=clock,
        )

        command = [
            sys.executable,
            str(worker_script),
            "--input",
            str(artifacts.input_path),
            "--output",
            str(artifacts.output_path),
        ]
        process_started = time.perf_counter()
        execution = _execute_worker_process(
            command,
            artifact_dir=artifacts.artifact_dir,
            timeout_seconds=timeout_seconds,
            max_output_bytes=max_output_bytes,
            memory_limit_bytes=memory_limit_bytes,
        )
        exit_code = execution.exit_code
        stdout = execution.stdout
        stderr = execution.stderr
        process_error = execution.error
        execution_catalog = execution.resource_limits.get("catalog")
        if isinstance(execution_catalog, dict):
            execution_catalog["artifact_paths"] = [
                artifacts.process_report_path_relative
            ]
            execution_catalog["run_id"] = run_id
            execution_catalog["subject_ids"] = {
                key: worker_parameters[key]
                for key in ("source_id", "source_revision_id")
                if isinstance(worker_parameters.get(key), str)
            }

        duration_ms = max(0, int((time.perf_counter() - process_started) * 1000))
        finished_at = timestamp_now(clock)

        if process_error is not None:
            return _record_worker_failure(
                connection,
                artifacts=artifacts,
                run_id=run_id,
                run_type=run_record.run_type,
                run_started_at=run_record.started_at,
                worker_run_id=worker_run_id,
                worker_name=worker_name,
                worker_version=worker_version,
                started_at=started_at,
                finished_at=finished_at,
                exit_code=exit_code,
                duration_ms=duration_ms,
                stdout=stdout,
                stderr=stderr,
                error=process_error,
                clock=clock,
                resource_limits=execution.resource_limits,
            )

        if exit_code not in accepted_exit_codes:
            return _record_worker_failure(
                connection,
                artifacts=artifacts,
                run_id=run_id,
                run_type=run_record.run_type,
                run_started_at=run_record.started_at,
                worker_run_id=worker_run_id,
                worker_name=worker_name,
                worker_version=worker_version,
                started_at=started_at,
                finished_at=finished_at,
                exit_code=exit_code,
                duration_ms=duration_ms,
                stdout=stdout,
                stderr=stderr,
                error=f"Worker exited with code {exit_code}.",
                clock=clock,
                resource_limits=execution.resource_limits,
            )

        try:
            output_payload = validate_worker_output(artifacts.output_path, run_id, worker_name)
        except WorkerOutputError as exc:
            return _record_worker_failure(
                connection,
                artifacts=artifacts,
                run_id=run_id,
                run_type=run_record.run_type,
                run_started_at=run_record.started_at,
                worker_run_id=worker_run_id,
                worker_name=worker_name,
                worker_version=worker_version,
                started_at=started_at,
                finished_at=finished_at,
                exit_code=exit_code,
                duration_ms=duration_ms,
                stdout=stdout,
                stderr=stderr,
                error=str(exc),
                clock=clock,
                resource_limits=execution.resource_limits,
            )

        output_json = canonical_json(output_payload)
        _atomic_write_text(artifacts.output_path, output_json)

        semantic_status = (
            "partial" if output_payload.get("status") == "partial" else "completed"
        )

        connection.execute("BEGIN")
        try:
            if apply_mutations is not None:
                apply_mutations(connection, output_payload)
            connection.execute(
                """
                UPDATE worker_runs
                SET status = ?,
                    exit_code = ?,
                    duration_ms = ?,
                    finished_at = ?
                WHERE worker_run_id = ?
                """,
                ("completed", exit_code, duration_ms, finished_at, worker_run_id),
            )
            mark_run_completed(
                connection,
                run_id,
                output_json=output_json,
                finished_at=finished_at,
            )
        except Exception as exc:
            connection.rollback()
            return _record_worker_failure(
                connection,
                artifacts=artifacts,
                run_id=run_id,
                run_type=run_record.run_type,
                run_started_at=run_record.started_at,
                worker_run_id=worker_run_id,
                worker_name=worker_name,
                worker_version=worker_version,
                started_at=started_at,
                finished_at=timestamp_now(clock),
                exit_code=exit_code,
                duration_ms=duration_ms,
                stdout=stdout,
                stderr=stderr,
                error=f"Failed to apply worker mutations: {exc}",
                clock=clock,
                resource_limits=execution.resource_limits,
            )
        else:
            connection.commit()

        worker_report = _worker_report(
            worker_run_id=worker_run_id,
            worker_name=worker_name,
            worker_version=worker_version,
            status=semantic_status,
            started_at=started_at,
            finished_at=finished_at,
            exit_code=exit_code,
            duration_ms=duration_ms,
            stdout=stdout,
            stderr=stderr,
            error=None,
            resource_limits=execution.resource_limits,
        )
        write_process_report(
            artifacts.process_report_path,
            base_process_report(
                run_id=run_id,
                run_type=run_record.run_type,
                status=semantic_status,
                started_at=run_record.started_at,
                finished_at=finished_at,
                artifact_dir=artifacts.artifact_dir_relative,
                config_hash=read_config_hash(artifacts),
                workers=[worker_report],
            ),
        )
        log_event(
            artifacts.log_path,
            level="INFO",
            event="worker_completed",
            message=f"Worker {worker_name} completed.",
            run_id=run_id,
            worker=worker_name,
            clock=clock,
        )
        log_event(
            artifacts.log_path,
            level="INFO",
            event="run_completed",
            message=f"Run {run_id} completed.",
            run_id=run_id,
            clock=clock,
        )
        return WorkerRunResult(
            run_id=run_id,
            worker_run_id=worker_run_id,
            worker_name=worker_name,
            status=semantic_status,
            exit_code=exit_code,
            duration_ms=duration_ms,
            output=output_payload,
            error=None,
            report_path=artifacts.process_report_path,
        )
    finally:
        connection.close()


def validate_worker_output(path: str | Path, run_id: str, worker_name: str) -> dict[str, Any]:
    output_path = Path(path)
    if not output_path.is_file():
        raise WorkerOutputError(f"Worker output is missing: {output_path.name}.")
    try:
        payload = json.loads(output_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise WorkerOutputError(f"Worker output is not valid JSON: {exc.msg}.") from exc
    if not isinstance(payload, dict):
        raise WorkerOutputError("Worker output must be a JSON object.")
    if payload.get("run_id") != run_id:
        raise WorkerOutputError(
            f"Worker output run_id is incoherent: expected {run_id}, got {payload.get('run_id')}."
        )
    if payload.get("worker_name") != worker_name:
        raise WorkerOutputError(
            "Worker output worker_name is incoherent: "
            f"expected {worker_name}, got {payload.get('worker_name')}."
        )
    return payload


def _record_worker_failure(
    connection: sqlite3.Connection,
    *,
    artifacts: Any,
    run_id: str,
    run_type: str,
    run_started_at: str,
    worker_run_id: str,
    worker_name: str,
    worker_version: str | None,
    started_at: str,
    finished_at: str,
    exit_code: int | None,
    duration_ms: int,
    stdout: str,
    stderr: str,
    error: str,
    clock: Clock | None,
    resource_limits: dict[str, Any] | None = None,
) -> WorkerRunResult:
    connection.execute("BEGIN")
    try:
        connection.execute(
            """
            UPDATE worker_runs
            SET status = ?,
                exit_code = ?,
                duration_ms = ?,
                finished_at = ?
            WHERE worker_run_id = ?
            """,
            ("failed", exit_code, duration_ms, finished_at, worker_run_id),
        )
        mark_run_failed(connection, run_id, finished_at=finished_at, output_json=None)
    except Exception as exc:
        connection.rollback()
        raise RunLifecycleError(f"Failed to record worker failure for {run_id}: {exc}") from exc
    else:
        connection.commit()

    worker_report = _worker_report(
        worker_run_id=worker_run_id,
        worker_name=worker_name,
        worker_version=worker_version,
        status="failed",
        started_at=started_at,
        finished_at=finished_at,
        exit_code=exit_code,
        duration_ms=duration_ms,
        stdout=stdout,
        stderr=stderr,
        error=error,
        resource_limits=resource_limits,
    )
    write_process_report(
        artifacts.process_report_path,
        base_process_report(
            run_id=run_id,
            run_type=run_type,
            status="failed",
            started_at=run_started_at,
            finished_at=finished_at,
            artifact_dir=artifacts.artifact_dir_relative,
            config_hash=read_config_hash(artifacts),
            error=error,
            workers=[worker_report],
        ),
    )
    log_event(
        artifacts.log_path,
        level="ERROR",
        event="worker_failed",
        message=f"Worker {worker_name} failed: {error}",
        run_id=run_id,
        worker=worker_name,
        clock=clock,
    )
    log_event(
        artifacts.log_path,
        level="ERROR",
        event="run_failed",
        message=f"Run {run_id} failed: {error}",
        run_id=run_id,
        clock=clock,
    )
    return WorkerRunResult(
        run_id=run_id,
        worker_run_id=worker_run_id,
        worker_name=worker_name,
        status="failed",
        exit_code=exit_code,
        duration_ms=duration_ms,
        output=None,
        error=error,
        report_path=artifacts.process_report_path,
    )


def _worker_report(
    *,
    worker_run_id: str,
    worker_name: str,
    worker_version: str | None,
    status: str,
    started_at: str,
    finished_at: str,
    exit_code: int | None,
    duration_ms: int,
    stdout: str,
    stderr: str,
    error: str | None,
    resource_limits: dict[str, Any] | None = None,
) -> dict[str, Any]:
    report = {
        "duration_ms": duration_ms,
        "error": error,
        "exit_code": exit_code,
        "finished_at": finished_at,
        "started_at": started_at,
        "status": status,
        "stderr": _truncate(stderr),
        "stdout": _truncate(stdout),
        "worker_name": worker_name,
        "worker_run_id": worker_run_id,
        "worker_version": worker_version,
    }
    if resource_limits:
        report["resource_limits"] = resource_limits
    return report


def _truncate(value: str, *, limit: int = 4000) -> str:
    if len(value) <= limit:
        return value
    return value[-limit:]


def _coerce_process_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def memory_limit_mode(memory_limit_bytes: int | None) -> str:
    if memory_limit_bytes is None:
        return "not_configured"
    return "monitored" if os.name == "nt" else "hard"


def _execute_worker_process(
    command: list[str],
    *,
    artifact_dir: Path,
    timeout_seconds: float | None,
    max_output_bytes: int | None,
    memory_limit_bytes: int | None,
) -> _ProcessExecution:
    mode = memory_limit_mode(memory_limit_bytes)
    resource_limits: dict[str, Any] = {
        "max_output_bytes": max_output_bytes,
        "memory_limit_bytes": memory_limit_bytes,
        "memory_limit_mode": mode,
        "peak_memory_bytes": None,
        "termination_reason": None,
        "timeout_seconds": timeout_seconds,
    }
    if max_output_bytes is None and memory_limit_bytes is None:
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
            return _ProcessExecution(
                completed.returncode,
                completed.stdout,
                completed.stderr,
                None,
                resource_limits,
            )
        except subprocess.TimeoutExpired as exc:
            resource_limits["termination_reason"] = "timeout"
            resource_limits["catalog"] = _operational_failure_catalog()
            return _ProcessExecution(
                5,
                _coerce_process_text(exc.stdout),
                _coerce_process_text(exc.stderr),
                f"Worker timed out after {timeout_seconds} seconds.",
                resource_limits,
            )

    stdout_path = artifact_dir / ".worker_stdout.tmp"
    stderr_path = artifact_dir / ".worker_stderr.tmp"
    for path in (stdout_path, stderr_path):
        if path.exists():
            path.unlink()
    preexec_fn = _hard_memory_limiter(memory_limit_bytes) if os.name != "nt" else None
    peak_memory = 0
    process: subprocess.Popen[bytes] | None = None
    try:
        with stdout_path.open("wb") as stdout_file, stderr_path.open("wb") as stderr_file:
            process = subprocess.Popen(
                command,
                stdout=stdout_file,
                stderr=stderr_file,
                preexec_fn=preexec_fn,
            )
            started = time.monotonic()
            process_error: str | None = None
            while process.poll() is None:
                elapsed = time.monotonic() - started
                if timeout_seconds is not None and elapsed > timeout_seconds:
                    resource_limits["termination_reason"] = "timeout"
                    process_error = f"Worker timed out after {timeout_seconds} seconds."
                    process.kill()
                    break
                captured_bytes = _file_size(stdout_path) + _file_size(stderr_path)
                if max_output_bytes is not None and captured_bytes > max_output_bytes:
                    resource_limits["termination_reason"] = "output_limit"
                    process_error = (
                        f"Worker process output exceeded {max_output_bytes} bytes."
                    )
                    process.kill()
                    break
                if os.name == "nt" and memory_limit_bytes is not None:
                    current_memory = _windows_process_memory_bytes(process.pid)
                    peak_memory = max(peak_memory, current_memory or 0)
                    if current_memory is not None and current_memory > memory_limit_bytes:
                        resource_limits["termination_reason"] = "memory_limit"
                        process_error = (
                            f"Worker memory exceeded {memory_limit_bytes} bytes "
                            "under monitored+kill enforcement."
                        )
                        process.kill()
                        break
                time.sleep(0.05)
            process.wait()
        resource_limits["peak_memory_bytes"] = peak_memory or None
        if process_error is not None:
            resource_limits["catalog"] = _operational_failure_catalog()
        stdout = _read_process_file(stdout_path, max_output_bytes)
        stderr = _read_process_file(stderr_path, max_output_bytes)
        exit_code = 5 if process_error is not None else process.returncode
        return _ProcessExecution(
            exit_code,
            stdout,
            stderr,
            process_error,
            resource_limits,
        )
    finally:
        if process is not None and process.poll() is None:
            process.kill()
            process.wait()
        for path in (stdout_path, stderr_path):
            if path.exists():
                path.unlink()


def _hard_memory_limiter(memory_limit_bytes: int | None) -> Callable[[], None] | None:
    if memory_limit_bytes is None:
        return None

    def set_limit() -> None:
        import resource

        resource.setrlimit(resource.RLIMIT_AS, (memory_limit_bytes, memory_limit_bytes))

    return set_limit


def _windows_process_memory_bytes(process_id: int) -> int | None:
    try:
        import ctypes
        from ctypes import wintypes

        class ProcessMemoryCounters(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        process_handle = ctypes.windll.kernel32.OpenProcess(0x0410, False, process_id)
        if not process_handle:
            return None
        try:
            counters = ProcessMemoryCounters()
            counters.cb = ctypes.sizeof(counters)
            if not ctypes.windll.psapi.GetProcessMemoryInfo(
                process_handle, ctypes.byref(counters), counters.cb
            ):
                return None
            return int(counters.WorkingSetSize)
        finally:
            ctypes.windll.kernel32.CloseHandle(process_handle)
    except (AttributeError, OSError):
        return None


def _file_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except FileNotFoundError:
        return 0


def _read_process_file(path: Path, limit: int | None) -> str:
    report_limit = min(limit or 65536, 65536)
    with path.open("rb") as stream:
        size = _file_size(path)
        if size > report_limit:
            stream.seek(size - report_limit)
        data = stream.read(report_limit)
    return data.decode("utf-8", errors="replace")


def _operational_failure_catalog() -> dict[str, Any]:
    return {
        "artifact_paths": [],
        "catalog_version": 1,
        "condition": "docling_timeout_or_error",
        "counters": {},
        "exit_code": 5,
        "mutations": "partial_artifacts_discarded",
        "outcome": None,
        "reason": "normalization_operational_failure",
        "retryable": True,
        "run_id": None,
        "severity": "error",
        "status": "failed",
        "subject_ids": {},
    }


def _atomic_write_text(path: Path, text: str) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{time.time_ns()}.tmp")
    try:
        temporary.write_text(text, encoding="utf-8", newline="\n")
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
