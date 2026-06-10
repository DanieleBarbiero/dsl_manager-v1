from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from dsl_mngr.cli.app import main
from dsl_mngr.core.candidate_validation import validate_candidate_payload


TIMESTAMP = "2026-06-10T10:00:00+00:00"
MANUAL_TEXT = (
    "Gestione Clienti consente la gestione dell'anagrafica clienti.\n"
    "La cancellazione di un cliente richiede controlli sugli ordini aperti.\n"
)
DDL_TEXT = "CREATE TABLE ANCLI (CODCLI CHAR(10) NOT NULL, PRIMARY KEY (CODCLI));\n"


@dataclass(frozen=True)
class EvidenceIds:
    manual_revision_id: str
    ddl_revision_id: str
    chunk_id: str
    fragment_id: str


def test_build_ai_package(tmp_path, capsys):
    workspace, evidence = _workspace_with_active_evidence(tmp_path / "build", capsys)
    assert (workspace / "configs" / "workers" / "ai_package.default.yaml").is_file()

    assert main(["ai", "package", str(workspace)]) == 0
    output = capsys.readouterr().out
    assert "Run: RUN_000001" in output
    assert "Package: AIPKG_000001" in output
    assert "Status: waiting_for_ai_candidates" in output
    assert "Sources: 2" in output
    assert "Chunks: 1" in output
    assert "Fragments: 1" in output
    assert "Outbox: ai/outbox/AIPKG_000001" in output
    assert "Manifest: ai/outbox/AIPKG_000001/package_manifest.json" in output

    package_dir = workspace / "ai" / "outbox" / "AIPKG_000001"
    expected_files = {
        "candidate_schema.json",
        "content.md",
        "instructions.md",
        "output_template.jsonl",
        "package_manifest.json",
        "source_manifest.json",
    }
    assert {path.name for path in package_dir.iterdir()} == expected_files

    package_manifest = _read_json(package_dir / "package_manifest.json")
    source_manifest = _read_json(package_dir / "source_manifest.json")
    candidate_schema = _read_json(package_dir / "candidate_schema.json")
    template_records = _read_jsonl(package_dir / "output_template.jsonl")
    content = (package_dir / "content.md").read_text(encoding="utf-8")
    instructions = (package_dir / "instructions.md").read_text(encoding="utf-8")

    assert "Do not update databases" in instructions
    assert f"ai/inbox/AIPKG_000001_candidates.jsonl" in instructions
    assert f"## Evidence {evidence.chunk_id}" in content
    assert f"## Evidence {evidence.fragment_id}" in content
    assert "- evidence_kind: chunk" in content
    assert "- evidence_kind: fragment" in content

    assert package_manifest["package_id"] == "AIPKG_000001"
    assert package_manifest["status"] == "waiting_for_ai_candidates"
    assert package_manifest["stale_check"]["is_stale"] is False
    assert package_manifest["source_revision_count"] == 2
    assert package_manifest["chunk_count"] == 1
    assert package_manifest["fragment_count"] == 1
    _assert_relative_manifest_paths(package_manifest)
    _assert_relative_manifest_paths(source_manifest)
    assert source_manifest["counts"] == {
        "chunks": 1,
        "fragments": 1,
        "source_revisions": 2,
    }
    assert source_manifest["chunks"][0]["chunk_id"] == evidence.chunk_id
    assert source_manifest["fragments"][0]["fragment_id"] == evidence.fragment_id
    assert candidate_schema["allowed_record_types"] == [
        "candidate_conflict",
        "candidate_fact",
        "candidate_mapping",
        "candidate_question",
        "candidate_relation",
    ]
    assert "chunk_id" in candidate_schema["anyOf"][0]["required"]
    assert "fragment_id" in candidate_schema["anyOf"][1]["required"]
    assert [record["record_type"] for record in template_records] == [
        "candidate_fact",
        "candidate_relation",
        "candidate_question",
    ]

    with _connect(workspace) as connection:
        for record in template_records:
            assert validate_candidate_payload(connection, record) is None
        package_row = connection.execute("SELECT * FROM ai_packages").fetchone()
        run = connection.execute("SELECT run_type, status FROM runs").fetchone()
        worker = connection.execute(
            "SELECT worker_name, status, exit_code FROM worker_runs"
        ).fetchone()

    assert package_row["package_id"] == "AIPKG_000001"
    assert package_row["status"] == "waiting_for_ai_candidates"
    assert package_row["package_path"] == "ai/outbox/AIPKG_000001"
    assert package_row["manifest_path"] == "ai/outbox/AIPKG_000001/package_manifest.json"
    assert "\\" not in package_row["manifest_path"]
    assert (run["run_type"], run["status"]) == ("ai_package", "completed")
    assert (worker["worker_name"], worker["status"], worker["exit_code"]) == (
        "build_ai_package",
        "completed",
        0,
    )
    _assert_ai_package_artifacts(workspace, "RUN_000001", "AIPKG_000001")

    completed = subprocess.run(
        [sys.executable, "-m", "dsl_mngr", "ai", "package", str(workspace)],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert completed.returncode == 0
    assert "Run: RUN_000002" in completed.stdout
    assert "Package: AIPKG_000002" in completed.stdout
    assert (workspace / "ai" / "outbox" / "AIPKG_000001").is_dir()
    assert (workspace / "ai" / "outbox" / "AIPKG_000002").is_dir()

    bad_workspace, _bad_evidence = _workspace_with_active_evidence(tmp_path / "bad", capsys)
    bad_profile = bad_workspace / "configs" / "workers" / "ai_package.bad.yaml"
    bad_profile.write_text(
        (bad_workspace / "configs" / "workers" / "ai_package.default.yaml").read_text(
            encoding="utf-8"
        )
        + "  unsupported_slice15_option: true\n",
        encoding="utf-8",
        newline="\n",
    )
    assert (
        main(
            [
                "ai",
                "package",
                str(bad_workspace),
                "--profile",
                "ai_package.bad",
            ]
        )
        == 2
    )
    captured = capsys.readouterr()
    assert "exit_code=4" in captured.err
    with _connect(bad_workspace) as connection:
        package_count = connection.execute("SELECT COUNT(*) FROM ai_packages").fetchone()[0]
        run = connection.execute("SELECT run_type, status FROM runs").fetchone()
        worker = connection.execute(
            "SELECT worker_name, status, exit_code FROM worker_runs"
        ).fetchone()
    assert package_count == 0
    assert (run["run_type"], run["status"]) == ("ai_package", "failed")
    assert (worker["worker_name"], worker["status"], worker["exit_code"]) == (
        "build_ai_package",
        "failed",
        4,
    )
    failed_report = _read_json(
        bad_workspace / "artifacts" / "runs" / "RUN_000001" / "process_report.json"
    )
    assert "unsupported_ai_package_option" in failed_report["workers"][0]["stderr"]
    assert "unsupported_slice15_option" in failed_report["workers"][0]["stderr"]


def test_ai_package_stale(tmp_path, capsys):
    workspace, evidence = _workspace_with_active_evidence(tmp_path / "stale", capsys)
    assert main(["ai", "package", str(workspace)]) == 0
    capsys.readouterr()
    _write_candidates(workspace, "AIPKG_000001", _valid_candidates(evidence)[:1])

    manual_path = workspace / "corpus" / "active" / "manuale_clienti.md"
    manual_path.write_text(MANUAL_TEXT + "Nuova evidenza dopo handoff.\n", encoding="utf-8")
    assert main(["corpus", "scan", str(workspace)]) == 0
    capsys.readouterr()

    assert main(["ai", "inbox", "scan", str(workspace)]) == 0
    scan_output = capsys.readouterr().out
    assert "AIPKG_000001" in scan_output
    assert "ai/inbox/AIPKG_000001_candidates.jsonl" in scan_output
    assert "exists" in scan_output
    assert "stale" in scan_output
    assert "source_revision_not_current" in scan_output

    assert main(["ai", "import", str(workspace), "--package", "AIPKG_000001"]) == 2
    captured = capsys.readouterr()
    assert "stale" in captured.err
    assert "source_revision_not_current" in captured.err
    with _connect(workspace) as connection:
        batch_count = connection.execute("SELECT COUNT(*) FROM candidate_batches").fetchone()[0]
        package = connection.execute("SELECT status, stale_reason FROM ai_packages").fetchone()
    assert batch_count == 0
    assert (package["status"], package["stale_reason"]) == (
        "stale",
        "source_revision_not_current",
    )

    assert (
        main(
            [
                "ai",
                "import",
                str(workspace),
                "--package",
                "AIPKG_000001",
                "--allow-stale",
            ]
        )
        == 0
    )
    captured = capsys.readouterr()
    assert "Warning:" in captured.err
    assert "Stale allowed: true" in captured.out
    with _connect(workspace) as connection:
        batch = connection.execute("SELECT * FROM candidate_batches").fetchone()
        package = connection.execute("SELECT status, stale_reason FROM ai_packages").fetchone()
        fact_count = connection.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
    assert batch["total_records"] == 1
    assert batch["accepted_count"] == 1
    assert package["status"] == "imported"
    assert package["stale_reason"] == "source_revision_not_current"
    assert fact_count == 0


def test_import_batch(tmp_path, capsys):
    workspace, evidence = _workspace_with_active_evidence(tmp_path / "import", capsys)
    assert main(["ai", "package", str(workspace)]) == 0
    capsys.readouterr()
    _write_candidates(workspace, "AIPKG_000001", _valid_candidates(evidence))

    assert main(["ai", "inbox", "scan", str(workspace)]) == 0
    scan_output = capsys.readouterr().out
    assert "AIPKG_000001" in scan_output
    assert "not stale" in scan_output

    assert main(["ai", "import", str(workspace), "--package", "AIPKG_000001"]) == 0
    output = capsys.readouterr().out
    assert "Run: RUN_000002" in output
    assert "Package: AIPKG_000001" in output
    assert "Batch: CBATCH_000001" in output
    assert "Total: 3" in output
    assert "Accepted: 3" in output
    assert "Rejected: 0" in output
    assert "Stale allowed: false" in output

    with _connect(workspace) as connection:
        package = connection.execute("SELECT * FROM ai_packages").fetchone()
        batch = connection.execute("SELECT * FROM candidate_batches").fetchone()
        accepted = connection.execute(
            "SELECT record_type, chunk_id, fragment_id FROM candidate_records ORDER BY line_number"
        ).fetchall()
        rejected_count = connection.execute("SELECT COUNT(*) FROM rejected_candidates").fetchone()[0]
        facts_count = connection.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
        relations_count = connection.execute("SELECT COUNT(*) FROM relations").fetchone()[0]
        run = connection.execute(
            "SELECT run_type, status FROM runs WHERE run_id = 'RUN_000002'"
        ).fetchone()

    assert package["status"] == "imported"
    assert batch["run_id"] == "RUN_000002"
    assert batch["input_path"] == "ai/inbox/AIPKG_000001_candidates.jsonl"
    assert batch["total_records"] == 3
    assert batch["accepted_count"] == 3
    assert batch["rejected_count"] == 0
    assert [(row["record_type"], row["chunk_id"], row["fragment_id"]) for row in accepted] == [
        ("candidate_fact", evidence.chunk_id, None),
        ("candidate_relation", None, evidence.fragment_id),
        ("candidate_question", evidence.chunk_id, None),
    ]
    assert rejected_count == 0
    assert facts_count == 0
    assert relations_count == 0
    assert (run["run_type"], run["status"]) == ("candidate_import", "completed")
    import_report = _read_json(workspace / "artifacts" / "runs" / "RUN_000002" / "process_report.json")
    assert import_report["package_id"] == "AIPKG_000001"
    assert import_report["input_path"] == "ai/inbox/AIPKG_000001_candidates.jsonl"
    assert import_report["batch_id"] == "CBATCH_000001"
    assert import_report["total_records"] == 3
    assert import_report["accepted_count"] == 3
    assert import_report["rejected_count"] == 0
    assert import_report["stale_allowed"] is False


def _workspace_with_active_evidence(base_path: Path, capsys) -> tuple[Path, EvidenceIds]:
    workspace = base_path / "workspace"
    assert main(["init", str(workspace)]) == 0
    assert main(["db", "init", str(workspace)]) == 0
    capsys.readouterr()

    active_dir = workspace / "corpus" / "active"
    (active_dir / "manuale_clienti.md").write_text(MANUAL_TEXT, encoding="utf-8", newline="\n")
    (active_dir / "schema_clienti.sql").write_text(DDL_TEXT, encoding="utf-8", newline="\n")
    assert main(["corpus", "scan", str(workspace)]) == 0
    capsys.readouterr()

    with _connect(workspace) as connection:
        manual_revision = connection.execute(
            "SELECT * FROM source_revisions WHERE file_path = ?",
            ("corpus/active/manuale_clienti.md",),
        ).fetchone()
        ddl_revision = connection.execute(
            "SELECT * FROM source_revisions WHERE file_path = ?",
            ("corpus/active/schema_clienti.sql",),
        ).fetchone()
        connection.execute(
            """
            UPDATE sources
            SET source_type = ?,
                source_subtype = ?,
                authority_level = ?,
                updated_at = ?
            WHERE source_id = ?
            """,
            (
                "legacy_document",
                "functional_manual",
                "functional_documentation",
                TIMESTAMP,
                manual_revision["source_id"],
            ),
        )
        connection.execute(
            """
            UPDATE sources
            SET source_type = ?,
                source_subtype = ?,
                authority_level = ?,
                updated_at = ?
            WHERE source_id = ?
            """,
            (
                "ddl",
                "table",
                "technical_structure",
                TIMESTAMP,
                ddl_revision["source_id"],
            ),
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
                manual_revision["source_revision_id"],
                1,
                MANUAL_TEXT,
                _sha256_text(MANUAL_TEXT),
                "{}",
                "active",
                TIMESTAMP,
            ),
        )
        connection.execute(
            """
            INSERT INTO source_fragments (
                fragment_id,
                source_revision_id,
                fragment_type,
                sequence,
                path_or_selector,
                line_start,
                line_end,
                char_start,
                char_end,
                text,
                text_hash,
                metadata_json,
                status,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "FRAG_000001",
                ddl_revision["source_revision_id"],
                "ddl_table",
                1,
                "table/ANCLI",
                1,
                1,
                0,
                len(DDL_TEXT),
                DDL_TEXT,
                _sha256_text(DDL_TEXT),
                "{}",
                "active",
                TIMESTAMP,
            ),
        )
        connection.commit()

    return workspace, EvidenceIds(
        manual_revision_id=manual_revision["source_revision_id"],
        ddl_revision_id=ddl_revision["source_revision_id"],
        chunk_id="CHK_000001",
        fragment_id="FRAG_000001",
    )


def _valid_candidates(evidence: EvidenceIds) -> list[dict[str, object]]:
    return [
        {
            "assertion_type": "explicit",
            "candidate_id": "CAND_AI_FACT_001",
            "chunk_id": evidence.chunk_id,
            "confidence": "high",
            "entity_name": "Cliente",
            "evidence_text": "Gestione Clienti consente la gestione dell'anagrafica clienti.",
            "fact_type": "business_entity",
            "property_name": "description",
            "property_value": "Anagrafica clienti",
            "record_type": "candidate_fact",
            "source_revision_id": evidence.manual_revision_id,
        },
        {
            "assertion_type": "explicit",
            "candidate_id": "CAND_AI_REL_001",
            "confidence": "medium",
            "evidence_text": "CREATE TABLE ANCLI",
            "fragment_id": evidence.fragment_id,
            "record_type": "candidate_relation",
            "relation_type": "stored_in",
            "source_entity": "Cliente",
            "source_revision_id": evidence.ddl_revision_id,
            "target_entity": "ANCLI",
        },
        {
            "assertion_type": "ambiguous",
            "candidate_id": "CAND_AI_QUESTION_001",
            "chunk_id": evidence.chunk_id,
            "confidence": "low",
            "evidence_text": "La cancellazione di un cliente richiede controlli sugli ordini aperti.",
            "question_text": "Quali ordini aperti bloccano la cancellazione del cliente?",
            "question_type": "clarification",
            "record_type": "candidate_question",
            "source_revision_id": evidence.manual_revision_id,
            "subject": "Cliente.delete_rule",
        },
    ]


def _write_candidates(
    workspace: Path,
    package_id: str,
    candidates: list[dict[str, object]],
) -> Path:
    path = workspace / "ai" / "inbox" / f"{package_id}_candidates.jsonl"
    path.write_text(
        "".join(
            json.dumps(candidate, ensure_ascii=False, sort_keys=True) + "\n"
            for candidate in candidates
        ),
        encoding="utf-8",
        newline="\n",
    )
    return path


def _assert_ai_package_artifacts(workspace: Path, run_id: str, package_id: str) -> None:
    artifact_dir = workspace / "artifacts" / "runs" / run_id
    input_payload = _read_json(artifact_dir / "input.json")
    output_payload = _read_json(artifact_dir / "output.json")
    report = _read_json(artifact_dir / "process_report.json")

    assert input_payload["package_id"] == package_id
    assert input_payload["output_dir"] == f"ai/outbox/{package_id}"
    assert input_payload["profile"] == "ai_package.default"
    assert input_payload["ai_package_options"]["package_format"] == "markdown_plus_json"
    assert len(input_payload["source_revisions"]) == 2
    assert len(input_payload["chunks"]) == 1
    assert len(input_payload["fragments"]) == 1
    assert output_payload["package_id"] == package_id
    assert output_payload["worker_name"] == "build_ai_package"
    assert output_payload["status"] == "completed"
    assert report["run_type"] == "ai_package"
    assert report["status"] == "completed"
    assert report["package_id"] == package_id
    assert report["workers"][0]["worker_name"] == "build_ai_package"
    assert report["workers"][0]["exit_code"] == 0
    for path_value in (
        input_payload["output_dir"],
        output_payload["package_path"],
        output_payload["manifest_path"],
        output_payload["content_path"],
        report["artifact_dir"],
    ):
        assert "\\" not in path_value
        assert not Path(path_value).is_absolute()


def _assert_relative_manifest_paths(payload: object) -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key.endswith("_path") or key in {"path", "package_path", "file_path"}:
                assert isinstance(value, str)
                assert "\\" not in value
                assert not Path(value).is_absolute()
            _assert_relative_manifest_paths(value)
    elif isinstance(payload, list):
        for item in payload:
            _assert_relative_manifest_paths(item)


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
