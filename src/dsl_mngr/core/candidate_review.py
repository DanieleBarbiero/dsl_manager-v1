from __future__ import annotations

import json
import re
import sqlite3
import unicodedata
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from dsl_mngr.core.candidate_import import persist_temporal_candidate_details
from dsl_mngr.core.candidate_validation import (
    optional_text,
    validate_candidate_payload,
    value_as_text,
)
from dsl_mngr.core.config import load_config
from dsl_mngr.core.canonical import (
    canonical_json_artifact_v1,
    canonical_json_v1,
    canonical_sha256_v1,
)
from dsl_mngr.core.database import open_database, resolve_database_settings
from dsl_mngr.core.runs import next_id, timestamp_now, validate_database_migrations
from dsl_mngr.core.temporal import TemporalError, materialize_temporal_interval


Clock = Callable[[], datetime]
FaultHook = Callable[[str], None]
_ALLOWED_OUTCOMES = {"confirmed", "rejected", "superseded"}


class CandidateReviewError(RuntimeError):
    def __init__(self, message: str, *, reason: str, exit_code: int = 2) -> None:
        super().__init__(message)
        self.reason = reason
        self.exit_code = exit_code


class CandidateReviewConflict(CandidateReviewError):
    def __init__(self, message: str, *, reason: str) -> None:
        super().__init__(message, reason=reason, exit_code=4)


@dataclass(frozen=True)
class ReviewResult:
    decision_id: str
    subject_type: str
    subject_id: str
    outcome: str
    reason: str
    previous_head_decision_id: str | None
    current_head_decision_id: str
    idempotency_key: str
    request_payload_hash: str
    semantic_payload_hash: str
    action: str
    reconciliation_id: str | None = None
    batch_id: str | None = None
    replacement_candidate_record_id: str | None = None
    replacement_decision_id: str | None = None

    def to_payload(self, *, run_id: str | None = None) -> dict[str, Any]:
        mutations = self.action == "created"
        return {
            "action": self.action,
            "artifact_paths": [],
            "batch_id": self.batch_id,
            "catalog_version": "result_catalog_v1",
            "condition": self.action,
            "counters": {"decisions_created": 1 if mutations else 0},
            "current_head_decision_id": self.current_head_decision_id,
            "decision_id": self.decision_id,
            "exit_code": 0,
            "idempotency_key": self.idempotency_key,
            "mutations": mutations,
            "outcome": self.outcome,
            "previous_head_decision_id": self.previous_head_decision_id,
            "reason": (
                "idempotent_replay"
                if self.action == "replayed"
                else "semantic_noop"
                if self.action == "semantic_noop"
                else self.reason
            ),
            "reconciliation_id": self.reconciliation_id,
            "replacement_candidate_record_id": self.replacement_candidate_record_id,
            "replacement_decision_id": self.replacement_decision_id,
            "request_payload_hash": self.request_payload_hash,
            "retryable": False,
            "run_id": run_id,
            "schema_version": "1",
            "semantic_payload_hash": self.semantic_payload_hash,
            "severity": "info",
            "status": "completed",
            "subject_ids": [self.subject_id],
            "subject_type": self.subject_type,
        }


class CandidateReviewService:
    """Append-only review service for candidate records."""

    def __init__(
        self,
        workspace_dir: str | Path,
        *,
        clock: Clock | None = None,
        fault_hook: FaultHook | None = None,
    ) -> None:
        self.settings = resolve_database_settings(workspace_dir)
        self.clock = clock
        self.fault_hook = fault_hook

    def confirm(
        self,
        candidate_record_id: str,
        *,
        actor_id: str,
        reason: str | None = None,
        expected_head_decision_id: str | None = None,
        idempotency_key: str | None = None,
        actor_type: str = "human",
        policy_id: str | None = None,
        policy_version: str | None = None,
        evidence_refs: Iterable[str] | None = None,
        run_id: str | None = None,
    ) -> ReviewResult:
        return self.review_candidate(
            candidate_record_id,
            outcome="confirmed",
            operation="confirm",
            actor_id=actor_id,
            actor_type=actor_type,
            reason=reason,
            expected_head_decision_id=expected_head_decision_id,
            idempotency_key=idempotency_key,
            policy_id=policy_id,
            policy_version=policy_version,
            evidence_refs=evidence_refs,
            run_id=run_id,
        )

    def reject(
        self,
        candidate_record_id: str,
        *,
        actor_id: str,
        reason: str,
        expected_head_decision_id: str | None = None,
        idempotency_key: str | None = None,
        actor_type: str = "human",
        policy_id: str | None = None,
        policy_version: str | None = None,
        evidence_refs: Iterable[str] | None = None,
        run_id: str | None = None,
    ) -> ReviewResult:
        return self.review_candidate(
            candidate_record_id,
            outcome="rejected",
            operation="reject",
            actor_id=actor_id,
            actor_type=actor_type,
            reason=reason,
            expected_head_decision_id=expected_head_decision_id,
            idempotency_key=idempotency_key,
            policy_id=policy_id,
            policy_version=policy_version,
            evidence_refs=evidence_refs,
            run_id=run_id,
        )

    def review_candidate(
        self,
        candidate_record_id: str,
        *,
        outcome: str,
        operation: str,
        actor_id: str,
        actor_type: str = "human",
        reason: str | None = None,
        expected_head_decision_id: str | None = None,
        idempotency_key: str | None = None,
        policy_id: str | None = None,
        policy_version: str | None = None,
        evidence_refs: Iterable[str] | None = None,
        run_id: str | None = None,
    ) -> ReviewResult:
        actor_id, policy_id, policy_version = _validate_actor(
            actor_type, actor_id, policy_id, policy_version
        )
        normalized_reason = _normalize_reason(reason, outcome=outcome, actor_type=actor_type)
        if outcome not in _ALLOWED_OUTCOMES:
            raise CandidateReviewError(
                f"Unsupported review outcome: {outcome}.",
                reason="review_outcome_invalid",
            )
        timestamp = timestamp_now(self.clock)
        connection = open_database(
            self.settings.database_path,
            enable_wal=self.settings.wal_enabled,
        )
        try:
            validate_database_migrations(connection)
            connection.execute("BEGIN IMMEDIATE")
            try:
                candidate = _require_candidate(connection, candidate_record_id)
                if actor_type == "automatic":
                    _require_automatic_reviewable(candidate)
                refs = _resolve_evidence_refs(connection, candidate, evidence_refs)
                request_payload, semantic_payload = _decision_payloads(
                    candidate=candidate,
                    operation=operation,
                    outcome=outcome,
                    reason=normalized_reason,
                    evidence_refs=refs,
                    actor_type=actor_type,
                    actor_id=actor_id,
                    policy_id=policy_id,
                    policy_version=policy_version,
                    expected_head_decision_id=expected_head_decision_id,
                )
                request_hash = canonical_sha256_v1(request_payload)
                semantic_hash = canonical_sha256_v1(semantic_payload)
                effective_key = _effective_idempotency_key(
                    idempotency_key,
                    actor_type=actor_type,
                    actor_id=actor_id,
                    subject_id=candidate_record_id,
                    operation=operation,
                    request_payload_hash=request_hash,
                    semantic_payload_hash=semantic_hash,
                    candidate_payload_hash=canonical_sha256_v1(
                        _candidate_payload(candidate)
                    ),
                    expected_head_decision_id=expected_head_decision_id,
                    policy_id=policy_id,
                    policy_version=policy_version,
                )

                replay = _load_idempotent_decision(
                    connection, actor_type, actor_id, effective_key
                )
                if replay is not None:
                    result = _replay_result(replay, request_hash)
                    connection.commit()
                    return result

                head = _load_head(connection, "candidate_record", candidate_record_id)
                _require_expected_head(head, expected_head_decision_id)
                if head is not None and head["semantic_payload_hash"] == semantic_hash:
                    connection.commit()
                    return ReviewResult(
                        decision_id=head["decision_id"],
                        subject_type="candidate_record",
                        subject_id=candidate_record_id,
                        outcome=head["outcome"],
                        reason=normalized_reason,
                        previous_head_decision_id=head["decision_id"],
                        current_head_decision_id=head["decision_id"],
                        idempotency_key=effective_key,
                        request_payload_hash=request_hash,
                        semantic_payload_hash=semantic_hash,
                        action="semantic_noop",
                    )

                decision_id = _insert_decision(
                    connection,
                    candidate_record_id=candidate_record_id,
                    actor_type=actor_type,
                    actor_id=actor_id,
                    outcome=outcome,
                    reason=normalized_reason,
                    run_id=run_id,
                    timestamp=timestamp,
                    previous_head=head,
                    expected_head_decision_id=expected_head_decision_id,
                    idempotency_key=effective_key,
                    request_payload=request_payload,
                    semantic_payload=semantic_payload,
                    evidence_refs=refs,
                    policy_id=policy_id,
                    policy_version=policy_version,
                )
                if outcome == "confirmed":
                    _materialize_temporal_candidate(
                        connection,
                        candidate_record_id=candidate_record_id,
                        decision_id=decision_id,
                        timestamp=timestamp,
                        max_intervals_per_subject=int(
                            load_config(self.settings.workspace_dir)["temporal"]
                            ["max_intervals_per_subject"]
                        ),
                    )
                reconciliation_id = None
                if head is not None and head["outcome"] == "confirmed" and outcome != "confirmed":
                    reconciliation_id = _open_reconciliation_if_materialized(
                        connection,
                        candidate_record_id=candidate_record_id,
                        replacement_candidate_record_id=None,
                        decision_id=decision_id,
                        reason="review_decision_superseded",
                        timestamp=timestamp,
                    )
                _fault(self.fault_hook, "before_commit")
                connection.commit()
                return ReviewResult(
                    decision_id=decision_id,
                    subject_type="candidate_record",
                    subject_id=candidate_record_id,
                    outcome=outcome,
                    reason=normalized_reason,
                    previous_head_decision_id=head["decision_id"] if head else None,
                    current_head_decision_id=decision_id,
                    idempotency_key=effective_key,
                    request_payload_hash=request_hash,
                    semantic_payload_hash=semantic_hash,
                    action="created",
                    reconciliation_id=reconciliation_id,
                )
            except Exception:
                connection.rollback()
                raise
        finally:
            connection.close()

    def correct(
        self,
        candidate_record_id: str,
        *,
        corrected_payload: dict[str, Any],
        actor_id: str,
        reason: str,
        expected_head_decision_id: str | None = None,
        idempotency_key: str | None = None,
        evidence_refs: Iterable[str] | None = None,
        run_id: str | None = None,
    ) -> ReviewResult:
        actor_id, _, _ = _validate_actor("human", actor_id, None, None)
        normalized_reason = _normalize_reason(reason, outcome="superseded", actor_type="human")
        timestamp = timestamp_now(self.clock)
        connection = open_database(
            self.settings.database_path,
            enable_wal=self.settings.wal_enabled,
        )
        try:
            validate_database_migrations(connection)
            connection.execute("BEGIN IMMEDIATE")
            try:
                original = _require_candidate(connection, candidate_record_id)
                refs = _resolve_evidence_refs_from_payload(
                    connection, corrected_payload, evidence_refs
                )
                request_payload, semantic_payload = _correction_payloads(
                    original=original,
                    corrected_payload=corrected_payload,
                    reason=normalized_reason,
                    evidence_refs=refs,
                    actor_id=actor_id,
                    expected_head_decision_id=expected_head_decision_id,
                )
                request_hash = canonical_sha256_v1(request_payload)
                semantic_hash = canonical_sha256_v1(semantic_payload)
                effective_key = _effective_idempotency_key(
                    idempotency_key,
                    actor_type="human",
                    actor_id=actor_id,
                    subject_id=candidate_record_id,
                    operation="correct",
                    request_payload_hash=request_hash,
                    semantic_payload_hash=semantic_hash,
                    candidate_payload_hash=canonical_sha256_v1(corrected_payload),
                    expected_head_decision_id=expected_head_decision_id,
                    policy_id=None,
                    policy_version=None,
                )
                replay = _load_idempotent_decision(
                    connection, "human", actor_id, effective_key
                )
                if replay is not None:
                    result = _correction_replay_result(connection, replay, request_hash)
                    connection.commit()
                    return result

                failure = validate_candidate_payload(connection, corrected_payload)
                if failure is not None:
                    raise CandidateReviewError(
                        failure.message,
                        reason=failure.reason,
                        exit_code=3,
                    )
                if _has_lineage_child(connection, candidate_record_id):
                    raise CandidateReviewConflict(
                        f"Candidate is not the current correction leaf: {candidate_record_id}.",
                        reason="correction_leaf_conflict",
                    )
                head = _load_head(connection, "candidate_record", candidate_record_id)
                _require_expected_head(head, expected_head_decision_id)

                superseded_decision_id = _insert_decision(
                    connection,
                    candidate_record_id=candidate_record_id,
                    actor_type="human",
                    actor_id=actor_id,
                    outcome="superseded",
                    reason=normalized_reason,
                    run_id=run_id,
                    timestamp=timestamp,
                    previous_head=head,
                    expected_head_decision_id=expected_head_decision_id,
                    idempotency_key=effective_key,
                    request_payload=request_payload,
                    semantic_payload=semantic_payload,
                    evidence_refs=refs,
                    policy_id=None,
                    policy_version=None,
                )
                _fault(self.fault_hook, "after_original_decision")

                correction_id = next_id(
                    connection, "candidate_corrections", "correction_id", "CCORR"
                )
                correction_group_id = next_id(
                    connection,
                    "candidate_corrections",
                    "correction_group_id",
                    "CORR",
                )
                effective_run_id = run_id or str(original["run_id"])
                batch_id = next_id(connection, "candidate_batches", "batch_id", "CBATCH")
                connection.execute(
                    """
                    INSERT INTO candidate_batches (
                        batch_id, run_id, input_path, origin_type, origin_ref,
                        total_records, accepted_count, rejected_count, status,
                        created_at, updated_at
                    )
                    VALUES (?, ?, NULL, 'human_correction', ?, 1, 1, 0,
                            'completed', ?, ?)
                    """,
                    (
                        batch_id,
                        effective_run_id,
                        f"review://{correction_group_id}",
                        timestamp,
                        timestamp,
                    ),
                )
                _fault(self.fault_hook, "after_batch")

                replacement_id = next_id(
                    connection, "candidate_records", "candidate_record_id", "CREC"
                )
                _insert_replacement_candidate(
                    connection,
                    candidate_record_id=replacement_id,
                    batch_id=batch_id,
                    run_id=effective_run_id,
                    payload=corrected_payload,
                    supersedes_candidate_record_id=candidate_record_id,
                    timestamp=timestamp,
                )
                if corrected_payload.get("record_type") == "temporal_interval":
                    persist_temporal_candidate_details(
                        connection,
                        replacement_id,
                        corrected_payload,
                    )
                lineage = connection.execute(
                    """
                    SELECT root_candidate_record_id
                    FROM candidate_lineage
                    WHERE candidate_record_id = ?
                    """,
                    (candidate_record_id,),
                ).fetchone()
                if lineage is None:
                    raise CandidateReviewError(
                        f"Candidate lineage not found: {candidate_record_id}.",
                        reason="candidate_lineage_missing",
                    )
                connection.execute(
                    """
                    INSERT INTO candidate_lineage (
                        candidate_record_id, root_candidate_record_id,
                        parent_candidate_record_id, correction_group_id
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        replacement_id,
                        lineage["root_candidate_record_id"],
                        candidate_record_id,
                        correction_group_id,
                    ),
                )
                delta = _payload_delta(_candidate_payload(original), corrected_payload)
                connection.execute(
                    """
                    INSERT INTO candidate_corrections (
                        correction_id, correction_group_id,
                        original_candidate_record_id, replacement_candidate_record_id,
                        delta_json, correction_evidence_refs_json, reason, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        correction_id,
                        correction_group_id,
                        candidate_record_id,
                        replacement_id,
                        canonical_json_v1(delta),
                        canonical_json_v1(list(refs)),
                        normalized_reason,
                        timestamp,
                    ),
                )
                _fault(self.fault_hook, "after_replacement")

                replacement_request, replacement_semantic = _decision_payloads(
                    candidate=_require_candidate(connection, replacement_id),
                    operation="correct_replacement_confirm",
                    outcome="confirmed",
                    reason=normalized_reason,
                    evidence_refs=refs,
                    actor_type="human",
                    actor_id=actor_id,
                    policy_id=None,
                    policy_version=None,
                    expected_head_decision_id=None,
                )
                replacement_decision_id = _insert_decision(
                    connection,
                    candidate_record_id=replacement_id,
                    actor_type="human",
                    actor_id=actor_id,
                    outcome="confirmed",
                    reason=normalized_reason,
                    run_id=effective_run_id,
                    timestamp=timestamp,
                    previous_head=None,
                    expected_head_decision_id=None,
                    idempotency_key=f"{effective_key}:replacement",
                    request_payload=replacement_request,
                    semantic_payload=replacement_semantic,
                    evidence_refs=refs,
                    policy_id=None,
                    policy_version=None,
                )
                _materialize_temporal_candidate(
                    connection,
                    candidate_record_id=replacement_id,
                    decision_id=replacement_decision_id,
                    timestamp=timestamp,
                    max_intervals_per_subject=int(
                        load_config(self.settings.workspace_dir)["temporal"]
                        ["max_intervals_per_subject"]
                    ),
                )
                reconciliation_id = _open_reconciliation_if_materialized(
                    connection,
                    candidate_record_id=candidate_record_id,
                    replacement_candidate_record_id=replacement_id,
                    decision_id=superseded_decision_id,
                    reason="candidate_corrected",
                    timestamp=timestamp,
                )
                _fault(self.fault_hook, "before_commit")
                connection.commit()
                return ReviewResult(
                    decision_id=superseded_decision_id,
                    subject_type="candidate_record",
                    subject_id=candidate_record_id,
                    outcome="superseded",
                    reason=normalized_reason,
                    previous_head_decision_id=head["decision_id"] if head else None,
                    current_head_decision_id=superseded_decision_id,
                    idempotency_key=effective_key,
                    request_payload_hash=request_hash,
                    semantic_payload_hash=semantic_hash,
                    action="created",
                    reconciliation_id=reconciliation_id,
                    batch_id=batch_id,
                    replacement_candidate_record_id=replacement_id,
                    replacement_decision_id=replacement_decision_id,
                )
            except Exception:
                connection.rollback()
                raise
        finally:
            connection.close()

    def list_candidates(self, *, outcome: str = "pending") -> list[dict[str, Any]]:
        if outcome not in {"pending", *_ALLOWED_OUTCOMES}:
            raise CandidateReviewError(
                f"Unsupported review list outcome: {outcome}.",
                reason="review_outcome_invalid",
            )
        connection = open_database(
            self.settings.database_path, enable_wal=self.settings.wal_enabled
        )
        try:
            validate_database_migrations(connection)
            rows = connection.execute(
                """
                SELECT
                    cr.candidate_record_id, cr.batch_id, cr.candidate_id,
                    cr.record_type, cr.assertion_type, cr.confidence,
                    h.decision_id, rd.outcome,
                    CASE WHEN child.candidate_record_id IS NULL THEN 1 ELSE 0 END AS is_leaf
                FROM candidate_records cr
                LEFT JOIN review_subject_heads h
                  ON h.subject_type = 'candidate_record'
                 AND h.subject_id = cr.candidate_record_id
                LEFT JOIN review_decisions rd ON rd.decision_id = h.decision_id
                LEFT JOIN candidate_lineage child
                  ON child.parent_candidate_record_id = cr.candidate_record_id
                WHERE (? = 'pending' AND h.decision_id IS NULL)
                   OR (? <> 'pending' AND rd.outcome = ?)
                ORDER BY cr.candidate_record_id
                """,
                (outcome, outcome, outcome),
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            connection.close()

    def show_candidate(self, candidate_record_id: str) -> dict[str, Any]:
        connection = open_database(
            self.settings.database_path, enable_wal=self.settings.wal_enabled
        )
        try:
            validate_database_migrations(connection)
            candidate = _require_candidate(connection, candidate_record_id)
            lineage = connection.execute(
                """
                SELECT * FROM candidate_lineage WHERE candidate_record_id = ?
                """,
                (candidate_record_id,),
            ).fetchone()
            decisions = connection.execute(
                """
                SELECT * FROM review_decisions
                WHERE subject_type = 'candidate_record' AND subject_id = ?
                ORDER BY created_at, decision_id
                """,
                (candidate_record_id,),
            ).fetchall()
            materialized = connection.execute(
                """
                SELECT
                    EXISTS(SELECT 1 FROM fact_evidence WHERE candidate_record_id = ?) AS fact_support,
                    EXISTS(SELECT 1 FROM relation_evidence WHERE candidate_record_id = ?) AS relation_support,
                    EXISTS(SELECT 1 FROM effective_fact_evidence WHERE candidate_record_id = ?) AS effective_fact_support,
                    EXISTS(SELECT 1 FROM effective_relation_evidence WHERE candidate_record_id = ?) AS effective_relation_support
                """,
                (candidate_record_id,) * 4,
            ).fetchone()
            return {
                "candidate": {**dict(candidate), "payload": _candidate_payload(candidate)},
                "decisions": [dict(row) for row in decisions],
                "lineage": dict(lineage) if lineage else None,
                "support": dict(materialized),
            }
        finally:
            connection.close()


def write_review_report(path: str | Path, payload: dict[str, Any]) -> None:
    Path(path).write_text(canonical_json_artifact_v1(payload), encoding="utf-8", newline="\n")


def _validate_actor(
    actor_type: str,
    actor_id: str | None,
    policy_id: str | None,
    policy_version: str | None,
) -> tuple[str, str | None, str | None]:
    normalized_actor_id = _clean_identifier(actor_id)
    if not normalized_actor_id:
        raise CandidateReviewError(
            "A stable human or policy actor id is required.",
            reason="review_actor_required",
        )
    if actor_type == "automatic":
        normalized_policy_id = _clean_identifier(policy_id)
        normalized_policy_version = _clean_identifier(policy_version)
        if not normalized_policy_id or not normalized_policy_version:
            raise CandidateReviewError(
                "Automatic review requires policy_id and policy_version.",
                reason="review_policy_required",
            )
        return normalized_actor_id, normalized_policy_id, normalized_policy_version
    if actor_type != "human":
        raise CandidateReviewError(
            f"Unsupported review actor type: {actor_type}.",
            reason="review_actor_type_invalid",
        )
    if policy_id is not None or policy_version is not None:
        raise CandidateReviewError(
            "Human review must not declare an automatic policy.",
            reason="review_policy_invalid",
        )
    return normalized_actor_id, None, None


def _normalize_reason(reason: str | None, *, outcome: str, actor_type: str) -> str:
    normalized = _normalize_text(reason or "")
    if not normalized and outcome == "confirmed":
        return "human_confirmed" if actor_type == "human" else "policy_confirmed"
    if not normalized:
        raise CandidateReviewError(
            "A non-empty reason is required for reject and correct.",
            reason="review_reason_required",
        )
    return normalized


def _require_candidate(connection: sqlite3.Connection, candidate_record_id: str) -> sqlite3.Row:
    row = connection.execute(
        "SELECT * FROM candidate_records WHERE candidate_record_id = ?",
        (candidate_record_id,),
    ).fetchone()
    if row is None:
        raise CandidateReviewError(
            f"Candidate record not found: {candidate_record_id}.",
            reason="candidate_not_found",
        )
    return row


def _candidate_payload(candidate: sqlite3.Row) -> dict[str, Any]:
    try:
        payload = json.loads(candidate["payload_json"])
    except (TypeError, json.JSONDecodeError) as exc:
        raise CandidateReviewError(
            f"Candidate payload is invalid: {candidate['candidate_record_id']}.",
            reason="candidate_payload_invalid",
        ) from exc
    if not isinstance(payload, dict):
        raise CandidateReviewError(
            f"Candidate payload is not an object: {candidate['candidate_record_id']}.",
            reason="candidate_payload_invalid",
        )
    return payload


def _require_automatic_reviewable(candidate: sqlite3.Row) -> None:
    payload = _candidate_payload(candidate)
    if candidate["record_type"] == "temporal_interval":
        raise CandidateReviewConflict(
            "Temporal candidates require common human review in schema 2.",
            reason="automatic_review_not_allowed",
        )
    rule_id = _clean_identifier(payload.get("rule_id"))
    rule_version = _clean_identifier(payload.get("rule_version"))
    producer_type = _clean_identifier(payload.get("producer_type"))
    if producer_type != "deterministic_rule" or not rule_id or not rule_version:
        raise CandidateReviewConflict(
            "Automatic review is allowed only for a named, versioned deterministic rule.",
            reason="automatic_review_not_allowed",
        )
    if candidate["assertion_type"] not in {"explicit", "observed"}:
        raise CandidateReviewConflict(
            "Automatic review cannot confirm an interpretive or ambiguous candidate.",
            reason="automatic_review_not_allowed",
        )


def _resolve_evidence_refs(
    connection: sqlite3.Connection,
    candidate: sqlite3.Row,
    evidence_refs: Iterable[str] | None,
) -> tuple[str, ...]:
    supplied = tuple(evidence_refs or ())
    if not supplied:
        if candidate["record_type"] == "temporal_interval":
            payload = _candidate_payload(candidate)
            supplied = tuple(str(value) for value in payload.get("temporal_evidence_ids", ()))
        else:
            supplied = tuple(
                str(value)
                for value in (candidate["chunk_id"], candidate["fragment_id"])
                if value is not None
            )
    return _validate_evidence_refs(connection, supplied)


def _resolve_evidence_refs_from_payload(
    connection: sqlite3.Connection,
    payload: dict[str, Any],
    evidence_refs: Iterable[str] | None,
) -> tuple[str, ...]:
    supplied = tuple(evidence_refs or ())
    if not supplied:
        if payload.get("record_type") == "temporal_interval":
            supplied = tuple(str(value) for value in payload.get("temporal_evidence_ids", ()))
        else:
            supplied = tuple(
                str(value)
                for value in (payload.get("chunk_id"), payload.get("fragment_id"))
                if optional_text(value) is not None
            )
    return _validate_evidence_refs(connection, supplied)


def _validate_evidence_refs(
    connection: sqlite3.Connection,
    evidence_refs: Iterable[str],
) -> tuple[str, ...]:
    refs = tuple(dict.fromkeys(_clean_identifier(value) for value in evidence_refs))
    refs = tuple(value for value in refs if value)
    for evidence_ref in refs:
        if evidence_ref.startswith("human://"):
            continue
        exists = connection.execute(
            """
            SELECT EXISTS(SELECT 1 FROM chunks WHERE chunk_id = ?)
                OR EXISTS(SELECT 1 FROM source_fragments WHERE fragment_id = ?)
                OR EXISTS(
                    SELECT 1 FROM raw_temporal_evidence WHERE temporal_evidence_id = ?
                )
            """,
            (evidence_ref, evidence_ref, evidence_ref),
        ).fetchone()[0]
        if not exists:
            raise CandidateReviewError(
                f"Evidence reference not found: {evidence_ref}.",
                reason="review_evidence_not_found",
            )
    return refs


def _decision_payloads(
    *,
    candidate: sqlite3.Row,
    operation: str,
    outcome: str,
    reason: str,
    evidence_refs: tuple[str, ...],
    actor_type: str,
    actor_id: str,
    policy_id: str | None,
    policy_version: str | None,
    expected_head_decision_id: str | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    subject = {
        "subject_id": candidate["candidate_record_id"],
        "subject_type": "candidate_record",
    }
    policy = {"policy_id": policy_id, "policy_version": policy_version}
    semantic = {
        "candidate_payload": _candidate_payload(candidate),
        "evidence_refs": list(evidence_refs),
        "outcome": outcome,
        "policy": policy,
        "subject": subject,
    }
    request = {
        "actor": {"actor_id": actor_id, "actor_type": actor_type},
        "candidate_payload": _candidate_payload(candidate),
        "evidence_refs": list(evidence_refs),
        "expected_head_decision_id": expected_head_decision_id,
        "operation": operation,
        "outcome": outcome,
        "policy": policy,
        "reason": reason,
        "subject": subject,
    }
    return request, semantic


def _correction_payloads(
    *,
    original: sqlite3.Row,
    corrected_payload: dict[str, Any],
    reason: str,
    evidence_refs: tuple[str, ...],
    actor_id: str,
    expected_head_decision_id: str | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    subject = {
        "subject_id": original["candidate_record_id"],
        "subject_type": "candidate_record",
    }
    semantic = {
        "candidate_payload": corrected_payload,
        "evidence_refs": list(evidence_refs),
        "outcome": "superseded",
        "policy": {"policy_id": None, "policy_version": None},
        "subject": subject,
    }
    request = {
        "actor": {"actor_id": actor_id, "actor_type": "human"},
        "candidate_payload": _candidate_payload(original),
        "correction_delta": _payload_delta(
            _candidate_payload(original), corrected_payload
        ),
        "corrected_payload": corrected_payload,
        "evidence_refs": list(evidence_refs),
        "expected_head_decision_id": expected_head_decision_id,
        "operation": "correct",
        "outcome": "superseded",
        "policy": {"policy_id": None, "policy_version": None},
        "reason": reason,
        "subject": subject,
    }
    return request, semantic


def _effective_idempotency_key(
    supplied: str | None,
    *,
    actor_type: str,
    actor_id: str,
    subject_id: str,
    operation: str,
    request_payload_hash: str,
    semantic_payload_hash: str,
    candidate_payload_hash: str,
    expected_head_decision_id: str | None,
    policy_id: str | None,
    policy_version: str | None,
) -> str:
    normalized = _clean_identifier(supplied)
    if normalized:
        return normalized
    if actor_type == "automatic":
        payload = {
            "actor_id": actor_id,
            "actor_type": actor_type,
            "candidate_payload_hash": candidate_payload_hash,
            "expected_head_decision_id": expected_head_decision_id,
            "operation": operation,
            "policy_id": policy_id,
            "policy_version": policy_version,
            "semantic_payload_hash": semantic_payload_hash,
            "subject_id": subject_id,
            "subject_type": "candidate_record",
        }
        return f"review:{canonical_sha256_v1(payload)}"
    payload = {
        "actor_id": actor_id,
        "actor_type": actor_type,
        "operation": operation,
        "request_payload_hash": request_payload_hash,
        "subject_id": subject_id,
        "subject_type": "candidate_record",
    }
    return f"review:{canonical_sha256_v1(payload)}"


def _load_idempotent_decision(
    connection: sqlite3.Connection,
    actor_type: str,
    actor_id: str,
    idempotency_key: str,
) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT * FROM review_decisions
        WHERE actor_type = ? AND actor_id = ? AND idempotency_key = ?
        """,
        (actor_type, actor_id, idempotency_key),
    ).fetchone()


def _replay_result(row: sqlite3.Row, request_hash: str) -> ReviewResult:
    if row["request_payload_hash"] != request_hash:
        raise CandidateReviewConflict(
            "The idempotency key was already used with a different request payload.",
            reason="idempotency_payload_conflict",
        )
    return ReviewResult(
        decision_id=row["decision_id"],
        subject_type=row["subject_type"],
        subject_id=row["subject_id"],
        outcome=row["outcome"],
        reason=row["reason"],
        previous_head_decision_id=row["supersedes_decision_id"],
        current_head_decision_id=row["decision_id"],
        idempotency_key=row["idempotency_key"],
        request_payload_hash=row["request_payload_hash"],
        semantic_payload_hash=row["semantic_payload_hash"],
        action="replayed",
    )


def _correction_replay_result(
    connection: sqlite3.Connection,
    row: sqlite3.Row,
    request_hash: str,
) -> ReviewResult:
    base = _replay_result(row, request_hash)
    correction = connection.execute(
        """
        SELECT cc.replacement_candidate_record_id, cr.batch_id
        FROM candidate_corrections cc
        JOIN candidate_records cr
          ON cr.candidate_record_id = cc.replacement_candidate_record_id
        WHERE cc.original_candidate_record_id = ?
        """,
        (row["subject_id"],),
    ).fetchone()
    if correction is None:
        raise CandidateReviewError(
            "Correction replay could not locate its replacement candidate.",
            reason="correction_replay_incomplete",
        )
    replacement_head = _load_head(
        connection, "candidate_record", correction["replacement_candidate_record_id"]
    )
    reconciliation = connection.execute(
        """
        SELECT reconciliation_id FROM reconciliation_required
        WHERE subject_type = 'candidate_record' AND subject_id = ?
        ORDER BY reconciliation_id DESC LIMIT 1
        """,
        (row["subject_id"],),
    ).fetchone()
    return ReviewResult(
        **{
            **base.__dict__,
            "batch_id": correction["batch_id"],
            "replacement_candidate_record_id": correction[
                "replacement_candidate_record_id"
            ],
            "replacement_decision_id": (
                replacement_head["decision_id"] if replacement_head else None
            ),
            "reconciliation_id": (
                reconciliation["reconciliation_id"] if reconciliation else None
            ),
        }
    )


def _load_head(
    connection: sqlite3.Connection,
    subject_type: str,
    subject_id: str,
) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT rd.*
        FROM review_subject_heads h
        JOIN review_decisions rd ON rd.decision_id = h.decision_id
        WHERE h.subject_type = ? AND h.subject_id = ?
        """,
        (subject_type, subject_id),
    ).fetchone()


def _require_expected_head(
    head: sqlite3.Row | None,
    expected_head_decision_id: str | None,
) -> None:
    actual = head["decision_id"] if head else None
    if actual != expected_head_decision_id:
        raise CandidateReviewConflict(
            f"Review head conflict: expected {expected_head_decision_id!r}, found {actual!r}.",
            reason="review_head_conflict",
        )


def _insert_decision(
    connection: sqlite3.Connection,
    *,
    candidate_record_id: str,
    actor_type: str,
    actor_id: str,
    outcome: str,
    reason: str,
    run_id: str | None,
    timestamp: str,
    previous_head: sqlite3.Row | None,
    expected_head_decision_id: str | None,
    idempotency_key: str,
    request_payload: dict[str, Any],
    semantic_payload: dict[str, Any],
    evidence_refs: tuple[str, ...],
    policy_id: str | None,
    policy_version: str | None,
) -> str:
    decision_id = next_id(connection, "review_decisions", "decision_id", "RDEC")
    request_hash = canonical_sha256_v1(request_payload)
    semantic_hash = canonical_sha256_v1(semantic_payload)
    connection.execute(
        """
        INSERT INTO review_decisions (
            decision_id, subject_type, subject_id, actor_type, actor_id,
            outcome, reason, run_id, created_at, supersedes_decision_id,
            expected_head_decision_id, idempotency_key,
            request_payload_hash, semantic_payload_hash,
            policy_id, policy_version, request_payload_json, semantic_payload_json
        )
        VALUES (?, 'candidate_record', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            decision_id,
            candidate_record_id,
            actor_type,
            actor_id,
            outcome,
            reason,
            run_id,
            timestamp,
            previous_head["decision_id"] if previous_head else None,
            expected_head_decision_id,
            idempotency_key,
            request_hash,
            semantic_hash,
            policy_id,
            policy_version,
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
        ON CONFLICT(subject_type, subject_id) DO UPDATE SET
            decision_id = excluded.decision_id,
            updated_at = excluded.updated_at
        """,
        (candidate_record_id, decision_id, timestamp),
    )
    return decision_id


def _open_reconciliation_if_materialized(
    connection: sqlite3.Connection,
    *,
    candidate_record_id: str,
    replacement_candidate_record_id: str | None,
    decision_id: str,
    reason: str,
    timestamp: str,
) -> str | None:
    materialized = connection.execute(
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
    if not materialized:
        return None
    existing = connection.execute(
        """
        SELECT reconciliation_id FROM reconciliation_required
        WHERE subject_type = 'candidate_record' AND subject_id = ? AND status = 'open'
        """,
        (candidate_record_id,),
    ).fetchone()
    if existing is not None:
        return str(existing["reconciliation_id"])
    reconciliation_id = next_id(
        connection,
        "reconciliation_required",
        "reconciliation_id",
        "RECON",
    )
    connection.execute(
        """
        INSERT INTO reconciliation_required (
            reconciliation_id, subject_type, subject_id, replacement_subject_id,
            reason, opened_by_decision_id, status, opened_at,
            closed_at, closed_by_run_id
        )
        VALUES (?, 'candidate_record', ?, ?, ?, ?, 'open', ?, NULL, NULL)
        """,
        (
            reconciliation_id,
            candidate_record_id,
            replacement_candidate_record_id,
            reason,
            decision_id,
            timestamp,
        ),
    )
    return reconciliation_id


def _materialize_temporal_candidate(
    connection: sqlite3.Connection,
    *,
    candidate_record_id: str,
    decision_id: str,
    timestamp: str,
    max_intervals_per_subject: int,
) -> None:
    try:
        materialize_temporal_interval(
            connection,
            candidate_record_id=candidate_record_id,
            decision_id=decision_id,
            timestamp=timestamp,
            max_intervals_per_subject=max_intervals_per_subject,
        )
    except TemporalError as exc:
        raise CandidateReviewError(
            str(exc),
            reason=exc.reason,
            exit_code=exc.exit_code,
        ) from exc


def _has_lineage_child(connection: sqlite3.Connection, candidate_record_id: str) -> bool:
    return bool(
        connection.execute(
            """
            SELECT EXISTS(
                SELECT 1 FROM candidate_lineage
                WHERE parent_candidate_record_id = ?
            )
            """,
            (candidate_record_id,),
        ).fetchone()[0]
    )


def _insert_replacement_candidate(
    connection: sqlite3.Connection,
    *,
    candidate_record_id: str,
    batch_id: str,
    run_id: str,
    payload: dict[str, Any],
    supersedes_candidate_record_id: str,
    timestamp: str,
) -> None:
    connection.execute(
        """
        INSERT INTO candidate_records (
            candidate_record_id, batch_id, run_id, line_number,
            candidate_id, record_type, source_revision_id, chunk_id, fragment_id,
            assertion_type, confidence, evidence_text, payload_json, created_at,
            supersedes_candidate_record_id
        )
        VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            candidate_record_id,
            batch_id,
            run_id,
            value_as_text(payload.get("candidate_id")),
            value_as_text(payload.get("record_type")),
            value_as_text(payload.get("source_revision_id")),
            optional_text(payload.get("chunk_id")),
            optional_text(payload.get("fragment_id")),
            value_as_text(payload.get("assertion_type")),
            value_as_text(payload.get("confidence")),
            value_as_text(payload.get("evidence_text")),
            canonical_json_v1(payload),
            timestamp,
            supersedes_candidate_record_id,
        ),
    )


def _payload_delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    delta: dict[str, Any] = {}
    for key in sorted(set(before) | set(after)):
        old = before.get(key, _MISSING)
        new = after.get(key, _MISSING)
        if old == new:
            continue
        delta[key] = {
            "after": None if new is _MISSING else new,
            "after_present": new is not _MISSING,
            "before": None if old is _MISSING else old,
            "before_present": old is not _MISSING,
        }
    return delta


def _fault(hook: FaultHook | None, point: str) -> None:
    if hook is not None:
        hook(point)


def _clean_identifier(value: Any) -> str:
    return _normalize_text("" if value is None else str(value))


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", value)).strip()


_MISSING = object()
