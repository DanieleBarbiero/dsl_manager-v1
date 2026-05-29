from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any


ALLOWED_RECORD_TYPES = {
    "candidate_fact",
    "candidate_relation",
    "candidate_mapping",
    "candidate_conflict",
    "candidate_question",
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
}


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
