from __future__ import annotations

import sqlite3
from pathlib import Path

from dsl_mngr.core.candidate_review import CandidateReviewService
from dsl_mngr.core.canonical import canonical_json_v1, canonical_sha256_v1
from dsl_mngr.core.temporal import create_temporal_candidate
from tests.test_slice_07_dsl_render import _ready_workspace_with_registry


TIMESTAMP = "2026-09-04T10:00:00+00:00"


def ready_workspace_with_interval(
    tmp_path: Path,
    *,
    subject_type: str = "fact",
    subject_id: str = "FACT_000001",
    start: str = "2025-01-01",
    end: str = "2025-12-31",
    precision: str = "day",
    timezone_status: str = "resolved",
    timezone_value: str = "Europe/Rome",
) -> tuple[Path, str]:
    workspace = _ready_workspace_with_registry(tmp_path)
    evidence_id = insert_raw_temporal_evidence(
        workspace,
        evidence_id="TEV_900001",
        target_subject_type=subject_type,
        target_subject_id=subject_id,
        raw_value=start,
    )
    with connect(workspace) as connection:
        run_id = str(
            connection.execute("SELECT run_id FROM runs ORDER BY run_id DESC LIMIT 1").fetchone()[0]
        )
    candidate = create_temporal_candidate(
        workspace,
        run_id=run_id,
        source_revision_id="REV_000001",
        target_subject_type=subject_type,
        target_subject_id=subject_id,
        temporal_evidence_ids=[evidence_id],
        normalized_start=start,
        normalized_end=end,
        original_precision=precision,
        timezone_status=timezone_status,
        timezone_value=timezone_value,
    )
    CandidateReviewService(workspace).confirm(
        candidate.candidate_record_id,
        actor_id="slice26-reviewer",
        idempotency_key=f"slice26:{candidate.candidate_record_id}:confirm",
    )
    return workspace, candidate.candidate_record_id


def insert_raw_temporal_evidence(
    workspace: Path,
    *,
    evidence_id: str,
    target_subject_type: str,
    target_subject_id: str,
    raw_value: str,
    timezone_status: str = "unknown",
    timezone_value: str | None = None,
) -> str:
    semantic = {
        "extraction_method": "test_explicit_evidence",
        "extraction_version": "1",
        "initial_reliability": "medium",
        "precision": (
            "second"
            if "T" in raw_value
            else "year"
            if len(raw_value) == 4
            else "month"
            if len(raw_value) == 7
            else "day"
        ),
        "raw_value": raw_value,
        "source_format": "w3cdtf",
        "source_fragment_id": None,
        "source_key": f"test:{evidence_id}",
        "source_revision_id": "REV_000001",
        "target_subject_id": target_subject_id,
        "target_subject_type": target_subject_type,
        "timezone_status": timezone_status,
        "timezone_value": timezone_value,
        "warnings": ["document_property_not_validity_interval"],
    }
    with connect(workspace) as connection:
        connection.execute(
            """
            INSERT INTO raw_temporal_evidence (
                temporal_evidence_id, target_subject_type, target_subject_id,
                source_revision_id, source_fragment_id, source_key, source_format,
                raw_value, extraction_method, extraction_version, precision,
                timezone_status, timezone_value, initial_reliability,
                warnings_json, evidence_hash, created_at
            )
            VALUES (?, ?, ?, 'REV_000001', NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                evidence_id,
                target_subject_type,
                target_subject_id,
                semantic["source_key"],
                semantic["source_format"],
                raw_value,
                semantic["extraction_method"],
                semantic["extraction_version"],
                semantic["precision"],
                timezone_status,
                timezone_value,
                semantic["initial_reliability"],
                canonical_json_v1(semantic["warnings"]),
                canonical_sha256_v1(semantic),
                TIMESTAMP,
            ),
        )
    return evidence_id


def connect(workspace: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(workspace / "workspace.sqlite")
    connection.row_factory = sqlite3.Row
    return connection
