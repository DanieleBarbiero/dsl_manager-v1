from __future__ import annotations

import hashlib
import json
from pathlib import Path

from dsl_mngr.cli.app import main
from dsl_mngr.core.candidate_derivation import derive_candidates
from dsl_mngr.core.candidate_import import import_candidate_file
from dsl_mngr.core.candidate_review import CandidateReviewService
from dsl_mngr.core.dsl_renderer import render_dsl_snapshot
from dsl_mngr.core.graph_export import GraphExportOptions, export_gexf_from_snapshot
from dsl_mngr.core.merge import merge_candidate_batches
from dsl_mngr.core.reconciliation import reconcile_required
from dsl_mngr.core.runs import start_run
from tests.slice_27_test_support import connect, registered_workspace


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VEGA_ROOT = PROJECT_ROOT / ".kb" / "projects" / "laboratorio_vega_ricambi"
VEGA_CORPUS = VEGA_ROOT / "corpus" / "active"
VEGA_TUTOR = (
    VEGA_ROOT
    / "materiale_di_supporto"
    / "laboratorio_vega_ricambi_interattivo_v_13.ps1"
)
VEGA_SOURCES = (
    VEGA_CORPUS / "database" / "schema_vega.sql",
    VEGA_CORPUS / "documenti" / "manuale_operativo_vega_2026.docx",
    VEGA_CORPUS / "documenti" / "matrice_priorita_vega_2026.xlsx",
    VEGA_CORPUS / "forms" / "frm_richiesta.xml",
    VEGA_CORPUS / "logs" / "vega_2026.log",
    VEGA_CORPUS / "plsql" / "logica_vega.sql",
)


def test_slice_32_vega_import_review_merge_reconcile_render(tmp_path, capsys):
    hashes_before = {path: _sha256(path) for path in VEGA_SOURCES}
    checksum_manifest = json.loads(
        (VEGA_ROOT / "materiale_di_supporto" / "checksums.json").read_text(
            encoding="utf-8"
        )
    )["files"]
    assert {
        path.relative_to(VEGA_CORPUS).as_posix(): digest
        for path, digest in hashes_before.items()
    } == checksum_manifest
    files = {
        path.relative_to(VEGA_CORPUS).as_posix(): path.read_bytes()
        for path in VEGA_SOURCES
    }
    workspace, parent_run_id, revisions = registered_workspace(tmp_path, files)

    parse_commands = (
        ("parse-ddl", revisions["schema_vega.sql"]),
        ("parse-db-code", revisions["logica_vega.sql"]),
        ("parse-xml-form", revisions["frm_richiesta.xml"]),
        ("parse-log", revisions["vega_2026.log"]),
    )
    for command, revision_id in parse_commands:
        assert main(["corpus", command, str(workspace), "--revision", revision_id]) == 0
        capsys.readouterr()

    rules = (
        ("ddl_table_fact/1", revisions["schema_vega.sql"]),
        ("ddl_column_fact/1", revisions["schema_vega.sql"]),
        ("db_code_unit/1", revisions["logica_vega.sql"]),
        ("db_code_dependency/2", revisions["logica_vega.sql"]),
        ("xml_form_structure/2", revisions["frm_richiesta.xml"]),
        ("xml_table_usage/2", revisions["frm_richiesta.xml"]),
        ("xml_button_operation/1", revisions["frm_richiesta.xml"]),
        ("log_event_observation/2", revisions["vega_2026.log"]),
    )
    batches: dict[str, str] = {}
    candidate_ids: dict[str, tuple[str, ...]] = {}
    for rule, revision_id in rules:
        run = start_run(
            workspace,
            run_type="candidate_derivation",
            parent_run_id=parent_run_id,
            input_payload={"rule": rule, "source_revision_id": revision_id},
        )
        result = derive_candidates(
            workspace,
            run_id=run.record.run_id,
            source_revision_id=revision_id,
            rule=rule,
            rule_set_version="2",
        )
        assert result.rejected == 0
        assert result.rejection_details == ()
        batches[rule] = result.batch_id
        candidate_ids[rule] = result.candidate_ids

    retry_run = start_run(
        workspace,
        run_type="candidate_derivation",
        parent_run_id=parent_run_id,
        input_payload={"rule": "log_event_observation/2", "retry": True},
    )
    retry = derive_candidates(
        workspace,
        run_id=retry_run.record.run_id,
        source_revision_id=revisions["vega_2026.log"],
        rule="log_event_observation/2",
        rule_set_version="2",
    )
    assert retry.candidate_ids == candidate_ids["log_event_observation/2"]

    with connect(workspace) as connection:
        payloads = {
            rule: [
                json.loads(row[0])
                for row in connection.execute(
                    "SELECT payload_json FROM candidate_records WHERE batch_id = ? "
                    "ORDER BY line_number",
                    (batch_id,),
                )
            ]
            for rule, batch_id in batches.items()
        }
    db_relations = payloads["db_code_dependency/2"]
    db_targets = {item["target_entity"] for item in db_relations}
    assert {
        "RICHIESTA_RICAMBIO.ID_RICHIESTA",
        "RICHIESTA_RICAMBIO.ID_ARTICOLO",
        "RICHIESTA_RICAMBIO.STATO",
        "ARTICOLO.QTA_DISPONIBILE",
        "ARTICOLO.ID_ARTICOLO",
    } <= db_targets
    assert not {
        "P_ID_RICHIESTA",
        "ARTICOLO.ID_RICHIESTA",
        "ARTICOLO.RICHIESTA_RICAMBIO",
        "NEW.STATO",
        "OLD.STATO",
    } & db_targets
    assert {item["resolution_status"] for item in db_relations} == {"resolved"}

    xml_structure = payloads["xml_form_structure/2"]
    xml_items = [item for item in xml_structure if item.get("source_element_kind") == "item"]
    assert len(xml_items) == 4
    assert {item["block_name"] for item in xml_items} == {"RICHIESTA_RICAMBIO"}
    item_mappings = [
        item
        for item in payloads["xml_table_usage/2"]
        if item.get("source_element_kind") == "item"
    ]
    assert {item["target_entity"] for item in item_mappings} == {
        "RICHIESTA_RICAMBIO.ID_RICHIESTA",
        "RICHIESTA_RICAMBIO.ID_ARTICOLO",
        "RICHIESTA_RICAMBIO.PRIORITA",
        "RICHIESTA_RICAMBIO.STATO",
    }
    assert {item["resolution_status"] for item in item_mappings} == {"resolved"}
    assert [
        (
            item["source_entity"],
            item["relation_type"],
            item["target_entity"],
            item["resolution_status"],
        )
        for item in payloads["xml_button_operation/1"]
    ] == [("FRM_RICHIESTA.BTN_PRENOTA", "calls", "PRC_PRENOTA_ARTICOLO", "resolved")]

    log_events = payloads["log_event_observation/2"]
    assert len(log_events) == 5
    assert len({item["entity_name"] for item in log_events}) == 5
    assert len({item["candidate_id"] for item in log_events}) == 5

    review = CandidateReviewService(workspace)
    with connect(workspace) as connection:
        records = [
            str(row[0])
            for row in connection.execute(
                "SELECT candidate_record_id FROM candidate_records WHERE batch_id IN "
                f"({','.join('?' for _ in batches)}) ORDER BY candidate_record_id",
                tuple(batches.values()),
            )
        ]
    for record_id in records:
        review.confirm(record_id, actor_id="slice-32-vega-reviewer")

    merge_run = start_run(
        workspace,
        run_type="merge",
        parent_run_id=parent_run_id,
        input_payload={"batch_ids": sorted(batches.values())},
    )
    merged = merge_candidate_batches(
        workspace,
        run_id=merge_run.record.run_id,
        batch_ids=tuple(batches.values()),
    )
    assert merged.status == "completed"
    assert merged.conflicts_created == 0
    with connect(workspace) as connection:
        assert connection.execute("SELECT COUNT(*) FROM conflicts").fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM facts WHERE fact_type = 'log_event'"
        ).fetchone()[0] == 5
        assert connection.execute(
            "SELECT COUNT(*) FROM relations WHERE relation_type = 'calls' "
            "AND source_entity = 'FRM_RICHIESTA.BTN_PRENOTA' "
            "AND target_entity = 'PRC_PRENOTA_ARTICOLO'"
        ).fetchone()[0] == 1

    with connect(workspace) as connection:
        retry_records = [
            str(row[0])
            for row in connection.execute(
                "SELECT candidate_record_id FROM candidate_records WHERE batch_id = ? "
                "ORDER BY candidate_record_id",
                (retry.batch_id,),
            )
        ]
    for record_id in retry_records:
        review.confirm(record_id, actor_id="slice-32-vega-retry-reviewer")
    retry_merge_run = start_run(
        workspace,
        run_type="merge",
        parent_run_id=retry_run.record.run_id,
        input_payload={"batch_ids": [retry.batch_id]},
    )
    retried_merge = merge_candidate_batches(
        workspace,
        run_id=retry_merge_run.record.run_id,
        batch_ids=(retry.batch_id,),
    )
    assert retried_merge.facts_created == 0
    assert retried_merge.facts_existing == 5
    with connect(workspace) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM facts WHERE fact_type = 'log_event'"
        ).fetchone()[0] == 5

    _exercise_ai_lifecycle(
        workspace,
        parent_run_id=parent_run_id,
        evidence_revision_id=revisions["vega_2026.log"],
    )

    tutor = VEGA_TUTOR.read_text(encoding="utf-8-sig")
    merge_position = tutor.index("'facts',\n                'merge'")
    reconcile_position = tutor.index("'facts',\n            'reconcile'")
    render_position = tutor.index("'dsl',\n            'render'")
    graph_position = tutor.index("'graph',\n            'export'")
    assert merge_position < reconcile_position < render_position < graph_position
    assert {path: _sha256(path) for path in VEGA_SOURCES} == hashes_before


def _exercise_ai_lifecycle(
    workspace: Path,
    *,
    parent_run_id: str,
    evidence_revision_id: str,
) -> None:
    with connect(workspace) as connection:
        evidence = connection.execute(
            "SELECT fragment_id, text FROM source_fragments "
            "WHERE source_revision_id = ? AND fragment_type = 'log_event' "
            "ORDER BY fragment_id LIMIT 1",
            (evidence_revision_id,),
        ).fetchone()
    assert evidence is not None
    candidates = (
        (
            "vega_ai_01.jsonl",
            [
                _ai_fact("AI_CONFIRMED_1", "AI.VEGA.1", "accepted", evidence_revision_id, evidence),
                _ai_fact("AI_PENDING", "AI.VEGA.PENDING", "pending", evidence_revision_id, evidence),
                _ai_fact("AI_REJECTED", "AI.VEGA.REJECTED", "rejected", evidence_revision_id, evidence),
            ],
        ),
        (
            "vega_ai_02.jsonl",
            [_ai_fact("AI_CONFIRMED_2", "AI.VEGA.2", "accepted", evidence_revision_id, evidence)],
        ),
    )
    ai_run = start_run(
        workspace,
        run_type="candidate_import",
        parent_run_id=parent_run_id,
        input_payload={"packages": [name for name, _ in candidates]},
    )
    imported_batches: list[str] = []
    record_ids: dict[str, str] = {}
    for package_number, (name, payloads) in enumerate(candidates, start=1):
        input_path = workspace / "ai" / "inbox" / name
        input_path.write_text(
            "".join(json.dumps(item, sort_keys=True) + "\n" for item in payloads),
            encoding="utf-8",
            newline="\n",
        )
        imported = import_candidate_file(
            workspace,
            run_id=ai_run.record.run_id,
            input_path=input_path,
            origin_type="ai_import",
            origin_ref=f"AIPKG_SLICE32_{package_number}",
        )
        assert imported.accepted_count == len(payloads)
        assert imported.rejected_count == 0
        imported_batches.append(imported.batch_id)
        with connect(workspace) as connection:
            for row in connection.execute(
                "SELECT candidate_id, candidate_record_id FROM candidate_records "
                "WHERE batch_id = ? ORDER BY line_number",
                (imported.batch_id,),
            ):
                record_ids[str(row["candidate_id"])] = str(row["candidate_record_id"])

    review = CandidateReviewService(workspace)
    review.confirm(record_ids["AI_CONFIRMED_1"], actor_id="slice-32-ai-reviewer")
    review.confirm(record_ids["AI_CONFIRMED_2"], actor_id="slice-32-ai-reviewer")
    review.reject(
        record_ids["AI_REJECTED"],
        actor_id="slice-32-ai-reviewer",
        reason="deliberate regression rejection",
    )
    with connect(workspace) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM effective_facts WHERE entity_name LIKE 'AI.VEGA.%'"
        ).fetchone()[0] == 0

    merge_run = start_run(
        workspace,
        run_type="merge",
        parent_run_id=ai_run.record.run_id,
        input_payload={"batch_ids": imported_batches},
    )
    merged = merge_candidate_batches(
        workspace,
        run_id=merge_run.record.run_id,
        batch_ids=tuple(imported_batches),
    )
    assert merged.status == "completed"
    assert merged.facts_created == 2
    assert merged.skipped_pending == 1
    assert merged.skipped_rejected == 1

    reconcile_run = start_run(
        workspace,
        run_type="reconciliation",
        parent_run_id=merge_run.record.run_id,
        input_payload={},
    )
    reconciled = reconcile_required(workspace, run_id=reconcile_run.record.run_id)
    assert reconciled.pending == 0
    render_run = start_run(
        workspace,
        run_type="dsl_render",
        parent_run_id=reconcile_run.record.run_id,
        input_payload={"schema_version": "2"},
    )
    rendered = render_dsl_snapshot(
        workspace,
        run_id=render_run.record.run_id,
        schema_version="2",
    )
    snapshot = json.loads((workspace / rendered.json_path).read_text(encoding="utf-8"))
    ai_entities = {item["name"] for item in snapshot["entities"] if item["name"].startswith("AI.VEGA.")}
    assert ai_entities == {"AI.VEGA.1", "AI.VEGA.2"}
    graph_run = start_run(
        workspace,
        run_type="gexf_export",
        parent_run_id=render_run.record.run_id,
        input_payload={"snapshot_id": rendered.snapshot_id, "dynamic": True},
    )
    exported = export_gexf_from_snapshot(
        workspace,
        run_id=graph_run.record.run_id,
        snapshot_id=rendered.snapshot_id,
        options=GraphExportOptions(dynamic=True, timeformat="date"),
    )
    assert (workspace / exported.graph_path).is_file()


def _ai_fact(candidate_id, entity_name, value, revision_id, evidence):
    return {
        "assertion_type": "ambiguous",
        "candidate_id": candidate_id,
        "chunk_id": None,
        "confidence": "low",
        "entity_name": entity_name,
        "evidence_text": str(evidence["text"]),
        "fact_type": "ai_observation",
        "fragment_id": str(evidence["fragment_id"]),
        "property_name": "status",
        "property_value": value,
        "record_type": "candidate_fact",
        "source_revision_id": revision_id,
    }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
