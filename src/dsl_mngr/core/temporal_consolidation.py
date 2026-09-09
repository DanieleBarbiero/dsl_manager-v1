from __future__ import annotations

import hashlib
import json
import re
from calendar import monthrange
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Protocol

from dsl_mngr.core.canonical import canonical_json_v1, canonical_sha256_v1
from dsl_mngr.core.database import open_database, resolve_database_settings, resolve_workspace_path
from dsl_mngr.core.runs import next_id, timestamp_now, validate_database_migrations
from dsl_mngr.core.temporal import (
    Clock,
    TemporalCandidateResult,
    TemporalError,
    TemporalEvidenceResult,
    create_temporal_candidate,
    extract_ooxml_temporal_evidence,
    persist_temporal_evidence_records,
)


CONSOLIDATION_POLICY_ID = "independent_temporal_evidence"
CONSOLIDATION_POLICY_VERSION = "1"
EXTRACTION_VERSION = "1"
_OOXML_SUFFIXES = {".docx", ".pptx", ".xlsx", ".xlsm"}
_TEXT_SUFFIXES = {".txt", ".md", ".markdown", ".sql", ".xml", ".log"}
_DECLARATIVE_KEYS = {
    "applicable_from",
    "applicable_to",
    "competence_date",
    "competence_month",
    "competence_year",
    "date_created",
    "date_modified",
    "date_published",
    "effective_date",
    "effective_from",
    "effective_to",
    "period",
    "valid_from",
    "valid_to",
}
_FROM_KEYS = {"applicable_from", "effective_from", "valid_from"}
_TO_KEYS = {"applicable_to", "effective_to", "valid_to"}
_TEMPORAL_VALUE = (
    r"(?:D:)?\d{4}(?:-?\d{2}(?:-?\d{2})?)?"
    r"(?:T?\d{2}:?\d{2}(?::?\d{2}(?:\.\d+)?)?"
    r"(?:Z|[+-]\d{2}:?\d{2}|[+-]\d{2}'\d{2}')?)?"
)


@dataclass(frozen=True)
class NormalizedTemporalInterval:
    start: str | None
    end: str | None
    original_precision: str
    timezone_status: str
    timezone_value: str | None
    bounds_semantics: str

    def signature(self) -> str:
        return canonical_sha256_v1(self.to_payload())

    def to_payload(self) -> dict[str, Any]:
        return {
            "bounds_semantics": self.bounds_semantics,
            "end": self.end,
            "original_precision": self.original_precision,
            "start": self.start,
            "timezone_status": self.timezone_status,
            "timezone_value": self.timezone_value,
        }


@dataclass(frozen=True)
class TemporalConsolidationResult:
    target_subject_type: str
    target_subject_id: str
    group_id: str
    group_hash: str
    assessment: str
    evidence_ids: tuple[str, ...]
    candidate_record_ids: tuple[str, ...]
    conflict_id: str | None


@dataclass(frozen=True)
class TemporalPropagationResult:
    policy: str
    candidate_record_ids: tuple[str, ...]
    conflict_id: str | None


class TemporalAiAdapter(Protocol):
    """Offline boundary: an adapter may propose evidence/candidates, never registry state."""

    def propose(self, request: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]: ...


def extract_temporal_evidence(
    workspace_dir: str | Path,
    *,
    source_revision_id: str,
    target_subject_type: str = "source_revision",
    target_subject_id: str | None = None,
    clock: Clock | None = None,
) -> TemporalEvidenceResult:
    """Extract heterogeneous evidence plus filename and exact registry first_seen_at."""
    settings = resolve_database_settings(workspace_dir)
    target_id = target_subject_id or source_revision_id
    connection = open_database(settings.database_path, enable_wal=settings.wal_enabled)
    try:
        validate_database_migrations(connection)
        revision = connection.execute(
            """
            SELECT sr.source_revision_id, sr.content_hash, sr.file_path,
                   s.first_seen_at
            FROM source_revisions sr
            JOIN sources s ON s.source_id = sr.source_id
            WHERE sr.source_revision_id = ?
            """,
            (source_revision_id,),
        ).fetchone()
    finally:
        connection.close()
    if revision is None:
        raise TemporalError(
            f"Source revision not found: {source_revision_id}.",
            reason="unknown_source_revision",
        )

    path = resolve_workspace_path(settings.workspace_dir, str(revision["file_path"]))
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise TemporalError(
            f"Temporal source cannot be read: {revision['file_path']}.",
            reason="source_read_failed",
        ) from exc
    if hashlib.sha256(data).hexdigest() != str(revision["content_hash"]):
        raise TemporalError(
            f"Source changed after registration: {revision['file_path']}.",
            reason="source_changed_during_read",
        )

    suffix = path.suffix.lower()
    extracted: list[dict[str, Any]] = []
    if suffix == ".pdf":
        extracted.extend(_pdf_records(data, source_revision_id, target_subject_type, target_id))
    elif suffix in {".html", ".htm"}:
        text = data.decode("utf-8", errors="replace")
        extracted.extend(_html_records(text, source_revision_id, target_subject_type, target_id))
    elif suffix in _TEXT_SUFFIXES:
        text = data.decode("utf-8", errors="replace")
        extracted.extend(
            _declared_text_records(
                text,
                suffix=suffix,
                source_revision_id=source_revision_id,
                target_subject_type=target_subject_type,
                target_subject_id=target_id,
            )
        )

    extracted.extend(
        _filename_records(
            path.name,
            source_revision_id,
            target_subject_type,
            target_id,
        )
    )
    extracted.append(
        _evidence_record(
            source_revision_id,
            target_subject_type,
            target_id,
            source_key="sources.first_seen_at",
            source_format="registry_datetime",
            raw_value=str(revision["first_seen_at"]),
            extraction_method="registry_first_seen",
            reliability="low",
            warnings=("operational_observation_not_semantic_validity",),
        )
    )

    secondary = persist_temporal_evidence_records(
        settings.workspace_dir,
        source_revision_id=source_revision_id,
        target_subject_type=target_subject_type,
        target_subject_id=target_id,
        records=extracted,
        clock=clock,
    )
    if suffix not in _OOXML_SUFFIXES:
        return secondary
    primary = extract_ooxml_temporal_evidence(
        settings.workspace_dir,
        source_revision_id=source_revision_id,
        target_subject_type=target_subject_type,
        target_subject_id=target_id,
        clock=clock,
    )
    return TemporalEvidenceResult(
        source_revision_id=source_revision_id,
        evidence_ids=tuple((*primary.evidence_ids, *secondary.evidence_ids)),
        evidence_hashes=tuple((*primary.evidence_hashes, *secondary.evidence_hashes)),
        inserted_count=primary.inserted_count + secondary.inserted_count,
        existing_count=primary.existing_count + secondary.existing_count,
    )


def consolidate_temporal_evidence(
    workspace_dir: str | Path,
    *,
    run_id: str,
    target_subject_type: str,
    target_subject_id: str,
    clock: Clock | None = None,
) -> TemporalConsolidationResult:
    """Group correlated signals and create pending review candidates per proposal."""
    settings = resolve_database_settings(workspace_dir)
    connection = open_database(settings.database_path, enable_wal=settings.wal_enabled)
    try:
        validate_database_migrations(connection)
        rows = connection.execute(
            """
            SELECT rte.*, sr.content_hash
            FROM raw_temporal_evidence rte
            JOIN source_revisions sr
              ON sr.source_revision_id = rte.source_revision_id
            WHERE rte.target_subject_type = ? AND rte.target_subject_id = ?
            ORDER BY rte.evidence_hash, rte.temporal_evidence_id
            """,
            (target_subject_type, target_subject_id),
        ).fetchall()
    finally:
        connection.close()
    if not rows:
        raise TemporalError(
            f"No temporal evidence for {target_subject_type}/{target_subject_id}.",
            reason="temporal_evidence_not_found",
        )

    proposals = _proposals_for_rows(rows)
    member_classes = _classify_members(rows, proposals)
    signatures = sorted(proposals)
    unresolved = any(
        proposal.timezone_status in {"unknown", "incompatible"}
        and _interval_timeformat(proposal) == "dateTime"
        for proposal, _ in proposals.values()
    )
    reliable_signatures = {
        signature
        for signature, (_, proposal_rows) in proposals.items()
        if any(str(row["initial_reliability"]) in {"high", "medium"} for row in proposal_rows)
    }
    independent_counts = {
        signature: len(
            {
                _correlation_identity(row)
                for row in proposal_rows
                if member_classes[str(row["temporal_evidence_id"])] == "independent"
            }
        )
        for signature, (_, proposal_rows) in proposals.items()
    }
    if len(signatures) > 1:
        assessment = "conflicted"
    elif unresolved or not signatures:
        assessment = "ambiguous"
    elif not reliable_signatures:
        assessment = "low_quality"
    elif independent_counts.get(signatures[0], 0) >= 2:
        assessment = "concordant"
    else:
        assessment = "single_source"

    timestamp = timestamp_now(clock)
    group_semantic = {
        "evidence_hashes": [str(row["evidence_hash"]) for row in rows],
        "policy_id": CONSOLIDATION_POLICY_ID,
        "policy_version": CONSOLIDATION_POLICY_VERSION,
        "target_subject_id": target_subject_id,
        "target_subject_type": target_subject_type,
    }
    group_hash = canonical_sha256_v1(group_semantic)
    connection = open_database(settings.database_path, enable_wal=settings.wal_enabled)
    try:
        validate_database_migrations(connection)
        connection.execute("BEGIN")
        existing_group = connection.execute(
            "SELECT group_id FROM temporal_evidence_groups WHERE group_hash = ?",
            (group_hash,),
        ).fetchone()
        if existing_group is None:
            group_id = next_id(connection, "temporal_evidence_groups", "group_id", "TEG")
            connection.execute(
                """
                INSERT INTO temporal_evidence_groups (
                    group_id, target_subject_type, target_subject_id, policy_id,
                    policy_version, group_hash, assessment, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    group_id,
                    target_subject_type,
                    target_subject_id,
                    CONSOLIDATION_POLICY_ID,
                    CONSOLIDATION_POLICY_VERSION,
                    group_hash,
                    assessment,
                    timestamp,
                ),
            )
            for ordinal, row in enumerate(rows, start=1):
                evidence_id = str(row["temporal_evidence_id"])
                connection.execute(
                    """
                    INSERT INTO temporal_evidence_group_members (
                        group_id, temporal_evidence_id, independence_class, ordinal
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (group_id, evidence_id, member_classes[evidence_id], ordinal),
                )
        else:
            group_id = str(existing_group["group_id"])

        conflict_id: str | None = None
        if assessment == "conflicted":
            existing_conflict = connection.execute(
                """
                SELECT conflict_id FROM temporal_conflicts
                WHERE group_id = ? AND reason = 'contradictory_temporal_signals'
                """,
                (group_id,),
            ).fetchone()
            if existing_conflict is None:
                conflict_id = next_id(connection, "temporal_conflicts", "conflict_id", "TCF")
                connection.execute(
                    """
                    INSERT INTO temporal_conflicts (
                        conflict_id, target_subject_type, target_subject_id, group_id,
                        reason, status, created_at, resolved_by_decision_id
                    ) VALUES (?, ?, ?, ?, 'contradictory_temporal_signals', 'open', ?, NULL)
                    """,
                    (conflict_id, target_subject_type, target_subject_id, group_id, timestamp),
                )
            else:
                conflict_id = str(existing_conflict["conflict_id"])
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    candidate_ids: list[str] = []
    for signature in signatures:
        proposal, proposal_rows = proposals[signature]
        source_revision_id = str(proposal_rows[0]["source_revision_id"])
        independent_count = independent_counts[signature]
        candidate = create_temporal_candidate(
            settings.workspace_dir,
            run_id=run_id,
            source_revision_id=source_revision_id,
            target_subject_type=target_subject_type,
            target_subject_id=target_subject_id,
            temporal_evidence_ids=[str(row["temporal_evidence_id"]) for row in proposal_rows],
            normalized_start=proposal.start,
            normalized_end=proposal.end,
            original_precision=proposal.original_precision,
            timezone_status=proposal.timezone_status,
            timezone_value=proposal.timezone_value,
            bounds_semantics=proposal.bounds_semantics,
            derivation_policy_id=CONSOLIDATION_POLICY_ID,
            derivation_policy_version=CONSOLIDATION_POLICY_VERSION,
            assertion_type="ambiguous",
            confidence="medium" if independent_count >= 2 else "low",
            semantic_annotations={
                "evidence_assessment": assessment,
                "evidence_group_hash": group_hash,
                "independent_signal_count": independent_count,
            },
            clock=clock,
        )
        candidate_ids.append(candidate.candidate_record_id)

    return TemporalConsolidationResult(
        target_subject_type=target_subject_type,
        target_subject_id=target_subject_id,
        group_id=group_id,
        group_hash=group_hash,
        assessment=assessment,
        evidence_ids=tuple(str(row["temporal_evidence_id"]) for row in rows),
        candidate_record_ids=tuple(candidate_ids),
        conflict_id=conflict_id,
    )


def derive_temporal_for_revision(
    workspace_dir: str | Path,
    *,
    run_id: str,
    source_revision_id: str,
    clock: Clock | None = None,
) -> TemporalConsolidationResult:
    extract_temporal_evidence(
        workspace_dir,
        source_revision_id=source_revision_id,
        clock=clock,
    )
    return consolidate_temporal_evidence(
        workspace_dir,
        run_id=run_id,
        target_subject_type="source_revision",
        target_subject_id=source_revision_id,
        clock=clock,
    )


def propagate_temporal_intervals(
    workspace_dir: str | Path,
    *,
    run_id: str,
    source_revision_id: str,
    target_subject_type: str,
    target_subject_id: str,
    source_subjects: Iterable[tuple[str, str]],
    policy: str,
    clock: Clock | None = None,
) -> TemporalPropagationResult:
    """Apply only an explicitly requested propagation policy; never inherit implicitly."""
    if policy not in {"explicit_copy", "intersection", "aggregation", "conflict"}:
        raise TemporalError(
            f"Unsupported temporal propagation policy: {policy}.",
            reason="temporal_propagation_policy_invalid",
        )
    settings = resolve_database_settings(workspace_dir)
    subjects = tuple(sorted(set(source_subjects)))
    connection = open_database(settings.database_path, enable_wal=settings.wal_enabled)
    try:
        validate_database_migrations(connection)
        intervals: list[dict[str, Any]] = []
        for subject_type, subject_id in subjects:
            rows = connection.execute(
                """
                SELECT ti.* FROM temporal_intervals ti
                JOIN review_subject_heads h
                  ON h.subject_type = 'candidate_record'
                 AND h.subject_id = ti.source_candidate_record_id
                JOIN review_decisions rd ON rd.decision_id = h.decision_id
                WHERE ti.subject_type = ? AND ti.subject_id = ?
                  AND rd.outcome = 'confirmed'
                ORDER BY ti.start_value, ti.end_value, ti.interval_hash
                """,
                (subject_type, subject_id),
            ).fetchall()
            for row in rows:
                intervals.append({**dict(row), "origin": f"{subject_type}:{subject_id}"})
    finally:
        connection.close()
    if not intervals:
        raise TemporalError("No effective source intervals to propagate.", reason="temporal_source_empty")

    if policy == "explicit_copy":
        derived = [_interval_from_row(row) for row in intervals]
    elif policy == "intersection":
        intersection = intersect_temporal_intervals(_interval_from_row(row) for row in intervals)
        derived = [] if intersection is None else [intersection]
    elif policy == "aggregation":
        derived = aggregate_temporal_intervals(_interval_from_row(row) for row in intervals)
    else:
        derived = []

    records = [
        _evidence_record(
            source_revision_id,
            target_subject_type,
            target_subject_id,
            source_key=f"propagation:{policy}:{row['origin']}",
            source_format="canonical_interval",
            raw_value=canonical_json_v1(_interval_from_row(row).to_payload()),
            extraction_method="explicit_temporal_propagation",
            reliability="medium",
            warnings=("explicit_policy_required",),
        )
        for row in intervals
    ]
    evidence = persist_temporal_evidence_records(
        settings.workspace_dir,
        source_revision_id=source_revision_id,
        target_subject_type=target_subject_type,
        target_subject_id=target_subject_id,
        records=records,
        clock=clock,
    )
    if policy == "conflict" or not derived:
        conflict_id = _persist_policy_conflict(
            settings.workspace_dir,
            target_subject_type=target_subject_type,
            target_subject_id=target_subject_id,
            evidence_ids=evidence.evidence_ids,
            policy=policy,
            reason=(
                "explicit_temporal_conflict"
                if policy == "conflict"
                else "empty_temporal_intersection"
            ),
            clock=clock,
        )
        return TemporalPropagationResult(policy, (), conflict_id)

    candidate_ids: list[str] = []
    for interval in derived:
        candidate = create_temporal_candidate(
            settings.workspace_dir,
            run_id=run_id,
            source_revision_id=source_revision_id,
            target_subject_type=target_subject_type,
            target_subject_id=target_subject_id,
            temporal_evidence_ids=evidence.evidence_ids,
            normalized_start=interval.start,
            normalized_end=interval.end,
            original_precision=interval.original_precision,
            timezone_status=interval.timezone_status,
            timezone_value=interval.timezone_value,
            bounds_semantics=interval.bounds_semantics,
            derivation_policy_id=f"temporal_{policy}",
            derivation_policy_version="1",
            semantic_annotations={"source_subjects": [list(value) for value in subjects]},
            clock=clock,
        )
        candidate_ids.append(candidate.candidate_record_id)
    return TemporalPropagationResult(policy, tuple(candidate_ids), None)


def _persist_policy_conflict(
    workspace_dir: str | Path,
    *,
    target_subject_type: str,
    target_subject_id: str,
    evidence_ids: tuple[str, ...],
    policy: str,
    reason: str,
    clock: Clock | None,
) -> str:
    settings = resolve_database_settings(workspace_dir)
    timestamp = timestamp_now(clock)
    semantic = {
        "evidence_ids": sorted(evidence_ids),
        "policy": policy,
        "reason": reason,
        "target_subject_id": target_subject_id,
        "target_subject_type": target_subject_type,
    }
    group_hash = canonical_sha256_v1(semantic)
    connection = open_database(settings.database_path, enable_wal=settings.wal_enabled)
    try:
        validate_database_migrations(connection)
        connection.execute("BEGIN")
        row = connection.execute(
            "SELECT group_id FROM temporal_evidence_groups WHERE group_hash = ?",
            (group_hash,),
        ).fetchone()
        if row is None:
            group_id = next_id(connection, "temporal_evidence_groups", "group_id", "TEG")
            connection.execute(
                """
                INSERT INTO temporal_evidence_groups (
                    group_id, target_subject_type, target_subject_id, policy_id,
                    policy_version, group_hash, assessment, created_at
                ) VALUES (?, ?, ?, ?, '1', ?, 'conflicted', ?)
                """,
                (
                    group_id,
                    target_subject_type,
                    target_subject_id,
                    f"temporal_{policy}",
                    group_hash,
                    timestamp,
                ),
            )
            for ordinal, evidence_id in enumerate(sorted(evidence_ids), start=1):
                connection.execute(
                    """
                    INSERT INTO temporal_evidence_group_members (
                        group_id, temporal_evidence_id, independence_class, ordinal
                    ) VALUES (?, ?, 'independent', ?)
                    """,
                    (group_id, evidence_id, ordinal),
                )
        else:
            group_id = str(row["group_id"])
        row = connection.execute(
            "SELECT conflict_id FROM temporal_conflicts WHERE group_id = ? AND reason = ?",
            (group_id, reason),
        ).fetchone()
        if row is None:
            conflict_id = next_id(connection, "temporal_conflicts", "conflict_id", "TCF")
            connection.execute(
                """
                INSERT INTO temporal_conflicts (
                    conflict_id, target_subject_type, target_subject_id, group_id,
                    reason, status, created_at, resolved_by_decision_id
                ) VALUES (?, ?, ?, ?, ?, 'open', ?, NULL)
                """,
                (
                    conflict_id,
                    target_subject_type,
                    target_subject_id,
                    group_id,
                    reason,
                    timestamp,
                ),
            )
        else:
            conflict_id = str(row["conflict_id"])
        connection.commit()
        return conflict_id
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def intersect_temporal_intervals(
    intervals: Iterable[NormalizedTemporalInterval],
) -> NormalizedTemporalInterval | None:
    values = tuple(intervals)
    _require_compatible_intervals(values)
    starts = [value.start for value in values if value.start is not None]
    ends = [value.end for value in values if value.end is not None]
    start = max(starts) if starts else None
    end = min(ends) if ends else None
    if start is not None and end is not None and start > end:
        return None
    template = values[0]
    precision = (
        "day"
        if _interval_timeformat(template) == "date"
        else _least_precise(*(value.original_precision for value in values))
    )
    return NormalizedTemporalInterval(
        start,
        end,
        precision,
        template.timezone_status,
        template.timezone_value,
        "inclusive",
    )


def aggregate_temporal_intervals(
    intervals: Iterable[NormalizedTemporalInterval],
) -> list[NormalizedTemporalInterval]:
    values = tuple(intervals)
    _require_compatible_intervals(values)
    unique = {value.signature(): value for value in values}
    return sorted(
        unique.values(),
        key=lambda value: (value.start or "", value.end or "", value.signature()),
    )


def handoff_ai_temporal_candidates(
    workspace_dir: str | Path,
    *,
    run_id: str,
    source_revision_id: str,
    target_subject_type: str,
    target_subject_id: str,
    adapter: TemporalAiAdapter,
    request: Mapping[str, Any],
    clock: Clock | None = None,
) -> tuple[str, ...]:
    """Import fake/external AI proposals through raw evidence and the common candidate inbox."""
    proposals = tuple(dict(item) for item in adapter.propose(dict(request)))
    records = [
        _evidence_record(
            source_revision_id,
            target_subject_type,
            target_subject_id,
            source_key=f"ai:proposal:{index}",
            source_format="ai_candidate_proposal",
            raw_value=str(proposal["raw_value"]),
            extraction_method="ai_candidate_handoff",
            reliability="low",
            warnings=("ai_proposal_requires_human_review",),
        )
        for index, proposal in enumerate(proposals, start=1)
    ]
    evidence = persist_temporal_evidence_records(
        workspace_dir,
        source_revision_id=source_revision_id,
        target_subject_type=target_subject_type,
        target_subject_id=target_subject_id,
        records=records,
        clock=clock,
    )
    result: list[str] = []
    for proposal, evidence_id in zip(proposals, evidence.evidence_ids, strict=True):
        candidate = create_temporal_candidate(
            workspace_dir,
            run_id=run_id,
            source_revision_id=source_revision_id,
            target_subject_type=target_subject_type,
            target_subject_id=target_subject_id,
            temporal_evidence_ids=[evidence_id],
            normalized_start=_optional_string(proposal.get("normalized_start")),
            normalized_end=_optional_string(proposal.get("normalized_end")),
            original_precision=str(proposal["original_precision"]),
            timezone_status=str(proposal["timezone_status"]),
            timezone_value=_optional_string(proposal.get("timezone_value")),
            bounds_semantics=str(proposal.get("bounds_semantics", "inclusive")),
            derivation_policy_id="ai_candidate_handoff",
            derivation_policy_version="1",
            assertion_type="ambiguous",
            confidence="low",
            clock=clock,
        )
        result.append(candidate.candidate_record_id)
    return tuple(result)


def explicit_precedence_candidate_payloads(
    text: str,
    *,
    source_revision_id: str,
    source_entity: str,
    chunk_id: str | None = None,
    fragment_id: str | None = None,
) -> list[dict[str, Any]]:
    """Create relation payloads only for literal supersedes/precedes/version_of markers."""
    results: list[dict[str, Any]] = []
    pattern = re.compile(
        r"(?im)^\s*(supersedes|precedes|version_of)\s*[:=]\s*([^\s,;#]+)\s*$"
    )
    for match in pattern.finditer(text):
        evidence_text = match.group(0).strip()
        semantic = {
            "relation_type": match.group(1).lower(),
            "source_entity": source_entity,
            "target_entity": match.group(2),
        }
        results.append(
            {
                **semantic,
                "assertion_type": "explicit",
                "candidate_id": f"precedence:{canonical_sha256_v1(semantic)}",
                "chunk_id": chunk_id,
                "confidence": "medium",
                "evidence_text": evidence_text,
                "fragment_id": fragment_id,
                "record_type": "candidate_relation",
                "source_revision_id": source_revision_id,
            }
        )
    return results


class _TemporalHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.values: list[tuple[str, str, str]] = []
        self._json_ld = False
        self._json_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key.lower(): value for key, value in attrs if value is not None}
        if tag.lower() == "time" and attributes.get("datetime"):
            self.values.append(("time:datetime", str(attributes["datetime"]), "html_time"))
        if tag.lower() == "meta" and attributes.get("content"):
            key = attributes.get("name") or attributes.get("property") or attributes.get("itemprop")
            normalized = _normalize_key(key or "")
            if normalized in _DECLARATIVE_KEYS:
                self.values.append((f"meta:{normalized}", str(attributes["content"]), "html_meta"))
        if tag.lower() == "script" and attributes.get("type", "").lower() == "application/ld+json":
            self._json_ld = True
            self._json_parts = []

    def handle_data(self, data: str) -> None:
        if self._json_ld:
            self._json_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "script" or not self._json_ld:
            return
        self._json_ld = False
        try:
            payload = json.loads("".join(self._json_parts))
        except json.JSONDecodeError:
            return
        for key, value in _walk_json(payload):
            normalized = _normalize_key(key)
            if normalized in _DECLARATIVE_KEYS and isinstance(value, (str, int)):
                self.values.append((f"jsonld:{normalized}", str(value), "json_ld"))


def _pdf_records(
    data: bytes,
    source_revision_id: str,
    target_subject_type: str,
    target_subject_id: str,
) -> list[dict[str, Any]]:
    text = data.decode("latin-1", errors="replace")
    values: list[tuple[str, str, str]] = []
    for key in ("CreationDate", "ModDate"):
        for match in re.finditer(rf"/{key}\s*\(([^)]{{1,128}})\)", text):
            values.append((f"info:{key}", match.group(1), "pdf_info"))
    for tag in ("CreateDate", "ModifyDate", "MetadataDate"):
        pattern = rf"<(?:[A-Za-z0-9_.-]+:)?{tag}\b[^>]*>([^<]{{1,128}})</"
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            values.append((f"xmp:{tag}", match.group(1).strip(), "pdf_xmp"))
    return [
        _evidence_record(
            source_revision_id,
            target_subject_type,
            target_subject_id,
            source_key=key,
            source_format=source_format,
            raw_value=value,
            extraction_method="pdf_embedded_metadata",
            reliability="medium",
            warnings=("document_property_not_validity_interval",),
        )
        for key, value, source_format in sorted(set(values))
    ]


def _html_records(
    text: str,
    source_revision_id: str,
    target_subject_type: str,
    target_subject_id: str,
) -> list[dict[str, Any]]:
    parser = _TemporalHtmlParser()
    parser.feed(text)
    return [
        _evidence_record(
            source_revision_id,
            target_subject_type,
            target_subject_id,
            source_key=key,
            source_format=source_format,
            raw_value=value,
            extraction_method="html_declared_temporality",
            reliability="medium",
            warnings=("declared_content_requires_review",),
        )
        for key, value, source_format in sorted(set(parser.values))
    ]


def _declared_text_records(
    text: str,
    *,
    suffix: str,
    source_revision_id: str,
    target_subject_type: str,
    target_subject_id: str,
) -> list[dict[str, Any]]:
    values: set[tuple[str, str]] = set()
    normalized_keys = "|".join(sorted(_DECLARATIVE_KEYS, key=len, reverse=True))
    pattern = re.compile(
        rf"(?im)(?<![A-Za-z0-9_])({normalized_keys})\s*[:=]\s*[\"']?({_TEMPORAL_VALUE})"
    )
    for match in pattern.finditer(text):
        values.add((_normalize_key(match.group(1)), match.group(2)))
    if suffix == ".xml":
        xml_pattern = re.compile(
            rf"(?is)<({normalized_keys})\b[^>]*>\s*({_TEMPORAL_VALUE})\s*</\1\s*>"
        )
        for match in xml_pattern.finditer(text):
            values.add((_normalize_key(match.group(1)), match.group(2)))
    source_format = {
        ".md": "markdown_declaration",
        ".markdown": "markdown_declaration",
        ".sql": "sql_declaration",
        ".xml": "xml_declaration",
        ".log": "log_declaration",
    }.get(suffix, "text_declaration")
    return [
        _evidence_record(
            source_revision_id,
            target_subject_type,
            target_subject_id,
            source_key=f"content:{key}",
            source_format=source_format,
            raw_value=value,
            extraction_method="declared_content_temporality",
            reliability="high",
            warnings=("declared_content_requires_review",),
        )
        for key, value in sorted(values)
    ]


def _filename_records(
    name: str,
    source_revision_id: str,
    target_subject_type: str,
    target_subject_id: str,
) -> list[dict[str, Any]]:
    stem = Path(name).stem
    values: set[str] = set()
    for match in re.finditer(r"(?<!\d)(\d{4}-\d{2}-\d{2})(?!\d)", stem):
        values.add(match.group(1))
    if not values:
        for match in re.finditer(r"(?<!\d)(\d{4}-\d{2})(?![-\d])", stem):
            values.add(match.group(1))
    if not values and not re.search(r"(?i)(?:^|[_-])v(?:ersion)?[_-]?\d{4}(?:$|[_-])", stem):
        for match in re.finditer(r"(?<!\d)((?:19|20)\d{2})(?!\d)", stem):
            values.add(match.group(1))
    return [
        _evidence_record(
            source_revision_id,
            target_subject_type,
            target_subject_id,
            source_key="filename:temporal_token",
            source_format="filename_token",
            raw_value=value,
            extraction_method="filename_temporality",
            reliability="medium",
            warnings=("filename_context_ambiguous",),
        )
        for value in sorted(values)
    ]


def _evidence_record(
    source_revision_id: str,
    target_subject_type: str,
    target_subject_id: str,
    *,
    source_key: str,
    source_format: str,
    raw_value: str,
    extraction_method: str,
    reliability: str,
    warnings: Iterable[str],
) -> dict[str, Any]:
    precision, timezone_status, timezone_value = _raw_characteristics(raw_value)
    return {
        "extraction_method": extraction_method,
        "extraction_version": EXTRACTION_VERSION,
        "initial_reliability": reliability,
        "precision": precision,
        "raw_value": raw_value,
        "source_format": source_format,
        "source_fragment_id": (
            target_subject_id if target_subject_type == "source_fragment" else None
        ),
        "source_key": source_key,
        "source_revision_id": source_revision_id,
        "target_subject_id": target_subject_id,
        "target_subject_type": target_subject_type,
        "timezone_status": timezone_status,
        "timezone_value": timezone_value,
        "warnings": sorted(set(warnings)),
    }


def _raw_characteristics(value: str) -> tuple[str, str, str | None]:
    proposal = _normalize_scalar(value)
    if proposal is None:
        return "unknown", "unknown", None
    return proposal.original_precision, proposal.timezone_status, proposal.timezone_value


def _normalize_scalar(value: str) -> NormalizedTemporalInterval | None:
    raw = value.strip()
    if raw.startswith("D:"):
        raw = _normalize_pdf_date(raw)
    compact = re.fullmatch(r"(\d{4})(\d{2})(\d{2})", raw)
    if compact:
        raw = "-".join(compact.groups())
    if re.fullmatch(r"\d{4}", raw):
        year = int(raw)
        return NormalizedTemporalInterval(
            f"{year:04d}-01-01", f"{year:04d}-12-31", "year", "unknown", None,
            "coverage_envelope",
        )
    if re.fullmatch(r"\d{4}-\d{2}", raw):
        year, month = (int(item) for item in raw.split("-"))
        try:
            last_day = monthrange(year, month)[1]
        except (ValueError, IndexError):
            return None
        return NormalizedTemporalInterval(
            f"{year:04d}-{month:02d}-01",
            f"{year:04d}-{month:02d}-{last_day:02d}",
            "month",
            "unknown",
            None,
            "coverage_envelope",
        )
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        try:
            normalized = date.fromisoformat(raw).isoformat()
        except ValueError:
            return None
        return NormalizedTemporalInterval(
            normalized, normalized, "day", "unknown", None, "inclusive"
        )
    if "T" not in raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    precision = "fractional_second" if parsed.microsecond else "second"
    if parsed.utcoffset() is None:
        timezone_status = "unknown"
        timezone_value = None
    else:
        timezone_status = "explicit"
        offset = parsed.strftime("%z")
        timezone_value = "UTC" if offset == "+0000" else f"{offset[:3]}:{offset[3:]}"
    normalized = parsed.isoformat()
    return NormalizedTemporalInterval(
        normalized, normalized, precision, timezone_status, timezone_value, "inclusive"
    )


def _normalize_pdf_date(value: str) -> str:
    match = re.fullmatch(
        r"D:(\d{4})(\d{2})?(\d{2})?(\d{2})?(\d{2})?(\d{2})?"
        r"(?:([Zz])|([+-])(\d{2})'?((?:\d{2})?)'?)?",
        value,
    )
    if not match:
        return value
    year, month, day, hour, minute, second, zulu, sign, off_hour, off_minute = match.groups()
    if month is None:
        return year
    if day is None:
        return f"{year}-{month}"
    result = f"{year}-{month}-{day}"
    if hour is not None:
        if minute is None or second is None:
            return value
        result += f"T{hour}:{minute}:{second}"
        if zulu:
            result += "Z"
        elif sign and off_hour:
            result += f"{sign}{off_hour}:{off_minute or '00'}"
    return result


def _proposals_for_rows(
    rows: Iterable[Mapping[str, Any]],
) -> dict[str, tuple[NormalizedTemporalInterval, list[Mapping[str, Any]]]]:
    result: dict[str, tuple[NormalizedTemporalInterval, list[Mapping[str, Any]]]] = {}
    directional: dict[tuple[str, str], dict[str, tuple[NormalizedTemporalInterval, Mapping[str, Any]]]] = {}
    for row in rows:
        proposal = _normalize_scalar(str(row["raw_value"]))
        if proposal is None:
            continue
        key = _normalize_key(str(row["source_key"]).rsplit(":", 1)[-1])
        direction = "from" if key in _FROM_KEYS else "to" if key in _TO_KEYS else None
        if direction:
            pair_key = (str(row["source_revision_id"]), _source_family(row))
            directional.setdefault(pair_key, {})[direction] = (proposal, row)
            continue
        _add_proposal(result, proposal, [row])
    for values in directional.values():
        start_pair = values.get("from")
        end_pair = values.get("to")
        if start_pair and end_pair:
            start, start_row = start_pair
            end, end_row = end_pair
            if _interval_timeformat(start) == _interval_timeformat(end):
                combined = NormalizedTemporalInterval(
                    start.start,
                    end.end,
                    _least_precise(start.original_precision, end.original_precision),
                    _combined_timezone_status(start, end),
                    start.timezone_value if start.timezone_value == end.timezone_value else None,
                    (
                        "coverage_envelope"
                        if "coverage_envelope" in {start.bounds_semantics, end.bounds_semantics}
                        else "inclusive"
                    ),
                )
                _add_proposal(result, combined, [start_row, end_row])
                continue
        for direction, (proposal, row) in sorted(values.items()):
            open_interval = NormalizedTemporalInterval(
                proposal.start if direction == "from" else None,
                proposal.end if direction == "to" else None,
                proposal.original_precision,
                proposal.timezone_status,
                proposal.timezone_value,
                proposal.bounds_semantics,
            )
            _add_proposal(result, open_interval, [row])
    return result


def _add_proposal(
    target: dict[str, tuple[NormalizedTemporalInterval, list[Mapping[str, Any]]]],
    proposal: NormalizedTemporalInterval,
    rows: Iterable[Mapping[str, Any]],
) -> None:
    signature = proposal.signature()
    if signature not in target:
        target[signature] = (proposal, [])
    known = {str(row["temporal_evidence_id"]) for row in target[signature][1]}
    target[signature][1].extend(
        row for row in rows if str(row["temporal_evidence_id"]) not in known
    )
    target[signature][1].sort(key=lambda row: str(row["evidence_hash"]))


def _classify_members(
    rows: Iterable[Mapping[str, Any]],
    proposals: Mapping[str, tuple[NormalizedTemporalInterval, list[Mapping[str, Any]]]],
) -> dict[str, str]:
    classes: dict[str, str] = {}
    seen: dict[str, dict[str, set[str]]] = {}
    for row in rows:
        evidence_id = str(row["temporal_evidence_id"])
        if str(row["initial_reliability"]) in {"low", "unknown"}:
            classes[evidence_id] = "low_quality"
            continue
        identity = _correlation_identity(row)
        value_signature = next(
            (
                signature
                for signature, (_, proposal_rows) in proposals.items()
                if any(str(item["temporal_evidence_id"]) == evidence_id for item in proposal_rows)
            ),
            "unparsed",
        )
        previous = seen.setdefault(value_signature, {})
        raw_values = previous.get(identity)
        if raw_values is not None:
            raw_value = str(row["raw_value"])
            classes[evidence_id] = "duplicate" if raw_value in raw_values else "correlated"
            raw_values.add(raw_value)
        else:
            classes[evidence_id] = "independent"
            previous[identity] = {str(row["raw_value"])}
    return classes


def _correlation_identity(row: Mapping[str, Any]) -> str:
    return f"{row['content_hash']}:{_source_family(row)}"


def _source_family(row: Mapping[str, Any]) -> str:
    source_key = str(row["source_key"]).split(":", 1)[0]
    method = str(row["extraction_method"])
    if method == "ooxml_embedded_metadata":
        return f"ooxml:{source_key}"
    if method == "pdf_embedded_metadata":
        return f"pdf:{source_key}"
    return method


def _interval_from_row(row: Mapping[str, Any]) -> NormalizedTemporalInterval:
    status = "resolved" if row.get("timezone_value") else "unknown"
    return NormalizedTemporalInterval(
        _optional_string(row.get("start_value")),
        _optional_string(row.get("end_value")),
        str(row["original_precision"]),
        status,
        _optional_string(row.get("timezone_value")),
        str(row["bounds_semantics"]),
    )


def _require_compatible_intervals(values: tuple[NormalizedTemporalInterval, ...]) -> None:
    if not values:
        raise TemporalError("Temporal interval collection is empty.", reason="temporal_source_empty")
    profiles = {
        (
            _interval_timeformat(value),
            value.timezone_value if _interval_timeformat(value) == "dateTime" else None,
        )
        for value in values
    }
    if len(profiles) > 1:
        raise TemporalError(
            "Temporal intervals have incompatible precision/timezone profiles.",
            reason="temporal_profile_incompatible",
        )


def _interval_timeformat(value: NormalizedTemporalInterval) -> str:
    for bound in (value.start, value.end):
        if bound is not None:
            return "dateTime" if "T" in bound else "date"
    return "date"


def _least_precise(*values: str) -> str:
    order = {"year": 0, "month": 1, "day": 2, "second": 3, "fractional_second": 4}
    return min(values, key=lambda value: order.get(value, -1))


def _combined_timezone_status(
    left: NormalizedTemporalInterval,
    right: NormalizedTemporalInterval,
) -> str:
    if left.timezone_status == right.timezone_status and left.timezone_value == right.timezone_value:
        return left.timezone_status
    if _interval_timeformat(left) == "date":
        return "unknown"
    return "incompatible"


def _walk_json(value: Any) -> Iterable[tuple[str, Any]]:
    if isinstance(value, dict):
        for key in sorted(value):
            item = value[key]
            yield str(key), item
            yield from _walk_json(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_json(item)


def _normalize_key(value: str) -> str:
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value)
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def _optional_string(value: Any) -> str | None:
    return None if value in {None, ""} else str(value)


__all__ = [
    "CONSOLIDATION_POLICY_ID",
    "CONSOLIDATION_POLICY_VERSION",
    "NormalizedTemporalInterval",
    "TemporalAiAdapter",
    "TemporalConsolidationResult",
    "TemporalPropagationResult",
    "aggregate_temporal_intervals",
    "consolidate_temporal_evidence",
    "derive_temporal_for_revision",
    "explicit_precedence_candidate_payloads",
    "extract_temporal_evidence",
    "handoff_ai_temporal_candidates",
    "intersect_temporal_intervals",
    "propagate_temporal_intervals",
]
