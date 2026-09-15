from __future__ import annotations

import json
import sqlite3

import pytest

from dsl_mngr.cli.app import main
from dsl_mngr.core.candidate_review import CandidateReviewService
from dsl_mngr.core.dsl_diff import diff_dsl_snapshots
from dsl_mngr.core.dsl_renderer import render_dsl_snapshot
from dsl_mngr.core.graph_export import GraphExportOptions, export_gexf_from_snapshot
from dsl_mngr.core.migrations import MIGRATIONS, Migration, apply_migrations
from dsl_mngr.core.reconciliation import reconcile_required
from dsl_mngr.core.temporal import create_temporal_candidate
from tests.slice_26_test_support import (
    connect,
    insert_raw_temporal_evidence,
    ready_workspace_with_interval,
)


def test_slice_31_migration_v12_backfills_atomically_and_is_append_only(tmp_path):
    workspace, candidate_id = ready_workspace_with_interval(tmp_path)
    with connect(workspace) as connection:
        connection.execute("DROP TRIGGER temporal_interval_supports_no_update")
        connection.execute("DROP TRIGGER temporal_interval_supports_no_delete")
        connection.execute("DROP TABLE temporal_interval_supports")
        connection.execute("DELETE FROM schema_migrations WHERE version = 12")
        connection.commit()
        first = apply_migrations(connection)
        second = apply_migrations(connection)
        assert [item.version for item in first.applied] == [12]
        assert second.applied == ()
        support = connection.execute("SELECT * FROM temporal_interval_supports").fetchone()
        interval = connection.execute("SELECT * FROM temporal_intervals").fetchone()
        assert support["candidate_record_id"] == candidate_id
        assert support["interval_id"] == interval["interval_id"]
        assert support["decision_id"] == interval["decision_id"]
        with pytest.raises(sqlite3.IntegrityError, match="append_only"):
            connection.execute(
                "UPDATE temporal_interval_supports SET created_at = 'changed'"
            )
        with pytest.raises(sqlite3.IntegrityError, match="append_only"):
            connection.execute("DELETE FROM temporal_interval_supports")

    memory = sqlite3.connect(":memory:")
    memory.row_factory = sqlite3.Row
    apply_migrations(memory, migrations=MIGRATIONS[:11])
    broken = Migration(
        version=12,
        name="broken_temporal_supports",
        statements=(*MIGRATIONS[11].statements, "CREATE TABLE invalid SQL"),
    )
    with pytest.raises(sqlite3.OperationalError):
        apply_migrations(memory, migrations=(broken,))
    assert memory.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE name = 'temporal_interval_supports'"
    ).fetchone()[0] == 0
    assert memory.execute(
        "SELECT COUNT(*) FROM schema_migrations WHERE version = 12"
    ).fetchone()[0] == 0


def test_slice_31_same_interval_has_multiple_effective_supports(tmp_path):
    workspace, first_candidate_id = ready_workspace_with_interval(tmp_path)
    evidence_id = insert_raw_temporal_evidence(
        workspace,
        evidence_id="TEV_931001",
        target_subject_type="fact",
        target_subject_id="FACT_000001",
        raw_value="2025-12-31",
    )
    with connect(workspace) as connection:
        run_id = str(connection.execute("SELECT run_id FROM runs ORDER BY run_id DESC").fetchone()[0])
    second = create_temporal_candidate(
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
    service = CandidateReviewService(workspace)
    before_support = render_dsl_snapshot(workspace, run_id=run_id, schema_version="2")
    service.confirm(second.candidate_record_id, actor_id="slice31-reviewer")
    with connect(workspace) as connection:
        assert connection.execute("SELECT COUNT(*) FROM temporal_intervals").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM temporal_interval_supports").fetchone()[0] == 2

    snapshot = render_dsl_snapshot(workspace, run_id=run_id, schema_version="2")
    content = json.loads((workspace / snapshot.json_path).read_text(encoding="utf-8"))
    fact = next(
        fact
        for entity in content["entities"]
        for fact in entity["facts"]
        if fact["fact_id"] == "FACT_000001"
    )
    supports = fact["intervals"][0]["supports"]
    assert [item["candidate_record_id"] for item in supports] == sorted(
        [first_candidate_id, second.candidate_record_id]
    )
    assert all(item["materialization_decision_id"] for item in supports)
    assert all(item["current_decision_id"] for item in supports)
    temporal_trace = content["traceability"]["temporal"]["fact:FACT_000001"]
    assert {item["candidate_record_id"] for item in temporal_trace} == {
        first_candidate_id,
        second.candidate_record_id,
    }
    assert all(item["support_id"] for item in temporal_trace)
    diff = diff_dsl_snapshots(
        workspace,
        run_id=run_id,
        from_snapshot_id=before_support.snapshot_id,
        to_snapshot_id=snapshot.snapshot_id,
    )
    diff_payload = json.loads((workspace / diff.json_path).read_text(encoding="utf-8"))
    temporal_causes = [
        cause
        for change in diff_payload["changes"]
        for cause in change["causes"]
        if cause["owner_type"] == "fact_temporal" and "support_id" in cause
    ]
    assert {cause["candidate_record_id"] for cause in temporal_causes} == {
        first_candidate_id,
        second.candidate_record_id,
    }
    graph = export_gexf_from_snapshot(
        workspace,
        run_id=run_id,
        snapshot_id=snapshot.snapshot_id,
        options=GraphExportOptions(dynamic=True, timeformat="date"),
    )
    graph_xml = (workspace / graph.graph_path).read_text(encoding="utf-8")
    assert "temporal_support_candidate_ids" in graph_xml
    assert first_candidate_id in graph_xml
    assert second.candidate_record_id in graph_xml

    first_head = service.show_candidate(first_candidate_id)["decisions"][-1]["decision_id"]
    service.reject(
        first_candidate_id,
        actor_id="slice31-reviewer",
        reason="first invalid",
        expected_head_decision_id=first_head,
    )
    reconcile_required(workspace, run_id=run_id)
    one_left = render_dsl_snapshot(workspace, run_id=run_id, schema_version="2")
    one_content = json.loads((workspace / one_left.json_path).read_text(encoding="utf-8"))
    one_fact = next(
        fact
        for entity in one_content["entities"]
        for fact in entity["facts"]
        if fact["fact_id"] == "FACT_000001"
    )
    assert len(one_fact["intervals"]) == 1
    assert [
        item["candidate_record_id"] for item in one_fact["intervals"][0]["supports"]
    ] == [second.candidate_record_id]

    second_head = service.show_candidate(second.candidate_record_id)["decisions"][-1][
        "decision_id"
    ]
    service.reject(
        second.candidate_record_id,
        actor_id="slice31-reviewer",
        reason="second invalid",
        expected_head_decision_id=second_head,
    )
    reconcile_required(workspace, run_id=run_id)
    none_left = render_dsl_snapshot(workspace, run_id=run_id, schema_version="2")
    none_content = json.loads((workspace / none_left.json_path).read_text(encoding="utf-8"))
    none_fact = next(
        fact
        for entity in none_content["entities"]
        for fact in entity["facts"]
        if fact["fact_id"] == "FACT_000001"
    )
    assert none_fact["intervals"] == []
    with connect(workspace) as connection:
        assert connection.execute("SELECT COUNT(*) FROM temporal_interval_supports").fetchone()[0] == 2


def test_slice_31_public_temporal_propagation_and_prevalidation(tmp_path, capsys):
    workspace, _ = ready_workspace_with_interval(tmp_path)
    capsys.readouterr()
    exit_code = main(
        [
            "temporal",
            "propagate",
            str(workspace),
            "--source-revision-id",
            "REV_000001",
            "--target-subject-type",
            "fact",
            "--target-subject-id",
            "FACT_000002",
            "--source-subject",
            "fact:FACT_000001",
            "--policy",
            "explicit_copy",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == payload["exit_code"] == 0
    assert payload["candidate_record_ids"]
    assert payload["candidate_batch_ids"]
    assert all((workspace / path).is_file() for path in payload["artifact_paths"])
    with connect(workspace) as connection:
        run = connection.execute(
            "SELECT run_type, status FROM runs WHERE run_id = ?", (payload["run_id"],)
        ).fetchone()
        assert tuple(run) == ("temporal_propagation", "completed")
    conflict_exit = main(
        [
            "temporal",
            "propagate",
            str(workspace),
            "--source-revision-id",
            "REV_000001",
            "--target-subject-type",
            "fact",
            "--target-subject-id",
            "FACT_000002",
            "--source-subject",
            "fact:FACT_000001",
            "--policy",
            "conflict",
        ]
    )
    conflict_payload = json.loads(capsys.readouterr().out)
    assert conflict_exit == conflict_payload["exit_code"] == 4
    assert conflict_payload["conflict_id"]
    with connect(workspace) as connection:
        evidence_before = connection.execute(
            "SELECT COUNT(*) FROM raw_temporal_evidence"
        ).fetchone()[0]

    duplicate_exit = main(
        [
            "temporal",
            "propagate",
            str(workspace),
            "--source-revision-id",
            "REV_000001",
            "--target-subject-type",
            "fact",
            "--target-subject-id",
            "FACT_000002",
            "--source-subject",
            "fact:FACT_000001",
            "--source-subject",
            "fact:FACT_000001",
            "--policy",
            "explicit_copy",
        ]
    )
    duplicate_payload = json.loads(capsys.readouterr().out)
    assert duplicate_exit == 3
    assert duplicate_payload["reason"] == "temporal_source_duplicate"
    with connect(workspace) as connection:
        assert connection.execute("SELECT COUNT(*) FROM raw_temporal_evidence").fetchone()[0] == evidence_before
