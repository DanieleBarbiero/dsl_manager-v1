from __future__ import annotations

import json

import pytest

from dsl_mngr.core.candidate_review import CandidateReviewError, CandidateReviewService
from dsl_mngr.core.config import dump_simple_yaml, load_config
from dsl_mngr.core.temporal import (
    TemporalError,
    create_temporal_candidate,
    persist_temporal_evidence_records,
)
from tests.slice_26_test_support import (
    connect,
    insert_raw_temporal_evidence,
    ready_workspace_with_interval,
)
from tests.slice_27_test_support import FIXED_TIME, registered_workspace
from tests.test_slice_07_dsl_render import _ready_workspace_with_registry


@pytest.mark.parametrize(
    ("raw", "start", "end", "precision", "timezone_status", "timezone_value", "semantics"),
    (
        ("2024", "2024-01-01", "2024-12-31", "year", "unknown", None, "coverage_envelope"),
        ("2024-02", "2024-02-01", "2024-02-29", "month", "unknown", None, "coverage_envelope"),
        ("2024-02-03", "2024-02-03", "2024-02-03", "day", "unknown", None, "inclusive"),
        (
            "2024-02-03T10:11:12Z",
            "2024-02-03T10:11:12Z",
            "2024-02-03T10:11:12Z",
            "second",
            "explicit",
            "UTC",
            "inclusive",
        ),
        (
            "2024-02-03T10:11:12+01:00",
            "2024-02-03T10:11:12+01:00",
            "2024-02-03T10:11:12+01:00",
            "second",
            "explicit",
            "+01:00",
            "inclusive",
        ),
    ),
)
def test_slice_27_precision_timezone(
    tmp_path,
    raw,
    start,
    end,
    precision,
    timezone_status,
    timezone_value,
    semantics,
):
    workspace = _ready_workspace_with_registry(tmp_path)
    evidence_id = insert_raw_temporal_evidence(
        workspace,
        evidence_id="TEV_970001",
        target_subject_type="fact",
        target_subject_id="FACT_000001",
        raw_value=raw,
        timezone_status=timezone_status,
        timezone_value=timezone_value,
    )
    with connect(workspace) as connection:
        run_id = str(connection.execute("SELECT run_id FROM runs ORDER BY run_id DESC LIMIT 1").fetchone()[0])
    candidate = create_temporal_candidate(
        workspace,
        run_id=run_id,
        source_revision_id="REV_000001",
        target_subject_type="fact",
        target_subject_id="FACT_000001",
        temporal_evidence_ids=[evidence_id],
        normalized_start=start,
        normalized_end=end,
        original_precision=precision,
        timezone_status=timezone_status,
        timezone_value=timezone_value,
        bounds_semantics=semantics,
    )
    CandidateReviewService(workspace).confirm(candidate.candidate_record_id, actor_id="reviewer")
    with connect(workspace) as connection:
        interval = connection.execute(
            "SELECT * FROM temporal_intervals WHERE source_candidate_record_id = ?",
            (candidate.candidate_record_id,),
        ).fetchone()
    assert interval["original_precision"] == precision
    assert interval["bounds_semantics"] == semantics
    assert interval["timeformat"] == ("dateTime" if "T" in start else "date")
    if "T" not in start:
        assert interval["start_value"] == start
        assert interval["end_value"] == end


def test_slice_27_unknown_datetime_stays_pending_and_is_not_truncated(tmp_path):
    workspace = _ready_workspace_with_registry(tmp_path)
    evidence_id = insert_raw_temporal_evidence(
        workspace,
        evidence_id="TEV_970002",
        target_subject_type="relation",
        target_subject_id="REL_000001",
        raw_value="2024-02-03T10:11:12",
    )
    with connect(workspace) as connection:
        run_id = str(connection.execute("SELECT run_id FROM runs ORDER BY run_id DESC LIMIT 1").fetchone()[0])
    candidate = create_temporal_candidate(
        workspace,
        run_id=run_id,
        source_revision_id="REV_000001",
        target_subject_type="relation",
        target_subject_id="REL_000001",
        temporal_evidence_ids=[evidence_id],
        normalized_start="2024-02-03T10:11:12",
        normalized_end="2024-02-03T11:11:12",
        original_precision="second",
        timezone_status="unknown",
        timezone_value=None,
    )
    with pytest.raises(CandidateReviewError) as caught:
        CandidateReviewService(workspace).confirm(candidate.candidate_record_id, actor_id="reviewer")
    assert caught.value.reason == "temporal_timezone_unknown"
    with connect(workspace) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM temporal_intervals WHERE source_candidate_record_id = ?",
            (candidate.candidate_record_id,),
        ).fetchone()[0] == 0


def test_slice_27_budget_at_and_over_evidence_and_intervals(tmp_path):
    workspace, _, revisions = registered_workspace(
        tmp_path / "evidence",
        {"budget.txt": "valid_from: 2024-01-01\n"},
    )
    config = load_config(workspace)
    config["temporal"]["max_evidence_per_source"] = 2
    (workspace / "configs" / "project.yaml").write_text(
        dump_simple_yaml(config), encoding="utf-8", newline="\n"
    )
    revision_id = revisions["budget.txt"]
    records = [_record(revision_id, f"2024-01-0{index}", index) for index in (1, 2)]
    at = persist_temporal_evidence_records(
        workspace,
        source_revision_id=revision_id,
        target_subject_type="source_revision",
        target_subject_id=revision_id,
        records=records,
    )
    assert at.inserted_count == 2
    with pytest.raises(TemporalError) as caught:
        persist_temporal_evidence_records(
            workspace,
            source_revision_id=revision_id,
            target_subject_type="source_revision",
            target_subject_id=revision_id,
            records=[*records, _record(revision_id, "2024-01-03", 3)],
        )
    assert caught.value.reason == "temporal_budget_exceeded"

    bounded, _ = ready_workspace_with_interval(tmp_path / "intervals")
    config = load_config(bounded)
    config["temporal"]["max_intervals_per_subject"] = 1
    (bounded / "configs" / "project.yaml").write_text(
        dump_simple_yaml(config), encoding="utf-8", newline="\n"
    )
    evidence_id = insert_raw_temporal_evidence(
        bounded,
        evidence_id="TEV_970003",
        target_subject_type="fact",
        target_subject_id="FACT_000001",
        raw_value="2026-01-01",
    )
    with connect(bounded) as connection:
        run_id = str(connection.execute("SELECT run_id FROM runs ORDER BY run_id DESC LIMIT 1").fetchone()[0])
    candidate = create_temporal_candidate(
        bounded,
        run_id=run_id,
        source_revision_id="REV_000001",
        target_subject_type="fact",
        target_subject_id="FACT_000001",
        temporal_evidence_ids=[evidence_id],
        normalized_start="2026-01-01",
        normalized_end="2026-12-31",
        original_precision="day",
        timezone_status="unknown",
        timezone_value=None,
    )
    with pytest.raises(CandidateReviewError) as caught:
        CandidateReviewService(bounded).confirm(candidate.candidate_record_id, actor_id="reviewer")
    assert caught.value.reason == "temporal_interval_budget_exceeded"


def _record(revision_id: str, value: str, ordinal: int) -> dict[str, object]:
    return {
        "extraction_method": "test",
        "extraction_version": "1",
        "initial_reliability": "medium",
        "precision": "day",
        "raw_value": value,
        "source_format": "test",
        "source_fragment_id": None,
        "source_key": f"test:{ordinal}",
        "source_revision_id": revision_id,
        "target_subject_id": revision_id,
        "target_subject_type": "source_revision",
        "timezone_status": "unknown",
        "timezone_value": None,
        "warnings": ["test"],
    }
