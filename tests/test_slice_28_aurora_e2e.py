from __future__ import annotations

import csv
import hashlib
import io
import json
import shutil
import socket
import urllib.request
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from dsl_mngr.cli.commands.corpus import (
    parse_db_code_source_revision,
    parse_ddl_source_revision,
    parse_log_source_revision,
    parse_xml_form_source_revision,
)
from dsl_mngr.core.batch_consolidation import (
    BatchConsolidationError,
    _derive_phase,
    _merge_phase,
    _review_phase,
    consolidate_batch,
)
from dsl_mngr.core.candidate_derivation import ALL_DERIVATION_RULE_CATALOG
from dsl_mngr.core.candidate_review import CandidateReviewService
from dsl_mngr.core.canonical import canonical_sha256_v1
from dsl_mngr.core.config import DEFAULT_CONFIG
from dsl_mngr.core.database import open_database, resolve_database_settings
from dsl_mngr.core.docling_adapter import DoclingNormalizationResult
from dsl_mngr.core.dsl_diff import diff_dsl_snapshots
from dsl_mngr.core.dsl_renderer import render_dsl_snapshot
from dsl_mngr.core.fragment_registry import load_fragment_id_seed
from dsl_mngr.core.gexf_validation import validate_dynamic_gexf
from dsl_mngr.core.graph_export import GraphExportOptions, export_gexf_from_snapshot
from dsl_mngr.core.migrations import migrate_workspace_database
from dsl_mngr.core.ooxml_preflight import (
    ExcelLimits,
    OoxmlPreflightError,
    acquire_source_once,
    build_workbook_manifest,
    preflight_ooxml,
    preflight_ooxml_metadata,
)
from dsl_mngr.core.runs import complete_run, start_run
from dsl_mngr.core.source_registry import scan_corpus
from dsl_mngr.core.temporal import persist_temporal_evidence_records
from dsl_mngr.core.temporal_consolidation import consolidate_temporal_evidence
from dsl_mngr.core.workbook_registry import persist_workbook_output
from dsl_mngr.core.workspace import initialize_workspace
from dsl_mngr.workers import normalize_docling


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
AURORA_ROOT = (
    REPOSITORY_ROOT
    / ".kb"
    / "projects"
    / "corpus aurora"
    / "corpus_mock_aurora_prestiti"
)
ACTIVE = AURORA_ROOT / "corpus" / "active"
SUPPORT = AURORA_ROOT / "materiale_di_supporto"
CONTROLLED = SUPPORT / "fixture_controllate"
CHECKSUMS = SUPPORT / "checksums.json"
EXPECTED = REPOSITORY_ROOT / "tests" / "expected" / "expected_slice_28_aurora_e2e.json"
MAIN_WORKBOOK = "documenti/nuovi_utili/matrice_stati_2025.xlsx"
MACRO_WORKBOOK = "documenti/nuovi_utili/calcolo_rate_macro_2025.xlsm"
CURRENT_REQUIREMENTS = "documenti/nuovi_utili/requisiti_modernizzazione_2025.md"
CURRENT_ADDENDUM = "documenti/nuovi_utili/decorrenza_modernizzazione_2025.txt"
CURRENT_DOCX = "documenti/nuovi_utili/manuale_ufficio_crediti_2024.docx"
HISTORICAL_MANUAL = "documenti/vecchi_utili/manuale_pratiche_2012.txt"
FIXED_TIME = datetime(2026, 9, 5, 10, 0, 0, tzinfo=timezone.utc)
LIMITS = ExcelLimits.from_config(dict(DEFAULT_CONFIG["excel"]))
AUTO_POLICIES = tuple(
    sorted(
        {
            contract.automatic_review_policy
            for contract in ALL_DERIVATION_RULE_CATALOG.values()
            if contract.automatic_review_allowed
        }
    )
)


def test_slice_28_checksum_inventory_and_references():
    manifest = json.loads(CHECKSUMS.read_text(encoding="utf-8"))
    expected_paths = set(manifest["files"])
    actual_paths = {
        path.relative_to(AURORA_ROOT).as_posix()
        for root in (ACTIVE, CONTROLLED)
        for path in root.rglob("*")
        if path.is_file()
    }
    assert manifest["algorithm"] == "sha256"
    assert manifest["schema_version"] == "1"
    assert actual_paths == expected_paths
    assert len([path for path in actual_paths if path.startswith("corpus/active/")]) == 18

    for relative, expected in manifest["files"].items():
        path = AURORA_ROOT / relative
        assert path.stat().st_size == expected["bytes"]
        assert _sha256(path) == expected["sha256"]

    with (SUPPORT / "inventario_fonti.csv").open(encoding="utf-8", newline="") as stream:
        inventory = list(csv.DictReader(stream, delimiter=";"))
    assert {row["percorso"] for row in inventory} == expected_paths
    assert {row["percorso"]: row["sha256"] for row in inventory} == {
        path: item["sha256"] for path, item in manifest["files"].items()
    }

    assert _sha256(ACTIVE / MAIN_WORKBOOK) == _sha256(
        REPOSITORY_ROOT / "tests" / "fixtures" / "slice_24" / "structural_workbook.xlsx"
    )
    assert _sha256(ACTIVE / MACRO_WORKBOOK) == _sha256(
        REPOSITORY_ROOT / "tests" / "fixtures" / "slice_24" / "macro_workbook.xlsm"
    )
    assert _sha256(CONTROLLED / "workbook_partial_controllato.xlsx") == _sha256(
        REPOSITORY_ROOT / "tests" / "fixtures" / "slice_25" / "candidate_workbook.xlsx"
    )

    real_support_files = {
        "checksums.json",
        "checklist_risultati_attesi.md",
        "guida_dsl-manager-powershell.md",
        "guida_dsl-manager_cmd.md",
        "inventario_fonti.csv",
        "limitazioni_intenzionali.md",
        "matrice_fixture_attesi.md",
    }
    assert all((SUPPORT / name).is_file() for name in real_support_files)
    corpus_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (AURORA_ROOT / "LEGGIMI_PRIMA.md", *sorted(SUPPORT.glob("*.md")))
    )
    assert "corpus_mock_aurora_prestiti.zip" not in corpus_text
    assert "guida_dsl-manager.md" not in corpus_text
    assert not (AURORA_ROOT / "corpus_mock_aurora_prestiti.zip").exists()
    assert not (AURORA_ROOT / "guida_dsl-manager.md").exists()


def test_slice_28_aurora_e2e(tmp_path, monkeypatch):
    _forbid_network(monkeypatch)
    monkeypatch.setattr(
        normalize_docling,
        "normalize_excel_stream_with_docling",
        _successful_excel_normalization,
    )

    first = _run_aurora_workflow(tmp_path / "first")
    second = _run_aurora_workflow(tmp_path / "second")
    assert first == second

    if not EXPECTED.is_file():
        raise AssertionError(json.dumps(first, ensure_ascii=False, indent=2, sort_keys=True))
    assert first == json.loads(EXPECTED.read_text(encoding="utf-8")), json.dumps(
        first,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )


def test_slice_28_malformed_partial_budget_and_no_network(tmp_path, monkeypatch):
    _forbid_network(monkeypatch)
    malformed = CONTROLLED / "workbook_malformed_controllato.xlsx"
    malformed_data = malformed.read_bytes()
    with pytest.raises(OoxmlPreflightError) as caught:
        preflight_ooxml(
            io.BytesIO(malformed_data),
            original_name=malformed.name,
            source_hash=hashlib.sha256(malformed_data).hexdigest(),
            limits=LIMITS,
        )
    assert caught.value.reason == "ooxml_security_violation"
    assert caught.value.status == "rejected"

    main = ACTIVE / MAIN_WORKBOOK
    exact = _build_manifest(main, limits=replace(LIMITS, max_cells=21))
    assert exact.cell_count == 21
    with pytest.raises(OoxmlPreflightError) as budget:
        _build_manifest(main, limits=replace(LIMITS, max_cells=20))
    assert budget.value.reason == "ooxml_budget_exceeded"

    workspace = _workspace_with_files(
        tmp_path / "partial",
        {"workbook_partial_controllato.xlsx": CONTROLLED / "workbook_partial_controllato.xlsx"},
    )
    monkeypatch.setattr(
        normalize_docling,
        "normalize_excel_stream_with_docling",
        _partial_excel_normalization,
    )
    output, manifest = _normalize_and_persist(
        workspace,
        "workbook_partial_controllato.xlsx",
        persist=False,
    )
    assert output["status"] == "partial"
    assert output["exit_code"] == 6
    assert "tables" in manifest
    required = {
        "normalized_json_path",
        "normalized_markdown_path",
        "workbook_manifest_path",
        "workbook_fragments_path",
        "workbook_report_path",
    }
    assert all((workspace / output[key]).is_file() for key in required)
    report = json.loads((workspace / output["workbook_report_path"]).read_text(encoding="utf-8"))
    assert report["status"] == "partial"
    assert report["catalog"]["reason"] == "normalization_partial"
    assert report["network_accessed"] is False
    assert report["macros_executed"] is False


def test_slice_28_batch_derive_accepts_docx_temporal_metadata(tmp_path, monkeypatch):
    _forbid_network(monkeypatch)
    workspace = _workspace_with_files(
        tmp_path / "docx_temporal_regression",
        {CURRENT_DOCX: ACTIVE / CURRENT_DOCX},
    )
    revision_id = _revisions_by_path(workspace)[CURRENT_DOCX]
    parent = start_run(
        workspace,
        run_type="batch",
        input_payload={"regression": "docx_temporal_preflight"},
        clock=lambda: FIXED_TIME,
    )

    derived = _derive_phase(
        resolve_database_settings(workspace),
        run_id=parent.record.run_id,
        parse_payload={
            "source_revision_ids": [revision_id],
            "structured_sources": [],
        },
        rule_set_version="1",
    )

    assert derived["status"] == "completed"
    assert derived["counters"]["temporal_evidence_extracted"] > 0
    with _connect(workspace) as connection:
        source_keys = {
            str(row[0])
            for row in connection.execute(
                "SELECT source_key FROM raw_temporal_evidence "
                "WHERE source_revision_id = ?",
                (revision_id,),
            ).fetchall()
        }
    assert "core:created" in source_keys
    assert "core:modified" in source_keys
    assert any(key.startswith("zip:") for key in source_keys)


def test_slice_28_ooxml_metadata_rejects_extension_content_type_mismatch(monkeypatch):
    _forbid_network(monkeypatch)
    data = (ACTIVE / CURRENT_DOCX).read_bytes()

    with pytest.raises(OoxmlPreflightError) as caught:
        preflight_ooxml_metadata(
            io.BytesIO(data),
            original_name="manuale_ufficio_crediti_2024.pptx",
            source_hash=hashlib.sha256(data).hexdigest(),
            limits=LIMITS,
        )

    assert caught.value.reason == "ooxml_security_violation"
    assert "content type" in str(caught.value)


def test_slice_28_order_retry_uses_aurora_sources(tmp_path, monkeypatch):
    _forbid_network(monkeypatch)
    source_files = {
        "database/dump_oracle_ddl.sql": ACTIVE / "database" / "dump_oracle_ddl.sql",
        "plsql/PRC_GENERA_PIANO.sql": ACTIVE / "plsql" / "PRC_GENERA_PIANO.sql",
    }
    clean = None
    clean_result = None
    for attempt in range(1, 4):
        clean = _workspace_with_files(tmp_path / f"clean_{attempt}", source_files)
        clean_result = consolidate_batch(clean)
        if clean_result["reason"] != "batch_parse_failed":
            break
    assert clean is not None and clean_result is not None
    assert clean_result["reason"] != "batch_parse_failed"
    clean_state = _candidate_state(clean)

    def crash(point: str) -> None:
        if point == "after_derive":
            raise RuntimeError("slice 28 controlled crash")

    retry = None
    controlled_crash = None
    for attempt in range(1, 4):
        retry = _workspace_with_files(
            tmp_path / f"retry_{attempt}",
            dict(reversed(tuple(source_files.items()))),
        )
        try:
            result = consolidate_batch(retry, fault_hook=crash)
        except BatchConsolidationError as exc:
            controlled_crash = exc
            break
        assert result["reason"] == "batch_parse_failed"
    assert retry is not None
    assert controlled_crash is not None
    assert "controlled crash" in str(controlled_crash)
    with _connect(retry) as connection:
        failed_run = str(
            connection.execute(
                "SELECT run_id FROM runs WHERE run_type = 'batch' "
                "AND parent_run_id IS NULL ORDER BY run_id DESC LIMIT 1"
            ).fetchone()[0]
        )
        records_before = int(
            connection.execute("SELECT COUNT(*) FROM candidate_records").fetchone()[0]
        )
    resumed = consolidate_batch(retry, resume_run_id=failed_run)
    with _connect(retry) as connection:
        records_after = int(
            connection.execute("SELECT COUNT(*) FROM candidate_records").fetchone()[0]
        )

    assert records_after == records_before
    assert resumed["counters"] == clean_result["counters"]
    assert _candidate_state(retry) == clean_state


def _run_aurora_workflow(root: Path) -> dict[str, Any]:
    workspace = _workspace_with_tree(root)
    first_scan = scan_corpus(workspace, clock=lambda: FIXED_TIME)
    second_scan = scan_corpus(workspace, clock=lambda: FIXED_TIME)
    assert (first_scan.added, second_scan.unchanged) == (18, 18)

    main_output, main_manifest = _normalize_and_persist(workspace, MAIN_WORKBOOK)
    macro_output, macro_manifest = _normalize_and_persist(workspace, MACRO_WORKBOOK)
    _assert_main_workbook(main_manifest)
    assert macro_manifest["macros"] == {
        "present": True,
        "part_name": "xl/vbaProject.bin",
        "content_hash": "0ced1464b3677e98f5e3a8c5d80135e18dc98dca39299f1a8cfd2a00999fbf9f",
        "executed": False,
    }

    parent = start_run(
        workspace,
        run_type="batch",
        input_payload={"slice": 28},
        clock=lambda: FIXED_TIME,
    )
    revisions = _revisions_by_path(workspace)
    parser_inputs = (
        ("parse_ddl", "database/dump_oracle_ddl.sql", parse_ddl_source_revision, "ddl.default"),
        ("parse_xml_form", "forms/FRM_CLIENTE.xml", parse_xml_form_source_revision, "xml_form.default"),
        ("parse_db_code", "plsql/PRC_GENERA_PIANO.sql", parse_db_code_source_revision, "db_code.default"),
        ("parse_log", "logs/batch_piano_rate_2025.log", parse_log_source_revision, "log.default"),
    )
    parser_projection: dict[str, dict[str, Any]] = {}
    structured_sources: list[dict[str, str]] = []
    for kind, relative, parser, profile in parser_inputs:
        revision_id = revisions[relative]
        result = parser(
            workspace,
            source_revision_id=revision_id,
            profile=profile,
            parent_run_id=parent.record.run_id,
        )
        assert result.worker_result.status == "completed"
        parser_projection[kind] = {
            "fragment_count": result.fragment_count,
            "fragments_hash": result.fragments_hash,
        }
        structured_sources.append({"kind": kind, "source_revision_id": revision_id})

    structured_sources.extend(
        [
            {"kind": "normalize_excel", "source_revision_id": revisions[MAIN_WORKBOOK]},
            {"kind": "normalize_excel", "source_revision_id": revisions[MACRO_WORKBOOK]},
        ]
    )
    derive = _derive_phase(
        resolve_database_settings(workspace),
        run_id=parent.record.run_id,
        parse_payload={
            "source_revision_ids": sorted(
                {item["source_revision_id"] for item in structured_sources}
            ),
            "structured_sources": structured_sources,
        },
        rule_set_version="28.1",
    )
    review = _review_phase(
        resolve_database_settings(workspace),
        run_id=parent.record.run_id,
        derive_payload=derive,
        automatic_policies=AUTO_POLICIES,
    )
    assert review["counters"]["auto_confirmed"] > 0
    assert review["counters"]["pending"] > 0

    merge = _merge_phase(
        resolve_database_settings(workspace),
        run_id=parent.record.run_id,
        derive_payload=derive,
        strict_review=False,
    )
    assert merge["counters"]["facts_created"] > 0
    assert merge["counters"]["relations_created"] > 0
    assert merge["counters"]["skipped_pending"] > 0

    temporal = _add_governed_temporal_evidence(
        workspace,
        run_id=parent.record.run_id,
        revisions=revisions,
    )
    v1 = render_dsl_snapshot(
        workspace,
        run_id=parent.record.run_id,
        schema_version="1",
        clock=lambda: FIXED_TIME,
    )
    v2 = render_dsl_snapshot(
        workspace,
        run_id=parent.record.run_id,
        schema_version="2",
        clock=lambda: FIXED_TIME,
    )
    cross = diff_dsl_snapshots(
        workspace,
        run_id=parent.record.run_id,
        from_snapshot_id=v1.snapshot_id,
        to_snapshot_id=v2.snapshot_id,
        cross_schema=True,
    )
    cross_payload = json.loads((workspace / cross.json_path).read_text(encoding="utf-8"))
    graph = export_gexf_from_snapshot(
        workspace,
        run_id=parent.record.run_id,
        snapshot_id=v2.snapshot_id,
        options=GraphExportOptions(dynamic=True),
    )
    graph_text = (workspace / graph.graph_path).read_text(encoding="utf-8")
    validation = validate_dynamic_gexf(graph_text)
    assert validation.xsd_valid is True
    assert validation.semantic_valid is True
    complete_run(
        workspace,
        parent.record.run_id,
        output_payload={"slice": 28, "status": "completed"},
        clock=lambda: FIXED_TIME,
    )

    with _connect(workspace) as connection:
        batch_semantics = [
            dict(row)
            for row in connection.execute(
                """
                SELECT origin_type, origin_ref, total_records, accepted_count,
                       rejected_count, status
                FROM candidate_batches
                ORDER BY origin_type, origin_ref, total_records, accepted_count,
                         rejected_count, status
                """
            ).fetchall()
        ]
        decision_hashes = [
            str(row[0])
            for row in connection.execute(
                "SELECT semantic_payload_hash FROM review_decisions "
                "ORDER BY semantic_payload_hash"
            ).fetchall()
        ]
    candidate_hashes = sorted(
        hash_value
        for item in derive["items"]
        for hash_value in item["payload_hashes"]
    )
    rules = sorted(item["rule"] for item in derive["items"])
    return {
        "candidates": {
            "batch_count": derive["counters"]["batches"],
            "batch_set_hash": canonical_sha256_v1(batch_semantics),
            "decision_count": len(decision_hashes),
            "decision_set_hash": canonical_sha256_v1(decision_hashes),
            "payload_count": len(candidate_hashes),
            "payload_set_hash": canonical_sha256_v1(candidate_hashes),
            "review_auto_confirmed": review["counters"]["auto_confirmed"],
            "review_pending": review["counters"]["pending"],
            "rules": rules,
        },
        "dsl": {
            "cross_schema_categories": cross_payload["summary"]["categories"],
            "cross_schema_total_changes": cross.total_changes,
            "v1_hash": v1.dsl_hash,
            "v2_hash": v2.dsl_hash,
        },
        "gexf": {
            "edge_count": validation.edge_count,
            "graph_hash": graph.graph_hash,
            "node_count": validation.node_count,
            "semantic_valid": validation.semantic_valid,
            "timeformat": validation.timeformat,
            "xsd_valid": validation.xsd_valid,
        },
        "merge": {
            "facts_created": merge["counters"]["facts_created"],
            "relations_created": merge["counters"]["relations_created"],
            "skipped_pending": merge["counters"]["skipped_pending"],
        },
        "normalization": {
            "macro": _normalization_projection(workspace, macro_output),
            "main": _normalization_projection(workspace, main_output),
        },
        "parsers": parser_projection,
        "sources": {
            "active_count": first_scan.added,
            "content_hash": canonical_sha256_v1(
                sorted(
                    item["sha256"]
                    for path, item in json.loads(CHECKSUMS.read_text(encoding="utf-8"))[
                        "files"
                    ].items()
                    if path.startswith("corpus/active/")
                )
            ),
            "second_scan_unchanged": second_scan.unchanged,
        },
        "temporal": temporal,
    }


def _workspace_with_tree(root: Path) -> Path:
    workspace = root / "workspace"
    initialize_workspace(workspace)
    migrate_workspace_database(workspace, clock=lambda: FIXED_TIME)
    shutil.copytree(ACTIVE, workspace / "corpus" / "active", dirs_exist_ok=True)
    return workspace


def _workspace_with_files(root: Path, files: dict[str, Path]) -> Path:
    workspace = root / "workspace"
    initialize_workspace(workspace)
    migrate_workspace_database(workspace, clock=lambda: FIXED_TIME)
    for relative, source in files.items():
        destination = workspace / "corpus" / "active" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    scan_corpus(workspace, clock=lambda: FIXED_TIME)
    return workspace


def _normalize_and_persist(
    workspace: Path,
    relative: str,
    *,
    persist: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    settings = resolve_database_settings(workspace)
    file_path = f"corpus/active/{relative}"
    with open_database(settings.database_path, enable_wal=settings.wal_enabled) as connection:
        row = connection.execute(
            "SELECT source_id, source_revision_id, content_hash FROM source_revisions "
            "WHERE file_path = ?",
            (file_path,),
        ).fetchone()
        assert row is not None
        seed = load_fragment_id_seed(connection, str(row["source_revision_id"]))
    output = normalize_docling.normalize(
        {
            "run_id": f"RUN_SLICE28_{row['source_id']}",
            "source_id": str(row["source_id"]),
            "source_revision_id": str(row["source_revision_id"]),
            "input_path": file_path,
            "output_dir": f"normalized/{row['source_id']}/{row['source_revision_id']}",
            "profile": "docling.no_images",
            "worker_config": {"name": "normalize_docling", "version": "1.0"},
            "docling_options": {"input_formats": "xlsx,xlsm"},
            "expected_source_hash": str(row["content_hash"]),
            "excel_limits": dict(DEFAULT_CONFIG["excel"]),
            "fragment_id_by_sequence": seed.fragment_id_by_sequence,
            "next_fragment_number": seed.next_fragment_number,
            "memory_limit_mode": "slice28_test",
        },
        workspace_dir=workspace,
    )
    manifest = json.loads((workspace / output["workbook_manifest_path"]).read_text(encoding="utf-8"))
    if persist:
        with open_database(settings.database_path, enable_wal=settings.wal_enabled) as connection:
            connection.execute("BEGIN")
            persist_workbook_output(
                connection,
                workspace_dir=workspace,
                output=output,
                expected_source_id=str(row["source_id"]),
                expected_source_revision_id=str(row["source_revision_id"]),
                expected_source_hash=str(row["content_hash"]),
                timestamp=FIXED_TIME.isoformat(),
            )
            connection.commit()
    return output, manifest


def _add_governed_temporal_evidence(
    workspace: Path,
    *,
    run_id: str,
    revisions: dict[str, str],
) -> dict[str, Any]:
    with _connect(workspace) as connection:
        fact_ids = [
            str(row[0])
            for row in connection.execute("SELECT fact_id FROM facts ORDER BY fact_id LIMIT 2")
        ]
    assert len(fact_ids) == 2
    current_revision = revisions[CURRENT_REQUIREMENTS]
    addendum_revision = revisions[CURRENT_ADDENDUM]
    historical_revision = revisions[HISTORICAL_MANUAL]

    _persist_date(workspace, current_revision, fact_ids[0], "2025-11-18", "markdown_declaration")
    _persist_date(workspace, addendum_revision, fact_ids[0], "2025-11-18", "text_declaration")
    concordant = consolidate_temporal_evidence(
        workspace,
        run_id=run_id,
        target_subject_type="fact",
        target_subject_id=fact_ids[0],
        clock=lambda: FIXED_TIME,
    )
    assert concordant.assessment == "concordant"
    assert len(concordant.candidate_record_ids) == 1
    with _connect(workspace) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM review_subject_heads WHERE subject_type = 'candidate_record' "
            "AND subject_id = ?",
            (concordant.candidate_record_ids[0],),
        ).fetchone()[0] == 0
    CandidateReviewService(workspace, clock=lambda: FIXED_TIME).confirm(
        concordant.candidate_record_ids[0],
        actor_id="aurora-temporal-reviewer",
        reason="due dichiarazioni indipendenti concordanti verificate",
        idempotency_key="slice28:temporal:concordant",
        run_id=run_id,
    )

    _persist_date(workspace, historical_revision, fact_ids[1], "2012-06-01", "text_declaration")
    _persist_date(workspace, current_revision, fact_ids[1], "2025-11-18", "markdown_declaration")
    conflicted = consolidate_temporal_evidence(
        workspace,
        run_id=run_id,
        target_subject_type="fact",
        target_subject_id=fact_ids[1],
        clock=lambda: FIXED_TIME,
    )
    assert conflicted.assessment == "conflicted"
    assert conflicted.conflict_id is not None
    with _connect(workspace) as connection:
        conflict_status = str(
            connection.execute(
                "SELECT status FROM temporal_conflicts WHERE conflict_id = ?",
                (conflicted.conflict_id,),
            ).fetchone()[0]
        )
        conflicted_intervals = int(
            connection.execute(
                "SELECT COUNT(*) FROM temporal_intervals WHERE subject_type = 'fact' "
                "AND subject_id = ?",
                (fact_ids[1],),
            ).fetchone()[0]
        )
        pending_conflict_candidates = int(
            connection.execute(
                """
                SELECT COUNT(*)
                FROM candidate_records cr
                LEFT JOIN review_subject_heads h
                  ON h.subject_type = 'candidate_record'
                 AND h.subject_id = cr.candidate_record_id
                WHERE cr.candidate_record_id IN ({}) AND h.subject_id IS NULL
                """.format(",".join("?" for _ in conflicted.candidate_record_ids)),
                conflicted.candidate_record_ids,
            ).fetchone()[0]
        )
    assert conflict_status == "open"
    assert conflicted_intervals == 0
    assert pending_conflict_candidates == len(conflicted.candidate_record_ids)
    return {
        "concordant_assessment": concordant.assessment,
        "concordant_group_hash": concordant.group_hash,
        "conflict_assessment": conflicted.assessment,
        "conflict_group_hash": conflicted.group_hash,
        "conflict_status": conflict_status,
        "conflicted_intervals": conflicted_intervals,
        "pending_conflict_candidates": pending_conflict_candidates,
    }


def _persist_date(
    workspace: Path,
    source_revision_id: str,
    fact_id: str,
    value: str,
    source_format: str,
) -> None:
    record = {
        "extraction_method": "declared_content_temporality",
        "extraction_version": "1",
        "initial_reliability": "high",
        "precision": "day",
        "raw_value": value,
        "source_format": source_format,
        "source_fragment_id": None,
        "source_key": "content:valid_from",
        "source_revision_id": source_revision_id,
        "target_subject_id": fact_id,
        "target_subject_type": "fact",
        "timezone_status": "unknown",
        "timezone_value": None,
        "warnings": ["declared_content_requires_review"],
    }
    persist_temporal_evidence_records(
        workspace,
        source_revision_id=source_revision_id,
        target_subject_type="fact",
        target_subject_id=fact_id,
        records=[record],
        clock=lambda: FIXED_TIME,
    )


def _assert_main_workbook(manifest: dict[str, Any]) -> None:
    assert [sheet["name"] for sheet in manifest["sheets"]] == ["Résumé", "隐 藏", "非常"]
    assert [sheet["visibility"] for sheet in manifest["sheets"]] == [
        "visible",
        "hidden",
        "very_hidden",
    ]
    assert sum(len(sheet["regions"]) for sheet in manifest["sheets"]) == 5
    assert sum(len(sheet["cells"]) for sheet in manifest["sheets"]) == 21
    assert manifest["sheets"][0]["merged_ranges"] == ["A3:B3"]
    assert len(manifest["named_ranges"]) == 2
    assert {cell["type"] for sheet in manifest["sheets"] for cell in sheet["cells"]} == {
        "blank",
        "bool",
        "date",
        "error",
        "number",
        "string",
    }
    cells = {
        cell["coordinate"]: cell
        for sheet in manifest["sheets"]
        for cell in sheet["cells"]
    }
    assert cells["D2"]["formula"] == "B2+C2"
    assert cells["D2"]["cached_value"] == "3.5"
    assert cells["E2"]["formula"] == "B2*C2"
    assert cells["E2"]["cached_value"] is None
    assert manifest["external_links"] == [
        {
            "source_part": "xl/externalLinks/externalLink1.xml",
            "relationship_id": "rId1",
            "target": "https://example.invalid/external.xlsx",
            "disposition": "not_dereferenced",
        }
    ]


def _normalization_projection(workspace: Path, output: dict[str, Any]) -> dict[str, Any]:
    required_keys = (
        "normalized_json_path",
        "normalized_markdown_path",
        "workbook_manifest_path",
        "workbook_fragments_path",
        "workbook_report_path",
    )
    for key in required_keys:
        assert (workspace / output[key]).is_file()
    report = json.loads((workspace / output["workbook_report_path"]).read_text(encoding="utf-8"))
    assert report["network_accessed"] is False
    assert report["macros_executed"] is False
    return {
        "artifact_names": sorted(Path(output[key]).name for key in required_keys),
        "fragments_hash": output["workbook_fragments_hash"],
        "manifest_hash": output["workbook_manifest_hash"],
        "normalized_hash": output["normalized_hash"],
        "normalized_json_sha256": _sha256(workspace / output["normalized_json_path"]),
        "normalized_markdown_sha256": _sha256(workspace / output["normalized_markdown_path"]),
        "status": output["status"],
        "workbook_report_sha256": _sha256(workspace / output["workbook_report_path"]),
    }


def _build_manifest(path: Path, *, limits: ExcelLimits):
    source_hash = _sha256(path)
    acquired = acquire_source_once(
        path,
        expected_hash=source_hash,
        max_file_bytes=limits.max_file_bytes,
    )
    checked = preflight_ooxml(
        acquired.cursor(),
        original_name=path.name,
        source_hash=source_hash,
        limits=limits,
    )
    return build_workbook_manifest(
        acquired.cursor(),
        preflight=checked,
        source_revision_id="REV_SLICE28_BUDGET",
        fragment_id_by_sequence={},
        next_fragment_number=1,
    )


def _successful_excel_normalization(
    _stream: io.BytesIO,
    *,
    original_name: str,
    docling_options: dict[str, Any],
) -> DoclingNormalizationResult:
    return _fake_normalization(original_name, docling_options, "success")


def _partial_excel_normalization(
    _stream: io.BytesIO,
    *,
    original_name: str,
    docling_options: dict[str, Any],
) -> DoclingNormalizationResult:
    return _fake_normalization(original_name, docling_options, "partial_success")


def _fake_normalization(
    original_name: str,
    docling_options: dict[str, Any],
    conversion_status: str,
) -> DoclingNormalizationResult:
    return DoclingNormalizationResult(
        markdown=f"# Aurora workbook\n\nSource: `{original_name}`\n",
        document={
            "name": original_name,
            "schema_name": "DoclingDocument",
            "text": "Aurora workbook normalization fixture",
        },
        docling_version="2.97.0",
        resolved_options={"input_formats": ["XLSX"], **docling_options},
        conversion_status=conversion_status,
    )


def _revisions_by_path(workspace: Path) -> dict[str, str]:
    with _connect(workspace) as connection:
        rows = connection.execute(
            "SELECT file_path, source_revision_id FROM source_revisions ORDER BY file_path"
        ).fetchall()
    prefix = "corpus/active/"
    return {
        str(row["file_path"])[len(prefix) :]: str(row["source_revision_id"])
        for row in rows
        if str(row["file_path"]).startswith(prefix)
    }


def _candidate_state(workspace: Path) -> dict[str, Any]:
    with _connect(workspace) as connection:
        candidates = [
            str(row[0])
            for row in connection.execute(
                "SELECT candidate_id FROM candidate_records ORDER BY candidate_id"
            )
        ]
        evidence = [
            str(row[0])
            for row in connection.execute(
                "SELECT evidence_hash FROM raw_temporal_evidence ORDER BY evidence_hash"
            )
        ]
        groups = [
            str(row[0])
            for row in connection.execute(
                "SELECT group_hash FROM temporal_evidence_groups ORDER BY group_hash"
            )
        ]
    return {
        "candidate_hash": canonical_sha256_v1(candidates),
        "candidate_count": len(candidates),
        "evidence_hash": canonical_sha256_v1(evidence),
        "group_hash": canonical_sha256_v1(groups),
    }


def _connect(workspace: Path):
    settings = resolve_database_settings(workspace)
    return open_database(settings.database_path, enable_wal=settings.wal_enabled)


def _forbid_network(monkeypatch) -> None:
    def reject(*_args, **_kwargs):
        raise AssertionError("Slice 28 must not access the network")

    monkeypatch.setattr(socket, "create_connection", reject)
    monkeypatch.setattr(urllib.request, "urlopen", reject)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
