from __future__ import annotations

import hashlib
import json
import sqlite3
import socket
import urllib.request
from pathlib import Path

import pytest

from dsl_mngr.cli.app import main
from dsl_mngr.core.ai_package import compute_package_hash_from_manifest
from dsl_mngr.core.migrations import MIGRATIONS, Migration, apply_migrations
from dsl_mngr.core.workspace import initialize_workspace


NOW = "2026-09-14T10:00:00+02:00"
CHUNK_TEXT = "Il cliente può sospendere un ordine ancora aperto.\r\n"
FRAGMENT_TEXT = "CREATE TABLE CLIENTI (ID INTEGER PRIMARY KEY);\n"


def test_plan_is_persisted_deterministic_explainable_and_policy_specific(tmp_path, capsys):
    workspace = _workspace_with_evidence(tmp_path / "workspace", capsys)

    assert main(["ai", "evidence", "plan", str(workspace), "--policy", "technical_extraction"]) == 0
    output = capsys.readouterr().out
    assert "Selection plan: AISEL_000001" in output
    assert "Included: 1" in output
    assert "Excluded: 1" in output

    with _connect(workspace) as connection:
        first = connection.execute(
            "SELECT * FROM ai_evidence_selection_plans WHERE selection_plan_id = 'AISEL_000001'"
        ).fetchone()
        rows = connection.execute(
            "SELECT evidence_id, outcome, selection_rank, reason_codes_json "
            "FROM ai_evidence_selection_items ORDER BY evidence_id"
        ).fetchall()
        assert connection.execute("SELECT COUNT(*) FROM ai_packages").fetchone()[0] == 0
    assert first["run_id"] == "RUN_000001"
    assert first["route_id"] == "technical_extraction"
    assert [(row["evidence_id"], row["outcome"]) for row in rows] == [
        ("CHK_000001", "excluded"),
        ("FRAG_000001", "included"),
    ]
    assert json.loads(rows[0]["reason_codes_json"]) == ["evidence_kind_excluded"]
    assert rows[1]["selection_rank"] == 1
    assert not any((workspace / "ai" / "outbox").iterdir())

    assert main(["ai", "evidence", "list", str(workspace), "--plan", "AISEL_000001"]) == 0
    listed = capsys.readouterr().out
    assert "CHK_000001" in listed and "FRAG_000001" in listed
    assert main(
        [
            "ai",
            "evidence",
            "explain",
            str(workspace),
            "--plan",
            "AISEL_000001",
            "CHK_000001",
        ]
    ) == 0
    explained = json.loads(capsys.readouterr().out)
    assert explained["item"]["reason_codes"] == ["evidence_kind_excluded"]
    with _connect(workspace) as connection:
        assert connection.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 1

    assert main(["ai", "evidence", "plan", str(workspace), "--policy", "technical_extraction"]) == 0
    capsys.readouterr()
    assert main(["ai", "evidence", "plan", str(workspace), "--policy", "domain_interpretation"]) == 0
    capsys.readouterr()
    with _connect(workspace) as connection:
        plans = connection.execute(
            "SELECT selection_plan_id, policy_id, selection_plan_hash, "
            "relevant_state_hash, included_count "
            "FROM ai_evidence_selection_plans ORDER BY selection_plan_id"
        ).fetchall()
    assert plans[0]["selection_plan_hash"] == plans[1]["selection_plan_hash"]
    assert plans[0]["relevant_state_hash"] == plans[1]["relevant_state_hash"]
    assert plans[2]["policy_id"] == "domain_interpretation"
    assert plans[2]["included_count"] == 2

    with _connect(workspace) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="append_only"):
            connection.execute(
                "UPDATE ai_evidence_selection_plans SET route_id = 'x' "
                "WHERE selection_plan_id = 'AISEL_000001'"
            )


def test_package_from_plan_contains_exact_ordered_selection_and_hashes(tmp_path, capsys):
    workspace = _workspace_with_evidence(tmp_path / "workspace", capsys)
    assert main(["ai", "evidence", "plan", str(workspace), "--policy", "technical_extraction"]) == 0
    capsys.readouterr()

    assert main(["ai", "package", str(workspace), "--selection-plan", "AISEL_000001"]) == 0
    output = capsys.readouterr().out
    assert "Selection plan: AISEL_000001" in output
    package_dir = workspace / "ai" / "outbox" / "AIPKG_000001"
    assert "CHK_000001" not in (package_dir / "content.md").read_text(encoding="utf-8")
    assert "FRAG_000001" in (package_dir / "content.md").read_text(encoding="utf-8")
    selection = _read_json(package_dir / "selection_plan.json")
    manifest = _read_json(package_dir / "package_manifest.json")
    source_manifest = _read_json(package_dir / "source_manifest.json")
    assert selection["selection_plan_id"] == "AISEL_000001"
    assert manifest["selection"]["selection_plan_id"] == "AISEL_000001"
    assert manifest["selection"]["ordered_evidence"] == [
        {"evidence_id": "FRAG_000001", "evidence_kind": "fragment", "rank": 1}
    ]
    assert source_manifest["selection"]["selection_plan_hash"] == selection[
        "selection_plan_hash"
    ]
    assert "selection_plan" in manifest["files"]
    assert manifest["package_hash"] == compute_package_hash_from_manifest(manifest)
    with _connect(workspace) as connection:
        package = connection.execute("SELECT * FROM ai_packages").fetchone()
    assert package["selection_plan_id"] == "AISEL_000001"
    assert package["chunk_count"] == 0
    assert package["fragment_count"] == 1

    assert main(
        ["ai", "package", str(workspace), "--selection-policy", "domain_interpretation"]
    ) == 0
    policy_output = capsys.readouterr().out
    assert "Selection plan: AISEL_000002" in policy_output
    policy_package = _read_json(
        workspace / "ai" / "outbox" / "AIPKG_000002" / "package_manifest.json"
    )
    assert policy_package["selection"]["selection_plan_id"] == "AISEL_000002"
    assert len(policy_package["selection"]["ordered_evidence"]) == 2


def test_stale_and_empty_selection_fail_with_code_4_without_package(tmp_path, capsys):
    workspace = _workspace_with_evidence(tmp_path / "stale", capsys)
    assert main(["ai", "evidence", "plan", str(workspace), "--policy", "technical_extraction"]) == 0
    capsys.readouterr()
    with _connect(workspace) as connection:
        connection.execute("UPDATE chunks SET status = 'inactive' WHERE chunk_id = 'CHK_000001'")
        connection.commit()
    assert main(["ai", "package", str(workspace), "--selection-plan", "AISEL_000001"]) == 4
    error = capsys.readouterr().err
    assert "selection_plan_stale" in error
    with _connect(workspace) as connection:
        assert connection.execute("SELECT COUNT(*) FROM ai_packages").fetchone()[0] == 0
    assert not any((workspace / "ai" / "outbox").iterdir())

    empty = _workspace_with_evidence(tmp_path / "empty", capsys, include_fragment=False)
    assert main(["ai", "package", str(empty), "--selection-policy", "technical_extraction"]) == 4
    error = capsys.readouterr().err
    assert "no_ai_eligible_evidence" in error
    with _connect(empty) as connection:
        assert connection.execute("SELECT COUNT(*) FROM ai_packages").fetchone()[0] == 0
        assert connection.execute("SELECT included_count FROM ai_evidence_selection_plans").fetchone()[0] == 0
    assert not any((empty / "ai" / "outbox").iterdir())


def test_policy_paths_and_unknown_keys_are_rejected_without_partial_plan(tmp_path, capsys):
    workspace = _workspace_with_evidence(tmp_path / "workspace", capsys)
    assert main(["ai", "evidence", "plan", str(workspace), "--policy", "../escape"]) == 2
    assert "invalid_selection_policy" in capsys.readouterr().err
    bad = workspace / "configs" / "ai_selection" / "bad.yaml"
    bad.write_text(
        (workspace / "configs" / "ai_selection" / "technical_extraction.yaml").read_text(
            encoding="utf-8"
        ).replace("policy_id: technical_extraction", "policy_id: bad")
        + "unknown:\n  option: true\n",
        encoding="utf-8",
        newline="\n",
    )
    assert main(["ai", "evidence", "plan", str(workspace), "--policy", "bad"]) == 2
    assert "Unsupported AI selection policy section" in capsys.readouterr().err
    with _connect(workspace) as connection:
        assert connection.execute("SELECT COUNT(*) FROM ai_evidence_selection_plans").fetchone()[0] == 0


def test_coverage_heads_and_budgets_change_declared_outcomes(tmp_path, capsys):
    workspace = _workspace_with_evidence(tmp_path / "workspace", capsys)
    _insert_deterministic_candidate(workspace)

    assert main(["ai", "evidence", "plan", str(workspace), "--policy", "technical_extraction"]) == 0
    capsys.readouterr()
    with _connect(workspace) as connection:
        pending = connection.execute(
            "SELECT coverage_state, outcome FROM ai_evidence_selection_items "
            "WHERE selection_plan_id = 'AISEL_000001' AND evidence_id = 'FRAG_000001'"
        ).fetchone()
    assert tuple(pending) == ("pending", "included")

    _insert_review_head(workspace, decision_id="RDEC_000001", outcome="confirmed")
    assert main(["ai", "evidence", "plan", str(workspace), "--policy", "technical_extraction"]) == 0
    capsys.readouterr()
    with _connect(workspace) as connection:
        confirmed = connection.execute(
            "SELECT coverage_state, outcome, reason_codes_json "
            "FROM ai_evidence_selection_items "
            "WHERE selection_plan_id = 'AISEL_000002' AND evidence_id = 'FRAG_000001'"
        ).fetchone()
    assert confirmed["coverage_state"] == "confirmed"
    assert confirmed["outcome"] == "excluded"
    assert json.loads(confirmed["reason_codes_json"]) == [
        "deterministic_coverage_excluded"
    ]
    assert main(["ai", "package", str(workspace), "--selection-plan", "AISEL_000001"]) == 4
    assert "selection_plan_stale" in capsys.readouterr().err

    _insert_review_head(
        workspace,
        decision_id="RDEC_000002",
        outcome="rejected",
        supersedes="RDEC_000001",
    )
    assert main(["ai", "evidence", "plan", str(workspace), "--policy", "technical_extraction"]) == 0
    capsys.readouterr()
    with _connect(workspace) as connection:
        rejected = connection.execute(
            "SELECT coverage_state, outcome FROM ai_evidence_selection_items "
            "WHERE selection_plan_id = 'AISEL_000003' AND evidence_id = 'FRAG_000001'"
        ).fetchone()
    assert tuple(rejected) == ("rejected", "included")

    _insert_corrected_candidate(workspace)
    assert main(["ai", "evidence", "plan", str(workspace), "--policy", "technical_extraction"]) == 0
    capsys.readouterr()
    with _connect(workspace) as connection:
        superseded = connection.execute(
            "SELECT coverage_state, outcome FROM ai_evidence_selection_items "
            "WHERE selection_plan_id = 'AISEL_000004' AND evidence_id = 'FRAG_000001'"
        ).fetchone()
    assert tuple(superseded) == ("superseded_non_leaf", "included")

    limited = workspace / "configs" / "ai_selection" / "limited.yaml"
    limited.write_text(
        (workspace / "configs" / "ai_selection" / "domain_interpretation.yaml")
        .read_text(encoding="utf-8")
        .replace("policy_id: domain_interpretation", "policy_id: limited")
        .replace("max_selected_evidence: 10000", "max_selected_evidence: 1"),
        encoding="utf-8",
        newline="\n",
    )
    assert main(["ai", "evidence", "plan", str(workspace), "--policy", "limited"]) == 0
    capsys.readouterr()
    with _connect(workspace) as connection:
        budget_excluded = connection.execute(
            "SELECT reason_codes_json FROM ai_evidence_selection_items "
            "WHERE selection_plan_id = 'AISEL_000005' AND outcome = 'excluded'"
        ).fetchone()[0]
    assert json.loads(budget_excluded) == [
        "lower_rank",
        "selection_item_budget_exceeded",
    ]


def test_registry_provenance_for_supported_fragment_producers(tmp_path, capsys):
    workspace = _workspace_with_evidence(tmp_path / "workspace", capsys)
    rows = (
        ("FRAG_000002", "xml_form", "parse_xml_form", "1.0"),
        ("FRAG_000003", "sql_procedure", "parse_db_code", "1.0"),
        ("FRAG_000004", "log_event", "parse_log", "1.0"),
        ("FRAG_000005", "excel_region", "workbook_manifest", "1"),
    )
    with _connect(workspace) as connection:
        for sequence, (fragment_id, fragment_type, producer, version) in enumerate(rows, start=3):
            text = f"evidence {fragment_id}\n"
            connection.execute(
                """
                INSERT INTO source_fragments (
                    fragment_id, source_revision_id, fragment_type, sequence,
                    path_or_selector, line_start, line_end, char_start, char_end,
                    text, text_hash, metadata_json, status, created_at
                ) VALUES (?, 'REV_000001', ?, ?, ?, 1, 1, 0, ?, ?, ?, ?, 'active', ?)
                """,
                (
                    fragment_id,
                    fragment_type,
                    sequence,
                    f"/{fragment_type}/{sequence}",
                    len(text),
                    text,
                    hashlib.sha256(text.encode()).hexdigest(),
                    json.dumps({"parser": producer, "parser_version": version}),
                    NOW,
                ),
            )
        connection.commit()
    policy_path = workspace / "configs" / "ai_selection" / "provenance.yaml"
    policy_path.write_text(
        (workspace / "configs" / "ai_selection" / "domain_interpretation.yaml")
        .read_text(encoding="utf-8")
        .replace("policy_id: domain_interpretation", "policy_id: provenance")
        .replace(
            "producers: []",
            'producers: ["chunk_docling","parse_ddl","parse_xml_form","parse_db_code","parse_log","workbook_manifest"]',
        )
        .replace("producer_versions: []", 'producer_versions: ["1.0","1"]'),
        encoding="utf-8",
        newline="\n",
    )
    assert main(["ai", "evidence", "plan", str(workspace), "--policy", "provenance"]) == 0
    assert "Included: 6" in capsys.readouterr().out
    with _connect(workspace) as connection:
        states = {
            row["evidence_id"]: row["coverage_state"]
            for row in connection.execute(
                "SELECT evidence_id, coverage_state FROM ai_evidence_selection_items"
            ).fetchall()
        }
    assert states["CHK_000001"] == "no_rule_applicable"
    for fragment_id, *_ in rows:
        assert states[fragment_id] == "applicable_no_candidate"
    assert main(
        [
            "ai",
            "evidence",
            "explain",
            str(workspace),
            "--plan",
            "AISEL_000001",
            "FRAG_000005",
        ]
    ) == 0
    explanation = json.loads(capsys.readouterr().out)
    assert "producer=workbook_manifest" in explanation["item"]["matched_criteria"]


def test_real_v10_upgrade_idempotence_and_atomic_rollback(tmp_path):
    workspace = tmp_path / "upgrade"
    initialize_workspace(workspace)
    database = workspace / "workspace.sqlite"
    with sqlite3.connect(database) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        first = apply_migrations(connection, migrations=MIGRATIONS[:10])
        upgraded = apply_migrations(connection, migrations=MIGRATIONS)
        repeated = apply_migrations(connection, migrations=MIGRATIONS)
        assert [migration.version for migration in first.applied] == list(range(1, 11))
        assert [migration.version for migration in upgraded.applied] == [11, 12]
        assert repeated.applied_count == 0
        assert repeated.skipped_count == 12
        columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(ai_packages)")
        }
        assert "selection_plan_id" in columns

    rollback_workspace = tmp_path / "rollback"
    initialize_workspace(rollback_workspace)
    rollback_database = rollback_workspace / "workspace.sqlite"
    with sqlite3.connect(rollback_database) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        apply_migrations(connection, migrations=MIGRATIONS[:10])
        broken = Migration(
            version=11,
            name="broken_ai_evidence_selection_schema",
            statements=(*MIGRATIONS[10].statements, "INSERT INTO missing_table VALUES (1)"),
        )
        with pytest.raises(sqlite3.OperationalError, match="missing_table"):
            apply_migrations(connection, migrations=(*MIGRATIONS[:10], broken))
        assert connection.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0] == 10
        table = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' "
            "AND name = 'ai_evidence_selection_plans'"
        ).fetchone()
        assert table is None
        columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(ai_packages)")
        }
        assert "selection_plan_id" not in columns


def test_profile_conflict_hard_budget_and_invalid_metadata_fail_closed(tmp_path, capsys):
    workspace = _workspace_with_evidence(tmp_path / "workspace", capsys)
    profile = workspace / "configs" / "workers" / "ai_package.selection.yaml"
    profile.write_text(
        (workspace / "configs" / "workers" / "ai_package.default.yaml").read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
        newline="\n",
    )
    assert main(
        [
            "ai",
            "evidence",
            "plan",
            str(workspace),
            "--policy",
            "domain_interpretation",
            "--profile",
            "ai_package.selection",
        ]
    ) == 0
    capsys.readouterr()
    profile.write_text(
        profile.read_text(encoding="utf-8").replace(
            "max_evidence_chars: 20000", "max_evidence_chars: 19999"
        ),
        encoding="utf-8",
        newline="\n",
    )
    assert main(
        [
            "ai",
            "package",
            str(workspace),
            "--selection-plan",
            "AISEL_000001",
            "--profile",
            "ai_package.selection",
        ]
    ) == 2
    assert "selection_profile_conflict" in capsys.readouterr().err
    assert not any((workspace / "ai" / "outbox").iterdir())

    hard = workspace / "configs" / "ai_selection" / "hard.yaml"
    hard.write_text(
        (workspace / "configs" / "ai_selection" / "domain_interpretation.yaml")
        .read_text(encoding="utf-8")
        .replace("policy_id: domain_interpretation", "policy_id: hard")
        .replace("max_examined_evidence: 100000", "max_examined_evidence: 1"),
        encoding="utf-8",
        newline="\n",
    )
    assert main(["ai", "evidence", "plan", str(workspace), "--policy", "hard"]) == 4
    assert "selection_examined_budget_exceeded" in capsys.readouterr().err
    with _connect(workspace) as connection:
        assert connection.execute("SELECT COUNT(*) FROM ai_evidence_selection_plans").fetchone()[0] == 1

    with _connect(workspace) as connection:
        connection.execute(
            "UPDATE chunks SET metadata_json = '{broken' WHERE chunk_id = 'CHK_000001'"
        )
        connection.commit()
    assert main(
        ["ai", "evidence", "plan", str(workspace), "--policy", "domain_interpretation"]
    ) == 0
    capsys.readouterr()
    with _connect(workspace) as connection:
        invalid = connection.execute(
            "SELECT outcome, reason_codes_json FROM ai_evidence_selection_items "
            "WHERE selection_plan_id = 'AISEL_000002' AND evidence_id = 'CHK_000001'"
        ).fetchone()
    assert invalid["outcome"] == "excluded"
    assert json.loads(invalid["reason_codes_json"]) == ["invalid_evidence_metadata"]


def test_selection_planning_is_offline(tmp_path, capsys, monkeypatch):
    def reject(*_args, **_kwargs):
        raise AssertionError("AI evidence selection must not access the network")

    monkeypatch.setattr(socket, "create_connection", reject)
    monkeypatch.setattr(urllib.request, "urlopen", reject)
    workspace = _workspace_with_evidence(tmp_path / "workspace", capsys)
    assert main(
        ["ai", "evidence", "plan", str(workspace), "--policy", "domain_interpretation"]
    ) == 0
    assert "Selection plan: AISEL_000001" in capsys.readouterr().out


def _workspace_with_evidence(
    workspace: Path, capsys, *, include_fragment: bool = True
) -> Path:
    assert main(["init", str(workspace)]) == 0
    assert main(["db", "init", str(workspace)]) == 0
    capsys.readouterr()
    chunk_hash = hashlib.sha256(CHUNK_TEXT.encode("utf-8")).hexdigest()
    fragment_hash = hashlib.sha256(FRAGMENT_TEXT.encode("utf-8")).hexdigest()
    with _connect(workspace) as connection:
        connection.execute(
            """
            INSERT INTO sources (
                source_id, logical_name, source_type, source_subtype, authority_level,
                first_seen_at, last_seen_at, current_revision_id, status, created_at, updated_at
            ) VALUES ('SRC_000001', 'mixed.sql', 'ddl', 'schema', 'technical_documentation',
                      ?, ?, NULL, 'active', ?, ?)
            """,
            (NOW, NOW, NOW, NOW),
        )
        connection.execute(
            """
            INSERT INTO source_revisions (
                source_revision_id, source_id, revision_number, content_hash, normalized_hash,
                file_path, file_size, detected_at, status, created_at
            ) VALUES ('REV_000001', 'SRC_000001', 1, ?, NULL,
                      'corpus/active/mixed.sql', ?, ?, 'active', ?)
            """,
            (fragment_hash, len(FRAGMENT_TEXT), NOW, NOW),
        )
        connection.execute(
            "UPDATE sources SET current_revision_id = 'REV_000001' WHERE source_id = 'SRC_000001'"
        )
        connection.execute(
            """
            INSERT INTO chunks (
                chunk_id, source_revision_id, sequence, text, text_hash,
                metadata_json, status, created_at
            ) VALUES ('CHK_000001', 'REV_000001', 1, ?, ?, ?, 'active', ?)
            """,
            (
                CHUNK_TEXT,
                chunk_hash,
                json.dumps(
                    {"chunker": "chunk_docling", "chunker_version": "1.0", "start_char": 0, "end_char": len(CHUNK_TEXT)}
                ),
                NOW,
            ),
        )
        if include_fragment:
            connection.execute(
                """
                INSERT INTO source_fragments (
                    fragment_id, source_revision_id, fragment_type, sequence,
                    path_or_selector, line_start, line_end, char_start, char_end,
                    text, text_hash, metadata_json, status, created_at
                ) VALUES ('FRAG_000001', 'REV_000001', 'ddl_table', 2,
                          'table/CLIENTI', 1, 1, 0, ?, ?, ?, ?, 'active', ?)
                """,
                (
                    len(FRAGMENT_TEXT),
                    FRAGMENT_TEXT,
                    fragment_hash,
                    json.dumps({"parser": "parse_ddl", "parser_version": "1.0"}),
                    NOW,
                ),
            )
        connection.commit()
    return workspace


def _connect(workspace: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(workspace / "workspace.sqlite")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _insert_deterministic_candidate(workspace: Path) -> None:
    payload = json.dumps(
        {
            "producer_type": "deterministic_rule",
            "rule_id": "ddl_table_fact",
            "rule_version": "1",
        },
        sort_keys=True,
    )
    with _connect(workspace) as connection:
        connection.execute(
            """
            INSERT INTO runs (
                run_id, run_type, status, started_at, finished_at, parent_run_id,
                input_json, output_json, created_at, updated_at
            ) VALUES ('RUN_DERIVE', 'candidate_derivation', 'completed', ?, ?, NULL,
                      '{}', '{}', ?, ?)
            """,
            (NOW, NOW, NOW, NOW),
        )
        connection.execute(
            """
            INSERT INTO candidate_batches (
                batch_id, run_id, input_path, origin_type, origin_ref,
                total_records, accepted_count, rejected_count, status, created_at, updated_at
            ) VALUES ('CBATCH_DERIVE', 'RUN_DERIVE', NULL, 'deterministic_derivation',
                      'derive://test', 1, 1, 0, 'completed', ?, ?)
            """,
            (NOW, NOW),
        )
        connection.execute(
            """
            INSERT INTO candidate_records (
                candidate_record_id, batch_id, run_id, line_number, candidate_id,
                record_type, source_revision_id, chunk_id, fragment_id, assertion_type,
                confidence, evidence_text, payload_json, created_at,
                supersedes_candidate_record_id
            ) VALUES ('CREC_DERIVE', 'CBATCH_DERIVE', 'RUN_DERIVE', 1, 'CAND_DERIVE',
                      'candidate_fact', 'REV_000001', NULL, 'FRAG_000001', 'explicit',
                      'high', ?, ?, ?, NULL)
            """,
            (FRAGMENT_TEXT, payload, NOW),
        )
        connection.execute(
            """
            INSERT INTO candidate_lineage (
                candidate_record_id, root_candidate_record_id,
                parent_candidate_record_id, correction_group_id
            ) VALUES ('CREC_DERIVE', 'CREC_DERIVE', NULL, NULL)
            """
        )
        connection.commit()


def _insert_review_head(
    workspace: Path,
    *,
    decision_id: str,
    outcome: str,
    supersedes: str | None = None,
) -> None:
    with _connect(workspace) as connection:
        connection.execute(
            """
            INSERT INTO review_decisions (
                decision_id, subject_type, subject_id, actor_type, actor_id,
                outcome, reason, run_id, created_at, supersedes_decision_id,
                expected_head_decision_id, idempotency_key, request_payload_hash,
                semantic_payload_hash, policy_id, policy_version,
                request_payload_json, semantic_payload_json
            ) VALUES (?, 'candidate_record', 'CREC_DERIVE', 'system', 'test',
                      ?, 'test', NULL, ?, ?, ?, ?, ?, ?, NULL, NULL, '{}', '{}')
            """,
            (
                decision_id,
                outcome,
                NOW,
                supersedes,
                supersedes,
                decision_id,
                hashlib.sha256((decision_id + "request").encode()).hexdigest(),
                hashlib.sha256((decision_id + "semantic").encode()).hexdigest(),
            ),
        )
        if supersedes is None:
            connection.execute(
                """
                INSERT INTO review_subject_heads (
                    subject_type, subject_id, decision_id, updated_at
                ) VALUES ('candidate_record', 'CREC_DERIVE', ?, ?)
                """,
                (decision_id, NOW),
            )
        else:
            connection.execute(
                """
                UPDATE review_subject_heads SET decision_id = ?, updated_at = ?
                WHERE subject_type = 'candidate_record' AND subject_id = 'CREC_DERIVE'
                """,
                (decision_id, NOW),
            )
        connection.commit()


def _insert_corrected_candidate(workspace: Path) -> None:
    with _connect(workspace) as connection:
        connection.execute(
            """
            INSERT INTO runs (
                run_id, run_type, status, started_at, finished_at, parent_run_id,
                input_json, output_json, created_at, updated_at
            ) VALUES ('RUN_CORRECT', 'candidate_correction', 'completed', ?, ?, NULL,
                      '{}', '{}', ?, ?)
            """,
            (NOW, NOW, NOW, NOW),
        )
        connection.execute(
            """
            INSERT INTO candidate_batches (
                batch_id, run_id, input_path, origin_type, origin_ref,
                total_records, accepted_count, rejected_count, status, created_at, updated_at
            ) VALUES ('CBATCH_CORRECT', 'RUN_CORRECT', NULL, 'human_correction',
                      'correction://test', 1, 1, 0, 'completed', ?, ?)
            """,
            (NOW, NOW),
        )
        connection.execute(
            """
            INSERT INTO candidate_records (
                candidate_record_id, batch_id, run_id, line_number, candidate_id,
                record_type, source_revision_id, chunk_id, fragment_id, assertion_type,
                confidence, evidence_text, payload_json, created_at,
                supersedes_candidate_record_id
            ) VALUES ('CREC_CORRECT', 'CBATCH_CORRECT', 'RUN_CORRECT', 1, 'CAND_CORRECT',
                      'candidate_fact', 'REV_000001', NULL, 'FRAG_000001', 'explicit',
                      'high', ?, '{}', ?, 'CREC_DERIVE')
            """,
            (FRAGMENT_TEXT, NOW),
        )
        connection.execute(
            """
            INSERT INTO candidate_lineage (
                candidate_record_id, root_candidate_record_id,
                parent_candidate_record_id, correction_group_id
            ) VALUES ('CREC_CORRECT', 'CREC_DERIVE', 'CREC_DERIVE', 'CORR_TEST')
            """
        )
        connection.commit()


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))
