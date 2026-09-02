from __future__ import annotations

import hashlib
import json
import queue
import re
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

from dsl_mngr.cli.app import main
from dsl_mngr.core.local_ui import resolve_local_ui_request
from dsl_mngr.core.migrations import migrate_workspace_database
from dsl_mngr.core.workspace import initialize_workspace


TIMESTAMP = "2026-06-01T10:00:00+00:00"
CHUNK_TEXT = 'Cliente <special> & "quoted" evidence.'


def test_ui_routes_smoke(tmp_path):
    workspace = _ready_ui_workspace(tmp_path)
    before = _db_fingerprint(workspace)

    dashboard = _get_body(workspace, "/")
    assert "DSL Manager Workspace" in dashboard
    assert "Rejected candidates" in dashboard

    runs = _get_body(workspace, "/runs")
    assert "RUN_000002" in runs
    assert "/runs/RUN_000002" in runs

    run_detail = _get_body(workspace, "/runs/RUN_000002")
    assert "Input JSON" in run_detail
    assert "Process report" in run_detail
    assert "/logs?run_id=RUN_000002" in run_detail

    app_logs = _get_body(workspace, "/logs")
    assert "Special &lt;tag&gt; &amp; &quot;quoted&quot;" in app_logs

    run_logs = _get_body(workspace, "/logs?run_id=RUN_000001")
    assert "Run &lt;log&gt; &amp; &quot;quoted&quot;" in run_logs

    rejected = _get_body(workspace, "/rejected-candidates")
    assert "CAND_&lt;bad&gt;&amp;&quot;" in rejected
    assert "Missing &lt;field&gt; &amp; &quot;quoted&quot;" in rejected

    conflicts = _get_body(workspace, "/conflicts")
    assert "CONFLICT_000001" in conflicts
    assert "open" in conflicts
    assert "resolved" in conflicts

    snapshots = _get_body(workspace, "/snapshots")
    assert "DSL_000001" in snapshots
    assert "exports/dsl/DSL_000001.json" in snapshots

    diff = _get_body(workspace, "/diff?from=DSL_000001&to=DSL_000002")
    assert "Existing diff" in diff
    assert "exports/dsl_diff/DSL_000001__DSL_000002.json" in diff
    assert "Diff &lt;change&gt; &amp;" in diff

    missing_diff = _get_body(workspace, "/diff?from=DSL_000002&to=DSL_000003")
    assert "Diff artifact not found" in missing_diff
    assert "dsl-manager dsl diff" in missing_diff

    unknown = resolve_local_ui_request(workspace, "GET", "/unknown")
    assert unknown.status == 404
    assert "No local UI route matches" in unknown.body.decode("utf-8")

    mutative = resolve_local_ui_request(workspace, "POST", "/runs")
    assert mutative.status == 405
    assert ("Allow", "GET, HEAD") in mutative.headers

    head = resolve_local_ui_request(workspace, "HEAD", "/runs")
    assert head.status == 200
    assert head.body == b""

    after = _db_fingerprint(workspace)
    assert after == before


def test_ui_cli_errors_are_readable(tmp_path, capsys):
    workspace = tmp_path / "not-initialized"

    assert main(["ui", "serve", str(workspace), "--port", "0"]) == 2

    captured = capsys.readouterr()
    assert "Workspace is not initialized" in captured.err
    assert "Traceback" not in captured.err
    assert not (workspace / "workspace.sqlite").exists()


def test_python_module_ui_serve_smoke_ephemeral_port(tmp_path):
    workspace = _ready_ui_workspace(tmp_path)
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "dsl_mngr",
            "ui",
            "serve",
            str(workspace),
            "--host",
            "127.0.0.1",
            "--port",
            "0",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        line = _readline_with_timeout(process, timeout=30)
        assert line.startswith("Serving DSL Manager UI at http://127.0.0.1:")
        url = line.removeprefix("Serving DSL Manager UI at ").strip()
        assert re.fullmatch(r"http://127\.0\.0\.1:\d+/", url)
        html = _open_url_with_retry(url)
        assert "DSL Manager Workspace" in html
    finally:
        _terminate_process(process)


def _get_body(workspace: Path, target: str) -> str:
    response = resolve_local_ui_request(workspace, "GET", target)
    assert response.status == 200
    assert ("Content-Type", "text/html; charset=utf-8") in response.headers
    body = response.body.decode("utf-8")
    assert body.startswith("<!doctype html>")
    return body


def _ready_ui_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    initialize_workspace(workspace)
    migrate_workspace_database(workspace)
    _seed_database(workspace)
    _seed_artifacts(workspace)
    return workspace


def _seed_database(workspace: Path) -> None:
    with _connect(workspace) as connection:
        _insert_source_revision_and_chunk(connection)
        _insert_run(
            connection,
            "RUN_000001",
            "candidate_validation",
            output_payload={"message": 'candidate output <json> & "quoted"'},
        )
        _insert_run(
            connection,
            "RUN_000002",
            "dsl_render",
            parent_run_id="RUN_000001",
            input_payload={"message": 'input <json> & "quoted"'},
            output_payload={"snapshot_id": "DSL_000001"},
        )
        _insert_run(connection, "RUN_000003", "dsl_render", output_payload={"snapshot_id": "DSL_000002"})
        _insert_run(connection, "RUN_000004", "dsl_diff", output_payload={"total_changes": 1})
        _insert_worker_run(connection)
        _insert_candidates(connection)
        _insert_facts_and_conflicts(connection)
        _insert_snapshots(connection)
        connection.commit()


def _insert_source_revision_and_chunk(connection: sqlite3.Connection) -> None:
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
        VALUES (?, ?, ?, NULL, ?, ?, ?, NULL, ?, ?, ?)
        """,
        (
            "SRC_000001",
            "corpus/active/manuale_clienti.txt",
            "legacy_document",
            "functional_documentation",
            TIMESTAMP,
            TIMESTAMP,
            "active",
            TIMESTAMP,
            TIMESTAMP,
        ),
    )
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
            "REV_000001",
            "SRC_000001",
            1,
            hashlib.sha256(CHUNK_TEXT.encode("utf-8")).hexdigest(),
            "corpus/active/manuale_clienti.txt",
            len(CHUNK_TEXT.encode("utf-8")),
            TIMESTAMP,
            "active",
            TIMESTAMP,
        ),
    )
    connection.execute(
        "UPDATE sources SET current_revision_id = ? WHERE source_id = ?",
        ("REV_000001", "SRC_000001"),
    )
    connection.execute(
        """
        INSERT INTO chunks (
            chunk_id,
            source_revision_id,
            sequence,
            text,
            text_hash,
            metadata_json,
            status,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "CHK_000001",
            "REV_000001",
            1,
            CHUNK_TEXT,
            hashlib.sha256(CHUNK_TEXT.encode("utf-8")).hexdigest(),
            "{}",
            "active",
            TIMESTAMP,
        ),
    )


def _insert_run(
    connection: sqlite3.Connection,
    run_id: str,
    run_type: str,
    *,
    parent_run_id: str | None = None,
    input_payload: dict[str, object] | None = None,
    output_payload: dict[str, object] | None = None,
) -> None:
    input_json = json.dumps(input_payload or {}, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    output_json = json.dumps(output_payload or {}, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    connection.execute(
        """
        INSERT INTO runs (
            run_id,
            run_type,
            status,
            started_at,
            finished_at,
            parent_run_id,
            input_json,
            output_json,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            run_type,
            "completed",
            TIMESTAMP,
            TIMESTAMP,
            parent_run_id,
            input_json,
            output_json,
            TIMESTAMP,
            TIMESTAMP,
        ),
    )


def _insert_worker_run(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        INSERT INTO worker_runs (
            worker_run_id,
            run_id,
            worker_name,
            worker_version,
            status,
            input_path,
            output_path,
            report_path,
            log_path,
            exit_code,
            duration_ms,
            started_at,
            finished_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "WRUN_000001",
            "RUN_000002",
            "render_dsl",
            "1.0",
            "completed",
            "artifacts/runs/RUN_000002/input.json",
            "artifacts/runs/RUN_000002/output.json",
            "artifacts/runs/RUN_000002/process_report.json",
            "artifacts/runs/RUN_000002/log.jsonl",
            0,
            12,
            TIMESTAMP,
            TIMESTAMP,
        ),
    )


def _insert_candidates(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        INSERT INTO candidate_batches (
            batch_id,
            run_id,
            input_path,
            total_records,
            accepted_count,
            rejected_count,
            status,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "CBATCH_000001",
            "RUN_000001",
            "ai/inbox/candidates.jsonl",
            3,
            2,
            1,
            "completed",
            TIMESTAMP,
            TIMESTAMP,
        ),
    )
    for index, candidate_id in enumerate(("CAND_001", "CAND_002"), start=1):
        connection.execute(
            """
            INSERT INTO candidate_records (
                candidate_record_id,
                batch_id,
                run_id,
                line_number,
                candidate_id,
                record_type,
                source_revision_id,
                chunk_id,
                fragment_id,
                assertion_type,
                confidence,
                evidence_text,
                payload_json,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?)
            """,
            (
                f"CREC_00000{index}",
                "CBATCH_000001",
                "RUN_000001",
                index,
                candidate_id,
                "candidate_fact",
                "REV_000001",
                "CHK_000001",
                "explicit",
                "high",
                CHUNK_TEXT,
                "{}",
                TIMESTAMP,
            ),
        )
    connection.execute(
        """
        INSERT INTO rejected_candidates (
            rejected_candidate_id,
            batch_id,
            run_id,
            line_number,
            candidate_id,
            record_type,
            reason,
            message,
            raw_line,
            payload_json,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "REJ_000001",
            "CBATCH_000001",
            "RUN_000001",
            3,
            'CAND_<bad>&"',
            "candidate_fact",
            "schema_error",
            'Missing <field> & "quoted"',
            "{bad}",
            None,
            TIMESTAMP,
        ),
    )


def _insert_facts_and_conflicts(connection: sqlite3.Connection) -> None:
    fact_rows = (
        ("FACT_000001", "active", "ACTIVE"),
        ("FACT_000002", "blocked", "BLOCKED"),
    )
    for index, (fact_id, normalized_value, property_value) in enumerate(fact_rows, start=1):
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
                hashlib.sha256(fact_id.encode("utf-8")).hexdigest(),
                "business_rule",
                "Cliente",
                "cliente",
                "status",
                property_value,
                normalized_value,
                "explicit",
                "high",
                "active",
                f"CREC_00000{index}",
                TIMESTAMP,
                TIMESTAMP,
            ),
        )
    for conflict_id, status in (("CONFLICT_000001", "open"), ("CONFLICT_000002", "resolved")):
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
                conflict_id,
                hashlib.sha256(conflict_id.encode("utf-8")).hexdigest(),
                "different_values_same_property",
                "Cliente",
                "cliente",
                "status",
                "FACT_000001",
                "FACT_000002",
                "ACTIVE",
                "BLOCKED",
                status,
                TIMESTAMP,
                TIMESTAMP,
            ),
        )


def _insert_snapshots(connection: sqlite3.Connection) -> None:
    for snapshot_id, run_id, dsl_hash in (
        ("DSL_000001", "RUN_000002", "a" * 64),
        ("DSL_000002", "RUN_000003", "b" * 64),
    ):
        content = {
            "metadata": {
                "schema_version": "1",
                "dsl_hash": dsl_hash,
                "registry_hash": "c" * 64,
                "counts": {"entities": 1, "facts": 2, "relations": 0, "conflicts": 2},
            },
            "entities": [],
            "relations": [],
            "conflicts": [],
            "traceability": {"facts": {}, "relations": {}},
        }
        connection.execute(
            """
            INSERT INTO dsl_snapshots (
                snapshot_id,
                run_id,
                dsl_hash,
                registry_hash,
                content_json,
                json_path,
                yaml_path,
                markdown_path,
                fact_count,
                relation_count,
                conflict_count,
                status,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot_id,
                run_id,
                dsl_hash,
                "c" * 64,
                json.dumps(content, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                f"exports/dsl/{snapshot_id}.json",
                f"exports/dsl/{snapshot_id}.yaml",
                f"exports/dsl/{snapshot_id}.md",
                2,
                0,
                2,
                "completed",
                TIMESTAMP,
            ),
        )


def _seed_artifacts(workspace: Path) -> None:
    for run_id in ("RUN_000001", "RUN_000002"):
        run_dir = workspace / "artifacts" / "runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "process_report.json").write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "run_type": "candidate_validation" if run_id == "RUN_000001" else "dsl_render",
                    "status": "completed",
                    "message": 'Report <json> & "quoted"',
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
        _write_jsonl(
            run_dir / "log.jsonl",
            [
                {
                    "timestamp": TIMESTAMP,
                    "level": "INFO",
                    "run_id": run_id,
                    "worker": "worker_a",
                    "event": "run_event",
                    "message": 'Run <log> & "quoted"',
                }
            ],
        )

    _write_jsonl(
        workspace / "logs" / "app.jsonl",
        [
            {
                "timestamp": TIMESTAMP,
                "level": "INFO",
                "run_id": "RUN_000001",
                "worker": "worker_a",
                "event": "app_event",
                "message": 'Special <tag> & "quoted"',
            }
        ],
    )

    diff_dir = workspace / "exports" / "dsl_diff"
    diff_dir.mkdir(parents=True, exist_ok=True)
    diff_payload = {
        "metadata": {
            "from_snapshot_id": "DSL_000001",
            "to_snapshot_id": "DSL_000002",
            "has_changes": True,
        },
        "summary": {"total_changes": 1, "added": 0, "removed": 0, "modified": 1},
        "changes": [
            {
                "change_id": "CHG_000001",
                "change_type": "modified_fact",
                "path": "entities[cliente].facts[status]",
                "before": "ACTIVE",
                "after": 'Diff <change> & "quoted"',
                "causes": [],
            }
        ],
    }
    (diff_dir / "DSL_000001__DSL_000002.json").write_text(
        json.dumps(diff_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (diff_dir / "DSL_000001__DSL_000002.md").write_text(
        "# DSL Diff\n",
        encoding="utf-8",
        newline="\n",
    )


def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records)
    path.write_text(content, encoding="utf-8", newline="\n")


def _db_fingerprint(workspace: Path) -> dict[str, object]:
    tables = (
        "runs",
        "worker_runs",
        "candidate_batches",
        "candidate_records",
        "rejected_candidates",
        "facts",
        "conflicts",
        "dsl_snapshots",
    )
    with _connect(workspace) as connection:
        counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in tables
        }
        runs = [
            tuple(row)
            for row in connection.execute("SELECT * FROM runs ORDER BY run_id").fetchall()
        ]
        snapshots = [
            tuple(row)
            for row in connection.execute(
                "SELECT * FROM dsl_snapshots ORDER BY snapshot_id"
            ).fetchall()
        ]
    return {"counts": counts, "runs": runs, "snapshots": snapshots}


def _readline_with_timeout(process: subprocess.Popen[str], *, timeout: float) -> str:
    assert process.stdout is not None
    lines: queue.Queue[str] = queue.Queue()

    def read_line() -> None:
        lines.put(process.stdout.readline())

    thread = threading.Thread(target=read_line, daemon=True)
    thread.start()
    try:
        line = lines.get(timeout=timeout)
    except queue.Empty:
        process.terminate()
        stderr = process.stderr.read() if process.stderr is not None else ""
        raise AssertionError(f"Timed out waiting for UI URL. stderr={stderr!r}") from None
    if not line:
        stderr = process.stderr.read() if process.stderr is not None else ""
        raise AssertionError(f"UI process exited before printing URL. stderr={stderr!r}")
    return line


def _open_url_with_retry(url: str) -> str:
    deadline = time.monotonic() + 10
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                assert response.status == 200
                return response.read().decode("utf-8")
        except Exception as exc:  # pragma: no cover - only used to retry a race.
            last_error = exc
            time.sleep(0.1)
    raise AssertionError(f"UI server did not respond: {last_error!r}")


def _terminate_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)
    if process.stdout is not None:
        process.stdout.close()
    if process.stderr is not None:
        process.stderr.close()


def _connect(workspace: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(workspace / "workspace.sqlite")
    connection.row_factory = sqlite3.Row
    return connection
