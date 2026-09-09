from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from dsl_mngr.core.candidate_validation import (
    CandidateValidationFailure,
    optional_text,
    validate_candidate_payload,
    value_as_text,
)
from dsl_mngr.core.database import (
    DatabaseConfigurationError,
    DatabaseSettings,
    ensure_workspace_initialized,
    open_database,
    resolve_database_settings,
    resolve_workspace_path,
)
from dsl_mngr.core.runs import (
    DatabaseNotReadyError,
    canonical_json,
    next_id,
    relative_workspace_path,
    run_artifact_paths,
    timestamp_now,
    validate_database_migrations,
    write_process_report,
)


Clock = Callable[[], datetime]


class CandidateImportError(RuntimeError):
    """Raised when candidate import cannot be completed."""


class CandidateDatabaseNotReadyError(CandidateImportError):
    """Raised when candidate validation needs a migrated database."""


@dataclass(frozen=True)
class CandidateInputFile:
    path: Path
    relative_path: str


@dataclass(frozen=True)
class CandidateImportResult:
    run_id: str
    batch_id: str
    input_path: str | None
    origin_type: str
    origin_ref: str | None
    total_records: int
    accepted_count: int
    rejected_count: int

    def to_output_payload(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted_count,
            "accepted_count": self.accepted_count,
            "batch_id": self.batch_id,
            "input_path": self.input_path,
            "origin_ref": self.origin_ref,
            "origin_type": self.origin_type,
            "rejected": self.rejected_count,
            "rejected_count": self.rejected_count,
            "run_id": self.run_id,
            "total": self.total_records,
            "total_records": self.total_records,
        }


def prepare_candidate_input_file(
    workspace_dir: str | Path,
    input_path: str | Path,
) -> CandidateInputFile:
    workspace_path = ensure_workspace_initialized(workspace_dir)
    try:
        resolved_path = resolve_workspace_path(workspace_path, input_path)
    except DatabaseConfigurationError as exc:
        raise CandidateImportError(f"Input path escapes the workspace: {input_path}") from exc

    if not resolved_path.is_file():
        raise CandidateImportError(f"Input path is not a file: {resolved_path}")

    return CandidateInputFile(
        path=resolved_path,
        relative_path=relative_workspace_path(workspace_path, resolved_path),
    )


def ensure_candidate_database_ready(workspace_dir: str | Path) -> DatabaseSettings:
    settings = resolve_database_settings(workspace_dir)
    if not settings.database_path.is_file():
        raise CandidateDatabaseNotReadyError(
            f"Database is not initialized: {settings.database_path}. "
            "Run 'dsl-manager db init <workspace>' before 'dsl-manager candidates validate'."
        )

    connection = open_database(settings.database_path, enable_wal=settings.wal_enabled)
    try:
        try:
            validate_database_migrations(connection)
        except DatabaseNotReadyError as exc:
            message = str(exc).replace(
                "dsl-manager run",
                "dsl-manager candidates validate",
            )
            raise CandidateDatabaseNotReadyError(message) from exc
    finally:
        connection.close()
    return settings


def import_candidate_file(
    workspace_dir: str | Path,
    *,
    run_id: str,
    input_path: str | Path,
    origin_type: str = "file_import",
    origin_ref: str | None = None,
    clock: Clock | None = None,
) -> CandidateImportResult:
    settings = ensure_candidate_database_ready(workspace_dir)
    input_file = prepare_candidate_input_file(settings.workspace_dir, input_path)
    timestamp = timestamp_now(clock)

    try:
        lines = input_file.path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise CandidateImportError(f"Input file is not valid UTF-8: {input_file.relative_path}") from exc

    connection = open_database(settings.database_path, enable_wal=settings.wal_enabled)
    try:
        validate_database_migrations(connection)
        batch_id = next_id(connection, "candidate_batches", "batch_id", "CBATCH")
        total_records = 0
        accepted_count = 0
        rejected_count = 0

        stored_input_path = (
            None
            if origin_type in {"human_correction", "deterministic_derivation"}
            else input_file.relative_path
        )
        connection.execute("BEGIN")
        try:
            _insert_batch(
                connection,
                batch_id=batch_id,
                run_id=run_id,
                input_path=stored_input_path,
                origin_type=origin_type,
                origin_ref=origin_ref,
                timestamp=timestamp,
            )

            for line_number, raw_line in enumerate(lines, start=1):
                if not raw_line.strip():
                    continue

                total_records += 1
                payload, failure = _parse_candidate_line(raw_line)
                if failure is None and payload is not None:
                    failure = validate_candidate_payload(connection, payload)

                if failure is None and payload is not None:
                    _insert_candidate_record(
                        connection,
                        batch_id=batch_id,
                        run_id=run_id,
                        line_number=line_number,
                        payload=payload,
                        timestamp=timestamp,
                    )
                    accepted_count += 1
                else:
                    _insert_rejected_candidate(
                        connection,
                        batch_id=batch_id,
                        run_id=run_id,
                        line_number=line_number,
                        raw_line=raw_line,
                        payload=payload,
                        failure=failure or CandidateValidationFailure(
                            reason="schema_validation_failed",
                            message="Candidate payload is invalid.",
                        ),
                        timestamp=timestamp,
                    )
                    rejected_count += 1

            _complete_batch(
                connection,
                batch_id=batch_id,
                total_records=total_records,
                accepted_count=accepted_count,
                rejected_count=rejected_count,
                timestamp=timestamp,
            )
        except Exception:
            connection.rollback()
            raise
        else:
            connection.commit()
    finally:
        connection.close()

    return CandidateImportResult(
        run_id=run_id,
        batch_id=batch_id,
        input_path=stored_input_path,
        origin_type=origin_type,
        origin_ref=origin_ref,
        total_records=total_records,
        accepted_count=accepted_count,
        rejected_count=rejected_count,
    )


def import_candidate_payloads(
    workspace_dir: str | Path,
    *,
    run_id: str,
    payloads: list[dict[str, Any]],
    origin_ref: str,
    clock: Clock | None = None,
) -> CandidateImportResult:
    """Import deterministic in-memory payloads through the common candidate contract."""
    settings = ensure_candidate_database_ready(workspace_dir)
    timestamp = timestamp_now(clock)
    connection = open_database(settings.database_path, enable_wal=settings.wal_enabled)
    try:
        validate_database_migrations(connection)
        batch_id = next_id(connection, "candidate_batches", "batch_id", "CBATCH")
        accepted_count = 0
        rejected_count = 0
        connection.execute("BEGIN")
        try:
            _insert_batch(
                connection,
                batch_id=batch_id,
                run_id=run_id,
                input_path=None,
                origin_type="deterministic_derivation",
                origin_ref=origin_ref,
                timestamp=timestamp,
            )
            for line_number, payload in enumerate(payloads, start=1):
                failure = validate_candidate_payload(connection, payload)
                if failure is None:
                    _insert_candidate_record(
                        connection,
                        batch_id=batch_id,
                        run_id=run_id,
                        line_number=line_number,
                        payload=payload,
                        timestamp=timestamp,
                    )
                    accepted_count += 1
                else:
                    _insert_rejected_candidate(
                        connection,
                        batch_id=batch_id,
                        run_id=run_id,
                        line_number=line_number,
                        raw_line=canonical_json(payload).rstrip("\n"),
                        payload=payload,
                        failure=failure,
                        timestamp=timestamp,
                    )
                    rejected_count += 1
            _complete_batch(
                connection,
                batch_id=batch_id,
                total_records=len(payloads),
                accepted_count=accepted_count,
                rejected_count=rejected_count,
                timestamp=timestamp,
            )
        except Exception:
            connection.rollback()
            raise
        else:
            connection.commit()
    finally:
        connection.close()
    return CandidateImportResult(
        run_id=run_id,
        batch_id=batch_id,
        input_path=None,
        origin_type="deterministic_derivation",
        origin_ref=origin_ref,
        total_records=len(payloads),
        accepted_count=accepted_count,
        rejected_count=rejected_count,
    )


def write_candidate_process_report(
    workspace_dir: str | Path,
    result: CandidateImportResult,
) -> None:
    artifacts = run_artifact_paths(workspace_dir, result.run_id)
    report = json.loads(artifacts.process_report_path.read_text(encoding="utf-8"))
    report.update(result.to_output_payload())
    write_process_report(artifacts.process_report_path, report)


def _parse_candidate_line(raw_line: str) -> tuple[Any | None, CandidateValidationFailure | None]:
    try:
        return json.loads(raw_line), None
    except json.JSONDecodeError as exc:
        return None, CandidateValidationFailure(
            reason="invalid_json",
            message=f"Invalid JSON at column {exc.colno}: {exc.msg}.",
        )


def _insert_batch(
    connection: sqlite3.Connection,
    *,
    batch_id: str,
    run_id: str,
    input_path: str | None,
    origin_type: str,
    origin_ref: str | None,
    timestamp: str,
) -> None:
    connection.execute(
        """
        INSERT INTO candidate_batches (
            batch_id,
            run_id,
            input_path,
            origin_type,
            origin_ref,
            total_records,
            accepted_count,
            rejected_count,
            status,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, 0, 0, 0, ?, ?, ?)
        """,
        (
            batch_id,
            run_id,
            input_path,
            origin_type,
            origin_ref,
            "running",
            timestamp,
            timestamp,
        ),
    )


def _complete_batch(
    connection: sqlite3.Connection,
    *,
    batch_id: str,
    total_records: int,
    accepted_count: int,
    rejected_count: int,
    timestamp: str,
) -> None:
    connection.execute(
        """
        UPDATE candidate_batches
        SET total_records = ?,
            accepted_count = ?,
            rejected_count = ?,
            status = ?,
            updated_at = ?
        WHERE batch_id = ?
        """,
        (
            total_records,
            accepted_count,
            rejected_count,
            "completed",
            timestamp,
            batch_id,
        ),
    )


def _insert_candidate_record(
    connection: sqlite3.Connection,
    *,
    batch_id: str,
    run_id: str,
    line_number: int,
    payload: dict[str, Any],
    timestamp: str,
) -> str:
    record_id = next_id(connection, "candidate_records", "candidate_record_id", "CREC")
    connection.execute(
        """
        INSERT INTO candidate_records (
            candidate_record_id,
            batch_id,
            run_id,
            line_number,
            candidate_id,
            record_type,
            source_revision_id,
            chunk_id,
            fragment_id,
            assertion_type,
            confidence,
            evidence_text,
            payload_json,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record_id,
            batch_id,
            run_id,
            line_number,
            value_as_text(payload.get("candidate_id")),
            value_as_text(payload.get("record_type")),
            value_as_text(payload.get("source_revision_id")),
            optional_text(payload.get("chunk_id")),
            optional_text(payload.get("fragment_id")),
            value_as_text(payload.get("assertion_type")),
            value_as_text(payload.get("confidence")),
            value_as_text(payload.get("evidence_text")),
            canonical_json(payload),
            timestamp,
        ),
    )
    connection.execute(
        """
        INSERT INTO candidate_lineage (
            candidate_record_id,
            root_candidate_record_id,
            parent_candidate_record_id,
            correction_group_id
        )
        VALUES (?, ?, NULL, NULL)
        """,
        (record_id, record_id),
    )
    if payload.get("record_type") == "temporal_interval":
        persist_temporal_candidate_details(connection, record_id, payload)
    return record_id


def persist_temporal_candidate_details(
    connection: sqlite3.Connection,
    candidate_record_id: str,
    payload: dict[str, Any],
) -> None:
    connection.execute(
        """
        INSERT INTO temporal_candidate_details (
            candidate_record_id, target_subject_type, target_subject_id,
            normalized_start, normalized_end, original_precision,
            timezone_status, timezone_value, bounds_semantics,
            derivation_policy_id, derivation_policy_version
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            candidate_record_id,
            value_as_text(payload.get("target_subject_type")),
            value_as_text(payload.get("target_subject_id")),
            optional_text(payload.get("normalized_start")),
            optional_text(payload.get("normalized_end")),
            value_as_text(payload.get("original_precision")),
            value_as_text(payload.get("timezone_status")),
            optional_text(payload.get("timezone_value")),
            value_as_text(payload.get("bounds_semantics")),
            value_as_text(payload.get("derivation_policy_id")),
            value_as_text(payload.get("derivation_policy_version")),
        ),
    )
    for ordinal, evidence_id in enumerate(payload.get("temporal_evidence_ids", []), start=1):
        connection.execute(
            """
            INSERT INTO temporal_candidate_evidence (
                candidate_record_id, temporal_evidence_id, ordinal
            )
            VALUES (?, ?, ?)
            """,
            (candidate_record_id, evidence_id, ordinal),
        )


def _insert_rejected_candidate(
    connection: sqlite3.Connection,
    *,
    batch_id: str,
    run_id: str,
    line_number: int,
    raw_line: str,
    payload: Any | None,
    failure: CandidateValidationFailure,
    timestamp: str,
) -> None:
    rejected_id = next_id(
        connection,
        "rejected_candidates",
        "rejected_candidate_id",
        "RCAND",
    )
    payload_json = canonical_json(payload) if payload is not None else None
    candidate_id = value_as_text(payload.get("candidate_id")) if isinstance(payload, dict) else None
    record_type = value_as_text(payload.get("record_type")) if isinstance(payload, dict) else None
    connection.execute(
        """
        INSERT INTO rejected_candidates (
            rejected_candidate_id,
            batch_id,
            run_id,
            line_number,
            candidate_id,
            record_type,
            reason,
            message,
            raw_line,
            payload_json,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            rejected_id,
            batch_id,
            run_id,
            line_number,
            candidate_id,
            record_type,
            failure.reason,
            failure.message,
            raw_line,
            payload_json,
            timestamp,
        ),
    )
