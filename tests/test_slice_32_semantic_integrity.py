from __future__ import annotations

import json
from pathlib import Path

import pytest

from dsl_mngr.cli.app import main
from dsl_mngr.core.candidate_derivation import derive_rule_records
from dsl_mngr.core.candidate_import import import_candidate_file
from dsl_mngr.core.candidate_review import CandidateReviewConflict, CandidateReviewService
from dsl_mngr.core.conflict_semantics import (
    EVENT,
    MULTI_VALUE,
    SINGLE_VALUE,
    conflict_semantics_payload,
    fact_conflict_semantics,
)
from dsl_mngr.core.db_code_parser import DbCodeOptions, parse_db_code_text
from dsl_mngr.core.merge import merge_candidate_batch
from dsl_mngr.core.schema_resolution import StructuralIndex
from dsl_mngr.core.xml_form_parser import (
    XmlFormOptions,
    build_fragment_records,
    parse_xml_form_text,
)
from tests.slice_27_test_support import connect, registered_workspace


def test_slice_32_log_identity_and_conflict_semantics(tmp_path, capsys):
    fragments = [
        _fragment(
            fragment_id=f"FRAG_{index:06d}",
            revision_id="REV_000001",
            fragment_type="log_event",
            path=f"log/line:{index}",
            text=f"2026-09-01 08:00:0{index} INFO scanner {kind}",
            metadata={
                "component": "scanner",
                "event_kind": kind,
                "level": "INFO",
                "message": kind,
                "observed_identifiers": {},
                "timestamp": f"2026-09-01 08:00:0{index}",
            },
        )
        for index, kind in enumerate(("start", "processed", "processed", "end"), start=1)
    ]
    events, issues = derive_rule_records("log_event_observation/2", fragments)
    retry, retry_issues = derive_rule_records("log_event_observation/2", reversed(fragments))
    assert issues == retry_issues == []
    assert events == retry
    assert [item["entity_name"] for item in events] == [
        "log_event:REV_000001:FRAG_000001",
        "log_event:REV_000001:FRAG_000002",
        "log_event:REV_000001:FRAG_000003",
        "log_event:REV_000001:FRAG_000004",
    ]
    assert {item["component"] for item in events} == {"scanner"}
    assert len({item["candidate_id"] for item in events}) == 4
    assert len({item["evidence_locator"]["path_or_selector"] for item in events}) == 4

    catalog = conflict_semantics_payload()
    assert catalog["catalog_version"] == "1"
    assert catalog["default"] == SINGLE_VALUE
    assert fact_conflict_semantics("log_event", "event_kind") == EVENT
    assert fact_conflict_semantics("entity_alias", "alias") == MULTI_VALUE
    assert fact_conflict_semantics("unknown_type", "status") == SINGLE_VALUE

    workspace, run_id, _revisions = registered_workspace(
        tmp_path / "merge",
        {"events.log": "2026-09-01 08:00:00 INFO scanner Start request=1\n"},
    )
    assert main(["corpus", "parse-log", str(workspace), "--revision", "REV_000001"]) == 0
    capsys.readouterr()
    with connect(workspace) as connection:
        evidence = connection.execute(
            "SELECT fragment_id, text FROM source_fragments WHERE fragment_type = 'log_event'"
        ).fetchone()
    records = [
        _candidate_fact("SINGLE_A", "asset", "status", "open", "business_entity", evidence),
        _candidate_fact("SINGLE_B", "asset", "status", "closed", "business_entity", evidence),
        _candidate_fact("MULTI_A", "asset", "alias", "A", "entity_alias", evidence),
        _candidate_fact("MULTI_B", "asset", "alias", "B", "entity_alias", evidence),
        _candidate_fact("EVENT_A", "component", "event_kind", "start", "log_event", evidence),
        _candidate_fact("EVENT_B", "component", "event_kind", "end", "log_event", evidence),
    ]
    input_path = workspace / "ai" / "inbox" / "slice_32_conflicts.jsonl"
    input_path.write_text(
        "".join(json.dumps(item, sort_keys=True) + "\n" for item in records),
        encoding="utf-8",
        newline="\n",
    )
    imported = import_candidate_file(workspace, run_id=run_id, input_path=input_path)
    service = CandidateReviewService(workspace)
    with connect(workspace) as connection:
        candidate_ids = [
            str(row[0])
            for row in connection.execute(
                "SELECT candidate_record_id FROM candidate_records WHERE batch_id = ? ORDER BY line_number",
                (imported.batch_id,),
            )
        ]
    for candidate_id in candidate_ids:
        service.confirm(candidate_id, actor_id="slice-32-reviewer")
    merged = merge_candidate_batch(workspace, run_id=run_id, batch_id=imported.batch_id)
    assert merged.facts_created == 6
    assert merged.conflicts_created == 1
    with connect(workspace) as connection:
        conflicts = connection.execute(
            "SELECT conflict_type, property_name FROM conflicts ORDER BY conflict_id"
        ).fetchall()
    assert [tuple(row) for row in conflicts] == [("different_values_same_property", "status")]


def test_slice_32_db_parser_is_scope_aware_and_handles_pseudorecords():
    sql = """
    CREATE PROCEDURE P_UPDATE(P_ID IN NUMBER) AS
    BEGIN
      UPDATE T_OUT o
         SET o.A = o.A + 1
       WHERE o.ID = (
          SELECT i.ID
            FROM T_IN i
            JOIN T_AUX a ON a.ID = i.AUX_ID
           WHERE i.REQUEST_ID = P_ID
             AND i.OUT_ID = o.ID
       );
    END;
    /
    CREATE TRIGGER TRG_OUT BEFORE UPDATE OF A ON T_OUT FOR EACH ROW
    BEGIN
      IF :NEW.A <> :OLD.A THEN
        RAISE_APPLICATION_ERROR(-20001, 'changed');
      END IF;
    END;
    /
    """
    parsed = parse_db_code_text(sql, DbCodeOptions())
    procedure = parsed.procedures[0]
    assert procedure.writes == ("T_OUT.A",)
    assert procedure.reads == (
        "T_OUT.A",
        "T_IN.ID",
        "T_AUX.ID",
        "T_IN.AUX_ID",
        "T_IN.REQUEST_ID",
        "T_IN.OUT_ID",
        "T_OUT.ID",
    )
    assert "P_ID" not in procedure.reads
    assert all("T_IN.T_IN" != item and "T_IN.T_AUX" != item for item in procedure.reads)
    assert parsed.triggers[0].reads == ("NEW.A", "OLD.A")

    simple = parse_db_code_text(
        "CREATE PROCEDURE P AS BEGIN UPDATE T SET A = A - 1 WHERE ID = 1; END; /",
        DbCodeOptions(),
    )
    assert simple.procedures[0].writes == ("T.A",)
    assert simple.procedures[0].reads == ("T.A", "T.ID")
    equivalent = parse_db_code_text(
        "CREATE PROCEDURE P AS\nBEGIN\nUPDATE T SET A=A-1 WHERE ID=1;\nEND;\n/",
        DbCodeOptions(),
    )
    assert equivalent.procedures[0].reads == simple.procedures[0].reads
    assert equivalent.procedures[0].writes == simple.procedures[0].writes


def test_slice_32_structural_resolution_and_auto_review_barrier(tmp_path, capsys):
    index = StructuralIndex.from_active_fragments(
        [
            {"fragment_type": "ddl_table", "metadata_json": {"table_name": "T"}},
            {
                "fragment_type": "ddl_column",
                "metadata_json": {"table_name": "T", "column_name": "A"},
            },
            {
                "fragment_type": "sql_procedure",
                "metadata_json": {"procedure_name": "P"},
            },
        ]
    )
    assert index.resolve_column("T.A").status == "resolved"
    assert index.resolve_column("T.B").status == "inconsistent"
    assert index.resolve_column("MISSING.B").status == "unresolved"
    assert index.resolve_code_unit("P").status == "resolved"
    assert index.resolve_code_unit("MISSING").status == "unresolved"

    db_fragment = _fragment(
        fragment_id="FRAG_DB",
        revision_id="REV_1",
        fragment_type="sql_procedure",
        path="procedure:P",
        text="procedure P",
        metadata={
            "procedure_name": "P",
            "parameters": [],
            "reads": ["T.A", "T.B", "MISSING.B"],
            "writes": [],
            "calls": ["P", "MISSING"],
        },
    )
    candidates, issues = derive_rule_records(
        "db_code_dependency/2", [db_fragment], context={"structural_index": index}
    )
    assert {(item["target_entity"], item["resolution_status"]) for item in candidates} == {
        ("T.A", "resolved"),
        ("MISSING.B", "unresolved"),
        ("P", "resolved"),
        ("MISSING", "unresolved"),
    }
    assert [(issue.reason, "T.B" in issue.message) for issue in issues] == [
        ("structural_reference_inconsistent", True)
    ]

    workspace, run_id, _ = registered_workspace(
        tmp_path / "review", {"unit.sql": "CREATE PROCEDURE P AS BEGIN NULL; END; /\n"}
    )
    assert main(["corpus", "parse-db-code", str(workspace), "--revision", "REV_000001"]) == 0
    capsys.readouterr()
    unresolved_fragment = _fragment_from_database(workspace, "sql_procedure")
    unresolved_fragment["metadata_json"] = json.dumps(
        {
            **json.loads(unresolved_fragment["metadata_json"]),
            "reads": ["UNKNOWN_TABLE.A"],
        },
        sort_keys=True,
    )
    payloads, unresolved_issues = derive_rule_records(
        "db_code_dependency/2", [unresolved_fragment], context={"structural_index": StructuralIndex.empty()}
    )
    assert unresolved_issues == [] and payloads[0]["resolution_status"] == "unresolved"
    input_path = workspace / "ai" / "inbox" / "unresolved.jsonl"
    input_path.write_text(json.dumps(payloads[0], sort_keys=True) + "\n", encoding="utf-8")
    imported = import_candidate_file(
        workspace,
        run_id=run_id,
        input_path=input_path,
        origin_type="deterministic_derivation",
        origin_ref="test://slice-32-unresolved",
    )
    with connect(workspace) as connection:
        candidate_record_id = str(
            connection.execute(
                "SELECT candidate_record_id FROM candidate_records WHERE batch_id = ?",
                (imported.batch_id,),
            ).fetchone()[0]
        )
    with pytest.raises(CandidateReviewConflict) as exc_info:
        CandidateReviewService(workspace).confirm(
            candidate_record_id,
            actor_id="policy:observed_db_code_dependency_only",
            actor_type="automatic",
            policy_id="observed_db_code_dependency_only",
            policy_version="1",
        )
    assert exc_info.value.reason == "structural_resolution_requires_review"


def test_slice_32_oracle_items_and_button_operation_are_preserved():
    xml = """<?xml version="1.0"?>
    <form name="F">
      <field name="LEGACY" table="T" column="A" required="true" />
      <block name="B1" table="T"><item name="SAME" column="A" required="true" /></block>
      <block name="B2" table="U"><item name="SAME" column="B" required="false" /></block>
      <button name="RUN" operation="P" />
      <button name="NOOP" />
    </form>"""
    parsed = parse_xml_form_text(xml, XmlFormOptions())
    assert parsed.field_count == 3
    assert parsed.required_field_count == 2
    records = build_fragment_records(
        parsed,
        source_revision_id="REV_1",
        source_hash="hash",
        parser_name="parse_xml_form",
        parser_version="1",
        fragment_id_by_sequence={},
        next_fragment_number=1,
    )
    fields = [record for record in records if record["fragment_type"] == "xml_field"]
    legacy = next(record for record in fields if record["metadata"]["field_name"] == "LEGACY")
    items = [record for record in fields if record["metadata"]["field_name"] == "SAME"]
    assert "source_element_kind" not in legacy["metadata"]
    assert {item["metadata"]["block_name"] for item in items} == {"B1", "B2"}
    assert len({item["path_or_selector"] for item in items}) == 2
    buttons = [record for record in records if record["fragment_type"] == "xml_button"]
    assert buttons[0]["metadata"]["operation"] == "P"
    assert "operation" not in buttons[1]["metadata"]

    fragments = [_derivation_fragment(record) for record in records]
    index = StructuralIndex.from_active_fragments(
        [
            {"fragment_type": "ddl_table", "metadata_json": {"table_name": "T"}},
            {"fragment_type": "ddl_column", "metadata_json": {"table_name": "T", "column_name": "A"}},
            {"fragment_type": "ddl_table", "metadata_json": {"table_name": "U"}},
            {"fragment_type": "ddl_column", "metadata_json": {"table_name": "U", "column_name": "B"}},
            {"fragment_type": "sql_procedure", "metadata_json": {"procedure_name": "P"}},
        ]
    )
    calls, call_issues = derive_rule_records(
        "xml_button_operation/1",
        [item for item in fragments if item["fragment_type"] == "xml_button"],
        context={"structural_index": index},
    )
    assert call_issues == []
    assert [(item["source_entity"], item["relation_type"], item["target_entity"], item["resolution_status"]) for item in calls] == [
        ("F.RUN", "calls", "P", "resolved")
    ]
    mappings, mapping_issues = derive_rule_records(
        "xml_table_usage/2",
        [item for item in fragments if item["fragment_type"] in {"xml_form", "xml_field"}],
        context={"structural_index": index},
    )
    assert mapping_issues == []
    item_mappings = [item for item in mappings if item.get("source_element_kind") == "item"]
    assert {(item["source_entity"], item["target_entity"]) for item in item_mappings} == {
        ("F.B1.SAME", "T.A"),
        ("F.B2.SAME", "U.B"),
    }
    assert {
        json.loads(item["metadata_json"])["required"]
        for item in fragments
        if item["fragment_type"] == "xml_field"
    } == {True, False}

    unresolved_calls, unresolved_call_issues = derive_rule_records(
        "xml_button_operation/1",
        [item for item in fragments if item["fragment_type"] == "xml_button"],
        context={"structural_index": StructuralIndex.empty()},
    )
    assert unresolved_call_issues == []
    assert [item["resolution_status"] for item in unresolved_calls] == ["unresolved"]

    legacy_fragment = next(
        item
        for item in fragments
        if item["fragment_type"] == "xml_field"
        and json.loads(item["metadata_json"])["field_name"] == "LEGACY"
    )
    unresolved_mappings, unresolved_mapping_issues = derive_rule_records(
        "xml_table_usage/2",
        [legacy_fragment],
        context={"structural_index": StructuralIndex.empty()},
    )
    assert unresolved_mapping_issues == []
    assert [item["resolution_status"] for item in unresolved_mappings] == ["unresolved"]
    inconsistent_index = StructuralIndex.from_active_fragments(
        [
            {"fragment_type": "ddl_table", "metadata_json": {"table_name": "T"}},
            {
                "fragment_type": "ddl_column",
                "metadata_json": {"table_name": "T", "column_name": "OTHER"},
            },
        ]
    )
    inconsistent_mappings, inconsistent_mapping_issues = derive_rule_records(
        "xml_table_usage/2",
        [legacy_fragment],
        context={"structural_index": inconsistent_index},
    )
    assert inconsistent_mappings == []
    assert [issue.reason for issue in inconsistent_mapping_issues] == [
        "structural_reference_inconsistent"
    ]


def _fragment(
    *,
    fragment_id: str,
    revision_id: str,
    fragment_type: str,
    path: str,
    text: str,
    metadata: dict[str, object],
) -> dict[str, object]:
    return {
        "fragment_id": fragment_id,
        "fragment_type": fragment_type,
        "line_end": 1,
        "line_start": 1,
        "metadata_json": json.dumps(metadata, sort_keys=True),
        "path_or_selector": path,
        "source_revision_id": revision_id,
        "text": text,
    }


def _candidate_fact(candidate_id, entity, prop, value, fact_type, evidence):
    return {
        "assertion_type": "observed",
        "candidate_id": candidate_id,
        "chunk_id": None,
        "confidence": "high",
        "entity_name": entity,
        "evidence_text": str(evidence["text"]),
        "fact_type": fact_type,
        "fragment_id": str(evidence["fragment_id"]),
        "property_name": prop,
        "property_value": value,
        "record_type": "candidate_fact",
        "source_revision_id": "REV_000001",
    }


def _fragment_from_database(workspace: Path, fragment_type: str) -> dict[str, object]:
    with connect(workspace) as connection:
        row = connection.execute(
            "SELECT * FROM source_fragments WHERE fragment_type = ? ORDER BY fragment_id LIMIT 1",
            (fragment_type,),
        ).fetchone()
    return dict(row)


def _derivation_fragment(record: dict[str, object]) -> dict[str, object]:
    return {
        **record,
        "metadata_json": json.dumps(record["metadata"], sort_keys=True),
    }
