from __future__ import annotations

import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import urllib.request
from pathlib import Path

import pytest

from dsl_mngr.cli.app import main
from dsl_mngr.core.batch_consolidation import (
    BatchConsolidationError,
    consolidate_batch,
)
from dsl_mngr.core.candidate_derivation import DERIVATION_RULE_CATALOG
from dsl_mngr.core.candidate_review import CandidateReviewService
from dsl_mngr.core.config import dump_simple_yaml, load_config
from dsl_mngr.core.migrations import migrate_workspace_database
from dsl_mngr.core.workspace import initialize_workspace


TESTS_DIR = Path(__file__).parent
DDL_FIXTURE = TESTS_DIR / "fixtures" / "ddl" / "schema_ordini.sql"
XML_FIXTURE = TESTS_DIR / "fixtures" / "xml_forms" / "form_cliente.xml"
DDL_POLICIES = tuple(
    contract.automatic_review_policy
    for contract in DERIVATION_RULE_CATALOG.values()
    if contract.parser_kind == "ddl"
)
DDL_XML_POLICIES = tuple(
    contract.automatic_review_policy
    for contract in DERIVATION_RULE_CATALOG.values()
    if contract.parser_kind in {"ddl", "xml_form"}
)


def test_slice_22_mixed_inputs_policy_reconcile_and_no_network(
    tmp_path, monkeypatch
):
    def reject_network(*args, **kwargs):
        del args, kwargs
        raise AssertionError("Slice 22 must not access the network")

    monkeypatch.setattr(socket, "create_connection", reject_network)
    monkeypatch.setattr(urllib.request, "urlopen", reject_network)
    workspace = _workspace(tmp_path / "mixed")
    _copy(DDL_FIXTURE, workspace, "01_schema.sql")
    (workspace / "corpus" / "active" / "02_unsupported.csv").write_text(
        "id,value\n1,unsupported\n", encoding="utf-8", newline="\n"
    )
    _set_policies(workspace, DDL_POLICIES)

    result = consolidate_batch(workspace, reconcile=True)

    assert result["catalog_version"] == "result_catalog_v1"
    assert result["status"] == "completed"
    assert result["exit_code"] == 0
    assert result["counters"]["parse_completed"] == 1
    assert result["counters"]["parse_skipped"] == 1
    assert result["counters"]["candidates_produced"] > 0
    assert result["counters"]["auto_confirmed"] == result["counters"]["candidates_produced"]
    assert result["counters"]["merged_candidates"] == result["counters"]["candidates_produced"]
    assert [phase["name"] for phase in result["phases"]] == [
        "parse",
        "derive",
        "review",
        "merge",
        "reconcile",
    ]
    assert [phase["status"] for phase in result["phases"]] == [
        "completed",
        "completed",
        "completed",
        "completed",
        "completed",
    ]
    assert all(
        phase["transitions"] == [{"from": "pending", "to": "running"}, {"from": "running", "to": "completed"}]
        for phase in result["phases"]
    )
    report = _read_json(workspace / result["artifact_paths"][1])
    checkpoint = _read_json(workspace / result["artifact_paths"][0])
    assert report == result
    assert checkpoint["status"] == "completed"
    assert [checkpoint["phases"][name]["status"] for name in checkpoint["phases"]] == [
        "completed",
        "completed",
        "completed",
        "completed",
        "completed",
    ]


def test_slice_22_policy_absent_version_mismatch_and_zero_candidates(tmp_path, capsys):
    empty_workspace = _workspace(tmp_path / "zero")
    (empty_workspace / "corpus" / "active" / "notes.csv").write_text(
        "id,value\n1,unsupported\n", encoding="utf-8", newline="\n"
    )

    assert main(["batch", "consolidate", str(empty_workspace)]) == 4
    captured = capsys.readouterr()
    empty_result = json.loads(captured.out)
    assert captured.err == ""
    assert empty_result["reason"] == "no_merge_eligible_candidates"
    assert empty_result["counters"]["candidate_batches"] == 0
    assert empty_result["counters"]["candidates_produced"] == 0
    assert empty_result["counters"]["parse_skipped"] == 1

    workspace = _workspace(tmp_path / "policy")
    _copy(DDL_FIXTURE, workspace, "schema.sql")
    absent = consolidate_batch(workspace)
    assert absent["status"] == "blocked"
    assert absent["exit_code"] == 4
    assert absent["counters"]["auto_confirmed"] == 0
    assert absent["counters"]["review_pending"] == absent["counters"]["candidates_produced"]
    assert _count(workspace, "review_decisions") == 0

    wrong_versions = tuple(f"{policy.rsplit('/', 1)[0]}/999" for policy in DDL_POLICIES)
    _set_policies(workspace, wrong_versions)
    mismatch = consolidate_batch(workspace, resume_run_id=absent["run_id"])
    assert mismatch["exit_code"] == 4
    assert mismatch["counters"]["policy_skipped_version"] == mismatch["counters"][
        "candidates_produced"
    ]
    assert _count(workspace, "review_decisions") == 0

    _set_policies(workspace, DDL_POLICIES)
    enabled = consolidate_batch(workspace, resume_run_id=mismatch["run_id"])
    assert enabled["exit_code"] == 0
    assert enabled["counters"]["auto_confirmed"] == enabled["counters"][
        "candidates_produced"
    ]
    assert enabled["counters"]["merged_candidates"] == enabled["counters"][
        "candidates_produced"
    ]


def test_slice_22_mixed_review_default_and_strict_rollback(tmp_path):
    default_workspace = _workspace(tmp_path / "default")
    _copy(DDL_FIXTURE, default_workspace, "schema.sql")
    blocked = consolidate_batch(default_workspace)
    candidate_ids = _candidate_ids(default_workspace)
    assert len(candidate_ids) >= 4
    _apply_mixed_review(default_workspace, candidate_ids)

    mixed = consolidate_batch(default_workspace, resume_run_id=blocked["run_id"])
    assert mixed["exit_code"] == 0
    assert mixed["reason"] == "merge_completed_with_skips"
    assert mixed["counters"]["merged_candidates"] == 1
    assert mixed["counters"]["review_confirmed"] == 1
    assert mixed["counters"]["review_rejected"] == 1
    assert mixed["counters"]["review_superseded"] == 1
    assert mixed["counters"]["review_pending"] > 0
    assert mixed["counters"]["skipped_pending"] > 0
    assert mixed["counters"]["skipped_rejected"] == 1
    assert mixed["counters"]["skipped_superseded"] == 1
    merge_result = next(
        phase["result"] for phase in mixed["phases"] if phase["name"] == "merge"
    )
    assert merge_result["merged_candidate_record_ids"] == sorted(
        merge_result["merged_candidate_record_ids"]
    )
    assert [item["candidate_record_id"] for item in merge_result["skipped_candidates"]] == sorted(
        item["candidate_record_id"] for item in merge_result["skipped_candidates"]
    )

    strict_workspace = _workspace(tmp_path / "strict")
    _copy(DDL_FIXTURE, strict_workspace, "schema.sql")
    strict_blocked = consolidate_batch(strict_workspace, strict_review=True)
    strict_candidate_ids = _candidate_ids(strict_workspace)
    _apply_mixed_review(strict_workspace, strict_candidate_ids)

    strict = consolidate_batch(strict_workspace, resume_run_id=strict_blocked["run_id"])
    assert strict["exit_code"] == 4
    assert strict["reason"] == "merge_review_precondition_failed"
    assert strict["status"] == "failed"
    assert _count(strict_workspace, "facts") == 0
    assert _count(strict_workspace, "relations") == 0
    assert _count(strict_workspace, "fact_evidence") == 0
    assert _count(strict_workspace, "relation_evidence") == 0


@pytest.mark.parametrize("fault_point", ["after_derive", "after_review", "after_merge"])
def test_slice_22_retry_convergence(tmp_path, fault_point):
    clean_workspace = _workspace(tmp_path / f"clean_{fault_point}")
    _copy(DDL_FIXTURE, clean_workspace, "schema.sql")
    _set_policies(clean_workspace, DDL_POLICIES)
    clean = consolidate_batch(clean_workspace)

    retry_workspace = _workspace(tmp_path / f"retry_{fault_point}")
    _copy(DDL_FIXTURE, retry_workspace, "schema.sql")
    _set_policies(retry_workspace, DDL_POLICIES)

    def crash(point: str) -> None:
        if point == fault_point:
            raise RuntimeError(f"crash at {point}")

    with pytest.raises(BatchConsolidationError, match=fault_point):
        consolidate_batch(retry_workspace, fault_hook=crash)
    failed_run_id = _root_batch_run_id(retry_workspace)
    candidates_before = _count(retry_workspace, "candidate_records")

    resumed = consolidate_batch(retry_workspace, resume_run_id=failed_run_id)
    supports_after_resume = _support_count(retry_workspace)
    replayed = consolidate_batch(retry_workspace, resume_run_id=resumed["run_id"])

    assert resumed["exit_code"] == replayed["exit_code"] == clean["exit_code"] == 0
    assert resumed["counters"] == replayed["counters"] == clean["counters"]
    assert resumed["effective_hashes"] == replayed["effective_hashes"] == clean[
        "effective_hashes"
    ]
    assert resumed["semantic_report_hash"] == replayed["semantic_report_hash"] == clean[
        "semantic_report_hash"
    ]
    assert _count(retry_workspace, "candidate_records") == candidates_before
    assert _support_count(retry_workspace) == supports_after_resume
    assert _duplicate_support_count(retry_workspace) == 0


def test_slice_22_inverse_input_order_converges(tmp_path):
    first = _workspace(tmp_path / "forward")
    _copy(DDL_FIXTURE, first, "01_schema.sql")
    _copy(XML_FIXTURE, first, "02_form.xml")
    _set_policies(first, DDL_XML_POLICIES)

    second = _workspace(tmp_path / "reverse")
    _copy(XML_FIXTURE, second, "02_form.xml")
    _copy(DDL_FIXTURE, second, "01_schema.sql")
    _set_policies(second, DDL_XML_POLICIES)

    forward = consolidate_batch(first)
    reverse = consolidate_batch(second)

    assert forward["exit_code"] == reverse["exit_code"] == 0
    assert forward["counters"] == reverse["counters"]
    assert forward["effective_hashes"] == reverse["effective_hashes"]
    assert forward["semantic_report_hash"] == reverse["semantic_report_hash"]


@pytest.mark.parametrize("entrypoint", ["module", "console"])
def test_slice_22_public_entrypoints_exit_four_without_traceback(tmp_path, entrypoint):
    workspace = _workspace(tmp_path / entrypoint)
    (workspace / "corpus" / "active" / "notes.csv").write_text(
        "id,value\n1,unsupported\n", encoding="utf-8", newline="\n"
    )
    if entrypoint == "module":
        command = [sys.executable, "-m", "dsl_mngr"]
    else:
        executable = Path(sys.executable).with_name(
            "dsl-manager.exe" if os.name == "nt" else "dsl-manager"
        )
        assert executable.is_file()
        command = [str(executable)]
    completed = subprocess.run(
        [*command, "batch", "consolidate", str(workspace)],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    payload = json.loads(completed.stdout)
    assert completed.returncode == 4
    assert completed.stderr == ""
    assert "Traceback" not in completed.stdout
    assert payload["reason"] == "no_merge_eligible_candidates"


def _workspace(path: Path) -> Path:
    initialize_workspace(path)
    migrate_workspace_database(path)
    return path


def _copy(source: Path, workspace: Path, name: str) -> None:
    shutil.copyfile(source, workspace / "corpus" / "active" / name)


def _set_policies(workspace: Path, policies: tuple[str, ...]) -> None:
    config = load_config(workspace)
    config["review"]["automatic_policies"] = list(policies)
    (workspace / "configs" / "project.yaml").write_text(
        dump_simple_yaml(config), encoding="utf-8", newline="\n"
    )


def _apply_mixed_review(workspace: Path, candidate_ids: tuple[str, ...]) -> None:
    service = CandidateReviewService(workspace)
    service.confirm(candidate_ids[0], actor_id="reviewer")
    service.reject(candidate_ids[1], actor_id="reviewer", reason="not accepted")
    service.review_candidate(
        candidate_ids[2],
        outcome="superseded",
        operation="supersede",
        actor_id="reviewer",
        reason="superseded by policy",
    )


def _candidate_ids(workspace: Path) -> tuple[str, ...]:
    with sqlite3.connect(workspace / "workspace.sqlite") as connection:
        rows = connection.execute(
            "SELECT candidate_record_id FROM candidate_records ORDER BY candidate_record_id"
        ).fetchall()
    return tuple(str(row[0]) for row in rows)


def _root_batch_run_id(workspace: Path) -> str:
    with sqlite3.connect(workspace / "workspace.sqlite") as connection:
        row = connection.execute(
            "SELECT run_id FROM runs WHERE run_type = 'batch' AND parent_run_id IS NULL "
            "ORDER BY run_id DESC LIMIT 1"
        ).fetchone()
    assert row is not None
    return str(row[0])


def _count(workspace: Path, table: str) -> int:
    assert table in {
        "candidate_records",
        "fact_evidence",
        "facts",
        "relation_evidence",
        "relations",
        "review_decisions",
    }
    with sqlite3.connect(workspace / "workspace.sqlite") as connection:
        return int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def _support_count(workspace: Path) -> int:
    return _count(workspace, "fact_evidence") + _count(workspace, "relation_evidence")


def _duplicate_support_count(workspace: Path) -> int:
    with sqlite3.connect(workspace / "workspace.sqlite") as connection:
        fact_duplicates = connection.execute(
            "SELECT COUNT(*) FROM ("
            "SELECT fact_id, candidate_record_id, COUNT(*) AS n FROM fact_evidence "
            "GROUP BY fact_id, candidate_record_id HAVING n > 1)"
        ).fetchone()[0]
        relation_duplicates = connection.execute(
            "SELECT COUNT(*) FROM ("
            "SELECT relation_id, candidate_record_id, COUNT(*) AS n FROM relation_evidence "
            "GROUP BY relation_id, candidate_record_id HAVING n > 1)"
        ).fetchone()[0]
    return int(fact_duplicates) + int(relation_duplicates)


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))
