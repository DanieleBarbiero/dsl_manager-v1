from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from dsl_mngr.cli.app import main
from dsl_mngr.core.candidate_review import (
    CandidateReviewConflict,
    CandidateReviewError,
    CandidateReviewService,
)
from dsl_mngr.core.merge import (
    MergeReviewPreconditionError,
    NoMergeEligibleCandidatesError,
    merge_candidate_batch,
)
from dsl_mngr.core.migrations import migrate_workspace_database
from dsl_mngr.core.reconciliation import (
    ReconciliationError,
    ReconciliationRequiredError,
    ensure_no_open_reconciliation,
    reconcile_required,
)
from dsl_mngr.core.workspace import initialize_workspace


TIMESTAMP = "2026-09-04T10:00:00+00:00"
EVIDENCE = "CREATE TABLE CLIENTI (ID INTEGER PRIMARY KEY);"


def test_slice_20_pending_not_mergeable(tmp_path):
    workspace, batch_id, candidate_ids = _workspace_with_candidates(
        tmp_path,
        [_fact("PENDING", value="database_table")],
    )

    with pytest.raises(NoMergeEligibleCandidatesError) as caught:
        merge_candidate_batch(workspace, run_id="RUN_000001", batch_id=batch_id)

    assert caught.value.reason == "no_merge_eligible_candidates"
    with _connect(workspace) as connection:
        assert connection.execute("SELECT COUNT(*) FROM facts").fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM review_subject_heads"
        ).fetchone()[0] == 0

    decision = CandidateReviewService(workspace).confirm(
        candidate_ids[0],
        actor_id="reviewer-1",
        expected_head_decision_id=None,
        idempotency_key="pending-confirm",
    )
    merged = merge_candidate_batch(workspace, run_id="RUN_000001", batch_id=batch_id)
    assert decision.outcome == "confirmed"
    assert merged.merged_candidate_record_ids == candidate_ids
    with _connect(workspace) as connection:
        assert connection.execute("SELECT COUNT(*) FROM facts").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM effective_facts").fetchone()[0] == 1


def test_slice_20_decision_chain(tmp_path):
    workspace, _, candidate_ids = _workspace_with_candidates(
        tmp_path,
        [_fact("CHAIN")],
    )
    candidate_id = candidate_ids[0]
    service = CandidateReviewService(workspace)
    confirmed = service.confirm(
        candidate_id,
        actor_id="reviewer-1",
        expected_head_decision_id=None,
        idempotency_key="chain-confirm",
    )
    rejected = service.reject(
        candidate_id,
        actor_id="reviewer-1",
        reason="evidence withdrawn",
        expected_head_decision_id=confirmed.decision_id,
        idempotency_key="chain-reject",
    )

    with _connect(workspace) as connection:
        rows = connection.execute(
            """
            SELECT decision_id, supersedes_decision_id
            FROM review_decisions ORDER BY decision_id
            """
        ).fetchall()
        assert [(row["decision_id"], row["supersedes_decision_id"]) for row in rows] == [
            (confirmed.decision_id, None),
            (rejected.decision_id, confirmed.decision_id),
        ]
        assert connection.execute(
            "SELECT decision_id FROM review_subject_heads WHERE subject_id = ?",
            (candidate_id,),
        ).fetchone()[0] == rejected.decision_id
        with pytest.raises(sqlite3.IntegrityError, match="append_only"):
            connection.execute(
                "UPDATE review_decisions SET reason = 'changed' WHERE decision_id = ?",
                (confirmed.decision_id,),
            )
        with pytest.raises(sqlite3.IntegrityError, match="review_decision_cycle"):
            _insert_raw_decision(
                connection,
                decision_id="RDEC_SELF",
                subject_id=candidate_id,
                supersedes_decision_id="RDEC_SELF",
            )
        with pytest.raises(sqlite3.IntegrityError, match="review_decision_subject_mismatch"):
            _insert_raw_decision(
                connection,
                decision_id="RDEC_WRONG_SUBJECT",
                subject_id="CREC_OTHER_SUBJECT",
                supersedes_decision_id=confirmed.decision_id,
            )


def test_slice_20_stale_head_atomic(tmp_path):
    workspace, _, candidate_ids = _workspace_with_candidates(tmp_path, [_fact("STALE")])
    first_writer = CandidateReviewService(workspace)
    second_writer = CandidateReviewService(workspace)
    decision = first_writer.confirm(
        candidate_ids[0],
        actor_id="writer-1",
        expected_head_decision_id=None,
        idempotency_key="writer-1-confirm",
    )

    with pytest.raises(CandidateReviewConflict) as caught:
        second_writer.reject(
            candidate_ids[0],
            actor_id="writer-2",
            reason="stale review",
            expected_head_decision_id=None,
            idempotency_key="writer-2-reject",
        )

    assert caught.value.reason == "review_head_conflict"
    with _connect(workspace) as connection:
        assert connection.execute("SELECT COUNT(*) FROM review_decisions").fetchone()[0] == 1
        assert connection.execute(
            "SELECT decision_id FROM review_subject_heads"
        ).fetchone()[0] == decision.decision_id


def test_slice_20_review_idempotency(tmp_path):
    workspace, _, candidate_ids = _workspace_with_candidates(tmp_path, [_fact("IDEMP")])
    candidate_id = candidate_ids[0]
    service = CandidateReviewService(workspace)
    first = service.confirm(
        candidate_id,
        actor_id="reviewer-1",
        reason="checked",
        expected_head_decision_id=None,
        idempotency_key="stable-key",
    )
    replay = service.confirm(
        candidate_id,
        actor_id="reviewer-1",
        reason="checked",
        expected_head_decision_id=None,
        idempotency_key="stable-key",
    )
    assert replay.action == "replayed"
    assert replay.decision_id == first.decision_id

    with pytest.raises(CandidateReviewConflict) as collision:
        service.confirm(
            candidate_id,
            actor_id="reviewer-1",
            reason="different request",
            expected_head_decision_id=None,
            idempotency_key="stable-key",
        )
    assert collision.value.reason == "idempotency_payload_conflict"

    noop = service.confirm(
        candidate_id,
        actor_id="reviewer-2",
        reason="independent explanation",
        expected_head_decision_id=first.decision_id,
        idempotency_key="semantic-noop",
    )
    assert noop.action == "semantic_noop"
    assert noop.decision_id == first.decision_id
    with _connect(workspace) as connection:
        assert connection.execute("SELECT COUNT(*) FROM review_decisions").fetchone()[0] == 1


def test_slice_20_actor_required(tmp_path):
    workspace, _, candidate_ids = _workspace_with_candidates(
        tmp_path,
        [
            _fact("ACTOR-1"),
            {
                **_fact("ACTOR-2", entity="ORDINI"),
                "producer_type": "deterministic_rule",
                "rule_id": "ddl_table_fact",
                "rule_version": "1",
            },
        ],
    )
    service = CandidateReviewService(workspace)
    with pytest.raises(CandidateReviewError) as actor_error:
        service.confirm(candidate_ids[0], actor_id="", expected_head_decision_id=None)
    assert actor_error.value.reason == "review_actor_required"

    with pytest.raises(CandidateReviewError) as reason_error:
        service.reject(
            candidate_ids[0],
            actor_id="reviewer-1",
            reason="  ",
            expected_head_decision_id=None,
        )
    assert reason_error.value.reason == "review_reason_required"

    with pytest.raises(CandidateReviewError) as policy_error:
        service.confirm(
            candidate_ids[0],
            actor_id="policy-engine",
            actor_type="automatic",
            expected_head_decision_id=None,
        )
    assert policy_error.value.reason == "review_policy_required"

    automatic = service.confirm(
        candidate_ids[1],
        actor_id="policy-engine",
        actor_type="automatic",
        policy_id="ddl_table_auto",
        policy_version="1",
        expected_head_decision_id=None,
    )
    with _connect(workspace) as connection:
        row = connection.execute(
            "SELECT actor_type, policy_id, policy_version FROM review_decisions WHERE decision_id = ?",
            (automatic.decision_id,),
        ).fetchone()
    assert tuple(row) == ("automatic", "ddl_table_auto", "1")


def test_slice_20_cli_review_and_reconcile_contract(tmp_path):
    workspace, _, candidate_ids = _workspace_with_candidates(tmp_path, [_fact("CLI")])
    console_script = Path(sys.executable).with_name("dsl-manager.exe")
    assert console_script.is_file()

    for command in (
        [str(console_script), "candidates", "review", "--help"],
        [sys.executable, "-m", "dsl_mngr", "facts", "reconcile", "--help"],
    ):
        completed = subprocess.run(command, check=False, capture_output=True, text=True)
        assert completed.returncode == 0
        assert "usage:" in completed.stdout
        assert completed.stderr == ""

    listed = subprocess.run(
        [
            sys.executable,
            "-m",
            "dsl_mngr",
            "candidates",
            "review",
            "list",
            str(workspace),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert listed.returncode == 0
    assert json.loads(listed.stdout)["subject_ids"] == [candidate_ids[0]]
    assert listed.stderr == ""

    missing_actor = subprocess.run(
        [
            sys.executable,
            "-m",
            "dsl_mngr",
            "candidates",
            "review",
            "confirm",
            str(workspace),
            candidate_ids[0],
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert missing_actor.returncode == 2
    assert missing_actor.stdout == ""
    assert "review_actor_required" in missing_actor.stderr
    assert "Traceback" not in missing_actor.stderr

    project_config = workspace / "configs" / "project.yaml"
    config_text = project_config.read_text(encoding="utf-8")
    project_config.write_text(
        config_text.replace(
            "  default_actor_id: \n",
            "  default_actor_id: configured-reviewer\n",
        ),
        encoding="utf-8",
        newline="\n",
    )

    confirmed = subprocess.run(
        [
            str(console_script),
            "candidates",
            "review",
            "confirm",
            str(workspace),
            candidate_ids[0],
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert confirmed.returncode == 0
    assert json.loads(confirmed.stdout)["outcome"] == "confirmed"
    assert confirmed.stderr == ""

    reconciled = subprocess.run(
        [sys.executable, "-m", "dsl_mngr", "facts", "reconcile", str(workspace)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert reconciled.returncode == 0
    assert json.loads(reconciled.stdout)["counters"]["processed"] == 0
    assert reconciled.stderr == ""


def test_slice_20_correction_atomic(tmp_path, capsys):
    workspace, batch_id, candidate_ids = _workspace_with_candidates(
        tmp_path,
        [_fact("CORRECT", value="old")],
    )
    original_id = candidate_ids[0]
    service = CandidateReviewService(workspace)
    original_head = service.confirm(
        original_id,
        actor_id="reviewer-1",
        expected_head_decision_id=None,
        idempotency_key="original-confirm",
    )
    merge_candidate_batch(workspace, run_id="RUN_000001", batch_id=batch_id)
    corrected = _fact("CORRECTED", value="new")

    def crash(point: str) -> None:
        if point == "after_batch":
            raise RuntimeError("injected crash")

    with pytest.raises(RuntimeError, match="injected crash"):
        CandidateReviewService(workspace, fault_hook=crash).correct(
            original_id,
            corrected_payload=corrected,
            actor_id="reviewer-1",
            reason="fix value",
            expected_head_decision_id=original_head.decision_id,
            idempotency_key="correction-key",
        )
    with _connect(workspace) as connection:
        assert connection.execute("SELECT COUNT(*) FROM candidate_corrections").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM candidate_batches").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM candidate_records").fetchone()[0] == 1

    result = service.correct(
        original_id,
        corrected_payload=corrected,
        actor_id="reviewer-1",
        reason="fix value",
        expected_head_decision_id=original_head.decision_id,
        idempotency_key="correction-key",
    )
    replay = service.correct(
        original_id,
        corrected_payload=corrected,
        actor_id="reviewer-1",
        reason="fix value",
        expected_head_decision_id=original_head.decision_id,
        idempotency_key="correction-key",
    )
    assert replay.action == "replayed"
    assert replay.batch_id == result.batch_id
    assert replay.replacement_candidate_record_id == result.replacement_candidate_record_id
    with pytest.raises(CandidateReviewConflict) as branch:
        service.correct(
            original_id,
            corrected_payload={**corrected, "property_value": "third"},
            actor_id="reviewer-2",
            reason="attempt branch",
            expected_head_decision_id=result.decision_id,
            idempotency_key="branch-key",
        )
    assert branch.value.reason == "correction_leaf_conflict"

    with _connect(workspace) as connection:
        original_payload = json.loads(
            connection.execute(
                "SELECT payload_json FROM candidate_records WHERE candidate_record_id = ?",
                (original_id,),
            ).fetchone()[0]
        )
        replacement_head = connection.execute(
            """
            SELECT rd.outcome FROM review_subject_heads h
            JOIN review_decisions rd ON rd.decision_id = h.decision_id
            WHERE h.subject_id = ?
            """,
            (result.replacement_candidate_record_id,),
        ).fetchone()[0]
        supersedes_candidate_record_id = connection.execute(
            """
            SELECT supersedes_candidate_record_id
            FROM candidate_records WHERE candidate_record_id = ?
            """,
            (result.replacement_candidate_record_id,),
        ).fetchone()[0]
        batch = connection.execute(
            "SELECT input_path, origin_type, origin_ref, status FROM candidate_batches WHERE batch_id = ?",
            (result.batch_id,),
        ).fetchone()
        assert original_payload["property_value"] == "old"
        assert replacement_head == "confirmed"
        assert supersedes_candidate_record_id == original_id
        assert tuple(batch) == (
            None,
            "human_correction",
            "review://CORR_000001",
            "completed",
        )
        assert connection.execute("SELECT COUNT(*) FROM effective_facts").fetchone()[0] == 0
    with pytest.raises(ReconciliationRequiredError):
        ensure_no_open_reconciliation(workspace)
    assert main(["dsl", "render", str(workspace)]) == 4
    assert "reconciliation_required" in capsys.readouterr().err
    assert main(
        [
            "dsl",
            "diff",
            str(workspace),
            "--from",
            "DSL_MISSING_LEFT",
            "--to",
            "DSL_MISSING_RIGHT",
        ]
    ) == 4
    assert "reconciliation_required" in capsys.readouterr().err
    assert main(
        ["graph", "export", str(workspace), "--snapshot", "DSL_MISSING"]
    ) == 4
    assert "reconciliation_required" in capsys.readouterr().err

    merged = merge_candidate_batch(
        workspace,
        run_id="RUN_000001",
        batch_id=result.batch_id or "",
    )
    assert merged.reconciliation_closed == 1
    with _connect(workspace) as connection:
        statuses = connection.execute(
            "SELECT property_value, status FROM facts ORDER BY property_value"
        ).fetchall()
        assert [(row[0], row[1]) for row in statuses] == [
            ("new", "active"),
            ("old", "unsupported"),
        ]
        assert connection.execute("SELECT COUNT(*) FROM effective_facts").fetchone()[0] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM reconciliation_required WHERE status = 'open'"
        ).fetchone()[0] == 0


def test_slice_20_mixed_merge_strict_and_no_eligible(tmp_path):
    workspace, batch_id, candidate_ids = _workspace_with_candidates(
        tmp_path / "mixed",
        [
            _fact("ELIGIBLE", value="one"),
            _fact("REJECTED", value="two"),
            _fact("PENDING", value="three"),
        ],
    )
    service = CandidateReviewService(workspace)
    service.confirm(
        candidate_ids[0],
        actor_id="reviewer",
        expected_head_decision_id=None,
        idempotency_key="mixed-confirm",
    )
    service.reject(
        candidate_ids[1],
        actor_id="reviewer",
        reason="not valid",
        expected_head_decision_id=None,
        idempotency_key="mixed-reject",
    )
    result = merge_candidate_batch(workspace, run_id="RUN_000001", batch_id=batch_id)
    assert result.facts_created == 1
    assert result.skipped_pending == 1
    assert result.skipped_rejected == 1

    strict_workspace, strict_batch, strict_ids = _workspace_with_candidates(
        tmp_path / "strict",
        [_fact("ELIGIBLE"), _fact("PENDING", value="pending")],
    )
    CandidateReviewService(strict_workspace).confirm(
        strict_ids[0],
        actor_id="reviewer",
        expected_head_decision_id=None,
        idempotency_key="strict-confirm",
    )
    with pytest.raises(MergeReviewPreconditionError):
        merge_candidate_batch(
            strict_workspace,
            run_id="RUN_000001",
            batch_id=strict_batch,
            strict_review=True,
        )
    with _connect(strict_workspace) as connection:
        assert connection.execute("SELECT COUNT(*) FROM facts").fetchone()[0] == 0


def test_slice_20_effective_support_and_simple_reconcile(tmp_path):
    workspace, batch_id, candidate_ids = _workspace_with_candidates(
        tmp_path,
        [
            _fact("SUPPORT-1"),
            _fact("SUPPORT-2"),
            _relation("RELATION-1"),
        ],
    )
    service = CandidateReviewService(workspace)
    heads = []
    for index, candidate_id in enumerate(candidate_ids):
        heads.append(
            service.confirm(
                candidate_id,
                actor_id="reviewer",
                expected_head_decision_id=None,
                idempotency_key=f"support-confirm-{index}",
            )
        )
    merge_candidate_batch(workspace, run_id="RUN_000001", batch_id=batch_id)
    rejected = service.reject(
        candidate_ids[0],
        actor_id="reviewer",
        reason="support withdrawn",
        expected_head_decision_id=heads[0].decision_id,
        idempotency_key="support-reject",
    )
    assert rejected.reconciliation_id is not None

    with _connect(workspace) as connection:
        assert connection.execute("SELECT COUNT(*) FROM effective_fact_evidence").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM effective_relation_evidence").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM effective_facts").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM effective_relations").fetchone()[0] == 1

    reconciled = reconcile_required(workspace, run_id="RUN_000001")
    assert reconciled.closed == 1
    assert reconciled.supports_removed == 1
    with _connect(workspace) as connection:
        assert connection.execute("SELECT COUNT(*) FROM fact_evidence").fetchone()[0] == 1
        assert connection.execute("SELECT status FROM facts").fetchone()[0] == "active"


def test_slice_20_reconcile_replacement_pending(tmp_path):
    workspace, batch_id, candidate_ids = _workspace_with_candidates(
        tmp_path,
        [_fact("ORIGINAL", value="old")],
    )
    service = CandidateReviewService(workspace)
    head = service.confirm(
        candidate_ids[0],
        actor_id="reviewer",
        expected_head_decision_id=None,
        idempotency_key="pending-replacement-confirm",
    )
    merge_candidate_batch(workspace, run_id="RUN_000001", batch_id=batch_id)
    correction = service.correct(
        candidate_ids[0],
        corrected_payload=_fact("REPLACEMENT", value="new"),
        actor_id="reviewer",
        reason="replace value",
        expected_head_decision_id=head.decision_id,
        idempotency_key="pending-replacement-correct",
    )

    with pytest.raises(ReconciliationError) as strict_error:
        reconcile_required(workspace, run_id="RUN_000001", strict=True)
    assert strict_error.value.reason == "replacement_merge_pending"
    with _connect(workspace) as connection:
        assert connection.execute("SELECT COUNT(*) FROM fact_evidence").fetchone()[0] == 1

    first = reconcile_required(workspace, run_id="RUN_000001")
    second = reconcile_required(workspace, run_id="RUN_000001")
    assert (first.closed, first.pending, first.supports_removed) == (0, 1, 1)
    assert (second.closed, second.pending, second.supports_removed) == (0, 1, 0)
    with _connect(workspace) as connection:
        assert connection.execute(
            "SELECT status FROM reconciliation_required"
        ).fetchone()[0] == "open"
        assert connection.execute("SELECT status FROM facts").fetchone()[0] == "unsupported"

    merged = merge_candidate_batch(
        workspace,
        run_id="RUN_000001",
        batch_id=correction.batch_id or "",
    )
    assert merged.reconciliation_closed == 1
    with _connect(workspace) as connection:
        assert connection.execute(
            "SELECT status FROM reconciliation_required"
        ).fetchone()[0] == "closed"
        assert connection.execute("SELECT COUNT(*) FROM effective_facts").fetchone()[0] == 1


def _workspace_with_candidates(
    tmp_path: Path,
    candidates: list[dict[str, object]],
) -> tuple[Path, str, tuple[str, ...]]:
    workspace = tmp_path / "workspace"
    initialize_workspace(workspace)
    migrate_workspace_database(workspace)
    _insert_evidence(workspace)
    input_path = workspace / "ai" / "inbox" / "candidates.jsonl"
    input_path.write_text(
        "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in candidates),
        encoding="utf-8",
        newline="\n",
    )
    assert main(["candidates", "validate", str(workspace), "--input", str(input_path)]) == 0
    with _connect(workspace) as connection:
        batch_id = connection.execute(
            "SELECT batch_id FROM candidate_batches ORDER BY batch_id DESC LIMIT 1"
        ).fetchone()[0]
        candidate_ids = tuple(
            row[0]
            for row in connection.execute(
                "SELECT candidate_record_id FROM candidate_records WHERE batch_id = ? ORDER BY line_number",
                (batch_id,),
            ).fetchall()
        )
    return workspace, str(batch_id), candidate_ids


def _insert_evidence(workspace: Path) -> None:
    digest = hashlib.sha256(EVIDENCE.encode("utf-8")).hexdigest()
    with _connect(workspace) as connection:
        connection.execute(
            """
            INSERT INTO sources (
                source_id, logical_name, source_type, source_subtype, authority_level,
                first_seen_at, last_seen_at, current_revision_id, status, created_at, updated_at
            ) VALUES ('SRC_000001', 'schema.sql', 'ddl', NULL, 'authoritative',
                      ?, ?, NULL, 'active', ?, ?)
            """,
            (TIMESTAMP,) * 4,
        )
        connection.execute(
            """
            INSERT INTO source_revisions (
                source_revision_id, source_id, revision_number, content_hash, normalized_hash,
                file_path, file_size, detected_at, status, created_at
            ) VALUES ('REV_000001', 'SRC_000001', 1, ?, NULL, 'corpus/active/schema.sql',
                      ?, ?, 'active', ?)
            """,
            (digest, len(EVIDENCE.encode("utf-8")), TIMESTAMP, TIMESTAMP),
        )
        connection.execute(
            "UPDATE sources SET current_revision_id = 'REV_000001' WHERE source_id = 'SRC_000001'"
        )
        connection.execute(
            """
            INSERT INTO chunks (
                chunk_id, source_revision_id, sequence, text, text_hash,
                metadata_json, status, created_at
            ) VALUES ('CHK_000001', 'REV_000001', 1, ?, ?, '{}', 'active', ?)
            """,
            (EVIDENCE, digest, TIMESTAMP),
        )
        connection.commit()


def _fact(candidate_id: str, *, value: str = "database_table", entity: str = "CLIENTI"):
    return {
        "assertion_type": "explicit",
        "candidate_id": candidate_id,
        "chunk_id": "CHK_000001",
        "confidence": "high",
        "entity_name": entity,
        "evidence_text": EVIDENCE,
        "fact_type": "database_table",
        "property_name": "object_type",
        "property_value": value,
        "record_type": "candidate_fact",
        "source_revision_id": "REV_000001",
    }


def _relation(candidate_id: str):
    return {
        "assertion_type": "explicit",
        "candidate_id": candidate_id,
        "chunk_id": "CHK_000001",
        "confidence": "high",
        "evidence_text": EVIDENCE,
        "record_type": "candidate_relation",
        "relation_type": "references",
        "source_entity": "CLIENTI",
        "source_revision_id": "REV_000001",
        "target_entity": "ORDINI",
    }


def _connect(workspace: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(workspace / "workspace.sqlite")
    connection.row_factory = sqlite3.Row
    return connection


def _insert_raw_decision(
    connection: sqlite3.Connection,
    *,
    decision_id: str,
    subject_id: str,
    supersedes_decision_id: str,
) -> None:
    connection.execute(
        """
        INSERT INTO review_decisions (
            decision_id, subject_type, subject_id, actor_type, actor_id,
            outcome, reason, run_id, created_at, supersedes_decision_id,
            expected_head_decision_id, idempotency_key,
            request_payload_hash, semantic_payload_hash,
            policy_id, policy_version, request_payload_json, semantic_payload_json
        ) VALUES (?, 'candidate_record', ?, 'human', 'reviewer', 'confirmed', 'test',
                  NULL, ?, ?, NULL, ?, 'hash', 'semantic', NULL, NULL, '{}', '{}')
        """,
        (decision_id, subject_id, TIMESTAMP, supersedes_decision_id, decision_id),
    )
