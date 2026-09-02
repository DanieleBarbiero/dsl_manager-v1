from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

from dsl_mngr.cli.app import main
from dsl_mngr.core.migrations import migrate_workspace_database
from dsl_mngr.core.workspace import initialize_workspace


FIXTURES_DIR = Path(__file__).parent / "fixtures" / "candidates"
CHUNK_TEXT = (
    "Manuale clienti. Gestione Clienti consente la gestione anagrafica clienti. "
    "La cancellazione richiede controlli sugli ordini aperti."
)
TIMESTAMP = "2026-05-29T12:00:00+00:00"


def test_import_candidate_fixture(tmp_path):
    workspace = _ready_workspace_with_chunk(tmp_path)
    input_file = _copy_fixture_to_inbox(workspace, "valid_fact.jsonl")

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "dsl_mngr",
            "candidates",
            "validate",
            str(workspace),
            "--input",
            str(input_file),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert "Run: RUN_000001" in completed.stdout
    assert "Batch: CBATCH_000001" in completed.stdout
    assert "Total: 1" in completed.stdout
    assert "Accepted: 1" in completed.stdout
    assert "Rejected: 0" in completed.stdout

    with _connect(workspace) as connection:
        batch = connection.execute("SELECT * FROM candidate_batches").fetchone()
        accepted = connection.execute("SELECT * FROM candidate_records").fetchall()
        rejected_count = connection.execute("SELECT COUNT(*) FROM rejected_candidates").fetchone()[0]
        run = connection.execute("SELECT * FROM runs WHERE run_id = 'RUN_000001'").fetchone()

    assert batch["batch_id"] == "CBATCH_000001"
    assert batch["run_id"] == "RUN_000001"
    assert batch["input_path"] == "ai/inbox/valid_fact.jsonl"
    assert batch["total_records"] == 1
    assert batch["accepted_count"] == 1
    assert batch["rejected_count"] == 0
    assert batch["status"] == "completed"
    assert len(accepted) == 1
    assert accepted[0]["candidate_id"] == "CAND_001"
    assert accepted[0]["record_type"] == "candidate_fact"
    assert accepted[0]["source_revision_id"] == "REV_000001"
    assert accepted[0]["chunk_id"] == "CHK_000001"
    assert rejected_count == 0
    assert run["run_type"] == "candidate_validation"
    assert run["status"] == "completed"

    _assert_artifacts(
        workspace,
        batch_id="CBATCH_000001",
        total=1,
        accepted=1,
        rejected=0,
    )


def test_reject_invalid_json(tmp_path, capsys):
    workspace = _ready_workspace_with_chunk(tmp_path)
    input_file = _copy_fixture_to_inbox(workspace, "invalid_json.jsonl")

    assert main(["candidates", "validate", str(workspace), "--input", str(input_file)]) == 0

    output = capsys.readouterr().out
    assert "Run: RUN_000001" in output
    assert "Accepted: 0" in output
    assert "Rejected: 1" in output

    _assert_rejection(
        workspace,
        reason="invalid_json",
        total=1,
        accepted=0,
        rejected=1,
    )


def test_reject_unknown_chunk(tmp_path, capsys):
    workspace = _ready_workspace_with_chunk(tmp_path)
    input_file = _copy_fixture_to_inbox(workspace, "unknown_chunk.jsonl")

    assert main(["candidates", "validate", str(workspace), "--input", str(input_file)]) == 0

    output = capsys.readouterr().out
    assert "Batch: CBATCH_000001" in output
    assert "Rejected: 1" in output

    _assert_rejection(
        workspace,
        reason="unknown_chunk",
        total=1,
        accepted=0,
        rejected=1,
    )


def test_reject_candidate_missing_evidence(tmp_path, capsys):
    workspace = _ready_workspace_with_chunk(tmp_path)
    input_file = _copy_fixture_to_inbox(workspace, "missing_evidence.jsonl")

    assert main(["candidates", "validate", str(workspace), "--input", str(input_file)]) == 0

    output = capsys.readouterr().out
    assert "Run: RUN_000001" in output
    assert "Rejected: 1" in output

    _assert_rejection(
        workspace,
        reason="evidence_text_not_found",
        total=1,
        accepted=0,
        rejected=1,
    )


def _ready_workspace_with_chunk(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    initialize_workspace(workspace)
    migrate_workspace_database(workspace)
    _insert_source_revision_and_chunk(workspace)
    return workspace


def _insert_source_revision_and_chunk(workspace: Path) -> None:
    with _connect(workspace) as connection:
        connection.execute(
            """
            INSERT INTO sources (
                source_id,
                logical_name,
                source_type,
                source_subtype,
                authority_level,
                first_seen_at,
                last_seen_at,
                current_revision_id,
                status,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, NULL, ?, ?, ?, NULL, ?, ?, ?)
            """,
            (
                "SRC_000001",
                "corpus/active/manuale_clienti.txt",
                "legacy_document",
                "functional_documentation",
                TIMESTAMP,
                TIMESTAMP,
                "active",
                TIMESTAMP,
                TIMESTAMP,
            ),
        )
        connection.execute(
            """
            INSERT INTO source_revisions (
                source_revision_id,
                source_id,
                revision_number,
                content_hash,
                normalized_hash,
                file_path,
                file_size,
                detected_at,
                status,
                created_at
            )
            VALUES (?, ?, ?, ?, NULL, ?, ?, ?, ?, ?)
            """,
            (
                "REV_000001",
                "SRC_000001",
                1,
                hashlib.sha256(CHUNK_TEXT.encode("utf-8")).hexdigest(),
                "corpus/active/manuale_clienti.txt",
                len(CHUNK_TEXT.encode("utf-8")),
                TIMESTAMP,
                "active",
                TIMESTAMP,
            ),
        )
        connection.execute(
            "UPDATE sources SET current_revision_id = ? WHERE source_id = ?",
            ("REV_000001", "SRC_000001"),
        )
        connection.execute(
            """
            INSERT INTO chunks (
                chunk_id,
                source_revision_id,
                sequence,
                text,
                text_hash,
                metadata_json,
                status,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "CHK_000001",
                "REV_000001",
                1,
                CHUNK_TEXT,
                hashlib.sha256(CHUNK_TEXT.encode("utf-8")).hexdigest(),
                "{}",
                "active",
                TIMESTAMP,
            ),
        )
        connection.commit()


def _copy_fixture_to_inbox(workspace: Path, name: str) -> Path:
    destination = workspace / "ai" / "inbox" / name
    shutil.copyfile(FIXTURES_DIR / name, destination)
    return destination


def _assert_rejection(
    workspace: Path,
    *,
    reason: str,
    total: int,
    accepted: int,
    rejected: int,
) -> None:
    with _connect(workspace) as connection:
        batch = connection.execute("SELECT * FROM candidate_batches").fetchone()
        accepted_count = connection.execute("SELECT COUNT(*) FROM candidate_records").fetchone()[0]
        rejected_rows = connection.execute("SELECT * FROM rejected_candidates").fetchall()
        run = connection.execute("SELECT * FROM runs WHERE run_id = 'RUN_000001'").fetchone()

    assert batch["total_records"] == total
    assert batch["accepted_count"] == accepted
    assert batch["rejected_count"] == rejected
    assert accepted_count == accepted
    assert [row["reason"] for row in rejected_rows] == [reason]
    assert run["run_type"] == "candidate_validation"
    assert run["status"] == "completed"
    _assert_artifacts(
        workspace,
        batch_id=batch["batch_id"],
        total=total,
        accepted=accepted,
        rejected=rejected,
    )


def _assert_artifacts(
    workspace: Path,
    *,
    batch_id: str,
    total: int,
    accepted: int,
    rejected: int,
) -> None:
    output_path = workspace / "artifacts" / "runs" / "RUN_000001" / "output.json"
    report_path = workspace / "artifacts" / "runs" / "RUN_000001" / "process_report.json"

    output = json.loads(output_path.read_text(encoding="utf-8"))
    report = json.loads(report_path.read_text(encoding="utf-8"))

    for document in (output, report):
        assert document["batch_id"] == batch_id
        assert document["total_records"] == total
        assert document["accepted_count"] == accepted
        assert document["rejected_count"] == rejected
        assert document["total"] == total
        assert document["accepted"] == accepted
        assert document["rejected"] == rejected

    assert report["run_type"] == "candidate_validation"
    assert report["status"] == "completed"


def _connect(workspace: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(workspace / "workspace.sqlite")
    connection.row_factory = sqlite3.Row
    return connection
