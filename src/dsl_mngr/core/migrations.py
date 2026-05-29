from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from dsl_mngr.core.database import DatabaseSettings, open_database, resolve_database_settings


Clock = Callable[[], datetime]


class MigrationError(RuntimeError):
    """Raised when the migration history is inconsistent."""


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    statements: tuple[str, ...]

    @property
    def checksum(self) -> str:
        payload = "\n".join((self.name, *self.statements))
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
        connection.execute("BEGIN")
        try:
            for statement in migration.statements:
                connection.execute(statement)
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
