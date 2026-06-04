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
CORPUS_FIXTURE_DIR = TESTS_DIR / "fixtures" / "corpus_initial"
CANDIDATE_FIXTURE = (
    TESTS_DIR / "fixtures" / "ai_candidates" / "AIPKG_MANUALI_001_candidates.jsonl"
)


def test_chunking_stable(tmp_path, capsys):
    workspace = _workspace_with_normalized_fixtures(tmp_path, capsys)
    assert (workspace / "configs" / "workers" / "docling.chunking.yaml").is_file()

    assert main(["corpus", "chunk", str(workspace), "--revision", "REV_000001"]) == 0
    first_output = capsys.readouterr().out
    assert "Run: RUN_000001" in first_output
    assert "Revision: REV_000001" in first_output
    assert "Source: SRC_000001" in first_output
    assert "Chunks: 1" in first_output
    assert "Chunks JSONL: chunks/SRC_000001/REV_000001/chunks.jsonl" in first_output
    assert "Report: chunks/SRC_000001/REV_000001/chunk_report.json" in first_output

    assert main(["corpus", "chunk", str(workspace), "--revision", "REV_000002"]) == 0
    second_output = capsys.readouterr().out
    assert "Run: RUN_000002" in second_output
    assert "Chunks: 1" in second_output

    first_jsonl = workspace / "chunks" / "SRC_000001" / "REV_000001" / "chunks.jsonl"
    first_report = workspace / "chunks" / "SRC_000001" / "REV_000001" / "chunk_report.json"
    second_jsonl = workspace / "chunks" / "SRC_000002" / "REV_000002" / "chunks.jsonl"
    second_report = workspace / "chunks" / "SRC_000002" / "REV_000002" / "chunk_report.json"
    for path in (first_jsonl, first_report, second_jsonl, second_report):
        assert path.is_file()

    first_records = _read_jsonl(first_jsonl)
    second_records = _read_jsonl(second_jsonl)
    assert [record["chunk_id"] for record in first_records + second_records] == [
        "CHK_000001",
        "CHK_000002",
    ]
    _assert_chunk_record(first_records[0], "REV_000001", 1)
    _assert_chunk_record(second_records[0], "REV_000002", 1)
    assert first_records[0]["metadata"]["start_char"] == 0
    assert first_records[0]["metadata"]["heading_path"] == ["Manuale clienti"]
    assert second_records[0]["metadata"]["heading_path"] == ["Manuale ordini"]

    first_hash = _read_json(first_report)["chunks_hash"]
    second_hash = _read_json(second_report)["chunks_hash"]
    assert _sha256_text(first_jsonl.read_text(encoding="utf-8")) == first_hash
    assert _sha256_text(second_jsonl.read_text(encoding="utf-8")) == second_hash

    assert main(["corpus", "chunk", str(workspace), "--revision", "REV_000001"]) == 0
    rerun_output = capsys.readouterr().out
    assert "Run: RUN_000003" in rerun_output
    assert _read_json(first_report)["chunks_hash"] == first_hash
    assert _read_jsonl(first_jsonl)[0]["chunk_id"] == "CHK_000001"
    _assert_no_duplicate_active_chunks(workspace)

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "dsl_mngr",
            "corpus",
            "chunk",
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
    assert "Run: RUN_000004" in completed.stdout
    assert _read_json(second_report)["chunks_hash"] == second_hash
    assert _read_jsonl(second_jsonl)[0]["chunk_id"] == "CHK_000002"
    _assert_no_duplicate_active_chunks(workspace)
    _assert_chunk_runs_and_workers(workspace, expected_count=4)
    _assert_process_reports(workspace, expected_count=4)


def test_chunk_evidence_lookup(tmp_path, capsys):
    workspace = _workspace_with_normalized_fixtures(tmp_path, capsys)
    assert main(["corpus", "chunk", str(workspace), "--revision", "REV_000001"]) == 0
    assert main(["corpus", "chunk", str(workspace), "--revision", "REV_000002"]) == 0
    capsys.readouterr()

    candidate_input = workspace / "ai" / "inbox" / CANDIDATE_FIXTURE.name
    shutil.copyfile(CANDIDATE_FIXTURE, candidate_input)
    assert main(["candidates", "validate", str(workspace), "--input", str(candidate_input)]) == 0
    output = capsys.readouterr().out
    assert "Total: 8" in output
    assert "Accepted: 8" in output
    assert "Rejected: 0" in output

    with _connect(workspace) as connection:
        accepted_count = connection.execute("SELECT COUNT(*) FROM candidate_records").fetchone()[0]
        rejected_count = connection.execute("SELECT COUNT(*) FROM rejected_candidates").fetchone()[0]
        batch = connection.execute("SELECT * FROM candidate_batches").fetchone()

    assert accepted_count == 8
    assert rejected_count == 0
    assert batch["input_path"] == "ai/inbox/AIPKG_MANUALI_001_candidates.jsonl"
    assert batch["status"] == "completed"


def test_chunk_unsupported_option_fails_without_active_chunks(tmp_path, capsys):
    workspace = _workspace_with_normalized_fixtures(tmp_path, capsys)
    bad_profile = workspace / "configs" / "workers" / "docling.bad_chunking.yaml"
    bad_profile.write_text(
        (workspace / "configs" / "workers" / "docling.chunking.yaml").read_text(
            encoding="utf-8"
        )
        + "  unsupported_slice11_option: true\n",
        encoding="utf-8",
        newline="\n",
    )

    assert (
        main(
            [
                "corpus",
                "chunk",
                str(workspace),
                "--revision",
                "REV_000001",
                "--profile",
                "docling.bad_chunking",
            ]
        )
        == 2
    )
    captured = capsys.readouterr()
    assert "exit_code=4" in captured.err

    with _connect(workspace) as connection:
        active_chunks = connection.execute(
            "SELECT COUNT(*) FROM chunks WHERE status = 'active'"
        ).fetchone()[0]
        run = connection.execute("SELECT run_type, status FROM runs").fetchone()
        worker = connection.execute(
            "SELECT worker_name, status, exit_code FROM worker_runs"
        ).fetchone()

    assert active_chunks == 0
    assert (run["run_type"], run["status"]) == ("chunk", "failed")
    assert (worker["worker_name"], worker["status"], worker["exit_code"]) == (
        "chunk_docling",
        "failed",
        4,
    )

    report = _read_json(workspace / "artifacts" / "runs" / "RUN_000001" / "process_report.json")
    assert report["run_type"] == "chunk"
    assert report["status"] == "failed"
    assert report["workers"][0]["exit_code"] == 4
    assert "unsupported_chunking_option" in report["workers"][0]["stderr"]
    assert "unsupported_slice11_option" in report["workers"][0]["stderr"]


def _workspace_with_normalized_fixtures(tmp_path: Path, capsys) -> Path:
    workspace = tmp_path / "workspace"
    assert main(["init", str(workspace)]) == 0
    assert main(["db", "init", str(workspace)]) == 0
    capsys.readouterr()

    shutil.copytree(CORPUS_FIXTURE_DIR, workspace / "corpus" / "active", dirs_exist_ok=True)
    assert main(["corpus", "scan", str(workspace)]) == 0
    scan_output = capsys.readouterr().out
    assert "Added: 2" in scan_output
    _prepare_normalized_outputs(workspace)
    return workspace


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


def _assert_chunk_record(record: dict[str, object], source_revision_id: str, sequence: int) -> None:
    assert record["source_revision_id"] == source_revision_id
    assert record["sequence"] == sequence
    assert record["status"] == "active"
    assert isinstance(record["text"], str)
    assert record["text"].endswith("\n")
    assert "\r" not in record["text"]
    assert record["text_hash"] == _sha256_text(record["text"])
    metadata = record["metadata"]
    assert metadata["chunker"] == "chunk_docling"
    assert metadata["chunker_version"] == "1.0"
    assert metadata["strategy"] == "heading_paragraph"
    assert metadata["normalized_markdown_path"].endswith("/normalized.md")
    assert metadata["normalized_json_path"].endswith("/normalized.json")
    assert metadata["source_text_kind"] == "normalized_markdown"
    for key in ("normalized_markdown_path", "normalized_json_path"):
        assert "\\" not in metadata[key]
        assert not Path(metadata[key]).is_absolute()


def _assert_no_duplicate_active_chunks(workspace: Path) -> None:
    with _connect(workspace) as connection:
        rows = connection.execute(
            """
            SELECT chunk_id, source_revision_id, sequence, status
            FROM chunks
            WHERE status = 'active'
            ORDER BY chunk_id
            """
        ).fetchall()
        duplicate_active = connection.execute(
            """
            SELECT source_revision_id, sequence, COUNT(*) AS count
            FROM chunks
            WHERE status = 'active'
            GROUP BY source_revision_id, sequence
            HAVING COUNT(*) > 1
            """
        ).fetchall()

    assert [
        (row["chunk_id"], row["source_revision_id"], row["sequence"], row["status"])
        for row in rows
    ] == [
        ("CHK_000001", "REV_000001", 1, "active"),
        ("CHK_000002", "REV_000002", 1, "active"),
    ]
    assert duplicate_active == []


def _assert_chunk_runs_and_workers(workspace: Path, *, expected_count: int) -> None:
    with _connect(workspace) as connection:
        runs = connection.execute(
            "SELECT run_id, run_type, status FROM runs ORDER BY run_id"
        ).fetchall()
        workers = connection.execute(
            "SELECT worker_name, status, exit_code FROM worker_runs ORDER BY worker_run_id"
        ).fetchall()

    assert [(row["run_type"], row["status"]) for row in runs] == [
        ("chunk", "completed")
    ] * expected_count
    assert [(row["worker_name"], row["status"], row["exit_code"]) for row in workers] == [
        ("chunk_docling", "completed", 0)
    ] * expected_count


def _assert_process_reports(workspace: Path, *, expected_count: int) -> None:
    for index in range(1, expected_count + 1):
        run_id = f"RUN_{index:06d}"
        artifact_dir = workspace / "artifacts" / "runs" / run_id
        input_payload = _read_json(artifact_dir / "input.json")
        output_payload = _read_json(artifact_dir / "output.json")
        report = _read_json(artifact_dir / "process_report.json")

        assert input_payload["source_id"].startswith("SRC_")
        assert input_payload["source_revision_id"].startswith("REV_")
        assert input_payload["normalized_hash"]
        assert input_payload["normalized_markdown_path"].endswith("/normalized.md")
        assert input_payload["normalized_json_path"].endswith("/normalized.json")
        assert input_payload["source_hash_path"].endswith("/source_hash.txt")
        assert input_payload["output_dir"].startswith("chunks/")
        assert input_payload["profile"] == "docling.chunking"
        assert input_payload["chunking_options"]["strategy"] == "heading_paragraph"
        assert output_payload["worker_name"] == "chunk_docling"
        assert output_payload["status"] == "completed"
        assert report["run_type"] == "chunk"
        assert report["status"] == "completed"
        assert report["artifact_dir"] == f"artifacts/runs/{run_id}"
        assert report["workers"][0]["worker_name"] == "chunk_docling"
        assert report["workers"][0]["exit_code"] == 0
        for path_value in (
            input_payload["normalized_markdown_path"],
            input_payload["normalized_json_path"],
            input_payload["source_hash_path"],
            input_payload["output_dir"],
            output_payload["chunks_jsonl_path"],
            output_payload["chunk_report_path"],
            report["artifact_dir"],
        ):
            assert "\\" not in path_value
            assert not Path(path_value).is_absolute()
        assert not Path(report["artifact_dir"]).is_absolute()


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


def _connect(workspace: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(workspace / "workspace.sqlite")
    connection.row_factory = sqlite3.Row
    return connection
