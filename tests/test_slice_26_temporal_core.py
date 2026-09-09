from __future__ import annotations

import hashlib
import io
import json
import shutil
import sqlite3
import zipfile
from pathlib import Path

import pytest

from dsl_mngr.cli.app import main
from dsl_mngr.core.candidate_review import (
    CandidateReviewConflict,
    CandidateReviewError,
    CandidateReviewService,
)
from dsl_mngr.core.migrations import MIGRATIONS, Migration, apply_migrations
from dsl_mngr.core.runs import start_run
from dsl_mngr.core.temporal import (
    create_temporal_candidate,
    extract_ooxml_temporal_evidence,
)
from tests.slice_26_test_support import (
    connect,
    insert_raw_temporal_evidence,
    ready_workspace_with_interval,
)
from tests.test_slice_07_dsl_render import _ready_workspace_with_registry


FIXTURE = Path(__file__).parent / "fixtures" / "slice_24" / "structural_workbook.xlsx"


def test_slice_26_migration_v9_and_rollback():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    apply_migrations(connection, migrations=MIGRATIONS[:8])
    failing = Migration(
        version=9,
        name="failed_temporal_core",
        statements=(*MIGRATIONS[8].statements, "CREATE TABLE incomplete SQL"),
    )
    with pytest.raises(sqlite3.OperationalError):
        apply_migrations(connection, migrations=(failing,))
    assert connection.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE name = 'raw_temporal_evidence'"
    ).fetchone()[0] == 0
    assert connection.execute(
        "SELECT COUNT(*) FROM schema_migrations WHERE version = 9"
    ).fetchone()[0] == 0
    applied = apply_migrations(connection, migrations=MIGRATIONS)
    assert [migration.version for migration in applied.applied] == [9, 10]
    table_names = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    assert {
        "raw_temporal_evidence",
        "temporal_candidate_details",
        "temporal_candidate_evidence",
        "temporal_intervals",
    }.issubset(table_names)


def test_slice_26_raw_evidence_fields(tmp_path, capsys):
    workspace, revision_id = _registered_ooxml_workspace(tmp_path, FIXTURE)
    result = extract_ooxml_temporal_evidence(
        workspace,
        source_revision_id=revision_id,
    )
    assert result.inserted_count == len(result.evidence_ids)
    with connect(workspace) as connection:
        rows = connection.execute(
            "SELECT * FROM raw_temporal_evidence ORDER BY source_key"
        ).fetchall()
        columns = set(rows[0].keys())
        assert columns == {
            "temporal_evidence_id",
            "target_subject_type",
            "target_subject_id",
            "source_revision_id",
            "source_fragment_id",
            "source_key",
            "source_format",
            "raw_value",
            "extraction_method",
            "extraction_version",
            "precision",
            "timezone_status",
            "timezone_value",
            "initial_reliability",
            "warnings_json",
            "evidence_hash",
            "created_at",
        }
        assert all(row["raw_value"] and row["extraction_method"] for row in rows)
        assert all(row["extraction_version"] and row["precision"] for row in rows)
        assert all(row["timezone_status"] and row["initial_reliability"] for row in rows)
        assert all(isinstance(json.loads(row["warnings_json"]), list) for row in rows)
        keys = {row["source_key"] for row in rows}
        assert {"core:created", "core:modified"}.issubset(keys)
        assert any(key.startswith("app:") for key in keys)
        assert any(key.startswith("zip:") for key in keys)
        core_rows = [row for row in rows if row["source_key"].startswith("core:")]
        assert {row["timezone_status"] for row in core_rows} == {"explicit"}
        assert {row["timezone_value"] for row in core_rows} == {"UTC"}
        assert all(
            "temporal_values_concordant" in json.loads(row["warnings_json"])
            for row in core_rows
        )
        zip_rows = [row for row in rows if row["source_key"].startswith("zip:")]
        assert {row["timezone_status"] for row in zip_rows} == {"unknown"}
        with pytest.raises(sqlite3.IntegrityError, match="append_only"):
            connection.execute(
                "UPDATE raw_temporal_evidence SET raw_value = 'changed' WHERE temporal_evidence_id = ?",
                (rows[0]["temporal_evidence_id"],),
            )
    replay = extract_ooxml_temporal_evidence(workspace, source_revision_id=revision_id)
    assert replay.inserted_count == 0
    assert replay.existing_count == len(result.evidence_ids)
    assert replay.evidence_hashes == result.evidence_hashes


def test_slice_26_contradictory_properties_stay_pending(tmp_path, capsys):
    contradictory = tmp_path / "contradictory.xlsx"
    _rewrite_core_modified(FIXTURE, contradictory, "2001-02-03T04:05:06Z")
    workspace, revision_id = _registered_ooxml_workspace(tmp_path, contradictory)
    evidence = extract_ooxml_temporal_evidence(workspace, source_revision_id=revision_id)
    with connect(workspace) as connection:
        core = connection.execute(
            """
            SELECT temporal_evidence_id, warnings_json
            FROM raw_temporal_evidence
            WHERE source_key IN ('core:created', 'core:modified')
            ORDER BY source_key
            """
        ).fetchall()
    run_id = start_run(workspace, run_type="test").record.run_id
    assert len(evidence.evidence_ids) > 2
    assert all(
        "temporal_values_contradictory" in json.loads(row["warnings_json"])
        for row in core
    )
    candidate = create_temporal_candidate(
        workspace,
        run_id=run_id,
        source_revision_id=revision_id,
        target_subject_type="source_revision",
        target_subject_id=revision_id,
        temporal_evidence_ids=[row["temporal_evidence_id"] for row in core],
        normalized_start="2000-01-01T00:00:00Z",
        normalized_end="2001-02-03T04:05:06Z",
        original_precision="second",
        timezone_status="explicit",
        timezone_value="UTC",
    )
    with connect(workspace) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM review_subject_heads WHERE subject_id = ?",
            (candidate.candidate_record_id,),
        ).fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM temporal_intervals").fetchone()[0] == 0


def test_slice_26_common_review(tmp_path):
    workspace = _ready_workspace_with_registry(tmp_path)
    evidence_id = insert_raw_temporal_evidence(
        workspace,
        evidence_id="TEV_900001",
        target_subject_type="fact",
        target_subject_id="FACT_000001",
        raw_value="2025-01-01",
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
        normalized_start="2025-01-01",
        normalized_end="2025-12-31",
        original_precision="day",
        timezone_status="resolved",
        timezone_value="Europe/Rome",
    )
    with connect(workspace) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM temporal_candidate_details WHERE candidate_record_id = ?",
            (candidate.candidate_record_id,),
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM temporal_candidate_evidence WHERE candidate_record_id = ?",
            (candidate.candidate_record_id,),
        ).fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM temporal_intervals").fetchone()[0] == 0
    service = CandidateReviewService(workspace)
    with pytest.raises(CandidateReviewConflict, match="common human review"):
        service.confirm(
            candidate.candidate_record_id,
            actor_type="automatic",
            actor_id="temporal-auto",
            policy_id="high_confidence",
            policy_version="1",
        )
    decision = service.confirm(candidate.candidate_record_id, actor_id="human-reviewer")
    assert decision.outcome == "confirmed"
    with connect(workspace) as connection:
        interval = connection.execute("SELECT * FROM temporal_intervals").fetchone()
        assert interval["subject_type"] == "fact"
        assert interval["subject_id"] == "FACT_000001"
        assert interval["start_value"] == "2025-01-01"
        assert interval["end_value"] == "2025-12-31"
        assert interval["timeformat"] == "date"
        assert interval["decision_id"] == decision.decision_id
        assert interval["source_candidate_record_id"] == candidate.candidate_record_id


def test_slice_26_multiple_intervals_and_timezone_resolution(tmp_path):
    workspace, _ = ready_workspace_with_interval(tmp_path)
    second_evidence = insert_raw_temporal_evidence(
        workspace,
        evidence_id="TEV_900002",
        target_subject_type="fact",
        target_subject_id="FACT_000001",
        raw_value="2026-01-01",
    )
    unknown_evidence = insert_raw_temporal_evidence(
        workspace,
        evidence_id="TEV_900003",
        target_subject_type="relation",
        target_subject_id="REL_000001",
        raw_value="2026-01-01T10:00:00",
    )
    with connect(workspace) as connection:
        run_id = str(connection.execute("SELECT run_id FROM runs ORDER BY run_id DESC LIMIT 1").fetchone()[0])
    second = create_temporal_candidate(
        workspace,
        run_id=run_id,
        source_revision_id="REV_000001",
        target_subject_type="fact",
        target_subject_id="FACT_000001",
        temporal_evidence_ids=[second_evidence],
        normalized_start="2026-01-01",
        normalized_end="2026-12-31",
        original_precision="day",
        timezone_status="resolved",
        timezone_value="Europe/Rome",
    )
    CandidateReviewService(workspace).confirm(
        second.candidate_record_id,
        actor_id="reviewer",
    )
    unknown = create_temporal_candidate(
        workspace,
        run_id=run_id,
        source_revision_id="REV_000001",
        target_subject_type="relation",
        target_subject_id="REL_000001",
        temporal_evidence_ids=[unknown_evidence],
        normalized_start="2026-01-01T10:00:00",
        normalized_end="2026-01-01T11:00:00",
        original_precision="second",
        timezone_status="unknown",
        timezone_value=None,
    )
    with pytest.raises(CandidateReviewError) as timezone_error:
        CandidateReviewService(workspace).confirm(unknown.candidate_record_id, actor_id="reviewer")
    assert timezone_error.value.reason == "temporal_timezone_unknown"
    with connect(workspace) as connection:
        assert connection.execute("SELECT COUNT(*) FROM temporal_intervals").fetchone()[0] == 2
        assert connection.execute(
            "SELECT COUNT(*) FROM review_subject_heads WHERE subject_id IN (?, ?)",
            (second.candidate_record_id, unknown.candidate_record_id),
        ).fetchone()[0] == 1


def test_slice_26_all_temporal_targets_and_coverage_envelope(tmp_path):
    workspace = _ready_workspace_with_registry(tmp_path)
    with connect(workspace) as connection:
        connection.execute(
            """
            INSERT INTO source_fragments (
                fragment_id, source_revision_id, fragment_type, sequence,
                path_or_selector, line_start, line_end, char_start, char_end,
                text, text_hash, metadata_json, status, created_at
            )
            VALUES (
                'FRAG_900001', 'REV_000001', 'test', 1, 'test/fragment',
                1, 1, 0, 8, 'evidence', ?, '{}', 'active',
                '2026-09-04T10:00:00+00:00'
            )
            """,
            (hashlib.sha256(b"evidence").hexdigest(),),
        )
        run_id = str(
            connection.execute(
                "SELECT run_id FROM runs ORDER BY run_id DESC LIMIT 1"
            ).fetchone()[0]
        )

    targets = (
        ("source_revision", "REV_000001"),
        ("source_fragment", "FRAG_900001"),
        ("candidate_record", "CREC_000001"),
        ("fact", "FACT_000001"),
        ("relation", "REL_000001"),
    )
    service = CandidateReviewService(workspace)
    for ordinal, (subject_type, subject_id) in enumerate(targets, start=1):
        evidence_id = insert_raw_temporal_evidence(
            workspace,
            evidence_id=f"TEV_91000{ordinal}",
            target_subject_type=subject_type,
            target_subject_id=subject_id,
            raw_value="2025",
        )
        candidate = create_temporal_candidate(
            workspace,
            run_id=run_id,
            source_revision_id="REV_000001",
            target_subject_type=subject_type,
            target_subject_id=subject_id,
            temporal_evidence_ids=[evidence_id],
            normalized_start="2025-01-01",
            normalized_end="2025-12-31",
            original_precision="year",
            timezone_status="resolved",
            timezone_value="Europe/Rome",
            bounds_semantics="coverage_envelope",
        )
        service.confirm(candidate.candidate_record_id, actor_id="reviewer")

    with connect(workspace) as connection:
        intervals = connection.execute(
            """
            SELECT subject_type, subject_id, start_value, end_value,
                   original_precision, bounds_semantics
            FROM temporal_intervals
            ORDER BY subject_type, subject_id
            """
        ).fetchall()
    assert {(row["subject_type"], row["subject_id"]) for row in intervals} == set(targets)
    assert all(row["start_value"] == "2025-01-01" for row in intervals)
    assert all(row["end_value"] == "2025-12-31" for row in intervals)
    assert all(row["original_precision"] == "year" for row in intervals)
    assert all(row["bounds_semantics"] == "coverage_envelope" for row in intervals)


def _registered_ooxml_workspace(tmp_path: Path, fixture: Path) -> tuple[Path, str]:
    workspace = tmp_path / "workspace"
    assert main(["init", str(workspace)]) == 0
    assert main(["db", "init", str(workspace)]) == 0
    target = workspace / "corpus" / "active" / fixture.name
    shutil.copyfile(fixture, target)
    assert main(["corpus", "scan", str(workspace)]) == 0
    with sqlite3.connect(workspace / "workspace.sqlite") as connection:
        revision_id = str(connection.execute("SELECT source_revision_id FROM source_revisions").fetchone()[0])
    return workspace, revision_id


def _rewrite_core_modified(source: Path, target: Path, modified: str) -> None:
    output = io.BytesIO()
    with zipfile.ZipFile(source) as original, zipfile.ZipFile(
        output, "w", compression=zipfile.ZIP_DEFLATED
    ) as replacement:
        for info in original.infolist():
            data = original.read(info)
            if info.filename == "docProps/core.xml":
                data = data.replace(b"2000-01-01T00:00:00Z", modified.encode("ascii"), 1)
            replacement.writestr(info, data)
    target.write_bytes(output.getvalue())
