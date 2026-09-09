from __future__ import annotations

import sqlite3

import pytest

from dsl_mngr.core.batch_consolidation import BatchConsolidationError, consolidate_batch
from dsl_mngr.core.candidate_review import CandidateReviewService
from dsl_mngr.core.reconciliation import reconcile_required
from dsl_mngr.core.temporal import create_temporal_candidate
from dsl_mngr.core.temporal_consolidation import (
    NormalizedTemporalInterval,
    aggregate_temporal_intervals,
    explicit_precedence_candidate_payloads,
    intersect_temporal_intervals,
    propagate_temporal_intervals,
)
from tests.slice_26_test_support import (
    connect,
    insert_raw_temporal_evidence,
    ready_workspace_with_interval,
)
from tests.slice_27_test_support import registered_workspace


def test_slice_27_explicit_propagation_intersection_aggregation_and_conflict(tmp_path):
    workspace, _ = ready_workspace_with_interval(tmp_path)
    run_id = _latest_run_id(workspace)
    evidence_id = insert_raw_temporal_evidence(
        workspace,
        evidence_id="TEV_972001",
        target_subject_type="relation",
        target_subject_id="REL_000001",
        raw_value="2025-06-01",
    )
    relation_candidate = create_temporal_candidate(
        workspace,
        run_id=run_id,
        source_revision_id="REV_000001",
        target_subject_type="relation",
        target_subject_id="REL_000001",
        temporal_evidence_ids=[evidence_id],
        normalized_start="2025-06-01",
        normalized_end="2025-07-31",
        original_precision="day",
        timezone_status="resolved",
        timezone_value="Europe/Rome",
    )
    CandidateReviewService(workspace).confirm(
        relation_candidate.candidate_record_id,
        actor_id="reviewer",
    )
    with connect(workspace) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM temporal_intervals WHERE subject_type = 'candidate_record' AND subject_id = 'CREC_000001'"
        ).fetchone()[0] == 0

    sources = (("fact", "FACT_000001"), ("relation", "REL_000001"))
    intersection = propagate_temporal_intervals(
        workspace,
        run_id=run_id,
        source_revision_id="REV_000001",
        target_subject_type="candidate_record",
        target_subject_id="CREC_000001",
        source_subjects=sources,
        policy="intersection",
    )
    assert len(intersection.candidate_record_ids) == 1
    CandidateReviewService(workspace).confirm(
        intersection.candidate_record_ids[0], actor_id="reviewer"
    )

    aggregation = propagate_temporal_intervals(
        workspace,
        run_id=run_id,
        source_revision_id="REV_000001",
        target_subject_type="candidate_record",
        target_subject_id="CREC_000002",
        source_subjects=sources,
        policy="aggregation",
    )
    assert len(aggregation.candidate_record_ids) == 2
    for candidate_id in aggregation.candidate_record_ids:
        CandidateReviewService(workspace).confirm(candidate_id, actor_id="reviewer")

    copied = propagate_temporal_intervals(
        workspace,
        run_id=run_id,
        source_revision_id="REV_000001",
        target_subject_type="candidate_record",
        target_subject_id="CREC_000003",
        source_subjects=(("relation", "REL_000001"),),
        policy="explicit_copy",
    )
    assert len(copied.candidate_record_ids) == 1

    conflict = propagate_temporal_intervals(
        workspace,
        run_id=run_id,
        source_revision_id="REV_000001",
        target_subject_type="fact",
        target_subject_id="FACT_000002",
        source_subjects=sources,
        policy="conflict",
    )
    assert conflict.candidate_record_ids == ()
    assert conflict.conflict_id is not None
    with connect(workspace) as connection:
        intervals = connection.execute(
            """
            SELECT subject_id, start_value, end_value FROM temporal_intervals
            WHERE subject_type = 'candidate_record'
            ORDER BY subject_id, start_value
            """
        ).fetchall()
        assert connection.execute(
            "SELECT status FROM temporal_conflicts WHERE conflict_id = ?",
            (conflict.conflict_id,),
        ).fetchone()[0] == "open"
    assert [(row["subject_id"], row["start_value"], row["end_value"]) for row in intervals] == [
        ("CREC_000001", "2025-06-01", "2025-07-31"),
        ("CREC_000002", "2025-01-01", "2025-12-31"),
        ("CREC_000002", "2025-06-01", "2025-07-31"),
    ]


def test_slice_27_interval_operations_preserve_disjoint_ranges():
    first = NormalizedTemporalInterval(
        "2024-01-01", "2024-02-01", "day", "unknown", None, "inclusive"
    )
    second = NormalizedTemporalInterval(
        "2024-03-01", "2024-04-01", "day", "unknown", None, "inclusive"
    )
    assert intersect_temporal_intervals((first, second)) is None
    assert aggregate_temporal_intervals((second, first, first)) == [first, second]


def test_slice_27_temporal_reconcile_closes_without_deleting_history(tmp_path):
    workspace, candidate_id = ready_workspace_with_interval(tmp_path)
    run_id = _latest_run_id(workspace)
    service = CandidateReviewService(workspace)
    with connect(workspace) as connection:
        head = str(
            connection.execute(
                "SELECT decision_id FROM review_subject_heads WHERE subject_id = ?",
                (candidate_id,),
            ).fetchone()[0]
        )
    rejected = service.reject(
        candidate_id,
        actor_id="reviewer",
        reason="withdrawn temporal assertion",
        expected_head_decision_id=head,
    )
    assert rejected.reconciliation_id is not None
    result = reconcile_required(workspace, run_id=run_id)
    assert result.closed == 1
    assert result.pending == 0
    with connect(workspace) as connection:
        assert connection.execute("SELECT COUNT(*) FROM temporal_intervals").fetchone()[0] == 1
        assert connection.execute(
            "SELECT status FROM reconciliation_required WHERE reconciliation_id = ?",
            (rejected.reconciliation_id,),
        ).fetchone()[0] == "closed"


def test_slice_27_batch_crash_retry_and_inverse_order_converge(tmp_path):
    clean, _, _ = registered_workspace(
        tmp_path / "clean",
        {
            "a.sql": "-- valid_from: 2024-01-01\nCREATE TABLE a(id INT);\n",
            "b.sql": "-- valid_from: 2025-01-01\nCREATE TABLE b(id INT);\n",
        },
    )
    clean_result = consolidate_batch(clean)
    clean_state = _temporal_state(clean)
    assert clean_result["counters"]["review_pending"] >= 2
    assert clean_result["counters"]["temporal_candidates"] == 4

    retry, _, _ = registered_workspace(
        tmp_path / "retry",
        {
            "b.sql": "-- valid_from: 2025-01-01\nCREATE TABLE b(id INT);\n",
            "a.sql": "-- valid_from: 2024-01-01\nCREATE TABLE a(id INT);\n",
        },
    )

    def crash(point: str) -> None:
        if point == "after_derive":
            raise RuntimeError("crash after temporal derive")

    with pytest.raises(BatchConsolidationError, match="crash after temporal derive"):
        consolidate_batch(retry, fault_hook=crash)
    with connect(retry) as connection:
        failed_run_id = str(
            connection.execute(
                "SELECT run_id FROM runs WHERE run_type = 'batch' AND parent_run_id IS NULL ORDER BY run_id DESC LIMIT 1"
            ).fetchone()[0]
        )
        candidates_before = connection.execute("SELECT COUNT(*) FROM candidate_records").fetchone()[0]
    resumed = consolidate_batch(retry, resume_run_id=failed_run_id)
    with connect(retry) as connection:
        assert connection.execute("SELECT COUNT(*) FROM candidate_records").fetchone()[0] == candidates_before
    assert resumed["counters"] == clean_result["counters"]
    assert _temporal_state(retry) == clean_state


def test_slice_27_batch_temporal_review_merge_and_reconcile(tmp_path):
    workspace, _, _ = registered_workspace(
        tmp_path,
        {"policy.sql": "-- valid_from: 2029-01-01\nCREATE TABLE policy(id INT);\n"},
    )
    blocked = consolidate_batch(workspace, reconcile=True)
    assert blocked["status"] == "blocked"
    with connect(workspace) as connection:
        temporal_ids = [
            str(row[0])
            for row in connection.execute(
                "SELECT candidate_record_id FROM candidate_records WHERE record_type = 'temporal_interval' ORDER BY candidate_record_id"
            )
        ]
    assert temporal_ids
    service = CandidateReviewService(workspace)
    for candidate_id in temporal_ids:
        service.confirm(candidate_id, actor_id="reviewer")

    resumed = consolidate_batch(
        workspace,
        reconcile=True,
        resume_run_id=blocked["run_id"],
    )
    assert resumed["exit_code"] == 0
    assert resumed["counters"]["merged_candidates"] >= len(temporal_ids)
    assert next(
        phase for phase in resumed["phases"] if phase["name"] == "reconcile"
    )["status"] == "completed"
    with connect(workspace) as connection:
        assert connection.execute("SELECT COUNT(*) FROM temporal_intervals").fetchone()[0] == len(
            temporal_ids
        )


def _temporal_state(workspace):
    with connect(workspace) as connection:
        return {
            "evidence": [
                row[0]
                for row in connection.execute(
                    "SELECT evidence_hash FROM raw_temporal_evidence ORDER BY evidence_hash"
                )
            ],
            "groups": [
                row[0]
                for row in connection.execute(
                    "SELECT group_hash FROM temporal_evidence_groups ORDER BY group_hash"
                )
            ],
            "candidate_payloads": [
                row[0]
                for row in connection.execute(
                    "SELECT candidate_id FROM candidate_records WHERE record_type = 'temporal_interval' ORDER BY candidate_id"
                )
            ],
            "intervals": [
                row[0]
                for row in connection.execute(
                    "SELECT interval_hash FROM temporal_intervals ORDER BY interval_hash"
                )
            ],
        }


def _latest_run_id(workspace):
    with connect(workspace) as connection:
        return str(connection.execute("SELECT run_id FROM runs ORDER BY run_id DESC LIMIT 1").fetchone()[0])
