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
EVIDENCE_DESCRIPTION = "Cliente description source."
EVIDENCE_STATUS_ACTIVE = "Cliente stato e attivo."
EVIDENCE_STATUS_BLOCKED = "Cliente stato e bloccato."
EVIDENCE_RELATION = "Il cliente puo inserire uno o piu ordini."
CHUNK_TEXT = " ".join(
    (
        EVIDENCE_DESCRIPTION,
        EVIDENCE_STATUS_ACTIVE,
        EVIDENCE_STATUS_BLOCKED,
        EVIDENCE_RELATION,
    )
)


def test_render_dsl_snapshot(tmp_path):
    workspace = _ready_workspace_with_registry(tmp_path)

    completed = subprocess.run(
        [sys.executable, "-m", "dsl_mngr", "dsl", "render", str(workspace)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert "Run: RUN_000003" in completed.stdout
    assert "Snapshot: DSL_000001" in completed.stdout
    assert "Facts: 3" in completed.stdout
    assert "Relations: 1" in completed.stdout
    assert "Conflicts: 1" in completed.stdout
    assert "JSON: exports/dsl/DSL_000001.json" in completed.stdout
    assert "YAML: exports/dsl/DSL_000001.yaml" in completed.stdout
    assert "Markdown: exports/dsl/DSL_000001.md" in completed.stdout

    json_path = workspace / "exports" / "dsl" / "DSL_000001.json"
    yaml_path = workspace / "exports" / "dsl" / "DSL_000001.yaml"
    markdown_path = workspace / "exports" / "dsl" / "DSL_000001.md"
    assert json_path.is_file()
    assert yaml_path.is_file()
    assert markdown_path.is_file()

    content = json.loads(json_path.read_text(encoding="utf-8"))
    assert len(content["metadata"]["dsl_hash"]) == 64
    assert len(content["metadata"]["registry_hash"]) == 64
    assert content["metadata"]["counts"] == {
        "conflicts": 1,
        "entities": 1,
        "facts": 3,
        "relations": 1,
    }
    assert content["entities"][0]["name"] == "Cliente"
    assert content["entities"][0]["canonical_name"] == "cliente"
    assert any(
        fact["fact_id"] == "FACT_000001"
        and fact["property_name"] == "description"
        and fact["property_value"] == "Anagrafica clienti gestita dal sistema"
        and fact["status"] == "active"
        for fact in content["entities"][0]["facts"]
    )
    assert content["relations"] == [
        {
            "assertion_type": "explicit",
            "canonical_source_entity": "cliente",
            "canonical_target_entity": "ordine",
            "confidence": "high",
            "relation_id": "REL_000001",
            "relation_type": "places",
            "source_entity": "Cliente",
            "status": "active",
            "target_entity": "Ordine",
        }
    ]
    assert content["conflicts"][0]["conflict_id"] == "CONFLICT_000001"
    assert content["conflicts"][0]["conflict_type"] == "different_values_same_property"
    assert content["conflicts"][0]["status"] == "open"

    assert "metadata:" in yaml_path.read_text(encoding="utf-8")
    markdown_text = markdown_path.read_text(encoding="utf-8")
    for heading in ("## Entities", "## Relations", "## Conflicts", "## Traceability"):
        assert heading in markdown_text

    with _connect(workspace) as connection:
        snapshot = connection.execute("SELECT * FROM dsl_snapshots").fetchone()

    assert snapshot["snapshot_id"] == "DSL_000001"
    assert snapshot["run_id"] == "RUN_000003"
    assert snapshot["dsl_hash"] == content["metadata"]["dsl_hash"]
    assert snapshot["registry_hash"] == content["metadata"]["registry_hash"]
    assert snapshot["content_json"] == json_path.read_text(encoding="utf-8")
    assert snapshot["json_path"] == "exports/dsl/DSL_000001.json"
    assert snapshot["yaml_path"] == "exports/dsl/DSL_000001.yaml"
    assert snapshot["markdown_path"] == "exports/dsl/DSL_000001.md"
    assert snapshot["fact_count"] == 3
    assert snapshot["relation_count"] == 1
    assert snapshot["conflict_count"] == 1
    assert snapshot["status"] == "completed"

    _assert_render_artifacts(
        workspace,
        "RUN_000003",
        {
            "conflict_count": 1,
            "dsl_hash": content["metadata"]["dsl_hash"],
            "fact_count": 3,
            "json_path": "exports/dsl/DSL_000001.json",
            "markdown_path": "exports/dsl/DSL_000001.md",
            "registry_hash": content["metadata"]["registry_hash"],
            "relation_count": 1,
            "snapshot_id": "DSL_000001",
            "yaml_path": "exports/dsl/DSL_000001.yaml",
        },
    )

    app_logs = [
        json.loads(line)
        for line in (workspace / "logs" / "app.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert app_logs[-1]["event"] == "dsl_render_completed"
    assert app_logs[-1]["run_id"] == "RUN_000003"


def test_snapshot_hash_stable(tmp_path):
    workspace = _ready_workspace_with_registry(tmp_path)

    assert main(["dsl", "render", str(workspace)]) == 0
    assert main(["dsl", "render", str(workspace)]) == 0

    with _connect(workspace) as connection:
        snapshots = connection.execute(
            "SELECT * FROM dsl_snapshots ORDER BY snapshot_id"
        ).fetchall()

    assert [row["snapshot_id"] for row in snapshots] == ["DSL_000001", "DSL_000002"]
    assert snapshots[0]["dsl_hash"] == snapshots[1]["dsl_hash"]
    assert snapshots[0]["registry_hash"] == snapshots[1]["registry_hash"]
    assert snapshots[0]["json_path"] == "exports/dsl/DSL_000001.json"
    assert snapshots[1]["json_path"] == "exports/dsl/DSL_000002.json"

    first_content = json.loads((workspace / snapshots[0]["json_path"]).read_text(encoding="utf-8"))
    second_content = json.loads((workspace / snapshots[1]["json_path"]).read_text(encoding="utf-8"))
    assert first_content["metadata"]["dsl_hash"] == second_content["metadata"]["dsl_hash"]
    assert first_content["metadata"]["registry_hash"] == second_content["metadata"]["registry_hash"]


def test_dsl_contains_traceability(tmp_path):
    workspace = _ready_workspace_with_registry(tmp_path)

    assert main(["dsl", "render", str(workspace)]) == 0

    content = json.loads(
        (workspace / "exports" / "dsl" / "DSL_000001.json").read_text(encoding="utf-8")
    )
    fact_evidence = content["traceability"]["facts"]["FACT_000001"][0]
    assert fact_evidence == {
        "candidate_record_id": "CREC_000001",
        "chunk_id": "CHK_000001",
        "evidence_text_hash": hashlib.sha256(EVIDENCE_DESCRIPTION.encode("utf-8")).hexdigest(),
        "file_path": "corpus/active/manuale_clienti.txt",
        "fragment_id": None,
        "source_id": "SRC_000001",
        "source_revision_id": "REV_000001",
    }

    relation_evidence = content["traceability"]["relations"]["REL_000001"][0]
    assert relation_evidence["candidate_record_id"] == "CREC_000004"
    assert relation_evidence["source_revision_id"] == "REV_000001"
    assert relation_evidence["source_id"] == "SRC_000001"
    assert relation_evidence["file_path"] == "corpus/active/manuale_clienti.txt"
    assert relation_evidence["chunk_id"] == "CHK_000001"
    assert relation_evidence["fragment_id"] is None
    assert relation_evidence["evidence_text_hash"] == hashlib.sha256(
        EVIDENCE_RELATION.encode("utf-8")
    ).hexdigest()


def _ready_workspace_with_registry(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    initialize_workspace(workspace)
    migrate_workspace_database(workspace)
    _insert_source_revision_and_chunk(workspace)
    batch_id = _validate_candidates(workspace)
    assert main(["facts", "merge", str(workspace), "--batch", batch_id]) == 0
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


def _validate_candidates(workspace: Path) -> str:
    input_file = workspace / "ai" / "inbox" / "slice_07_candidates.jsonl"
    records = [
        _candidate_fact(
            candidate_id="CAND_FACT_001",
            entity_name="Cliente",
            property_name="description",
            property_value="Anagrafica clienti gestita dal sistema",
            evidence_text=EVIDENCE_DESCRIPTION,
        ),
        _candidate_fact(
            candidate_id="CAND_STATUS_001",
            entity_name="Cliente",
            property_name="status",
            property_value="ATTIVO",
            evidence_text=EVIDENCE_STATUS_ACTIVE,
            fact_type="business_rule",
        ),
        _candidate_fact(
            candidate_id="CAND_STATUS_002",
            entity_name="Cliente",
            property_name="status",
            property_value="BLOCCATO",
            evidence_text=EVIDENCE_STATUS_BLOCKED,
            fact_type="business_rule",
        ),
        _candidate_relation(
            candidate_id="CAND_REL_001",
            source_entity="Cliente",
            relation_type="places",
            target_entity="Ordine",
            evidence_text=EVIDENCE_RELATION,
        ),
    ]
    lines = [json.dumps(record, sort_keys=True) for record in records]
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


def _assert_render_artifacts(
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
    assert process_report["run_type"] == "dsl_render"
    assert process_report["status"] == "completed"
    assert process_report["artifact_dir"] == f"artifacts/runs/{run_id}"
    assert "\\" not in process_report["artifact_dir"]


def _connect(workspace: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(workspace / "workspace.sqlite")
    connection.row_factory = sqlite3.Row
    return connection
