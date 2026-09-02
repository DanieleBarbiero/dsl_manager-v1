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
XML_FIXTURE = TESTS_DIR / "fixtures" / "xml_forms" / "form_cliente.xml"
LOG_FIXTURE = TESTS_DIR / "fixtures" / "logs" / "log_batch_ordini.log"
CORPUS_FIXTURE_DIR = TESTS_DIR / "fixtures" / "corpus_initial"


def test_batch_report(tmp_path, capsys):
    workspace = _workspace(tmp_path / "report", capsys)
    _copy_process_fixtures(workspace, include_unsupported=True)

    assert main(["batch", "process-dir", str(workspace)]) == 0
    output = capsys.readouterr().out
    assert "Run: RUN_000001" in output
    assert "Command: process-dir" in output
    assert "Items: 4" in output
    assert "Completed: 3" in output
    assert "Failed: 0" in output
    assert "Skipped: 1" in output
    assert "Report: artifacts/runs/RUN_000001/batch_report.json" in output

    batch_report = _read_json(workspace / "artifacts" / "runs" / "RUN_000001" / "batch_report.json")
    process_report = _read_json(
        workspace / "artifacts" / "runs" / "RUN_000001" / "process_report.json"
    )
    output_payload = _read_json(workspace / "artifacts" / "runs" / "RUN_000001" / "output.json")
    input_payload = _read_json(workspace / "artifacts" / "runs" / "RUN_000001" / "input.json")

    assert batch_report["run_id"] == "RUN_000001"
    assert batch_report["run_type"] == "batch"
    assert batch_report["batch_command"] == "process-dir"
    assert batch_report["status"] == "completed"
    assert batch_report["summary"] == {
        "completed": 3,
        "failed": 0,
        "skipped": 1,
        "total": 4,
    }
    assert process_report["summary"] == batch_report["summary"]
    assert process_report["items"] == batch_report["items"]
    assert output_payload["summary"] == batch_report["summary"]
    assert output_payload["batch_report_path"] == "artifacts/runs/RUN_000001/batch_report.json"
    assert input_payload["batch_command"] == "process-dir"
    assert input_payload["options"]["path"] == "corpus/active"
    assert len(input_payload["planned_items"]) == 4

    assert [item["kind"] for item in batch_report["items"]] == [
        "parse_ddl",
        "parse_xml_form",
        "parse_log",
        "unsupported_source_type",
    ]
    assert [item["status"] for item in batch_report["items"]] == [
        "completed",
        "completed",
        "completed",
        "skipped",
    ]
    assert batch_report["items"][3]["reason"] == "unsupported_source_type"
    _assert_report_paths_relative(batch_report)

    with _connect(workspace) as connection:
        runs = connection.execute(
            "SELECT run_id, run_type, status, parent_run_id FROM runs ORDER BY run_id"
        ).fetchall()
        fragments = connection.execute(
            "SELECT fragment_type, COUNT(*) AS count FROM source_fragments "
            "WHERE status = 'active' GROUP BY fragment_type ORDER BY fragment_type"
        ).fetchall()

    assert [(row["run_type"], row["status"], row["parent_run_id"]) for row in runs] == [
        ("batch", "completed", None),
        ("parse_ddl", "completed", "RUN_000001"),
        ("parse_xml_form", "completed", "RUN_000001"),
        ("parse_log", "completed", "RUN_000001"),
    ]
    assert {row["fragment_type"] for row in fragments} >= {
        "ddl_table",
        "log_event",
        "xml_form",
    }

    log_events = _read_jsonl(workspace / "artifacts" / "runs" / "RUN_000001" / "log.jsonl")
    assert {record["event"] for record in log_events} >= {
        "batch_started",
        "batch_item_completed",
        "batch_completed",
    }

    module_workspace = _workspace(tmp_path / "module_entrypoint", capsys)
    shutil.copyfile(LOG_FIXTURE, module_workspace / "corpus" / "active" / "01_log.log")
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "dsl_mngr",
            "batch",
            "process-dir",
            str(module_workspace),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert completed.returncode == 0
    assert "Run: RUN_000001" in completed.stdout
    assert "Command: process-dir" in completed.stdout


def test_batch_continues_on_error(tmp_path, capsys):
    workspace = _workspace(tmp_path / "continue", capsys)
    _copy_failure_process_fixtures(workspace)

    assert main(["batch", "process-dir", str(workspace)]) == 2
    output = capsys.readouterr().out
    assert "Run: RUN_000001" in output
    assert "Completed: 2" in output
    assert "Failed: 1" in output
    assert "Skipped: 0" in output
    assert "Failed items:" in output
    assert "BITEM_000002 parse_xml_form REV_000002" in output

    batch_report = _read_json(workspace / "artifacts" / "runs" / "RUN_000001" / "batch_report.json")
    assert batch_report["status"] == "failed"
    assert batch_report["summary"] == {
        "completed": 2,
        "failed": 1,
        "skipped": 0,
        "total": 3,
    }
    assert [item["status"] for item in batch_report["items"]] == [
        "completed",
        "failed",
        "completed",
    ]
    assert batch_report["items"][1]["run_id"] == "RUN_000003"
    assert batch_report["items"][1]["exit_code"] == 5
    assert "xml" in batch_report["items"][1]["error"].lower()

    with _connect(workspace) as connection:
        runs = connection.execute(
            "SELECT run_id, run_type, status, parent_run_id FROM runs ORDER BY run_id"
        ).fetchall()
        log_fragments = connection.execute(
            "SELECT COUNT(*) FROM source_fragments WHERE fragment_type = 'log_event'"
        ).fetchone()[0]

    assert [(row["run_type"], row["status"], row["parent_run_id"]) for row in runs] == [
        ("batch", "failed", None),
        ("parse_ddl", "completed", "RUN_000001"),
        ("parse_xml_form", "failed", "RUN_000001"),
        ("parse_log", "completed", "RUN_000001"),
    ]
    assert log_fragments == 4


def test_batch_stop_on_error(tmp_path, capsys):
    workspace = _workspace(tmp_path / "stop", capsys)
    _copy_failure_process_fixtures(workspace)

    assert main(["batch", "process-dir", str(workspace), "--stop-on-error"]) == 2
    output = capsys.readouterr().out
    assert "Completed: 1" in output
    assert "Failed: 1" in output
    assert "Skipped: 1" in output

    batch_report = _read_json(workspace / "artifacts" / "runs" / "RUN_000001" / "batch_report.json")
    assert batch_report["status"] == "failed"
    assert batch_report["stop_on_error"] is True
    assert [item["status"] for item in batch_report["items"]] == [
        "completed",
        "failed",
        "skipped",
    ]
    assert batch_report["items"][2]["kind"] == "parse_log"
    assert batch_report["items"][2]["reason"] == "stopped_after_error"
    assert batch_report["items"][2]["run_id"] is None

    with _connect(workspace) as connection:
        runs = connection.execute(
            "SELECT run_type, status, parent_run_id FROM runs ORDER BY run_id"
        ).fetchall()
        log_fragments = connection.execute(
            "SELECT COUNT(*) FROM source_fragments WHERE fragment_type = 'log_event'"
        ).fetchone()[0]

    assert [(row["run_type"], row["status"], row["parent_run_id"]) for row in runs] == [
        ("batch", "failed", None),
        ("parse_ddl", "completed", "RUN_000001"),
        ("parse_xml_form", "failed", "RUN_000001"),
    ]
    assert log_fragments == 0


def test_batch_other_commands_smoke(tmp_path, capsys):
    workspace = _workspace(tmp_path / "smoke", capsys)
    shutil.copytree(CORPUS_FIXTURE_DIR, workspace / "corpus" / "active", dirs_exist_ok=True)
    assert main(["corpus", "scan", str(workspace)]) == 0
    capsys.readouterr()
    _prepare_normalized_outputs(workspace)

    assert main(["batch", "chunk-dir", str(workspace)]) == 0
    chunk_output = capsys.readouterr().out
    assert "Run: RUN_000001" in chunk_output
    assert "Command: chunk-dir" in chunk_output
    assert "Items: 2" in chunk_output
    assert "Completed: 2" in chunk_output
    _assert_parent_for_subruns(workspace, "RUN_000001", ("chunk", "chunk"))

    assert main(["ai", "package-batch", str(workspace)]) == 0
    package_output = capsys.readouterr().out
    assert "Run: RUN_000004" in package_output
    assert "Command: package-batch" in package_output
    assert "Completed: 2" in package_output
    _assert_parent_for_subruns(workspace, "RUN_000004", ("ai_package", "ai_package"))

    _write_batch_candidates(workspace)
    assert main(["candidates", "validate-batch", str(workspace)]) == 0
    validate_output = capsys.readouterr().out
    assert "Run: RUN_000007" in validate_output
    assert "Command: validate-batch" in validate_output
    assert "Completed: 2" in validate_output
    _assert_parent_for_subruns(
        workspace,
        "RUN_000007",
        ("candidate_validation", "candidate_validation"),
    )

    with _connect(workspace) as connection:
        facts_before_merge = connection.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
        relations_before_merge = connection.execute("SELECT COUNT(*) FROM relations").fetchone()[0]
    assert facts_before_merge == 0
    assert relations_before_merge == 0

    assert main(["facts", "merge-batch", str(workspace)]) == 0
    merge_output = capsys.readouterr().out
    assert "Run: RUN_000010" in merge_output
    assert "Command: merge-batch" in merge_output
    assert "Completed: 2" in merge_output
    _assert_parent_for_subruns(workspace, "RUN_000010", ("merge", "merge"))

    with _connect(workspace) as connection:
        facts_after_merge = connection.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
        relations_after_merge = connection.execute("SELECT COUNT(*) FROM relations").fetchone()[0]
        dsl_snapshots = connection.execute("SELECT COUNT(*) FROM dsl_snapshots").fetchone()[0]

    assert facts_after_merge == 1
    assert relations_after_merge == 1
    assert dsl_snapshots == 0


def _workspace(base_path: Path, capsys) -> Path:
    workspace = base_path / "workspace"
    assert main(["init", str(workspace)]) == 0
    assert main(["db", "init", str(workspace)]) == 0
    capsys.readouterr()
    return workspace


def _copy_process_fixtures(workspace: Path, *, include_unsupported: bool = False) -> None:
    shutil.copyfile(DDL_FIXTURE, workspace / "corpus" / "active" / "01_schema_ordini.sql")
    shutil.copyfile(XML_FIXTURE, workspace / "corpus" / "active" / "02_form_cliente.xml")
    shutil.copyfile(LOG_FIXTURE, workspace / "corpus" / "active" / "03_log_batch_ordini.log")
    if include_unsupported:
        (workspace / "corpus" / "active" / "04_notes.csv").write_text(
            "id,value\n1,unsupported\n",
            encoding="utf-8",
            newline="\n",
        )


def _copy_failure_process_fixtures(workspace: Path) -> None:
    shutil.copyfile(DDL_FIXTURE, workspace / "corpus" / "active" / "01_schema_ordini.sql")
    (workspace / "corpus" / "active" / "02_bad_form.xml").write_text(
        "<form name=\"BROKEN\"><field></form",
        encoding="utf-8",
        newline="\n",
    )
    shutil.copyfile(LOG_FIXTURE, workspace / "corpus" / "active" / "03_log_batch_ordini.log")


def _prepare_normalized_outputs(workspace: Path) -> None:
    with _connect(workspace) as connection:
        revisions = connection.execute(
            """
            SELECT source_id, source_revision_id, file_path, content_hash
            FROM source_revisions
            ORDER BY file_path
            """
        ).fetchall()
        for revision in revisions:
            markdown = (workspace / revision["file_path"]).read_text(encoding="utf-8")
            markdown = markdown.replace("\r\n", "\n").replace("\r", "\n")
            normalized_hash = _sha256_text(markdown)
            output_dir = (
                workspace
                / "normalized"
                / revision["source_id"]
                / revision["source_revision_id"]
            )
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "normalized.md").write_text(markdown, encoding="utf-8", newline="\n")
            (output_dir / "normalized.json").write_text(
                json.dumps(
                    {
                        "schema_name": "DoclingDocument",
                        "source_revision_id": revision["source_revision_id"],
                        "texts": [{"text_hash": normalized_hash}],
                    },
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
                newline="\n",
            )
            (output_dir / "source_hash.txt").write_text(
                revision["content_hash"] + "\n",
                encoding="utf-8",
                newline="\n",
            )
            connection.execute(
                """
                UPDATE source_revisions
                SET normalized_hash = ?
                WHERE source_revision_id = ?
                """,
                (normalized_hash, revision["source_revision_id"]),
            )
        connection.commit()


def _write_batch_candidates(workspace: Path) -> None:
    candidates = [
        (
            "01_cliente.jsonl",
            {
                "assertion_type": "explicit",
                "candidate_id": "CAND_BATCH_FACT_001",
                "chunk_id": "CHK_000001",
                "confidence": "high",
                "entity_name": "Cliente",
                "evidence_text": "Cliente è una business entity del dominio commerciale.",
                "fact_type": "business_entity",
                "property_name": "description",
                "property_value": "Cliente del dominio commerciale",
                "record_type": "candidate_fact",
                "source_revision_id": "REV_000001",
            },
        ),
        (
            "02_ordini.jsonl",
            {
                "assertion_type": "explicit",
                "candidate_id": "CAND_BATCH_REL_001",
                "chunk_id": "CHK_000002",
                "confidence": "high",
                "evidence_text": "Il cliente può inserire uno o più ordini.",
                "record_type": "candidate_relation",
                "relation_type": "places",
                "source_entity": "Cliente",
                "source_revision_id": "REV_000002",
                "target_entity": "Ordine",
            },
        ),
    ]
    for filename, payload in candidates:
        (workspace / "ai" / "inbox" / filename).write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )


def _assert_parent_for_subruns(
    workspace: Path,
    parent_run_id: str,
    expected_run_types: tuple[str, ...],
) -> None:
    with _connect(workspace) as connection:
        rows = connection.execute(
            """
            SELECT run_type, status, parent_run_id
            FROM runs
            WHERE parent_run_id = ?
            ORDER BY run_id
            """,
            (parent_run_id,),
        ).fetchall()
    assert [row["run_type"] for row in rows] == list(expected_run_types)
    assert [row["status"] for row in rows] == ["completed"] * len(expected_run_types)
    assert [row["parent_run_id"] for row in rows] == [parent_run_id] * len(expected_run_types)


def _assert_report_paths_relative(payload: object) -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key.endswith("_path") or key == "input_path":
                assert isinstance(value, str)
                assert "\\" not in value
                assert not Path(value).is_absolute()
            _assert_report_paths_relative(value)
    elif isinstance(payload, list):
        for item in payload:
            _assert_report_paths_relative(item)


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _connect(workspace: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(workspace / "workspace.sqlite")
    connection.row_factory = sqlite3.Row
    return connection
