from __future__ import annotations

import json
from pathlib import Path
from xml.etree import ElementTree

import pytest

from dsl_mngr.core.candidate_review import CandidateReviewService
from dsl_mngr.core.dsl_renderer import render_dsl_snapshot
from dsl_mngr.core.gexf_validation import GEXF_NAMESPACE, GexfValidationError, validate_dynamic_gexf
from dsl_mngr.core.graph_export import (
    GraphExportError,
    GraphExportOptions,
    export_gexf_from_snapshot,
)
from dsl_mngr.core.temporal import create_temporal_candidate
from tests.slice_26_test_support import (
    connect,
    insert_raw_temporal_evidence,
    ready_workspace_with_interval,
)


EXPECTED = Path(__file__).parent / "expected" / "expected_slice_27_temporal_spells.json"


def test_slice_27_spells_bounds_and_shared_golden_hash(tmp_path):
    workspace, _ = ready_workspace_with_interval(tmp_path)
    run_id = _latest_run_id(workspace)
    evidence_id = insert_raw_temporal_evidence(
        workspace,
        evidence_id="TEV_971001",
        target_subject_type="fact",
        target_subject_id="FACT_000001",
        raw_value="2027",
    )
    candidate = create_temporal_candidate(
        workspace,
        run_id=run_id,
        source_revision_id="REV_000001",
        target_subject_type="fact",
        target_subject_id="FACT_000001",
        temporal_evidence_ids=[evidence_id],
        normalized_start="2027-01-01",
        normalized_end="2027-12-31",
        original_precision="year",
        timezone_status="unknown",
        timezone_value=None,
        bounds_semantics="coverage_envelope",
    )
    CandidateReviewService(workspace).confirm(candidate.candidate_record_id, actor_id="reviewer")

    first = render_dsl_snapshot(workspace, run_id=run_id, schema_version="2")
    second = render_dsl_snapshot(workspace, run_id=run_id, schema_version="2")
    first_content = json.loads((workspace / first.json_path).read_text(encoding="utf-8"))
    fact = next(
        fact
        for entity in first_content["entities"]
        for fact in entity["facts"]
        if fact["fact_id"] == "FACT_000001"
    )
    assert fact["intervals"] == json.loads(EXPECTED.read_text(encoding="utf-8"))
    assert first.dsl_hash == second.dsl_hash
    assert (workspace / first.json_path).read_bytes() == (workspace / second.json_path).read_bytes()

    exported = export_gexf_from_snapshot(
        workspace,
        run_id=run_id,
        snapshot_id=first.snapshot_id,
        options=GraphExportOptions(dynamic=True),
    )
    xml = (workspace / exported.graph_path).read_text(encoding="utf-8")
    assert validate_dynamic_gexf(xml).semantic_valid is True
    document = ElementTree.fromstring(xml)
    fact_node = next(
        node
        for node in document.findall(f".//{{{GEXF_NAMESPACE}}}node")
        if node.attrib["id"] == "fact:FACT_000001"
    )
    mention = next(
        edge
        for edge in document.findall(f".//{{{GEXF_NAMESPACE}}}edge")
        if edge.attrib["id"] == "mentions:FACT_000001"
    )
    expected_spells = [("2025-01-01", "2025-12-31"), ("2027-01-01", "2027-12-31")]
    for element in (fact_node, mention):
        spells = element.findall(
            f"./{{{GEXF_NAMESPACE}}}spells/{{{GEXF_NAMESPACE}}}spell"
        )
        assert [(spell.attrib.get("start"), spell.attrib.get("end")) for spell in spells] == expected_spells


def test_slice_27_edge_outside_node_bounds_is_rejected():
    xml = f"""<gexf xmlns="{GEXF_NAMESPACE}" version="1.3">
  <graph defaultedgetype="directed" mode="dynamic" timeformat="date" timerepresentation="interval">
    <nodes>
      <node id="a" start="2025-01-01" end="2025-12-31" />
      <node id="b" start="2025-01-01" end="2025-12-31" />
    </nodes>
    <edges><edge id="e" source="a" target="b" start="2024-01-01" end="2025-02-01" /></edges>
  </graph>
</gexf>"""
    with pytest.raises(GexfValidationError, match="outside"):
        validate_dynamic_gexf(xml)


def test_slice_27_temporal_output_modes_omit_separate_strict(tmp_path):
    workspace, _ = ready_workspace_with_interval(tmp_path)
    run_id = _latest_run_id(workspace)
    evidence_id = insert_raw_temporal_evidence(
        workspace,
        evidence_id="TEV_971002",
        target_subject_type="relation",
        target_subject_id="REL_000001",
        raw_value="2025-06-01T10:00:00+02:00",
        timezone_status="explicit",
        timezone_value="+02:00",
    )
    candidate = create_temporal_candidate(
        workspace,
        run_id=run_id,
        source_revision_id="REV_000001",
        target_subject_type="relation",
        target_subject_id="REL_000001",
        temporal_evidence_ids=[evidence_id],
        normalized_start="2025-06-01T10:00:00+02:00",
        normalized_end="2025-06-01T11:00:00+02:00",
        original_precision="second",
        timezone_status="explicit",
        timezone_value="+02:00",
    )
    CandidateReviewService(workspace).confirm(candidate.candidate_record_id, actor_id="reviewer")
    snapshot = render_dsl_snapshot(
        workspace,
        run_id=run_id,
        schema_version="2",
        allow_incomplete=True,
    )

    with pytest.raises(GraphExportError) as caught:
        export_gexf_from_snapshot(
            workspace,
            run_id=run_id,
            snapshot_id=snapshot.snapshot_id,
            output_dir="exports/strict",
            options=GraphExportOptions(dynamic=True, temporal_output_mode="strict"),
        )
    assert caught.value.reason == "temporal_profile_incompatible"

    omitted = export_gexf_from_snapshot(
        workspace,
        run_id=run_id,
        snapshot_id=snapshot.snapshot_id,
        output_dir="exports/omit",
        options=GraphExportOptions(dynamic=True, temporal_output_mode="omit"),
    )
    assert any(warning["code"] == "temporal_profile_incompatible" for warning in omitted.warnings)
    assert omitted.separated_graph_paths == ()

    separated = export_gexf_from_snapshot(
        workspace,
        run_id=run_id,
        snapshot_id=snapshot.snapshot_id,
        output_dir="exports/separate",
        options=GraphExportOptions(dynamic=True, temporal_output_mode="separate"),
    )
    assert len(separated.separated_graph_paths) == 1
    companion = workspace / separated.separated_graph_paths[0]
    assert companion.name.endswith(".dateTime.gexf")
    assert validate_dynamic_gexf(companion.read_text(encoding="utf-8")).timeformat == "dateTime"


def _latest_run_id(workspace: Path) -> str:
    with connect(workspace) as connection:
        return str(connection.execute("SELECT run_id FROM runs ORDER BY run_id DESC LIMIT 1").fetchone()[0])
