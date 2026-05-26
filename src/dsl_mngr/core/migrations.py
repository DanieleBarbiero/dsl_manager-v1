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
