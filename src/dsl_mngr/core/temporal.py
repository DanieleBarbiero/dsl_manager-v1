from __future__ import annotations

import json
import re
import sqlite3
import zipfile
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dsl_mngr.core.candidate_import import CandidateImportResult, import_candidate_payloads
from dsl_mngr.core.canonical import canonical_json_v1, canonical_sha256_v1
from dsl_mngr.core.config import load_config
from dsl_mngr.core.database import open_database, resolve_database_settings, resolve_workspace_path
from dsl_mngr.core.ooxml_preflight import (
    ExcelLimits,
    acquire_source_once,
    preflight_ooxml_metadata,
)
from dsl_mngr.core.runs import next_id, timestamp_now, validate_database_migrations


Clock = Callable[[], datetime]
TEMPORAL_EXTRACTION_METHOD = "ooxml_embedded_metadata"
TEMPORAL_EXTRACTION_VERSION = "1"
TEMPORAL_TARGET_TYPES = {
    "source_revision",
    "source_fragment",
    "candidate_record",
    "fact",
    "relation",
}
_OFFSET_SUFFIX = re.compile(r"([+-]\d{2}:\d{2})$")


class TemporalError(RuntimeError):
    def __init__(self, message: str, *, reason: str = "temporal_invalid", exit_code: int = 3) -> None:
        super().__init__(message)
        self.reason = reason
        self.exit_code = exit_code


@dataclass(frozen=True)
class TemporalEvidenceResult:
    source_revision_id: str
    evidence_ids: tuple[str, ...]
    evidence_hashes: tuple[str, ...]
    inserted_count: int
    existing_count: int


@dataclass(frozen=True)
class TemporalCandidateResult:
    batch: CandidateImportResult
    candidate_record_id: str


def extract_ooxml_temporal_evidence(
    workspace_dir: str | Path,
    *,
    source_revision_id: str,
    target_subject_type: str = "source_revision",
    target_subject_id: str | None = None,
    clock: Clock | None = None,
) -> TemporalEvidenceResult:
    """Persist core/app properties and every ZIP timestamp as separate raw evidence."""
    settings = resolve_database_settings(workspace_dir)
    config = load_config(settings.workspace_dir)
    limits = ExcelLimits.from_config(config["excel"])
    target_id = target_subject_id or source_revision_id
    if target_subject_type not in TEMPORAL_TARGET_TYPES:
        raise TemporalError(
            f"Unsupported temporal target type: {target_subject_type}.",
            reason="temporal_target_invalid",
        )

    connection = open_database(settings.database_path, enable_wal=settings.wal_enabled)
    try:
        validate_database_migrations(connection)
        revision = connection.execute(
            """
            SELECT source_revision_id, content_hash, file_path
            FROM source_revisions
            WHERE source_revision_id = ?
            """,
            (source_revision_id,),
        ).fetchone()
        if revision is None:
            raise TemporalError(
                f"Source revision not found: {source_revision_id}.",
                reason="unknown_source_revision",
            )
        _require_target(connection, target_subject_type, target_id)
    finally:
        connection.close()

    source_path = resolve_workspace_path(settings.workspace_dir, revision["file_path"])
    acquired = acquire_source_once(
        source_path,
        expected_hash=str(revision["content_hash"]),
        max_file_bytes=limits.max_file_bytes,
    )
    preflight_ooxml_metadata(
        acquired.cursor(),
        original_name=Path(str(revision["file_path"])).name,
        source_hash=acquired.sha256,
        limits=limits,
    )
    records = _extract_records(
        acquired.data,
        source_revision_id=source_revision_id,
        target_subject_type=target_subject_type,
        target_subject_id=target_id,
        limits=limits,
    )
    return persist_temporal_evidence_records(
        settings.workspace_dir,
        source_revision_id=source_revision_id,
        target_subject_type=target_subject_type,
        target_subject_id=target_id,
        records=records,
        clock=clock,
    )


def persist_temporal_evidence_records(
    workspace_dir: str | Path,
    *,
    source_revision_id: str,
    target_subject_type: str,
    target_subject_id: str,
    records: Iterable[dict[str, Any]],
    clock: Clock | None = None,
) -> TemporalEvidenceResult:
    """Persist bounded, canonical raw evidence without assigning semantic truth."""
    settings = resolve_database_settings(workspace_dir)
    config = load_config(settings.workspace_dir)
    ordered_records = sorted(
        (dict(record) for record in records),
        key=lambda item: (
            str(item.get("source_key", "")),
            str(item.get("raw_value", "")),
            canonical_sha256_v1(item),
        ),
    )
    maximum = int(config["temporal"]["max_evidence_per_source"])
    if len(ordered_records) > maximum:
        raise TemporalError(
            f"Temporal evidence exceeds temporal.max_evidence_per_source ({maximum}).",
            reason="temporal_budget_exceeded",
        )

    timestamp = timestamp_now(clock)
    evidence_ids: list[str] = []
    evidence_hashes: list[str] = []
    inserted = 0
    existing = 0
    connection = open_database(settings.database_path, enable_wal=settings.wal_enabled)
    try:
        validate_database_migrations(connection)
        connection.execute("BEGIN")
        try:
            existing_hashes = {
                str(row["evidence_hash"])
                for row in connection.execute(
                    """
                    SELECT evidence_hash FROM raw_temporal_evidence
                    WHERE source_revision_id = ?
                    """,
                    (source_revision_id,),
                ).fetchall()
            }
            incoming_hashes = {
                canonical_sha256_v1(record) for record in ordered_records
            }
            if len(existing_hashes | incoming_hashes) > maximum:
                raise TemporalError(
                    "Temporal evidence exceeds temporal.max_evidence_per_source "
                    f"({maximum}).",
                    reason="temporal_budget_exceeded",
                )
            _require_target(connection, target_subject_type, target_subject_id)
            for record in ordered_records:
                if (
                    record.get("source_revision_id") != source_revision_id
                    or record.get("target_subject_type") != target_subject_type
                    or record.get("target_subject_id") != target_subject_id
                ):
                    raise TemporalError(
                        "Temporal evidence record does not match its persistence scope.",
                        reason="temporal_evidence_scope_mismatch",
                    )
                evidence_hash = canonical_sha256_v1(record)
                row = connection.execute(
                    """
                    SELECT temporal_evidence_id
                    FROM raw_temporal_evidence
                    WHERE evidence_hash = ?
                    """,
                    (evidence_hash,),
                ).fetchone()
                if row is None:
                    evidence_id = next_id(
                        connection,
                        "raw_temporal_evidence",
                        "temporal_evidence_id",
                        "TEV",
                    )
                    connection.execute(
                        """
                        INSERT INTO raw_temporal_evidence (
                            temporal_evidence_id, target_subject_type, target_subject_id,
                            source_revision_id, source_fragment_id, source_key, source_format,
                            raw_value, extraction_method, extraction_version, precision,
                            timezone_status, timezone_value, initial_reliability,
                            warnings_json, evidence_hash, created_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            evidence_id,
                            record["target_subject_type"],
                            record["target_subject_id"],
                            record["source_revision_id"],
                            record["source_fragment_id"],
                            record["source_key"],
                            record["source_format"],
                            record["raw_value"],
                            record["extraction_method"],
                            record["extraction_version"],
                            record["precision"],
                            record["timezone_status"],
                            record["timezone_value"],
                            record["initial_reliability"],
                            canonical_json_v1(record["warnings"]),
                            evidence_hash,
                            timestamp,
                        ),
                    )
                    inserted += 1
                else:
                    evidence_id = str(row["temporal_evidence_id"])
                    existing += 1
                evidence_ids.append(evidence_id)
                evidence_hashes.append(evidence_hash)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
    finally:
        connection.close()
    return TemporalEvidenceResult(
        source_revision_id=source_revision_id,
        evidence_ids=tuple(evidence_ids),
        evidence_hashes=tuple(evidence_hashes),
        inserted_count=inserted,
        existing_count=existing,
    )


def create_temporal_candidate(
    workspace_dir: str | Path,
    *,
    run_id: str,
    source_revision_id: str,
    target_subject_type: str,
    target_subject_id: str,
    temporal_evidence_ids: Iterable[str],
    normalized_start: str | None,
    normalized_end: str | None,
    original_precision: str,
    timezone_status: str,
    timezone_value: str | None,
    bounds_semantics: str = "inclusive",
    derivation_policy_id: str = "ooxml_metadata_temporal_candidate",
    derivation_policy_version: str = "1",
    assertion_type: str = "ambiguous",
    confidence: str = "low",
    semantic_annotations: dict[str, Any] | None = None,
    clock: Clock | None = None,
) -> TemporalCandidateResult:
    evidence_ids = tuple(dict.fromkeys(str(value) for value in temporal_evidence_ids))
    settings = resolve_database_settings(workspace_dir)
    connection = open_database(settings.database_path, enable_wal=settings.wal_enabled)
    try:
        validate_database_migrations(connection)
        rows = connection.execute(
            f"""
            SELECT temporal_evidence_id, raw_value
            FROM raw_temporal_evidence
            WHERE temporal_evidence_id IN ({','.join('?' for _ in evidence_ids)})
            ORDER BY temporal_evidence_id
            """,
            evidence_ids,
        ).fetchall() if evidence_ids else []
    finally:
        connection.close()
    if len(rows) != len(evidence_ids):
        raise TemporalError(
            "One or more temporal evidence identifiers do not exist.",
            reason="temporal_evidence_not_found",
        )
    evidence_text = str(rows[0]["raw_value"])
    semantic = {
        "bounds_semantics": bounds_semantics,
        "derivation_policy_id": derivation_policy_id,
        "derivation_policy_version": derivation_policy_version,
        "normalized_end": normalized_end,
        "normalized_start": normalized_start,
        "original_precision": original_precision,
        "source_revision_id": source_revision_id,
        "target_subject_id": target_subject_id,
        "target_subject_type": target_subject_type,
        "temporal_evidence_ids": list(evidence_ids),
        "timezone_status": timezone_status,
        "timezone_value": timezone_value,
        **(semantic_annotations or {}),
    }
    payload = {
        **semantic,
        "assertion_type": assertion_type,
        "candidate_id": f"temporal:{canonical_sha256_v1(semantic)}",
        "confidence": confidence,
        "evidence_text": evidence_text,
        "record_type": "temporal_interval",
    }
    batch = import_candidate_payloads(
        settings.workspace_dir,
        run_id=run_id,
        payloads=[payload],
        origin_ref=f"temporal://{canonical_sha256_v1(semantic)}",
        clock=clock,
    )
    if batch.accepted_count != 1:
        connection = open_database(settings.database_path, enable_wal=settings.wal_enabled)
        try:
            rejection = connection.execute(
                """
                SELECT reason, message FROM rejected_candidates
                WHERE batch_id = ? ORDER BY line_number LIMIT 1
                """,
                (batch.batch_id,),
            ).fetchone()
        finally:
            connection.close()
        raise TemporalError(
            str(rejection["message"] if rejection else "Temporal candidate was rejected."),
            reason=str(rejection["reason"] if rejection else "candidate_schema_invalid"),
        )
    connection = open_database(settings.database_path, enable_wal=settings.wal_enabled)
    try:
        row = connection.execute(
            "SELECT candidate_record_id FROM candidate_records WHERE batch_id = ?",
            (batch.batch_id,),
        ).fetchone()
    finally:
        connection.close()
    return TemporalCandidateResult(batch=batch, candidate_record_id=str(row[0]))


def materialize_temporal_interval(
    connection: sqlite3.Connection,
    *,
    candidate_record_id: str,
    decision_id: str,
    timestamp: str,
    max_intervals_per_subject: int = 1000,
) -> str | None:
    detail = connection.execute(
        """
        SELECT tcd.*, cr.record_type
        FROM temporal_candidate_details tcd
        JOIN candidate_records cr ON cr.candidate_record_id = tcd.candidate_record_id
        WHERE tcd.candidate_record_id = ?
        """,
        (candidate_record_id,),
    ).fetchone()
    if detail is None:
        return None
    if detail["record_type"] != "temporal_interval":
        raise TemporalError("Temporal detail belongs to a non-temporal candidate.")
    start, start_format = _normalized_materialized_bound(
        detail["normalized_start"], detail["timezone_status"], detail["timezone_value"]
    )
    end, end_format = _normalized_materialized_bound(
        detail["normalized_end"], detail["timezone_status"], detail["timezone_value"]
    )
    formats = {value for value in (start_format, end_format) if value is not None}
    if len(formats) != 1:
        raise TemporalError(
            "Temporal candidate bounds have no single timeformat.",
            reason="temporal_timeformat_incompatible",
        )
    timeformat = formats.pop()
    if timeformat == "dateTime" and detail["timezone_status"] not in {
        "explicit",
        "resolved",
    }:
        raise TemporalError(
            "Temporal candidate timezone is not resolved.",
            reason="temporal_timezone_unknown",
            exit_code=4,
        )
    existing_same = connection.execute(
        """
        SELECT interval_id FROM temporal_intervals
        WHERE source_candidate_record_id = ?
        """,
        (candidate_record_id,),
    ).fetchone()
    if existing_same is not None:
        _resolve_temporal_conflicts(connection, candidate_record_id, decision_id)
        return str(existing_same["interval_id"])
    effective_count = int(connection.execute(
        """
        SELECT COUNT(*)
        FROM temporal_intervals ti
        JOIN review_subject_heads h
          ON h.subject_type = 'candidate_record'
         AND h.subject_id = ti.source_candidate_record_id
        JOIN review_decisions rd ON rd.decision_id = h.decision_id
        WHERE ti.subject_type = ? AND ti.subject_id = ?
          AND ti.source_candidate_record_id <> ?
          AND rd.outcome = 'confirmed'
        """,
        (detail["target_subject_type"], detail["target_subject_id"], candidate_record_id),
    ).fetchone()[0])
    if effective_count >= max_intervals_per_subject:
        raise TemporalError(
            "The target reached temporal.max_intervals_per_subject "
            f"({max_intervals_per_subject}).",
            reason="temporal_interval_budget_exceeded",
            exit_code=4,
        )
    semantic = {
        "bounds_semantics": detail["bounds_semantics"],
        "end_value": end,
        "original_precision": detail["original_precision"],
        "start_value": start,
        "subject_id": detail["target_subject_id"],
        "subject_type": detail["target_subject_type"],
        "timeformat": timeformat,
        "timezone_value": detail["timezone_value"],
    }
    interval_hash = canonical_sha256_v1(semantic)
    existing_semantic = connection.execute(
        """
        SELECT interval_id FROM temporal_intervals
        WHERE subject_type = ? AND subject_id = ? AND interval_hash = ?
        """,
        (
            detail["target_subject_type"],
            detail["target_subject_id"],
            interval_hash,
        ),
    ).fetchone()
    if existing_semantic is not None:
        _resolve_temporal_conflicts(connection, candidate_record_id, decision_id)
        return str(existing_semantic["interval_id"])
    interval_id = next_id(connection, "temporal_intervals", "interval_id", "TINT")
    connection.execute(
        """
        INSERT INTO temporal_intervals (
            interval_id, subject_type, subject_id, start_value, end_value,
            timeformat, timezone_value, original_precision, bounds_semantics,
            decision_id, source_candidate_record_id, interval_hash, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            interval_id,
            detail["target_subject_type"],
            detail["target_subject_id"],
            start,
            end,
            timeformat,
            detail["timezone_value"],
            detail["original_precision"],
            detail["bounds_semantics"],
            decision_id,
            candidate_record_id,
            interval_hash,
            timestamp,
        ),
    )
    _resolve_temporal_conflicts(connection, candidate_record_id, decision_id)
    return interval_id


def _resolve_temporal_conflicts(
    connection: sqlite3.Connection,
    candidate_record_id: str,
    decision_id: str,
) -> None:
    connection.execute(
        """
        UPDATE temporal_conflicts
        SET status = 'resolved', resolved_by_decision_id = ?
        WHERE status = 'open' AND group_id IN (
            SELECT DISTINCT tegm.group_id
            FROM temporal_candidate_evidence tce
            JOIN temporal_evidence_group_members tegm
              ON tegm.temporal_evidence_id = tce.temporal_evidence_id
            WHERE tce.candidate_record_id = ?
        )
        """,
        (decision_id, candidate_record_id),
    )


def _extract_records(
    data: bytes,
    *,
    source_revision_id: str,
    target_subject_type: str,
    target_subject_id: str,
    limits: ExcelLimits,
) -> list[dict[str, Any]]:
    with zipfile.ZipFile(PathLikeBytes(data)) as package:
        core_values = _xml_properties(package, "docProps/core.xml", limits)
        app_values = _xml_properties(package, "docProps/app.xml", limits)
        records: list[dict[str, Any]] = []
        core_temporal = [
            (key, value) for key, value in core_values if key in {"created", "modified", "lastPrinted"}
        ]
        distinct_core = {_syntactic_temporal_value(value) for _, value in core_temporal}
        distinct_core.discard(None)
        core_assessment = (
            "temporal_values_contradictory" if len(distinct_core) > 1 else "temporal_values_concordant"
        )
        for key, value in core_temporal:
            precision, timezone_status, timezone_value, source_format = _raw_characteristics(value)
            records.append(
                _record(
                    source_revision_id,
                    target_subject_type,
                    target_subject_id,
                    source_key=f"core:{key}",
                    source_format=source_format,
                    raw_value=value,
                    precision=precision,
                    timezone_status=timezone_status,
                    timezone_value=timezone_value,
                    reliability="medium",
                    warnings=[core_assessment, "document_property_not_validity_interval"],
                )
            )
        for key, value in app_values:
            records.append(
                _record(
                    source_revision_id,
                    target_subject_type,
                    target_subject_id,
                    source_key=f"app:{key}",
                    source_format="ooxml_app_property",
                    raw_value=value,
                    precision="unknown",
                    timezone_status="unknown",
                    timezone_value=None,
                    reliability="low",
                    warnings=["application_metadata_not_validity_interval"],
                )
            )
        for info in sorted(package.infolist(), key=lambda item: item.filename):
            if info.is_dir():
                continue
            zip_value = "%04d-%02d-%02dT%02d:%02d:%02d" % info.date_time
            records.append(
                _record(
                    source_revision_id,
                    target_subject_type,
                    target_subject_id,
                    source_key=f"zip:{info.filename}",
                    source_format="zip_dos_datetime",
                    raw_value=zip_value,
                    precision="second",
                    timezone_status="unknown",
                    timezone_value=None,
                    reliability="low",
                    warnings=["zip_timestamp_timezone_unknown", "package_timestamp_not_validity_interval"],
                )
            )
    return sorted(records, key=lambda item: (item["source_key"], item["raw_value"]))


class PathLikeBytes:
    """Seekable in-memory wrapper accepted by zipfile without filesystem extraction."""

    def __init__(self, data: bytes) -> None:
        import io

        self._stream = io.BytesIO(data)

    def read(self, size: int = -1) -> bytes:
        return self._stream.read(size)

    def seek(self, offset: int, whence: int = 0) -> int:
        return self._stream.seek(offset, whence)

    def tell(self) -> int:
        return self._stream.tell()

    def seekable(self) -> bool:
        return True


def _xml_properties(
    package: zipfile.ZipFile,
    part_name: str,
    limits: ExcelLimits,
) -> list[tuple[str, str]]:
    try:
        info = package.getinfo(part_name)
    except KeyError:
        return []
    if info.file_size > limits.max_xml_part_bytes:
        raise TemporalError(
            f"OOXML metadata part exceeds excel.max_xml_part_bytes: {part_name}.",
            reason="temporal_budget_exceeded",
        )
    raw = package.read(part_name)
    try:
        root = ElementTree.fromstring(raw)
    except ElementTree.ParseError as exc:
        raise TemporalError(
            f"OOXML metadata part is malformed: {part_name}.",
            reason="ooxml_security_violation",
        ) from exc
    values: list[tuple[str, str]] = []
    for child in root:
        text = (child.text or "").strip()
        if text:
            values.append((child.tag.rsplit("}", 1)[-1], text))
    return sorted(values)


def _record(
    source_revision_id: str,
    target_subject_type: str,
    target_subject_id: str,
    *,
    source_key: str,
    source_format: str,
    raw_value: str,
    precision: str,
    timezone_status: str,
    timezone_value: str | None,
    reliability: str,
    warnings: list[str],
) -> dict[str, Any]:
    return {
        "extraction_method": TEMPORAL_EXTRACTION_METHOD,
        "extraction_version": TEMPORAL_EXTRACTION_VERSION,
        "initial_reliability": reliability,
        "precision": precision,
        "raw_value": raw_value,
        "source_format": source_format,
        "source_fragment_id": (
            target_subject_id if target_subject_type == "source_fragment" else None
        ),
        "source_key": source_key,
        "source_revision_id": source_revision_id,
        "target_subject_id": target_subject_id,
        "target_subject_type": target_subject_type,
        "timezone_status": timezone_status,
        "timezone_value": timezone_value,
        "warnings": sorted(set(warnings)),
    }


def _raw_characteristics(value: str) -> tuple[str, str, str | None, str]:
    if re.fullmatch(r"\d{4}", value):
        return "year", "unknown", None, "w3cdtf"
    if re.fullmatch(r"\d{4}-\d{2}", value):
        return "month", "unknown", None, "w3cdtf"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return "day", "unknown", None, "w3cdtf"
    precision = "fractional_second" if re.search(r"\.\d+", value) else "second"
    if value.endswith("Z"):
        return precision, "explicit", "UTC", "w3cdtf"
    match = _OFFSET_SUFFIX.search(value)
    if match:
        return precision, "explicit", match.group(1), "w3cdtf"
    return precision, "unknown", None, "w3cdtf"


def _syntactic_temporal_value(value: str) -> str | None:
    text = value.replace("Z", "+00:00")
    try:
        if "T" in text:
            return datetime.fromisoformat(text).isoformat()
        return date.fromisoformat(text).isoformat()
    except ValueError:
        return None


def _normalized_materialized_bound(
    value: str | None,
    timezone_status: str,
    timezone_value: str | None,
) -> tuple[str | None, str | None]:
    if value is None:
        return None, None
    if "T" not in value:
        return date.fromisoformat(value).isoformat(), "date"
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.utcoffset() is None:
        if timezone_status != "resolved" or timezone_value is None:
            raise TemporalError(
                "dateTime bound has no explicit or resolved timezone.",
                reason="temporal_timezone_unknown",
            )
        try:
            parsed = parsed.replace(tzinfo=ZoneInfo(timezone_value))
        except ZoneInfoNotFoundError as exc:
            raise TemporalError(
                f"Unknown resolved timezone: {timezone_value}.",
                reason="temporal_timezone_invalid",
            ) from exc
    return parsed.isoformat(), "dateTime"


def _require_target(connection: sqlite3.Connection, subject_type: str, subject_id: str) -> None:
    table, column = {
        "source_revision": ("source_revisions", "source_revision_id"),
        "source_fragment": ("source_fragments", "fragment_id"),
        "candidate_record": ("candidate_records", "candidate_record_id"),
        "fact": ("facts", "fact_id"),
        "relation": ("relations", "relation_id"),
    }[subject_type]
    if not connection.execute(
        f"SELECT EXISTS(SELECT 1 FROM {table} WHERE {column} = ?)", (subject_id,)
    ).fetchone()[0]:
        raise TemporalError(
            f"Temporal target not found: {subject_type}/{subject_id}.",
            reason="temporal_target_not_found",
        )
