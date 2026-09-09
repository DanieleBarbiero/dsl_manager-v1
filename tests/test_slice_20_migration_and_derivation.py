from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
from decimal import Decimal
from pathlib import Path

import pytest

from dsl_mngr.cli.app import main
from dsl_mngr.core.canonical import (
    CanonicalJsonError,
    canonical_json_artifact_v1,
    canonical_json_v1,
    canonical_sha256_v1,
)
from dsl_mngr.core.candidate_derivation import DERIVATION_RULE_CATALOG
from dsl_mngr.core.migrations import MIGRATIONS, apply_migrations
from dsl_mngr.core.workspace import initialize_workspace


TIMESTAMP = "2026-09-04T10:00:00+00:00"
DDL_FIXTURE = Path(__file__).parent / "fixtures" / "ddl" / "schema_ordini.sql"


def test_slice_20_canonical_json_hash():
    composed = {"é": "café", "emoji": "😀", "items": [None, True, 2]}
    decomposed = {"e\u0301": "cafe\u0301", "items": [None, True, 2], "emoji": "😀"}
    expected = '{"emoji":"😀","items":[null,true,2],"é":"café"}'

    assert canonical_json_v1(composed) == expected
    assert canonical_json_v1(decomposed) == expected
    assert canonical_sha256_v1(composed) == canonical_sha256_v1(decomposed)
    assert canonical_json_artifact_v1(composed) == expected + "\n"
    assert canonical_json_v1({"missing": 1}) != canonical_json_v1(
        {"missing": 1, "nullable": None}
    )
    assert canonical_json_v1({"big": 123456789012345678901234567890}) == (
        '{"big":123456789012345678901234567890}'
    )
    assert canonical_json_v1({"decimal": Decimal("1.2300"), "zero": Decimal("-0")}) == (
        '{"decimal":"1.23","zero":"0"}'
    )
    assert canonical_json_v1({"ordered": ["b", "a"]}) != canonical_json_v1(
        {"ordered": ["a", "b"]}
    )
    with pytest.raises(CanonicalJsonError, match="Binary floating-point"):
        canonical_json_v1({"not_typed": 1.5})
    with pytest.raises(CanonicalJsonError, match="key collision"):
        canonical_json_v1({"é": 1, "e\u0301": 2})


def test_slice_20_migrate_real_v6(tmp_path):
    workspace = tmp_path / "workspace"
    initialize_workspace(workspace)
    database_path = workspace / "workspace.sqlite"
    connection = _connect_path(database_path)
    try:
        apply_migrations(connection, migrations=MIGRATIONS[:6])
        _seed_real_v6(connection)
    finally:
        connection.close()

    snapshot_file = workspace / "exports" / "dsl" / "DSL_000001.json"
    snapshot_file.parent.mkdir(parents=True, exist_ok=True)
    snapshot_bytes = b'{"legacy":true}\n'
    snapshot_file.write_bytes(snapshot_bytes)

    connection = _connect_path(database_path)
    try:
        result = apply_migrations(connection, migrations=MIGRATIONS[:7])
        assert [migration.version for migration in result.applied] == [7]
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 0
        columns = {
            row["name"]: row
            for row in connection.execute("PRAGMA table_info(candidate_batches)")
        }
        assert columns["input_path"]["notnull"] == 0
        assert {"origin_type", "origin_ref"}.issubset(columns)
        candidate_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(candidate_records)")
        }
        assert "supersedes_candidate_record_id" in candidate_columns
        assert tuple(
            connection.execute(
                "SELECT origin_type, origin_ref, input_path FROM candidate_batches"
            ).fetchone()
        ) == ("file_import", None, "ai/inbox/legacy.jsonl")

        heads = connection.execute(
            """
            SELECT h.subject_id, rd.actor_type, rd.actor_id, rd.outcome,
                   rd.policy_id, rd.policy_version
            FROM review_subject_heads h
            JOIN review_decisions rd ON rd.decision_id = h.decision_id
            ORDER BY h.subject_id
            """
        ).fetchall()
        assert [tuple(row) for row in heads] == [
            ("CREC_ACTIVE", "system", "migration", "confirmed", "legacy_backfill", "1"),
            ("CREC_OBSERVED", "system", "migration", "confirmed", "legacy_backfill", "1"),
        ]
        assert connection.execute("SELECT COUNT(*) FROM candidate_lineage").fetchone()[0] == 4
        assert connection.execute("SELECT COUNT(*) FROM effective_facts").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM effective_relations").fetchone()[0] == 1
        assert connection.execute(
            "SELECT content_json FROM dsl_snapshots WHERE snapshot_id = 'DSL_000001'"
        ).fetchone()[0] == '{"legacy":true}'

        connection.execute(
            """
            INSERT INTO runs (
                run_id, run_type, status, started_at, finished_at, parent_run_id,
                input_json, output_json, created_at, updated_at
            ) VALUES ('RUN_INTERNAL', 'candidate_derivation', 'completed', ?, ?, NULL,
                      NULL, NULL, ?, ?)
            """,
            (TIMESTAMP,) * 4,
        )
        connection.execute(
            """
            INSERT INTO candidate_batches (
                batch_id, run_id, input_path, origin_type, origin_ref,
                total_records, accepted_count, rejected_count, status,
                created_at, updated_at
            ) VALUES ('CBATCH_INTERNAL', 'RUN_INTERNAL', NULL,
                      'deterministic_derivation', 'derive://DERIVE_999999',
                      0, 0, 0, 'completed', ?, ?)
            """,
            (TIMESTAMP, TIMESTAMP),
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO candidate_batches (
                    batch_id, run_id, input_path, origin_type, origin_ref,
                    total_records, accepted_count, rejected_count, status,
                    created_at, updated_at
                ) VALUES ('CBATCH_BAD', 'RUN_INTERNAL', 'forbidden.jsonl',
                          'human_correction', 'review://CORR_BAD',
                          0, 0, 0, 'completed', ?, ?)
                """,
                (TIMESTAMP, TIMESTAMP),
            )
    finally:
        connection.close()

    assert snapshot_file.read_bytes() == snapshot_bytes


def test_slice_20_ddl_table_candidate(tmp_path, capsys):
    assert "ddl_table_fact/1" in DERIVATION_RULE_CATALOG
    workspace = tmp_path / "workspace"
    initialize_workspace(workspace)
    assert main(["db", "init", str(workspace)]) == 0
    destination = workspace / "corpus" / "active" / "schema_ordini.sql"
    shutil.copyfile(DDL_FIXTURE, destination)

    assert main(["corpus", "scan", str(workspace)]) == 0
    capsys.readouterr()
    assert main(["corpus", "parse-ddl", str(workspace), "--revision", "REV_000001"]) == 0
    assert main(
        [
            "candidates",
            "derive",
            str(workspace),
            "--source-revision-id",
            "REV_000001",
            "--rule",
            "ddl_table_fact/1",
        ]
    ) == 0
    first_output = capsys.readouterr().out
    first_payload = json.loads(first_output[first_output.index("{") :])
    first_batch = first_payload["batch_id"]

    with _connect(workspace) as connection:
        batch = connection.execute(
            "SELECT input_path, origin_type, origin_ref, accepted_count FROM candidate_batches WHERE batch_id = ?",
            (first_batch,),
        ).fetchone()
        candidates = connection.execute(
            """
            SELECT candidate_record_id, candidate_id, payload_json
            FROM candidate_records WHERE batch_id = ? ORDER BY candidate_record_id
            """,
            (first_batch,),
        ).fetchall()
        assert tuple(batch[:2]) == (None, "deterministic_derivation")
        assert batch["origin_ref"].startswith("derive://DERIVE_")
        assert batch["accepted_count"] == 3
        assert connection.execute(
            "SELECT COUNT(*) FROM review_subject_heads WHERE subject_id IN (SELECT candidate_record_id FROM candidate_records WHERE batch_id = ?)",
            (first_batch,),
        ).fetchone()[0] == 0
        first_candidate_bytes = [canonical_json_v1(json.loads(row["payload_json"])) for row in candidates]
        assert all(json.loads(item)["rule_id"] == "ddl_table_fact" for item in first_candidate_bytes)
        assert all(json.loads(item)["rule_version"] == "1" for item in first_candidate_bytes)

    assert main(
        ["candidates", "derive", str(workspace), "--source-revision-id", "REV_000001"]
    ) == 0
    second_payload = json.loads(capsys.readouterr().out)
    with _connect(workspace) as connection:
        second_candidates = connection.execute(
            "SELECT payload_json FROM candidate_records WHERE batch_id = ? ORDER BY candidate_record_id",
            (second_payload["batch_id"],),
        ).fetchall()
        second_candidate_bytes = [
            canonical_json_v1(json.loads(row["payload_json"])) for row in second_candidates
        ]
    assert second_candidate_bytes == first_candidate_bytes

    for candidate in candidates:
        assert main(
            [
                "candidates",
                "review",
                "confirm",
                str(workspace),
                candidate["candidate_record_id"],
                "--actor-id",
                "ddl-reviewer",
            ]
        ) == 0
        review_payload = json.loads(capsys.readouterr().out)
        assert review_payload["outcome"] == "confirmed"
        assert review_payload["mutations"] is True

    assert main(["facts", "merge", str(workspace), "--batch", first_batch]) == 0
    capsys.readouterr()
    with _connect(workspace) as connection:
        facts = connection.execute(
            "SELECT entity_name, fact_type, status FROM facts ORDER BY entity_name"
        ).fetchall()
        assert [tuple(row) for row in facts] == [
            ("ANCLI", "database_table", "active"),
            ("ORDRIG", "database_table", "active"),
            ("ORDTES", "database_table", "active"),
        ]
        assert connection.execute("SELECT COUNT(*) FROM effective_facts").fetchone()[0] == 3


def _seed_real_v6(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        INSERT INTO runs (
            run_id, run_type, status, started_at, finished_at, parent_run_id,
            input_json, output_json, created_at, updated_at
        ) VALUES ('RUN_LEGACY', 'candidate_validation', 'completed', ?, ?, NULL,
                  NULL, NULL, ?, ?)
        """,
        (TIMESTAMP,) * 4,
    )
    connection.execute(
        """
        INSERT INTO sources (
            source_id, logical_name, source_type, source_subtype, authority_level,
            first_seen_at, last_seen_at, current_revision_id, status, created_at, updated_at
        ) VALUES ('SRC_LEGACY', 'legacy.sql', 'ddl', NULL, 'authoritative',
                  ?, ?, NULL, 'active', ?, ?)
        """,
        (TIMESTAMP,) * 4,
    )
    connection.execute(
        """
        INSERT INTO source_revisions (
            source_revision_id, source_id, revision_number, content_hash, normalized_hash,
            file_path, file_size, detected_at, status, created_at
        ) VALUES ('REV_LEGACY', 'SRC_LEGACY', 1, 'source-hash', NULL,
                  'corpus/active/legacy.sql', 10, ?, 'active', ?)
        """,
        (TIMESTAMP, TIMESTAMP),
    )
    connection.execute(
        "UPDATE sources SET current_revision_id = 'REV_LEGACY' WHERE source_id = 'SRC_LEGACY'"
    )
    connection.execute(
        """
        INSERT INTO chunks (
            chunk_id, source_revision_id, sequence, text, text_hash,
            metadata_json, status, created_at
        ) VALUES ('CHK_LEGACY', 'REV_LEGACY', 1, 'legacy evidence',
                  'chunk-hash', '{}', 'active', ?)
        """,
        (TIMESTAMP,),
    )
    connection.execute(
        """
        INSERT INTO candidate_batches (
            batch_id, run_id, input_path, total_records, accepted_count,
            rejected_count, status, created_at, updated_at
        ) VALUES ('CBATCH_LEGACY', 'RUN_LEGACY', 'ai/inbox/legacy.jsonl',
                  4, 4, 0, 'completed', ?, ?)
        """,
        (TIMESTAMP, TIMESTAMP),
    )
    candidates = (
        ("CREC_ACTIVE", "explicit", "candidate_fact"),
        ("CREC_CONFLICT", "explicit", "candidate_fact"),
        ("CREC_INFERRED", "inferred", "candidate_fact"),
        ("CREC_OBSERVED", "observed", "candidate_relation"),
    )
    for line_number, (candidate_record_id, assertion_type, record_type) in enumerate(
        candidates, start=1
    ):
        payload = {
            "assertion_type": assertion_type,
            "candidate_id": "DUPLICATE_DECLARATIVE_ID",
            "chunk_id": "CHK_LEGACY",
            "confidence": "high",
            "evidence_text": "legacy evidence",
            "record_type": record_type,
            "source_revision_id": "REV_LEGACY",
        }
        connection.execute(
            """
            INSERT INTO candidate_records (
                candidate_record_id, batch_id, run_id, line_number, candidate_id,
                record_type, source_revision_id, chunk_id, fragment_id,
                assertion_type, confidence, evidence_text, payload_json, created_at
            ) VALUES (?, 'CBATCH_LEGACY', 'RUN_LEGACY', ?, ?, ?, 'REV_LEGACY',
                      'CHK_LEGACY', NULL, ?, 'high', 'legacy evidence', ?, ?)
            """,
            (
                candidate_record_id,
                line_number,
                payload["candidate_id"],
                record_type,
                assertion_type,
                json.dumps(payload, sort_keys=True),
                TIMESTAMP,
            ),
        )
    _insert_fact(connection, "FACT_ACTIVE", "CREC_ACTIVE", "active")
    _insert_fact(connection, "FACT_CONFLICT", "CREC_CONFLICT", "conflicted")
    _insert_fact(connection, "FACT_INFERRED", "CREC_INFERRED", "inferred")
    connection.execute(
        """
        INSERT INTO relations (
            relation_id, relation_identity_hash, source_entity,
            canonical_source_entity, relation_type, target_entity,
            canonical_target_entity, assertion_type, confidence, status,
            first_candidate_record_id, created_at, updated_at
        ) VALUES ('REL_ACTIVE', 'rel-hash', 'A', 'a', 'references', 'B', 'b',
                  'observed', 'high', 'active', 'CREC_OBSERVED', ?, ?)
        """,
        (TIMESTAMP, TIMESTAMP),
    )
    connection.execute(
        """
        INSERT INTO relation_evidence (
            relation_evidence_id, relation_id, candidate_record_id,
            source_revision_id, chunk_id, fragment_id, evidence_text,
            evidence_text_hash, created_at
        ) VALUES ('REV_LEGACY_1', 'REL_ACTIVE', 'CREC_OBSERVED', 'REV_LEGACY',
                  'CHK_LEGACY', NULL, 'legacy evidence', 'evidence-hash', ?)
        """,
        (TIMESTAMP,),
    )
    connection.execute(
        """
        INSERT INTO dsl_snapshots (
            snapshot_id, run_id, dsl_hash, registry_hash, content_json,
            json_path, yaml_path, markdown_path, fact_count, relation_count,
            conflict_count, status, created_at
        ) VALUES ('DSL_000001', 'RUN_LEGACY', 'dsl-hash', 'registry-hash',
                  '{"legacy":true}', 'exports/dsl/DSL_000001.json',
                  'exports/dsl/DSL_000001.yaml', 'exports/dsl/DSL_000001.md',
                  3, 1, 0, 'completed', ?)
        """,
        (TIMESTAMP,),
    )
    connection.commit()


def _insert_fact(
    connection: sqlite3.Connection,
    fact_id: str,
    candidate_record_id: str,
    status: str,
) -> None:
    connection.execute(
        """
        INSERT INTO facts (
            fact_id, fact_identity_hash, fact_type, entity_name,
            canonical_entity_name, property_name, property_value,
            normalized_property_value, assertion_type, confidence, status,
            first_candidate_record_id, created_at, updated_at
        ) VALUES (?, ?, 'database_table', ?, ?, 'object_type', 'database_table',
                  'database_table', ?, 'high', ?, ?, ?, ?)
        """,
        (
            fact_id,
            f"hash-{fact_id}",
            fact_id,
            fact_id.lower(),
            "inferred" if status == "inferred" else "explicit",
            status,
            candidate_record_id,
            TIMESTAMP,
            TIMESTAMP,
        ),
    )
    connection.execute(
        """
        INSERT INTO fact_evidence (
            fact_evidence_id, fact_id, candidate_record_id, source_revision_id,
            chunk_id, fragment_id, evidence_text, evidence_text_hash, created_at
        ) VALUES (?, ?, ?, 'REV_LEGACY', 'CHK_LEGACY', NULL,
                  'legacy evidence', 'evidence-hash', ?)
        """,
        (f"FEV_{fact_id}", fact_id, candidate_record_id, TIMESTAMP),
    )


def _connect(workspace: Path) -> sqlite3.Connection:
    return _connect_path(workspace / "workspace.sqlite")


def _connect_path(database_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection
