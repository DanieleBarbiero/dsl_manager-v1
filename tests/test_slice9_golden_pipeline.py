from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
from pathlib import Path

from dsl_mngr.cli.app import main


TESTS_DIR = Path(__file__).parent
CORPUS_FIXTURE_DIR = TESTS_DIR / "fixtures" / "corpus_initial"
CANDIDATE_FIXTURE = (
    TESTS_DIR / "fixtures" / "ai_candidates" / "AIPKG_MANUALI_001_candidates.jsonl"
)
EXPECTED_DSL_JSON = TESTS_DIR / "expected" / "expected_dsl.full.json"
EXPECTED_DSL_YAML = TESTS_DIR / "expected" / "expected_dsl.full.yaml"
EXPECTED_CONFLICTS = TESTS_DIR / "expected" / "expected_conflicts.json"
EXPECTED_GRAPH_EDGES = TESTS_DIR / "expected" / "expected_graph_edges.json"
CHUNK_SEED_TIMESTAMP = "2026-06-01T00:00:00+00:00"


def test_golden_full_pipeline(tmp_path, capsys):
    workspace = tmp_path / "workspace"

    assert main(["init", str(workspace)]) == 0
    assert main(["db", "init", str(workspace)]) == 0
    capsys.readouterr()

    shutil.copytree(CORPUS_FIXTURE_DIR, workspace / "corpus" / "active", dirs_exist_ok=True)

    assert main(["corpus", "scan", str(workspace)]) == 0
    scan_output = capsys.readouterr().out
    assert "Added: 2" in scan_output
    assert "Modified: 0" in scan_output
    assert "Deleted: 0" in scan_output
    assert "Unchanged: 0" in scan_output
    _assert_scanned_sources(workspace)

    seeded_chunks = _seed_chunks_for_active_revisions(workspace)
    assert seeded_chunks == [
        ("CHK_000001", "REV_000001", "corpus/active/manuale_clienti.md"),
        ("CHK_000002", "REV_000002", "corpus/active/manuale_ordini.md"),
    ]
    _assert_chunks_reference_active_revisions(workspace)

    candidate_input = workspace / "ai" / "inbox" / CANDIDATE_FIXTURE.name
    shutil.copyfile(CANDIDATE_FIXTURE, candidate_input)
    total_records = _jsonl_record_count(CANDIDATE_FIXTURE)

    assert main(["candidates", "validate", str(workspace), "--input", str(candidate_input)]) == 0
    validation_output = capsys.readouterr().out
    assert f"Total: {total_records}" in validation_output
    assert f"Accepted: {total_records}" in validation_output
    assert "Rejected: 0" in validation_output
    _assert_candidate_validation(workspace, total_records)

    assert main(["facts", "merge", str(workspace), "--batch", "CBATCH_000001"]) == 0
    merge_output = capsys.readouterr().out
    assert "Candidate records: 8" in merge_output
    assert "Facts created: 6" in merge_output
    assert "Relations created: 2" in merge_output
    assert "Conflicts created: 0" in merge_output
    assert "Skipped: 0" in merge_output
    _assert_merged_registry(workspace)

    assert main(["dsl", "render", str(workspace)]) == 0
    render_output = capsys.readouterr().out
    assert "Snapshot: DSL_000001" in render_output
    assert "Facts: 6" in render_output
    assert "Relations: 2" in render_output
    assert "Conflicts: 0" in render_output

    first_json_path = workspace / "exports" / "dsl" / "DSL_000001.json"
    first_yaml_path = workspace / "exports" / "dsl" / "DSL_000001.yaml"
    assert first_json_path.read_text(encoding="utf-8") == EXPECTED_DSL_JSON.read_text(
        encoding="utf-8"
    )
    assert first_yaml_path.read_text(encoding="utf-8") == EXPECTED_DSL_YAML.read_text(
        encoding="utf-8"
    )

    first_content = json.loads(first_json_path.read_text(encoding="utf-8"))
    assert first_content["conflicts"] == _read_json(EXPECTED_CONFLICTS)
    assert _graph_edges_from_dsl(first_content) == _read_json(EXPECTED_GRAPH_EDGES)

    assert main(["dsl", "render", str(workspace)]) == 0
    second_render_output = capsys.readouterr().out
    assert "Snapshot: DSL_000002" in second_render_output
    second_content = _read_json(workspace / "exports" / "dsl" / "DSL_000002.json")
    assert second_content["metadata"]["dsl_hash"] == first_content["metadata"]["dsl_hash"]
    assert second_content["metadata"]["registry_hash"] == first_content["metadata"]["registry_hash"]

    assert main(
        [
            "dsl",
            "diff",
            str(workspace),
            "--from",
            "DSL_000001",
            "--to",
            "DSL_000002",
        ]
    ) == 0
    diff_output = capsys.readouterr().out
    assert "Changes: 0" in diff_output
    assert "Added: 0" in diff_output
    assert "Removed: 0" in diff_output
    assert "Modified: 0" in diff_output
    _assert_zero_diff(workspace)

    _assert_run_artifacts(workspace)
    _assert_app_logs(workspace)


def test_slice9_expected_files_are_static_valid_and_readable():
    expected_dsl = _read_json(EXPECTED_DSL_JSON)

    assert len(expected_dsl["metadata"]["dsl_hash"]) == 64
    assert len(expected_dsl["metadata"]["registry_hash"]) == 64
    assert expected_dsl["metadata"]["counts"] == {
        "conflicts": 0,
        "entities": 3,
        "facts": 6,
        "relations": 2,
    }
    assert _read_json(EXPECTED_CONFLICTS) == []
    assert _read_json(EXPECTED_GRAPH_EDGES) == [
        {"source": "cliente", "target": "ordine", "type": "places"},
        {"source": "ordine", "target": "rigaordine", "type": "has_rows"},
    ]

    yaml_text = EXPECTED_DSL_YAML.read_text(encoding="utf-8")
    assert yaml_text.startswith("metadata:\n")
    assert expected_dsl["metadata"]["dsl_hash"] in yaml_text
    for path in (EXPECTED_DSL_JSON, EXPECTED_DSL_YAML, EXPECTED_CONFLICTS, EXPECTED_GRAPH_EDGES):
        data = path.read_bytes()
        assert data.endswith(b"\n")
        assert b"\r" not in data


def _assert_scanned_sources(workspace: Path) -> None:
    with _connect(workspace) as connection:
        sources = connection.execute(
            "SELECT source_id, logical_name, current_revision_id, status "
            "FROM sources ORDER BY logical_name"
        ).fetchall()
        revisions = connection.execute(
            "SELECT source_revision_id, file_path, status FROM source_revisions ORDER BY file_path"
        ).fetchall()
        event_types = [
            row["event_type"]
            for row in connection.execute(
                "SELECT event_type FROM source_events ORDER BY source_event_id"
            ).fetchall()
        ]

    assert [(row["source_id"], row["logical_name"], row["current_revision_id"]) for row in sources] == [
        ("SRC_000001", "corpus/active/manuale_clienti.md", "REV_000001"),
        ("SRC_000002", "corpus/active/manuale_ordini.md", "REV_000002"),
    ]
    assert [(row["source_revision_id"], row["file_path"], row["status"]) for row in revisions] == [
        ("REV_000001", "corpus/active/manuale_clienti.md", "active"),
        ("REV_000002", "corpus/active/manuale_ordini.md", "active"),
    ]
    assert {row["status"] for row in sources} == {"active"}
    assert event_types == ["source_added", "source_added"]


def _seed_chunks_for_active_revisions(workspace: Path) -> list[tuple[str, str, str]]:
    with _connect(workspace) as connection:
        revisions = connection.execute(
            """
            SELECT source_revision_id, file_path
            FROM source_revisions
            WHERE status = 'active'
            ORDER BY file_path
            """
        ).fetchall()
        seeded: list[tuple[str, str, str]] = []
        for index, revision in enumerate(revisions, start=1):
            chunk_id = f"CHK_{index:06d}"
            text = (workspace / revision["file_path"]).read_text(encoding="utf-8")
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
                    chunk_id,
                    revision["source_revision_id"],
                    1,
                    text,
                    hashlib.sha256(text.encode("utf-8")).hexdigest(),
                    json.dumps({"seeded_by": "slice9_test"}, sort_keys=True),
                    "active",
                    CHUNK_SEED_TIMESTAMP,
                ),
            )
            seeded.append((chunk_id, revision["source_revision_id"], revision["file_path"]))
        connection.commit()
    return seeded


def _assert_chunks_reference_active_revisions(workspace: Path) -> None:
    with _connect(workspace) as connection:
        rows = connection.execute(
            """
            SELECT c.chunk_id, c.source_revision_id, sr.status AS revision_status
            FROM chunks c
            JOIN source_revisions sr ON sr.source_revision_id = c.source_revision_id
            ORDER BY c.chunk_id
            """
        ).fetchall()

    assert [(row["chunk_id"], row["source_revision_id"], row["revision_status"]) for row in rows] == [
        ("CHK_000001", "REV_000001", "active"),
        ("CHK_000002", "REV_000002", "active"),
    ]


def _assert_candidate_validation(workspace: Path, total_records: int) -> None:
    with _connect(workspace) as connection:
        batch = connection.execute("SELECT * FROM candidate_batches").fetchone()
        accepted_count = connection.execute("SELECT COUNT(*) FROM candidate_records").fetchone()[0]
        rejected_count = connection.execute("SELECT COUNT(*) FROM rejected_candidates").fetchone()[0]

    assert batch["batch_id"] == "CBATCH_000001"
    assert batch["input_path"] == "ai/inbox/AIPKG_MANUALI_001_candidates.jsonl"
    assert batch["total_records"] == total_records
    assert batch["accepted_count"] == total_records
    assert batch["rejected_count"] == 0
    assert batch["status"] == "completed"
    assert accepted_count == total_records
    assert rejected_count == 0


def _assert_merged_registry(workspace: Path) -> None:
    with _connect(workspace) as connection:
        facts = connection.execute(
            """
            SELECT canonical_entity_name, property_name, property_value, status
            FROM facts
            ORDER BY canonical_entity_name, property_name
            """
        ).fetchall()
        relations = connection.execute(
            """
            SELECT canonical_source_entity, relation_type, canonical_target_entity, status
            FROM relations
            ORDER BY canonical_source_entity, relation_type, canonical_target_entity
            """
        ).fetchall()
        conflict_count = connection.execute("SELECT COUNT(*) FROM conflicts").fetchone()[0]

    assert [(row["canonical_entity_name"], row["property_name"], row["status"]) for row in facts] == [
        ("cliente", "delete_rule", "active"),
        ("cliente", "description", "active"),
        ("ordine", "composition", "active"),
        ("ordine", "description", "active"),
        ("ordine", "status_values", "active"),
        ("rigaordine", "description", "active"),
    ]
    assert [
        (row["canonical_source_entity"], row["relation_type"], row["canonical_target_entity"], row["status"])
        for row in relations
    ] == [
        ("cliente", "places", "ordine", "active"),
        ("ordine", "has_rows", "rigaordine", "active"),
    ]
    assert conflict_count == 0


def _graph_edges_from_dsl(content: dict[str, object]) -> list[dict[str, str]]:
    return [
        {
            "source": relation["canonical_source_entity"],
            "target": relation["canonical_target_entity"],
            "type": relation["relation_type"],
        }
        for relation in content["relations"]
    ]


def _assert_zero_diff(workspace: Path) -> None:
    json_path = workspace / "exports" / "dsl_diff" / "DSL_000001__DSL_000002.json"
    markdown_path = workspace / "exports" / "dsl_diff" / "DSL_000001__DSL_000002.md"
    assert json_path.is_file()
    assert markdown_path.is_file()

    payload = _read_json(json_path)
    assert payload["summary"]["total_changes"] == 0
    assert payload["changes"] == []

    with _connect(workspace) as connection:
        run = connection.execute("SELECT * FROM runs WHERE run_id = 'RUN_000005'").fetchone()
    assert run["run_type"] == "dsl_diff"
    assert run["status"] == "completed"


def _assert_run_artifacts(workspace: Path) -> None:
    with _connect(workspace) as connection:
        runs = connection.execute(
            "SELECT run_id, run_type, status FROM runs ORDER BY run_id"
        ).fetchall()

    assert [(row["run_id"], row["run_type"], row["status"]) for row in runs] == [
        ("RUN_000001", "candidate_validation", "completed"),
        ("RUN_000002", "merge", "completed"),
        ("RUN_000003", "dsl_render", "completed"),
        ("RUN_000004", "dsl_render", "completed"),
        ("RUN_000005", "dsl_diff", "completed"),
    ]
    for row in runs:
        artifact_dir = workspace / "artifacts" / "runs" / row["run_id"]
        for name in (
            "input.json",
            "output.json",
            "process_report.json",
            "resolved_config.yaml",
            "config_hash.txt",
            "log.jsonl",
        ):
            assert (artifact_dir / name).is_file()
        process_report = _read_json(artifact_dir / "process_report.json")
        assert process_report["artifact_dir"] == f"artifacts/runs/{row['run_id']}"
        assert "\\" not in process_report["artifact_dir"]
        assert not Path(process_report["artifact_dir"]).is_absolute()


def _assert_app_logs(workspace: Path) -> None:
    events = [entry["event"] for entry in _app_logs(workspace)]
    assert "candidate_validation_completed" in events
    assert "facts_merge_completed" in events
    assert events.count("dsl_render_completed") == 2
    assert "dsl_diff_completed" in events


def _jsonl_record_count(path: Path) -> int:
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def _app_logs(workspace: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in (workspace / "logs" / "app.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _connect(workspace: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(workspace / "workspace.sqlite")
    connection.row_factory = sqlite3.Row
    return connection
