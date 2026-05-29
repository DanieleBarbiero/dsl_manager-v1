from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

from dsl_mngr.cli.app import main
from dsl_mngr.core.migrations import migrate_workspace_database
from dsl_mngr.core.workspace import initialize_workspace


TIMESTAMP = "2026-05-29T12:00:00+00:00"
EVIDENCE_FACT = "Cliente description source."
EVIDENCE_STATUS_ACTIVE = "Cliente stato e attivo."
EVIDENCE_STATUS_BLOCKED = "Cliente stato e bloccato."
EVIDENCE_RELATION = "Il cliente puo inserire uno o piu ordini."
CHUNK_TEXT = " ".join(
    (
        EVIDENCE_FACT,
        EVIDENCE_STATUS_ACTIVE,
        EVIDENCE_STATUS_BLOCKED,
        EVIDENCE_RELATION,
    )
)


def test_merge_facts_idempotent(tmp_path):
    workspace = _ready_workspace_with_chunk(tmp_path)
    batch_id = _validate_candidates(
        workspace,
        "fact.jsonl",
        [
            _candidate_fact(
                candidate_id="CAND_FACT_001",
                entity_name=" Cliente ",
                property_name=" description ",
                property_value="Anagrafica   clienti gestita dal sistema",
                evidence_text=EVIDENCE_FACT,
            )
        ],
    )

    first = subprocess.run(
        [
            sys.executable,
            "-m",
            "dsl_mngr",
            "facts",
            "merge",
            str(workspace),
            "--batch",
            batch_id,
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert first.returncode == 0
    assert "Run: RUN_000002" in first.stdout
    assert "Batch: CBATCH_000001" in first.stdout
    assert "Candidate records: 1" in first.stdout
    assert "Facts created: 1" in first.stdout
    assert "Facts existing: 0" in first.stdout

    assert main(["facts", "merge", str(workspace), "--batch", batch_id]) == 0

    with _connect(workspace) as connection:
        facts = connection.execute("SELECT * FROM facts").fetchall()
        evidence = connection.execute("SELECT * FROM fact_evidence").fetchall()
        runs = connection.execute(
            "SELECT run_id, run_type, status FROM runs ORDER BY run_id"
        ).fetchall()

    assert len(facts) == 1
    assert facts[0]["fact_id"] == "FACT_000001"
    assert facts[0]["canonical_entity_name"] == "cliente"
    assert facts[0]["normalized_property_value"] == "Anagrafica clienti gestita dal sistema"
    assert facts[0]["status"] == "active"
    assert len(evidence) == 1
    assert evidence[0]["candidate_record_id"] == "CREC_000001"
    assert evidence[0]["source_revision_id"] == "REV_000001"
    assert evidence[0]["chunk_id"] == "CHK_000001"
    assert evidence[0]["evidence_text"] == EVIDENCE_FACT
    assert [(row["run_type"], row["status"]) for row in runs] == [
        ("candidate_validation", "completed"),
        ("merge", "completed"),
        ("merge", "completed"),
    ]

    _assert_merge_artifacts(
        workspace,
        "RUN_000002",
        {
            "batch_id": "CBATCH_000001",
            "candidate_record_count": 1,
            "facts_created": 1,
            "facts_existing": 0,
            "relations_created": 0,
            "relations_existing": 0,
            "conflicts_created": 0,
            "conflicts_existing": 0,
            "skipped_records": 0,
        },
    )
    _assert_merge_artifacts(
        workspace,
        "RUN_000003",
        {
            "batch_id": "CBATCH_000001",
            "candidate_record_count": 1,
            "facts_created": 0,
            "facts_existing": 1,
            "relations_created": 0,
            "relations_existing": 0,
            "conflicts_created": 0,
            "conflicts_existing": 0,
            "skipped_records": 0,
        },
    )


def test_merge_relation(tmp_path):
    workspace = _ready_workspace_with_chunk(tmp_path)
    batch_id = _validate_candidates(
        workspace,
        "relation.jsonl",
        [
            _candidate_relation(
                candidate_id="CAND_REL_001",
                source_entity="Cliente",
                relation_type="places",
                target_entity="Ordine",
                evidence_text=EVIDENCE_RELATION,
            ),
            _candidate_question(
                candidate_id="CAND_SKIP_001",
                evidence_text=EVIDENCE_RELATION,
            ),
        ],
        raw_lines=("{invalid json",),
    )

    assert main(["facts", "merge", str(workspace), "--batch", batch_id]) == 0
    assert main(["facts", "merge", str(workspace), "--batch", batch_id]) == 0

    with _connect(workspace) as connection:
        batch = connection.execute("SELECT * FROM candidate_batches").fetchone()
        relations = connection.execute("SELECT * FROM relations").fetchall()
        evidence = connection.execute("SELECT * FROM relation_evidence").fetchall()
        rejected_count = connection.execute("SELECT COUNT(*) FROM rejected_candidates").fetchone()[0]

    assert batch["accepted_count"] == 2
    assert batch["rejected_count"] == 1
    assert rejected_count == 1
    assert len(relations) == 1
    assert relations[0]["relation_id"] == "REL_000001"
    assert relations[0]["canonical_source_entity"] == "cliente"
    assert relations[0]["relation_type"] == "places"
    assert relations[0]["canonical_target_entity"] == "ordine"
    assert relations[0]["status"] == "active"
    assert len(evidence) == 1
    assert evidence[0]["candidate_record_id"] == "CREC_000001"
    assert evidence[0]["evidence_text"] == EVIDENCE_RELATION

    _assert_merge_artifacts(
        workspace,
        "RUN_000002",
        {
            "batch_id": "CBATCH_000001",
            "candidate_record_count": 2,
            "facts_created": 0,
            "facts_existing": 0,
            "relations_created": 1,
            "relations_existing": 0,
            "conflicts_created": 0,
            "conflicts_existing": 0,
            "skipped_records": 1,
        },
    )
    _assert_merge_artifacts(
        workspace,
        "RUN_000003",
        {
            "batch_id": "CBATCH_000001",
            "candidate_record_count": 2,
            "facts_created": 0,
            "facts_existing": 0,
            "relations_created": 0,
            "relations_existing": 1,
            "conflicts_created": 0,
            "conflicts_existing": 0,
            "skipped_records": 1,
        },
    )


def test_merge_conflict(tmp_path):
    workspace = _ready_workspace_with_chunk(tmp_path)
    batch_id = _validate_candidates(
        workspace,
        "conflict.jsonl",
        [
            _candidate_fact(
                candidate_id="CAND_STATUS_001",
                fact_type="business_rule",
                entity_name="Cliente",
                property_name="status",
                property_value="ATTIVO",
                evidence_text=EVIDENCE_STATUS_ACTIVE,
            ),
            _candidate_fact(
                candidate_id="CAND_STATUS_002",
                fact_type="business_rule",
                entity_name="Cliente",
                property_name="status",
                property_value="BLOCCATO",
                evidence_text=EVIDENCE_STATUS_BLOCKED,
            ),
        ],
    )

    assert main(["facts", "merge", str(workspace), "--batch", batch_id]) == 0
    assert main(["facts", "merge", str(workspace), "--batch", batch_id]) == 0

    with _connect(workspace) as connection:
        facts = connection.execute("SELECT * FROM facts ORDER BY fact_id").fetchall()
        evidence_count = connection.execute("SELECT COUNT(*) FROM fact_evidence").fetchone()[0]
        conflicts = connection.execute("SELECT * FROM conflicts").fetchall()

    assert len(facts) == 2
    assert {row["status"] for row in facts} == {"conflicted"}
    assert evidence_count == 2
    assert len(conflicts) == 1
    assert conflicts[0]["conflict_type"] == "different_values_same_property"
    assert conflicts[0]["canonical_entity_name"] == "cliente"
    assert conflicts[0]["property_name"] == "status"
    assert conflicts[0]["status"] == "open"

    _assert_merge_artifacts(
        workspace,
        "RUN_000002",
        {
            "batch_id": "CBATCH_000001",
            "candidate_record_count": 2,
            "facts_created": 2,
            "facts_existing": 0,
            "relations_created": 0,
            "relations_existing": 0,
            "conflicts_created": 1,
            "conflicts_existing": 0,
            "skipped_records": 0,
        },
    )
    _assert_merge_artifacts(
        workspace,
        "RUN_000003",
        {
            "batch_id": "CBATCH_000001",
            "candidate_record_count": 2,
            "facts_created": 0,
            "facts_existing": 2,
            "relations_created": 0,
            "relations_existing": 0,
            "conflicts_created": 0,
            "conflicts_existing": 1,
            "skipped_records": 0,
        },
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


def _validate_candidates(
    workspace: Path,
    filename: str,
    records: list[dict[str, object]],
    *,
    raw_lines: tuple[str, ...] = (),
) -> str:
    input_file = workspace / "ai" / "inbox" / filename
    lines = [json.dumps(record, sort_keys=True) for record in records]
    lines.extend(raw_lines)
    input_file.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    assert main(["candidates", "validate", str(workspace), "--input", str(input_file)]) == 0
    with _connect(workspace) as connection:
        row = connection.execute(
            "SELECT batch_id FROM candidate_batches ORDER BY batch_id DESC LIMIT 1"
        ).fetchone()
    return row["batch_id"]


def _candidate_fact(
    *,
    candidate_id: str,
    entity_name: str,
    property_name: str,
    property_value: str,
    evidence_text: str,
    fact_type: str = "business_entity",
) -> dict[str, object]:
    return {
        "assertion_type": "explicit",
        "candidate_id": candidate_id,
        "chunk_id": "CHK_000001",
        "confidence": "high",
        "entity_name": entity_name,
        "evidence_text": evidence_text,
        "fact_type": fact_type,
        "property_name": property_name,
        "property_value": property_value,
        "record_type": "candidate_fact",
        "source_revision_id": "REV_000001",
    }


def _candidate_relation(
    *,
    candidate_id: str,
    source_entity: str,
    relation_type: str,
    target_entity: str,
    evidence_text: str,
) -> dict[str, object]:
    return {
        "assertion_type": "explicit",
        "candidate_id": candidate_id,
        "chunk_id": "CHK_000001",
        "confidence": "high",
        "evidence_text": evidence_text,
        "record_type": "candidate_relation",
        "relation_type": relation_type,
        "source_entity": source_entity,
        "source_revision_id": "REV_000001",
        "target_entity": target_entity,
    }


def _candidate_question(*, candidate_id: str, evidence_text: str) -> dict[str, object]:
    return {
        "assertion_type": "ambiguous",
        "candidate_id": candidate_id,
        "chunk_id": "CHK_000001",
        "confidence": "low",
        "evidence_text": evidence_text,
        "question_text": "Serve conferma umana?",
        "question_type": "open_point",
        "record_type": "candidate_question",
        "source_revision_id": "REV_000001",
        "subject": "Cliente",
    }


def _assert_merge_artifacts(
    workspace: Path,
    run_id: str,
    expected: dict[str, object],
) -> None:
    artifact_dir = workspace / "artifacts" / "runs" / run_id
    for name in ("input.json", "output.json", "process_report.json"):
        document = json.loads((artifact_dir / name).read_text(encoding="utf-8"))
        for key, value in expected.items():
            assert document[key] == value

    process_report = json.loads((artifact_dir / "process_report.json").read_text(encoding="utf-8"))
    assert process_report["run_type"] == "merge"
    assert process_report["status"] == "completed"
    assert process_report["artifact_dir"] == f"artifacts/runs/{run_id}"
    assert "\\" not in process_report["artifact_dir"]


def _connect(workspace: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(workspace / "workspace.sqlite")
    connection.row_factory = sqlite3.Row
    return connection
