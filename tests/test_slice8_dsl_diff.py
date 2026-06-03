from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

from dsl_mngr.cli.app import main
from dsl_mngr.core.migrations import migrate_workspace_database
from dsl_mngr.core.workspace import initialize_workspace


TIMESTAMP = "2026-05-30T12:00:00+00:00"
HASH_FROM = "a" * 64
HASH_TO = "b" * 64
REGISTRY_FROM = "c" * 64
REGISTRY_TO = "d" * 64


def test_diff_added_entity(tmp_path, capsys):
    workspace = _ready_workspace(tmp_path)
    before = _dsl_content(
        dsl_hash=HASH_FROM,
        registry_hash=REGISTRY_FROM,
        entities=[_entity("Cliente", "cliente", [_fact("FACT_000001", "Cliente")])],
        traceability={
            "facts": {"FACT_000001": [_evidence("CREC_000001")]},
            "relations": {},
        },
    )
    after = _dsl_content(
        dsl_hash=HASH_TO,
        registry_hash=REGISTRY_TO,
        entities=[
            _entity("Cliente", "cliente", [_fact("FACT_000001", "Cliente")]),
            _entity("Ordine", "ordine", [_fact("FACT_000002", "Ordine")]),
        ],
        traceability={
            "facts": {
                "FACT_000001": [_evidence("CREC_000001")],
                "FACT_000002": [_evidence("CREC_000002", chunk_id="CHK_000002")],
            },
            "relations": {},
        },
    )
    _insert_snapshots(workspace, before, after)

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

    stdout = capsys.readouterr().out
    assert "Run: RUN_000003" in stdout
    assert "From: DSL_000001" in stdout
    assert "To: DSL_000002" in stdout
    assert "Changes: 1" in stdout
    assert "Added: 1" in stdout
    assert "JSON: exports/dsl_diff/DSL_000001__DSL_000002.json" in stdout
    assert "Markdown: exports/dsl_diff/DSL_000001__DSL_000002.md" in stdout

    diff_json = workspace / "exports" / "dsl_diff" / "DSL_000001__DSL_000002.json"
    diff_markdown = workspace / "exports" / "dsl_diff" / "DSL_000001__DSL_000002.md"
    assert diff_json.is_file()
    assert diff_markdown.is_file()

    payload = json.loads(diff_json.read_text(encoding="utf-8"))
    assert payload["metadata"]["from_snapshot_id"] == "DSL_000001"
    assert payload["metadata"]["to_snapshot_id"] == "DSL_000002"
    assert payload["metadata"]["from_dsl_hash"] == HASH_FROM
    assert payload["metadata"]["to_dsl_hash"] == HASH_TO
    assert payload["metadata"]["has_changes"] is True
    assert payload["summary"]["total_changes"] == 1
    assert payload["summary"]["added"] == 1
    assert payload["summary"]["entities"]["added"] == 1
    assert payload["summary"]["facts"]["added"] == 1

    change = payload["changes"][0]
    assert change["change_id"] == "CHG_000001"
    assert change["change_type"] == "added_entity"
    assert change["path"] == "entities[ordine]"
    assert change["before"] is None
    assert change["after"] == {"canonical_name": "ordine", "name": "Ordine"}
    assert change["causes"] == [
        {
            "side": "after",
            "owner_type": "fact",
            "owner_id": "FACT_000002",
            "candidate_record_id": "CREC_000002",
            "source_revision_id": "REV_000001",
            "source_id": "SRC_000001",
            "file_path": "corpus/active/manuale_clienti.txt",
            "chunk_id": "CHK_000002",
            "fragment_id": None,
            "evidence_text_hash": "e" * 64,
        }
    ]

    markdown = diff_markdown.read_text(encoding="utf-8")
    assert "## Snapshots" in markdown
    assert "## Summary" in markdown
    assert "### added_entity" in markdown
    assert "CREC_000002" in markdown

    _assert_completed_artifacts(
        workspace,
        "RUN_000003",
        {
            "from_snapshot_id": "DSL_000001",
            "to_snapshot_id": "DSL_000002",
            "from_dsl_hash": HASH_FROM,
            "to_dsl_hash": HASH_TO,
            "total_changes": 1,
            "added_count": 1,
            "removed_count": 0,
            "modified_count": 0,
            "json_path": "exports/dsl_diff/DSL_000001__DSL_000002.json",
            "markdown_path": "exports/dsl_diff/DSL_000001__DSL_000002.md",
        },
    )

    app_logs = _app_logs(workspace)
    assert app_logs[-1]["event"] == "dsl_diff_completed"
    assert app_logs[-1]["run_id"] == "RUN_000003"


def test_diff_modified_relation(tmp_path):
    workspace = _ready_workspace(tmp_path)
    entities = [
        _entity("Cliente", "cliente", [_fact("FACT_000001", "Cliente")]),
        _entity("Ordine", "ordine", [_fact("FACT_000002", "Ordine")]),
    ]
    before = _dsl_content(
        dsl_hash=HASH_FROM,
        registry_hash=REGISTRY_FROM,
        entities=entities,
        relations=[
            _relation(
                "REL_000001",
                source_entity="Cliente",
                target_entity="Ordine",
                confidence="high",
            )
        ],
        traceability={
            "facts": {
                "FACT_000001": [_evidence("CREC_000001")],
                "FACT_000002": [_evidence("CREC_000002")],
            },
            "relations": {"REL_000001": [_evidence("CREC_000003")]},
        },
    )
    after = _dsl_content(
        dsl_hash=HASH_TO,
        registry_hash=REGISTRY_TO,
        entities=entities,
        relations=[
            _relation(
                "REL_000002",
                source_entity="Cliente",
                target_entity="Ordine",
                confidence="medium",
            )
        ],
        traceability={
            "facts": {
                "FACT_000001": [_evidence("CREC_000001")],
                "FACT_000002": [_evidence("CREC_000002")],
            },
            "relations": {"REL_000002": [_evidence("CREC_000004", chunk_id="CHK_000004")]},
        },
    )
    _insert_snapshots(workspace, before, after)

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

    payload = json.loads(
        (workspace / "exports" / "dsl_diff" / "DSL_000001__DSL_000002.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["summary"]["modified"] == 1
    assert payload["summary"]["relations"]["modified"] == 1

    change = payload["changes"][0]
    assert change["change_type"] == "modified_relation"
    assert change["path"] == "relations[cliente.places.ordine]"
    assert change["before"]["confidence"] == "high"
    assert change["after"]["confidence"] == "medium"
    assert [cause["side"] for cause in change["causes"]] == ["before", "after"]
    assert [cause["owner_id"] for cause in change["causes"]] == ["REL_000001", "REL_000002"]


def test_diff_requires_traceability(tmp_path, capsys):
    workspace = _ready_workspace(tmp_path)
    before = _dsl_content(
        dsl_hash=HASH_FROM,
        registry_hash=REGISTRY_FROM,
        traceability={"facts": {}, "relations": {}},
    )
    after = _dsl_content(
        dsl_hash=HASH_TO,
        registry_hash=REGISTRY_TO,
        entities=[_entity("Cliente", "cliente", [_fact("FACT_000001", "Cliente")])],
        traceability={"facts": {}, "relations": {}},
    )
    _insert_snapshots(workspace, before, after)

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
    ) == 2

    stderr = capsys.readouterr().err
    assert "missing_traceability" in stderr
    assert not (workspace / "exports" / "dsl_diff" / "DSL_000001__DSL_000002.json").exists()

    with _connect(workspace) as connection:
        run = connection.execute("SELECT * FROM runs WHERE run_id = 'RUN_000003'").fetchone()
    assert run["run_type"] == "dsl_diff"
    assert run["status"] == "failed"

    process_report = json.loads(
        (workspace / "artifacts" / "runs" / "RUN_000003" / "process_report.json").read_text(
            encoding="utf-8"
        )
    )
    assert process_report["run_type"] == "dsl_diff"
    assert process_report["status"] == "failed"
    assert "missing_traceability" in process_report["error"]
    assert _app_logs(workspace)[-1]["event"] == "dsl_diff_failed"


def test_diff_same_hash_has_no_changes(tmp_path):
    workspace = _ready_workspace(tmp_path)
    content = _dsl_content(
        dsl_hash=HASH_FROM,
        registry_hash=REGISTRY_FROM,
        entities=[_entity("Cliente", "cliente", [_fact("FACT_000001", "Cliente")])],
        traceability={
            "facts": {"FACT_000001": [_evidence("CREC_000001")]},
            "relations": {},
        },
    )
    _insert_snapshots(workspace, content, content)

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "dsl_mngr",
            "dsl",
            "diff",
            str(workspace),
            "--from",
            "DSL_000001",
            "--to",
            "DSL_000002",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert "Run: RUN_000003" in completed.stdout
    assert "Changes: 0" in completed.stdout
    assert "Added: 0" in completed.stdout
    assert "Removed: 0" in completed.stdout
    assert "Modified: 0" in completed.stdout

    json_path = workspace / "exports" / "dsl_diff" / "DSL_000001__DSL_000002.json"
    markdown_path = workspace / "exports" / "dsl_diff" / "DSL_000001__DSL_000002.md"
    assert json_path.is_file()
    assert markdown_path.is_file()

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["metadata"]["has_changes"] is False
    assert payload["summary"] == {
        "total_changes": 0,
        "added": 0,
        "removed": 0,
        "modified": 0,
        "entities": {"added": 0, "removed": 0, "modified": 0},
        "facts": {"added": 0, "removed": 0, "modified": 0},
        "relations": {"added": 0, "removed": 0, "modified": 0},
        "conflicts": {"added": 0, "removed": 0, "modified": 0},
    }
    assert payload["changes"] == []
    assert "## Changes\n- none\n" in markdown_path.read_text(encoding="utf-8")


def _ready_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    initialize_workspace(workspace)
    migrate_workspace_database(workspace)
    return workspace


def _insert_snapshots(
    workspace: Path,
    before: dict[str, object],
    after: dict[str, object],
) -> None:
    with _connect(workspace) as connection:
        _insert_run(connection, "RUN_000001")
        _insert_run(connection, "RUN_000002")
        _insert_snapshot(connection, "DSL_000001", "RUN_000001", before)
        _insert_snapshot(connection, "DSL_000002", "RUN_000002", after)
        connection.commit()


def _insert_run(connection: sqlite3.Connection, run_id: str) -> None:
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
        VALUES (?, ?, ?, ?, ?, NULL, ?, ?, ?, ?)
        """,
        (
            run_id,
            "dsl_render",
            "completed",
            TIMESTAMP,
            TIMESTAMP,
            "{}",
            "{}",
            TIMESTAMP,
            TIMESTAMP,
        ),
    )


def _insert_snapshot(
    connection: sqlite3.Connection,
    snapshot_id: str,
    run_id: str,
    content: dict[str, object],
) -> None:
    metadata = content["metadata"]
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
            metadata["dsl_hash"],
            metadata["registry_hash"],
            json.dumps(content, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            f"exports/dsl/{snapshot_id}.json",
            f"exports/dsl/{snapshot_id}.yaml",
            f"exports/dsl/{snapshot_id}.md",
            metadata["counts"]["facts"],
            metadata["counts"]["relations"],
            metadata["counts"]["conflicts"],
            "completed",
            TIMESTAMP,
        ),
    )


def _dsl_content(
    *,
    dsl_hash: str,
    registry_hash: str,
    entities: list[dict[str, object]] | None = None,
    relations: list[dict[str, object]] | None = None,
    conflicts: list[dict[str, object]] | None = None,
    traceability: dict[str, object] | None = None,
) -> dict[str, object]:
    entities = entities or []
    relations = relations or []
    conflicts = conflicts or []
    traceability = traceability or {"facts": {}, "relations": {}}
    return {
        "metadata": {
            "schema_version": "1",
            "dsl_hash": dsl_hash,
            "registry_hash": registry_hash,
            "counts": {
                "entities": len(entities),
                "facts": sum(len(entity["facts"]) for entity in entities),
                "relations": len(relations),
                "conflicts": len(conflicts),
            },
        },
        "entities": entities,
        "relations": relations,
        "conflicts": conflicts,
        "traceability": traceability,
    }


def _entity(
    name: str,
    canonical_name: str,
    facts: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "name": name,
        "canonical_name": canonical_name,
        "facts": facts,
    }


def _fact(
    fact_id: str,
    entity_name: str,
    *,
    fact_type: str = "business_entity",
    property_name: str = "description",
    property_value: str | None = None,
    confidence: str = "high",
) -> dict[str, object]:
    return {
        "assertion_type": "explicit",
        "confidence": confidence,
        "fact_id": fact_id,
        "fact_type": fact_type,
        "property_name": property_name,
        "property_value": property_value or f"{entity_name} gestito dal sistema",
        "status": "active",
    }


def _relation(
    relation_id: str,
    *,
    source_entity: str,
    target_entity: str,
    relation_type: str = "places",
    confidence: str = "high",
) -> dict[str, object]:
    return {
        "assertion_type": "explicit",
        "canonical_source_entity": source_entity.lower(),
        "canonical_target_entity": target_entity.lower(),
        "confidence": confidence,
        "relation_id": relation_id,
        "relation_type": relation_type,
        "source_entity": source_entity,
        "status": "active",
        "target_entity": target_entity,
    }


def _evidence(
    candidate_record_id: str,
    *,
    source_revision_id: str = "REV_000001",
    source_id: str = "SRC_000001",
    file_path: str = "corpus/active/manuale_clienti.txt",
    chunk_id: str | None = "CHK_000001",
    fragment_id: str | None = None,
    evidence_text_hash: str = "e" * 64,
) -> dict[str, object]:
    return {
        "candidate_record_id": candidate_record_id,
        "source_revision_id": source_revision_id,
        "source_id": source_id,
        "file_path": file_path,
        "chunk_id": chunk_id,
        "fragment_id": fragment_id,
        "evidence_text_hash": evidence_text_hash,
    }


def _assert_completed_artifacts(
    workspace: Path,
    run_id: str,
    expected: dict[str, object],
) -> None:
    artifact_dir = workspace / "artifacts" / "runs" / run_id
    for name in ("input.json", "output.json", "process_report.json"):
        document = json.loads((artifact_dir / name).read_text(encoding="utf-8"))
        for key, value in expected.items():
            assert document[key] == value

    process_report = json.loads((artifact_dir / "process_report.json").read_text(encoding="utf-8"))
    assert process_report["run_type"] == "dsl_diff"
    assert process_report["status"] == "completed"
    assert process_report["artifact_dir"] == f"artifacts/runs/{run_id}"
    assert "\\" not in process_report["artifact_dir"]


def _app_logs(workspace: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in (workspace / "logs" / "app.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _connect(workspace: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(workspace / "workspace.sqlite")
    connection.row_factory = sqlite3.Row
    return connection
