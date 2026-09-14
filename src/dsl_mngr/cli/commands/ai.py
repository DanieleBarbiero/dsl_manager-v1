from __future__ import annotations

import sqlite3
import shutil
import sys
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dsl_mngr.core.ai_inbox import (
    AiInboxError,
    AiPackageStaleError,
    import_ai_candidates,
    scan_ai_inbox,
)
from dsl_mngr.core.ai_package import (
    AI_PACKAGE_STATUS_WAITING,
    AiPackageError,
    PreparedAiPackage,
    next_ai_package_id,
    persist_ai_package_output,
    prepare_ai_package_input,
    write_ai_package_process_report,
)
from dsl_mngr.core.ai_selection import (
    AiSelectionError,
    SelectionPlanResult,
    create_selection_plan,
    explain_selection_item,
    list_selection_items,
    prepare_selection_package,
)
from dsl_mngr.core.batch import BatchError, ai_package_batch, batch_cli_lines
from dsl_mngr.core.config import WorkerProfileError, load_config, load_worker_profile
from dsl_mngr.core.database import (
    DatabaseConfigurationError,
    WorkspaceNotInitializedError,
    open_database,
    resolve_database_settings,
    resolve_workspace_path,
)
from dsl_mngr.core.logging_setup import log_event
from dsl_mngr.core.runs import (
    DatabaseNotReadyError,
    RunLifecycleError,
    fail_run,
    start_run,
    timestamp_now,
    validate_database_migrations,
)
from dsl_mngr.core.worker_runner import WorkerRunResult, WorkerRunnerError, run_worker
from dsl_mngr.workers import build_ai_package as build_ai_package_worker


@dataclass(frozen=True)
class AiPackageCommandResult:
    run_id: str
    package_id: str
    status: str
    package_hash: str
    package_path: str
    manifest_path: str
    source_revision_count: int
    chunk_count: int
    fragment_count: int
    worker_result: WorkerRunResult
    selection_plan_id: str | None = None


def run_ai_package_command(args: object) -> int:
    workspace = Path(getattr(args, "workspace"))
    revisions = tuple(getattr(args, "revision", None) or ())
    profile = getattr(args, "profile", None) or "ai_package.default"
    selection_policy = getattr(args, "selection_policy", None)
    selection_plan_id = getattr(args, "selection_plan_id", None)

    try:
        result = build_ai_package(
            workspace,
            revision_ids=revisions,
            profile=profile,
            selection_policy=selection_policy,
            selection_plan_id=selection_plan_id,
        )
    except AiSelectionError as exc:
        print(f"Error [{exc.reason}]: {exc}", file=sys.stderr)
        return exc.exit_code
    except (
        AiPackageError,
        DatabaseConfigurationError,
        DatabaseNotReadyError,
        RunLifecycleError,
        WorkerProfileError,
        WorkerRunnerError,
        WorkspaceNotInitializedError,
    ) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if result.worker_result.status != "completed":
        print(
            "Error: AI package build failed for "
            f"{result.package_id}; run={result.run_id}; exit_code={result.worker_result.exit_code}.",
            file=sys.stderr,
        )
        return 2

    print(f"Run: {result.run_id}")
    print(f"Package: {result.package_id}")
    print(f"Status: {result.status}")
    print(f"Sources: {result.source_revision_count}")
    print(f"Chunks: {result.chunk_count}")
    print(f"Fragments: {result.fragment_count}")
    print(f"Package hash: {result.package_hash}")
    print(f"Outbox: {result.package_path}")
    print(f"Manifest: {result.manifest_path}")
    if result.selection_plan_id is not None:
        print(f"Selection plan: {result.selection_plan_id}")
    return 0


def run_ai_evidence_plan_command(args: object) -> int:
    try:
        result = create_selection_plan(
            Path(getattr(args, "workspace")),
            policy_name=getattr(args, "policy"),
            revision_ids=tuple(getattr(args, "revision", None) or ()),
            profile_name=getattr(args, "profile", None) or "ai_package.default",
        )
    except (
        AiSelectionError,
        DatabaseConfigurationError,
        DatabaseNotReadyError,
        RunLifecycleError,
        WorkerProfileError,
        WorkspaceNotInitializedError,
    ) as exc:
        reason = getattr(exc, "reason", "selection_failed")
        print(f"Error [{reason}]: {exc}", file=sys.stderr)
        return int(getattr(exc, "exit_code", 2))
    _print_selection_plan(result)
    return 0


def run_ai_evidence_list_command(args: object) -> int:
    try:
        items = list_selection_items(
            Path(getattr(args, "workspace")),
            getattr(args, "plan_id"),
            outcome=getattr(args, "outcome", None),
        )
    except (
        AiSelectionError,
        DatabaseConfigurationError,
        DatabaseNotReadyError,
        RunLifecycleError,
        WorkspaceNotInitializedError,
    ) as exc:
        reason = getattr(exc, "reason", "selection_failed")
        print(f"Error [{reason}]: {exc}", file=sys.stderr)
        return int(getattr(exc, "exit_code", 2))
    for item in items:
        rank = "-" if item["rank"] is None else str(item["rank"])
        reasons = ",".join(item["reason_codes"]) or "-"
        print(
            f"{item['outcome']} | rank={rank} | {item['evidence_kind']} | "
            f"{item['evidence_id']} | coverage={item['coverage_state']} | reasons={reasons}"
        )
    return 0


def run_ai_evidence_explain_command(args: object) -> int:
    try:
        payload = explain_selection_item(
            Path(getattr(args, "workspace")),
            getattr(args, "plan_id"),
            getattr(args, "evidence_id"),
        )
    except (
        AiSelectionError,
        DatabaseConfigurationError,
        DatabaseNotReadyError,
        RunLifecycleError,
        WorkspaceNotInitializedError,
    ) as exc:
        reason = getattr(exc, "reason", "selection_failed")
        print(f"Error [{reason}]: {exc}", file=sys.stderr)
        return int(getattr(exc, "exit_code", 2))
    from dsl_mngr.core.runs import canonical_json

    print(canonical_json(payload), end="")
    return 0


def run_ai_package_batch_command(args: object) -> int:
    workspace = Path(getattr(args, "workspace"))
    revisions = tuple(getattr(args, "revision", None) or ())
    profile = getattr(args, "profile", None) or "ai_package.default"
    stop_on_error = bool(getattr(args, "stop_on_error", False))

    try:
        result = ai_package_batch(
            workspace,
            revision_ids=revisions,
            profile=profile,
            stop_on_error=stop_on_error,
        )
    except (
        AiPackageError,
        BatchError,
        DatabaseConfigurationError,
        DatabaseNotReadyError,
        RunLifecycleError,
        WorkerProfileError,
        WorkerRunnerError,
        WorkspaceNotInitializedError,
    ) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print("\n".join(batch_cli_lines(result)))
    return 2 if result.summary["failed"] else 0


def run_ai_inbox_scan_command(args: object) -> int:
    workspace = Path(getattr(args, "workspace"))
    try:
        items = scan_ai_inbox(workspace)
    except (
        AiInboxError,
        AiPackageError,
        DatabaseConfigurationError,
        DatabaseNotReadyError,
        RunLifecycleError,
        WorkspaceNotInitializedError,
    ) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if not items:
        print("No AI candidate files found.")
        return 0

    for item in items:
        exists_label = "exists" if item.package_exists else "missing"
        stale_label = "stale" if item.is_stale else "not stale"
        reason = item.reason or "-"
        print(
            f"{item.package_id} | {item.candidate_file} | "
            f"{exists_label} | {stale_label} | {reason}"
        )
    return 0


def run_ai_import_command(args: object) -> int:
    workspace = Path(getattr(args, "workspace"))
    package_id = getattr(args, "package_id")
    input_path = getattr(args, "input_path", None)
    allow_stale = bool(getattr(args, "allow_stale", False))

    try:
        result = import_ai_candidates(
            workspace,
            package_id=package_id,
            input_path=input_path,
            allow_stale=allow_stale,
        )
    except AiPackageStaleError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except (
        AiInboxError,
        AiPackageError,
        DatabaseConfigurationError,
        DatabaseNotReadyError,
        RunLifecycleError,
        WorkspaceNotInitializedError,
    ) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if result.stale_allowed and result.stale_reason:
        message = (
            f"Import allowed for stale AI package {result.package_id}; "
            f"reason={result.stale_reason}"
        )
        print(f"Warning: {message}", file=sys.stderr)
        log_event(
            _resolve_app_log_path(workspace.resolve()),
            level="WARNING",
            event="ai_import_stale_allowed",
            message=message,
            run_id=result.run_id,
        )

    print(f"Run: {result.run_id}")
    print(f"Package: {result.package_id}")
    print(f"Batch: {result.batch_id}")
    print(f"Total: {result.total_records}")
    print(f"Accepted: {result.accepted_count}")
    print(f"Rejected: {result.rejected_count}")
    print(f"Stale allowed: {_format_bool(result.stale_allowed)}")
    return 0


def build_ai_package(
    workspace_dir: str | Path,
    *,
    revision_ids: tuple[str, ...],
    profile: str,
    parent_run_id: str | None = None,
    selection_policy: str | None = None,
    selection_plan_id: str | None = None,
) -> AiPackageCommandResult:
    settings = resolve_database_settings(workspace_dir)
    if selection_policy is not None and selection_plan_id is not None:
        raise AiSelectionError(
            "--selection-policy and --selection-plan are mutually exclusive.",
            reason="selection_options_conflict",
        )
    if selection_plan_id is not None and revision_ids:
        raise AiSelectionError(
            "--revision cannot be combined with --selection-plan; the plan scope is authoritative.",
            reason="selection_scope_conflict",
        )
    profile_config = load_worker_profile(
        settings.workspace_dir,
        profile,
        required_sections=("worker", "ai_package"),
    )
    worker_config = dict(profile_config["worker"])
    ai_package_options = dict(profile_config["ai_package"])
    worker_version = str(worker_config.get("version", "1.0"))

    selection = None
    if selection_policy is not None:
        plan = create_selection_plan(
            settings.workspace_dir,
            policy_name=selection_policy,
            revision_ids=revision_ids,
            profile_name=profile,
        )
        selection_plan_id = plan.selection_plan_id
        revision_ids = ()
    if selection_plan_id is not None:
        selection = prepare_selection_package(
            settings.workspace_dir,
            plan_id=selection_plan_id,
            profile_name=profile,
        )

    package_id = _allocate_package_id(settings)

    prepared = prepare_ai_package_input(
        settings,
        package_id=package_id,
        revision_ids=revision_ids,
        profile=profile,
        worker_config=worker_config,
        ai_package_options=ai_package_options,
        selection=selection,
    )
    started = start_run(
        settings.workspace_dir,
        run_type="ai_package",
        parent_run_id=parent_run_id,
        input_payload=prepared.worker_input,
        cli_options={
            "ai_package": ai_package_options,
            "profile": {"name": profile},
            "worker": worker_config,
        },
    )

    try:
        worker_result = run_worker(
            settings.workspace_dir,
            run_id=started.record.run_id,
            worker_name="build_ai_package",
            worker_path=Path(build_ai_package_worker.__file__).resolve(),
            worker_version=worker_version,
            input_payload=prepared.worker_input,
            apply_mutations=_persist_ai_package_mutation(
                settings.workspace_dir,
                prepared,
                started.record.run_id,
            ),
        )
    except Exception as exc:
        _cleanup_failed_selection_package(settings.workspace_dir, prepared)
        fail_run(
            settings.workspace_dir,
            started.record.run_id,
            error=f"AI package orchestration failed: {exc}",
        )
        raise

    app_log_path = _resolve_app_log_path(settings.workspace_dir)
    if worker_result.status != "completed":
        _cleanup_failed_selection_package(settings.workspace_dir, prepared)
        log_event(
            app_log_path,
            level="ERROR",
            event="ai_package_failed",
            message=(
                f"AI package build failed; package={package_id}; "
                f"run={started.record.run_id}; exit_code={worker_result.exit_code}"
            ),
            run_id=started.record.run_id,
            worker="build_ai_package",
        )
        return AiPackageCommandResult(
            run_id=started.record.run_id,
            package_id=package_id,
            status="failed",
            package_hash="",
            package_path=prepared.output_dir,
            manifest_path="",
            source_revision_count=prepared.source_revision_count,
            chunk_count=prepared.chunk_count,
            fragment_count=prepared.fragment_count,
            worker_result=worker_result,
            selection_plan_id=prepared.selection_plan_id,
        )

    output = worker_result.output or {}
    write_ai_package_process_report(settings.workspace_dir, output)
    log_event(
        app_log_path,
        level="INFO",
        event="ai_package_completed",
        message=(
            f"AI package completed; package={package_id}; "
            f"chunks={prepared.chunk_count}; fragments={prepared.fragment_count}"
        ),
        run_id=started.record.run_id,
        worker="build_ai_package",
    )
    return AiPackageCommandResult(
        run_id=started.record.run_id,
        package_id=package_id,
        status=AI_PACKAGE_STATUS_WAITING,
        package_hash=str(output["package_hash"]),
        package_path=str(output["package_path"]),
        manifest_path=str(output["manifest_path"]),
        source_revision_count=int(output["source_revision_count"]),
        chunk_count=int(output["chunk_count"]),
        fragment_count=int(output["fragment_count"]),
        worker_result=worker_result,
        selection_plan_id=prepared.selection_plan_id,
    )


def _allocate_package_id(settings: Any) -> str:
    if not settings.database_path.is_file():
        raise DatabaseNotReadyError(
            f"Database is not initialized: {settings.database_path}. "
            "Run 'dsl-manager db init <workspace>' before 'dsl-manager ai package'."
        )
    connection = open_database(settings.database_path, enable_wal=settings.wal_enabled)
    try:
        validate_database_migrations(connection)
        return next_ai_package_id(connection)
    finally:
        connection.close()


def _persist_ai_package_mutation(
    workspace_dir: Path,
    prepared: PreparedAiPackage,
    run_id: str,
):
    def apply(connection: sqlite3.Connection, output: dict[str, Any]) -> None:
        persist_ai_package_output(
            connection,
            workspace_dir=workspace_dir,
            output=output,
            expected_package_id=prepared.package_id,
            expected_run_id=run_id,
            expected_source_revision_count=prepared.source_revision_count,
            expected_chunk_count=prepared.chunk_count,
            expected_fragment_count=prepared.fragment_count,
            timestamp=timestamp_now(None),
            expected_selection_plan_id=prepared.selection_plan_id,
        )

    return apply


def _cleanup_failed_selection_package(
    workspace_dir: Path, prepared: PreparedAiPackage
) -> None:
    if prepared.selection_plan_id is None:
        return
    output_dir = (workspace_dir / prepared.output_dir).resolve()
    expected_parent = (workspace_dir / "ai" / "outbox").resolve()
    if output_dir.parent != expected_parent or output_dir.name != prepared.package_id:
        return
    if output_dir.is_dir():
        shutil.rmtree(output_dir)


def _print_selection_plan(result: SelectionPlanResult) -> None:
    print(f"Run: {result.run_id}")
    print(f"Selection plan: {result.selection_plan_id}")
    print(f"Route: {result.route}")
    print(f"Policy: {result.policy_name}/{result.policy_version}")
    print(f"Examined: {result.examined_count}")
    print(f"Included: {result.included_count}")
    print(f"Excluded: {result.excluded_count}")
    print(f"Selected chars: {result.selected_chars}")
    print(f"Reason summary: {json.dumps(result.reason_summary, sort_keys=True)}")
    print(f"Relevant state hash: {result.relevant_state_hash}")
    print(f"Plan hash: {result.plan_hash}")
    print(f"Report: {result.report_path}")


def _resolve_app_log_path(workspace_dir: Path) -> Path:
    config = load_config(workspace_dir)
    logging_config = config.get("logging", {})
    configured_path = logging_config.get("app_log_path", "logs/app.jsonl")
    return resolve_workspace_path(workspace_dir, configured_path)


def _format_bool(value: bool) -> str:
    return "true" if value else "false"
