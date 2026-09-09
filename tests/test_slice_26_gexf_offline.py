from __future__ import annotations

import hashlib
import json
import socket
from importlib import resources
from pathlib import Path
from xml.etree import ElementTree

import pytest

import dsl_mngr.core.graph_export as graph_export_module
from dsl_mngr.core.candidate_review import CandidateReviewService
from dsl_mngr.core.dsl_renderer import render_dsl_snapshot
from dsl_mngr.core.gexf_validation import (
    EXPECTED_SCHEMA_HASHES,
    GEXF_NAMESPACE,
    GexfValidationError,
    load_gexf_schema_resources,
    validate_dynamic_gexf,
)
from dsl_mngr.core.graph_export import (
    GraphExportError,
    GraphExportOptions,
    export_gexf_from_snapshot,
)
from dsl_mngr.core.reconciliation import ReconciliationRequiredError
from tests.slice_26_test_support import connect, ready_workspace_with_interval


def test_slice_26_gexf_offline(tmp_path):
    workspace, _ = ready_workspace_with_interval(tmp_path)
    run_id = _latest_run_id(workspace)
    snapshot = render_dsl_snapshot(
        workspace,
        run_id=run_id,
        schema_version="2",
    )
    exported = export_gexf_from_snapshot(
        workspace,
        run_id=run_id,
        snapshot_id=snapshot.snapshot_id,
        options=GraphExportOptions(dynamic=True, timeformat="date"),
    )
    xml = (workspace / exported.graph_path).read_text(encoding="utf-8")
    validated = validate_dynamic_gexf(xml)
    assert validated.xsd_valid is True
    assert validated.semantic_valid is True
    assert validated.timeformat == "date"
    root = ElementTree.fromstring(xml)
    assert root.tag == f"{{{GEXF_NAMESPACE}}}gexf"
    assert root.attrib["version"] == "1.3"
    graph = root.find(f"{{{GEXF_NAMESPACE}}}graph")
    assert graph is not None
    assert graph.attrib == {
        "defaultedgetype": "directed",
        "mode": "dynamic",
        "timeformat": "date",
        "timerepresentation": "interval",
        "timezone": "Europe/Rome",
    }
    nodes = root.findall(f".//{{{GEXF_NAMESPACE}}}node")
    temporal_node = next(node for node in nodes if node.attrib["id"] == "fact:FACT_000001")
    assert temporal_node.attrib["start"] == "2025-01-01"
    assert temporal_node.attrib["end"] == "2025-12-31"
    mention = next(
        edge
        for edge in root.findall(f".//{{{GEXF_NAMESPACE}}}edge")
        if edge.attrib["id"] == "mentions:FACT_000001"
    )
    assert mention.attrib["start"] == "2025-01-01"
    assert mention.attrib["end"] == "2025-12-31"
    with connect(workspace) as connection:
        row = connection.execute(
            "SELECT * FROM graph_exports WHERE graph_export_id = ?",
            (exported.graph_export_id,),
        ).fetchone()
    assert row["status"] == "completed"
    assert row["graph_hash"] == exported.graph_hash


def test_slice_26_xsd_sha_package_and_no_network(monkeypatch):
    def deny_network(*args, **kwargs):
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket, "socket", deny_network)
    schemas, manifest = load_gexf_schema_resources()
    directory = resources.files("dsl_mngr.resources.gexf").joinpath("1.3")
    assert manifest["commit"] == "66efb132569f61e5e8a313d78144484238ac7315"
    assert manifest["license"] == "CC BY 4.0"
    assert {item["file"]: item["sha256"] for item in manifest["resources"]} == (
        EXPECTED_SCHEMA_HASHES
    )
    for name, expected in EXPECTED_SCHEMA_HASHES.items():
        assert directory.joinpath(name).is_file()
        assert hashlib.sha256(schemas[name]).hexdigest() == expected
    assert validate_dynamic_gexf(_valid_semantic_fixture()).xsd_valid is True


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        (lambda xml: xml.replace('target="b"', 'target="missing"'), "unknown source or target"),
        (lambda xml: xml.replace('end="2025-06-30"', 'end="2026-06-30"'), "outside"),
        (lambda xml: xml.replace('value="1"', 'value="not-an-integer"'), "not valid for type"),
        (
            lambda xml: xml.replace(
                '<node id="a"', '<node id="z"', 1
            ).replace('source="a"', 'source="z"'),
            "stable id order",
        ),
    ),
)
def test_slice_26_gexf_semantic_refs_types_order_and_bounds(mutation, message):
    with pytest.raises(GexfValidationError, match=message) as caught:
        validate_dynamic_gexf(mutation(_valid_semantic_fixture()))
    assert caught.value.reason == "gexf_semantic_invalid"


@pytest.mark.parametrize("reason", ("gexf_xsd_invalid", "gexf_semantic_invalid"))
def test_slice_26_gexf_error_does_not_publish_or_register(
    tmp_path,
    monkeypatch,
    reason,
):
    workspace, _ = ready_workspace_with_interval(tmp_path)
    run_id = _latest_run_id(workspace)
    snapshot = render_dsl_snapshot(workspace, run_id=run_id, schema_version="2")

    def fail_validation(xml):
        raise GexfValidationError("forced validation failure", reason=reason)

    monkeypatch.setattr(graph_export_module, "validate_dynamic_gexf", fail_validation)
    with pytest.raises(GraphExportError) as caught:
        export_gexf_from_snapshot(
            workspace,
            run_id=run_id,
            snapshot_id=snapshot.snapshot_id,
            output_dir="exports/failed_dynamic",
            options=GraphExportOptions(dynamic=True),
        )
    assert caught.value.reason == reason
    assert not (workspace / "exports" / "failed_dynamic" / f"{snapshot.snapshot_id}.gexf").exists()
    assert not (
        workspace
        / "exports"
        / "failed_dynamic"
        / f"{snapshot.snapshot_id}.graph_report.json"
    ).exists()
    with connect(workspace) as connection:
        assert connection.execute("SELECT COUNT(*) FROM graph_exports").fetchone()[0] == 0


def test_slice_26_datetime_export_is_timezone_resolved_and_hash_stable(tmp_path):
    workspace, _ = ready_workspace_with_interval(
        tmp_path,
        subject_type="relation",
        subject_id="REL_000001",
        start="2025-06-01T10:00:00",
        end="2025-06-01T11:00:00",
        precision="second",
        timezone_status="resolved",
        timezone_value="Europe/Rome",
    )
    run_id = _latest_run_id(workspace)
    first_snapshot = render_dsl_snapshot(workspace, run_id=run_id, schema_version="2")
    second_snapshot = render_dsl_snapshot(workspace, run_id=run_id, schema_version="2")
    first = export_gexf_from_snapshot(
        workspace,
        run_id=run_id,
        snapshot_id=first_snapshot.snapshot_id,
        options=GraphExportOptions(dynamic=True, timeformat="dateTime"),
    )
    second = export_gexf_from_snapshot(
        workspace,
        run_id=run_id,
        snapshot_id=second_snapshot.snapshot_id,
        options=GraphExportOptions(dynamic=True, timeformat="dateTime"),
    )
    first_xml = (workspace / first.graph_path).read_text(encoding="utf-8")
    second_xml = (workspace / second.graph_path).read_text(encoding="utf-8")
    assert first.graph_hash == second.graph_hash
    assert first_xml == second_xml
    assert validate_dynamic_gexf(first_xml).timeformat == "dateTime"
    relation = next(
        edge
        for edge in ElementTree.fromstring(first_xml).findall(
            f".//{{{GEXF_NAMESPACE}}}edge"
        )
        if edge.attrib["id"] == "relation:REL_000001"
    )
    assert relation.attrib["start"] == "2025-06-01T10:00:00+02:00"
    assert relation.attrib["end"] == "2025-06-01T11:00:00+02:00"


def test_slice_26_dynamic_requires_v2_and_allow_incomplete_is_dynamic_only(tmp_path):
    workspace, candidate_record_id = ready_workspace_with_interval(tmp_path)
    run_id = _latest_run_id(workspace)
    v1 = render_dsl_snapshot(workspace, run_id=run_id, schema_version="1")
    with pytest.raises(GraphExportError, match="schema 2"):
        export_gexf_from_snapshot(
            workspace,
            run_id=run_id,
            snapshot_id=v1.snapshot_id,
            options=GraphExportOptions(dynamic=True),
        )
    with pytest.raises(GraphExportError, match="only with --dynamic"):
        export_gexf_from_snapshot(
            workspace,
            run_id=run_id,
            snapshot_id=v1.snapshot_id,
            options=GraphExportOptions(allow_incomplete=True),
        )

    v2 = render_dsl_snapshot(workspace, run_id=run_id, schema_version="2")
    with connect(workspace) as connection:
        head = str(
            connection.execute(
                "SELECT decision_id FROM review_subject_heads WHERE subject_id = ?",
                (candidate_record_id,),
            ).fetchone()[0]
        )
    CandidateReviewService(workspace).reject(
        candidate_record_id,
        actor_id="reviewer",
        reason="withdrawn",
        expected_head_decision_id=head,
    )
    with pytest.raises(ReconciliationRequiredError, match="reconciliation_required"):
        export_gexf_from_snapshot(
            workspace,
            run_id=run_id,
            snapshot_id=v2.snapshot_id,
            options=GraphExportOptions(dynamic=True),
        )
    allowed = export_gexf_from_snapshot(
        workspace,
        run_id=run_id,
        snapshot_id=v2.snapshot_id,
        options=GraphExportOptions(dynamic=True, allow_incomplete=True),
    )
    assert allowed.warning_count >= 1
    assert sum(
        warning["code"] == "reconciliation_required" for warning in allowed.warnings
    ) == 1


def _valid_semantic_fixture() -> str:
    return """<?xml version="1.0" encoding="utf-8"?>
<gexf xmlns="http://gexf.net/1.3" version="1.3">
  <graph defaultedgetype="directed" mode="dynamic" timeformat="date" timerepresentation="interval">
    <attributes class="node" mode="static">
      <attribute id="n0" title="count" type="integer" />
    </attributes>
    <nodes>
      <node id="a" label="A" start="2025-01-01" end="2025-12-31">
        <attvalues><attvalue for="n0" value="1" /></attvalues>
      </node>
      <node id="b" label="B" start="2025-01-01" end="2025-12-31" />
    </nodes>
    <edges>
      <edge id="e" source="a" target="b" type="directed" start="2025-02-01" end="2025-06-30" />
    </edges>
  </graph>
</gexf>
"""


def _latest_run_id(workspace: Path) -> str:
    with connect(workspace) as connection:
        return str(connection.execute("SELECT run_id FROM runs ORDER BY run_id DESC LIMIT 1").fetchone()[0])
