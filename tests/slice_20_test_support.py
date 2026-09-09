from __future__ import annotations

import sqlite3
from pathlib import Path

from dsl_mngr.core.candidate_review import CandidateReviewService


def confirm_materializable_candidates(
    workspace: Path,
    batch_id: str,
    *,
    actor_id: str = "legacy-test-reviewer",
) -> tuple[str, ...]:
    """Apply the Slice 20 review precondition to legacy merge fixtures."""

    connection = sqlite3.connect(workspace / "workspace.sqlite")
    try:
        rows = connection.execute(
            """
            SELECT candidate_record_id
            FROM candidate_records
            WHERE batch_id = ?
              AND record_type IN ('candidate_fact', 'candidate_relation')
            ORDER BY candidate_record_id
            """,
            (batch_id,),
        ).fetchall()
    finally:
        connection.close()

    service = CandidateReviewService(workspace)
    candidate_record_ids = tuple(str(row[0]) for row in rows)
    for candidate_record_id in candidate_record_ids:
        service.confirm(
            candidate_record_id,
            actor_id=actor_id,
            expected_head_decision_id=None,
            idempotency_key=f"legacy-test:{candidate_record_id}:confirm",
        )
    return candidate_record_ids
