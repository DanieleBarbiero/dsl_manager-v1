from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from dsl_mngr.core.canonical import canonical_json_v1, canonical_sha256_v1
from dsl_mngr.core.database import DatabaseSettings, open_database, resolve_database_settings


Clock = Callable[[], datetime]
MigrationRunner = Callable[[sqlite3.Connection, str], None]


class MigrationError(RuntimeError):
    """Raised when the migration history is inconsistent."""


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    statements: tuple[str, ...]
    runner: MigrationRunner | None = None
    requires_foreign_keys_disabled: bool = False

    @property
    def checksum(self) -> str:
        parts = [self.name, *self.statements]
        if self.runner is not None:
            parts.append(f"runner:{self.runner.__name__}")
        if self.requires_foreign_keys_disabled:
            parts.append("requires_foreign_keys_disabled:true")
        payload = "\n".join(parts)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class MigrationResult:
    applied: tuple[Migration, ...]
    skipped: tuple[Migration, ...]

    @property
    def applied_count(self) -> int:
        return len(self.applied)

    @property
    def skipped_count(self) -> int:
        return len(self.skipped)


@dataclass(frozen=True)
class DatabaseMigrationResult:
    settings: DatabaseSettings
    migrations: MigrationResult
    database_created: bool

    @property
    def database_path(self) -> Path:
        return self.settings.database_path

    @property
    def applied_count(self) -> int:
        return self.migrations.applied_count

    @property
    def skipped_count(self) -> int:
        return self.migrations.skipped_count


SCHEMA_MIGRATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    checksum TEXT NOT NULL,
    applied_at TEXT NOT NULL
)
"""


def _run_v7_backfill(connection: sqlite3.Connection, applied_at: str) -> None:
    candidate_rows = connection.execute(
        """
        SELECT candidate_record_id
        FROM candidate_records
        ORDER BY candidate_record_id
        """
    ).fetchall()
    for row in candidate_rows:
        candidate_record_id = str(row["candidate_record_id"])
        connection.execute(
            """
            INSERT INTO candidate_lineage (
                candidate_record_id,
                root_candidate_record_id,
                parent_candidate_record_id,
                correction_group_id
            )
            VALUES (?, ?, NULL, NULL)
            """,
            (candidate_record_id, candidate_record_id),
        )

    materialized_rows = connection.execute(
        """
        SELECT DISTINCT
            cr.candidate_record_id,
            cr.run_id,
            cr.payload_json,
            cr.chunk_id,
            cr.fragment_id
        FROM candidate_records cr
        WHERE cr.assertion_type IN ('explicit', 'observed')
          AND (
              EXISTS (
                  SELECT 1
                  FROM fact_evidence fe
                  JOIN facts f ON f.fact_id = fe.fact_id
                  WHERE fe.candidate_record_id = cr.candidate_record_id
                    AND f.status = 'active'
              )
              OR EXISTS (
                  SELECT 1
                  FROM relation_evidence re
                  JOIN relations r ON r.relation_id = re.relation_id
                  WHERE re.candidate_record_id = cr.candidate_record_id
                    AND r.status = 'active'
              )
          )
        ORDER BY cr.candidate_record_id
        """
    ).fetchall()
    for row in materialized_rows:
        candidate_record_id = str(row["candidate_record_id"])
        decision_id = f"RDEC_LEGACY_{candidate_record_id}"
        evidence_refs = [
            value
            for value in (row["chunk_id"], row["fragment_id"])
            if value is not None
        ]
        candidate_payload = _json_object(row["payload_json"])
        request_payload = {
            "actor": {"actor_id": "migration", "actor_type": "system"},
            "candidate_payload": candidate_payload,
            "evidence_refs": evidence_refs,
            "expected_head_decision_id": None,
            "operation": "legacy_backfill",
            "outcome": "confirmed",
            "policy": {"policy_id": "legacy_backfill", "policy_version": "1"},
            "reason": "legacy_backfill",
            "subject": {
                "subject_id": candidate_record_id,
                "subject_type": "candidate_record",
            },
        }
        semantic_payload = {
            "candidate_payload": candidate_payload,
            "evidence_refs": evidence_refs,
            "outcome": "confirmed",
            "policy": {"policy_id": "legacy_backfill", "policy_version": "1"},
            "subject": {
                "subject_id": candidate_record_id,
                "subject_type": "candidate_record",
            },
        }
        connection.execute(
            """
            INSERT INTO review_decisions (
                decision_id, subject_type, subject_id, actor_type, actor_id,
                outcome, reason, run_id, created_at, supersedes_decision_id,
                expected_head_decision_id, idempotency_key,
                request_payload_hash, semantic_payload_hash,
                policy_id, policy_version,
                request_payload_json, semantic_payload_json
            )
            VALUES (?, 'candidate_record', ?, 'system', 'migration',
                    'confirmed', 'legacy_backfill', ?, ?, NULL,
                    NULL, ?, ?, ?, 'legacy_backfill', '1', ?, ?)
            """,
            (
                decision_id,
                candidate_record_id,
                row["run_id"],
                applied_at,
                f"legacy_backfill:{candidate_record_id}",
                canonical_sha256_v1(request_payload),
                canonical_sha256_v1(semantic_payload),
                canonical_json_v1(request_payload),
                canonical_json_v1(semantic_payload),
            ),
        )
        for ordinal, evidence_ref in enumerate(evidence_refs, start=1):
            connection.execute(
                """
                INSERT INTO review_decision_evidence (decision_id, evidence_ref, ordinal)
                VALUES (?, ?, ?)
                """,
                (decision_id, evidence_ref, ordinal),
            )
        connection.execute(
            """
            INSERT INTO review_subject_heads (
                subject_type, subject_id, decision_id, updated_at
            )
            VALUES ('candidate_record', ?, ?, ?)
            """,
            (candidate_record_id, decision_id, applied_at),
        )


def _json_object(value: str) -> dict[str, Any]:
    import json

    payload = json.loads(value)
    return payload if isinstance(payload, dict) else {}


MIGRATIONS: tuple[Migration, ...] = (
    Migration(
        version=1,
        name="create_minimal_registry_schema",
        statements=(
            """
            CREATE TABLE IF NOT EXISTS sources (
                source_id TEXT PRIMARY KEY,
                logical_name TEXT NOT NULL,
                source_type TEXT NOT NULL,
                source_subtype TEXT,
                authority_level TEXT NOT NULL,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                current_revision_id TEXT,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (current_revision_id)
                    REFERENCES source_revisions(source_revision_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS source_revisions (
                source_revision_id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                revision_number INTEGER NOT NULL,
                content_hash TEXT NOT NULL,
                normalized_hash TEXT,
                file_path TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                detected_at TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (source_id)
                    REFERENCES sources(source_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS source_events (
                source_event_id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                source_revision_id TEXT,
                event_type TEXT NOT NULL,
                event_timestamp TEXT NOT NULL,
                details_json TEXT,
                run_id TEXT,
                FOREIGN KEY (source_id)
                    REFERENCES sources(source_id),
                FOREIGN KEY (source_revision_id)
                    REFERENCES source_revisions(source_revision_id),
                FOREIGN KEY (run_id)
                    REFERENCES runs(run_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                run_type TEXT NOT NULL,
                status TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                parent_run_id TEXT,
                input_json TEXT,
                output_json TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (parent_run_id)
                    REFERENCES runs(run_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS worker_runs (
                worker_run_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                worker_name TEXT NOT NULL,
                worker_version TEXT,
                status TEXT NOT NULL,
                input_path TEXT,
                output_path TEXT,
                report_path TEXT,
                log_path TEXT,
                exit_code INTEGER,
                duration_ms INTEGER,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                FOREIGN KEY (run_id)
                    REFERENCES runs(run_id)
            )
            """,
        ),
    ),
    Migration(
        version=2,
        name="create_candidate_validation_schema",
        statements=(
            """
            CREATE TABLE IF NOT EXISTS chunks (
                chunk_id TEXT PRIMARY KEY,
                source_revision_id TEXT NOT NULL,
                sequence INTEGER NOT NULL,
                text TEXT NOT NULL,
                text_hash TEXT,
                metadata_json TEXT,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (source_revision_id)
                    REFERENCES source_revisions(source_revision_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS source_fragments (
                fragment_id TEXT PRIMARY KEY,
                source_revision_id TEXT NOT NULL,
                fragment_type TEXT NOT NULL,
                sequence INTEGER NOT NULL,
                path_or_selector TEXT,
                line_start INTEGER,
                line_end INTEGER,
                char_start INTEGER,
                char_end INTEGER,
                text TEXT NOT NULL,
                text_hash TEXT,
                metadata_json TEXT,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (source_revision_id)
                    REFERENCES source_revisions(source_revision_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS candidate_batches (
                batch_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                input_path TEXT NOT NULL,
                total_records INTEGER NOT NULL,
                accepted_count INTEGER NOT NULL,
                rejected_count INTEGER NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (run_id)
                    REFERENCES runs(run_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS candidate_records (
                candidate_record_id TEXT PRIMARY KEY,
                batch_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                line_number INTEGER NOT NULL,
                candidate_id TEXT NOT NULL,
                record_type TEXT NOT NULL,
                source_revision_id TEXT NOT NULL,
                chunk_id TEXT,
                fragment_id TEXT,
                assertion_type TEXT NOT NULL,
                confidence TEXT NOT NULL,
                evidence_text TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (batch_id)
                    REFERENCES candidate_batches(batch_id),
                FOREIGN KEY (run_id)
                    REFERENCES runs(run_id),
                FOREIGN KEY (source_revision_id)
                    REFERENCES source_revisions(source_revision_id),
                FOREIGN KEY (chunk_id)
                    REFERENCES chunks(chunk_id),
                FOREIGN KEY (fragment_id)
                    REFERENCES source_fragments(fragment_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS rejected_candidates (
                rejected_candidate_id TEXT PRIMARY KEY,
                batch_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                line_number INTEGER NOT NULL,
                candidate_id TEXT,
                record_type TEXT,
                reason TEXT NOT NULL,
                message TEXT,
                raw_line TEXT,
                payload_json TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (batch_id)
                    REFERENCES candidate_batches(batch_id),
                FOREIGN KEY (run_id)
                    REFERENCES runs(run_id)
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_chunks_source_revision
            ON chunks(source_revision_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_source_fragments_source_revision
            ON source_fragments(source_revision_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_candidate_records_batch
            ON candidate_records(batch_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_rejected_candidates_batch
            ON rejected_candidates(batch_id)
            """,
        ),
    ),
    Migration(
        version=3,
        name="create_fact_merge_schema",
        statements=(
            """
            CREATE TABLE IF NOT EXISTS facts (
                fact_id TEXT PRIMARY KEY,
                fact_identity_hash TEXT NOT NULL UNIQUE,
                fact_type TEXT NOT NULL,
                entity_name TEXT NOT NULL,
                canonical_entity_name TEXT NOT NULL,
                property_name TEXT NOT NULL,
                property_value TEXT NOT NULL,
                normalized_property_value TEXT NOT NULL,
                assertion_type TEXT NOT NULL,
                confidence TEXT NOT NULL,
                status TEXT NOT NULL,
                first_candidate_record_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (first_candidate_record_id)
                    REFERENCES candidate_records(candidate_record_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS fact_evidence (
                fact_evidence_id TEXT PRIMARY KEY,
                fact_id TEXT NOT NULL,
                candidate_record_id TEXT NOT NULL,
                source_revision_id TEXT NOT NULL,
                chunk_id TEXT,
                fragment_id TEXT,
                evidence_text TEXT NOT NULL,
                evidence_text_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE (fact_id, candidate_record_id),
                FOREIGN KEY (fact_id)
                    REFERENCES facts(fact_id),
                FOREIGN KEY (candidate_record_id)
                    REFERENCES candidate_records(candidate_record_id),
                FOREIGN KEY (source_revision_id)
                    REFERENCES source_revisions(source_revision_id),
                FOREIGN KEY (chunk_id)
                    REFERENCES chunks(chunk_id),
                FOREIGN KEY (fragment_id)
                    REFERENCES source_fragments(fragment_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS relations (
                relation_id TEXT PRIMARY KEY,
                relation_identity_hash TEXT NOT NULL UNIQUE,
                source_entity TEXT NOT NULL,
                canonical_source_entity TEXT NOT NULL,
                relation_type TEXT NOT NULL,
                target_entity TEXT NOT NULL,
                canonical_target_entity TEXT NOT NULL,
                assertion_type TEXT NOT NULL,
                confidence TEXT NOT NULL,
                status TEXT NOT NULL,
                first_candidate_record_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (first_candidate_record_id)
                    REFERENCES candidate_records(candidate_record_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS relation_evidence (
                relation_evidence_id TEXT PRIMARY KEY,
                relation_id TEXT NOT NULL,
                candidate_record_id TEXT NOT NULL,
                source_revision_id TEXT NOT NULL,
                chunk_id TEXT,
                fragment_id TEXT,
                evidence_text TEXT NOT NULL,
                evidence_text_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE (relation_id, candidate_record_id),
                FOREIGN KEY (relation_id)
                    REFERENCES relations(relation_id),
                FOREIGN KEY (candidate_record_id)
                    REFERENCES candidate_records(candidate_record_id),
                FOREIGN KEY (source_revision_id)
                    REFERENCES source_revisions(source_revision_id),
                FOREIGN KEY (chunk_id)
                    REFERENCES chunks(chunk_id),
                FOREIGN KEY (fragment_id)
                    REFERENCES source_fragments(fragment_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS conflicts (
                conflict_id TEXT PRIMARY KEY,
                conflict_key_hash TEXT NOT NULL UNIQUE,
                conflict_type TEXT NOT NULL,
                entity_name TEXT NOT NULL,
                canonical_entity_name TEXT NOT NULL,
                property_name TEXT NOT NULL,
                left_fact_id TEXT NOT NULL,
                right_fact_id TEXT NOT NULL,
                left_value TEXT NOT NULL,
                right_value TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (left_fact_id)
                    REFERENCES facts(fact_id),
                FOREIGN KEY (right_fact_id)
                    REFERENCES facts(fact_id)
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_fact_evidence_candidate_record
            ON fact_evidence(candidate_record_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_relation_evidence_candidate_record
            ON relation_evidence(candidate_record_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_facts_entity_property
            ON facts(canonical_entity_name, property_name)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_relations_entities_type
            ON relations(canonical_source_entity, relation_type, canonical_target_entity)
            """,
        ),
    ),
    Migration(
        version=4,
        name="create_dsl_snapshot_schema",
        statements=(
            """
            CREATE TABLE IF NOT EXISTS dsl_snapshots (
                snapshot_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                dsl_hash TEXT NOT NULL,
                registry_hash TEXT NOT NULL,
                content_json TEXT NOT NULL,
                json_path TEXT NOT NULL,
                yaml_path TEXT NOT NULL,
                markdown_path TEXT NOT NULL,
                fact_count INTEGER NOT NULL,
                relation_count INTEGER NOT NULL,
                conflict_count INTEGER NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (run_id)
                    REFERENCES runs(run_id)
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_dsl_snapshots_dsl_hash
            ON dsl_snapshots(dsl_hash)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_dsl_snapshots_run
            ON dsl_snapshots(run_id)
            """,
        ),
    ),
    Migration(
        version=5,
        name="create_ai_package_schema",
        statements=(
            """
            CREATE TABLE IF NOT EXISTS ai_packages (
                package_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                package_path TEXT NOT NULL,
                manifest_path TEXT NOT NULL,
                content_path TEXT NOT NULL,
                instructions_path TEXT NOT NULL,
                candidate_schema_path TEXT NOT NULL,
                output_template_path TEXT NOT NULL,
                package_hash TEXT NOT NULL,
                source_revision_count INTEGER NOT NULL,
                chunk_count INTEGER NOT NULL,
                fragment_count INTEGER NOT NULL,
                status TEXT NOT NULL,
                stale_reason TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (run_id)
                    REFERENCES runs(run_id)
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_ai_packages_run
            ON ai_packages(run_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_ai_packages_status
            ON ai_packages(status)
            """,
        ),
    ),
    Migration(
        version=6,
        name="create_graph_export_schema",
        statements=(
            """
            CREATE TABLE IF NOT EXISTS graph_exports (
                graph_export_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                snapshot_id TEXT NOT NULL,
                dsl_hash TEXT NOT NULL,
                graph_hash TEXT NOT NULL,
                format TEXT NOT NULL,
                graph_path TEXT NOT NULL,
                report_path TEXT NOT NULL,
                node_count INTEGER NOT NULL,
                edge_count INTEGER NOT NULL,
                orphan_count INTEGER NOT NULL,
                warning_count INTEGER NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (run_id)
                    REFERENCES runs(run_id),
                FOREIGN KEY (snapshot_id)
                    REFERENCES dsl_snapshots(snapshot_id)
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_graph_exports_run
            ON graph_exports(run_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_graph_exports_snapshot
            ON graph_exports(snapshot_id)
            """,
        ),
    ),
    Migration(
        version=7,
        name="create_candidate_review_lineage_schema",
        statements=(
            "PRAGMA defer_foreign_keys = ON",
            """
            CREATE TABLE candidate_batches_v7 (
                batch_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                input_path TEXT,
                origin_type TEXT NOT NULL,
                origin_ref TEXT,
                total_records INTEGER NOT NULL,
                accepted_count INTEGER NOT NULL,
                rejected_count INTEGER NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                CHECK (
                    (origin_type IN ('file_import', 'ai_import') AND input_path IS NOT NULL)
                    OR
                    (origin_type IN ('human_correction', 'deterministic_derivation')
                     AND input_path IS NULL AND origin_ref IS NOT NULL)
                ),
                FOREIGN KEY (run_id) REFERENCES runs(run_id)
            )
            """,
            """
            INSERT INTO candidate_batches_v7 (
                batch_id, run_id, input_path, origin_type, origin_ref,
                total_records, accepted_count, rejected_count, status,
                created_at, updated_at
            )
            SELECT
                batch_id, run_id, input_path, 'file_import', NULL,
                total_records, accepted_count, rejected_count, status,
                created_at, updated_at
            FROM candidate_batches
            """,
            "DROP TABLE candidate_batches",
            "ALTER TABLE candidate_batches_v7 RENAME TO candidate_batches",
            """
            CREATE INDEX idx_candidate_batches_origin
            ON candidate_batches(origin_type, origin_ref)
            """,
            """
            ALTER TABLE candidate_records
            ADD COLUMN supersedes_candidate_record_id TEXT
                REFERENCES candidate_records(candidate_record_id)
            """,
            """
            CREATE UNIQUE INDEX idx_candidate_records_supersedes
            ON candidate_records(supersedes_candidate_record_id)
            WHERE supersedes_candidate_record_id IS NOT NULL
            """,
            """
            CREATE TABLE review_decisions (
                decision_id TEXT PRIMARY KEY,
                subject_type TEXT NOT NULL,
                subject_id TEXT NOT NULL,
                actor_type TEXT NOT NULL,
                actor_id TEXT NOT NULL,
                outcome TEXT NOT NULL CHECK (outcome IN ('confirmed', 'rejected', 'superseded')),
                reason TEXT NOT NULL,
                run_id TEXT,
                created_at TEXT NOT NULL,
                supersedes_decision_id TEXT,
                expected_head_decision_id TEXT,
                idempotency_key TEXT NOT NULL,
                request_payload_hash TEXT NOT NULL,
                semantic_payload_hash TEXT NOT NULL,
                policy_id TEXT,
                policy_version TEXT,
                request_payload_json TEXT NOT NULL,
                semantic_payload_json TEXT NOT NULL,
                UNIQUE (actor_type, actor_id, idempotency_key),
                FOREIGN KEY (run_id) REFERENCES runs(run_id),
                FOREIGN KEY (supersedes_decision_id) REFERENCES review_decisions(decision_id),
                FOREIGN KEY (expected_head_decision_id) REFERENCES review_decisions(decision_id),
                CHECK (actor_type IN ('human', 'automatic', 'system')),
                CHECK (
                    (actor_type = 'automatic'
                     AND policy_id IS NOT NULL AND policy_version IS NOT NULL)
                    OR
                    (actor_type = 'human'
                     AND policy_id IS NULL AND policy_version IS NULL)
                    OR actor_type = 'system'
                )
            )
            """,
            """
            CREATE TABLE review_subject_heads (
                subject_type TEXT NOT NULL,
                subject_id TEXT NOT NULL,
                decision_id TEXT NOT NULL UNIQUE,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (subject_type, subject_id),
                FOREIGN KEY (decision_id) REFERENCES review_decisions(decision_id)
            )
            """,
            """
            CREATE TABLE review_decision_evidence (
                decision_id TEXT NOT NULL,
                evidence_ref TEXT NOT NULL,
                ordinal INTEGER NOT NULL,
                PRIMARY KEY (decision_id, ordinal),
                FOREIGN KEY (decision_id) REFERENCES review_decisions(decision_id)
            )
            """,
            """
            CREATE TABLE review_audit_notes (
                note_id TEXT PRIMARY KEY,
                subject_type TEXT NOT NULL,
                subject_id TEXT NOT NULL,
                actor_type TEXT NOT NULL,
                actor_id TEXT NOT NULL,
                reason TEXT NOT NULL,
                request_payload_hash TEXT NOT NULL,
                idempotency_key TEXT NOT NULL,
                run_id TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (run_id) REFERENCES runs(run_id)
            )
            """,
            """
            CREATE TABLE candidate_lineage (
                candidate_record_id TEXT PRIMARY KEY,
                root_candidate_record_id TEXT NOT NULL,
                parent_candidate_record_id TEXT UNIQUE,
                correction_group_id TEXT,
                FOREIGN KEY (candidate_record_id) REFERENCES candidate_records(candidate_record_id),
                FOREIGN KEY (root_candidate_record_id) REFERENCES candidate_records(candidate_record_id),
                FOREIGN KEY (parent_candidate_record_id) REFERENCES candidate_records(candidate_record_id)
            )
            """,
            """
            CREATE TABLE candidate_corrections (
                correction_id TEXT PRIMARY KEY,
                correction_group_id TEXT NOT NULL UNIQUE,
                original_candidate_record_id TEXT NOT NULL,
                replacement_candidate_record_id TEXT NOT NULL UNIQUE,
                delta_json TEXT NOT NULL,
                correction_evidence_refs_json TEXT NOT NULL,
                reason TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (original_candidate_record_id)
                    REFERENCES candidate_records(candidate_record_id),
                FOREIGN KEY (replacement_candidate_record_id)
                    REFERENCES candidate_records(candidate_record_id)
            )
            """,
            """
            CREATE TABLE reconciliation_required (
                reconciliation_id TEXT PRIMARY KEY,
                subject_type TEXT NOT NULL,
                subject_id TEXT NOT NULL,
                replacement_subject_id TEXT,
                reason TEXT NOT NULL,
                opened_by_decision_id TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('open', 'closed')),
                opened_at TEXT NOT NULL,
                closed_at TEXT,
                closed_by_run_id TEXT,
                FOREIGN KEY (opened_by_decision_id) REFERENCES review_decisions(decision_id),
                FOREIGN KEY (closed_by_run_id) REFERENCES runs(run_id)
            )
            """,
            """
            CREATE UNIQUE INDEX idx_reconciliation_open_subject
            ON reconciliation_required(subject_type, subject_id)
            WHERE status = 'open'
            """,
            """
            CREATE TABLE candidate_derivation_runs (
                derivation_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                rule_set_version TEXT NOT NULL,
                source_revision_id TEXT,
                batch_id TEXT,
                status TEXT NOT NULL,
                counters_json TEXT NOT NULL,
                report_path TEXT NOT NULL,
                created_at TEXT NOT NULL,
                completed_at TEXT,
                FOREIGN KEY (run_id) REFERENCES runs(run_id),
                FOREIGN KEY (source_revision_id)
                    REFERENCES source_revisions(source_revision_id),
                FOREIGN KEY (batch_id) REFERENCES candidate_batches(batch_id)
            )
            """,
            """
            CREATE TRIGGER review_decisions_no_update
            BEFORE UPDATE ON review_decisions
            BEGIN
                SELECT RAISE(ABORT, 'review_decisions_append_only');
            END
            """,
            """
            CREATE TRIGGER review_decisions_no_delete
            BEFORE DELETE ON review_decisions
            BEGIN
                SELECT RAISE(ABORT, 'review_decisions_append_only');
            END
            """,
            """
            CREATE TRIGGER review_decisions_same_subject
            BEFORE INSERT ON review_decisions
            WHEN NEW.supersedes_decision_id IS NOT NULL
            BEGIN
                SELECT CASE WHEN NOT EXISTS (
                    SELECT 1
                    FROM review_decisions previous
                    WHERE previous.decision_id = NEW.supersedes_decision_id
                      AND previous.subject_type = NEW.subject_type
                      AND previous.subject_id = NEW.subject_id
                ) THEN RAISE(ABORT, 'review_decision_subject_mismatch') END;
            END
            """,
            """
            CREATE TRIGGER review_decisions_acyclic
            BEFORE INSERT ON review_decisions
            WHEN NEW.supersedes_decision_id IS NOT NULL
            BEGIN
                SELECT CASE WHEN NEW.supersedes_decision_id = NEW.decision_id
                    THEN RAISE(ABORT, 'review_decision_cycle') END;
                WITH RECURSIVE ancestors(decision_id) AS (
                    SELECT NEW.supersedes_decision_id
                    UNION ALL
                    SELECT rd.supersedes_decision_id
                    FROM review_decisions rd
                    JOIN ancestors a ON rd.decision_id = a.decision_id
                    WHERE rd.supersedes_decision_id IS NOT NULL
                )
                SELECT CASE WHEN EXISTS (
                    SELECT 1 FROM ancestors WHERE decision_id = NEW.decision_id
                ) THEN RAISE(ABORT, 'review_decision_cycle') END;
            END
            """,
            """
            CREATE TRIGGER review_subject_heads_subject_insert
            BEFORE INSERT ON review_subject_heads
            BEGIN
                SELECT CASE WHEN NOT EXISTS (
                    SELECT 1 FROM review_decisions rd
                    WHERE rd.decision_id = NEW.decision_id
                      AND rd.subject_type = NEW.subject_type
                      AND rd.subject_id = NEW.subject_id
                ) THEN RAISE(ABORT, 'review_head_subject_mismatch') END;
            END
            """,
            """
            CREATE TRIGGER review_subject_heads_subject_update
            BEFORE UPDATE ON review_subject_heads
            BEGIN
                SELECT CASE WHEN NOT EXISTS (
                    SELECT 1 FROM review_decisions rd
                    WHERE rd.decision_id = NEW.decision_id
                      AND rd.subject_type = NEW.subject_type
                      AND rd.subject_id = NEW.subject_id
                ) THEN RAISE(ABORT, 'review_head_subject_mismatch') END;
            END
            """,
            """
            CREATE TRIGGER candidate_lineage_cycle_insert
            BEFORE INSERT ON candidate_lineage
            WHEN NEW.parent_candidate_record_id IS NOT NULL
            BEGIN
                WITH RECURSIVE ancestors(candidate_record_id) AS (
                    SELECT NEW.parent_candidate_record_id
                    UNION ALL
                    SELECT cl.parent_candidate_record_id
                    FROM candidate_lineage cl
                    JOIN ancestors a
                      ON cl.candidate_record_id = a.candidate_record_id
                    WHERE cl.parent_candidate_record_id IS NOT NULL
                )
                SELECT CASE WHEN EXISTS (
                    SELECT 1 FROM ancestors
                    WHERE candidate_record_id = NEW.candidate_record_id
                ) THEN RAISE(ABORT, 'candidate_lineage_cycle') END;
                SELECT CASE WHEN NOT EXISTS (
                    SELECT 1 FROM candidate_lineage parent
                    WHERE parent.candidate_record_id = NEW.parent_candidate_record_id
                      AND parent.root_candidate_record_id = NEW.root_candidate_record_id
                ) THEN RAISE(ABORT, 'candidate_lineage_root_mismatch') END;
                SELECT CASE WHEN NOT EXISTS (
                    SELECT 1 FROM candidate_records candidate
                    WHERE candidate.candidate_record_id = NEW.candidate_record_id
                      AND candidate.supersedes_candidate_record_id
                          = NEW.parent_candidate_record_id
                ) THEN RAISE(ABORT, 'candidate_lineage_parent_mismatch') END;
            END
            """,
            """
            CREATE TRIGGER candidate_lineage_root_insert
            BEFORE INSERT ON candidate_lineage
            WHEN NEW.parent_candidate_record_id IS NULL
            BEGIN
                SELECT CASE WHEN NEW.root_candidate_record_id <> NEW.candidate_record_id
                    THEN RAISE(ABORT, 'candidate_lineage_root_mismatch') END;
            END
            """,
            """
            CREATE TRIGGER candidate_lineage_no_update
            BEFORE UPDATE ON candidate_lineage
            BEGIN
                SELECT RAISE(ABORT, 'candidate_lineage_append_only');
            END
            """,
            """
            CREATE TRIGGER candidate_lineage_no_delete
            BEFORE DELETE ON candidate_lineage
            BEGIN
                SELECT RAISE(ABORT, 'candidate_lineage_append_only');
            END
            """,
            """
            CREATE VIEW effective_fact_evidence AS
            SELECT
                fe.*,
                rd.decision_id AS review_decision_id,
                rd.semantic_payload_hash AS review_semantic_payload_hash,
                rd.policy_id AS review_policy_id,
                rd.policy_version AS review_policy_version
            FROM fact_evidence fe
            JOIN candidate_lineage cl
              ON cl.candidate_record_id = fe.candidate_record_id
            JOIN review_subject_heads h
              ON h.subject_type = 'candidate_record'
             AND h.subject_id = fe.candidate_record_id
            JOIN review_decisions rd ON rd.decision_id = h.decision_id
            WHERE rd.outcome = 'confirmed'
              AND NOT EXISTS (
                  SELECT 1 FROM candidate_lineage child
                  WHERE child.parent_candidate_record_id = fe.candidate_record_id
              )
            """,
            """
            CREATE VIEW effective_relation_evidence AS
            SELECT
                re.*,
                rd.decision_id AS review_decision_id,
                rd.semantic_payload_hash AS review_semantic_payload_hash,
                rd.policy_id AS review_policy_id,
                rd.policy_version AS review_policy_version
            FROM relation_evidence re
            JOIN candidate_lineage cl
              ON cl.candidate_record_id = re.candidate_record_id
            JOIN review_subject_heads h
              ON h.subject_type = 'candidate_record'
             AND h.subject_id = re.candidate_record_id
            JOIN review_decisions rd ON rd.decision_id = h.decision_id
            WHERE rd.outcome = 'confirmed'
              AND NOT EXISTS (
                  SELECT 1 FROM candidate_lineage child
                  WHERE child.parent_candidate_record_id = re.candidate_record_id
              )
            """,
            """
            CREATE VIEW effective_facts AS
            SELECT f.*
            FROM facts f
            WHERE EXISTS (
                SELECT 1 FROM effective_fact_evidence efe
                WHERE efe.fact_id = f.fact_id
            )
            """,
            """
            CREATE VIEW effective_relations AS
            SELECT r.*
            FROM relations r
            WHERE EXISTS (
                SELECT 1 FROM effective_relation_evidence ere
                WHERE ere.relation_id = r.relation_id
            )
            """,
        ),
        runner=_run_v7_backfill,
        requires_foreign_keys_disabled=True,
    ),
    Migration(
        version=8,
        name="create_workbook_manifest_schema",
        statements=(
            """
            CREATE TABLE workbook_manifests (
                manifest_id TEXT PRIMARY KEY,
                source_revision_id TEXT NOT NULL UNIQUE,
                schema_version TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                manifest_hash TEXT NOT NULL,
                artifact_path TEXT NOT NULL,
                status TEXT NOT NULL,
                warnings_json TEXT NOT NULL,
                FOREIGN KEY (source_revision_id)
                    REFERENCES source_revisions(source_revision_id)
            )
            """,
            """
            CREATE TABLE workbook_sheets (
                sheet_id TEXT PRIMARY KEY,
                manifest_id TEXT NOT NULL,
                sheet_index INTEGER NOT NULL,
                name TEXT NOT NULL,
                visibility TEXT NOT NULL,
                relationship_id TEXT NOT NULL,
                part_name TEXT NOT NULL,
                max_row INTEGER NOT NULL,
                max_column INTEGER NOT NULL,
                UNIQUE (manifest_id, sheet_index),
                UNIQUE (manifest_id, name),
                FOREIGN KEY (manifest_id)
                    REFERENCES workbook_manifests(manifest_id)
            )
            """,
            """
            CREATE TABLE workbook_regions (
                region_id TEXT PRIMARY KEY,
                sheet_id TEXT NOT NULL,
                ordinal INTEGER NOT NULL,
                start_cell TEXT NOT NULL,
                end_cell TEXT NOT NULL,
                region_kind TEXT NOT NULL,
                region_hash TEXT NOT NULL,
                fragment_id TEXT,
                UNIQUE (sheet_id, ordinal),
                FOREIGN KEY (sheet_id) REFERENCES workbook_sheets(sheet_id),
                FOREIGN KEY (fragment_id) REFERENCES source_fragments(fragment_id)
            )
            """,
            """
            CREATE INDEX idx_workbook_manifests_hash
            ON workbook_manifests(manifest_hash)
            """,
            """
            CREATE INDEX idx_workbook_sheets_manifest
            ON workbook_sheets(manifest_id, sheet_index)
            """,
            """
            CREATE INDEX idx_workbook_regions_sheet
            ON workbook_regions(sheet_id, ordinal)
            """,
            """
            CREATE UNIQUE INDEX idx_workbook_regions_fragment
            ON workbook_regions(fragment_id)
            WHERE fragment_id IS NOT NULL
            """,
        ),
    ),
    Migration(
        version=9,
        name="create_temporal_core_schema",
        statements=(
            """
            CREATE TABLE raw_temporal_evidence (
                temporal_evidence_id TEXT PRIMARY KEY,
                target_subject_type TEXT NOT NULL CHECK (
                    target_subject_type IN (
                        'source_revision', 'source_fragment', 'candidate_record',
                        'fact', 'relation'
                    )
                ),
                target_subject_id TEXT NOT NULL,
                source_revision_id TEXT NOT NULL,
                source_fragment_id TEXT,
                source_key TEXT NOT NULL,
                source_format TEXT NOT NULL,
                raw_value TEXT NOT NULL,
                extraction_method TEXT NOT NULL,
                extraction_version TEXT NOT NULL,
                precision TEXT NOT NULL,
                timezone_status TEXT NOT NULL CHECK (
                    timezone_status IN ('explicit', 'resolved', 'unknown', 'incompatible')
                ),
                timezone_value TEXT,
                initial_reliability TEXT NOT NULL CHECK (
                    initial_reliability IN ('high', 'medium', 'low', 'unknown')
                ),
                warnings_json TEXT NOT NULL,
                evidence_hash TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                FOREIGN KEY (source_revision_id)
                    REFERENCES source_revisions(source_revision_id),
                FOREIGN KEY (source_fragment_id)
                    REFERENCES source_fragments(fragment_id)
            )
            """,
            """
            CREATE TABLE temporal_candidate_details (
                candidate_record_id TEXT PRIMARY KEY,
                target_subject_type TEXT NOT NULL CHECK (
                    target_subject_type IN (
                        'source_revision', 'source_fragment', 'candidate_record',
                        'fact', 'relation'
                    )
                ),
                target_subject_id TEXT NOT NULL,
                normalized_start TEXT,
                normalized_end TEXT,
                original_precision TEXT NOT NULL,
                timezone_status TEXT NOT NULL CHECK (
                    timezone_status IN ('explicit', 'resolved', 'unknown', 'incompatible')
                ),
                timezone_value TEXT,
                bounds_semantics TEXT NOT NULL CHECK (
                    bounds_semantics IN ('inclusive', 'coverage_envelope')
                ),
                derivation_policy_id TEXT NOT NULL,
                derivation_policy_version TEXT NOT NULL,
                FOREIGN KEY (candidate_record_id)
                    REFERENCES candidate_records(candidate_record_id)
            )
            """,
            """
            CREATE TABLE temporal_candidate_evidence (
                candidate_record_id TEXT NOT NULL,
                temporal_evidence_id TEXT NOT NULL,
                ordinal INTEGER NOT NULL CHECK (ordinal > 0),
                PRIMARY KEY (candidate_record_id, ordinal),
                UNIQUE (candidate_record_id, temporal_evidence_id),
                FOREIGN KEY (candidate_record_id)
                    REFERENCES temporal_candidate_details(candidate_record_id),
                FOREIGN KEY (temporal_evidence_id)
                    REFERENCES raw_temporal_evidence(temporal_evidence_id)
            )
            """,
            """
            CREATE TABLE temporal_intervals (
                interval_id TEXT PRIMARY KEY,
                subject_type TEXT NOT NULL CHECK (
                    subject_type IN (
                        'source_revision', 'source_fragment', 'candidate_record',
                        'fact', 'relation'
                    )
                ),
                subject_id TEXT NOT NULL,
                start_value TEXT,
                end_value TEXT,
                timeformat TEXT NOT NULL CHECK (timeformat IN ('date', 'dateTime')),
                timezone_value TEXT,
                original_precision TEXT NOT NULL,
                bounds_semantics TEXT NOT NULL CHECK (
                    bounds_semantics IN ('inclusive', 'coverage_envelope')
                ),
                decision_id TEXT NOT NULL,
                source_candidate_record_id TEXT NOT NULL,
                interval_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE (subject_type, subject_id, interval_hash),
                UNIQUE (source_candidate_record_id),
                FOREIGN KEY (decision_id) REFERENCES review_decisions(decision_id),
                FOREIGN KEY (source_candidate_record_id)
                    REFERENCES temporal_candidate_details(candidate_record_id)
            )
            """,
            """
            CREATE INDEX idx_raw_temporal_evidence_target
            ON raw_temporal_evidence(target_subject_type, target_subject_id)
            """,
            """
            CREATE INDEX idx_raw_temporal_evidence_revision
            ON raw_temporal_evidence(source_revision_id, temporal_evidence_id)
            """,
            """
            CREATE INDEX idx_temporal_intervals_subject
            ON temporal_intervals(subject_type, subject_id)
            """,
            """
            CREATE TRIGGER raw_temporal_evidence_no_update
            BEFORE UPDATE ON raw_temporal_evidence
            BEGIN
                SELECT RAISE(ABORT, 'raw_temporal_evidence_append_only');
            END
            """,
            """
            CREATE TRIGGER raw_temporal_evidence_no_delete
            BEFORE DELETE ON raw_temporal_evidence
            BEGIN
                SELECT RAISE(ABORT, 'raw_temporal_evidence_append_only');
            END
            """,
            """
            CREATE TRIGGER temporal_intervals_no_update
            BEFORE UPDATE ON temporal_intervals
            BEGIN
                SELECT RAISE(ABORT, 'temporal_intervals_append_only');
            END
            """,
            """
            CREATE TRIGGER temporal_intervals_no_delete
            BEFORE DELETE ON temporal_intervals
            BEGIN
                SELECT RAISE(ABORT, 'temporal_intervals_append_only');
            END
            """,
        ),
    ),
    Migration(
        version=10,
        name="create_temporal_consolidation_schema",
        statements=(
            """
            CREATE TABLE temporal_evidence_groups (
                group_id TEXT PRIMARY KEY,
                target_subject_type TEXT NOT NULL CHECK (
                    target_subject_type IN (
                        'source_revision', 'source_fragment', 'candidate_record',
                        'fact', 'relation'
                    )
                ),
                target_subject_id TEXT NOT NULL,
                policy_id TEXT NOT NULL,
                policy_version TEXT NOT NULL,
                group_hash TEXT NOT NULL UNIQUE,
                assessment TEXT NOT NULL CHECK (
                    assessment IN (
                        'concordant', 'single_source', 'ambiguous',
                        'conflicted', 'low_quality'
                    )
                ),
                created_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE temporal_evidence_group_members (
                group_id TEXT NOT NULL,
                temporal_evidence_id TEXT NOT NULL,
                independence_class TEXT NOT NULL CHECK (
                    independence_class IN (
                        'independent', 'correlated', 'duplicate', 'low_quality'
                    )
                ),
                ordinal INTEGER NOT NULL CHECK (ordinal > 0),
                PRIMARY KEY (group_id, temporal_evidence_id),
                UNIQUE (group_id, ordinal),
                FOREIGN KEY (group_id)
                    REFERENCES temporal_evidence_groups(group_id),
                FOREIGN KEY (temporal_evidence_id)
                    REFERENCES raw_temporal_evidence(temporal_evidence_id)
            )
            """,
            """
            CREATE TABLE temporal_conflicts (
                conflict_id TEXT PRIMARY KEY,
                target_subject_type TEXT NOT NULL CHECK (
                    target_subject_type IN (
                        'source_revision', 'source_fragment', 'candidate_record',
                        'fact', 'relation'
                    )
                ),
                target_subject_id TEXT NOT NULL,
                group_id TEXT NOT NULL,
                reason TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('open', 'resolved')),
                created_at TEXT NOT NULL,
                resolved_by_decision_id TEXT,
                UNIQUE (group_id, reason),
                FOREIGN KEY (group_id)
                    REFERENCES temporal_evidence_groups(group_id),
                FOREIGN KEY (resolved_by_decision_id)
                    REFERENCES review_decisions(decision_id)
            )
            """,
            """
            CREATE INDEX idx_temporal_evidence_groups_target
            ON temporal_evidence_groups(target_subject_type, target_subject_id)
            """,
            """
            CREATE INDEX idx_temporal_conflicts_target_status
            ON temporal_conflicts(target_subject_type, target_subject_id, status)
            """,
        ),
    ),
)


def migrate_workspace_database(
    workspace_dir: str | Path,
    *,
    cli_options: dict[str, Any] | None = None,
    clock: Clock | None = None,
) -> DatabaseMigrationResult:
    settings = resolve_database_settings(workspace_dir, cli_options=cli_options)
    database_created = not settings.database_path.exists()
    connection = open_database(settings.database_path, enable_wal=settings.wal_enabled)
    try:
        migrations = apply_migrations(connection, clock=clock)
    finally:
        connection.close()

    return DatabaseMigrationResult(
        settings=settings,
        migrations=migrations,
        database_created=database_created,
    )


def apply_migrations(
    connection: sqlite3.Connection,
    *,
    migrations: Iterable[Migration] = MIGRATIONS,
    clock: Clock | None = None,
) -> MigrationResult:
    ordered_migrations = _ordered_migrations(migrations)
    connection.execute(SCHEMA_MIGRATIONS_TABLE)
    existing = _load_existing_migrations(connection)

    applied: list[Migration] = []
    skipped: list[Migration] = []
    for migration in ordered_migrations:
        existing_record = existing.get(migration.version)
        if existing_record is not None:
            _validate_existing_migration(migration, existing_record)
            skipped.append(migration)
            continue

        applied_at = _timestamp(clock)
        foreign_keys_were_enabled = bool(connection.execute("PRAGMA foreign_keys").fetchone()[0])
        if migration.requires_foreign_keys_disabled and foreign_keys_were_enabled:
            connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute("BEGIN")
        try:
            for statement in migration.statements:
                connection.execute(statement)
            if migration.runner is not None:
                migration.runner(connection, applied_at)
            if migration.requires_foreign_keys_disabled:
                violations = connection.execute("PRAGMA foreign_key_check").fetchall()
                if violations:
                    first = violations[0]
                    raise MigrationError(
                        "Migration produced a foreign-key violation: "
                        f"table={first[0]}, rowid={first[1]}, parent={first[2]}."
                    )
            connection.execute(
                """
                INSERT INTO schema_migrations (version, name, checksum, applied_at)
                VALUES (?, ?, ?, ?)
                """,
                (migration.version, migration.name, migration.checksum, applied_at),
            )
        except Exception:
            connection.rollback()
            raise
        else:
            connection.commit()
        finally:
            if migration.requires_foreign_keys_disabled and foreign_keys_were_enabled:
                connection.execute("PRAGMA foreign_keys = ON")
        applied.append(migration)

    return MigrationResult(applied=tuple(applied), skipped=tuple(skipped))


def _ordered_migrations(migrations: Iterable[Migration]) -> tuple[Migration, ...]:
    ordered = tuple(sorted(migrations, key=lambda migration: migration.version))
    versions = [migration.version for migration in ordered]
    if versions != sorted(set(versions)):
        raise MigrationError("Migration versions must be unique and ordered.")
    return ordered


def _load_existing_migrations(connection: sqlite3.Connection) -> dict[int, sqlite3.Row]:
    rows = connection.execute(
        "SELECT version, name, checksum, applied_at FROM schema_migrations"
    ).fetchall()
    return {int(row["version"]): row for row in rows}


def _validate_existing_migration(migration: Migration, row: sqlite3.Row) -> None:
    if row["name"] != migration.name or row["checksum"] != migration.checksum:
        raise MigrationError(
            f"Recorded migration {migration.version} does not match current definition."
        )


def _timestamp(clock: Clock | None) -> str:
    now = clock() if clock else datetime.now().astimezone()
    return now.isoformat(timespec="seconds")
