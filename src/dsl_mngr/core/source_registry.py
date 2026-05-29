from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from dsl_mngr.core.config import load_config
from dsl_mngr.core.database import (
    DatabaseConfigurationError,
    DatabaseSettings,
    WorkspaceNotInitializedError,
    open_database,
    resolve_database_settings,
)
from dsl_mngr.core.hashing import sha256_file
from dsl_mngr.core.migrations import MIGRATIONS


Clock = Callable[[], datetime]


class CorpusScanError(RuntimeError):
    """Raised when corpus scanning cannot be completed."""


class DatabaseNotReadyError(CorpusScanError):
    """Raised when the workspace database has not been initialized or migrated."""


@dataclass(frozen=True)
class ScannedFile:
    path: Path
    relative_path: str
    content_hash: str
    file_size: int


@dataclass(frozen=True)
class CorpusScanResult:
    workspace_dir: Path
    corpus_dir: Path
    added: int
    modified: int
    deleted: int
    unchanged: int


def scan_corpus(
    workspace_dir: str | Path,
    *,
    corpus_path: str | Path | None = None,
    clock: Clock | None = None,
) -> CorpusScanResult:
    settings = resolve_database_settings(workspace_dir)
    _ensure_database_file_exists(settings)
    corpus_dir = _resolve_corpus_dir(settings.workspace_dir, corpus_path)
    scanned_files = _scan_files(settings.workspace_dir, corpus_dir)

    connection = open_database(settings.database_path, enable_wal=settings.wal_enabled)
    try:
        _ensure_database_migrated(connection)
        return _apply_scan(connection, settings, corpus_dir, scanned_files, clock=clock)
    finally:
        connection.close()


def _ensure_database_file_exists(settings: DatabaseSettings) -> None:
    if not settings.database_path.is_file():
        raise DatabaseNotReadyError(
            f"Database is not initialized: {settings.database_path}. "
            "Run 'dsl-manager db init <workspace>' before 'dsl-manager corpus scan'."
        )


def _resolve_corpus_dir(workspace_dir: Path, corpus_path: str | Path | None) -> Path:
    if corpus_path is None:
        config = load_config(workspace_dir)
        corpus_config = config.get("corpus", {})
        corpus_path = corpus_config.get("active_dir", "corpus/active")

    try:
        resolved = _resolve_inside_workspace(workspace_dir, corpus_path)
    except DatabaseConfigurationError as exc:
        raise CorpusScanError(f"Corpus path escapes the workspace: {corpus_path}") from exc

    if not resolved.is_dir():
        raise CorpusScanError(f"Corpus path is not a directory: {resolved}")
    return resolved


def _resolve_inside_workspace(workspace_dir: Path, configured_path: str | Path) -> Path:
    workspace_path = workspace_dir.resolve()
    raw_path = Path(str(configured_path)).expanduser()
    resolved_path = raw_path.resolve() if raw_path.is_absolute() else (workspace_path / raw_path).resolve()
    try:
        resolved_path.relative_to(workspace_path)
    except ValueError as exc:
        raise DatabaseConfigurationError(
            f"Configured path escapes the workspace: {configured_path}"
        ) from exc
    return resolved_path


def _scan_files(workspace_dir: Path, corpus_dir: Path) -> tuple[ScannedFile, ...]:
    scanned: list[ScannedFile] = []
    for path in sorted((entry for entry in corpus_dir.rglob("*") if entry.is_file()), key=_path_key):
        scanned.append(
            ScannedFile(
                path=path,
                relative_path=_relative_workspace_path(workspace_dir, path),
                content_hash=sha256_file(path),
                file_size=path.stat().st_size,
            )
        )
    return tuple(scanned)


def _ensure_database_migrated(connection: sqlite3.Connection) -> None:
    schema_row = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'schema_migrations'"
    ).fetchone()
    if schema_row is None:
        raise DatabaseNotReadyError(
            "Database schema is not initialized. "
            "Run 'dsl-manager db init <workspace>' before 'dsl-manager corpus scan'."
        )

    rows = connection.execute(
        "SELECT version, name, checksum FROM schema_migrations"
    ).fetchall()
    applied = {int(row["version"]): row for row in rows}
    for migration in MIGRATIONS:
        row = applied.get(migration.version)
        if row is None:
            raise DatabaseNotReadyError(
                "Database has pending migrations. "
                "Run 'dsl-manager db init <workspace>' before 'dsl-manager corpus scan'."
            )
        if row["name"] != migration.name or row["checksum"] != migration.checksum:
            raise DatabaseNotReadyError(
                f"Database migration {migration.version} does not match this application version."
            )


def _apply_scan(
    connection: sqlite3.Connection,
    settings: DatabaseSettings,
    corpus_dir: Path,
    scanned_files: tuple[ScannedFile, ...],
    *,
    clock: Clock | None,
) -> CorpusScanResult:
    timestamp = _timestamp(clock)
    existing_sources = _load_sources_under_corpus(
        connection,
        _relative_workspace_path(settings.workspace_dir, corpus_dir),
    )
    scanned_by_path = {scanned_file.relative_path: scanned_file for scanned_file in scanned_files}

    added = 0
    modified = 0
    unchanged = 0

    connection.execute("BEGIN")
    try:
        for relative_path in sorted(scanned_by_path):
            scanned_file = scanned_by_path[relative_path]
            source = existing_sources.get(relative_path)
            if source is None:
                _register_added_source(connection, scanned_file, timestamp)
                added += 1
                continue

            current_hash = source["current_content_hash"]
            if (
                source["status"] == "active"
                and source["current_revision_status"] == "active"
                and current_hash == scanned_file.content_hash
            ):
                _mark_source_seen(connection, source["source_id"], timestamp)
                unchanged += 1
                continue

            _register_modified_source(connection, source, scanned_file, timestamp)
            modified += 1

        deleted = 0
        for relative_path in sorted(existing_sources):
            if relative_path in scanned_by_path:
                continue
            source = existing_sources[relative_path]
            if source["status"] == "deleted_from_corpus":
                continue
            _register_deleted_source(connection, source, timestamp)
            deleted += 1
    except Exception:
        connection.rollback()
        raise
    else:
        connection.commit()

    return CorpusScanResult(
        workspace_dir=settings.workspace_dir,
        corpus_dir=corpus_dir,
        added=added,
        modified=modified,
        deleted=deleted,
        unchanged=unchanged,
    )


def _load_sources_under_corpus(connection: sqlite3.Connection, corpus_relative_path: str) -> dict[str, sqlite3.Row]:
    rows = connection.execute(
        """
        SELECT
            s.source_id,
            s.logical_name,
            s.status,
            s.current_revision_id,
            r.content_hash AS current_content_hash,
            r.status AS current_revision_status
        FROM sources AS s
        LEFT JOIN source_revisions AS r
            ON r.source_revision_id = s.current_revision_id
        ORDER BY s.logical_name
        """
    ).fetchall()
    return {
        row["logical_name"]: row
        for row in rows
        if _is_under_corpus(row["logical_name"], corpus_relative_path)
    }


def _is_under_corpus(logical_name: str, corpus_relative_path: str) -> bool:
    if not corpus_relative_path:
        return True
    return logical_name == corpus_relative_path or logical_name.startswith(f"{corpus_relative_path}/")


def _register_added_source(
    connection: sqlite3.Connection,
    scanned_file: ScannedFile,
    timestamp: str,
) -> None:
    source_id = _next_id(connection, "sources", "source_id", "SRC")
    revision_id = _next_id(connection, "source_revisions", "source_revision_id", "REV")
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
        VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?)
        """,
        (
            source_id,
            scanned_file.relative_path,
            "unknown",
            None,
            "unknown",
            timestamp,
            timestamp,
            "active",
            timestamp,
            timestamp,
        ),
    )
    _insert_revision(
        connection,
        revision_id=revision_id,
        source_id=source_id,
        revision_number=1,
        scanned_file=scanned_file,
        timestamp=timestamp,
        status="active",
    )
    connection.execute(
        "UPDATE sources SET current_revision_id = ? WHERE source_id = ?",
        (revision_id, source_id),
    )
    _insert_event(
        connection,
        source_id=source_id,
        revision_id=revision_id,
        event_type="source_added",
        timestamp=timestamp,
        details={
            "content_hash": scanned_file.content_hash,
            "file_path": scanned_file.relative_path,
            "file_size": scanned_file.file_size,
        },
    )


def _register_modified_source(
    connection: sqlite3.Connection,
    source: sqlite3.Row,
    scanned_file: ScannedFile,
    timestamp: str,
) -> None:
    source_id = source["source_id"]
    previous_revision_id = source["current_revision_id"]
    revision_id = _next_id(connection, "source_revisions", "source_revision_id", "REV")
    revision_number = _next_revision_number(connection, source_id)

    if previous_revision_id is not None:
        connection.execute(
            "UPDATE source_revisions SET status = ? WHERE source_revision_id = ?",
            ("superseded", previous_revision_id),
        )

    _insert_revision(
        connection,
        revision_id=revision_id,
        source_id=source_id,
        revision_number=revision_number,
        scanned_file=scanned_file,
        timestamp=timestamp,
        status="active",
    )
    connection.execute(
        """
        UPDATE sources
        SET last_seen_at = ?,
            current_revision_id = ?,
            status = ?,
            updated_at = ?
        WHERE source_id = ?
        """,
        (timestamp, revision_id, "active", timestamp, source_id),
    )
    _insert_event(
        connection,
        source_id=source_id,
        revision_id=revision_id,
        event_type="source_modified",
        timestamp=timestamp,
        details={
            "content_hash": scanned_file.content_hash,
            "file_path": scanned_file.relative_path,
            "file_size": scanned_file.file_size,
            "previous_revision_id": previous_revision_id,
        },
    )


def _register_deleted_source(
    connection: sqlite3.Connection,
    source: sqlite3.Row,
    timestamp: str,
) -> None:
    source_id = source["source_id"]
    revision_id = source["current_revision_id"]
    connection.execute(
        """
        UPDATE sources
        SET status = ?,
            updated_at = ?
        WHERE source_id = ?
        """,
        ("deleted_from_corpus", timestamp, source_id),
    )
    if revision_id is not None:
        connection.execute(
            "UPDATE source_revisions SET status = ? WHERE source_revision_id = ?",
            ("deleted", revision_id),
        )
    _insert_event(
        connection,
        source_id=source_id,
        revision_id=revision_id,
        event_type="source_deleted",
        timestamp=timestamp,
        details={"file_path": source["logical_name"]},
    )


def _mark_source_seen(connection: sqlite3.Connection, source_id: str, timestamp: str) -> None:
    connection.execute(
        """
        UPDATE sources
        SET last_seen_at = ?,
            updated_at = ?
        WHERE source_id = ?
        """,
        (timestamp, timestamp, source_id),
    )


def _insert_revision(
    connection: sqlite3.Connection,
    *,
    revision_id: str,
    source_id: str,
    revision_number: int,
    scanned_file: ScannedFile,
    timestamp: str,
    status: str,
) -> None:
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
            revision_id,
            source_id,
            revision_number,
            scanned_file.content_hash,
            scanned_file.relative_path,
            scanned_file.file_size,
            timestamp,
            status,
            timestamp,
        ),
    )


def _insert_event(
    connection: sqlite3.Connection,
    *,
    source_id: str,
    revision_id: str | None,
    event_type: str,
    timestamp: str,
    details: dict[str, Any],
) -> None:
    event_id = _next_id(connection, "source_events", "source_event_id", "EVT")
    connection.execute(
        """
        INSERT INTO source_events (
            source_event_id,
            source_id,
            source_revision_id,
            event_type,
            event_timestamp,
            details_json,
            run_id
        )
        VALUES (?, ?, ?, ?, ?, ?, NULL)
        """,
        (
            event_id,
            source_id,
            revision_id,
            event_type,
            timestamp,
            json.dumps(details, ensure_ascii=False, sort_keys=True),
        ),
    )


def _next_revision_number(connection: sqlite3.Connection, source_id: str) -> int:
    row = connection.execute(
        "SELECT COALESCE(MAX(revision_number), 0) + 1 AS next_revision_number "
        "FROM source_revisions WHERE source_id = ?",
        (source_id,),
    ).fetchone()
    return int(row["next_revision_number"])


def _next_id(connection: sqlite3.Connection, table: str, column: str, prefix: str) -> str:
    rows = connection.execute(
        f"SELECT {column} FROM {table} WHERE {column} LIKE ?",
        (f"{prefix}_%",),
    ).fetchall()
    next_number = 1
    for row in rows:
        raw_id = row[column]
        try:
            number = int(str(raw_id).rsplit("_", 1)[1])
        except (IndexError, ValueError):
            continue
        next_number = max(next_number, number + 1)
    return f"{prefix}_{next_number:06d}"


def _relative_workspace_path(workspace_dir: Path, path: Path) -> str:
    return path.resolve().relative_to(workspace_dir.resolve()).as_posix()


def _path_key(path: Path) -> str:
    return path.as_posix().lower()


def _timestamp(clock: Clock | None) -> str:
    now = clock() if clock else datetime.now().astimezone()
    return now.isoformat(timespec="seconds")
