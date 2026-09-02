from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from dsl_mngr.cli.app import main


TESTS_DIR = Path(__file__).parent
EXPECTED_DSL_JSON = TESTS_DIR / "expected" / "expected_dsl.full.json"
EXPECTED_GRAPH_EDGES = TESTS_DIR / "expected" / "expected_graph_edges.json"
TIMESTAMP = "2026-06-10T12:00:00+00:00"
GEXF_NS = {"g": "http://www.gexf.net/1.2draft"}


def test_export_gexf(tmp_path, capsys):
    workspace = _ready_workspace(tmp_path)
    content = json.loads(EXPECTED_DSL_JSON.read_text(encoding="utf-8"))
    _insert_snapshot(workspace, "DSL_000001", "RUN_000001", content)

    assert main(["graph", "export", str(workspace), "--snapshot", "DSL_000001"]) == 0
    stdout = capsys.readouterr().out
    assert "Run: RUN_000002" in stdout
    assert "Graph export: GEXF_000001" in stdout
    assert "Snapshot: DSL_000001" in stdout
    assert "Format: gexf" in stdout
    assert f"DSL hash: {content['metadata']['dsl_hash']}" in stdout
    assert "Orphans: 0" in stdout
    assert "Warnings: 0" in stdout
    assert "GEXF: exports/graph/DSL_000001.gexf" in stdout
    assert "Report: exports/graph/DSL_000001.graph_report.json" in stdout

    graph_path = workspace / "exports" / "graph" / "DSL_000001.gexf"
    report_path = workspace / "exports" / "graph" / "DSL_000001.graph_report.json"
    assert graph_path.is_file()
    assert report_path.is_file()

    parsed = _parse_gexf(graph_path)
    assert parsed["defaultedgetype"] == "directed"
    nodes = parsed["nodes"]
    edges = parsed["edges"]

    for node_id in ("entity:cliente", "entity:ordine", "entity:rigaordine"):
        assert nodes[node_id]["node_type"] == "domain_entity"
        assert nodes[node_id]["status"] == "active"
        assert nodes[node_id]["node_id"] == node_id
    assert nodes["entity:cliente"]["canonical_name"] == "cliente"
    assert nodes["entity:cliente"]["fact_count"] == "2"
    assert nodes["fact:FACT_000002"]["node_type"] == "business_rule"
    assert nodes["fact:FACT_000002"]["property_name"] == "delete_rule"
    assert nodes["source:SRC_000001"]["node_type"] == "source"

    expected_edges = json.loads(EXPECTED_GRAPH_EDGES.read_text(encoding="utf-8"))
    relation_edges = [
        {
            "source": edge["source"].removeprefix("entity:"),
            "target": edge["target"].removeprefix("entity:"),
            "type": edge["edge_type"],
        }
        for edge in edges.values()
        if edge.get("relation_id") and edge["edge_type"] != "derives_from"
    ]
    assert sorted(relation_edges, key=lambda edge: (edge["source"], edge["type"], edge["target"])) == expected_edges

    rel_1 = edges["relation:REL_000001"]
    assert rel_1["edge_type"] == "places"
    assert rel_1["relation_id"] == "REL_000001"
    assert rel_1["assertion_type"] == "explicit"
    assert rel_1["confidence"] == "high"
    assert rel_1["status"] == "active"
    assert rel_1["source_entity"] == "Cliente"
    assert rel_1["target_entity"] == "Ordine"
    assert edges["mentions:FACT_000002"]["edge_type"] == "mentions"

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["graph_export_id"] == "GEXF_000001"
    assert report["run_id"] == "RUN_000002"
    assert report["snapshot_id"] == "DSL_000001"
    assert report["format"] == "gexf"
    assert report["dsl_hash"] == content["metadata"]["dsl_hash"]
    assert report["registry_hash"] == content["metadata"]["registry_hash"]
    assert len(report["graph_hash"]) == 64
    assert report["graph_path"] == "exports/graph/DSL_000001.gexf"
    assert report["report_path"] == "exports/graph/DSL_000001.graph_report.json"
    assert report["node_count"] == len(nodes)
    assert report["edge_count"] == len(edges)
    assert report["orphan_count"] == 0
    assert report["warning_count"] == 0
    assert report["warnings"] == []

    _assert_graph_export_record(workspace, report)
    _assert_completed_artifacts(workspace, "RUN_000002", report)
    assert _app_logs(workspace)[-1]["event"] == "gexf_export_completed"

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "dsl_mngr",
            "graph",
            "export",
            str(workspace),
            "--snapshot",
            "DSL_000001",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0
    assert "Graph export: GEXF_000002" in completed.stdout

    with _connect(workspace) as connection:
        graph_hashes = [
            row["graph_hash"]
            for row in connection.execute(
                "SELECT graph_hash FROM graph_exports ORDER BY graph_export_id"
            ).fetchall()
        ]
        dsl_render_runs = connection.execute(
            "SELECT COUNT(*) FROM runs WHERE run_type = 'dsl_render'"
        ).fetchone()[0]
        snapshot_count = connection.execute("SELECT COUNT(*) FROM dsl_snapshots").fetchone()[0]

    assert graph_hashes == [report["graph_hash"], report["graph_hash"]]
    assert dsl_render_runs == 1
    assert snapshot_count == 1


def test_gexf_orphan_warning(tmp_path, capsys):
    workspace = _ready_workspace(tmp_path)
    content = _orphan_dsl_content()
    _insert_snapshot(workspace, "DSL_000001", "RUN_000001", content)

    assert main(["graph", "export", str(workspace), "--snapshot", "DSL_000001"]) == 0
    stdout = capsys.readouterr().out
    assert "Run: RUN_000002" in stdout
    assert "Graph export: GEXF_000001" in stdout
    assert "Orphans: 1" in stdout
    assert "Warnings: 1" in stdout
    assert "Warnings:\n- orphan_node_added: relation REL_000001 references missing target entity ordine" in stdout

    parsed = _parse_gexf(workspace / "exports" / "graph" / "DSL_000001.gexf")
    assert parsed["nodes"]["entity:ordine"]["status"] == "orphaned"
    assert parsed["nodes"]["entity:ordine"]["node_type"] == "domain_entity"

    report = json.loads(
        (workspace / "exports" / "graph" / "DSL_000001.graph_report.json").read_text(
            encoding="utf-8"
        )
    )
    assert report["orphan_count"] == 1
    assert report["warning_count"] == 1
    assert report["warnings"] == [
        {
            "canonical_entity": "ordine",
            "code": "orphan_node_added",
            "message": "relation REL_000001 references missing target entity ordine",
            "relation_id": "REL_000001",
            "role": "target",
        }
    ]

    with _connect(workspace) as connection:
        default_run = connection.execute("SELECT * FROM runs WHERE run_id = 'RUN_000002'").fetchone()
        graph_export_count = connection.execute("SELECT COUNT(*) FROM graph_exports").fetchone()[0]
    assert default_run["run_type"] == "gexf_export"
    assert default_run["status"] == "completed"
    assert graph_export_count == 1

    assert (
        main(
            [
                "graph",
                "export",
                str(workspace),
                "--snapshot",
                "DSL_000001",
                "--strict-orphans",
            ]
        )
        == 2
    )
    stderr = capsys.readouterr().err
    assert "strict_orphans" in stderr
    assert "missing target entity ordine" in stderr

    with _connect(workspace) as connection:
        strict_run = connection.execute("SELECT * FROM runs WHERE run_id = 'RUN_000003'").fetchone()
        completed_exports = connection.execute(
            "SELECT COUNT(*) FROM graph_exports WHERE status = 'completed'"
        ).fetchone()[0]
    assert strict_run["run_type"] == "gexf_export"
    assert strict_run["status"] == "failed"
    assert completed_exports == 1
    assert _app_logs(workspace)[-1]["event"] == "gexf_export_failed"


def _ready_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    assert main(["init", str(workspace)]) == 0
    assert main(["db", "init", str(workspace)]) == 0
    return workspace


def _insert_snapshot(
    workspace: Path,
    snapshot_id: str,
    run_id: str,
    content: dict[str, object],
    *,
    status: str = "completed",
) -> None:
    metadata = content["metadata"]
    with _connect(workspace) as connection:
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
                status,
                TIMESTAMP,
            ),
        )
        connection.commit()


def _orphan_dsl_content() -> dict[str, object]:
    return {
        "metadata": {
            "schema_version": "1",
            "dsl_hash": "b" * 64,
            "registry_hash": "c" * 64,
            "counts": {
                "entities": 1,
                "facts": 1,
                "relations": 1,
                "conflicts": 0,
            },
        },
        "entities": [
            {
                "canonical_name": "cliente",
                "facts": [
                    {
                        "assertion_type": "explicit",
                        "confidence": "high",
                        "fact_id": "FACT_000001",
                        "fact_type": "business_entity",
                        "property_name": "description",
                        "property_value": "Cliente gestito dal sistema.",
                        "status": "active",
                    }
                ],
                "name": "Cliente",
            }
        ],
        "relations": [
            {
                "assertion_type": "explicit",
                "canonical_source_entity": "cliente",
                "canonical_target_entity": "ordine",
                "confidence": "high",
                "relation_id": "REL_000001",
                "relation_type": "places",
                "source_entity": "Cliente",
                "status": "active",
                "target_entity": "Ordine",
            }
        ],
        "conflicts": [],
        "traceability": {
            "facts": {
                "FACT_000001": [
                    {
                        "candidate_record_id": "CREC_000001",
                        "chunk_id": "CHK_000001",
                        "evidence_text_hash": "d" * 64,
                        "file_path": "corpus/active/manuale_clienti.md",
                        "fragment_id": None,
                        "source_id": "SRC_000001",
                        "source_revision_id": "REV_000001",
                    }
                ]
            },
            "relations": {
                "REL_000001": [
                    {
                        "candidate_record_id": "CREC_000002",
                        "chunk_id": "CHK_000001",
                        "evidence_text_hash": "e" * 64,
                        "file_path": "corpus/active/manuale_clienti.md",
                        "fragment_id": None,
                        "source_id": "SRC_000001",
                        "source_revision_id": "REV_000001",
                    }
                ]
            },
        },
    }


def _parse_gexf(path: Path) -> dict[str, object]:
    root = ET.parse(path).getroot()
    graph = root.find("g:graph", GEXF_NS)
    assert graph is not None
    attr_titles = _attribute_titles(graph)

    nodes = {}
    for node in graph.findall("g:nodes/g:node", GEXF_NS):
        values = {
            "id": node.attrib["id"],
            "label": node.attrib["label"],
            **_attvalues(node, attr_titles),
        }
        nodes[node.attrib["id"]] = values

    edges = {}
    for edge in graph.findall("g:edges/g:edge", GEXF_NS):
        values = {
            "id": edge.attrib["id"],
            "label": edge.attrib["label"],
            "source": edge.attrib["source"],
            "target": edge.attrib["target"],
            **_attvalues(edge, attr_titles),
        }
        edges[edge.attrib["id"]] = values

    return {
        "defaultedgetype": graph.attrib["defaultedgetype"],
        "edges": edges,
        "nodes": nodes,
    }


def _attribute_titles(graph: ET.Element) -> dict[str, str]:
    return {
        attribute.attrib["id"]: attribute.attrib["title"]
        for attribute in graph.findall("g:attributes/g:attribute", GEXF_NS)
    }


def _attvalues(element: ET.Element, attr_titles: dict[str, str]) -> dict[str, str]:
    return {
        attr_titles[attvalue.attrib["for"]]: attvalue.attrib["value"]
        for attvalue in element.findall("g:attvalues/g:attvalue", GEXF_NS)
    }


def _assert_graph_export_record(workspace: Path, report: dict[str, object]) -> None:
    with _connect(workspace) as connection:
        row = connection.execute("SELECT * FROM graph_exports").fetchone()
        run = connection.execute("SELECT * FROM runs WHERE run_id = ?", (report["run_id"],)).fetchone()

    assert row["graph_export_id"] == report["graph_export_id"]
    assert row["run_id"] == report["run_id"]
    assert row["snapshot_id"] == report["snapshot_id"]
    assert row["dsl_hash"] == report["dsl_hash"]
    assert row["graph_hash"] == report["graph_hash"]
    assert row["format"] == "gexf"
    assert row["graph_path"] == report["graph_path"]
    assert row["report_path"] == report["report_path"]
    assert "\\" not in row["graph_path"]
    assert "\\" not in row["report_path"]
    assert not Path(row["graph_path"]).is_absolute()
    assert not Path(row["report_path"]).is_absolute()
    assert row["node_count"] == report["node_count"]
    assert row["edge_count"] == report["edge_count"]
    assert row["orphan_count"] == report["orphan_count"]
    assert row["warning_count"] == report["warning_count"]
    assert row["status"] == "completed"
    assert run["run_type"] == "gexf_export"
    assert run["status"] == "completed"


def _assert_completed_artifacts(workspace: Path, run_id: str, expected: dict[str, object]) -> None:
    artifact_dir = workspace / "artifacts" / "runs" / run_id
    for name in (
        "input.json",
        "output.json",
        "process_report.json",
        "resolved_config.yaml",
        "config_hash.txt",
        "log.jsonl",
    ):
        assert (artifact_dir / name).is_file()
    for name in ("input.json", "output.json", "process_report.json"):
        document = json.loads((artifact_dir / name).read_text(encoding="utf-8"))
        for key, value in expected.items():
            assert document[key] == value
    process_report = json.loads((artifact_dir / "process_report.json").read_text(encoding="utf-8"))
    assert process_report["run_type"] == "gexf_export"
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
