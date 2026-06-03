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
SOURCE_FIXTURE = TESTS_DIR / "fixtures" / "corpus_initial" / "manuale_clienti.md"
IMAGE_SUFFIXES = {".bmp", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}


def test_docling_normalization_no_images(tmp_path, capsys):
    workspace = _ready_workspace(tmp_path, capsys)
    assert (workspace / "configs" / "workers" / "docling.no_images.yaml").is_file()

    source_path = workspace / "corpus" / "active" / SOURCE_FIXTURE.name
    shutil.copyfile(SOURCE_FIXTURE, source_path)

    assert main(["corpus", "scan", str(workspace)]) == 0
    scan_output = capsys.readouterr().out
    assert "Added: 1" in scan_output
    _assert_revision_registered(workspace)

    assert main(["corpus", "normalize", str(workspace), "--revision", "REV_000001"]) == 0
    normalize_output = capsys.readouterr().out
    assert "Run: RUN_000001" in normalize_output
    assert "Revision: REV_000001" in normalize_output
    assert "Source: SRC_000001" in normalize_output
    assert "Markdown: normalized/SRC_000001/REV_000001/normalized.md" in normalize_output
    assert "JSON: normalized/SRC_000001/REV_000001/normalized.json" in normalize_output
    assert "Report: normalized/SRC_000001/REV_000001/docling_report.json" in normalize_output

    first_hash = _assert_normalized_outputs(workspace)
    _assert_run_and_worker_completed(workspace, "RUN_000001")
    _assert_process_report(workspace, "RUN_000001", status="completed", exit_code=0)
    _assert_no_image_files(workspace / "normalized", workspace / "artifacts" / "runs")

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "dsl_mngr",
            "corpus",
            "normalize",
            str(workspace),
            "--revision",
            "REV_000001",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert completed.returncode == 0
    assert "Run: RUN_000002" in completed.stdout
    second_hash = _normalized_hash_from_db(workspace)
    assert second_hash == first_hash
    _assert_run_and_worker_completed(workspace, "RUN_000002")
    _assert_no_chunking_records(workspace)


def test_docling_unsupported_option(tmp_path, capsys):
    workspace = _ready_workspace(tmp_path, capsys)
    source_path = workspace / "corpus" / "active" / SOURCE_FIXTURE.name
    shutil.copyfile(SOURCE_FIXTURE, source_path)
    assert main(["corpus", "scan", str(workspace)]) == 0
    capsys.readouterr()

    bad_profile = workspace / "configs" / "workers" / "docling.unsupported.yaml"
    bad_profile.write_text(
        (workspace / "configs" / "workers" / "docling.no_images.yaml").read_text(
            encoding="utf-8"
        )
        + "  unsupported_slice10_option: true\n",
        encoding="utf-8",
        newline="\n",
    )

    assert (
        main(
            [
                "corpus",
                "normalize",
                str(workspace),
                "--revision",
                "REV_000001",
                "--profile",
                "docling.unsupported",
            ]
        )
        == 2
    )
    captured = capsys.readouterr()
    assert "exit_code=4" in captured.err

    with _connect(workspace) as connection:
        revision = connection.execute(
            "SELECT normalized_hash FROM source_revisions WHERE source_revision_id = 'REV_000001'"
        ).fetchone()
        run = connection.execute("SELECT run_type, status FROM runs").fetchone()
        worker = connection.execute(
            "SELECT worker_name, status, exit_code FROM worker_runs"
        ).fetchone()

    assert revision["normalized_hash"] is None
    assert (run["run_type"], run["status"]) == ("normalize", "failed")
    assert (worker["worker_name"], worker["status"], worker["exit_code"]) == (
        "normalize_docling",
        "failed",
        4,
    )

    output_dir = workspace / "normalized" / "SRC_000001" / "REV_000001"
    assert not (output_dir / "normalized.md").exists()
    assert not (output_dir / "normalized.json").exists()
    assert not (output_dir / "source_hash.txt").exists()
    assert not (output_dir / "docling_report.json").exists()

    report = _read_json(workspace / "artifacts" / "runs" / "RUN_000001" / "process_report.json")
    assert report["run_type"] == "normalize"
    assert report["status"] == "failed"
    assert report["workers"][0]["exit_code"] == 4
    assert "unsupported_docling_option" in report["workers"][0]["stderr"]
    assert "unsupported_slice10_option" in report["workers"][0]["stderr"]
    _assert_no_chunking_records(workspace)


def _ready_workspace(tmp_path: Path, capsys) -> Path:
    workspace = tmp_path / "workspace"
    assert main(["init", str(workspace)]) == 0
    assert main(["db", "init", str(workspace)]) == 0
    capsys.readouterr()
    return workspace


def _assert_revision_registered(workspace: Path) -> None:
    with _connect(workspace) as connection:
        source = connection.execute("SELECT * FROM sources").fetchone()
        revision = connection.execute("SELECT * FROM source_revisions").fetchone()

    assert source["source_id"] == "SRC_000001"
    assert source["current_revision_id"] == "REV_000001"
    assert revision["source_revision_id"] == "REV_000001"
    assert revision["file_path"] == "corpus/active/manuale_clienti.md"
    assert revision["content_hash"] == _sha256_file(workspace / revision["file_path"])


def _assert_normalized_outputs(workspace: Path) -> str:
    output_dir = workspace / "normalized" / "SRC_000001" / "REV_000001"
    markdown_path = output_dir / "normalized.md"
    json_path = output_dir / "normalized.json"
    source_hash_path = output_dir / "source_hash.txt"
    report_path = output_dir / "docling_report.json"

    assert markdown_path.is_file()
    assert json_path.is_file()
    assert source_hash_path.is_file()
    assert report_path.is_file()

    markdown = markdown_path.read_text(encoding="utf-8")
    assert "Manuale clienti" in markdown
    assert "business entity" in markdown
    assert "\r" not in markdown

    normalized_json = _read_json(json_path)
    assert normalized_json["schema_name"] == "DoclingDocument"
    assert "texts" in normalized_json

    with _connect(workspace) as connection:
        revision = connection.execute(
            "SELECT content_hash, normalized_hash FROM source_revisions"
        ).fetchone()
        runs = connection.execute(
            "SELECT run_id, run_type, status FROM runs ORDER BY run_id"
        ).fetchall()
        workers = connection.execute(
            "SELECT worker_name, status, exit_code FROM worker_runs ORDER BY worker_run_id"
        ).fetchall()

    expected_markdown_hash = hashlib.sha256(markdown.encode("utf-8")).hexdigest()
    assert revision["normalized_hash"] == expected_markdown_hash
    assert source_hash_path.read_text(encoding="utf-8").strip() == revision["content_hash"]
    assert [(row["run_id"], row["run_type"], row["status"]) for row in runs] == [
        ("RUN_000001", "normalize", "completed"),
    ]
    assert [(row["worker_name"], row["status"], row["exit_code"]) for row in workers] == [
        ("normalize_docling", "completed", 0),
    ]

    report = _read_json(report_path)
    assert report["docling_version"] == "2.97.0"
    assert report["profile"] == "docling.no_images"
    assert report["resolved_config"]["docling"]["images_enabled"] is False
    assert report["resolved_config"]["docling"]["generate_page_images"] is False
    assert report["resolved_config"]["docling"]["generate_picture_images"] is False
    assert report["resolved_config"]["docling"]["ocr_enabled"] is False
    assert report["outputs"]["normalized_hash"] == expected_markdown_hash
    for path in report["outputs"].values():
        if isinstance(path, str) and path.endswith((".md", ".json", ".txt")):
            _assert_workspace_relative(path)

    return expected_markdown_hash


def _assert_run_and_worker_completed(workspace: Path, run_id: str) -> None:
    with _connect(workspace) as connection:
        run = connection.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        worker = connection.execute(
            "SELECT * FROM worker_runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()

    assert run["run_type"] == "normalize"
    assert run["status"] == "completed"
    assert worker["worker_name"] == "normalize_docling"
    assert worker["status"] == "completed"
    assert worker["exit_code"] == 0
    assert worker["input_path"] == f"artifacts/runs/{run_id}/input.json"
    assert worker["output_path"] == f"artifacts/runs/{run_id}/output.json"


def _assert_process_report(workspace: Path, run_id: str, *, status: str, exit_code: int) -> None:
    artifact_dir = workspace / "artifacts" / "runs" / run_id
    input_payload = _read_json(artifact_dir / "input.json")
    output_payload = _read_json(artifact_dir / "output.json")
    report = _read_json(artifact_dir / "process_report.json")

    assert input_payload["source_id"] == "SRC_000001"
    assert input_payload["source_revision_id"] == "REV_000001"
    assert input_payload["input_path"] == "corpus/active/manuale_clienti.md"
    assert input_payload["output_dir"] == "normalized/SRC_000001/REV_000001"
    assert input_payload["profile"] == "docling.no_images"
    assert input_payload["docling_options"]["generate_page_images"] is False
    assert output_payload["worker_name"] == "normalize_docling"
    assert output_payload["status"] == "completed"

    assert report["run_type"] == "normalize"
    assert report["status"] == status
    assert report["artifact_dir"] == f"artifacts/runs/{run_id}"
    assert report["workers"][0]["worker_name"] == "normalize_docling"
    assert report["workers"][0]["exit_code"] == exit_code
    _assert_workspace_relative(report["artifact_dir"])


def _assert_no_image_files(*roots: Path) -> None:
    generated = [
        path.relative_to(root).as_posix()
        for root in roots
        if root.exists()
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    ]
    assert generated == []


def _assert_no_chunking_records(workspace: Path) -> None:
    with _connect(workspace) as connection:
        chunk_count = connection.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        fragment_count = connection.execute("SELECT COUNT(*) FROM source_fragments").fetchone()[0]

    assert chunk_count == 0
    assert fragment_count == 0


def _normalized_hash_from_db(workspace: Path) -> str:
    with _connect(workspace) as connection:
        row = connection.execute("SELECT normalized_hash FROM source_revisions").fetchone()
    return row["normalized_hash"]


def _assert_workspace_relative(value: str) -> None:
    assert "\\" not in value
    assert not Path(value).is_absolute()
    assert ".." not in Path(value).parts


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _connect(workspace: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(workspace / "workspace.sqlite")
    connection.row_factory = sqlite3.Row
    return connection
