from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from dsl_mngr.core.database import open_database, resolve_database_settings
from dsl_mngr.core.runs import timestamp_now, validate_database_migrations


class ReconciliationError(RuntimeError):
    def __init__(self, message: str, *, reason: str, exit_code: int = 4) -> None:
        super().__init__(message)
        self.reason = reason
        self.exit_code = exit_code


class ReconciliationRequiredError(ReconciliationError):
    def __init__(self, count: int) -> None:
        super().__init__(
            f"reconciliation_required: {count} open reconciliation item(s).",
            reason="reconciliation_required",
        )
        self.count = count


@dataclass(frozen=True)
class ReconciliationResult:
    run_id: str
    processed: int
    closed: int
    pending: int
    supports_removed: int
    reconciliation_ids: tuple[str, ...]

    def to_payload(self) -> dict[str, Any]:
        reason = "replacement_merge_pending" if self.pending else "success"
        return {
            "artifact_paths": [],
            "catalog_version": "result_catalog_v1",
            "condition": "reconcile",
            "counters": {
                "closed": self.closed,
                "pending": self.pending,
                "processed": self.processed,
                "supports_removed": self.supports_removed,
            },
            "exit_code": 4 if self.pending else 0,
            "mutations": self.supports_removed > 0 or self.closed > 0,
            "outcome": None,
            "reason": reason,
            "reconciliation_ids": list(self.reconciliation_ids),
            "retryable": bool(self.pending),
            "run_id": self.run_id,
            "schema_version": "1",
            "severity": "warning" if self.pending else "info",
            "status": "pending" if self.pending else "completed",
            "subject_ids": [],
        }


def ensure_no_open_reconciliation(workspace_dir: str | Path) -> None:
    settings = resolve_database_settings(workspace_dir)
    connection = open_database(
        settings.database_path, enable_wal=settings.wal_enabled
    )
    try:
        validate_database_migrations(connection)
        assert_no_open_reconciliation(connection)
    finally:
        connection.close()


def assert_no_open_reconciliation(connection: sqlite3.Connection) -> None:
    count = int(
        connection.execute(
            "SELECT COUNT(*) FROM reconciliation_required WHERE status = 'open'"
        ).fetchone()[0]
    )
    if count:
        raise ReconciliationRequiredError(count)


def reconcile_required(
    workspace_dir: str | Path,
    *,
    run_id: str,
    reconciliation_id: str | None = None,
    strict: bool = False,
    clock: Any = None,
) -> ReconciliationResult:
    settings = resolve_database_settings(workspace_dir)
    timestamp = timestamp_now(clock)
    connection = open_database(
        settings.database_path, enable_wal=settings.wal_enabled
    )
    try:
        validate_database_migrations(connection)
        connection.execute("BEGIN IMMEDIATE")
        try:
            rows = _load_open_items(connection, reconciliation_id)
            if reconciliation_id is not None and not rows:
                exists = connection.execute(
                    """
                    SELECT status FROM reconciliation_required
                    WHERE reconciliation_id = ?
                    """,
                    (reconciliation_id,),
                ).fetchone()
                if exists is None:
                    raise ReconciliationError(
                        f"Reconciliation item not found: {reconciliation_id}.",
                        reason="reconciliation_not_found",
                        exit_code=2,
                    )
            pending_ids = [
                row["reconciliation_id"]
                for row in rows
                if row["replacement_subject_id"] is not None
                and not _candidate_is_materialized(
                    connection, row["replacement_subject_id"]
                )
            ]
            if strict and pending_ids:
                raise ReconciliationError(
                    "replacement_merge_pending: strict reconciliation rolled back.",
                    reason="replacement_merge_pending",
                )

            supports_removed = 0
            closed = 0
            pending = 0
            ids: list[str] = []
            for row in rows:
                ids.append(row["reconciliation_id"])
                supports_removed += compensate_candidate_support(
                    connection, row["subject_id"], timestamp=timestamp
                )
                replacement = row["replacement_subject_id"]
                if replacement is not None and not _candidate_is_materialized(
                    connection, replacement
                ):
                    pending += 1
                    continue
                _close_item(
                    connection,
                    row["reconciliation_id"],
                    run_id=run_id,
                    timestamp=timestamp,
                )
                closed += 1
            connection.commit()
        except Exception:
            connection.rollback()
            raise
    finally:
        connection.close()

    return ReconciliationResult(
        run_id=run_id,
        processed=len(rows),
        closed=closed,
        pending=pending,
        supports_removed=supports_removed,
        reconciliation_ids=tuple(ids),
    )


def finalize_reconciliation_for_replacement(
    connection: sqlite3.Connection,
    replacement_candidate_record_id: str,
    *,
    run_id: str,
    timestamp: str,
) -> tuple[int, int]:
    rows = connection.execute(
        """
        SELECT reconciliation_id, subject_id
        FROM reconciliation_required
        WHERE status = 'open' AND replacement_subject_id = ?
        ORDER BY reconciliation_id
        """,
        (replacement_candidate_record_id,),
    ).fetchall()
    removed = 0
    for row in rows:
        removed += compensate_candidate_support(
            connection, row["subject_id"], timestamp=timestamp
        )
        _close_item(
            connection,
            row["reconciliation_id"],
            run_id=run_id,
            timestamp=timestamp,
        )
    return len(rows), removed


def compensate_candidate_support(
    connection: sqlite3.Connection,
    candidate_record_id: str,
    *,
    timestamp: str,
) -> int:
    fact_ids = [
        row["fact_id"]
        for row in connection.execute(
            "SELECT fact_id FROM fact_evidence WHERE candidate_record_id = ?",
            (candidate_record_id,),
        ).fetchall()
    ]
    relation_ids = [
        row["relation_id"]
        for row in connection.execute(
            "SELECT relation_id FROM relation_evidence WHERE candidate_record_id = ?",
            (candidate_record_id,),
        ).fetchall()
    ]
    fact_removed = connection.execute(
        "DELETE FROM fact_evidence WHERE candidate_record_id = ?",
        (candidate_record_id,),
    ).rowcount
    relation_removed = connection.execute(
        "DELETE FROM relation_evidence WHERE candidate_record_id = ?",
        (candidate_record_id,),
    ).rowcount
    for fact_id in fact_ids:
        if not connection.execute(
            "SELECT 1 FROM fact_evidence WHERE fact_id = ? LIMIT 1", (fact_id,)
        ).fetchone():
            connection.execute(
                "UPDATE facts SET status = 'unsupported', updated_at = ? WHERE fact_id = ?",
                (timestamp, fact_id),
            )
    for relation_id in relation_ids:
        if not connection.execute(
            "SELECT 1 FROM relation_evidence WHERE relation_id = ? LIMIT 1",
            (relation_id,),
        ).fetchone():
            connection.execute(
                """
                UPDATE relations
                SET status = 'unsupported', updated_at = ?
                WHERE relation_id = ?
                """,
                (timestamp, relation_id),
            )
    return int(fact_removed + relation_removed)


def _load_open_items(
    connection: sqlite3.Connection,
    reconciliation_id: str | None,
) -> list[sqlite3.Row]:
    if reconciliation_id is not None:
        return connection.execute(
            """
            SELECT * FROM reconciliation_required
            WHERE status = 'open' AND reconciliation_id = ?
            ORDER BY reconciliation_id
            """,
            (reconciliation_id,),
        ).fetchall()
    return connection.execute(
        """
        SELECT * FROM reconciliation_required
        WHERE status = 'open'
        ORDER BY reconciliation_id
        """
    ).fetchall()


def _candidate_is_materialized(
    connection: sqlite3.Connection, candidate_record_id: str
) -> bool:
    return bool(
        connection.execute(
            """
            SELECT EXISTS(
                SELECT 1 FROM fact_evidence WHERE candidate_record_id = ?
            ) OR EXISTS(
                SELECT 1 FROM relation_evidence WHERE candidate_record_id = ?
            ) OR EXISTS(
                SELECT 1 FROM temporal_intervals WHERE source_candidate_record_id = ?
            )
            """,
            (candidate_record_id, candidate_record_id, candidate_record_id),
        ).fetchone()[0]
    )


def _close_item(
    connection: sqlite3.Connection,
    reconciliation_id: str,
    *,
    run_id: str,
    timestamp: str,
) -> None:
    connection.execute(
        """
        UPDATE reconciliation_required
        SET status = 'closed', closed_at = ?, closed_by_run_id = ?
        WHERE reconciliation_id = ? AND status = 'open'
        """,
        (timestamp, run_id, reconciliation_id),
    )
