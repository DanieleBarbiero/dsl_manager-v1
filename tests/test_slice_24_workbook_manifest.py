from __future__ import annotations

import hashlib
import io
import json
import shutil
import sqlite3
from dataclasses import replace
from pathlib import Path

import pytest

from dsl_mngr.core.config import DEFAULT_CONFIG
from dsl_mngr.core.database import open_database, resolve_database_settings
from dsl_mngr.core.docling_adapter import DoclingNormalizationResult
from dsl_mngr.core.fragment_registry import load_fragment_id_seed
from dsl_mngr.core.migrations import MIGRATIONS, apply_migrations, migrate_workspace_database
from dsl_mngr.core.ooxml_preflight import (
    ExcelLimits,
    OoxmlPreflightError,
    acquire_source_once,
    build_workbook_manifest,
    enforce_output_budget,
    preflight_ooxml,
)
from dsl_mngr.core.source_registry import scan_corpus
from dsl_mngr.core.workbook_registry import persist_workbook_output
from dsl_mngr.core.workspace import initialize_workspace
from dsl_mngr.workers import normalize_docling


FIXTURES = Path(__file__).parent / "fixtures" / "slice_24"
STRUCTURAL_XLSX = FIXTURES / "structural_workbook.xlsx"
MACRO_XLSM = FIXTURES / "macro_workbook.xlsm"
CHECKSUMS = json.loads((FIXTURES / "checksums.json").read_text(encoding="utf-8"))
GOLDEN = (
    Path(__file__).parent
    / "expected"
    / "expected_slice_24_workbook_manifest.json"
)
LIMITS = ExcelLimits.from_config(dict(DEFAULT_CONFIG["excel"]))


def test_slice_24_formula_cached():
    built = _build(STRUCTURAL_XLSX)
    cells = {
        cell["coordinate"]: cell
        for sheet in built.manifest["sheets"]
        for cell in sheet["cells"]
    }

    assert cells["D2"] == {
        "coordinate": "D2",
        "row": 2,
        "column": 4,
        "type": "number",
        "value": None,
        "formula": "B2+C2",
        "cached_value": "3.5",
        "style_id": 0,
    }
    assert cells["E2"]["formula"] == "B2*C2"
    assert cells["E2"]["cached_value"] is None
    assert cells["E2"]["value"] is None


def test_slice_24_manifest_golden():
    built = _build(STRUCTURAL_XLSX)

    assert built.manifest_json == GOLDEN.read_text(encoding="utf-8")
    assert hashlib.sha256(built.manifest_json.encode("utf-8")).hexdigest() == (
        built.manifest_hash
    )
    manifest = built.manifest
    assert manifest["schema_version"] == "1"
    assert [sheet["name"] for sheet in manifest["sheets"]] == [
        "Résumé",
        "隐 藏",
        "非常",
    ]
    assert [sheet["visibility"] for sheet in manifest["sheets"]] == [
        "visible",
        "hidden",
        "very_hidden",
    ]
    assert [cell["coordinate"] for cell in manifest["sheets"][0]["cells"]] == [
        "A1",
        "B1",
        "C1",
        "D1",
        "E1",
        "F1",
        "A2",
        "B2",
        "C2",
        "D2",
        "E2",
        "F2",
        "A3",
        "C3",
        "D3",
        "F3",
        "H10",
        "I10",
    ]
    assert {cell["type"] for cell in manifest["sheets"][0]["cells"]} == {
        "blank",
        "bool",
        "date",
        "error",
        "number",
        "string",
    }
    assert manifest["sheets"][0]["merged_ranges"] == ["A3:B3"]
    assert manifest["named_ranges"] == [
        {
            "scope": "workbook",
            "sheet_name": None,
            "name": "MainBlock",
            "refers_to": "'Résumé'!$A$1:$F$3",
        },
        {
            "scope": "sheet",
            "sheet_name": "Résumé",
            "name": "LocalPair",
            "refers_to": "'Résumé'!$H$10:$I$10",
        },
    ]
    assert manifest["external_links"] == [
        {
            "source_part": "xl/externalLinks/externalLink1.xml",
            "relationship_id": "rId1",
            "target": "https://example.invalid/external.xlsx",
            "disposition": "not_dereferenced",
        }
    ]
    assert manifest["macros"] == {
        "present": False,
        "part_name": None,
        "content_hash": None,
        "executed": False,
    }
    assert built.cell_count == 21
    assert built.region_count == 5
    assert len(built.fragments) == 5
    assert [fragment["sequence"] for fragment in built.fragments] == list(range(1, 6))
    assert all(fragment["locator"]["part_name"].startswith("xl/") for fragment in built.fragments)
    assert str(Path.cwd().resolve()) not in built.manifest_json
    assert "created_at" not in built.manifest_json
    assert "run_id" not in built.manifest_json


def test_slice_24_macro_hash_and_fixture_checksums():
    for fixture in (STRUCTURAL_XLSX, MACRO_XLSM):
        assert hashlib.sha256(fixture.read_bytes()).hexdigest() == CHECKSUMS[fixture.name]

    built = _build(MACRO_XLSM, revision_id="REV_SLICE24_MACRO")
    assert built.manifest["macros"] == {
        "present": True,
        "part_name": "xl/vbaProject.bin",
        "content_hash": "0ced1464b3677e98f5e3a8c5d80135e18dc98dca39299f1a8cfd2a00999fbf9f",
        "executed": False,
    }


def test_slice_24_limits_at_and_over_boundaries():
    at_cells = _build(STRUCTURAL_XLSX, limits=replace(LIMITS, max_cells=21))
    assert at_cells.cell_count == 21
    with pytest.raises(OoxmlPreflightError, match="excel.max_cells") as cells_over:
        _build(STRUCTURAL_XLSX, limits=replace(LIMITS, max_cells=20))
    assert cells_over.value.reason == "ooxml_budget_exceeded"

    at_regions = _build(STRUCTURAL_XLSX, limits=replace(LIMITS, max_regions=5))
    assert at_regions.region_count == 5
    with pytest.raises(OoxmlPreflightError, match="excel.max_regions") as regions_over:
        _build(STRUCTURAL_XLSX, limits=replace(LIMITS, max_regions=4))
    assert regions_over.value.reason == "ooxml_budget_exceeded"

    relationship_count = len(at_regions.manifest["relationships"])
    assert _preflight(
        STRUCTURAL_XLSX,
        replace(LIMITS, max_relationships=relationship_count),
    ).relationships == relationship_count
    with pytest.raises(OoxmlPreflightError, match="excel.max_relationships"):
        _preflight(
            STRUCTURAL_XLSX,
            replace(LIMITS, max_relationships=relationship_count - 1),
        )

    serialized = {
        "workbook_manifest.json": at_regions.manifest_json,
        "workbook_fragments.jsonl": at_regions.fragments_jsonl,
    }
    exact_output_size = sum(len(value.encode("utf-8")) for value in serialized.values())
    assert enforce_output_budget(serialized, exact_output_size) == exact_output_size
    with pytest.raises(OoxmlPreflightError, match="excel.max_output_bytes"):
        enforce_output_budget(serialized, exact_output_size - 1)


def test_slice_24_deterministic_across_logical_runs_and_no_network(monkeypatch):
    def forbidden_network(*_args, **_kwargs):
        raise AssertionError("Network access is forbidden while parsing OOXML.")

    monkeypatch.setattr("socket.create_connection", forbidden_network)
    first = _build(STRUCTURAL_XLSX)
    second = _build(STRUCTURAL_XLSX)

    assert first.manifest_json == second.manifest_json
    assert first.fragments_jsonl == second.fragments_jsonl
    assert first.manifest_hash == second.manifest_hash
    assert first.fragments_hash == second.fragments_hash


def test_slice_24_migration_v8_worker_artifacts_and_db_roundtrip(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    initialize_workspace(workspace)
    migrate_workspace_database(workspace)
    source = workspace / "corpus" / "active" / STRUCTURAL_XLSX.name
    shutil.copyfile(STRUCTURAL_XLSX, source)
    scan_corpus(workspace)
    settings = resolve_database_settings(workspace)
    connection = open_database(settings.database_path, enable_wal=settings.wal_enabled)
    try:
        row = connection.execute(
            "SELECT source_id, source_revision_id, content_hash FROM source_revisions"
        ).fetchone()
        source_id = str(row["source_id"])
        revision_id = str(row["source_revision_id"])
        source_hash = str(row["content_hash"])
        seed = load_fragment_id_seed(connection, revision_id)
    finally:
        connection.close()

    monkeypatch.setattr(
        normalize_docling,
        "normalize_excel_stream_with_docling",
        lambda *_args, **_kwargs: _fake_normalization(),
    )
    output = normalize_docling.normalize(
        {
            "run_id": "RUN_SLICE24_001",
            "source_id": source_id,
            "source_revision_id": revision_id,
            "input_path": f"corpus/active/{STRUCTURAL_XLSX.name}",
            "output_dir": f"normalized/{source_id}/{revision_id}",
            "profile": "docling.no_images",
            "worker_config": {"name": "normalize_docling", "version": "1.0"},
            "docling_options": {"input_formats": "xlsx,xlsm"},
            "expected_source_hash": source_hash,
            "excel_limits": dict(DEFAULT_CONFIG["excel"]),
            "fragment_id_by_sequence": seed.fragment_id_by_sequence,
            "next_fragment_number": seed.next_fragment_number,
            "memory_limit_mode": "test",
        },
        workspace_dir=workspace,
    )

    assert output["workbook_manifest_path"].endswith("/workbook_manifest.json")
    assert output["workbook_fragments_path"].endswith("/workbook_fragments.jsonl")
    assert output["workbook_report_path"].endswith("/workbook_report.json")
    report = json.loads((workspace / output["workbook_report_path"]).read_text(encoding="utf-8"))
    assert report["catalog"]["status"] == "completed"
    assert report["network_accessed"] is False
    assert report["macros_executed"] is False

    connection = open_database(settings.database_path, enable_wal=settings.wal_enabled)
    try:
        connection.execute("BEGIN")
        first = persist_workbook_output(
            connection,
            workspace_dir=workspace,
            output=output,
            expected_source_id=source_id,
            expected_source_revision_id=revision_id,
            expected_source_hash=source_hash,
            timestamp="2026-09-04T12:00:00+00:00",
        )
        connection.commit()
        ids_before = _registry_ids(connection)
        connection.execute("BEGIN")
        second = persist_workbook_output(
            connection,
            workspace_dir=workspace,
            output=output,
            expected_source_id=source_id,
            expected_source_revision_id=revision_id,
            expected_source_hash=source_hash,
            timestamp="2026-09-04T13:00:00+00:00",
        )
        connection.commit()
        assert first == second
        assert ids_before == _registry_ids(connection)
        assert connection.execute("SELECT COUNT(*) FROM workbook_manifests").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM workbook_sheets").fetchone()[0] == 3
        assert connection.execute("SELECT COUNT(*) FROM workbook_regions").fetchone()[0] == 5
        assert connection.execute(
            "SELECT COUNT(*) FROM source_fragments WHERE fragment_type = 'excel_region' AND status = 'active'"
        ).fetchone()[0] == 5
        assert connection.execute(
            "SELECT artifact_path FROM workbook_manifests"
        ).fetchone()[0] == output["workbook_manifest_path"]
    finally:
        connection.close()


def test_slice_24_v8_is_append_only_from_v7():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        apply_migrations(connection, migrations=MIGRATIONS[:7])
        result = apply_migrations(connection, migrations=MIGRATIONS[:8])
        assert [migration.version for migration in result.applied] == [8]
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert {
            "workbook_manifests",
            "workbook_sheets",
            "workbook_regions",
        }.issubset(tables)
    finally:
        connection.close()


def _build(
    fixture: Path,
    *,
    revision_id: str = "REV_SLICE24_001",
    limits: ExcelLimits = LIMITS,
):
    source_hash = hashlib.sha256(fixture.read_bytes()).hexdigest()
    acquired = acquire_source_once(
        fixture,
        expected_hash=source_hash,
        max_file_bytes=limits.max_file_bytes,
    )
    checked = preflight_ooxml(
        acquired.cursor(),
        original_name=fixture.name,
        source_hash=source_hash,
        limits=limits,
    )
    return build_workbook_manifest(
        acquired.cursor(),
        preflight=checked,
        source_revision_id=revision_id,
        fragment_id_by_sequence={},
        next_fragment_number=1,
    )


def _preflight(fixture: Path, limits: ExcelLimits):
    data = fixture.read_bytes()
    return preflight_ooxml(
        io.BytesIO(data),
        original_name=fixture.name,
        source_hash=hashlib.sha256(data).hexdigest(),
        limits=limits,
    )


def _fake_normalization() -> DoclingNormalizationResult:
    return DoclingNormalizationResult(
        markdown="# Structural workbook\n",
        document={"name": "structural_workbook", "schema_name": "DoclingDocument"},
        docling_version="2.97.0",
        resolved_options={"input_formats": ["XLSX"]},
        conversion_status="success",
    )


def _registry_ids(connection: sqlite3.Connection) -> tuple[list[str], list[str], list[str]]:
    return (
        [row[0] for row in connection.execute("SELECT manifest_id FROM workbook_manifests ORDER BY manifest_id")],
        [row[0] for row in connection.execute("SELECT sheet_id FROM workbook_sheets ORDER BY sheet_id")],
        [row[0] for row in connection.execute("SELECT region_id FROM workbook_regions ORDER BY region_id")],
    )
