from __future__ import annotations

import json
from pathlib import Path

import pytest

from dsl_mngr.core.candidate_review import CandidateReviewService
from dsl_mngr.core.dsl_diff import DslDiffError, diff_dsl_snapshots
from dsl_mngr.core.dsl_renderer import DslRenderError, render_dsl_snapshot
from dsl_mngr.core.reconciliation import ReconciliationRequiredError
from dsl_mngr.core.temporal import create_temporal_candidate
from tests.slice_26_test_support import (
    connect,
    insert_raw_temporal_evidence,
    ready_workspace_with_interval,
)
from tests.test_slice_07_dsl_render import _ready_workspace_with_registry


EXPECTED = Path(__file__).parent / "expected" / "expected_slice_26_dsl_v2.json"


def test_slice_26_dsl_v2_roundtrip(tmp_path):
    workspace, _ = ready_workspace_with_interval(tmp_path)
    run_id = _latest_run_id(workspace)
    first = render_dsl_snapshot(workspace, run_id=run_id, schema_version="2")
    second = render_dsl_snapshot(workspace, run_id=run_id, schema_version="2")
    first_bytes = (workspace / first.json_path).read_bytes()
    first_content = json.loads(first_bytes)
    assert first.dsl_hash == second.dsl_hash
    assert first.registry_hash == second.registry_hash
    assert (workspace / second.json_path).read_bytes() == first_bytes
    assert first_content == json.loads(EXPECTED.read_text(encoding="utf-8"))
    assert first_content["metadata"]["schema_version"] == "2"
    assert first_content["metadata"]["temporal"] == {
        "base": "day",
        "gexf_timeformat": "date",
        "representation": "interval",
        "timezone": "Europe/Rome",
    }
    facts = [fact for entity in first_content["entities"] for fact in entity["facts"]]
    assert all("intervals" in fact for fact in facts)
    assert next(fact for fact in facts if fact["fact_id"] == "FACT_000001")["intervals"] == [
        {
            "bounds_semantics": "inclusive",
            "end": "2025-12-31",
            "original_precision": "day",
            "start": "2025-01-01",
            "timeformat": "date",
            "timezone": "Europe/Rome",
        }
    ]
    assert all(
        fact["intervals"] == [] for fact in facts if fact["fact_id"] != "FACT_000001"
    )
    assert all(relation["intervals"] == [] for relation in first_content["relations"])
    temporal_trace = first_content["traceability"]["temporal"]["fact:FACT_000001"]
    assert temporal_trace == [
        {
            "candidate_record_id": "CREC_000005",
            "chunk_id": None,
            "evidence_text_hash": temporal_trace[0]["evidence_text_hash"],
            "file_path": "corpus/active/manuale_clienti.txt",
            "fragment_id": None,
            "source_id": "SRC_000001",
            "source_revision_id": "REV_000001",
            "temporal_evidence_id": "TEV_900001",
        }
    ]
    insert_raw_temporal_evidence(
        workspace,
        evidence_id="TEV_900099",
        target_subject_type="fact",
        target_subject_id="FACT_000001",
        raw_value="2024-01-01",
    )
    after_raw_only = render_dsl_snapshot(
        workspace,
        run_id=run_id,
        schema_version="2",
    )
    assert after_raw_only.dsl_hash == first.dsl_hash
    assert after_raw_only.registry_hash == first.registry_hash
    assert (workspace / after_raw_only.json_path).read_bytes() == first_bytes
    with connect(workspace) as connection:
        row = connection.execute(
            "SELECT dsl_hash, registry_hash, content_json FROM dsl_snapshots WHERE snapshot_id = ?",
            (first.snapshot_id,),
        ).fetchone()
    assert row["dsl_hash"] == first.dsl_hash
    assert row["registry_hash"] == first.registry_hash
    assert row["content_json"].encode("utf-8") == first_bytes


def test_slice_26_historical_snapshot_immutable(tmp_path):
    workspace = _ready_workspace_with_registry(tmp_path)
    run_id = _latest_run_id(workspace)
    before = render_dsl_snapshot(workspace, run_id=run_id)
    before_bytes = (workspace / before.json_path).read_bytes()
    before_hash = before.dsl_hash
    _add_fact_interval(workspace, run_id)
    after = render_dsl_snapshot(workspace, run_id=run_id)
    assert after.dsl_hash == before_hash
    assert (workspace / after.json_path).read_bytes() == before_bytes
    assert (workspace / before.json_path).read_bytes() == before_bytes
    assert json.loads(before_bytes)["metadata"]["schema_version"] == "1"
    with connect(workspace) as connection:
        persisted = connection.execute(
            "SELECT dsl_hash, content_json FROM dsl_snapshots WHERE snapshot_id = ?",
            (before.snapshot_id,),
        ).fetchone()
    assert persisted["dsl_hash"] == before_hash
    assert persisted["content_json"].encode("utf-8") == before_bytes


def test_slice_26_diff_same_schema_only(tmp_path):
    workspace, _ = ready_workspace_with_interval(tmp_path)
    run_id = _latest_run_id(workspace)
    v1 = render_dsl_snapshot(workspace, run_id=run_id, schema_version="1")
    v2a = render_dsl_snapshot(workspace, run_id=run_id, schema_version="2")
    v2b = render_dsl_snapshot(workspace, run_id=run_id, schema_version="2")
    same = diff_dsl_snapshots(
        workspace,
        run_id=run_id,
        from_snapshot_id=v2a.snapshot_id,
        to_snapshot_id=v2b.snapshot_id,
    )
    assert same.total_changes == 0
    with pytest.raises(DslDiffError, match="Cross-schema"):
        diff_dsl_snapshots(
            workspace,
            run_id=run_id,
            from_snapshot_id=v1.snapshot_id,
            to_snapshot_id=v2a.snapshot_id,
        )


def test_slice_26_diff_detects_interval_and_reports_temporal_evidence(tmp_path):
    workspace = _ready_workspace_with_registry(tmp_path)
    run_id = _latest_run_id(workspace)
    before = render_dsl_snapshot(workspace, run_id=run_id, schema_version="2")
    _add_fact_interval(workspace, run_id)
    after = render_dsl_snapshot(workspace, run_id=run_id, schema_version="2")

    result = diff_dsl_snapshots(
        workspace,
        run_id=run_id,
        from_snapshot_id=before.snapshot_id,
        to_snapshot_id=after.snapshot_id,
    )
    payload = json.loads((workspace / result.json_path).read_text(encoding="utf-8"))
    assert result.total_changes == 1
    assert payload["changes"][0]["change_type"] == "modified_fact"
    temporal_causes = [
        cause
        for cause in payload["changes"][0]["causes"]
        if cause["owner_type"] == "fact_temporal"
    ]
    assert temporal_causes == [
        {
            "candidate_record_id": "CREC_000005",
            "chunk_id": None,
            "evidence_text_hash": temporal_causes[0]["evidence_text_hash"],
            "file_path": "corpus/active/manuale_clienti.txt",
            "fragment_id": None,
            "owner_id": "FACT_000001",
            "owner_type": "fact_temporal",
            "side": "after",
            "source_id": "SRC_000001",
            "source_revision_id": "REV_000001",
            "temporal_evidence_id": "TEV_900020",
        }
    ]


def test_slice_26_reconciliation_block_and_allow_incomplete_v2_only(tmp_path):
    workspace, candidate_record_id = ready_workspace_with_interval(tmp_path)
    run_id = _latest_run_id(workspace)
    with connect(workspace) as connection:
        head = str(
            connection.execute(
                "SELECT decision_id FROM review_subject_heads WHERE subject_id = ?",
                (candidate_record_id,),
            ).fetchone()[0]
        )
    CandidateReviewService(workspace).reject(
        candidate_record_id,
        actor_id="slice26-reviewer",
        reason="withdrawn",
        expected_head_decision_id=head,
    )
    with pytest.raises(ReconciliationRequiredError):
        render_dsl_snapshot(workspace, run_id=run_id, schema_version="2")
    with pytest.raises(DslRenderError, match="schema 2"):
        render_dsl_snapshot(
            workspace,
            run_id=run_id,
            schema_version="1",
            allow_incomplete=True,
        )
    allowed = render_dsl_snapshot(
        workspace,
        run_id=run_id,
        schema_version="2",
        allow_incomplete=True,
    )
    content = json.loads((workspace / allowed.json_path).read_text(encoding="utf-8"))
    assert content["metadata"]["incomplete"] == {
        "allowed": True,
        "omitted_intervals": 0,
        "open_reconciliations": 1,
    }
    assert content["metadata"]["warnings"] == [
        {"count": 1, "reason": "reconciliation_required"}
    ]
    facts = [fact for entity in content["entities"] for fact in entity["facts"]]
    assert all(fact["intervals"] == [] for fact in facts)


def test_slice_26_datetime_timezone_resolved_without_truncation(tmp_path):
    workspace, _ = ready_workspace_with_interval(
        tmp_path,
        subject_type="relation",
        subject_id="REL_000001",
        start="2025-06-01T10:00:00",
        end="2025-06-01T11:00:00",
        precision="second",
        timezone_status="resolved",
        timezone_value="Europe/Rome",
    )
    result = render_dsl_snapshot(
        workspace,
        run_id=_latest_run_id(workspace),
        schema_version="2",
    )
    content = json.loads((workspace / result.json_path).read_text(encoding="utf-8"))
    assert content["metadata"]["temporal"] == {
        "base": "timestamp",
        "gexf_timeformat": "dateTime",
        "representation": "interval",
        "timezone": "Europe/Rome",
    }
    interval = content["relations"][0]["intervals"][0]
    assert interval["start"] == "2025-06-01T10:00:00+02:00"
    assert interval["end"] == "2025-06-01T11:00:00+02:00"


def test_slice_26_source_interval_is_not_inherited(tmp_path):
    workspace = _ready_workspace_with_registry(tmp_path)
    run_id = _latest_run_id(workspace)
    evidence_id = insert_raw_temporal_evidence(
        workspace,
        evidence_id="TEV_900010",
        target_subject_type="source_revision",
        target_subject_id="REV_000001",
        raw_value="2025-01-01",
    )
    candidate = create_temporal_candidate(
        workspace,
        run_id=run_id,
        source_revision_id="REV_000001",
        target_subject_type="source_revision",
        target_subject_id="REV_000001",
        temporal_evidence_ids=[evidence_id],
        normalized_start="2025-01-01",
        normalized_end="2025-12-31",
        original_precision="day",
        timezone_status="resolved",
        timezone_value="Europe/Rome",
    )
    CandidateReviewService(workspace).confirm(
        candidate.candidate_record_id,
        actor_id="reviewer",
    )
    result = render_dsl_snapshot(workspace, run_id=run_id, schema_version="2")
    content = json.loads((workspace / result.json_path).read_text(encoding="utf-8"))
    assert all(
        fact["intervals"] == []
        for entity in content["entities"]
        for fact in entity["facts"]
    )
    assert all(relation["intervals"] == [] for relation in content["relations"])


def _add_fact_interval(workspace: Path, run_id: str) -> str:
    evidence_id = insert_raw_temporal_evidence(
        workspace,
        evidence_id="TEV_900020",
        target_subject_type="fact",
        target_subject_id="FACT_000001",
        raw_value="2025-01-01",
    )
    candidate = create_temporal_candidate(
        workspace,
        run_id=run_id,
        source_revision_id="REV_000001",
        target_subject_type="fact",
        target_subject_id="FACT_000001",
        temporal_evidence_ids=[evidence_id],
        normalized_start="2025-01-01",
        normalized_end="2025-12-31",
        original_precision="day",
        timezone_status="resolved",
        timezone_value="Europe/Rome",
    )
    CandidateReviewService(workspace).confirm(candidate.candidate_record_id, actor_id="reviewer")
    return candidate.candidate_record_id


def _latest_run_id(workspace: Path) -> str:
    with connect(workspace) as connection:
        return str(connection.execute("SELECT run_id FROM runs ORDER BY run_id DESC LIMIT 1").fetchone()[0])
