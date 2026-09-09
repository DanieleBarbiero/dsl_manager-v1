from __future__ import annotations

import socket

from dsl_mngr.core.temporal_consolidation import (
    explicit_precedence_candidate_payloads,
    handoff_ai_temporal_candidates,
)
from tests.slice_26_test_support import connect
from tests.slice_27_test_support import registered_workspace


class _FakeTemporalAdapter:
    def propose(self, request):
        assert request == {"prompt": "read-only"}
        return [
            {
                "raw_value": "valid_from: 2028-01-01",
                "normalized_start": "2028-01-01",
                "normalized_end": "2028-12-31",
                "original_precision": "day",
                "timezone_status": "unknown",
                "timezone_value": None,
                "bounds_semantics": "inclusive",
            }
        ]


def test_slice_27_ai_candidate_handoff_is_pending_and_no_network(tmp_path, monkeypatch):
    def deny_network(*args, **kwargs):
        del args, kwargs
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket, "socket", deny_network)
    workspace, run_id, revisions = registered_workspace(
        tmp_path,
        {"policy.txt": "valid_from: 2028-01-01\n"},
    )
    revision_id = revisions["policy.txt"]
    candidate_ids = handoff_ai_temporal_candidates(
        workspace,
        run_id=run_id,
        source_revision_id=revision_id,
        target_subject_type="source_revision",
        target_subject_id=revision_id,
        adapter=_FakeTemporalAdapter(),
        request={"prompt": "read-only"},
    )
    assert len(candidate_ids) == 1
    with connect(workspace) as connection:
        candidate = connection.execute(
            "SELECT assertion_type, confidence, record_type FROM candidate_records WHERE candidate_record_id = ?",
            (candidate_ids[0],),
        ).fetchone()
        evidence = connection.execute(
            """
            SELECT extraction_method, initial_reliability, warnings_json
            FROM raw_temporal_evidence
            """
        ).fetchone()
        assert connection.execute("SELECT COUNT(*) FROM review_decisions").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM temporal_intervals").fetchone()[0] == 0
    assert dict(candidate) == {
        "assertion_type": "ambiguous",
        "confidence": "low",
        "record_type": "temporal_interval",
    }
    assert evidence["extraction_method"] == "ai_candidate_handoff"
    assert evidence["initial_reliability"] == "low"
    assert "requires_human_review" in evidence["warnings_json"]


def test_slice_27_version_precedence_requires_an_explicit_reference():
    implicit = explicit_precedence_candidate_payloads(
        "policy_v2.md follows policy_v1.md by filename order",
        source_revision_id="REV_1",
        source_entity="policy_v2",
        chunk_id="CHUNK_1",
    )
    explicit = explicit_precedence_candidate_payloads(
        "supersedes: policy_v1",
        source_revision_id="REV_1",
        source_entity="policy_v2",
        chunk_id="CHUNK_1",
    )
    assert implicit == []
    assert len(explicit) == 1
    assert explicit[0]["record_type"] == "candidate_relation"
    assert explicit[0]["relation_type"] == "supersedes"
    assert explicit[0]["assertion_type"] == "explicit"
