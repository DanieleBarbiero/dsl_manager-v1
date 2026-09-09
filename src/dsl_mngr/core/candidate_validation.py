from __future__ import annotations

import re
import sqlite3
from calendar import monthrange
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any


ALLOWED_RECORD_TYPES = {
    "candidate_fact",
    "candidate_relation",
    "candidate_mapping",
    "candidate_conflict",
    "candidate_question",
    "temporal_interval",
}
ALLOWED_ASSERTION_TYPES = {"explicit", "inferred", "ambiguous", "observed"}
ALLOWED_CONFIDENCE = {"high", "medium", "low"}
COMMON_REQUIRED_FIELDS = (
    "candidate_id",
    "source_revision_id",
    "assertion_type",
    "confidence",
    "evidence_text",
)
SPECIFIC_REQUIRED_FIELDS = {
    "candidate_fact": (
        "fact_type",
        "entity_name",
        "property_name",
        "property_value",
    ),
    "candidate_relation": (
        "source_entity",
        "relation_type",
        "target_entity",
    ),
    "candidate_mapping": (
        "domain_entity",
        "technical_object",
        "mapping_type",
    ),
    "candidate_conflict": (
        "conflict_type",
        "subject",
        "left_value",
        "right_value",
    ),
    "candidate_question": (
        "question_type",
        "subject",
        "question_text",
    ),
    "temporal_interval": (
        "target_subject_type",
        "target_subject_id",
        "original_precision",
        "timezone_status",
        "bounds_semantics",
        "derivation_policy_id",
        "derivation_policy_version",
        "temporal_evidence_ids",
    ),
}

TEMPORAL_TARGET_TYPES = {
    "source_revision",
    "source_fragment",
    "candidate_record",
    "fact",
    "relation",
}
TEMPORAL_TIMEZONE_STATUSES = {"explicit", "resolved", "unknown", "incompatible"}
UNRESOLVED_TEMPLATE_PATTERNS = (
    re.compile(r"\$\{[^{}]+\}"),
    re.compile(r"\{\{[^{}]+\}\}"),
    re.compile(r"(?i)(?:^|\b)REPLACE_[A-Z0-9_]+(?:\b|$)"),
    re.compile(r"(?i)^\s*(?:PLACEHOLDER|TBD|TODO)\s*$"),
    re.compile(r"<<[^<>]+>>"),
)


@dataclass(frozen=True)
class CandidateValidationFailure:
    reason: str
    message: str


def validate_candidate_payload(
    connection: sqlite3.Connection,
    payload: Any,
) -> CandidateValidationFailure | None:
    if not isinstance(payload, dict):
        return CandidateValidationFailure(
            reason="schema_validation_failed",
            message="Candidate must be a JSON object.",
        )

    record_type = payload.get("record_type")
    if record_type not in ALLOWED_RECORD_TYPES:
        return CandidateValidationFailure(
            reason="schema_validation_failed",
            message="record_type is missing or unsupported.",
        )

    missing_common = [field for field in COMMON_REQUIRED_FIELDS if _is_missing(payload.get(field))]
    if missing_common:
        return CandidateValidationFailure(
            reason="schema_validation_failed",
            message=f"Missing required field(s): {', '.join(missing_common)}.",
        )

    assertion_type = payload.get("assertion_type")
    if assertion_type not in ALLOWED_ASSERTION_TYPES:
        return CandidateValidationFailure(
            reason="invalid_assertion_type",
            message=f"Invalid assertion_type: {assertion_type}.",
        )

    confidence = payload.get("confidence")
    if confidence not in ALLOWED_CONFIDENCE:
        return CandidateValidationFailure(
            reason="invalid_confidence",
            message=f"Invalid confidence: {confidence}.",
        )

    evidence_text = payload.get("evidence_text")
    if not isinstance(evidence_text, str) or not evidence_text.strip():
        return CandidateValidationFailure(
            reason="schema_validation_failed",
            message="evidence_text must be a non-empty string.",
        )

    missing_specific = [
        field
        for field in SPECIFIC_REQUIRED_FIELDS[record_type]
        if _is_missing(payload.get(field))
    ]
    if missing_specific:
        return CandidateValidationFailure(
            reason="schema_validation_failed",
            message=f"Missing required field(s): {', '.join(missing_specific)}.",
        )

    unresolved_fields = [
        field
        for field in SPECIFIC_REQUIRED_FIELDS[record_type]
        if _contains_unresolved_template(payload.get(field))
    ]
    if unresolved_fields:
        return CandidateValidationFailure(
            reason="unresolved_template_placeholder",
            message=(
                "Unresolved template placeholder in semantic field(s): "
                f"{', '.join(unresolved_fields)}."
            ),
        )

    if record_type == "temporal_interval":
        return _validate_temporal_candidate(connection, payload)

    chunk_id = optional_text(payload.get("chunk_id"))
    fragment_id = optional_text(payload.get("fragment_id"))
    if chunk_id is None and fragment_id is None:
        return CandidateValidationFailure(
            reason="schema_validation_failed",
            message="Either chunk_id or fragment_id is required.",
        )

    source_revision_id = value_as_text(payload.get("source_revision_id"))
    if not _source_revision_exists(connection, source_revision_id):
        return CandidateValidationFailure(
            reason="unknown_source_revision",
            message=f"Unknown source_revision_id: {source_revision_id}.",
        )

    evidence_found = False
    if chunk_id is not None:
        chunk = _load_chunk(connection, chunk_id)
        if chunk is None:
            return CandidateValidationFailure(
                reason="unknown_chunk",
                message=f"Unknown chunk_id: {chunk_id}.",
            )
        if chunk["source_revision_id"] != source_revision_id:
            return CandidateValidationFailure(
                reason="chunk_source_mismatch",
                message=f"Chunk {chunk_id} does not belong to {source_revision_id}.",
            )
        evidence_found = evidence_text in chunk["text"]

    if fragment_id is not None:
        fragment = _load_fragment(connection, fragment_id)
        if fragment is None:
            return CandidateValidationFailure(
                reason="unknown_fragment",
                message=f"Unknown fragment_id: {fragment_id}.",
            )
        if fragment["source_revision_id"] != source_revision_id:
            return CandidateValidationFailure(
                reason="fragment_source_mismatch",
                message=f"Fragment {fragment_id} does not belong to {source_revision_id}.",
            )
        evidence_found = evidence_found or evidence_text in fragment["text"]

    if not evidence_found:
        return CandidateValidationFailure(
            reason="evidence_text_not_found",
            message="evidence_text was not found in the referenced evidence.",
        )

    return None


def _validate_temporal_candidate(
    connection: sqlite3.Connection,
    payload: dict[str, Any],
) -> CandidateValidationFailure | None:
    source_revision_id = value_as_text(payload.get("source_revision_id"))
    if not _source_revision_exists(connection, source_revision_id):
        return CandidateValidationFailure(
            reason="unknown_source_revision",
            message=f"Unknown source_revision_id: {source_revision_id}.",
        )

    target_type = value_as_text(payload.get("target_subject_type"))
    target_id = value_as_text(payload.get("target_subject_id"))
    if target_type not in TEMPORAL_TARGET_TYPES:
        return CandidateValidationFailure(
            reason="temporal_target_invalid",
            message=f"Unsupported temporal target type: {target_type}.",
        )
    if not _temporal_target_exists(connection, target_type, target_id):
        return CandidateValidationFailure(
            reason="temporal_target_not_found",
            message=f"Temporal target not found: {target_type}/{target_id}.",
        )

    evidence_ids = payload.get("temporal_evidence_ids")
    if (
        not isinstance(evidence_ids, list)
        or not evidence_ids
        or not all(isinstance(item, str) and item.strip() for item in evidence_ids)
        or len(evidence_ids) != len(set(evidence_ids))
    ):
        return CandidateValidationFailure(
            reason="temporal_evidence_invalid",
            message="temporal_evidence_ids must be a non-empty list of unique identifiers.",
        )

    evidence_text = value_as_text(payload.get("evidence_text"))
    for evidence_id in evidence_ids:
        row = connection.execute(
            """
            SELECT source_revision_id, target_subject_type, target_subject_id, raw_value
            FROM raw_temporal_evidence
            WHERE temporal_evidence_id = ?
            """,
            (evidence_id,),
        ).fetchone()
        if row is None:
            return CandidateValidationFailure(
                reason="temporal_evidence_not_found",
                message=f"Temporal evidence not found: {evidence_id}.",
            )
        # Temporal candidates may consolidate independent evidence from more than
        # one revision. source_revision_id remains the candidate's origin, while
        # each raw evidence row retains its own exact revision provenance.
        if row["target_subject_type"] != target_type or row["target_subject_id"] != target_id:
            return CandidateValidationFailure(
                reason="temporal_evidence_target_mismatch",
                message=f"Temporal evidence {evidence_id} has a different target.",
            )

    evidence_values = connection.execute(
        f"""
        SELECT raw_value FROM raw_temporal_evidence
        WHERE temporal_evidence_id IN ({','.join('?' for _ in evidence_ids)})
        """,
        tuple(evidence_ids),
    ).fetchall()
    if not any(evidence_text in str(row["raw_value"]) for row in evidence_values):
        return CandidateValidationFailure(
            reason="evidence_text_not_found",
            message="evidence_text was not found in the referenced temporal evidence.",
        )

    start = optional_text(payload.get("normalized_start"))
    end = optional_text(payload.get("normalized_end"))
    if start is None and end is None:
        return CandidateValidationFailure(
            reason="temporal_bounds_missing",
            message="At least one normalized temporal bound is required.",
        )
    start_value, start_format = _parse_temporal_bound(start)
    end_value, end_format = _parse_temporal_bound(end)
    if start is not None and start_value is None:
        return CandidateValidationFailure(
            reason="temporal_bound_invalid",
            message=f"Invalid normalized_start: {start}.",
        )
    if end is not None and end_value is None:
        return CandidateValidationFailure(
            reason="temporal_bound_invalid",
            message=f"Invalid normalized_end: {end}.",
        )
    formats = {value for value in (start_format, end_format) if value is not None}
    if len(formats) > 1:
        return CandidateValidationFailure(
            reason="temporal_timeformat_incompatible",
            message="Temporal bounds must use the same date or dateTime format.",
        )
    if start_value is not None and end_value is not None:
        try:
            start_after_end = start_value > end_value
        except TypeError:
            return CandidateValidationFailure(
                reason="temporal_timeformat_incompatible",
                message="Temporal bounds must use compatible timezone forms.",
            )
        if start_after_end:
            return CandidateValidationFailure(
                reason="temporal_bounds_invalid",
                message="normalized_start must not be after normalized_end.",
            )

    timezone_status = value_as_text(payload.get("timezone_status"))
    timezone_value = optional_text(payload.get("timezone_value"))
    if timezone_status not in TEMPORAL_TIMEZONE_STATUSES:
        return CandidateValidationFailure(
            reason="temporal_timezone_invalid",
            message=f"Unsupported timezone_status: {timezone_status}.",
        )
    if timezone_status in {"explicit", "resolved"} and timezone_value is None:
        return CandidateValidationFailure(
            reason="temporal_timezone_invalid",
            message="A timezone value is required when timezone is explicit or resolved.",
        )
    if timezone_status in {"unknown", "incompatible"} and timezone_value is not None:
        return CandidateValidationFailure(
            reason="temporal_timezone_invalid",
            message="Unknown or incompatible timezone must not carry a timezone value.",
        )
    if formats == {"dateTime"} and timezone_status == "explicit":
        for text in (start, end):
            if text is not None and not _datetime_has_explicit_offset(text):
                return CandidateValidationFailure(
                    reason="temporal_timezone_invalid",
                    message="Explicit dateTime bounds must carry Z or an explicit offset.",
                )

    bounds_semantics = payload.get("bounds_semantics")
    if bounds_semantics not in {"inclusive", "coverage_envelope"}:
        return CandidateValidationFailure(
            reason="temporal_bounds_semantics_invalid",
            message="bounds_semantics must be inclusive or coverage_envelope.",
        )
    original_precision = value_as_text(payload.get("original_precision"))
    if original_precision not in {
        "year",
        "month",
        "day",
        "second",
        "fractional_second",
    }:
        return CandidateValidationFailure(
            reason="temporal_precision_invalid",
            message=f"Unsupported original_precision: {original_precision}.",
        )
    if original_precision in {"year", "month"} and bounds_semantics != "coverage_envelope":
        return CandidateValidationFailure(
            reason="temporal_precision_invalid",
            message="Year and month precision require coverage_envelope bounds.",
        )
    if original_precision == "year" and not _is_year_envelope(start, end):
        return CandidateValidationFailure(
            reason="temporal_precision_invalid",
            message="Year precision requires the exact January-to-December coverage envelope.",
        )
    if original_precision == "month" and not _is_month_envelope(start, end):
        return CandidateValidationFailure(
            reason="temporal_precision_invalid",
            message="Month precision requires the exact calendar-month coverage envelope.",
        )
    return None


def _is_year_envelope(start: str | None, end: str | None) -> bool:
    if start is None or end is None or "T" in start or "T" in end:
        return False
    try:
        start_date = date.fromisoformat(start)
        end_date = date.fromisoformat(end)
    except ValueError:
        return False
    return (
        (start_date.month, start_date.day) == (1, 1)
        and (end_date.month, end_date.day) == (12, 31)
    )


def _is_month_envelope(start: str | None, end: str | None) -> bool:
    if start is None or end is None or "T" in start or "T" in end:
        return False
    try:
        start_date = date.fromisoformat(start)
        end_date = date.fromisoformat(end)
    except ValueError:
        return False
    return (
        start_date.day == 1
        and end_date.day == monthrange(end_date.year, end_date.month)[1]
    )


def _temporal_target_exists(
    connection: sqlite3.Connection,
    target_type: str,
    target_id: str,
) -> bool:
    table_and_column = {
        "source_revision": ("source_revisions", "source_revision_id"),
        "source_fragment": ("source_fragments", "fragment_id"),
        "candidate_record": ("candidate_records", "candidate_record_id"),
        "fact": ("facts", "fact_id"),
        "relation": ("relations", "relation_id"),
    }[target_type]
    table, column = table_and_column
    return bool(
        connection.execute(
            f"SELECT EXISTS(SELECT 1 FROM {table} WHERE {column} = ?)",
            (target_id,),
        ).fetchone()[0]
    )


def _parse_temporal_bound(value: str | None) -> tuple[date | datetime | None, str | None]:
    if value is None:
        return None, None
    if "T" not in value:
        try:
            return date.fromisoformat(value), "date"
        except ValueError:
            return None, None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")), "dateTime"
    except ValueError:
        return None, None


def _datetime_has_explicit_offset(value: str) -> bool:
    if value.endswith("Z"):
        return True
    parsed = datetime.fromisoformat(value)
    return parsed.utcoffset() is not None


def optional_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return str(value)


def value_as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def _source_revision_exists(connection: sqlite3.Connection, source_revision_id: str) -> bool:
    row = connection.execute(
        "SELECT source_revision_id FROM source_revisions WHERE source_revision_id = ?",
        (source_revision_id,),
    ).fetchone()
    return row is not None


def _load_chunk(connection: sqlite3.Connection, chunk_id: str) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT chunk_id, source_revision_id, text
        FROM chunks
        WHERE chunk_id = ?
        """,
        (chunk_id,),
    ).fetchone()


def _load_fragment(connection: sqlite3.Connection, fragment_id: str) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT fragment_id, source_revision_id, text
        FROM source_fragments
        WHERE fragment_id = ?
        """,
        (fragment_id,),
    ).fetchone()


def _is_missing(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _contains_unresolved_template(value: Any) -> bool:
    if isinstance(value, str):
        return any(pattern.search(value) is not None for pattern in UNRESOLVED_TEMPLATE_PATTERNS)
    if isinstance(value, dict):
        return any(_contains_unresolved_template(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_unresolved_template(item) for item in value)
    return False
