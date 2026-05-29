from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from dsl_mngr.core.database import (
    DatabaseSettings,
    open_database,
    resolve_database_settings,
)
from dsl_mngr.core.runs import (
    DatabaseNotReadyError,
    canonical_json,
    next_id,
    run_artifact_paths,
    timestamp_now,
    validate_database_migrations,
    write_process_report,
)


Clock = Callable[[], datetime]

SKIPPED_RECORD_TYPES = {
    "candidate_conflict",
    "candidate_mapping",
    "candidate_question",
}
class MergeError(RuntimeError):
    """Raised when candidate records cannot be merged."""


class MergeDatabaseNotReadyError(MergeError):
    """Raised when facts merge needs a migrated database."""


@dataclass(frozen=True)
class MergeBatchInfo:
    batch_id: str
    candidate_record_count: int

    def to_initial_payload(self) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "candidate_record_count": self.candidate_record_count,
            "facts_created": 0,
            "facts_existing": 0,
            "relations_created": 0,
            "relations_existing": 0,
            "conflicts_created": 0,
            "conflicts_existing": 0,
            "skipped_records": 0,
        }


@dataclass(frozen=True)
class MergeResult:
    run_id: str
    batch_id: str
    candidate_record_count: int
    facts_created: int
    facts_existing: int
    relations_created: int
    relations_existing: int
    conflicts_created: int
    conflicts_existing: int
    skipped_records: int

    def to_artifact_payload(self) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "candidate_record_count": self.candidate_record_count,
            "conflicts_created": self.conflicts_created,
            "conflicts_existing": self.conflicts_existing,
            "facts_created": self.facts_created,
            "facts_existing": self.facts_existing,
            "relations_created": self.relations_created,
            "relations_existing": self.relations_existing,
            "run_id": self.run_id,
            "skipped_records": self.skipped_records,
        }


@dataclass
class _MergeCounters:
    facts_created: int = 0
    facts_existing: int = 0
    relations_created: int = 0
    relations_existing: int = 0
    conflicts_created: int = 0
    conflicts_existing: int = 0
    skipped_records: int = 0
    created_conflict_hashes: set[str] = field(default_factory=set)
    existing_conflict_hashes: set[str] = field(default_factory=set)

    def count_created_conflict(self, conflict_key_hash: str) -> None:
        if conflict_key_hash not in self.created_conflict_hashes:
            self.created_conflict_hashes.add(conflict_key_hash)
            self.conflicts_created += 1

    def count_existing_conflict(self, conflict_key_hash: str) -> None:
        if (
            conflict_key_hash not in self.created_conflict_hashes
            and conflict_key_hash not in self.existing_conflict_hashes
        ):
            self.existing_conflict_hashes.add(conflict_key_hash)
            self.conflicts_existing += 1


def ensure_merge_database_ready(workspace_dir: str | Path) -> DatabaseSettings:
    settings = resolve_database_settings(workspace_dir)
    if not settings.database_path.is_file():
        raise MergeDatabaseNotReadyError(
            f"Database is not initialized: {settings.database_path}. "
            "Run 'dsl-manager db init <workspace>' before 'dsl-manager facts merge'."
        )

    connection = open_database(settings.database_path, enable_wal=settings.wal_enabled)
    try:
        try:
            validate_database_migrations(connection)
        except DatabaseNotReadyError as exc:
            message = str(exc).replace("dsl-manager run", "dsl-manager facts merge")
            raise MergeDatabaseNotReadyError(message) from exc
    finally:
        connection.close()
    return settings


def load_merge_batch_info(workspace_dir: str | Path, batch_id: str) -> MergeBatchInfo:
    settings = ensure_merge_database_ready(workspace_dir)
    connection = open_database(settings.database_path, enable_wal=settings.wal_enabled)
    try:
        validate_database_migrations(connection)
        _require_batch(connection, batch_id)
        count = connection.execute(
            """
            SELECT COUNT(*)
            FROM candidate_records
            WHERE batch_id = ?
            """,
            (batch_id,),
        ).fetchone()[0]
    finally:
        connection.close()

    return MergeBatchInfo(
        batch_id=batch_id,
        candidate_record_count=int(count),
    )


def merge_candidate_batch(
    workspace_dir: str | Path,
    *,
    run_id: str,
    batch_id: str,
    clock: Clock | None = None,
) -> MergeResult:
    settings = ensure_merge_database_ready(workspace_dir)
    timestamp = timestamp_now(clock)
    connection = open_database(settings.database_path, enable_wal=settings.wal_enabled)
    counters = _MergeCounters()

    try:
        validate_database_migrations(connection)
        _require_batch(connection, batch_id)
        records = _load_candidate_records(connection, batch_id)

        connection.execute("BEGIN")
        try:
            for record in records:
                record_type = record["record_type"]
                if record_type == "candidate_fact":
                    _merge_fact(connection, record, timestamp=timestamp, counters=counters)
                elif record_type == "candidate_relation":
                    _merge_relation(connection, record, timestamp=timestamp, counters=counters)
                elif record_type in SKIPPED_RECORD_TYPES:
                    counters.skipped_records += 1
                else:
                    counters.skipped_records += 1
            connection.commit()
        except Exception:
            connection.rollback()
            raise
    finally:
        connection.close()

    return MergeResult(
        run_id=run_id,
        batch_id=batch_id,
        candidate_record_count=len(records),
        facts_created=counters.facts_created,
        facts_existing=counters.facts_existing,
        relations_created=counters.relations_created,
        relations_existing=counters.relations_existing,
        conflicts_created=counters.conflicts_created,
        conflicts_existing=counters.conflicts_existing,
        skipped_records=counters.skipped_records,
    )


def write_merge_artifacts(workspace_dir: str | Path, result: MergeResult) -> None:
    artifacts = run_artifact_paths(workspace_dir, result.run_id)
    payload = result.to_artifact_payload()
    input_document = {
        "artifact_dir": artifacts.artifact_dir_relative,
        "run_id": result.run_id,
        "run_type": "merge",
        **payload,
    }
    artifacts.input_path.write_text(canonical_json(input_document), encoding="utf-8", newline="\n")

    report = json.loads(artifacts.process_report_path.read_text(encoding="utf-8"))
    report.update(payload)
    write_process_report(artifacts.process_report_path, report)


def _require_batch(connection: sqlite3.Connection, batch_id: str) -> sqlite3.Row:
    row = connection.execute(
        """
        SELECT batch_id
        FROM candidate_batches
        WHERE batch_id = ?
        """,
        (batch_id,),
    ).fetchone()
    if row is None:
        raise MergeError(f"Candidate batch not found: {batch_id}.")
    return row


def _load_candidate_records(
    connection: sqlite3.Connection,
    batch_id: str,
) -> list[sqlite3.Row]:
    return connection.execute(
        """
        SELECT
            candidate_record_id,
            batch_id,
            line_number,
            candidate_id,
            record_type,
            source_revision_id,
            chunk_id,
            fragment_id,
            assertion_type,
            confidence,
            evidence_text,
            payload_json
        FROM candidate_records
        WHERE batch_id = ?
        ORDER BY line_number, candidate_record_id
        """,
        (batch_id,),
    ).fetchall()


def _merge_fact(
    connection: sqlite3.Connection,
    record: sqlite3.Row,
    *,
    timestamp: str,
    counters: _MergeCounters,
) -> None:
    payload = _payload_from_record(record)
    fact_type = _clean_text(payload.get("fact_type"))
    entity_name = _clean_text(payload.get("entity_name"))
    canonical_entity_name = normalize_name(entity_name)
    property_name = _clean_text(payload.get("property_name"))
    property_key = normalize_name(property_name)
    property_value = _clean_text(payload.get("property_value"))
    normalized_property_value = normalize_value(property_value)
    fact_identity_hash = _stable_hash(
        [
            "fact",
            canonical_entity_name,
            property_key,
            normalized_property_value,
        ]
    )

    fact = _load_fact_by_hash(connection, fact_identity_hash)
    if fact is None:
        fact_id = next_id(connection, "facts", "fact_id", "FACT")
        connection.execute(
            """
            INSERT INTO facts (
                fact_id,
                fact_identity_hash,
                fact_type,
                entity_name,
                canonical_entity_name,
                property_name,
                property_value,
                normalized_property_value,
                assertion_type,
                confidence,
                status,
                first_candidate_record_id,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                fact_id,
                fact_identity_hash,
                fact_type,
                entity_name,
                canonical_entity_name,
                property_name,
                property_value,
                normalized_property_value,
                record["assertion_type"],
                record["confidence"],
                _status_for_assertion(record["assertion_type"]),
                record["candidate_record_id"],
                timestamp,
                timestamp,
            ),
        )
        counters.facts_created += 1
        fact = _load_fact_by_id(connection, fact_id)
    else:
        counters.facts_existing += 1

    if fact is None:
        raise MergeError(f"Fact could not be loaded after merge: {fact_identity_hash}.")

    evidence_created = _ensure_fact_evidence(connection, fact["fact_id"], record, timestamp)
    if evidence_created:
        _touch_fact(connection, fact["fact_id"], timestamp)

    _ensure_fact_conflicts(
        connection,
        fact,
        property_key=property_key,
        timestamp=timestamp,
        counters=counters,
    )


def _merge_relation(
    connection: sqlite3.Connection,
    record: sqlite3.Row,
    *,
    timestamp: str,
    counters: _MergeCounters,
) -> None:
    payload = _payload_from_record(record)
    source_entity = _clean_text(payload.get("source_entity"))
    canonical_source_entity = normalize_name(source_entity)
    relation_type = _clean_text(payload.get("relation_type"))
    relation_type_key = normalize_name(relation_type)
    target_entity = _clean_text(payload.get("target_entity"))
    canonical_target_entity = normalize_name(target_entity)
    relation_identity_hash = _stable_hash(
        [
            "relation",
            canonical_source_entity,
            relation_type_key,
            canonical_target_entity,
        ]
    )

    relation = _load_relation_by_hash(connection, relation_identity_hash)
    if relation is None:
        relation_id = next_id(connection, "relations", "relation_id", "REL")
        connection.execute(
            """
            INSERT INTO relations (
                relation_id,
                relation_identity_hash,
                source_entity,
                canonical_source_entity,
                relation_type,
                target_entity,
                canonical_target_entity,
                assertion_type,
                confidence,
                status,
                first_candidate_record_id,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                relation_id,
                relation_identity_hash,
                source_entity,
                canonical_source_entity,
                relation_type,
                target_entity,
                canonical_target_entity,
                record["assertion_type"],
                record["confidence"],
                _status_for_assertion(record["assertion_type"]),
                record["candidate_record_id"],
                timestamp,
                timestamp,
            ),
        )
        counters.relations_created += 1
        relation = _load_relation_by_id(connection, relation_id)
    else:
        counters.relations_existing += 1

    if relation is None:
        raise MergeError(f"Relation could not be loaded after merge: {relation_identity_hash}.")

    evidence_created = _ensure_relation_evidence(
        connection,
        relation["relation_id"],
        record,
        timestamp,
    )
    if evidence_created:
        _touch_relation(connection, relation["relation_id"], timestamp)


def _ensure_fact_evidence(
    connection: sqlite3.Connection,
    fact_id: str,
    record: sqlite3.Row,
    timestamp: str,
) -> bool:
    row = connection.execute(
        """
        SELECT fact_evidence_id
        FROM fact_evidence
        WHERE fact_id = ? AND candidate_record_id = ?
        """,
        (fact_id, record["candidate_record_id"]),
    ).fetchone()
    if row is not None:
        return False

    connection.execute(
        """
        INSERT INTO fact_evidence (
            fact_evidence_id,
            fact_id,
            candidate_record_id,
            source_revision_id,
            chunk_id,
            fragment_id,
            evidence_text,
            evidence_text_hash,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            next_id(connection, "fact_evidence", "fact_evidence_id", "FEV"),
            fact_id,
            record["candidate_record_id"],
            record["source_revision_id"],
            record["chunk_id"],
            record["fragment_id"],
            record["evidence_text"],
            _text_hash(record["evidence_text"]),
            timestamp,
        ),
    )
    return True


def _ensure_relation_evidence(
    connection: sqlite3.Connection,
    relation_id: str,
    record: sqlite3.Row,
    timestamp: str,
) -> bool:
    row = connection.execute(
        """
        SELECT relation_evidence_id
        FROM relation_evidence
        WHERE relation_id = ? AND candidate_record_id = ?
        """,
        (relation_id, record["candidate_record_id"]),
    ).fetchone()
    if row is not None:
        return False

    connection.execute(
        """
        INSERT INTO relation_evidence (
            relation_evidence_id,
            relation_id,
            candidate_record_id,
            source_revision_id,
            chunk_id,
            fragment_id,
            evidence_text,
            evidence_text_hash,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            next_id(connection, "relation_evidence", "relation_evidence_id", "REV"),
            relation_id,
            record["candidate_record_id"],
            record["source_revision_id"],
            record["chunk_id"],
            record["fragment_id"],
            record["evidence_text"],
            _text_hash(record["evidence_text"]),
            timestamp,
        ),
    )
    return True


def _ensure_fact_conflicts(
    connection: sqlite3.Connection,
    fact: sqlite3.Row,
    *,
    property_key: str,
    timestamp: str,
    counters: _MergeCounters,
) -> None:
    rows = connection.execute(
        """
        SELECT
            fact_id,
            entity_name,
            canonical_entity_name,
            property_name,
            property_value,
            normalized_property_value
        FROM facts
        WHERE canonical_entity_name = ?
          AND fact_id <> ?
        ORDER BY fact_id
        """,
        (fact["canonical_entity_name"], fact["fact_id"]),
    ).fetchall()

    for other in rows:
        if normalize_name(other["property_name"]) != property_key:
            continue
        if other["normalized_property_value"] == fact["normalized_property_value"]:
            continue
        _ensure_different_value_conflict(
            connection,
            fact,
            other,
            property_key=property_key,
            timestamp=timestamp,
            counters=counters,
        )


def _ensure_different_value_conflict(
    connection: sqlite3.Connection,
    left: sqlite3.Row,
    right: sqlite3.Row,
    *,
    property_key: str,
    timestamp: str,
    counters: _MergeCounters,
) -> None:
    ordered = sorted(
        (left, right),
        key=lambda row: (row["normalized_property_value"], row["fact_id"]),
    )
    left_fact = ordered[0]
    right_fact = ordered[1]
    conflict_key_hash = _stable_hash(
        [
            "conflict",
            "different_values_same_property",
            left_fact["canonical_entity_name"],
            property_key,
            left_fact["normalized_property_value"],
            right_fact["normalized_property_value"],
        ]
    )

    existing = connection.execute(
        """
        SELECT conflict_id
        FROM conflicts
        WHERE conflict_key_hash = ?
        """,
        (conflict_key_hash,),
    ).fetchone()
    if existing is None:
        connection.execute(
            """
            INSERT INTO conflicts (
                conflict_id,
                conflict_key_hash,
                conflict_type,
                entity_name,
                canonical_entity_name,
                property_name,
                left_fact_id,
                right_fact_id,
                left_value,
                right_value,
                status,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                next_id(connection, "conflicts", "conflict_id", "CONFLICT"),
                conflict_key_hash,
                "different_values_same_property",
                left_fact["entity_name"],
                left_fact["canonical_entity_name"],
                left_fact["property_name"],
                left_fact["fact_id"],
                right_fact["fact_id"],
                left_fact["property_value"],
                right_fact["property_value"],
                "open",
                timestamp,
                timestamp,
            ),
        )
        counters.count_created_conflict(conflict_key_hash)
    else:
        counters.count_existing_conflict(conflict_key_hash)

    connection.execute(
        """
        UPDATE facts
        SET status = ?,
            updated_at = ?
        WHERE fact_id IN (?, ?)
          AND status <> ?
        """,
        (
            "conflicted",
            timestamp,
            left_fact["fact_id"],
            right_fact["fact_id"],
            "conflicted",
        ),
    )


def _load_fact_by_hash(connection: sqlite3.Connection, fact_identity_hash: str) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT *
        FROM facts
        WHERE fact_identity_hash = ?
        """,
        (fact_identity_hash,),
    ).fetchone()


def _load_fact_by_id(connection: sqlite3.Connection, fact_id: str) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT *
        FROM facts
        WHERE fact_id = ?
        """,
        (fact_id,),
    ).fetchone()


def _load_relation_by_hash(
    connection: sqlite3.Connection,
    relation_identity_hash: str,
) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT *
        FROM relations
        WHERE relation_identity_hash = ?
        """,
        (relation_identity_hash,),
    ).fetchone()


def _load_relation_by_id(connection: sqlite3.Connection, relation_id: str) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT *
        FROM relations
        WHERE relation_id = ?
        """,
        (relation_id,),
    ).fetchone()


def _touch_fact(connection: sqlite3.Connection, fact_id: str, timestamp: str) -> None:
    connection.execute(
        """
        UPDATE facts
        SET updated_at = ?
        WHERE fact_id = ?
        """,
        (timestamp, fact_id),
    )


def _touch_relation(connection: sqlite3.Connection, relation_id: str, timestamp: str) -> None:
    connection.execute(
        """
        UPDATE relations
        SET updated_at = ?
        WHERE relation_id = ?
        """,
        (timestamp, relation_id),
    )


def _payload_from_record(record: sqlite3.Row) -> dict[str, Any]:
    try:
        payload = json.loads(record["payload_json"])
    except json.JSONDecodeError as exc:
        raise MergeError(
            f"Candidate record has invalid payload_json: {record['candidate_record_id']}."
        ) from exc
    if not isinstance(payload, dict):
        raise MergeError(
            f"Candidate record payload_json is not an object: {record['candidate_record_id']}."
        )
    return payload


def _status_for_assertion(assertion_type: str) -> str:
    if assertion_type in {"explicit", "observed"}:
        return "active"
    if assertion_type == "inferred":
        return "inferred"
    if assertion_type == "ambiguous":
        return "pending_review"
    return "pending_review"


def normalize_name(value: Any) -> str:
    return normalize_value(value).lower()


def normalize_value(value: Any) -> str:
    return _WHITESPACE_RE.sub(" ", _clean_text(value)).strip()


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _stable_hash(payload: list[str]) -> str:
    data = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


_WHITESPACE_RE = re.compile(r"\s+")
