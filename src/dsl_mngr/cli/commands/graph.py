from __future__ import annotations

import sys
from pathlib import Path

from dsl_mngr.core.config import WorkerProfileError, load_config, load_worker_profile
from dsl_mngr.core.database import (
    DatabaseConfigurationError,
    WorkspaceNotInitializedError,
    resolve_workspace_path,
)
from dsl_mngr.core.graph_export import (
    GraphExportDatabaseNotReadyError,
    GraphExportError,
    GraphExportOptions,
    GraphExportResult,
    ensure_graph_export_database_ready,
    export_gexf_from_snapshot,
    write_graph_export_artifacts,
)
from dsl_mngr.core.logging_setup import log_event
from dsl_mngr.core.runs import (
    DatabaseNotReadyError,
    RunLifecycleError,
    complete_run,
    fail_run,
    start_run,
)


def run_graph_export_command(args: object) -> int:
    workspace = Path(getattr(args, "workspace"))
    snapshot_id = getattr(args, "snapshot_id")
    output_dir = getattr(args, "output_dir", None)
    export_format = getattr(args, "format", "gexf")
    strict_orphans = bool(getattr(args, "strict_orphans", False))

    if export_format != "gexf":
        print(
            f"Error: Unsupported graph export format: {export_format}. Expected: gexf.",
            file=sys.stderr,
        )
        return 2

    try:
        ensure_graph_export_database_ready(workspace)
        options = _load_graph_options(workspace, strict_orphans=strict_orphans)
        started = start_run(
            workspace,
            run_type="gexf_export",
            input_payload={
                "format": export_format,
                "options": options.to_payload(),
                "output_dir": output_dir or "exports/graph",
                "snapshot_id": snapshot_id,
            },
        )
    except (
        DatabaseConfigurationError,
        DatabaseNotReadyError,
        GraphExportDatabaseNotReadyError,
        GraphExportError,
        RunLifecycleError,
        WorkerProfileError,
        WorkspaceNotInitializedError,
    ) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    try:
        result = export_gexf_from_snapshot(
            workspace,
            run_id=started.record.run_id,
            snapshot_id=snapshot_id,
            output_dir=output_dir,
            format=export_format,
            options=options,
        )
        complete_run(
            workspace,
            started.record.run_id,
            output_payload=result.to_artifact_payload(),
        )
        write_graph_export_artifacts(workspace, result)
    except (
        DatabaseConfigurationError,
        DatabaseNotReadyError,
        GraphExportDatabaseNotReadyError,
        GraphExportError,
        RunLifecycleError,
        WorkspaceNotInitializedError,
    ) as exc:
        _mark_started_run_failed(workspace, started.record.run_id, str(exc))
        _log_graph_export_failed(started.artifacts.workspace_dir, started.record.run_id, str(exc))
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    _log_graph_export_completed(started.artifacts.workspace_dir, result)
    _print_result(result)
    return 0


def _load_graph_options(workspace: Path, *, strict_orphans: bool) -> GraphExportOptions:
    profile_path = workspace / "configs" / "workers" / "gexf.default.yaml"
    if not profile_path.is_file():
        return GraphExportOptions(strict_orphans=strict_orphans)

    profile = load_worker_profile(
        workspace,
        "gexf.default",
        required_sections=("worker", "graph"),
    )
    graph = profile["graph"]
    return GraphExportOptions(
        include_sources=bool(graph.get("include_sources", True)),
        include_fact_nodes=bool(graph.get("include_fact_nodes", True)),
        include_conflicts=bool(graph.get("include_conflicts", True)),
        strict_orphans=strict_orphans or bool(graph.get("strict_orphans", False)),
        directed=bool(graph.get("directed", True)),
        node_label_strategy=str(graph.get("node_label_strategy", "readable")),
    )


def _print_result(result: GraphExportResult) -> None:
    print(f"Run: {result.run_id}")
    print(f"Graph export: {result.graph_export_id}")
    print(f"Snapshot: {result.snapshot_id}")
    print(f"Format: {result.format}")
    print(f"DSL hash: {result.dsl_hash}")
    print(f"Graph hash: {result.graph_hash}")
    print(f"Nodes: {result.node_count}")
    print(f"Edges: {result.edge_count}")
    print(f"Orphans: {result.orphan_count}")
    print(f"Warnings: {result.warning_count}")
    print(f"GEXF: {result.graph_path}")
    print(f"Report: {result.report_path}")
    if result.warnings:
        print("Warnings:")
        for warning in result.warnings:
            print(f"- {warning['code']}: {warning['message']}")


def _mark_started_run_failed(workspace: Path, run_id: str, error: str) -> None:
    try:
        fail_run(
            workspace,
            run_id,
            error=error,
            output_payload={"error": error},
        )
    except (
        DatabaseConfigurationError,
        DatabaseNotReadyError,
        RunLifecycleError,
        WorkspaceNotInitializedError,
    ):
        return


def _log_graph_export_completed(workspace_dir: Path, result: GraphExportResult) -> None:
    try:
        log_path = _resolve_app_log_path(workspace_dir)
    except (DatabaseConfigurationError, WorkspaceNotInitializedError):
        return

    log_event(
        log_path,
        level="INFO",
        event="gexf_export_completed",
        message=(
            f"GEXF export completed; snapshot={result.snapshot_id}; "
            f"nodes={result.node_count}; edges={result.edge_count}; "
            f"orphans={result.orphan_count}"
        ),
        run_id=result.run_id,
    )


def _log_graph_export_failed(workspace_dir: Path, run_id: str, error: str) -> None:
    try:
        log_path = _resolve_app_log_path(workspace_dir)
    except (DatabaseConfigurationError, WorkspaceNotInitializedError):
        return

    log_event(
        log_path,
        level="ERROR",
        event="gexf_export_failed",
        message=f"GEXF export failed; error={error}",
        run_id=run_id,
    )


def _resolve_app_log_path(workspace_dir: Path) -> Path:
    config = load_config(workspace_dir)
    logging_config = config.get("logging", {})
    configured_path = logging_config.get("app_log_path", "logs/app.jsonl")
    return resolve_workspace_path(workspace_dir, configured_path)
