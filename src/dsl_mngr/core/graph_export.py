from __future__ import annotations

import copy
import hashlib
import json
import sqlite3
import xml.etree.ElementTree as ET
from collections.abc import Iterable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from dsl_mngr.core.database import (
    DatabaseConfigurationError,
    DatabaseSettings,
    open_database,
    resolve_database_settings,
    resolve_workspace_path,
)
from dsl_mngr.core.gexf_validation import (
    GEXF_NAMESPACE,
    GexfValidationError,
    validate_dynamic_gexf,
)
from dsl_mngr.core.reconciliation import assert_no_open_reconciliation
from dsl_mngr.core.runs import (
    DatabaseNotReadyError,
    canonical_json,
    next_id,
    relative_workspace_path,
    run_artifact_paths,
    timestamp_now,
    validate_database_migrations,
    write_process_report,
)


GEXF_NS = "http://www.gexf.net/1.2draft"
SUPPORTED_SCHEMA_VERSIONS = {"1", "2"}

NODE_ATTRIBUTES: tuple[tuple[str, str], ...] = (
    ("node_id", "string"),
    ("label", "string"),
    ("node_type", "string"),
    ("canonical_name", "string"),
    ("status", "string"),
    ("source_count", "integer"),
    ("fact_count", "integer"),
    ("source_ids", "string"),
    ("fact_ids", "string"),
    ("fact_id", "string"),
    ("fact_type", "string"),
    ("property_name", "string"),
    ("assertion_type", "string"),
    ("confidence", "string"),
    ("source_id", "string"),
    ("file_path", "string"),
    ("file_paths", "string"),
    ("source_revision_ids", "string"),
    ("conflict_id", "string"),
    ("conflict_type", "string"),
    ("left_fact_id", "string"),
    ("right_fact_id", "string"),
)

EDGE_ATTRIBUTES: tuple[tuple[str, str], ...] = (
    ("edge_id", "string"),
    ("edge_type", "string"),
    ("relation_id", "string"),
    ("assertion_type", "string"),
    ("confidence", "string"),
    ("status", "string"),
    ("source_entity", "string"),
    ("target_entity", "string"),
    ("source_ids", "string"),
    ("source_id", "string"),
    ("source_revision_ids", "string"),
    ("fact_id", "string"),
    ("owner_type", "string"),
    ("owner_id", "string"),
    ("conflict_id", "string"),
    ("conflict_side", "string"),
)


class GraphExportError(RuntimeError):
    """Raised when a DSL snapshot cannot be exported as GEXF."""

    def __init__(
        self,
        message: str,
        *,
        reason: str = "graph_export_invalid",
        exit_code: int = 2,
    ) -> None:
        super().__init__(message)
        self.reason = reason
        self.exit_code = exit_code


class GraphExportDatabaseNotReadyError(GraphExportError):
    """Raised when GEXF export needs a migrated database."""


@dataclass(frozen=True)
class GraphExportOptions:
    include_sources: bool = True
    include_fact_nodes: bool = True
    include_conflicts: bool = True
    strict_orphans: bool = False
    directed: bool = True
    node_label_strategy: str = "readable"
    dynamic: bool = False
    timeformat: str | None = None
    allow_incomplete: bool = False
    temporal_output_mode: str = "strict"

    def to_payload(self) -> dict[str, Any]:
        payload = {
            "directed": self.directed,
            "include_conflicts": self.include_conflicts,
            "include_fact_nodes": self.include_fact_nodes,
            "include_sources": self.include_sources,
            "node_label_strategy": self.node_label_strategy,
            "strict_orphans": self.strict_orphans,
        }
        if (
            self.dynamic
            or self.timeformat is not None
            or self.allow_incomplete
            or self.temporal_output_mode != "strict"
        ):
            payload.update(
                {
                    "allow_incomplete": self.allow_incomplete,
                    "dynamic": self.dynamic,
                    "temporal_output_mode": self.temporal_output_mode,
                    "timeformat": self.timeformat,
                }
            )
        return payload


@dataclass(frozen=True)
class GraphExportResult:
    graph_export_id: str
    run_id: str
    snapshot_id: str
    format: str
    dsl_hash: str
    registry_hash: str
    graph_hash: str
    graph_path: str
    report_path: str
    node_count: int
    edge_count: int
    orphan_count: int
    warning_count: int
    options: GraphExportOptions
    warnings: tuple[dict[str, Any], ...]
    separated_graph_paths: tuple[str, ...] = ()

    def to_artifact_payload(self) -> dict[str, Any]:
        return {
            "dsl_hash": self.dsl_hash,
            "edge_count": self.edge_count,
            "format": self.format,
            "graph_export_id": self.graph_export_id,
            "graph_hash": self.graph_hash,
            "graph_path": self.graph_path,
            "node_count": self.node_count,
            "options": self.options.to_payload(),
            "orphan_count": self.orphan_count,
            "registry_hash": self.registry_hash,
            "report_path": self.report_path,
            "run_id": self.run_id,
            "snapshot_id": self.snapshot_id,
            "warning_count": self.warning_count,
            "warnings": list(self.warnings),
            "separated_graph_paths": list(self.separated_graph_paths),
        }


@dataclass(frozen=True)
class _Snapshot:
    snapshot_id: str
    dsl_hash: str
    registry_hash: str
    content: dict[str, Any]


@dataclass(frozen=True)
class _GraphNode:
    node_id: str
    label: str
    attributes: dict[str, Any]

    def payload(self) -> dict[str, Any]:
        return {
            "attributes": self.attributes,
            "id": self.node_id,
            "label": self.label,
        }


@dataclass(frozen=True)
class _GraphEdge:
    edge_id: str
    source: str
    target: str
    label: str
    attributes: dict[str, Any]

    def payload(self) -> dict[str, Any]:
        return {
            "attributes": self.attributes,
            "id": self.edge_id,
            "label": self.label,
            "source": self.source,
            "target": self.target,
        }


@dataclass(frozen=True)
class _GraphModel:
    nodes: tuple[_GraphNode, ...]
    edges: tuple[_GraphEdge, ...]
    warnings: tuple[dict[str, Any], ...]
    orphan_count: int

    def payload(self) -> dict[str, Any]:
        return {
            "directed": True,
            "edges": [edge.payload() for edge in self.edges],
            "nodes": [node.payload() for node in self.nodes],
            "orphan_count": self.orphan_count,
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class _DynamicInterval:
    start: str | None
    end: str | None

    def payload(self) -> dict[str, Any]:
        return {"end": self.end, "start": self.start}


@dataclass(frozen=True)
class _DynamicNode:
    node: _GraphNode
    intervals: tuple[_DynamicInterval, ...]

    def payload(self) -> dict[str, Any]:
        return {**self.node.payload(), "intervals": [item.payload() for item in self.intervals]}


@dataclass(frozen=True)
class _DynamicEdge:
    edge: _GraphEdge
    intervals: tuple[_DynamicInterval, ...]

    def payload(self) -> dict[str, Any]:
        return {**self.edge.payload(), "intervals": [item.payload() for item in self.intervals]}


@dataclass(frozen=True)
class _DynamicGraphModel:
    nodes: tuple[_DynamicNode, ...]
    edges: tuple[_DynamicEdge, ...]
    warnings: tuple[dict[str, Any], ...]
    orphan_count: int
    timeformat: str
    timezone: str | None

    def payload(self) -> dict[str, Any]:
        return {
            "directed": True,
            "dynamic": True,
            "edges": [edge.payload() for edge in self.edges],
            "nodes": [node.payload() for node in self.nodes],
            "orphan_count": self.orphan_count,
            "timeformat": self.timeformat,
            "timezone": self.timezone,
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class _GraphPaths:
    graph_file: Path
    report_file: Path
    graph_path: str
    report_path: str


def ensure_graph_export_database_ready(
    workspace_dir: str | Path,
    *,
    dynamic: bool = False,
    allow_incomplete: bool = False,
) -> DatabaseSettings:
    if allow_incomplete and not dynamic:
        raise GraphExportError("--allow-incomplete is supported only with --dynamic.")
    settings = resolve_database_settings(workspace_dir)
    if not settings.database_path.is_file():
        raise GraphExportDatabaseNotReadyError(
            f"Database is not initialized: {settings.database_path}. "
            "Run 'dsl-manager db init <workspace>' before 'dsl-manager graph export'."
        )

    connection = open_database(settings.database_path, enable_wal=settings.wal_enabled)
    try:
        try:
            validate_database_migrations(connection)
            if not allow_incomplete:
                assert_no_open_reconciliation(connection)
        except DatabaseNotReadyError as exc:
            message = str(exc).replace("dsl-manager run", "dsl-manager graph export")
            raise GraphExportDatabaseNotReadyError(message) from exc
    finally:
        connection.close()
    return settings


def export_gexf_from_snapshot(
    workspace_dir: str | Path,
    *,
    run_id: str,
    snapshot_id: str,
    output_dir: str | Path | None = None,
    format: str = "gexf",
    options: GraphExportOptions | None = None,
) -> GraphExportResult:
    if format != "gexf":
        raise GraphExportError(f"Unsupported graph export format: {format}. Expected: gexf.")

    options = options or GraphExportOptions()
    if not options.directed:
        raise GraphExportError("GEXF export supports only directed graphs in v1.")
    if options.temporal_output_mode not in {"omit", "separate", "strict"}:
        raise GraphExportError(
            "temporal_output_mode must be omit, separate, or strict.",
            reason="temporal_output_mode_invalid",
        )
    if options.temporal_output_mode != "strict" and not options.dynamic:
        raise GraphExportError("Temporal output modes are supported only with --dynamic.")

    settings = ensure_graph_export_database_ready(
        workspace_dir,
        dynamic=options.dynamic,
        allow_incomplete=options.allow_incomplete,
    )
    export_dir = _resolve_output_dir(settings.workspace_dir, output_dir)
    paths = _graph_paths(settings.workspace_dir, export_dir, snapshot_id)

    connection = open_database(settings.database_path, enable_wal=settings.wal_enabled)
    try:
        validate_database_migrations(connection)
        if not options.allow_incomplete:
            assert_no_open_reconciliation(connection)
        open_reconciliation_count = int(
            connection.execute(
                "SELECT COUNT(*) FROM reconciliation_required WHERE status = 'open'"
            ).fetchone()[0]
        )
        snapshot = _load_snapshot(connection, snapshot_id)
        graph_export_id = next_id(connection, "graph_exports", "graph_export_id", "GEXF")
    finally:
        connection.close()

    snapshot_schema = str(snapshot.content["metadata"]["schema_version"])
    if options.dynamic and snapshot_schema != "2":
        raise GraphExportError("--dynamic requires a DSL schema 2 snapshot.")
    if not options.dynamic and snapshot_schema != "1":
        raise GraphExportError("DSL schema 2 snapshots require --dynamic.")
    graph = (
        build_dynamic_graph_model(
            snapshot.content,
            options=options,
            open_reconciliation_count=open_reconciliation_count,
        )
        if options.dynamic
        else build_graph_model(snapshot.content, options=options)
    )
    graph_hash = _graph_hash(snapshot, graph, options=options, format=format)
    gexf_text = render_dynamic_gexf(graph) if options.dynamic else render_gexf(graph)
    separated_outputs: list[tuple[Path, str, str]] = []
    if options.dynamic:
        try:
            validate_dynamic_gexf(gexf_text)
            if options.temporal_output_mode == "separate":
                selected = str(graph.timeformat)
                for profile in sorted(_content_timeformats(snapshot.content) - {selected}):
                    profile_options = replace(
                        options,
                        timeformat=profile,
                        temporal_output_mode="omit",
                    )
                    profile_graph = build_dynamic_graph_model(
                        snapshot.content,
                        options=profile_options,
                        open_reconciliation_count=open_reconciliation_count,
                    )
                    profile_text = render_dynamic_gexf(profile_graph)
                    validate_dynamic_gexf(profile_text)
                    profile_file = export_dir / f"{snapshot_id}.{profile}.gexf"
                    separated_outputs.append(
                        (
                            profile_file,
                            relative_workspace_path(settings.workspace_dir, profile_file),
                            profile_text,
                        )
                    )
        except GexfValidationError as exc:
            raise GraphExportError(
                str(exc),
                reason=exc.reason,
                exit_code=exc.exit_code,
            ) from exc
    report = _build_report(
        graph_export_id=graph_export_id,
        run_id=run_id,
        snapshot=snapshot,
        format=format,
        graph_hash=graph_hash,
        paths=paths,
        graph=graph,
        options=options,
    )
    report["separated_graph_paths"] = [value[1] for value in separated_outputs]

    export_dir.mkdir(parents=True, exist_ok=True)
    paths.graph_file.write_text(gexf_text, encoding="utf-8", newline="\n")
    for profile_file, _, profile_text in separated_outputs:
        profile_file.write_text(profile_text, encoding="utf-8", newline="\n")
    paths.report_file.write_text(canonical_json(report), encoding="utf-8", newline="\n")

    timestamp = timestamp_now(None)
    connection = open_database(settings.database_path, enable_wal=settings.wal_enabled)
    try:
        validate_database_migrations(connection)
        if not options.allow_incomplete:
            assert_no_open_reconciliation(connection)
        connection.execute("BEGIN")
        try:
            connection.execute(
                """
                INSERT INTO graph_exports (
                    graph_export_id,
                    run_id,
                    snapshot_id,
                    dsl_hash,
                    graph_hash,
                    format,
                    graph_path,
                    report_path,
                    node_count,
                    edge_count,
                    orphan_count,
                    warning_count,
                    status,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    graph_export_id,
                    run_id,
                    snapshot.snapshot_id,
                    snapshot.dsl_hash,
                    graph_hash,
                    format,
                    paths.graph_path,
                    paths.report_path,
                    len(graph.nodes),
                    len(graph.edges),
                    graph.orphan_count,
                    len(graph.warnings),
                    "completed",
                    timestamp,
                ),
            )
        except Exception:
            connection.rollback()
            raise
        else:
            connection.commit()
    finally:
        connection.close()

    return GraphExportResult(
        graph_export_id=graph_export_id,
        run_id=run_id,
        snapshot_id=snapshot.snapshot_id,
        format=format,
        dsl_hash=snapshot.dsl_hash,
        registry_hash=snapshot.registry_hash,
        graph_hash=graph_hash,
        graph_path=paths.graph_path,
        report_path=paths.report_path,
        node_count=len(graph.nodes),
        edge_count=len(graph.edges),
        orphan_count=graph.orphan_count,
        warning_count=len(graph.warnings),
        options=options,
        warnings=graph.warnings,
        separated_graph_paths=tuple(value[1] for value in separated_outputs),
    )


def build_graph_model(content: dict[str, Any], *, options: GraphExportOptions) -> _GraphModel:
    _validate_dsl_content(content)
    traceability = content["traceability"]
    fact_traceability = traceability["facts"]
    relation_traceability = traceability["relations"]

    nodes: dict[str, _GraphNode] = {}
    edges: dict[str, _GraphEdge] = {}
    warnings: list[dict[str, Any]] = []
    orphan_nodes: set[str] = set()
    source_index: dict[str, dict[str, set[str]]] = {}
    entity_keys: set[str] = set()
    fact_index: dict[str, tuple[str, str, dict[str, Any]]] = {}

    entities = _sorted_entities(content["entities"])
    for entity in entities:
        canonical_name = _required_string(entity, "canonical_name", "entity")
        entity_keys.add(canonical_name)
        facts = _entity_facts(entity)
        fact_ids = [_required_string(fact, "fact_id", "fact") for fact in facts]
        source_ids = _source_ids_for_facts(fact_traceability, fact_ids)
        for fact in facts:
            fact_index[_required_string(fact, "fact_id", "fact")] = (
                canonical_name,
                _entity_label(entity),
                fact,
            )
            _remember_sources(source_index, fact_traceability.get(fact["fact_id"], []))
        _add_node(
            nodes,
            _GraphNode(
                node_id=_entity_node_id(canonical_name),
                label=_entity_label(entity),
                attributes={
                    "canonical_name": canonical_name,
                    "fact_count": len(facts),
                    "fact_ids": _inline_json(sorted(fact_ids)),
                    "label": _entity_label(entity),
                    "node_id": _entity_node_id(canonical_name),
                    "node_type": "domain_entity",
                    "source_count": len(source_ids),
                    "source_ids": _inline_json(source_ids),
                    "status": str(entity.get("status") or "active"),
                },
            ),
        )

    if options.include_fact_nodes:
        for entity in entities:
            canonical_name = _required_string(entity, "canonical_name", "entity")
            entity_label = _entity_label(entity)
            for fact in _sorted_facts(_entity_facts(entity)):
                if not _include_fact_node(fact, include_temporal=options.dynamic):
                    continue
                fact_id = _required_string(fact, "fact_id", "fact")
                _add_fact_node(nodes, fact, canonical_name, entity_label, fact_traceability)
                _add_edge(
                    edges,
                    _GraphEdge(
                        edge_id=f"mentions:{fact_id}",
                        source=_entity_node_id(canonical_name),
                        target=_fact_node_id(fact_id),
                        label="mentions",
                        attributes={
                            "assertion_type": fact.get("assertion_type") or "",
                            "confidence": fact.get("confidence") or "",
                            "edge_id": f"mentions:{fact_id}",
                            "edge_type": "mentions",
                            "fact_id": fact_id,
                            "owner_id": fact_id,
                            "owner_type": "fact",
                            "source_entity": canonical_name,
                            "source_ids": _inline_json(_source_ids_for_owner(fact_traceability, fact_id)),
                            "status": fact.get("status") or "",
                            "target_entity": fact.get("property_name") or "",
                        },
                    ),
                )

    for relation in _sorted_relations(content["relations"]):
        relation_id = _required_string(relation, "relation_id", "relation")
        source_entity = _required_string(relation, "canonical_source_entity", "relation")
        target_entity = _required_string(relation, "canonical_target_entity", "relation")
        _remember_sources(source_index, relation_traceability.get(relation_id, []))

        for endpoint_name, role in ((source_entity, "source"), (target_entity, "target")):
            if endpoint_name in entity_keys:
                continue
            if options.strict_orphans:
                raise GraphExportError(
                    "strict_orphans: "
                    f"relation {relation_id} references missing {role} entity {endpoint_name}."
                )
            _add_orphan_entity_node(nodes, endpoint_name)
            orphan_nodes.add(endpoint_name)
            warnings.append(
                {
                    "code": "orphan_node_added",
                    "message": (
                        f"relation {relation_id} references missing {role} entity {endpoint_name}"
                    ),
                    "relation_id": relation_id,
                    "role": role,
                    "canonical_entity": endpoint_name,
                }
            )

        _add_edge(
            edges,
            _GraphEdge(
                edge_id=f"relation:{relation_id}",
                source=_entity_node_id(source_entity),
                target=_entity_node_id(target_entity),
                label=str(relation.get("relation_type") or ""),
                attributes={
                    "assertion_type": relation.get("assertion_type") or "",
                    "confidence": relation.get("confidence") or "",
                    "edge_id": f"relation:{relation_id}",
                    "edge_type": relation.get("relation_type") or "",
                    "relation_id": relation_id,
                    "source_entity": relation.get("source_entity") or source_entity,
                    "source_ids": _inline_json(_source_ids_for_owner(relation_traceability, relation_id)),
                    "status": relation.get("status") or "",
                    "target_entity": relation.get("target_entity") or target_entity,
                },
            ),
        )

    if options.include_conflicts:
        _add_conflict_graph_items(
            nodes,
            edges,
            content["conflicts"],
            fact_index=fact_index,
            fact_traceability=fact_traceability,
        )

    if options.include_sources:
        _add_source_graph_items(
            nodes,
            edges,
            entities,
            content["relations"],
            source_index=source_index,
            fact_traceability=fact_traceability,
            relation_traceability=relation_traceability,
        )

    return _GraphModel(
        nodes=tuple(sorted(nodes.values(), key=lambda node: node.node_id)),
        edges=tuple(sorted(edges.values(), key=lambda edge: edge.edge_id)),
        warnings=tuple(_sorted_warnings(warnings)),
        orphan_count=len(orphan_nodes),
    )


def build_dynamic_graph_model(
    content: dict[str, Any],
    *,
    options: GraphExportOptions,
    open_reconciliation_count: int = 0,
) -> _DynamicGraphModel:
    _validate_dsl_content(content)
    metadata = content["metadata"]
    if metadata.get("schema_version") != "2":
        raise GraphExportError("Dynamic GEXF export requires DSL schema 2.")
    temporal = metadata.get("temporal")
    if not isinstance(temporal, dict):
        raise GraphExportError("DSL schema 2 metadata.temporal is missing.")
    declared_timeformat = temporal.get("gexf_timeformat")
    if declared_timeformat not in {"date", "dateTime"}:
        raise GraphExportError("DSL schema 2 temporal timeformat is invalid.")
    timeformat = options.timeformat or str(declared_timeformat)
    profile_differs = timeformat != declared_timeformat
    allow_temporal_omission = (
        options.allow_incomplete or options.temporal_output_mode in {"omit", "separate"}
    )
    if profile_differs and not allow_temporal_omission:
        raise GraphExportError(
            "temporal_profile_incompatible: requested timeformat differs from the snapshot profile.",
            reason="temporal_profile_incompatible",
            exit_code=3,
        )

    base = build_graph_model(content, options=options)
    warnings = list(base.warnings)
    fact_intervals: dict[str, tuple[_DynamicInterval, ...]] = {}
    relation_intervals: dict[str, tuple[_DynamicInterval, ...]] = {}
    omitted = 0
    for entity in _sorted_entities(content["entities"]):
        for fact in _sorted_facts(_entity_facts(entity)):
            fact_id = _required_string(fact, "fact_id", "fact")
            intervals, count = _dynamic_intervals(
                fact.get("intervals"),
                timeformat=timeformat,
                allow_incomplete=allow_temporal_omission,
                omit_all=False,
                owner=f"fact/{fact_id}",
            )
            fact_intervals[fact_id] = intervals
            omitted += count
    for relation in _sorted_relations(content["relations"]):
        relation_id = _required_string(relation, "relation_id", "relation")
        intervals, count = _dynamic_intervals(
            relation.get("intervals"),
            timeformat=timeformat,
            allow_incomplete=allow_temporal_omission,
            omit_all=False,
            owner=f"relation/{relation_id}",
        )
        relation_intervals[relation_id] = intervals
        omitted += count
    if omitted:
        warnings.append(
            {
                "code": "temporal_profile_incompatible",
                "message": f"Omitted {omitted} interval(s) from the dynamic export.",
                "omitted_intervals": omitted,
            }
        )
    incomplete = metadata.get("incomplete")
    if isinstance(incomplete, dict) and incomplete.get("open_reconciliations"):
        warnings.append(
            {
                "code": "reconciliation_required",
                "message": (
                    "Dynamic export is based on effective state while reconciliation "
                    f"remains open ({incomplete['open_reconciliations']})."
                ),
            }
        )
    elif open_reconciliation_count:
        warnings.append(
            {
                "code": "reconciliation_required",
                "message": (
                    "Dynamic export was explicitly allowed while reconciliation "
                    f"remains open ({open_reconciliation_count})."
                ),
            }
        )

    dynamic_nodes = []
    for node in base.nodes:
        intervals: tuple[_DynamicInterval, ...] = ()
        if node.node_id.startswith("fact:"):
            intervals = fact_intervals.get(node.node_id.removeprefix("fact:"), ())
        dynamic_nodes.append(_DynamicNode(node=node, intervals=intervals))
    dynamic_edges = []
    for edge in base.edges:
        intervals = ()
        if edge.edge_id.startswith("relation:"):
            intervals = relation_intervals.get(edge.edge_id.removeprefix("relation:"), ())
        elif edge.edge_id.startswith("mentions:"):
            intervals = fact_intervals.get(edge.edge_id.removeprefix("mentions:"), ())
        dynamic_edges.append(_DynamicEdge(edge=edge, intervals=intervals))
    timezone = temporal.get("timezone")
    return _DynamicGraphModel(
        nodes=tuple(dynamic_nodes),
        edges=tuple(dynamic_edges),
        warnings=tuple(_sorted_warnings(warnings)),
        orphan_count=base.orphan_count,
        timeformat=timeformat,
        timezone=(str(timezone) if timezone not in {None, "unknown"} else None),
    )


def _dynamic_intervals(
    raw_intervals: Any,
    *,
    timeformat: str,
    allow_incomplete: bool,
    omit_all: bool,
    owner: str,
) -> tuple[tuple[_DynamicInterval, ...], int]:
    if not isinstance(raw_intervals, list):
        raise GraphExportError(f"DSL schema 2 {owner} intervals must be a list.")
    result: list[_DynamicInterval] = []
    omitted = 0
    for value in raw_intervals:
        if not isinstance(value, dict):
            raise GraphExportError(f"DSL schema 2 {owner} interval must be an object.")
        is_date = value.get("timeformat") == "date"
        compatible = (
            not omit_all
            and value.get("timeformat") == timeformat
            and value.get("bounds_semantics") in {"inclusive", "coverage_envelope"}
            and (
                is_date
                or value.get("timezone") not in {None, "unknown", "incompatible"}
            )
        )
        if not compatible:
            if allow_incomplete:
                omitted += 1
                continue
            raise GraphExportError(
                f"temporal_profile_incompatible: {owner} interval is unresolved or incompatible.",
                reason="temporal_profile_incompatible",
                exit_code=3,
            )
        start = value.get("start")
        end = value.get("end")
        if start is None and end is None:
            raise GraphExportError(f"DSL schema 2 {owner} interval has no bounds.")
        result.append(
            _DynamicInterval(
                start=str(start) if start is not None else None,
                end=str(end) if end is not None else None,
            )
        )
    return tuple(sorted(result, key=lambda value: (value.start or "", value.end or ""))), omitted


def render_dynamic_gexf(graph: _DynamicGraphModel) -> str:
    ET.register_namespace("", GEXF_NAMESPACE)
    qname = lambda name: f"{{{GEXF_NAMESPACE}}}{name}"
    root = ET.Element(qname("gexf"), {"version": "1.3"})
    graph_attributes = {
        "defaultedgetype": "directed",
        "mode": "dynamic",
        "timeformat": graph.timeformat,
        "timerepresentation": "interval",
    }
    if graph.timezone is not None:
        graph_attributes["timezone"] = graph.timezone
    graph_element = ET.SubElement(root, qname("graph"), graph_attributes)
    _append_attributes_ns(graph_element, "node", NODE_ATTRIBUTES, qname)
    _append_attributes_ns(graph_element, "edge", EDGE_ATTRIBUTES, qname)
    nodes_element = ET.SubElement(graph_element, qname("nodes"))
    node_attr_ids = _attribute_ids("node", NODE_ATTRIBUTES)
    for item in graph.nodes:
        node_element = ET.SubElement(
            nodes_element,
            qname("node"),
            _dynamic_element_attributes(item.node.node_id, item.node.label, item.intervals),
        )
        _append_attvalues_ns(
            node_element,
            item.node.attributes,
            node_attr_ids,
            NODE_ATTRIBUTES,
            qname,
        )
        _append_spells_ns(node_element, item.intervals, qname)
    edges_element = ET.SubElement(graph_element, qname("edges"))
    edge_attr_ids = _attribute_ids("edge", EDGE_ATTRIBUTES)
    for item in graph.edges:
        attributes = {
            "id": item.edge.edge_id,
            "label": item.edge.label,
            "source": item.edge.source,
            "target": item.edge.target,
            "type": "directed",
        }
        attributes.update(_interval_attributes(item.intervals))
        edge_element = ET.SubElement(edges_element, qname("edge"), attributes)
        _append_attvalues_ns(
            edge_element,
            item.edge.attributes,
            edge_attr_ids,
            EDGE_ATTRIBUTES,
            qname,
        )
        _append_spells_ns(edge_element, item.intervals, qname)
    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="unicode", xml_declaration=True) + "\n"


def _dynamic_element_attributes(
    identifier: str,
    label: str,
    intervals: tuple[_DynamicInterval, ...],
) -> dict[str, str]:
    result = {"id": identifier, "label": label}
    result.update(_interval_attributes(intervals))
    return result


def _interval_attributes(intervals: tuple[_DynamicInterval, ...]) -> dict[str, str]:
    if len(intervals) != 1:
        return {}
    interval = intervals[0]
    return {
        **({"start": interval.start} if interval.start is not None else {}),
        **({"end": interval.end} if interval.end is not None else {}),
    }


def _append_spells_ns(
    parent: ET.Element,
    intervals: tuple[_DynamicInterval, ...],
    qname: Any,
) -> None:
    if len(intervals) <= 1:
        return
    spells = ET.SubElement(parent, qname("spells"))
    for interval in intervals:
        ET.SubElement(
            spells,
            qname("spell"),
            {
                **({"start": interval.start} if interval.start is not None else {}),
                **({"end": interval.end} if interval.end is not None else {}),
            },
        )


def _content_timeformats(content: dict[str, Any]) -> set[str]:
    formats: set[str] = set()
    for entity in content.get("entities", []):
        for fact in entity.get("facts", []):
            formats.update(
                str(value["timeformat"])
                for value in fact.get("intervals", [])
                if isinstance(value, dict) and value.get("timeformat") in {"date", "dateTime"}
            )
    for relation in content.get("relations", []):
        formats.update(
            str(value["timeformat"])
            for value in relation.get("intervals", [])
            if isinstance(value, dict) and value.get("timeformat") in {"date", "dateTime"}
        )
    return formats


def render_gexf(graph: _GraphModel) -> str:
    ET.register_namespace("", GEXF_NS)
    root = ET.Element(_qname("gexf"), {"version": "1.2"})
    graph_element = ET.SubElement(
        root,
        _qname("graph"),
        {"defaultedgetype": "directed", "mode": "static"},
    )
    _append_attributes(graph_element, "node", NODE_ATTRIBUTES)
    _append_attributes(graph_element, "edge", EDGE_ATTRIBUTES)

    nodes_element = ET.SubElement(graph_element, _qname("nodes"))
    node_attr_ids = _attribute_ids("node", NODE_ATTRIBUTES)
    for node in graph.nodes:
        node_element = ET.SubElement(
            nodes_element,
            _qname("node"),
            {"id": node.node_id, "label": node.label},
        )
        _append_attvalues(node_element, node.attributes, node_attr_ids, NODE_ATTRIBUTES)

    edges_element = ET.SubElement(graph_element, _qname("edges"))
    edge_attr_ids = _attribute_ids("edge", EDGE_ATTRIBUTES)
    for edge in graph.edges:
        edge_element = ET.SubElement(
            edges_element,
            _qname("edge"),
            {
                "id": edge.edge_id,
                "label": edge.label,
                "source": edge.source,
                "target": edge.target,
                "type": "directed",
            },
        )
        _append_attvalues(edge_element, edge.attributes, edge_attr_ids, EDGE_ATTRIBUTES)

    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="unicode", xml_declaration=True) + "\n"


def write_graph_export_artifacts(workspace_dir: str | Path, result: GraphExportResult) -> None:
    artifacts = run_artifact_paths(workspace_dir, result.run_id)
    payload = result.to_artifact_payload()
    input_document = {
        "artifact_dir": artifacts.artifact_dir_relative,
        "parameters": {
            "format": result.format,
            "options": result.options.to_payload(),
            "output_dir": str(Path(result.graph_path).parent).replace("\\", "/"),
            "snapshot_id": result.snapshot_id,
        },
        "run_id": result.run_id,
        "run_type": "gexf_export",
        **payload,
    }
    artifacts.input_path.write_text(canonical_json(input_document), encoding="utf-8", newline="\n")

    report = json.loads(artifacts.process_report_path.read_text(encoding="utf-8"))
    report.update(payload)
    write_process_report(artifacts.process_report_path, report)


def _resolve_output_dir(workspace_dir: Path, output_dir: str | Path | None) -> Path:
    configured = "exports/graph" if output_dir is None else output_dir
    try:
        return resolve_workspace_path(workspace_dir, configured)
    except DatabaseConfigurationError as exc:
        raise GraphExportError(f"Output path escapes the workspace: {output_dir}") from exc


def _graph_paths(workspace_dir: Path, output_dir: Path, snapshot_id: str) -> _GraphPaths:
    graph_file = output_dir / f"{snapshot_id}.gexf"
    report_file = output_dir / f"{snapshot_id}.graph_report.json"
    return _GraphPaths(
        graph_file=graph_file,
        report_file=report_file,
        graph_path=relative_workspace_path(workspace_dir, graph_file),
        report_path=relative_workspace_path(workspace_dir, report_file),
    )


def _load_snapshot(connection: sqlite3.Connection, snapshot_id: str) -> _Snapshot:
    row = connection.execute(
        """
        SELECT snapshot_id, dsl_hash, content_json, status
        FROM dsl_snapshots
        WHERE snapshot_id = ?
        """,
        (snapshot_id,),
    ).fetchone()
    if row is None:
        raise GraphExportError(f"Snapshot not found: {snapshot_id}.")
    if row["status"] != "completed":
        raise GraphExportError(
            f"Snapshot {snapshot_id} must have status completed; current status is {row['status']}."
        )

    try:
        content = json.loads(row["content_json"])
    except json.JSONDecodeError as exc:
        raise GraphExportError(f"Snapshot {snapshot_id} content_json is not valid JSON.") from exc
    if not isinstance(content, dict):
        raise GraphExportError(f"Snapshot {snapshot_id} content_json must be a JSON object.")

    _validate_dsl_content(content, snapshot_id=snapshot_id)
    metadata = content["metadata"]
    if metadata.get("dsl_hash") != row["dsl_hash"]:
        raise GraphExportError(
            f"Snapshot {snapshot_id} metadata.dsl_hash does not match dsl_snapshots.dsl_hash."
        )

    return _Snapshot(
        snapshot_id=row["snapshot_id"],
        dsl_hash=row["dsl_hash"],
        registry_hash=metadata["registry_hash"],
        content=content,
    )


def _validate_dsl_content(content: dict[str, Any], *, snapshot_id: str | None = None) -> None:
    label = f"Snapshot {snapshot_id}" if snapshot_id else "DSL snapshot"
    metadata = content.get("metadata")
    if not isinstance(metadata, dict):
        raise GraphExportError(f"{label} is missing metadata.")
    schema_version = metadata.get("schema_version")
    if schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        raise GraphExportError(
            f"{label} metadata.schema_version is not supported: {schema_version}."
        )
    if not isinstance(metadata.get("dsl_hash"), str) or not metadata["dsl_hash"]:
        raise GraphExportError(f"{label} metadata.dsl_hash is missing.")
    if not isinstance(metadata.get("registry_hash"), str) or not metadata["registry_hash"]:
        raise GraphExportError(f"{label} metadata.registry_hash is missing.")

    for section_name in ("entities", "relations", "conflicts"):
        if not isinstance(content.get(section_name), list):
            raise GraphExportError(f"{label} section {section_name} must be a list.")

    traceability = content.get("traceability")
    if not isinstance(traceability, dict):
        raise GraphExportError(f"{label} is missing traceability.")
    for section_name in ("facts", "relations"):
        if not isinstance(traceability.get(section_name), dict):
            raise GraphExportError(f"{label} traceability.{section_name} must be an object.")
    if schema_version == "2":
        if not isinstance(traceability.get("temporal"), dict):
            raise GraphExportError(f"{label} traceability.temporal must be an object.")
        temporal = metadata.get("temporal")
        if not isinstance(temporal, dict):
            raise GraphExportError(f"{label} metadata.temporal is missing.")
        if (
            temporal.get("representation") != "interval"
            or temporal.get("base") not in {"day", "timestamp"}
            or temporal.get("gexf_timeformat") not in {"date", "dateTime"}
            or temporal.get("timezone") in {None, ""}
        ):
            raise GraphExportError(f"{label} metadata.temporal is invalid.")
        expected_format = "date" if temporal["base"] == "day" else "dateTime"
        if temporal["gexf_timeformat"] != expected_format:
            raise GraphExportError(f"{label} metadata.temporal mapping is inconsistent.")
        for entity in content["entities"]:
            if not isinstance(entity, dict):
                raise GraphExportError(f"{label} entity items must be objects.")
            for fact in _entity_facts(entity):
                if not isinstance(fact, dict) or not isinstance(fact.get("intervals"), list):
                    raise GraphExportError(f"{label} schema 2 facts require intervals lists.")
        for relation in content["relations"]:
            if not isinstance(relation, dict) or not isinstance(
                relation.get("intervals"), list
            ):
                raise GraphExportError(f"{label} schema 2 relations require intervals lists.")


def _add_source_graph_items(
    nodes: dict[str, _GraphNode],
    edges: dict[str, _GraphEdge],
    entities: list[dict[str, Any]],
    relations: list[dict[str, Any]],
    *,
    source_index: dict[str, dict[str, set[str]]],
    fact_traceability: dict[str, Any],
    relation_traceability: dict[str, Any],
) -> None:
    for source_id in sorted(source_index):
        source_data = source_index[source_id]
        file_paths = sorted(source_data["file_paths"])
        source_revision_ids = sorted(source_data["source_revision_ids"])
        label = file_paths[0] if file_paths else source_id
        _add_node(
            nodes,
            _GraphNode(
                node_id=_source_node_id(source_id),
                label=label,
                attributes={
                    "file_path": label,
                    "file_paths": _inline_json(file_paths),
                    "label": label,
                    "node_id": _source_node_id(source_id),
                    "node_type": "source",
                    "source_id": source_id,
                    "source_revision_ids": _inline_json(source_revision_ids),
                    "status": "active",
                },
            ),
        )

    for entity in _sorted_entities(entities):
        canonical_name = _required_string(entity, "canonical_name", "entity")
        for fact in _sorted_facts(_entity_facts(entity)):
            fact_id = _required_string(fact, "fact_id", "fact")
            target = _fact_node_id(fact_id) if _fact_node_id(fact_id) in nodes else _entity_node_id(canonical_name)
            for source_id in _source_ids_for_owner(fact_traceability, fact_id):
                revisions = _source_revision_ids_for_owner(fact_traceability, fact_id, source_id)
                _add_edge(
                    edges,
                    _GraphEdge(
                        edge_id=f"source-fact:{source_id}:{fact_id}",
                        source=_source_node_id(source_id),
                        target=target,
                        label="derives_from",
                        attributes={
                            "edge_id": f"source-fact:{source_id}:{fact_id}",
                            "edge_type": "derives_from",
                            "fact_id": fact_id,
                            "owner_id": fact_id,
                            "owner_type": "fact",
                            "source_id": source_id,
                            "source_revision_ids": _inline_json(revisions),
                        },
                    ),
                )

    for relation in _sorted_relations(relations):
        relation_id = _required_string(relation, "relation_id", "relation")
        target_entity = _required_string(relation, "canonical_target_entity", "relation")
        target = _entity_node_id(target_entity)
        if target not in nodes:
            continue
        for source_id in _source_ids_for_owner(relation_traceability, relation_id):
            revisions = _source_revision_ids_for_owner(relation_traceability, relation_id, source_id)
            _add_edge(
                edges,
                _GraphEdge(
                    edge_id=f"source-relation:{source_id}:{relation_id}",
                    source=_source_node_id(source_id),
                    target=target,
                    label="derives_from",
                    attributes={
                        "edge_id": f"source-relation:{source_id}:{relation_id}",
                        "edge_type": "derives_from",
                        "owner_id": relation_id,
                        "owner_type": "relation",
                        "relation_id": relation_id,
                        "source_id": source_id,
                        "source_revision_ids": _inline_json(revisions),
                    },
                ),
            )


def _add_conflict_graph_items(
    nodes: dict[str, _GraphNode],
    edges: dict[str, _GraphEdge],
    conflicts: list[Any],
    *,
    fact_index: dict[str, tuple[str, str, dict[str, Any]]],
    fact_traceability: dict[str, Any],
) -> None:
    for conflict in _sorted_conflicts(conflicts):
        if str(conflict.get("status") or "") != "open":
            continue
        conflict_id = _required_string(conflict, "conflict_id", "conflict")
        label = ".".join(
            value
            for value in (
                conflict.get("canonical_entity_name"),
                conflict.get("property_name"),
                "conflict",
            )
            if isinstance(value, str) and value
        )
        _add_node(
            nodes,
            _GraphNode(
                node_id=_conflict_node_id(conflict_id),
                label=label or conflict_id,
                attributes={
                    "canonical_name": conflict.get("canonical_entity_name") or "",
                    "conflict_id": conflict_id,
                    "conflict_type": conflict.get("conflict_type") or "",
                    "label": label or conflict_id,
                    "left_fact_id": conflict.get("left_fact_id") or "",
                    "node_id": _conflict_node_id(conflict_id),
                    "node_type": "conflict",
                    "property_name": conflict.get("property_name") or "",
                    "right_fact_id": conflict.get("right_fact_id") or "",
                    "status": conflict.get("status") or "",
                },
            ),
        )
        for side in ("left", "right"):
            fact_id = _required_string(conflict, f"{side}_fact_id", "conflict")
            if _fact_node_id(fact_id) not in nodes:
                indexed = fact_index.get(fact_id)
                if indexed is None:
                    _add_placeholder_fact_node(nodes, fact_id)
                else:
                    canonical_name, entity_label, fact = indexed
                    _add_fact_node(nodes, fact, canonical_name, entity_label, fact_traceability)
            _add_edge(
                edges,
                _GraphEdge(
                    edge_id=f"conflict:{conflict_id}:{side}",
                    source=_conflict_node_id(conflict_id),
                    target=_fact_node_id(fact_id),
                    label="conflicts_with",
                    attributes={
                        "conflict_id": conflict_id,
                        "conflict_side": side,
                        "edge_id": f"conflict:{conflict_id}:{side}",
                        "edge_type": "conflicts_with",
                        "fact_id": fact_id,
                        "owner_id": conflict_id,
                        "owner_type": "conflict",
                        "status": conflict.get("status") or "",
                    },
                ),
            )


def _add_fact_node(
    nodes: dict[str, _GraphNode],
    fact: dict[str, Any],
    canonical_name: str,
    entity_label: str,
    fact_traceability: dict[str, Any],
) -> None:
    fact_id = _required_string(fact, "fact_id", "fact")
    fact_type = _required_string(fact, "fact_type", "fact")
    property_name = _required_string(fact, "property_name", "fact")
    source_ids = _source_ids_for_owner(fact_traceability, fact_id)
    label = f"{entity_label}.{property_name}"
    _add_node(
        nodes,
        _GraphNode(
            node_id=_fact_node_id(fact_id),
            label=label,
            attributes={
                "assertion_type": fact.get("assertion_type") or "",
                "canonical_name": canonical_name,
                "confidence": fact.get("confidence") or "",
                "fact_id": fact_id,
                "fact_type": fact_type,
                "label": label,
                "node_id": _fact_node_id(fact_id),
                "node_type": fact_type if fact_type == "business_rule" else "fact",
                "property_name": property_name,
                "source_count": len(source_ids),
                "source_ids": _inline_json(source_ids),
                "status": fact.get("status") or "",
            },
        ),
    )


def _add_placeholder_fact_node(nodes: dict[str, _GraphNode], fact_id: str) -> None:
    _add_node(
        nodes,
        _GraphNode(
            node_id=_fact_node_id(fact_id),
            label=fact_id,
            attributes={
                "fact_id": fact_id,
                "label": fact_id,
                "node_id": _fact_node_id(fact_id),
                "node_type": "fact",
                "status": "orphaned",
            },
        ),
    )


def _add_orphan_entity_node(nodes: dict[str, _GraphNode], canonical_name: str) -> None:
    _add_node(
        nodes,
        _GraphNode(
            node_id=_entity_node_id(canonical_name),
            label=canonical_name,
            attributes={
                "canonical_name": canonical_name,
                "fact_count": 0,
                "fact_ids": _inline_json([]),
                "label": canonical_name,
                "node_id": _entity_node_id(canonical_name),
                "node_type": "domain_entity",
                "source_count": 0,
                "source_ids": _inline_json([]),
                "status": "orphaned",
            },
        ),
    )


def _add_node(nodes: dict[str, _GraphNode], node: _GraphNode) -> None:
    nodes.setdefault(node.node_id, node)


def _add_edge(edges: dict[str, _GraphEdge], edge: _GraphEdge) -> None:
    edges.setdefault(edge.edge_id, edge)


def _append_attributes(
    graph_element: ET.Element,
    klass: str,
    attributes: tuple[tuple[str, str], ...],
) -> None:
    attrs_element = ET.SubElement(
        graph_element,
        _qname("attributes"),
        {"class": klass, "mode": "static"},
    )
    for index, (title, attr_type) in enumerate(attributes):
        ET.SubElement(
            attrs_element,
            _qname("attribute"),
            {"id": f"{klass}_{index}", "title": title, "type": attr_type},
        )


def _append_attributes_ns(
    graph_element: ET.Element,
    klass: str,
    attributes: tuple[tuple[str, str], ...],
    qname: Any,
) -> None:
    attrs_element = ET.SubElement(
        graph_element,
        qname("attributes"),
        {"class": klass, "mode": "static"},
    )
    for index, (title, attr_type) in enumerate(attributes):
        ET.SubElement(
            attrs_element,
            qname("attribute"),
            {"id": f"{klass}_{index}", "title": title, "type": attr_type},
        )


def _append_attvalues(
    element: ET.Element,
    values: dict[str, Any],
    attr_ids: dict[str, str],
    attributes: tuple[tuple[str, str], ...],
) -> None:
    present_values = {
        title: values[title]
        for title, _attr_type in attributes
        if title in values and values[title] is not None
    }
    if not present_values:
        return

    attvalues = ET.SubElement(element, _qname("attvalues"))
    for title in present_values:
        ET.SubElement(
            attvalues,
            _qname("attvalue"),
            {"for": attr_ids[title], "value": _xml_value(present_values[title])},
        )


def _append_attvalues_ns(
    element: ET.Element,
    values: dict[str, Any],
    attr_ids: dict[str, str],
    attributes: tuple[tuple[str, str], ...],
    qname: Any,
) -> None:
    present_values = {
        title: values[title]
        for title, _attr_type in attributes
        if title in values and values[title] is not None
    }
    if not present_values:
        return
    attvalues = ET.SubElement(element, qname("attvalues"))
    for title in present_values:
        ET.SubElement(
            attvalues,
            qname("attvalue"),
            {"for": attr_ids[title], "value": _xml_value(present_values[title])},
        )


def _attribute_ids(klass: str, attributes: tuple[tuple[str, str], ...]) -> dict[str, str]:
    return {title: f"{klass}_{index}" for index, (title, _attr_type) in enumerate(attributes)}


def _qname(name: str) -> str:
    return f"{{{GEXF_NS}}}{name}"


def _xml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _build_report(
    *,
    graph_export_id: str,
    run_id: str,
    snapshot: _Snapshot,
    format: str,
    graph_hash: str,
    paths: _GraphPaths,
    graph: _GraphModel | _DynamicGraphModel,
    options: GraphExportOptions,
) -> dict[str, Any]:
    return {
        "dsl_hash": snapshot.dsl_hash,
        "edge_count": len(graph.edges),
        "format": format,
        "graph_export_id": graph_export_id,
        "graph_hash": graph_hash,
        "graph_path": paths.graph_path,
        "node_count": len(graph.nodes),
        "options": options.to_payload(),
        "orphan_count": graph.orphan_count,
        "registry_hash": snapshot.registry_hash,
        "report_path": paths.report_path,
        "run_id": run_id,
        "snapshot_id": snapshot.snapshot_id,
        "warning_count": len(graph.warnings),
        "warnings": list(graph.warnings),
    }


def _graph_hash(
    snapshot: _Snapshot,
    graph: _GraphModel | _DynamicGraphModel,
    *,
    options: GraphExportOptions,
    format: str,
) -> str:
    payload = {
        "dsl_hash": snapshot.dsl_hash,
        "format": format,
        "graph": graph.payload(),
        "options": options.to_payload(),
        "schema_version": snapshot.content["metadata"]["schema_version"],
    }
    if not options.dynamic:
        payload["snapshot_id"] = snapshot.snapshot_id
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def _sorted_entities(values: Iterable[Any]) -> list[dict[str, Any]]:
    entities = []
    for value in values:
        if not isinstance(value, dict):
            raise GraphExportError("DSL entity items must be objects.")
        entities.append(copy.deepcopy(value))
    return sorted(
        entities,
        key=lambda entity: (
            entity.get("canonical_name") or "",
            entity.get("name") or "",
        ),
    )


def _sorted_facts(values: Iterable[Any]) -> list[dict[str, Any]]:
    facts = []
    for value in values:
        if not isinstance(value, dict):
            raise GraphExportError("DSL fact items must be objects.")
        facts.append(copy.deepcopy(value))
    return sorted(
        facts,
        key=lambda fact: (
            fact.get("fact_type") or "",
            fact.get("property_name") or "",
            fact.get("fact_id") or "",
        ),
    )


def _sorted_relations(values: Iterable[Any]) -> list[dict[str, Any]]:
    relations = []
    for value in values:
        if not isinstance(value, dict):
            raise GraphExportError("DSL relation items must be objects.")
        relations.append(copy.deepcopy(value))
    return sorted(
        relations,
        key=lambda relation: (
            relation.get("canonical_source_entity") or "",
            relation.get("relation_type") or "",
            relation.get("canonical_target_entity") or "",
            relation.get("relation_id") or "",
        ),
    )


def _sorted_conflicts(values: Iterable[Any]) -> list[dict[str, Any]]:
    conflicts = []
    for value in values:
        if not isinstance(value, dict):
            raise GraphExportError("DSL conflict items must be objects.")
        conflicts.append(copy.deepcopy(value))
    return sorted(
        conflicts,
        key=lambda conflict: (
            conflict.get("conflict_type") or "",
            conflict.get("canonical_entity_name") or "",
            conflict.get("property_name") or "",
            conflict.get("conflict_id") or "",
        ),
    )


def _sorted_warnings(warnings: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        (copy.deepcopy(warning) for warning in warnings),
        key=lambda warning: (
            warning.get("code") or "",
            warning.get("relation_id") or "",
            warning.get("role") or "",
            warning.get("canonical_entity") or "",
            warning.get("message") or "",
        ),
    )


def _entity_facts(entity: dict[str, Any]) -> list[Any]:
    facts = entity.get("facts", [])
    if not isinstance(facts, list):
        raise GraphExportError(
            f"Entity {entity.get('canonical_name') or '<unknown>'} facts must be a list."
        )
    return facts


def _entity_label(entity: dict[str, Any]) -> str:
    name = entity.get("name")
    if isinstance(name, str) and name:
        return name
    return _required_string(entity, "canonical_name", "entity")


def _include_fact_node(
    fact: dict[str, Any],
    *,
    include_temporal: bool = False,
) -> bool:
    return fact.get("fact_type") == "business_rule" or (
        include_temporal and bool(fact.get("intervals"))
    )


def _source_ids_for_facts(traceability: dict[str, Any], fact_ids: Iterable[str]) -> list[str]:
    source_ids: set[str] = set()
    for fact_id in fact_ids:
        source_ids.update(_source_ids_for_owner(traceability, fact_id))
    return sorted(source_ids)


def _source_ids_for_owner(traceability: dict[str, Any], owner_id: str) -> list[str]:
    source_ids: set[str] = set()
    for evidence in _traceability_items(traceability, owner_id):
        source_id = evidence.get("source_id")
        if isinstance(source_id, str) and source_id:
            source_ids.add(source_id)
    return sorted(source_ids)


def _source_revision_ids_for_owner(
    traceability: dict[str, Any],
    owner_id: str,
    source_id: str,
) -> list[str]:
    source_revision_ids: set[str] = set()
    for evidence in _traceability_items(traceability, owner_id):
        if evidence.get("source_id") != source_id:
            continue
        revision_id = evidence.get("source_revision_id")
        if isinstance(revision_id, str) and revision_id:
            source_revision_ids.add(revision_id)
    return sorted(source_revision_ids)


def _remember_sources(source_index: dict[str, dict[str, set[str]]], evidence_items: Any) -> None:
    if not isinstance(evidence_items, list):
        return
    for evidence in evidence_items:
        if not isinstance(evidence, dict):
            continue
        source_id = evidence.get("source_id")
        if not isinstance(source_id, str) or not source_id:
            continue
        data = source_index.setdefault(
            source_id,
            {"file_paths": set(), "source_revision_ids": set()},
        )
        file_path = evidence.get("file_path")
        if isinstance(file_path, str) and file_path:
            data["file_paths"].add(file_path)
        source_revision_id = evidence.get("source_revision_id")
        if isinstance(source_revision_id, str) and source_revision_id:
            data["source_revision_ids"].add(source_revision_id)


def _traceability_items(traceability: dict[str, Any], owner_id: str) -> list[dict[str, Any]]:
    raw_items = traceability.get(owner_id, [])
    if not isinstance(raw_items, list):
        raise GraphExportError(f"traceability[{owner_id}] must be a list.")
    items: list[dict[str, Any]] = []
    for item in raw_items:
        if not isinstance(item, dict):
            raise GraphExportError(f"traceability[{owner_id}] items must be objects.")
        items.append(item)
    return items


def _required_string(value: dict[str, Any], key: str, context: str) -> str:
    raw_value = value.get(key)
    if not isinstance(raw_value, str) or raw_value == "":
        raise GraphExportError(f"DSL {context} is missing {key}.")
    return raw_value


def _entity_node_id(canonical_name: str) -> str:
    return f"entity:{canonical_name}"


def _fact_node_id(fact_id: str) -> str:
    return f"fact:{fact_id}"


def _source_node_id(source_id: str) -> str:
    return f"source:{source_id}"


def _conflict_node_id(conflict_id: str) -> str:
    return f"conflict:{conflict_id}"


def _inline_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
