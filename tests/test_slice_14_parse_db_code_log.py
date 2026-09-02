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
DB_CODE_FIXTURE_DIR = TESTS_DIR / "fixtures" / "db_code"
LOG_FIXTURE = TESTS_DIR / "fixtures" / "logs" / "log_batch_ordini.log"


def test_parse_db_code_trigger(tmp_path, capsys):
    workspace = _workspace_with_db_code_fixtures(tmp_path / "db_code", capsys)
    assert (workspace / "configs" / "workers" / "db_code.default.yaml").is_file()

    assert main(["corpus", "parse-db-code", str(workspace), "--revision", "REV_000001"]) == 0
    procedure_output = capsys.readouterr().out
    assert "Run: RUN_000001" in procedure_output
    assert "Procedures: 1" in procedure_output
    assert "Triggers: 0" in procedure_output
    assert "Statements: 1" in procedure_output
    assert "Calls: 0" in procedure_output
    assert "Fragments JSONL: fragments/SRC_000001/REV_000001/fragments.jsonl" in procedure_output
    assert "Report: fragments/SRC_000001/REV_000001/db_code_report.json" in procedure_output

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "dsl_mngr",
            "corpus",
            "parse-db-code",
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
    assert "Procedures: 0" in completed.stdout
    assert "Triggers: 1" in completed.stdout
    assert "Statements: 1" in completed.stdout
    assert "Writes: 1" in completed.stdout
    assert "Calls: 0" in completed.stdout

    trigger_jsonl_path = workspace / "fragments" / "SRC_000002" / "REV_000002" / "fragments.jsonl"
    trigger_report_path = workspace / "fragments" / "SRC_000002" / "REV_000002" / "db_code_report.json"
    procedure_report_path = workspace / "fragments" / "SRC_000001" / "REV_000001" / "db_code_report.json"
    assert trigger_jsonl_path.is_file()
    assert trigger_report_path.is_file()
    assert procedure_report_path.is_file()

    trigger_records = _read_jsonl(trigger_jsonl_path)
    trigger_report = _read_json(trigger_report_path)
    procedure_report = _read_json(procedure_report_path)
    assert len(trigger_records) == 2
    assert trigger_report["trigger_count"] == 1
    assert trigger_report["procedure_count"] == 0
    assert trigger_report["statement_count"] == 1
    assert trigger_report["fragments_hash"] == _sha256_text(
        trigger_jsonl_path.read_text(encoding="utf-8")
    )
    assert trigger_report["outputs"]["fragments_jsonl_path"] == (
        "fragments/SRC_000002/REV_000002/fragments.jsonl"
    )
    assert trigger_report["outputs"]["db_code_report_path"] == (
        "fragments/SRC_000002/REV_000002/db_code_report.json"
    )
    assert procedure_report["db_code_objects"]["procedures"][0]["procedure_name"] == (
        "PRC_CALCOLA_SCONTO"
    )
    assert procedure_report["db_code_objects"]["procedures"][0]["parameters"] == [
        "P_CODCLI",
        "P_IDORD",
    ]
    assert "ORDTES.STATO" in procedure_report["writes"]

    trigger = _record_by_type(trigger_records, "sql_trigger")
    statement = _record_by_type(trigger_records, "sql_statement")
    assert trigger["metadata"]["parser"] == "parse_db_code"
    assert trigger["metadata"]["object_type"] == "trigger"
    assert trigger["metadata"]["trigger_name"] == "TRG_ORDTES_CONF"
    assert trigger["metadata"]["trigger_timing"] == "AFTER"
    assert trigger["metadata"]["trigger_event"] == "UPDATE"
    assert trigger["metadata"]["target_table"] == "ORDTES"
    assert "NEW.STATO" in trigger["metadata"]["reads"]
    assert "ORDTES.DATCONF" in trigger["metadata"]["writes"]
    assert trigger["metadata"]["calls"] == []
    assert statement["metadata"]["parent_object_name"] == "TRG_ORDTES_CONF"
    assert statement["metadata"]["parent_object_type"] == "trigger"
    assert statement["metadata"]["statement_kind"] == "UPDATE"
    assert "ORDTES.DATCONF" in statement["metadata"]["writes"]
    assert "NEW.IDORD" in statement["metadata"]["reads"]
    for record in trigger_records:
        assert record["text_hash"] == _sha256_text(record["text"])
        assert "\\" not in record["path_or_selector"]

    with _connect(workspace) as connection:
        sources = connection.execute(
            "SELECT source_id, source_type, source_subtype, authority_level FROM sources ORDER BY source_id"
        ).fetchall()
        counts = connection.execute(
            """
            SELECT source_revision_id, fragment_type, COUNT(*) AS count
            FROM source_fragments
            WHERE status = 'active'
            GROUP BY source_revision_id, fragment_type
            ORDER BY source_revision_id, fragment_type
            """
        ).fetchall()

    assert [
        (row["source_type"], row["source_subtype"], row["authority_level"])
        for row in sources
    ] == [
        ("database_code", "procedure", "runtime_code"),
        ("database_code", "trigger", "runtime_code"),
    ]
    assert [(row["source_revision_id"], row["fragment_type"], row["count"]) for row in counts] == [
        ("REV_000001", "sql_procedure", 1),
        ("REV_000001", "sql_statement", 1),
        ("REV_000002", "sql_statement", 1),
        ("REV_000002", "sql_trigger", 1),
    ]

    first_ids = [record["fragment_id"] for record in trigger_records]
    first_hash = trigger_report["fragments_hash"]
    assert main(["corpus", "parse-db-code", str(workspace), "--revision", "REV_000002"]) == 0
    rerun_output = capsys.readouterr().out
    assert "Run: RUN_000003" in rerun_output
    second_records = _read_jsonl(trigger_jsonl_path)
    assert [record["fragment_id"] for record in second_records] == first_ids
    assert _read_json(trigger_report_path)["fragments_hash"] == first_hash
    assert _sha256_text(trigger_jsonl_path.read_text(encoding="utf-8")) == first_hash

    with _connect(workspace) as connection:
        active_trigger_fragments = connection.execute(
            """
            SELECT COUNT(*)
            FROM source_fragments
            WHERE status = 'active'
              AND source_revision_id = 'REV_000002'
            """
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
    assert active_trigger_fragments == 2
    assert duplicate_active == []
    _assert_parse_run_and_worker(
        workspace,
        expected=[
            ("parse_db_code", "completed", 0),
            ("parse_db_code", "completed", 0),
            ("parse_db_code", "completed", 0),
        ],
    )
    _assert_process_report_db_code(workspace, "RUN_000002")

    candidate_path = workspace / "ai" / "inbox" / "db_code_candidate.jsonl"
    candidate = {
        "assertion_type": "explicit",
        "candidate_id": "CAND_SQL_TRIGGER_WRITES_001",
        "chunk_id": None,
        "confidence": "high",
        "entity_name": "TRG_ORDTES_CONF",
        "evidence_text": "SET DATCONF = CURRENT_DATE",
        "fact_type": "technical_behavior",
        "fragment_id": statement["fragment_id"],
        "property_name": "writes",
        "property_value": "ORDTES.DATCONF",
        "record_type": "candidate_fact",
        "source_revision_id": "REV_000002",
    }
    candidate_path.write_text(
        json.dumps(candidate, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    assert main(["candidates", "validate", str(workspace), "--input", str(candidate_path)]) == 0
    validation_output = capsys.readouterr().out
    assert "Batch: CBATCH_000001" in validation_output
    assert "Accepted: 1" in validation_output
    assert "Rejected: 0" in validation_output
    assert main(["facts", "merge", str(workspace), "--batch", "CBATCH_000001"]) == 0
    merge_output = capsys.readouterr().out
    assert "Facts created: 1" in merge_output

    with _connect(workspace) as connection:
        fact = connection.execute("SELECT * FROM facts").fetchone()
        evidence = connection.execute("SELECT * FROM fact_evidence").fetchone()
    assert (fact["entity_name"], fact["property_name"], fact["property_value"], fact["status"]) == (
        "TRG_ORDTES_CONF",
        "writes",
        "ORDTES.DATCONF",
        "active",
    )
    assert evidence["fragment_id"] == statement["fragment_id"]
    assert evidence["chunk_id"] is None

    bad_workspace = _workspace_with_single_db_code_fixture(tmp_path / "db_code_bad", capsys)
    bad_profile = bad_workspace / "configs" / "workers" / "db_code.bad.yaml"
    bad_profile.write_text(
        (bad_workspace / "configs" / "workers" / "db_code.default.yaml").read_text(
            encoding="utf-8"
        )
        + "  unsupported_slice14_option: true\n",
        encoding="utf-8",
        newline="\n",
    )
    assert (
        main(
            [
                "corpus",
                "parse-db-code",
                str(bad_workspace),
                "--revision",
                "REV_000001",
                "--profile",
                "db_code.bad",
            ]
        )
        == 2
    )
    captured = capsys.readouterr()
    assert "exit_code=4" in captured.err
    _assert_failed_worker_without_fragments(
        bad_workspace,
        run_type="parse_db_code",
        worker_name="parse_db_code",
        error_token="unsupported_db_code_option",
    )


def test_parse_log(tmp_path, capsys):
    workspace = _workspace_with_log_fixture(tmp_path / "log", capsys)
    assert (workspace / "configs" / "workers" / "log.default.yaml").is_file()

    assert main(["corpus", "parse-log", str(workspace), "--revision", "REV_000001"]) == 0
    output = capsys.readouterr().out
    assert "Run: RUN_000001" in output
    assert "Revision: REV_000001" in output
    assert "Source: SRC_000001" in output
    assert "Events: 4" in output
    assert "Warnings: 1" in output
    assert "Components: BATCH_ORDINI" in output
    assert "Fragments: 4" in output
    assert "Fragments JSONL: fragments/SRC_000001/REV_000001/fragments.jsonl" in output
    assert "Report: fragments/SRC_000001/REV_000001/log_report.json" in output

    jsonl_path = workspace / "fragments" / "SRC_000001" / "REV_000001" / "fragments.jsonl"
    report_path = workspace / "fragments" / "SRC_000001" / "REV_000001" / "log_report.json"
    records = _read_jsonl(jsonl_path)
    report = _read_json(report_path)
    assert len(records) == 4
    assert report["event_count"] == 4
    assert report["warning_count"] == 1
    assert report["components"] == ["BATCH_ORDINI"]
    assert report["fragments_hash"] == _sha256_text(jsonl_path.read_text(encoding="utf-8"))
    assert report["outputs"]["fragments_jsonl_path"] == (
        "fragments/SRC_000001/REV_000001/fragments.jsonl"
    )
    assert report["outputs"]["log_report_path"] == "fragments/SRC_000001/REV_000001/log_report.json"

    event_kinds = [record["metadata"]["event_kind"] for record in records]
    assert event_kinds == ["start", "processed", "warning", "end"]
    processed = records[1]
    warning = records[2]
    end = records[3]
    assert processed["metadata"]["timestamp"] == "2026-01-15 22:00:03"
    assert processed["metadata"]["level"] == "INFO"
    assert processed["metadata"]["component"] == "BATCH_ORDINI"
    assert processed["metadata"]["message"] == "processed order IDORD=1001 CODCLI=C000000001"
    assert processed["metadata"]["observed_identifiers"] == {
        "CODCLI": "C000000001",
        "IDORD": "1001",
    }
    assert warning["metadata"]["observed_identifiers"] == {"CODCLI": "C000000002"}
    assert end["metadata"]["observed_identifiers"] == {"processed": "2", "warnings": "1"}
    for record in records:
        assert record["fragment_type"] == "log_event"
        assert record["metadata"]["parser"] == "parse_log"
        assert record["metadata"]["object_type"] == "log_event"
        assert record["text_hash"] == _sha256_text(record["text"])
        assert "\\" not in record["path_or_selector"]

    with _connect(workspace) as connection:
        source = connection.execute("SELECT * FROM sources").fetchone()
        active_count = connection.execute(
            "SELECT COUNT(*) FROM source_fragments WHERE status = 'active'"
        ).fetchone()[0]
    assert (source["source_type"], source["source_subtype"], source["authority_level"]) == (
        "log",
        "batch_log",
        "runtime_observation",
    )
    assert active_count == 4
    _assert_process_report_log(workspace, "RUN_000001")

    first_ids = [record["fragment_id"] for record in records]
    first_hash = report["fragments_hash"]
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "dsl_mngr",
            "corpus",
            "parse-log",
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
    assert "Run: RUN_000002" in completed.stdout
    second_records = _read_jsonl(jsonl_path)
    assert [record["fragment_id"] for record in second_records] == first_ids
    assert _read_json(report_path)["fragments_hash"] == first_hash
    assert _sha256_text(jsonl_path.read_text(encoding="utf-8")) == first_hash
    _assert_parse_run_and_worker(
        workspace,
        expected=[
            ("parse_log", "completed", 0),
            ("parse_log", "completed", 0),
        ],
    )

    candidate_path = workspace / "ai" / "inbox" / "log_candidates.jsonl"
    evidence_text = "processed order IDORD=1001 CODCLI=C000000001"
    candidates = [
        {
            "assertion_type": "observed",
            "candidate_id": "CAND_LOG_EVENT_001",
            "chunk_id": None,
            "confidence": "high",
            "entity_name": "BATCH_ORDINI",
            "evidence_text": evidence_text,
            "fact_type": "runtime_event",
            "fragment_id": processed["fragment_id"],
            "property_name": "processed_order",
            "property_value": "IDORD=1001 CODCLI=C000000001",
            "record_type": "candidate_fact",
            "source_revision_id": "REV_000001",
        },
        {
            "assertion_type": "observed",
            "candidate_id": "CAND_LOG_OBSERVED_IN_001",
            "chunk_id": None,
            "confidence": "high",
            "evidence_text": evidence_text,
            "fragment_id": processed["fragment_id"],
            "record_type": "candidate_relation",
            "relation_type": "observed_in",
            "source_entity": "BATCH_ORDINI processed order IDORD=1001",
            "source_revision_id": "REV_000001",
            "target_entity": "log_batch_ordini.log",
        },
    ]
    candidate_path.write_text(
        "".join(json.dumps(candidate, ensure_ascii=False, sort_keys=True) + "\n" for candidate in candidates),
        encoding="utf-8",
        newline="\n",
    )
    assert main(["candidates", "validate", str(workspace), "--input", str(candidate_path)]) == 0
    validation_output = capsys.readouterr().out
    assert "Batch: CBATCH_000001" in validation_output
    assert "Accepted: 2" in validation_output
    assert "Rejected: 0" in validation_output
    assert main(["facts", "merge", str(workspace), "--batch", "CBATCH_000001"]) == 0
    merge_output = capsys.readouterr().out
    assert "Facts created: 1" in merge_output
    assert "Relations created: 1" in merge_output

    with _connect(workspace) as connection:
        fact = connection.execute("SELECT * FROM facts").fetchone()
        relation = connection.execute("SELECT * FROM relations").fetchone()
        fact_evidence = connection.execute("SELECT * FROM fact_evidence").fetchone()
        relation_evidence = connection.execute("SELECT * FROM relation_evidence").fetchone()
    assert (fact["entity_name"], fact["assertion_type"], fact["status"]) == (
        "BATCH_ORDINI",
        "observed",
        "active",
    )
    assert (
        relation["source_entity"],
        relation["relation_type"],
        relation["target_entity"],
        relation["assertion_type"],
        relation["status"],
    ) == (
        "BATCH_ORDINI processed order IDORD=1001",
        "observed_in",
        "log_batch_ordini.log",
        "observed",
        "active",
    )
    assert fact_evidence["fragment_id"] == processed["fragment_id"]
    assert relation_evidence["fragment_id"] == processed["fragment_id"]

    bad_workspace = _workspace_with_log_fixture(tmp_path / "log_bad", capsys)
    bad_profile = bad_workspace / "configs" / "workers" / "log.bad.yaml"
    bad_profile.write_text(
        (bad_workspace / "configs" / "workers" / "log.default.yaml").read_text(encoding="utf-8")
        + "  unsupported_slice14_option: true\n",
        encoding="utf-8",
        newline="\n",
    )
    assert (
        main(
            [
                "corpus",
                "parse-log",
                str(bad_workspace),
                "--revision",
                "REV_000001",
                "--profile",
                "log.bad",
            ]
        )
        == 2
    )
    captured = capsys.readouterr()
    assert "exit_code=4" in captured.err
    _assert_failed_worker_without_fragments(
        bad_workspace,
        run_type="parse_log",
        worker_name="parse_log",
        error_token="unsupported_log_option",
    )


def _workspace_with_db_code_fixtures(base_path: Path, capsys) -> Path:
    workspace = base_path / "workspace"
    assert main(["init", str(workspace)]) == 0
    assert main(["db", "init", str(workspace)]) == 0
    capsys.readouterr()

    shutil.copytree(DB_CODE_FIXTURE_DIR, workspace / "corpus" / "active", dirs_exist_ok=True)
    assert main(["corpus", "scan", str(workspace)]) == 0
    scan_output = capsys.readouterr().out
    assert "Added: 2" in scan_output

    with _connect(workspace) as connection:
        sources = connection.execute("SELECT * FROM sources ORDER BY source_id").fetchall()
        revisions = connection.execute(
            "SELECT * FROM source_revisions ORDER BY source_revision_id"
        ).fetchall()

    assert [source["source_type"] for source in sources] == ["unknown", "unknown"]
    assert [revision["source_revision_id"] for revision in revisions] == [
        "REV_000001",
        "REV_000002",
    ]
    assert revisions[0]["file_path"] == "corpus/active/procedura_sconti.sql"
    assert revisions[1]["file_path"] == "corpus/active/trigger_ordini.sql"
    for revision in revisions:
        assert revision["content_hash"] == _sha256_file(workspace / revision["file_path"])
    return workspace


def _workspace_with_single_db_code_fixture(base_path: Path, capsys) -> Path:
    workspace = base_path / "workspace"
    assert main(["init", str(workspace)]) == 0
    assert main(["db", "init", str(workspace)]) == 0
    capsys.readouterr()
    shutil.copyfile(
        DB_CODE_FIXTURE_DIR / "trigger_ordini.sql",
        workspace / "corpus" / "active" / "trigger_ordini.sql",
    )
    assert main(["corpus", "scan", str(workspace)]) == 0
    capsys.readouterr()
    return workspace


def _workspace_with_log_fixture(base_path: Path, capsys) -> Path:
    workspace = base_path / "workspace"
    assert main(["init", str(workspace)]) == 0
    assert main(["db", "init", str(workspace)]) == 0
    capsys.readouterr()

    shutil.copyfile(LOG_FIXTURE, workspace / "corpus" / "active" / LOG_FIXTURE.name)
    assert main(["corpus", "scan", str(workspace)]) == 0
    scan_output = capsys.readouterr().out
    assert "Added: 1" in scan_output

    with _connect(workspace) as connection:
        source = connection.execute("SELECT * FROM sources").fetchone()
        revision = connection.execute("SELECT * FROM source_revisions").fetchone()
    assert source["source_type"] == "unknown"
    assert revision["source_revision_id"] == "REV_000001"
    assert revision["file_path"] == "corpus/active/log_batch_ordini.log"
    assert revision["content_hash"] == _sha256_file(workspace / revision["file_path"])
    return workspace


def _assert_parse_run_and_worker(workspace: Path, *, expected: list[tuple[str, str, int]]) -> None:
    with _connect(workspace) as connection:
        runs = connection.execute(
            "SELECT run_type, status FROM runs ORDER BY run_id"
        ).fetchall()
        workers = connection.execute(
            "SELECT worker_name, status, exit_code FROM worker_runs ORDER BY worker_run_id"
        ).fetchall()

    assert [(row["run_type"], row["status"]) for row in runs] == [
        (worker_name, status) for worker_name, status, _exit_code in expected
    ]
    assert [(row["worker_name"], row["status"], row["exit_code"]) for row in workers] == expected


def _assert_process_report_db_code(workspace: Path, run_id: str) -> None:
    artifact_dir = workspace / "artifacts" / "runs" / run_id
    input_payload = _read_json(artifact_dir / "input.json")
    output_payload = _read_json(artifact_dir / "output.json")
    report = _read_json(artifact_dir / "process_report.json")

    assert input_payload["source_id"] == "SRC_000002"
    assert input_payload["source_revision_id"] == "REV_000002"
    assert input_payload["input_path"] == "corpus/active/trigger_ordini.sql"
    assert input_payload["output_dir"] == "fragments/SRC_000002/REV_000002"
    assert input_payload["profile"] == "db_code.default"
    assert input_payload["db_code_options"]["dialect"] == "generic_sql"
    assert output_payload["worker_name"] == "parse_db_code"
    assert output_payload["status"] == "completed"
    assert output_payload["fragment_count"] == 2
    assert report["run_type"] == "parse_db_code"
    assert report["status"] == "completed"
    assert report["workers"][0]["worker_name"] == "parse_db_code"
    assert report["workers"][0]["exit_code"] == 0
    for path_value in (
        input_payload["input_path"],
        input_payload["output_dir"],
        output_payload["fragments_jsonl_path"],
        output_payload["db_code_report_path"],
        report["artifact_dir"],
    ):
        assert "\\" not in path_value
        assert not Path(path_value).is_absolute()


def _assert_process_report_log(workspace: Path, run_id: str) -> None:
    artifact_dir = workspace / "artifacts" / "runs" / run_id
    input_payload = _read_json(artifact_dir / "input.json")
    output_payload = _read_json(artifact_dir / "output.json")
    report = _read_json(artifact_dir / "process_report.json")

    assert input_payload["source_id"] == "SRC_000001"
    assert input_payload["source_revision_id"] == "REV_000001"
    assert input_payload["input_path"] == "corpus/active/log_batch_ordini.log"
    assert input_payload["output_dir"] == "fragments/SRC_000001/REV_000001"
    assert input_payload["profile"] == "log.default"
    assert input_payload["log_options"]["parser"] == "line_regex"
    assert output_payload["worker_name"] == "parse_log"
    assert output_payload["status"] == "completed"
    assert output_payload["fragment_count"] == 4
    assert report["run_type"] == "parse_log"
    assert report["status"] == "completed"
    assert report["workers"][0]["worker_name"] == "parse_log"
    assert report["workers"][0]["exit_code"] == 0
    for path_value in (
        input_payload["input_path"],
        input_payload["output_dir"],
        output_payload["fragments_jsonl_path"],
        output_payload["log_report_path"],
        report["artifact_dir"],
    ):
        assert "\\" not in path_value
        assert not Path(path_value).is_absolute()


def _assert_failed_worker_without_fragments(
    workspace: Path,
    *,
    run_type: str,
    worker_name: str,
    error_token: str,
) -> None:
    with _connect(workspace) as connection:
        active_fragments = connection.execute(
            "SELECT COUNT(*) FROM source_fragments WHERE status = 'active'"
        ).fetchone()[0]
        run = connection.execute("SELECT run_type, status FROM runs").fetchone()
        worker = connection.execute(
            "SELECT worker_name, status, exit_code FROM worker_runs"
        ).fetchone()
    assert active_fragments == 0
    assert (run["run_type"], run["status"]) == (run_type, "failed")
    assert (worker["worker_name"], worker["status"], worker["exit_code"]) == (
        worker_name,
        "failed",
        4,
    )
    report = _read_json(workspace / "artifacts" / "runs" / "RUN_000001" / "process_report.json")
    assert report["run_type"] == run_type
    assert report["status"] == "failed"
    assert report["workers"][0]["exit_code"] == 4
    assert error_token in report["workers"][0]["stderr"]
    assert "unsupported_slice14_option" in report["workers"][0]["stderr"]
    assert not (workspace / "fragments" / "SRC_000001" / "REV_000001" / "fragments.jsonl").exists()


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
