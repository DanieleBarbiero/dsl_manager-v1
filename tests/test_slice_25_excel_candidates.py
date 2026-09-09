from __future__ import annotations

import hashlib
import io
import json
import shutil
import socket
import urllib.request
from pathlib import Path
from typing import Any

from dsl_mngr.core.batch import BatchResult
from dsl_mngr.core.batch_consolidation import _derive_phase, _parse_payload, _review_phase
from dsl_mngr.core.candidate_derivation import (
    EXCEL_DERIVATION_RULE_CATALOG,
    _load_rule_fragments,
    derive_candidates,
    derive_rule_records,
)
from dsl_mngr.core.candidate_review import CandidateReviewService
from dsl_mngr.core.candidate_validation import validate_candidate_payload
from dsl_mngr.core.canonical import canonical_json_artifact_v1, canonical_json_v1
from dsl_mngr.core.config import DEFAULT_CONFIG
from dsl_mngr.core.database import open_database, resolve_database_settings
from dsl_mngr.core.fragment_registry import load_fragment_id_seed
from dsl_mngr.core.merge import merge_candidate_batches
from dsl_mngr.core.migrations import migrate_workspace_database
from dsl_mngr.core.ooxml_preflight import (
    ExcelLimits,
    acquire_source_once,
    build_workbook_manifest,
    preflight_ooxml,
)
from dsl_mngr.core.runs import complete_run, start_run
from dsl_mngr.core.source_registry import scan_corpus
from dsl_mngr.core.workbook_registry import persist_workbook_output
from dsl_mngr.core.workspace import initialize_workspace


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "slice_25"
WORKBOOK = FIXTURE_DIR / "candidate_workbook.xlsx"
CHECKSUMS = json.loads((FIXTURE_DIR / "checksums.json").read_text(encoding="utf-8"))
EXPECTED = Path(__file__).parent / "expected" / "expected_slice_25_excel_candidates.json"
RULES = tuple(EXCEL_DERIVATION_RULE_CATALOG)
AUTO_POLICIES = tuple(
    contract.automatic_review_policy
    for contract in EXCEL_DERIVATION_RULE_CATALOG.values()
)


def test_slice_25_excel_candidates(tmp_path, monkeypatch):
    def reject_network(*_args, **_kwargs):
        raise AssertionError("Slice 25 must not access the network")

    monkeypatch.setattr(socket, "create_connection", reject_network)
    monkeypatch.setattr(urllib.request, "urlopen", reject_network)
    assert hashlib.sha256(WORKBOOK.read_bytes()).hexdigest() == CHECKSUMS[WORKBOOK.name]
    assert RULES == (
        "excel_workbook_fact/1",
        "excel_sheet_fact/1",
        "excel_region_fact/1",
        "excel_named_range_fact/1",
        "excel_table_fact/1",
        "excel_explicit_reference/1",
    )
    assert all(
        contract.rule_version == "1"
        and contract.parser_kind == "workbook_manifest"
        and contract.default_review_state == "pending"
        for contract in EXCEL_DERIVATION_RULE_CATALOG.values()
    )

    workspace, revision_id, manifest = _registered_workspace(tmp_path / "workspace")
    settings = resolve_database_settings(workspace)
    assert [sheet["visibility"] for sheet in manifest["sheets"]] == [
        "visible",
        "hidden",
        "very_hidden",
    ]
    assert len(manifest["tables"]) == 1
    assert manifest["tables"][0]["display_name"] == "Orders"
    assert len(manifest["external_links"]) == 1
    assert manifest["external_links"][0]["disposition"] == "not_dereferenced"
    formula_cells = {
        cell["coordinate"]: cell
        for sheet in manifest["sheets"]
        for cell in sheet["cells"]
        if cell.get("formula") is not None
    }
    assert formula_cells["H1"]["formula"] == "SUM(Orders[Amount])"
    assert formula_cells["H1"]["cached_value"] == "30"
    assert formula_cells["H7"]["cached_value"] == "41"

    parsed = _parse_payload(
        BatchResult(
            run_id="RUN_PARSE",
            run_type="batch",
            batch_command="process-dir",
            status="completed",
            stop_on_error=False,
            summary={"total": 1, "completed": 1, "failed": 0, "skipped": 0},
            items=(
                {
                    "kind": "normalize",
                    "outputs": {"is_excel": True},
                    "source_revision_id": revision_id,
                    "status": "completed",
                },
            ),
            report_path="artifacts/RUN_PARSE/batch_report.json",
        )
    )
    assert parsed["structured_sources"] == [
        {"kind": "normalize_excel", "source_revision_id": revision_id}
    ]

    parent = start_run(
        workspace,
        run_type="batch",
        input_payload={"slice": 25},
    )
    derive_payload = _derive_phase(
        settings,
        run_id=parent.record.run_id,
        parse_payload={
            "structured_sources": [
                {"kind": "normalize_excel", "source_revision_id": revision_id}
            ]
        },
        rule_set_version="25.1",
    )
    assert [item["rule"] for item in derive_payload["items"]] == sorted(RULES)
    assert derive_payload["counters"]["batches"] == len(RULES)
    assert derive_payload["counters"]["rejected"] == 0

    batches = {item["rule"]: item["batch_id"] for item in derive_payload["items"]}
    candidates = {
        rule: _batch_payloads(workspace, batch_id)
        for rule, batch_id in batches.items()
    }
    all_candidates = [candidate for records in candidates.values() for candidate in records]
    assert all_candidates
    assert all(candidate["producer_type"] == "deterministic_rule" for candidate in all_candidates)
    assert all(
        set(
            (
                "coordinate",
                "fragment_id",
                "manifest_id",
                "part_name",
                "sheet_name",
                "source_revision_id",
            )
        ).issubset(candidate["evidence_locator"])
        for candidate in all_candidates
    )
    assert all(candidate["fragment_id"] for candidate in all_candidates)
    assert all(candidate["evidence_text"] for candidate in all_candidates)
    assert _count(workspace, "facts") == 0
    assert _count(workspace, "relations") == 0
    assert _count(workspace, "review_decisions") == 0
    assert _count(workspace, "candidate_lineage") == len(all_candidates)
    assert _batch_origins(workspace, tuple(batches.values())) == {
        "deterministic_derivation"
    }

    sheet_candidates = candidates["excel_sheet_fact/1"]
    visibility = {
        candidate["technical_attributes"]["sheet_name"]:
        candidate["technical_attributes"]["visibility"]
        for candidate in sheet_candidates
    }
    assert visibility == {
        "Hidden": "hidden",
        "Main": "visible",
        "VeryHidden": "very_hidden",
    }
    assert all(candidate["property_value"] == "excel_sheet" for candidate in sheet_candidates)

    region_candidates = candidates["excel_region_fact/1"]
    main_blocks = [
        candidate
        for candidate in region_candidates
        if candidate["evidence_locator"]["sheet_name"] == "Main"
        and candidate["evidence_locator"]["coordinate"] in {"A1:B3", "E1:F3"}
    ]
    assert len(main_blocks) == 2
    assert main_blocks[0]["candidate_id"] != main_blocks[1]["candidate_id"]
    assert _cell_values(main_blocks[0]) == _cell_values(main_blocks[1])

    named_candidates = candidates["excel_named_range_fact/1"]
    local_ranges = [
        candidate
        for candidate in named_candidates
        if candidate["technical_attributes"]["name"] == "LocalBlock"
    ]
    assert {(item["technical_attributes"]["scope"], item["evidence_locator"]["coordinate"]) for item in local_ranges} == {
        ("sheet", "E2:F3"),
        ("workbook", "A2:B3"),
    }

    references = candidates["excel_explicit_reference/1"]
    reference_kinds = {
        candidate["technical_attributes"]["reference_kind"] for candidate in references
    }
    assert reference_kinds == {"named_range", "region", "table"}
    assert any(
        candidate["technical_attributes"]["reference_kind"] == "named_range"
        and "/named_range:sheet:Main:LocalBlock" in candidate["target_entity"]
        for candidate in references
    )
    assert not any(
        "external.xlsx" in canonical_json_v1(
            {
                "source": candidate["source_entity"],
                "target": candidate["target_entity"],
            }
        )
        for candidate in references
    )

    semantic_values = {
        str(candidate.get("property_value"))
        for candidate in all_candidates
        if candidate["record_type"] == "candidate_fact"
    }
    assert semantic_values == {
        "excel_named_range",
        "excel_region",
        "excel_sheet",
        "excel_table",
        "excel_workbook",
    }
    assert "Code" in canonical_json_v1(
        [candidate["technical_attributes"] for candidate in region_candidates]
    )
    assert "SUM(Orders[Amount])" in canonical_json_v1(
        [candidate["technical_attributes"] for candidate in region_candidates]
    )

    with open_database(settings.database_path, enable_wal=settings.wal_enabled) as connection:
        raw_inputs = _load_rule_fragments(
            connection,
            EXCEL_DERIVATION_RULE_CATALOG["excel_region_fact/1"],
            revision_id,
            workspace,
        )
        forward, forward_issues = derive_rule_records("excel_region_fact/1", raw_inputs)
        reversed_records, reversed_issues = derive_rule_records(
            "excel_region_fact/1", reversed(raw_inputs)
        )
        assert forward == reversed_records
        assert forward_issues == reversed_issues == []

        missing_evidence = dict(forward[0])
        missing_evidence["fragment_id"] = "FRAG_999999"
        failure = validate_candidate_payload(connection, missing_evidence)
        assert failure is not None
        assert failure.reason == "unknown_fragment"

    first_region_item = next(
        item for item in derive_payload["items"] if item["rule"] == "excel_region_fact/1"
    )
    repeated_run = start_run(
        workspace,
        run_type="candidate_derivation",
        parent_run_id=parent.record.run_id,
        input_payload={"rule": "excel_region_fact/1", "source_revision_id": revision_id},
    )
    repeated = derive_candidates(
        workspace,
        run_id=repeated_run.record.run_id,
        source_revision_id=revision_id,
        rule="excel_region_fact/1",
        rule_set_version="25.1",
    )
    complete_run(workspace, repeated_run.record.run_id, output_payload=repeated.to_payload())
    assert list(repeated.candidate_ids) == first_region_item["candidate_ids"]
    assert list(repeated.payload_hashes) == first_region_item["payload_hashes"]
    assert repeated.semantic_report_hash == first_region_item["semantic_report_hash"]
    assert _record_ids(workspace, repeated.batch_id).isdisjoint(
        _record_ids(workspace, first_region_item["batch_id"])
    )

    projection = _golden_projection(manifest, candidates)
    if not EXPECTED.is_file():
        raise AssertionError(json.dumps(projection, ensure_ascii=False, indent=2, sort_keys=True))
    assert projection == json.loads(EXPECTED.read_text(encoding="utf-8"))

    review_payload = _review_phase(
        settings,
        run_id=parent.record.run_id,
        derive_payload=derive_payload,
        automatic_policies=AUTO_POLICIES,
    )
    fact_count = sum(
        len(records)
        for rule, records in candidates.items()
        if EXCEL_DERIVATION_RULE_CATALOG[rule].candidate_record_type == "candidate_fact"
    )
    assert review_payload["counters"]["auto_confirmed"] == fact_count
    assert review_payload["counters"]["pending"] == len(references)
    assert {
        item["reason"]
        for item in review_payload["items"]
        if item["outcome"] == "pending"
    } == {"automatic_review_not_allowed"}
    assert _count(workspace, "facts") == 0
    assert _count(workspace, "relations") == 0

    merge_run = start_run(
        workspace,
        run_type="merge",
        parent_run_id=parent.record.run_id,
        input_payload={"batch_ids": list(batches.values())},
    )
    merged = merge_candidate_batches(
        workspace,
        run_id=merge_run.record.run_id,
        batch_ids=tuple(batches.values()),
    )
    assert merged.status == "completed"
    assert merged.facts_created == fact_count
    assert merged.relations_created == 0
    assert merged.skipped_pending == len(references)
    assert _count(workspace, "facts") == fact_count
    assert _count(workspace, "relations") == 0

    pending_record = _candidate_record_ids(
        workspace, batches["excel_explicit_reference/1"]
    )[0]
    CandidateReviewService(workspace).confirm(pending_record, actor_id="slice25-reviewer")
    human_merge_run = start_run(
        workspace,
        run_type="merge",
        parent_run_id=parent.record.run_id,
        input_payload={"batch_ids": [batches["excel_explicit_reference/1"]]},
    )
    human_merged = merge_candidate_batches(
        workspace,
        run_id=human_merge_run.record.run_id,
        batch_ids=(batches["excel_explicit_reference/1"],),
    )
    assert human_merged.relations_created == 1
    assert _count(workspace, "relations") == 1


def _registered_workspace(path: Path) -> tuple[Path, str, dict[str, Any]]:
    initialize_workspace(path)
    migrate_workspace_database(path)
    source_path = path / "corpus" / "active" / WORKBOOK.name
    shutil.copyfile(WORKBOOK, source_path)
    scan_corpus(path)
    settings = resolve_database_settings(path)
    connection = open_database(settings.database_path, enable_wal=settings.wal_enabled)
    try:
        row = connection.execute(
            "SELECT source_id, source_revision_id, content_hash FROM source_revisions"
        ).fetchone()
        assert row is not None
        source_id = str(row["source_id"])
        revision_id = str(row["source_revision_id"])
        source_hash = str(row["content_hash"])
        seed = load_fragment_id_seed(connection, revision_id)
    finally:
        connection.close()

    limits = ExcelLimits.from_config(dict(DEFAULT_CONFIG["excel"]))
    acquired = acquire_source_once(
        source_path,
        expected_hash=source_hash,
        max_file_bytes=limits.max_file_bytes,
    )
    preflight = preflight_ooxml(
        acquired.cursor(),
        original_name=source_path.name,
        source_hash=source_hash,
        limits=limits,
    )
    built = build_workbook_manifest(
        acquired.cursor(),
        preflight=preflight,
        source_revision_id=revision_id,
        fragment_id_by_sequence=seed.fragment_id_by_sequence,
        next_fragment_number=seed.next_fragment_number,
    )
    output_dir = path / "normalized" / source_id / revision_id
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "workbook_manifest.json"
    fragments_path = output_dir / "workbook_fragments.jsonl"
    report_path = output_dir / "workbook_report.json"
    manifest_path.write_text(built.manifest_json, encoding="utf-8", newline="\n")
    fragments_path.write_text(built.fragments_jsonl, encoding="utf-8", newline="\n")
    report_path.write_text(canonical_json_artifact_v1({"status": "completed"}), encoding="utf-8")
    output = {
        "source_id": source_id,
        "source_revision_id": revision_id,
        "source_hash": source_hash,
        "status": "completed",
        "workbook_cell_count": built.cell_count,
        "workbook_fragment_count": len(built.fragments),
        "workbook_fragments_hash": built.fragments_hash,
        "workbook_fragments_path": fragments_path.relative_to(path).as_posix(),
        "workbook_manifest_hash": built.manifest_hash,
        "workbook_manifest_path": manifest_path.relative_to(path).as_posix(),
        "workbook_region_count": built.region_count,
        "workbook_report_path": report_path.relative_to(path).as_posix(),
        "workbook_sheet_count": len(built.manifest["sheets"]),
    }
    connection = open_database(settings.database_path, enable_wal=settings.wal_enabled)
    try:
        connection.execute("BEGIN")
        persist_workbook_output(
            connection,
            workspace_dir=path,
            output=output,
            expected_source_id=source_id,
            expected_source_revision_id=revision_id,
            expected_source_hash=source_hash,
            timestamp="2026-09-04T12:00:00+00:00",
        )
        connection.commit()
    finally:
        connection.close()
    return path, revision_id, built.manifest


def _batch_payloads(workspace: Path, batch_id: str) -> list[dict[str, Any]]:
    settings = resolve_database_settings(workspace)
    with open_database(settings.database_path, enable_wal=settings.wal_enabled) as connection:
        rows = connection.execute(
            "SELECT payload_json FROM candidate_records WHERE batch_id = ? "
            "ORDER BY line_number, candidate_record_id",
            (batch_id,),
        ).fetchall()
    return [json.loads(row["payload_json"]) for row in rows]


def _candidate_record_ids(workspace: Path, batch_id: str) -> list[str]:
    settings = resolve_database_settings(workspace)
    with open_database(settings.database_path, enable_wal=settings.wal_enabled) as connection:
        rows = connection.execute(
            "SELECT candidate_record_id FROM candidate_records WHERE batch_id = ? "
            "ORDER BY line_number, candidate_record_id",
            (batch_id,),
        ).fetchall()
    return [str(row["candidate_record_id"]) for row in rows]


def _record_ids(workspace: Path, batch_id: str) -> set[str]:
    return set(_candidate_record_ids(workspace, batch_id))


def _count(workspace: Path, table: str) -> int:
    assert table in {
        "candidate_lineage",
        "facts",
        "relations",
        "review_decisions",
    }
    settings = resolve_database_settings(workspace)
    with open_database(settings.database_path, enable_wal=settings.wal_enabled) as connection:
        return int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def _batch_origins(workspace: Path, batch_ids: tuple[str, ...]) -> set[str]:
    settings = resolve_database_settings(workspace)
    placeholders = ", ".join("?" for _ in batch_ids)
    with open_database(settings.database_path, enable_wal=settings.wal_enabled) as connection:
        rows = connection.execute(
            f"SELECT origin_type FROM candidate_batches WHERE batch_id IN ({placeholders})",
            batch_ids,
        ).fetchall()
    return {str(row["origin_type"]) for row in rows}


def _cell_values(candidate: dict[str, Any]) -> list[tuple[str, str]]:
    return [
        (str(cell["type"]), str(cell["value"]))
        for cell in candidate["technical_attributes"]["cell_attributes"]
    ]


def _golden_projection(
    manifest: dict[str, Any],
    candidates: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    return {
        "manifest": {
            "external_links": len(manifest["external_links"]),
            "named_ranges": [
                [item["scope"], item["sheet_name"], item["name"], item["refers_to"]]
                for item in manifest["named_ranges"]
            ],
            "sheets": [
                [sheet["index"], sheet["name"], sheet["visibility"]]
                for sheet in manifest["sheets"]
            ],
            "tables": [
                [item["sheet_name"], item["display_name"], item["refers_to"]]
                for item in manifest["tables"]
            ],
        },
        "rules": {
            rule: {
                "automatic_review_allowed": EXCEL_DERIVATION_RULE_CATALOG[
                    rule
                ].automatic_review_allowed,
                "automatic_review_policy": EXCEL_DERIVATION_RULE_CATALOG[
                    rule
                ].automatic_review_policy,
                "candidates": [
                    {
                        "candidate_id": candidate["candidate_id"],
                        "coordinate": candidate["evidence_locator"]["coordinate"],
                        "record_type": candidate["record_type"],
                        "semantic_type": candidate.get(
                            "fact_type", candidate.get("relation_type")
                        ),
                        "sheet_name": candidate["evidence_locator"]["sheet_name"],
                    }
                    for candidate in records
                ],
            }
            for rule, records in sorted(candidates.items())
        },
    }
