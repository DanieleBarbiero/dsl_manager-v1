from __future__ import annotations

import shutil
import sqlite3
import json
from pathlib import Path

import pytest

from dsl_mngr.core.source_registry import scan_corpus
from dsl_mngr.core.migrations import MIGRATIONS, Migration, apply_migrations
from dsl_mngr.core.temporal import persist_temporal_evidence_records
from dsl_mngr.core.temporal_consolidation import (
    consolidate_temporal_evidence,
    extract_temporal_evidence,
)
from tests.slice_27_test_support import FIXED_TIME, connect, registered_workspace
from tests.test_slice_07_dsl_render import _ready_workspace_with_registry


FIXTURES = Path(__file__).parent / "fixtures"


def test_slice_27_migration_v10_is_append_only_idempotent_and_atomic():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    apply_migrations(connection, migrations=MIGRATIONS[:9])
    failing = Migration(
        version=10,
        name="failed_temporal_consolidation",
        statements=(*MIGRATIONS[9].statements, "CREATE TABLE broken SQL"),
    )
    with pytest.raises(sqlite3.OperationalError):
        apply_migrations(connection, migrations=(failing,))
    assert connection.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE name = 'temporal_evidence_groups'"
    ).fetchone()[0] == 0
    first = apply_migrations(connection, migrations=MIGRATIONS)
    second = apply_migrations(connection, migrations=MIGRATIONS)
    assert [migration.version for migration in first.applied] == [10]
    assert first.skipped_count == 9
    assert second.applied_count == 0
    assert second.skipped_count == 10


def test_slice_27_all_source_extractors_and_exact_first_seen(tmp_path):
    xlsx = (FIXTURES / "slice_23" / "real_workbook.xlsx").read_bytes()
    pdf = b"""%PDF-1.7
/CreationDate (D:20240102123456+01'00')
<x:xmpmeta><xmp:ModifyDate>2024-01-02T12:34:56Z</xmp:ModifyDate></x:xmpmeta>
%%EOF
"""
    files = {
        "book.xlsx": xlsx,
        "contract.pdf": pdf,
        "page.html": (
            '<time datetime="2024-03-04">effective</time>'
            '<meta itemprop="datePublished" content="2024-03-04T10:30:00+01:00">'
            '<script type="application/ld+json">'
            '{"dateModified":"2024-03-05"}</script>'
        ),
        "notes.txt": "valid_from: 2024-01-01\n",
        "policy.md": "competence_year: 2024\n",
        "schema.sql": "-- effective_date = 2024-02-01\nCREATE TABLE x(id INT);\n",
        "form.xml": "<root><valid_to>2024-12-31</valid_to></root>\n",
        "events.log": "valid_from=2024-04-01 event=deploy\n2024-04-02 ordinary event\n",
        "filename_2024-07.txt": "no content declaration\n",
    }
    workspace, _, revisions = registered_workspace(tmp_path, files)
    for revision_id in revisions.values():
        extract_temporal_evidence(
            workspace,
            source_revision_id=revision_id,
            clock=lambda: FIXED_TIME,
        )

    with connect(workspace) as connection:
        rows = connection.execute(
            """
            SELECT sr.file_path, rte.source_key, rte.source_format, rte.raw_value,
                   rte.extraction_method, rte.extraction_version, rte.precision,
                   rte.timezone_status, rte.timezone_value,
                   rte.initial_reliability, rte.warnings_json
            FROM raw_temporal_evidence rte
            JOIN source_revisions sr
              ON sr.source_revision_id = rte.source_revision_id
            ORDER BY sr.file_path, rte.source_key, rte.raw_value
            """
        ).fetchall()
        first_seen = connection.execute(
            """
            SELECT rte.raw_value, s.first_seen_at
            FROM raw_temporal_evidence rte
            JOIN source_revisions sr ON sr.source_revision_id = rte.source_revision_id
            JOIN sources s ON s.source_id = sr.source_id
            WHERE rte.source_key = 'sources.first_seen_at'
            """
        ).fetchall()

    by_name: dict[str, list] = {}
    for row in rows:
        by_name.setdefault(Path(str(row["file_path"])).name, []).append(row)
    assert any(row["source_format"] == "pdf_info" for row in by_name["contract.pdf"])
    assert any(row["source_format"] == "pdf_xmp" for row in by_name["contract.pdf"])
    assert {row["source_format"] for row in by_name["page.html"]} >= {
        "html_time",
        "html_meta",
        "json_ld",
    }
    assert any(row["source_format"] == "text_declaration" for row in by_name["notes.txt"])
    assert any(row["source_format"] == "markdown_declaration" for row in by_name["policy.md"])
    assert any(row["source_format"] == "sql_declaration" for row in by_name["schema.sql"])
    assert any(row["source_format"] == "xml_declaration" for row in by_name["form.xml"])
    assert any(row["source_format"] == "log_declaration" for row in by_name["events.log"])
    assert not any(row["raw_value"] == "2024-04-02" for row in by_name["events.log"])
    assert any(row["source_format"] == "filename_token" for row in by_name["filename_2024-07.txt"])
    assert any(row["extraction_method"] == "ooxml_embedded_metadata" for row in by_name["book.xlsx"])
    assert all(row["extraction_version"] for row in rows)
    assert all(row["warnings_json"] for row in rows)
    assert first_seen and all(row["raw_value"] == row["first_seen_at"] for row in first_seen)


def test_slice_27_independent_concordance_correlation_and_conflict(tmp_path):
    workspace = _ready_workspace_with_registry(tmp_path)
    active = workspace / "corpus" / "active"
    (active / "independent_a.txt").write_text("valid_from: 2024-01-01\nA", encoding="utf-8")
    (active / "independent_b.txt").write_text("valid_from: 2024-01-01\nB", encoding="utf-8")
    (active / "copy_a.txt").write_text("valid_from: 2025-01-01\n", encoding="utf-8")
    shutil.copyfile(active / "copy_a.txt", active / "copy_b.txt")
    scan_corpus(workspace, clock=lambda: FIXED_TIME)
    with connect(workspace) as connection:
        run_id = str(connection.execute("SELECT run_id FROM runs ORDER BY run_id DESC LIMIT 1").fetchone()[0])
        revisions = {
            Path(str(row["file_path"])).name: str(row["source_revision_id"])
            for row in connection.execute("SELECT file_path, source_revision_id FROM source_revisions")
        }

    for name in ("independent_a.txt", "independent_b.txt"):
        _persist_explicit(
            workspace,
            revisions[name],
            "FACT_000001",
            "2024-01-01",
        )
    concordant = consolidate_temporal_evidence(
        workspace,
        run_id=run_id,
        target_subject_type="fact",
        target_subject_id="FACT_000001",
    )
    assert concordant.assessment == "concordant"
    assert len(concordant.candidate_record_ids) == 1
    with connect(workspace) as connection:
        payload = connection.execute(
            "SELECT payload_json FROM candidate_records WHERE candidate_record_id = ?",
            (concordant.candidate_record_ids[0],),
        ).fetchone()[0]
        classes = [
            row[0]
            for row in connection.execute(
                """
                SELECT independence_class FROM temporal_evidence_group_members
                WHERE group_id = ? ORDER BY ordinal
                """,
                (concordant.group_id,),
            )
        ]
    assert json.loads(payload)["confidence"] == "medium"
    assert classes == ["independent", "independent"]

    for name in ("copy_a.txt", "copy_b.txt"):
        _persist_explicit(workspace, revisions[name], "FACT_000002", "2025-01-01")
    correlated = consolidate_temporal_evidence(
        workspace,
        run_id=run_id,
        target_subject_type="fact",
        target_subject_id="FACT_000002",
    )
    assert correlated.assessment == "single_source"
    with connect(workspace) as connection:
        classes = {
            row[0]
            for row in connection.execute(
                "SELECT independence_class FROM temporal_evidence_group_members WHERE group_id = ?",
                (correlated.group_id,),
            )
        }
    assert classes == {"independent", "duplicate"}

    _persist_explicit(workspace, revisions["independent_a.txt"], "FACT_000003", "2024-01-01")
    _persist_explicit(workspace, revisions["independent_b.txt"], "FACT_000003", "2026-01-01")
    conflicted = consolidate_temporal_evidence(
        workspace,
        run_id=run_id,
        target_subject_type="fact",
        target_subject_id="FACT_000003",
    )
    assert conflicted.assessment == "conflicted"
    assert conflicted.conflict_id is not None
    with connect(workspace) as connection:
        assert connection.execute(
            "SELECT status FROM temporal_conflicts WHERE conflict_id = ?",
            (conflicted.conflict_id,),
        ).fetchone()[0] == "open"
        assert connection.execute("SELECT COUNT(*) FROM temporal_intervals").fetchone()[0] == 0


def _persist_explicit(workspace: Path, revision_id: str, target_id: str, value: str) -> None:
    record = {
        "extraction_method": "declared_content_temporality",
        "extraction_version": "1",
        "initial_reliability": "high",
        "precision": "day",
        "raw_value": value,
        "source_format": "text_declaration",
        "source_fragment_id": None,
        "source_key": "content:effective_date",
        "source_revision_id": revision_id,
        "target_subject_id": target_id,
        "target_subject_type": "fact",
        "timezone_status": "unknown",
        "timezone_value": None,
        "warnings": ["declared_content_requires_review"],
    }
    persist_temporal_evidence_records(
        workspace,
        source_revision_id=revision_id,
        target_subject_type="fact",
        target_subject_id=target_id,
        records=[record],
        clock=lambda: FIXED_TIME,
    )
