from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

from dsl_mngr.cli.app import main


TESTS_DIR = Path(__file__).parent
XML_FIXTURE_DIR = TESTS_DIR / "fixtures" / "xml_forms"


def test_parse_xml_form(tmp_path, capsys):
    workspace = _workspace_with_xml_fixtures(tmp_path, capsys)
    assert (workspace / "configs" / "workers" / "xml_form.default.yaml").is_file()
    assert (workspace / "fragments").is_dir()

    assert main(["corpus", "parse-xml-form", str(workspace), "--revision", "REV_000001"]) == 0
    output = capsys.readouterr().out
    assert "Run: RUN_000001" in output
    assert "Revision: REV_000001" in output
    assert "Source: SRC_000001" in output
    assert "Forms: 1" in output
    assert "Fields: 3" in output
    assert "Required fields: 2" in output
    assert "Buttons: 1" in output
    assert "Table references: 1" in output
    assert "Edit relations: 1" in output
    assert "Fragments: 5" in output
    assert "Fragments JSONL: fragments/SRC_000001/REV_000001/fragments.jsonl" in output
    assert "Report: fragments/SRC_000001/REV_000001/xml_form_report.json" in output

    jsonl_path = workspace / "fragments" / "SRC_000001" / "REV_000001" / "fragments.jsonl"
    report_path = workspace / "fragments" / "SRC_000001" / "REV_000001" / "xml_form_report.json"
    assert jsonl_path.is_file()
    assert report_path.is_file()

    records = _read_jsonl(jsonl_path)
    report = _read_json(report_path)
    assert len(records) == 5
    assert report["form_count"] == 1
    assert report["field_count"] == 3
    assert report["required_field_count"] == 2
    assert report["button_count"] == 1
    assert report["table_reference_count"] == 1
    assert report["edit_relation_count"] == 1
    assert report["fragments_hash"] == _sha256_text(jsonl_path.read_text(encoding="utf-8"))
    assert report["outputs"]["fragments_jsonl_path"] == "fragments/SRC_000001/REV_000001/fragments.jsonl"
    assert report["outputs"]["xml_form_report_path"] == (
        "fragments/SRC_000001/REV_000001/xml_form_report.json"
    )

    form_record = _record_by_type(records, "xml_form")
    assert form_record["metadata"]["form_name"] == "FRM_CLIENTE"
    assert form_record["metadata"]["title"] == "Cliente"
    assert form_record["metadata"]["table_references"] == ["ANCLI"]
    assert form_record["metadata"]["edit_relations"] == [
        {
            "field_names": ["CODCLI", "RAGSOC", "PIVA"],
            "relation_type": "edits",
            "source_form": "FRM_CLIENTE",
            "target_table": "ANCLI",
        }
    ]
    assert report["edit_relations"] == form_record["metadata"]["edit_relations"]

    fields = {
        record["metadata"]["field_name"]: record["metadata"]
        for record in records
        if record["fragment_type"] == "xml_field"
    }
    assert set(fields) == {"CODCLI", "RAGSOC", "PIVA"}
    assert fields["CODCLI"]["required"] is True
    assert fields["RAGSOC"]["required"] is True
    assert fields["PIVA"]["required"] is False
    assert {
        (metadata["table_name"], metadata["column_name"], metadata["mapping_type"])
        for metadata in fields.values()
    } == {
        ("ANCLI", "CODCLI", "form_field_to_column"),
        ("ANCLI", "RAGSOC", "form_field_to_column"),
        ("ANCLI", "PIVA", "form_field_to_column"),
    }

    button = _record_by_type(records, "xml_button")
    assert button["metadata"]["button_name"] == "SAVE"
    assert button["metadata"]["action_kind"] == "save"
    assert button["path_or_selector"] == "/form[@name='FRM_CLIENTE']/button[@name='SAVE']"

    for record in records:
        assert record["text_hash"] == _sha256_text(record["text"])
        assert "\\" not in record["path_or_selector"]
        assert record["metadata"]["parser"] == "parse_xml_form"
        assert record["metadata"]["source_hash"]

    with _connect(workspace) as connection:
        source = connection.execute(
            "SELECT * FROM sources WHERE source_id = 'SRC_000001'"
        ).fetchone()
        db_counts = connection.execute(
            """
            SELECT fragment_type, COUNT(*) AS count
            FROM source_fragments
            WHERE status = 'active'
              AND source_revision_id = 'REV_000001'
            GROUP BY fragment_type
            ORDER BY fragment_type
            """
        ).fetchall()

    assert (source["source_type"], source["source_subtype"], source["authority_level"]) == (
        "xml_form",
        "form",
        "technical_structure",
    )
    assert [(row["fragment_type"], row["count"]) for row in db_counts] == [
        ("xml_button", 1),
        ("xml_field", 3),
        ("xml_form", 1),
    ]
    _assert_parse_run_and_worker(workspace, expected_count=1)
    _assert_process_report(workspace, "RUN_000001")

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "dsl_mngr",
            "corpus",
            "parse-xml-form",
            str(workspace),
            "--revision",
            "REV_000002",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert completed.returncode == 0
    assert "Run: RUN_000002" in completed.stdout
    order_report = _read_json(
        workspace / "fragments" / "SRC_000002" / "REV_000002" / "xml_form_report.json"
    )
    assert order_report["xml_form_objects"]["forms"][0]["name"] == "FRM_ORDINE"
    assert order_report["xml_form_objects"]["forms"][0]["buttons"][0]["action_kind"] == "confirm"
    _assert_parse_run_and_worker(workspace, expected_count=2)


def test_form_edits_table_relation(tmp_path, capsys):
    workspace = _workspace_with_xml_fixtures(tmp_path, capsys)
    assert main(["corpus", "parse-xml-form", str(workspace), "--revision", "REV_000001"]) == 0
    capsys.readouterr()

    with _connect(workspace) as connection:
        form_fragment = connection.execute(
            """
            SELECT fragment_id, text
            FROM source_fragments
            WHERE status = 'active'
              AND fragment_type = 'xml_form'
              AND source_revision_id = 'REV_000001'
            """
        ).fetchone()

    evidence_text = 'table="ANCLI" column="CODCLI"'
    assert evidence_text in form_fragment["text"]
    candidate_path = workspace / "ai" / "inbox" / "xml_form_relation_candidate.jsonl"
    candidate = {
        "assertion_type": "explicit",
        "candidate_id": "CAND_XML_FORM_EDITS_001",
        "chunk_id": None,
        "confidence": "high",
        "evidence_text": evidence_text,
        "fragment_id": form_fragment["fragment_id"],
        "record_type": "candidate_relation",
        "relation_type": "edits",
        "source_entity": "FRM_CLIENTE",
        "source_revision_id": "REV_000001",
        "target_entity": "ANCLI",
    }
    candidate_path.write_text(
        json.dumps(candidate, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    assert main(["candidates", "validate", str(workspace), "--input", str(candidate_path)]) == 0
    validation_output = capsys.readouterr().out
    assert "Total: 1" in validation_output
    assert "Accepted: 1" in validation_output
    assert "Rejected: 0" in validation_output

    with _connect(workspace) as connection:
        accepted = connection.execute("SELECT * FROM candidate_records").fetchone()
        rejected_count = connection.execute("SELECT COUNT(*) FROM rejected_candidates").fetchone()[0]

    assert accepted["fragment_id"] == form_fragment["fragment_id"]
    assert accepted["chunk_id"] is None
    assert rejected_count == 0

    assert main(["facts", "merge", str(workspace), "--batch", "CBATCH_000001"]) == 0
    merge_output = capsys.readouterr().out
    assert "Relations created: 1" in merge_output

    with _connect(workspace) as connection:
        relation = connection.execute("SELECT * FROM relations").fetchone()
        evidence = connection.execute("SELECT * FROM relation_evidence").fetchone()

    assert (
        relation["source_entity"],
        relation["relation_type"],
        relation["target_entity"],
        relation["status"],
    ) == ("FRM_CLIENTE", "edits", "ANCLI", "active")
    assert evidence["fragment_id"] == form_fragment["fragment_id"]
    assert evidence["chunk_id"] is None


def test_parse_xml_form_idempotent_rerun(tmp_path, capsys):
    workspace = _workspace_with_xml_fixtures(tmp_path, capsys)
    assert main(["corpus", "parse-xml-form", str(workspace), "--revision", "REV_000001"]) == 0
    capsys.readouterr()

    jsonl_path = workspace / "fragments" / "SRC_000001" / "REV_000001" / "fragments.jsonl"
    report_path = workspace / "fragments" / "SRC_000001" / "REV_000001" / "xml_form_report.json"
    first_records = _read_jsonl(jsonl_path)
    first_ids = [record["fragment_id"] for record in first_records]
    first_hash = _read_json(report_path)["fragments_hash"]

    assert main(["corpus", "parse-xml-form", str(workspace), "--revision", "REV_000001"]) == 0
    output = capsys.readouterr().out
    assert "Run: RUN_000002" in output

    second_records = _read_jsonl(jsonl_path)
    assert [record["fragment_id"] for record in second_records] == first_ids
    assert _read_json(report_path)["fragments_hash"] == first_hash
    assert _sha256_text(jsonl_path.read_text(encoding="utf-8")) == first_hash

    with _connect(workspace) as connection:
        active_count = connection.execute(
            "SELECT COUNT(*) FROM source_fragments WHERE status = 'active'"
        ).fetchone()[0]
        duplicate_active = connection.execute(
            """
            SELECT source_revision_id, sequence, COUNT(*) AS count
            FROM source_fragments
            WHERE status = 'active'
            GROUP BY source_revision_id, sequence
            HAVING COUNT(*) > 1
            """
        ).fetchall()

    assert active_count == 5
    assert duplicate_active == []
    _assert_parse_run_and_worker(workspace, expected_count=2)


def test_parse_xml_form_unsupported_option_fails_without_active_fragments(tmp_path, capsys):
    workspace = _workspace_with_xml_fixtures(tmp_path, capsys)
    bad_profile = workspace / "configs" / "workers" / "xml_form.bad.yaml"
    bad_profile.write_text(
        (workspace / "configs" / "workers" / "xml_form.default.yaml").read_text(
            encoding="utf-8"
        )
        + "  unsupported_slice13_option: true\n",
        encoding="utf-8",
        newline="\n",
    )

    assert (
        main(
            [
                "corpus",
                "parse-xml-form",
                str(workspace),
                "--revision",
                "REV_000001",
                "--profile",
                "xml_form.bad",
            ]
        )
        == 2
    )
    captured = capsys.readouterr()
    assert "exit_code=4" in captured.err

    with _connect(workspace) as connection:
        active_fragments = connection.execute(
            "SELECT COUNT(*) FROM source_fragments WHERE status = 'active'"
        ).fetchone()[0]
        run = connection.execute("SELECT run_type, status FROM runs").fetchone()
        worker = connection.execute(
            "SELECT worker_name, status, exit_code FROM worker_runs"
        ).fetchone()

    assert active_fragments == 0
    assert (run["run_type"], run["status"]) == ("parse_xml_form", "failed")
    assert (worker["worker_name"], worker["status"], worker["exit_code"]) == (
        "parse_xml_form",
        "failed",
        4,
    )

    report = _read_json(workspace / "artifacts" / "runs" / "RUN_000001" / "process_report.json")
    assert report["run_type"] == "parse_xml_form"
    assert report["status"] == "failed"
    assert report["workers"][0]["exit_code"] == 4
    assert "unsupported_xml_form_option" in report["workers"][0]["stderr"]
    assert "unsupported_slice13_option" in report["workers"][0]["stderr"]
    assert not (workspace / "fragments" / "SRC_000001" / "REV_000001" / "fragments.jsonl").exists()


def _workspace_with_xml_fixtures(tmp_path: Path, capsys) -> Path:
    workspace = tmp_path / "workspace"
    assert main(["init", str(workspace)]) == 0
    assert main(["db", "init", str(workspace)]) == 0
    capsys.readouterr()

    shutil.copytree(XML_FIXTURE_DIR, workspace / "corpus" / "active", dirs_exist_ok=True)
    assert main(["corpus", "scan", str(workspace)]) == 0
    scan_output = capsys.readouterr().out
    assert "Added: 2" in scan_output

    with _connect(workspace) as connection:
        sources = connection.execute("SELECT * FROM sources ORDER BY source_id").fetchall()
        revisions = connection.execute(
            "SELECT * FROM source_revisions ORDER BY source_revision_id"
        ).fetchall()

    assert [source["source_id"] for source in sources] == ["SRC_000001", "SRC_000002"]
    assert [source["source_type"] for source in sources] == ["unknown", "unknown"]
    assert [revision["source_revision_id"] for revision in revisions] == [
        "REV_000001",
        "REV_000002",
    ]
    assert revisions[0]["file_path"] == "corpus/active/form_cliente.xml"
    assert revisions[1]["file_path"] == "corpus/active/form_ordine.xml"
    for revision in revisions:
        assert revision["content_hash"] == _sha256_file(workspace / revision["file_path"])
    return workspace


def _assert_parse_run_and_worker(workspace: Path, *, expected_count: int) -> None:
    with _connect(workspace) as connection:
        runs = connection.execute(
            "SELECT run_id, run_type, status FROM runs ORDER BY run_id"
        ).fetchall()
        workers = connection.execute(
            "SELECT worker_name, status, exit_code FROM worker_runs ORDER BY worker_run_id"
        ).fetchall()

    assert [(row["run_type"], row["status"]) for row in runs] == [
        ("parse_xml_form", "completed")
    ] * expected_count
    assert [(row["worker_name"], row["status"], row["exit_code"]) for row in workers] == [
        ("parse_xml_form", "completed", 0)
    ] * expected_count


def _assert_process_report(workspace: Path, run_id: str) -> None:
    artifact_dir = workspace / "artifacts" / "runs" / run_id
    input_payload = _read_json(artifact_dir / "input.json")
    output_payload = _read_json(artifact_dir / "output.json")
    report = _read_json(artifact_dir / "process_report.json")

    assert input_payload["source_id"] == "SRC_000001"
    assert input_payload["source_revision_id"] == "REV_000001"
    assert input_payload["source_hash"]
    assert input_payload["input_path"] == "corpus/active/form_cliente.xml"
    assert input_payload["output_dir"] == "fragments/SRC_000001/REV_000001"
    assert input_payload["profile"] == "xml_form.default"
    assert input_payload["xml_form_options"]["parser"] == "elementtree"
    assert input_payload["fragment_id_by_sequence"] == {}
    assert input_payload["next_fragment_number"] == 1
    assert output_payload["worker_name"] == "parse_xml_form"
    assert output_payload["status"] == "completed"
    assert output_payload["fragment_count"] == 5
    assert output_payload["xml_form_objects"]["forms"][0]["name"] == "FRM_CLIENTE"
    assert report["run_type"] == "parse_xml_form"
    assert report["status"] == "completed"
    assert report["artifact_dir"] == f"artifacts/runs/{run_id}"
    assert report["workers"][0]["worker_name"] == "parse_xml_form"
    assert report["workers"][0]["exit_code"] == 0
    for path_value in (
        input_payload["input_path"],
        input_payload["output_dir"],
        output_payload["fragments_jsonl_path"],
        output_payload["xml_form_report_path"],
        report["artifact_dir"],
    ):
        assert "\\" not in path_value
        assert not Path(path_value).is_absolute()


def _record_by_type(records: list[dict[str, object]], fragment_type: str) -> dict[str, object]:
    matches = [record for record in records if record["fragment_type"] == fragment_type]
    assert len(matches) == 1
    return matches[0]


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _connect(workspace: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(workspace / "workspace.sqlite")
    connection.row_factory = sqlite3.Row
    return connection
