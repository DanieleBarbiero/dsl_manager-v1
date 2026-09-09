from __future__ import annotations

import json
import shutil
import socket
import sqlite3
import urllib.request
from pathlib import Path
from typing import Any

from dsl_mngr.cli.app import main
from dsl_mngr.core.candidate_derivation import (
    DERIVATION_RULE_CATALOG,
    derive_rule_records,
)
from dsl_mngr.core.candidate_validation import validate_candidate_payload
from dsl_mngr.core.canonical import canonical_json_v1
from dsl_mngr.core.workspace import initialize_workspace


TESTS_DIR = Path(__file__).parent
FIXTURES = TESTS_DIR / "fixtures"
EXPECTED = TESTS_DIR / "expected" / "expected_slice_21_rule_matrix.json"
SLICE_21_RULES = (
    "ddl_column_fact/1",
    "ddl_fk_relation/1",
    "xml_form_structure/1",
    "xml_table_usage/1",
    "db_code_unit/1",
    "db_code_dependency/1",
    "log_event_observation/1",
)


def test_slice_21_rule_matrix(tmp_path, capsys, monkeypatch):
    network_calls: list[str] = []

    def reject_network(*args, **kwargs):
        del args, kwargs
        network_calls.append("network")
        raise AssertionError("Slice 21 must not access the network")

    monkeypatch.setattr(socket, "create_connection", reject_network)
    monkeypatch.setattr(urllib.request, "urlopen", reject_network)

    expected_catalog = ("ddl_table_fact/1", *SLICE_21_RULES)
    assert tuple(DERIVATION_RULE_CATALOG) == expected_catalog
    for name in expected_catalog:
        contract = DERIVATION_RULE_CATALOG[name]
        assert contract.rule_version == "1"
        assert contract.input_schema.startswith("source_fragment/")
        assert contract.assertion_type in {"explicit", "observed"}
        assert contract.evidence_locator == (
            "source_revision_id+fragment_id+path_or_selector+line_start+line_end"
        )
        assert contract.automatic_review_policy.endswith("/1")
        assert contract.default_review_state == "pending"

    workspace = _parsed_workspace(tmp_path / "workspace", capsys)
    revisions = _revision_map(workspace)
    invocations = (
        ("ddl_column_fact/1", revisions["schema_ordini.sql"]),
        ("ddl_fk_relation/1", revisions["schema_ordini.sql"]),
        ("xml_form_structure/1", revisions["form_cliente.xml"]),
        ("xml_table_usage/1", revisions["form_cliente.xml"]),
        ("db_code_unit/1", revisions["procedura_dipendenze.sql"]),
        ("db_code_unit/1", revisions["trigger_ordini.sql"]),
        ("db_code_dependency/1", revisions["procedura_dipendenze.sql"]),
        ("db_code_dependency/1", revisions["trigger_ordini.sql"]),
        ("log_event_observation/1", revisions["log_batch_ordini.log"]),
    )

    projected: dict[str, list[dict[str, Any]]] = {rule: [] for rule in SLICE_21_RULES}
    first_column_result: dict[str, Any] | None = None
    with _connect(workspace) as connection:
        facts_before = connection.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
        relations_before = connection.execute("SELECT COUNT(*) FROM relations").fetchone()[0]

    for rule, revision_id in invocations:
        result = _derive(workspace, capsys, rule, revision_id)
        assert result["catalog_version"] == "result_catalog_v1"
        assert result["rule"] == rule
        assert result["counters"]["auto_confirmed"] == 0
        assert result["counters"]["deduplicated"] == 0
        assert result["counters"]["input_fragments"] > 0
        assert result["counters"]["pending"] == result["counters"]["produced"]
        assert result["rule_counts"][rule]["produced"] == result["counters"]["produced"]
        report = json.loads((workspace / result["artifact_paths"][1]).read_text(encoding="utf-8"))
        assert report == result
        payloads = _batch_payloads(workspace, result["batch_id"])
        projected[rule].extend(_project_candidate(payload) for payload in payloads)
        _assert_pending_derivation_batch(workspace, result["batch_id"], len(payloads))
        if rule == "ddl_column_fact/1":
            first_column_result = result

    for candidates in projected.values():
        candidates.sort(key=canonical_json_v1)
    if not EXPECTED.is_file():
        raise AssertionError(json.dumps(projected, ensure_ascii=False, indent=2, sort_keys=True))
    assert projected == json.loads(EXPECTED.read_text(encoding="utf-8"))
    assert network_calls == []

    assert first_column_result is not None
    second_column_result = _derive(
        workspace, capsys, "ddl_column_fact/1", revisions["schema_ordini.sql"]
    )
    assert second_column_result["batch_id"] != first_column_result["batch_id"]
    assert second_column_result["candidate_ids"] == first_column_result["candidate_ids"]
    assert second_column_result["payload_hashes"] == first_column_result["payload_hashes"]
    assert second_column_result["semantic_report_hash"] == first_column_result["semantic_report_hash"]
    assert _batch_payloads(workspace, second_column_result["batch_id"]) == _batch_payloads(
        workspace, first_column_result["batch_id"]
    )

    with _connect(workspace) as connection:
        first_records = {
            row[0]
            for row in connection.execute(
                "SELECT candidate_record_id FROM candidate_records WHERE batch_id = ?",
                (first_column_result["batch_id"],),
            )
        }
        second_records = {
            row[0]
            for row in connection.execute(
                "SELECT candidate_record_id FROM candidate_records WHERE batch_id = ?",
                (second_column_result["batch_id"],),
            )
        }
        assert first_records.isdisjoint(second_records)
        assert connection.execute("SELECT COUNT(*) FROM facts").fetchone()[0] == facts_before
        assert connection.execute("SELECT COUNT(*) FROM relations").fetchone()[0] == relations_before


def test_slice_21_fk_resolved_and_unresolved(tmp_path, capsys):
    resolved = _single_parsed_workspace(
        tmp_path / "resolved",
        capsys,
        FIXTURES / "ddl" / "schema_ordini.sql",
        "parse-ddl",
    )
    resolved_revision = next(iter(_revision_map(resolved).values()))
    resolved_result = _derive(resolved, capsys, "ddl_fk_relation/1", resolved_revision)
    assert resolved_result["counters"] == {
        "auto_confirmed": 0,
        "deduplicated": 0,
        "input_fragments": 5,
        "pending": 2,
        "produced": 2,
        "rejected": 0,
    }

    unresolved = _single_parsed_workspace(
        tmp_path / "unresolved",
        capsys,
        FIXTURES / "slice_21" / "schema_fk_unresolved.sql",
        "parse-ddl",
    )
    unresolved_revision = next(iter(_revision_map(unresolved).values()))
    first = _derive(unresolved, capsys, "ddl_fk_relation/1", unresolved_revision)
    second = _derive(unresolved, capsys, "ddl_fk_relation/1", unresolved_revision)
    assert first["counters"]["produced"] == 0
    assert first["counters"]["rejected"] == 1
    assert first["reason"] == "derivation_insufficient_evidence"
    assert first["derivation_rejections"] == second["derivation_rejections"]
    assert first["semantic_report_hash"] == second["semantic_report_hash"]


def test_slice_21_xml_read_write_and_ambiguous_signals():
    base = _fragment(
        fragment_type="xml_form",
        metadata={"form_name": "FRM_TEST", "table_references": ["TAB_A"]},
    )
    explicit_read = dict(base)
    explicit_read["metadata_json"] = json.dumps(
        {
            "form_name": "FRM_TEST",
            "table_references": ["TAB_A"],
            "table_usage_relations": [
                {"relation_type": "reads", "target_table": "TAB_A"}
            ],
        }
    )
    read_candidates, read_issues = derive_rule_records(
        "xml_table_usage/1", [explicit_read]
    )
    assert [(item["relation_type"], item["target_entity"]) for item in read_candidates] == [
        ("reads_from", "TAB_A")
    ]
    assert read_issues == []

    explicit_write = dict(base)
    explicit_write["metadata_json"] = json.dumps(
        {
            "edit_relations": [
                {"relation_type": "edits", "target_table": "TAB_A"}
            ],
            "form_name": "FRM_TEST",
            "table_references": ["TAB_A"],
        }
    )
    write_candidates, write_issues = derive_rule_records(
        "xml_table_usage/1", [explicit_write]
    )
    assert [item["relation_type"] for item in write_candidates] == ["writes_to"]
    assert write_issues == []

    ambiguous_candidates, ambiguous_issues = derive_rule_records(
        "xml_table_usage/1", [base]
    )
    assert ambiguous_candidates == []
    assert [issue.reason for issue in ambiguous_issues] == [
        "derivation_insufficient_evidence"
    ]


def test_slice_21_locator_order_deduplication_and_db_function():
    first = _fragment(
        fragment_id="FRAG_B",
        path="/table/B/column/COL_B",
        fragment_type="ddl_column",
        metadata={"column_name": "COL_B", "data_type": "INTEGER", "table_name": "TAB_B"},
    )
    second = _fragment(
        fragment_id="FRAG_A",
        path="/table/A/column/COL_A",
        fragment_type="ddl_column",
        metadata={"column_name": "COL_A", "data_type": "CHAR(2)", "table_name": "TAB_A"},
    )
    ordered, issues = derive_rule_records("ddl_column_fact/1", [first, second])
    reversed_order, reversed_issues = derive_rule_records(
        "ddl_column_fact/1", [second, first]
    )
    deduplicated, duplicate_issues = derive_rule_records(
        "ddl_column_fact/1", [second, first, second]
    )
    assert ordered == reversed_order == deduplicated
    assert issues == reversed_issues == duplicate_issues == []
    assert [item["entity_name"] for item in ordered] == ["TAB_A.COL_A", "TAB_B.COL_B"]

    missing_locator = dict(first)
    missing_locator["path_or_selector"] = None
    candidates, locator_issues = derive_rule_records(
        "ddl_column_fact/1", [missing_locator]
    )
    assert candidates == []
    assert locator_issues[0].reason == "derivation_insufficient_evidence"
    assert "path_or_selector" in locator_issues[0].message

    function = _fragment(
        fragment_type="sql_function",
        metadata={
            "calls": ["FN_AUDIT"],
            "function_name": "FN_TOTAL",
            "reads": ["ORDRIG.QTA"],
            "writes": [],
        },
    )
    units, unit_issues = derive_rule_records("db_code_unit/1", [function])
    dependencies, dependency_issues = derive_rule_records(
        "db_code_dependency/1", [function]
    )
    assert units[0]["property_value"] == "function"
    assert {(item["relation_type"], item["target_entity"]) for item in dependencies} == {
        ("calls", "FN_AUDIT"),
        ("reads_from", "ORDRIG.QTA"),
    }
    assert unit_issues == dependency_issues == []


def test_slice_21_unresolved_template_rejected():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(
        """
        CREATE TABLE source_revisions (source_revision_id TEXT PRIMARY KEY);
        CREATE TABLE chunks (
            chunk_id TEXT PRIMARY KEY, source_revision_id TEXT NOT NULL, text TEXT NOT NULL
        );
        CREATE TABLE source_fragments (
            fragment_id TEXT PRIMARY KEY, source_revision_id TEXT NOT NULL, text TEXT NOT NULL
        );
        INSERT INTO source_revisions VALUES ('REV_1');
        INSERT INTO source_fragments VALUES ('FRAG_1', 'REV_1', 'explicit evidence');
        """
    )
    base = {
        "assertion_type": "explicit",
        "candidate_id": "CAND_1",
        "confidence": "high",
        "entity_name": "ENTITY",
        "evidence_text": "explicit evidence",
        "fact_type": "technical_object",
        "fragment_id": "FRAG_1",
        "property_name": "kind",
        "property_value": "value",
        "record_type": "candidate_fact",
        "source_revision_id": "REV_1",
    }
    for field, placeholder in (
        ("entity_name", "REPLACE_ENTITY"),
        ("fact_type", "${fact_type}"),
        ("property_value", "{{ value }}"),
        ("property_name", "<<property>>"),
        ("property_value", "TBD"),
    ):
        payload = {**base, field: placeholder}
        failure = validate_candidate_payload(connection, payload)
        assert failure is not None
        assert failure.reason == "unresolved_template_placeholder"
        assert field in failure.message
    valid = validate_candidate_payload(connection, base)
    assert valid is None
    connection.close()


def _parsed_workspace(workspace: Path, capsys) -> Path:
    initialize_workspace(workspace)
    assert main(["db", "init", str(workspace)]) == 0
    files = (
        (FIXTURES / "ddl" / "schema_ordini.sql", "schema_ordini.sql"),
        (FIXTURES / "xml_forms" / "form_cliente.xml", "form_cliente.xml"),
        (FIXTURES / "slice_21" / "procedura_dipendenze.sql", "procedura_dipendenze.sql"),
        (FIXTURES / "db_code" / "trigger_ordini.sql", "trigger_ordini.sql"),
        (FIXTURES / "logs" / "log_batch_ordini.log", "log_batch_ordini.log"),
    )
    for source, name in files:
        shutil.copyfile(source, workspace / "corpus" / "active" / name)
    assert main(["corpus", "scan", str(workspace)]) == 0
    capsys.readouterr()
    revisions = _revision_map(workspace)
    for command, name in (
        ("parse-ddl", "schema_ordini.sql"),
        ("parse-xml-form", "form_cliente.xml"),
        ("parse-db-code", "procedura_dipendenze.sql"),
        ("parse-db-code", "trigger_ordini.sql"),
        ("parse-log", "log_batch_ordini.log"),
    ):
        assert main(["corpus", command, str(workspace), "--revision", revisions[name]]) == 0
        capsys.readouterr()
    return workspace


def _single_parsed_workspace(
    workspace: Path, capsys, fixture: Path, parser_command: str
) -> Path:
    initialize_workspace(workspace)
    assert main(["db", "init", str(workspace)]) == 0
    shutil.copyfile(fixture, workspace / "corpus" / "active" / fixture.name)
    assert main(["corpus", "scan", str(workspace)]) == 0
    capsys.readouterr()
    revision = next(iter(_revision_map(workspace).values()))
    assert main(["corpus", parser_command, str(workspace), "--revision", revision]) == 0
    capsys.readouterr()
    return workspace


def _revision_map(workspace: Path) -> dict[str, str]:
    with _connect(workspace) as connection:
        rows = connection.execute(
            "SELECT file_path, source_revision_id FROM source_revisions ORDER BY file_path"
        ).fetchall()
    return {Path(row["file_path"]).name: row["source_revision_id"] for row in rows}


def _derive(workspace: Path, capsys, rule: str, revision_id: str) -> dict[str, Any]:
    assert main(
        [
            "candidates",
            "derive",
            str(workspace),
            "--source-revision-id",
            revision_id,
            "--rule",
            rule,
        ]
    ) == 0
    output = capsys.readouterr().out
    return json.loads(output[output.index("{") :])


def _batch_payloads(workspace: Path, batch_id: str) -> list[dict[str, Any]]:
    with _connect(workspace) as connection:
        rows = connection.execute(
            "SELECT payload_json FROM candidate_records WHERE batch_id = ? ORDER BY line_number",
            (batch_id,),
        ).fetchall()
    return [json.loads(row["payload_json"]) for row in rows]


def _assert_pending_derivation_batch(workspace: Path, batch_id: str, expected: int) -> None:
    with _connect(workspace) as connection:
        batch = connection.execute(
            "SELECT origin_type, origin_ref, accepted_count FROM candidate_batches WHERE batch_id = ?",
            (batch_id,),
        ).fetchone()
        heads = connection.execute(
            """
            SELECT COUNT(*) FROM review_subject_heads
            WHERE subject_id IN (
                SELECT candidate_record_id FROM candidate_records WHERE batch_id = ?
            )
            """,
            (batch_id,),
        ).fetchone()[0]
    assert tuple(batch) == ("deterministic_derivation", batch["origin_ref"], expected)
    assert batch["origin_ref"].startswith("derive://DERIVE_")
    assert heads == 0


def _project_candidate(payload: dict[str, Any]) -> dict[str, Any]:
    dynamic = {
        "candidate_id",
        "evidence_locator",
        "evidence_text",
        "fragment_id",
        "source_revision_id",
    }
    return {key: value for key, value in payload.items() if key not in dynamic}


def _fragment(
    *,
    fragment_id: str = "FRAG_1",
    fragment_type: str,
    metadata: dict[str, Any],
    path: str | None = "/object/1",
) -> dict[str, Any]:
    return {
        "fragment_id": fragment_id,
        "fragment_type": fragment_type,
        "line_end": 1,
        "line_start": 1,
        "metadata_json": json.dumps(metadata),
        "parser_kind": "test_parser",
        "path_or_selector": path,
        "source_revision_id": "REV_1",
        "text": "explicit evidence",
    }


def _connect(workspace: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(workspace / "workspace.sqlite")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection
