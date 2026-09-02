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
DDL_FIXTURE = TESTS_DIR / "fixtures" / "ddl" / "schema_ordini.sql"


def test_parse_ddl_tables(tmp_path, capsys):
    workspace = _workspace_with_ddl_fixture(tmp_path, capsys)
    assert (workspace / "configs" / "workers" / "ddl.default.yaml").is_file()
    assert (workspace / "fragments").is_dir()

    assert main(["corpus", "parse-ddl", str(workspace), "--revision", "REV_000001"]) == 0
    output = capsys.readouterr().out
    assert "Run: RUN_000001" in output
    assert "Revision: REV_000001" in output
    assert "Source: SRC_000001" in output
    assert "Tables: 3" in output
    assert "Columns: 12" in output
    assert "Foreign keys: 2" in output
    assert "Fragments: 20" in output
    assert "Fragments JSONL: fragments/SRC_000001/REV_000001/fragments.jsonl" in output
    assert "Report: fragments/SRC_000001/REV_000001/ddl_report.json" in output

    jsonl_path = workspace / "fragments" / "SRC_000001" / "REV_000001" / "fragments.jsonl"
    report_path = workspace / "fragments" / "SRC_000001" / "REV_000001" / "ddl_report.json"
    assert jsonl_path.is_file()
    assert report_path.is_file()

    records = _read_jsonl(jsonl_path)
    report = _read_json(report_path)
    assert len(records) == 20
    assert report["table_count"] == 3
    assert report["column_count"] == 12
    assert report["foreign_key_count"] == 2
    assert report["fragments_hash"] == _sha256_text(jsonl_path.read_text(encoding="utf-8"))
    assert report["outputs"]["fragments_jsonl_path"] == "fragments/SRC_000001/REV_000001/fragments.jsonl"
    assert report["outputs"]["ddl_report_path"] == "fragments/SRC_000001/REV_000001/ddl_report.json"

    table_names = {
        record["metadata"]["table_name"]
        for record in records
        if record["fragment_type"] == "ddl_table"
    }
    assert table_names == {"ANCLI", "ORDTES", "ORDRIG"}
    column_types = {
        (record["metadata"]["table_name"], record["metadata"]["column_name"]): record["metadata"]["data_type"]
        for record in records
        if record["fragment_type"] == "ddl_column"
    }
    assert column_types[("ANCLI", "CODCLI")] == "CHAR(10)"
    assert column_types[("ANCLI", "RAGSOC")] == "VARCHAR(80)"
    assert column_types[("ORDRIG", "QTA")] == "DECIMAL(9,2)"

    pk_records = [
        record
        for record in records
        if record["metadata"].get("constraint_kind") == "primary_key"
    ]
    assert [record["metadata"]["columns"] for record in pk_records] == [
        ["CODCLI"],
        ["IDORD"],
        ["IDORD", "RIGA"],
    ]
    for record in records:
        assert record["text_hash"] == _sha256_text(record["text"])
        assert "\\" not in record["path_or_selector"]
        assert record["metadata"]["parser"] == "parse_ddl"
        assert record["metadata"]["source_hash"]

    with _connect(workspace) as connection:
        source = connection.execute("SELECT * FROM sources").fetchone()
        db_counts = connection.execute(
            """
            SELECT fragment_type, COUNT(*) AS count
            FROM source_fragments
            WHERE status = 'active'
            GROUP BY fragment_type
            ORDER BY fragment_type
            """
        ).fetchall()

    assert (source["source_type"], source["source_subtype"], source["authority_level"]) == (
        "ddl",
        "mixed_ddl",
        "technical_structure",
    )
    assert [(row["fragment_type"], row["count"]) for row in db_counts] == [
        ("ddl_column", 12),
        ("ddl_constraint", 5),
        ("ddl_table", 3),
    ]
    _assert_parse_run_and_worker(workspace, expected_count=1)
    _assert_process_report(workspace, "RUN_000001")


def test_parse_ddl_foreign_keys(tmp_path, capsys):
    workspace = _workspace_with_ddl_fixture(tmp_path, capsys)
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "dsl_mngr",
            "corpus",
            "parse-ddl",
            str(workspace),
            "--revision",
            "REV_000001",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert completed.returncode == 0
    assert "Run: RUN_000001" in completed.stdout

    records = _read_jsonl(
        workspace / "fragments" / "SRC_000001" / "REV_000001" / "fragments.jsonl"
    )
    fk_records = [
        record
        for record in records
        if record["metadata"].get("constraint_kind") == "foreign_key"
    ]
    assert [
        (
            record["metadata"]["table_name"],
            record["metadata"]["columns"],
            record["metadata"]["references_table"],
            record["metadata"]["references_columns"],
            record["path_or_selector"],
        )
        for record in fk_records
    ] == [
        (
            "ORDTES",
            ["CODCLI"],
            "ANCLI",
            ["CODCLI"],
            "table:ORDTES/foreign_key:CODCLI->ANCLI.CODCLI",
        ),
        (
            "ORDRIG",
            ["IDORD"],
            "ORDTES",
            ["IDORD"],
            "table:ORDRIG/foreign_key:IDORD->ORDTES.IDORD",
        ),
    ]

    report = _read_json(workspace / "fragments" / "SRC_000001" / "REV_000001" / "ddl_report.json")
    assert report["ddl_objects"]["tables"][1]["constraints"][1]["constraint_kind"] == "foreign_key"
    assert report["ddl_objects"]["tables"][1]["constraints"][1]["references_table"] == "ANCLI"
    _assert_parse_run_and_worker(workspace, expected_count=1)


def test_parse_ddl_fragment_evidence_lookup(tmp_path, capsys):
    workspace = _workspace_with_ddl_fixture(tmp_path, capsys)
    assert main(["corpus", "parse-ddl", str(workspace), "--revision", "REV_000001"]) == 0
    capsys.readouterr()

    with _connect(workspace) as connection:
        fk_fragment = connection.execute(
            """
            SELECT fragment_id
            FROM source_fragments
            WHERE status = 'active'
              AND fragment_type = 'ddl_constraint'
              AND path_or_selector = 'table:ORDTES/foreign_key:CODCLI->ANCLI.CODCLI'
            """
        ).fetchone()

    candidate_path = workspace / "ai" / "inbox" / "ddl_fk_candidate.jsonl"
    candidate = {
        "assertion_type": "explicit",
        "candidate_id": "CAND_DDL_FK_001",
        "chunk_id": None,
        "confidence": "high",
        "evidence_text": "FOREIGN KEY (CODCLI) REFERENCES ANCLI(CODCLI)",
        "fragment_id": fk_fragment["fragment_id"],
        "record_type": "candidate_relation",
        "relation_type": "references",
        "source_entity": "ORDTES",
        "source_revision_id": "REV_000001",
        "target_entity": "ANCLI",
    }
    candidate_path.write_text(
        json.dumps(candidate, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    assert main(["candidates", "validate", str(workspace), "--input", str(candidate_path)]) == 0
    output = capsys.readouterr().out
    assert "Total: 1" in output
    assert "Accepted: 1" in output
    assert "Rejected: 0" in output

    with _connect(workspace) as connection:
        accepted = connection.execute("SELECT * FROM candidate_records").fetchone()
        rejected_count = connection.execute("SELECT COUNT(*) FROM rejected_candidates").fetchone()[0]

    assert accepted["fragment_id"] == fk_fragment["fragment_id"]
    assert accepted["chunk_id"] is None
    assert rejected_count == 0


def test_parse_ddl_idempotent_rerun(tmp_path, capsys):
    workspace = _workspace_with_ddl_fixture(tmp_path, capsys)
    assert main(["corpus", "parse-ddl", str(workspace), "--revision", "REV_000001"]) == 0
    capsys.readouterr()

    jsonl_path = workspace / "fragments" / "SRC_000001" / "REV_000001" / "fragments.jsonl"
    report_path = workspace / "fragments" / "SRC_000001" / "REV_000001" / "ddl_report.json"
    first_records = _read_jsonl(jsonl_path)
    first_ids = [record["fragment_id"] for record in first_records]
    first_hash = _read_json(report_path)["fragments_hash"]

    assert main(["corpus", "parse-ddl", str(workspace), "--revision", "REV_000001"]) == 0
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

    assert active_count == 20
    assert duplicate_active == []
    _assert_parse_run_and_worker(workspace, expected_count=2)


def test_parse_ddl_unsupported_option_fails_without_active_fragments(tmp_path, capsys):
    workspace = _workspace_with_ddl_fixture(tmp_path, capsys)
    bad_profile = workspace / "configs" / "workers" / "ddl.bad.yaml"
    bad_profile.write_text(
        (workspace / "configs" / "workers" / "ddl.default.yaml").read_text(encoding="utf-8")
        + "  unsupported_slice12_option: true\n",
        encoding="utf-8",
        newline="\n",
    )

    assert (
        main(
            [
                "corpus",
                "parse-ddl",
                str(workspace),
                "--revision",
                "REV_000001",
                "--profile",
                "ddl.bad",
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
    assert (run["run_type"], run["status"]) == ("parse_ddl", "failed")
    assert (worker["worker_name"], worker["status"], worker["exit_code"]) == (
        "parse_ddl",
        "failed",
        4,
    )

    report = _read_json(workspace / "artifacts" / "runs" / "RUN_000001" / "process_report.json")
    assert report["run_type"] == "parse_ddl"
    assert report["status"] == "failed"
    assert report["workers"][0]["exit_code"] == 4
    assert "unsupported_ddl_option" in report["workers"][0]["stderr"]
    assert "unsupported_slice12_option" in report["workers"][0]["stderr"]
    assert not (workspace / "fragments" / "SRC_000001" / "REV_000001" / "fragments.jsonl").exists()


def _workspace_with_ddl_fixture(tmp_path: Path, capsys) -> Path:
    workspace = tmp_path / "workspace"
    assert main(["init", str(workspace)]) == 0
    assert main(["db", "init", str(workspace)]) == 0
    capsys.readouterr()

    shutil.copyfile(DDL_FIXTURE, workspace / "corpus" / "active" / DDL_FIXTURE.name)
    assert main(["corpus", "scan", str(workspace)]) == 0
    scan_output = capsys.readouterr().out
    assert "Added: 1" in scan_output

    with _connect(workspace) as connection:
        source = connection.execute("SELECT * FROM sources").fetchone()
        revision = connection.execute("SELECT * FROM source_revisions").fetchone()

    assert source["source_id"] == "SRC_000001"
    assert source["source_type"] == "unknown"
    assert revision["source_revision_id"] == "REV_000001"
    assert revision["file_path"] == "corpus/active/schema_ordini.sql"
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
        ("parse_ddl", "completed")
    ] * expected_count
    assert [(row["worker_name"], row["status"], row["exit_code"]) for row in workers] == [
        ("parse_ddl", "completed", 0)
    ] * expected_count


def _assert_process_report(workspace: Path, run_id: str) -> None:
    artifact_dir = workspace / "artifacts" / "runs" / run_id
    input_payload = _read_json(artifact_dir / "input.json")
    output_payload = _read_json(artifact_dir / "output.json")
    report = _read_json(artifact_dir / "process_report.json")

    assert input_payload["source_id"] == "SRC_000001"
    assert input_payload["source_revision_id"] == "REV_000001"
    assert input_payload["source_hash"]
    assert input_payload["input_path"] == "corpus/active/schema_ordini.sql"
    assert input_payload["output_dir"] == "fragments/SRC_000001/REV_000001"
    assert input_payload["profile"] == "ddl.default"
    assert input_payload["ddl_options"]["dialect"] == "generic_sql"
    assert input_payload["fragment_id_by_sequence"] == {}
    assert input_payload["next_fragment_number"] == 1
    assert output_payload["worker_name"] == "parse_ddl"
    assert output_payload["status"] == "completed"
    assert output_payload["fragment_count"] == 20
    assert report["run_type"] == "parse_ddl"
    assert report["status"] == "completed"
    assert report["artifact_dir"] == f"artifacts/runs/{run_id}"
    assert report["workers"][0]["worker_name"] == "parse_ddl"
    assert report["workers"][0]["exit_code"] == 0
    for path_value in (
        input_payload["input_path"],
        input_payload["output_dir"],
        output_payload["fragments_jsonl_path"],
        output_payload["ddl_report_path"],
        report["artifact_dir"],
    ):
        assert "\\" not in path_value
        assert not Path(path_value).is_absolute()


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
