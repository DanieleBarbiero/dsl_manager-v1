from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dsl_mngr.core.database import (
    DatabaseConfigurationError,
    DatabaseSettings,
    WorkspaceNotInitializedError,
    open_database,
    resolve_database_settings,
    resolve_workspace_path,
)
from dsl_mngr.core.logging_setup import log_event
from dsl_mngr.core.merge import MergeDatabaseNotReadyError, MergeError
from dsl_mngr.core.runs import (
    DatabaseNotReadyError,
    RunLifecycleError,
    canonical_json,
    complete_run,
    ensure_workspace_database_ready,
    fail_run,
    relative_workspace_path,
    start_run,
    timestamp_now,
    update_run_input,
    validate_database_migrations,
    write_process_report,
)
from dsl_mngr.core.source_registry import scan_corpus


class BatchError(RuntimeError):
    """Raised when a batch command cannot be planned or executed."""


@dataclass
class BatchItem:
    item_id: str
    kind: str
    status: str = "pending"
    source_id: str | None = None
    source_revision_id: str | None = None
    input_path: str | None = None
    batch_id: str | None = None
    reason: str | None = None
    run_id: str | None = None
    error: str | None = None
    exit_code: int | None = None
    outputs: dict[str, Any] = field(default_factory=dict)
    workspace_dir: Path | None = field(default=None, repr=False, compare=False)

    def to_report_item(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "error": self.error,
            "item_id": self.item_id,
            "kind": self.kind,
            "outputs": self.outputs,
            "run_id": self.run_id,
            "status": self.status,
        }
        for key, value in (
            ("batch_id", self.batch_id),
            ("exit_code", self.exit_code),
            ("input_path", self.input_path),
            ("reason", self.reason),
            ("source_id", self.source_id),
            ("source_revision_id", self.source_revision_id),
        ):
            if value is not None:
                payload[key] = value
        return payload

    def to_planned_item(self) -> dict[str, Any]:
        payload = self.to_report_item()
        payload.pop("error", None)
        payload.pop("outputs", None)
        payload.pop("run_id", None)
        payload.pop("exit_code", None)
        return payload


@dataclass(frozen=True)
class BatchResult:
    run_id: str
    run_type: str
    batch_command: str
    status: str
    stop_on_error: bool
    summary: dict[str, int]
    items: tuple[dict[str, Any], ...]
    report_path: str


def process_dir(
    workspace_dir: str | Path,
    *,
    corpus_path: str | Path | None = None,
    stop_on_error: bool = False,
) -> BatchResult:
    settings = _require_database_ready(workspace_dir)
    scan_result = scan_corpus(settings.workspace_dir, corpus_path=corpus_path)
    scan_path = relative_workspace_path(settings.workspace_dir, scan_result.corpus_dir)
    revisions = _load_active_revisions_under(settings, scan_path)
    items = _plan_process_dir_items(settings.workspace_dir, revisions)
    input_payload = {
        "batch_command": "process-dir",
        "options": {
            "path": scan_path,
            "scan": {
                "added": scan_result.added,
                "deleted": scan_result.deleted,
                "modified": scan_result.modified,
                "unchanged": scan_result.unchanged,
            },
        },
        "planned_items": [item.to_planned_item() for item in items],
        "stop_on_error": stop_on_error,
    }
    return _execute_batch(
        settings,
        batch_command="process-dir",
        stop_on_error=stop_on_error,
        input_payload=input_payload,
        items=items,
        executor=_execute_process_dir_item,
    )


def chunk_dir(
    workspace_dir: str | Path,
    *,
    revision_ids: tuple[str, ...] = (),
    profile: str = "docling.chunking",
    stop_on_error: bool = False,
) -> BatchResult:
    settings = _require_database_ready(workspace_dir)
    revisions = _load_chunkable_revisions(settings, revision_ids)
    items = _items_from_revisions(revisions, kind="chunk")
    input_payload = {
        "batch_command": "chunk-dir",
        "options": {
            "profile": profile,
            "revision_ids": list(_stable_unique(revision_ids)),
        },
        "planned_items": [item.to_planned_item() for item in items],
        "stop_on_error": stop_on_error,
    }
    return _execute_batch(
        settings,
        batch_command="chunk-dir",
        stop_on_error=stop_on_error,
        input_payload=input_payload,
        items=items,
        executor=lambda item, parent_run_id: _execute_chunk_item(
            item,
            parent_run_id=parent_run_id,
            profile=profile,
        ),
    )


def ai_package_batch(
    workspace_dir: str | Path,
    *,
    revision_ids: tuple[str, ...] = (),
    profile: str = "ai_package.default",
    stop_on_error: bool = False,
) -> BatchResult:
    settings = _require_database_ready(workspace_dir)
    revisions = _load_ai_package_revisions(settings, revision_ids)
    items: list[BatchItem] = []
    for index, revision in enumerate(revisions, start=1):
        status = "pending"
        reason = None
        if int(revision["active_evidence_count"]) == 0:
            status = "skipped"
            reason = "no_active_evidence"
        items.append(
            BatchItem(
                item_id=_item_id(index),
                kind="ai_package",
                status=status,
                source_id=revision["source_id"],
                source_revision_id=revision["source_revision_id"],
                input_path=revision["file_path"],
                reason=reason,
                outputs={
                    "active_chunks": int(revision["active_chunk_count"]),
                    "active_fragments": int(revision["active_fragment_count"]),
                }
                if status == "skipped"
                else {},
            )
        )
    _attach_workspace(items, settings.workspace_dir)

    input_payload = {
        "batch_command": "package-batch",
        "options": {
            "profile": profile,
            "revision_ids": list(_stable_unique(revision_ids)),
        },
        "planned_items": [item.to_planned_item() for item in items],
        "stop_on_error": stop_on_error,
    }
    return _execute_batch(
        settings,
        batch_command="package-batch",
        stop_on_error=stop_on_error,
        input_payload=input_payload,
        items=items,
        executor=lambda item, parent_run_id: _execute_ai_package_item(
            item,
            parent_run_id=parent_run_id,
            profile=profile,
        ),
    )


def candidates_validate_batch(
    workspace_dir: str | Path,
    *,
    input_dir: str | Path = "ai/inbox",
    pattern: str = "*.jsonl",
    stop_on_error: bool = False,
) -> BatchResult:
    settings = _require_database_ready(workspace_dir)
    files = _candidate_input_files(settings.workspace_dir, input_dir, pattern)
    items = [
        BatchItem(
            item_id=_item_id(index),
            kind="candidate_validation",
            input_path=relative_workspace_path(settings.workspace_dir, path),
        )
        for index, path in enumerate(files, start=1)
    ]
    _attach_workspace(items, settings.workspace_dir)
    input_payload = {
        "batch_command": "validate-batch",
        "options": {
            "input_dir": _relative_existing_dir(settings.workspace_dir, input_dir),
            "pattern": pattern,
        },
        "planned_items": [item.to_planned_item() for item in items],
        "stop_on_error": stop_on_error,
    }
    return _execute_batch(
        settings,
        batch_command="validate-batch",
        stop_on_error=stop_on_error,
        input_payload=input_payload,
        items=items,
        executor=_execute_candidate_validation_item,
    )


def facts_merge_batch(
    workspace_dir: str | Path,
    *,
    batch_ids: tuple[str, ...] = (),
    stop_on_error: bool = False,
) -> BatchResult:
    settings = _require_database_ready(workspace_dir)
    candidate_batches = _load_candidate_batches(settings, batch_ids)
    items = [
        BatchItem(
            item_id=_item_id(index),
            kind="merge",
            batch_id=row["batch_id"],
            input_path=row["input_path"],
            outputs={"candidate_record_count": int(row["accepted_count"])},
        )
        for index, row in enumerate(candidate_batches, start=1)
    ]
    _attach_workspace(items, settings.workspace_dir)
    input_payload = {
        "batch_command": "merge-batch",
        "options": {"batch_ids": list(_stable_unique(batch_ids))},
        "planned_items": [item.to_planned_item() for item in items],
        "stop_on_error": stop_on_error,
    }
    return _execute_batch(
        settings,
        batch_command="merge-batch",
        stop_on_error=stop_on_error,
        input_payload=input_payload,
        items=items,
        executor=_execute_merge_item,
    )


def batch_cli_lines(result: BatchResult) -> list[str]:
    lines = [
        f"Run: {result.run_id}",
        f"Command: {result.batch_command}",
        f"Items: {result.summary['total']}",
        f"Completed: {result.summary['completed']}",
        f"Failed: {result.summary['failed']}",
        f"Skipped: {result.summary['skipped']}",
        f"Report: {result.report_path}",
    ]
    failed_items = [item for item in result.items if item.get("status") == "failed"]
    if failed_items:
        lines.append("Failed items:")
        for item in failed_items:
            subject = (
                item.get("source_revision_id")
                or item.get("batch_id")
                or item.get("input_path")
                or "-"
            )
            lines.append(
                f"- {item['item_id']} {item['kind']} {subject}: {item.get('error') or 'failed'}"
            )
    return lines


def _execute_batch(
    settings: DatabaseSettings,
    *,
    batch_command: str,
    stop_on_error: bool,
    input_payload: dict[str, Any],
    items: list[BatchItem],
    executor: Any,
) -> BatchResult:
    started = start_run(
        settings.workspace_dir,
        run_type="batch",
        input_payload=input_payload,
        cli_options={"batch": {"command": batch_command, "stop_on_error": stop_on_error}},
    )
    batch_input = {
        "artifact_dir": started.artifacts.artifact_dir_relative,
        "batch_command": batch_command,
        "options": input_payload.get("options", {}),
        "planned_items": input_payload.get("planned_items", []),
        "run_id": started.record.run_id,
        "run_type": "batch",
        "stop_on_error": stop_on_error,
    }
    _replace_run_input(settings, started.record.run_id, batch_input)
    log_event(
        started.artifacts.log_path,
        level="INFO",
        event="batch_started",
        message=f"Batch {batch_command} started with {len(items)} item(s).",
        run_id=started.record.run_id,
    )

    normalization_failed: set[str] = set()
    failed_seen = False
    executed_items: list[BatchItem] = []
    remaining_due_to_stop = False

    for item in items:
        if remaining_due_to_stop:
            _mark_item_skipped(item, "stopped_after_error")
            _log_batch_item(started.artifacts.log_path, started.record.run_id, item)
            executed_items.append(item)
            continue

        if item.status == "skipped":
            _log_batch_item(started.artifacts.log_path, started.record.run_id, item)
            executed_items.append(item)
            continue

        if item.kind == "chunk" and item.source_revision_id in normalization_failed:
            _mark_item_skipped(item, "normalize_failed")
            _log_batch_item(started.artifacts.log_path, started.record.run_id, item)
            executed_items.append(item)
            continue

        try:
            executor(item, started.record.run_id)
        except Exception as exc:
            _mark_item_failed(item, _short_error(exc))

        if item.kind == "normalize" and item.status == "failed" and item.source_revision_id:
            normalization_failed.add(item.source_revision_id)

        if item.status == "failed":
            failed_seen = True
        _log_batch_item(started.artifacts.log_path, started.record.run_id, item)
        executed_items.append(item)

        if item.status == "failed" and stop_on_error:
            remaining_due_to_stop = True

    summary = _summary(executed_items)
    final_status = "failed" if summary["failed"] else "completed"
    report = {
        "batch_command": batch_command,
        "items": [item.to_report_item() for item in executed_items],
        "run_id": started.record.run_id,
        "run_type": "batch",
        "status": final_status,
        "stop_on_error": stop_on_error,
        "summary": summary,
    }
    report_path = _batch_report_path(started.artifacts)
    report_relative = relative_workspace_path(settings.workspace_dir, report_path)
    output_payload = {
        "batch_command": batch_command,
        "batch_report_path": report_relative,
        "status": final_status,
        "summary": summary,
    }

    try:
        report_path.write_text(canonical_json(report), encoding="utf-8", newline="\n")
        if failed_seen:
            fail_run(
                settings.workspace_dir,
                started.record.run_id,
                error=f"Batch {batch_command} failed: {summary['failed']} item(s) failed.",
                output_payload=output_payload,
            )
        else:
            complete_run(
                settings.workspace_dir,
                started.record.run_id,
                output_payload=output_payload,
            )
        _augment_batch_process_report(
            started.artifacts.process_report_path,
            batch_command=batch_command,
            report_relative=report_relative,
            report=report,
        )
    except Exception as exc:
        _fail_running_batch_after_report_error(
            settings.workspace_dir,
            started.record.run_id,
            str(exc),
        )
        raise BatchError(f"Failed to write batch report: {_short_error(exc)}") from exc

    log_event(
        started.artifacts.log_path,
        level="ERROR" if final_status == "failed" else "INFO",
        event="batch_failed" if final_status == "failed" else "batch_completed",
        message=(
            f"Batch {batch_command} {final_status}; "
            f"completed={summary['completed']}; failed={summary['failed']}; "
            f"skipped={summary['skipped']}."
        ),
        run_id=started.record.run_id,
    )
    return BatchResult(
        run_id=started.record.run_id,
        run_type="batch",
        batch_command=batch_command,
        status=final_status,
        stop_on_error=stop_on_error,
        summary=summary,
        items=tuple(report["items"]),
        report_path=report_relative,
    )


def _execute_process_dir_item(item: BatchItem, parent_run_id: str) -> None:
    if item.kind == "normalize":
        from dsl_mngr.cli.commands.corpus import normalize_source_revision

        result = normalize_source_revision(
            _workspace_from_item(item),
            source_revision_id=str(item.source_revision_id),
            profile="docling.no_images",
            parent_run_id=parent_run_id,
        )
        _apply_worker_result(
            item,
            run_id=result.run_id,
            worker_result=result.worker_result,
            outputs={
                "normalized_hash": result.normalized_hash,
                "normalized_markdown_path": result.normalized_markdown_path,
            },
        )
        return

    if item.kind == "chunk":
        _execute_chunk_item(item, parent_run_id=parent_run_id, profile="docling.chunking")
        return

    if item.kind == "parse_ddl":
        from dsl_mngr.cli.commands.corpus import parse_ddl_source_revision

        result = parse_ddl_source_revision(
            _workspace_from_item(item),
            source_revision_id=str(item.source_revision_id),
            profile="ddl.default",
            parent_run_id=parent_run_id,
        )
        _apply_worker_result(
            item,
            run_id=result.run_id,
            worker_result=result.worker_result,
            outputs={
                "columns": result.column_count,
                "foreign_keys": result.foreign_key_count,
                "fragments": result.fragment_count,
                "tables": result.table_count,
            },
        )
        return

    if item.kind == "parse_xml_form":
        from dsl_mngr.cli.commands.corpus import parse_xml_form_source_revision

        result = parse_xml_form_source_revision(
            _workspace_from_item(item),
            source_revision_id=str(item.source_revision_id),
            profile="xml_form.default",
            parent_run_id=parent_run_id,
        )
        _apply_worker_result(
            item,
            run_id=result.run_id,
            worker_result=result.worker_result,
            outputs={
                "fields": result.field_count,
                "forms": result.form_count,
                "fragments": result.fragment_count,
            },
        )
        return

    if item.kind == "parse_db_code":
        from dsl_mngr.cli.commands.corpus import parse_db_code_source_revision

        result = parse_db_code_source_revision(
            _workspace_from_item(item),
            source_revision_id=str(item.source_revision_id),
            profile="db_code.default",
            parent_run_id=parent_run_id,
        )
        _apply_worker_result(
            item,
            run_id=result.run_id,
            worker_result=result.worker_result,
            outputs={
                "fragments": result.fragment_count,
                "procedures": result.procedure_count,
                "statements": result.statement_count,
                "triggers": result.trigger_count,
            },
        )
        return

    if item.kind == "parse_log":
        from dsl_mngr.cli.commands.corpus import parse_log_source_revision

        result = parse_log_source_revision(
            _workspace_from_item(item),
            source_revision_id=str(item.source_revision_id),
            profile="log.default",
            parent_run_id=parent_run_id,
        )
        _apply_worker_result(
            item,
            run_id=result.run_id,
            worker_result=result.worker_result,
            outputs={
                "events": result.event_count,
                "fragments": result.fragment_count,
                "warnings": result.warning_count,
            },
        )
        return

    _mark_item_failed(item, f"Unsupported batch item kind: {item.kind}.")


def _execute_chunk_item(item: BatchItem, *, parent_run_id: str, profile: str) -> None:
    from dsl_mngr.cli.commands.corpus import chunk_source_revision

    result = chunk_source_revision(
        _workspace_from_item(item),
        source_revision_id=str(item.source_revision_id),
        profile=profile,
        parent_run_id=parent_run_id,
    )
    _apply_worker_result(
        item,
        run_id=result.run_id,
        worker_result=result.worker_result,
        outputs={"chunks": result.chunk_count, "chunks_hash": result.chunks_hash},
    )


def _execute_ai_package_item(item: BatchItem, *, parent_run_id: str, profile: str) -> None:
    from dsl_mngr.cli.commands.ai import build_ai_package

    result = build_ai_package(
        _workspace_from_item(item),
        revision_ids=(str(item.source_revision_id),),
        profile=profile,
        parent_run_id=parent_run_id,
    )
    _apply_worker_result(
        item,
        run_id=result.run_id,
        worker_result=result.worker_result,
        outputs={
            "chunks": result.chunk_count,
            "fragments": result.fragment_count,
            "package_id": result.package_id,
            "package_path": result.package_path,
        },
    )


def _execute_candidate_validation_item(item: BatchItem, parent_run_id: str) -> None:
    from dsl_mngr.cli.commands.candidates import validate_candidate_file

    result = validate_candidate_file(
        _workspace_from_item(item),
        input_path=str(item.input_path),
        parent_run_id=parent_run_id,
    )
    item.run_id = result.run_id
    item.status = "completed"
    item.error = None
    item.outputs = {
        "accepted": result.accepted_count,
        "batch_id": result.batch_id,
        "rejected": result.rejected_count,
        "total": result.total_records,
    }


def _execute_merge_item(item: BatchItem, parent_run_id: str) -> None:
    from dsl_mngr.cli.commands.facts import merge_facts_candidate_batch

    result = merge_facts_candidate_batch(
        _workspace_from_item(item),
        batch_id=str(item.batch_id),
        parent_run_id=parent_run_id,
    )
    item.run_id = result.run_id
    item.status = "completed"
    item.error = None
    item.outputs = result.to_artifact_payload()


def _workspace_from_item(item: BatchItem) -> Path:
    if item.workspace_dir is None:
        raise BatchError("Internal batch item is missing workspace context.")
    return item.workspace_dir


def _attach_workspace(items: list[BatchItem], workspace_dir: Path) -> list[BatchItem]:
    for item in items:
        item.workspace_dir = workspace_dir
    return items


def _plan_process_dir_items(workspace_dir: Path, revisions: list[sqlite3.Row]) -> list[BatchItem]:
    items: list[BatchItem] = []
    for revision in sorted(revisions, key=lambda row: row["file_path"].lower()):
        actions = _actions_for_revision(workspace_dir, revision)
        if not actions:
            items.append(
                BatchItem(
                    item_id="",
                    kind="unsupported_source_type",
                    status="skipped",
                    source_id=revision["source_id"],
                    source_revision_id=revision["source_revision_id"],
                    input_path=revision["file_path"],
                    reason="unsupported_source_type",
                )
            )
            continue
        for action in actions:
            items.append(
                BatchItem(
                    item_id="",
                    kind=action,
                    source_id=revision["source_id"],
                    source_revision_id=revision["source_revision_id"],
                    input_path=revision["file_path"],
                )
            )
    for index, item in enumerate(items, start=1):
        item.item_id = _item_id(index)
    return _attach_workspace(items, workspace_dir)


def _items_from_revisions(revisions: list[sqlite3.Row], *, kind: str) -> list[BatchItem]:
    items = [
        BatchItem(
            item_id=_item_id(index),
            kind=kind,
            source_id=revision["source_id"],
            source_revision_id=revision["source_revision_id"],
            input_path=revision["file_path"],
        )
        for index, revision in enumerate(revisions, start=1)
    ]
    if revisions:
        workspace = Path(revisions[0]["workspace_dir"])
        _attach_workspace(items, workspace)
    return items


def _actions_for_revision(workspace_dir: Path, revision: sqlite3.Row) -> list[str]:
    source_type = str(revision["source_type"] or "unknown")
    file_path = str(revision["file_path"])
    suffix = Path(file_path).suffix.lower()

    if source_type == "legacy_document" or suffix in {
        ".docx",
        ".html",
        ".md",
        ".pdf",
        ".pptx",
        ".txt",
    }:
        return ["normalize", "chunk"]
    if source_type == "xml_form" or suffix == ".xml":
        return ["parse_xml_form"]
    if source_type == "log" or suffix == ".log":
        return ["parse_log"]

    text = _read_short_text(workspace_dir, file_path) if suffix == ".sql" else ""
    actions: list[str] = []
    if source_type == "ddl" or _looks_like_ddl(text):
        actions.append("parse_ddl")
    if source_type == "database_code" or _looks_like_database_code(text):
        actions.append("parse_db_code")
    return actions


def _looks_like_ddl(text: str) -> bool:
    return bool(
        re.search(
            r"\bCREATE\s+(TABLE|INDEX|VIEW)\b|\b(ALTER\s+TABLE|CONSTRAINT|FOREIGN\s+KEY|PRIMARY\s+KEY)\b",
            text,
            flags=re.IGNORECASE,
        )
    )


def _looks_like_database_code(text: str) -> bool:
    return bool(
        re.search(
            r"\bCREATE\s+(TRIGGER|PROCEDURE|FUNCTION)\b|\b(CALL|DELETE|EXEC|INSERT|MERGE|UPDATE)\b",
            text,
            flags=re.IGNORECASE,
        )
    )


def _read_short_text(workspace_dir: Path, relative_path: str, *, limit: int = 512_000) -> str:
    try:
        path = resolve_workspace_path(workspace_dir, relative_path)
        return path.read_text(encoding="utf-8", errors="ignore")[:limit]
    except OSError:
        return ""


def _load_active_revisions_under(settings: DatabaseSettings, root_relative_path: str) -> list[sqlite3.Row]:
    connection = open_database(settings.database_path, enable_wal=settings.wal_enabled)
    try:
        validate_database_migrations(connection)
        rows = connection.execute(
            """
            SELECT
                sr.source_revision_id,
                sr.source_id,
                sr.file_path,
                sr.content_hash,
                sr.normalized_hash,
                s.source_type,
                s.source_subtype,
                s.authority_level,
                ? AS workspace_dir
            FROM source_revisions AS sr
            JOIN sources AS s
                ON s.source_id = sr.source_id
            WHERE sr.status = 'active'
              AND s.status = 'active'
              AND (
                sr.file_path = ?
                OR sr.file_path LIKE ?
              )
            ORDER BY sr.file_path, sr.source_revision_id
            """,
            (
                str(settings.workspace_dir),
                root_relative_path,
                f"{root_relative_path.rstrip('/')}/%",
            ),
        ).fetchall()
    finally:
        connection.close()
    return rows


def _load_chunkable_revisions(
    settings: DatabaseSettings,
    revision_ids: tuple[str, ...],
) -> list[sqlite3.Row]:
    requested = _stable_unique(revision_ids)
    connection = open_database(settings.database_path, enable_wal=settings.wal_enabled)
    try:
        validate_database_migrations(connection)
        if requested:
            placeholders = ",".join("?" for _ in requested)
            rows = connection.execute(
                f"""
                SELECT
                    sr.source_revision_id,
                    sr.source_id,
                    sr.file_path,
                    ? AS workspace_dir
                FROM source_revisions AS sr
                JOIN sources AS s
                    ON s.source_id = sr.source_id
                WHERE sr.source_revision_id IN ({placeholders})
                  AND sr.status = 'active'
                  AND s.status = 'active'
                ORDER BY sr.source_revision_id
                """,
                (str(settings.workspace_dir), *requested),
            ).fetchall()
            found = {row["source_revision_id"] for row in rows}
            missing = [revision_id for revision_id in requested if revision_id not in found]
            if missing:
                raise BatchError("Source revision is not active or was not found: " + ", ".join(missing) + ".")
            return rows

        return connection.execute(
            """
            SELECT
                sr.source_revision_id,
                sr.source_id,
                sr.file_path,
                ? AS workspace_dir
            FROM source_revisions AS sr
            JOIN sources AS s
                ON s.source_id = sr.source_id
            WHERE sr.status = 'active'
              AND s.status = 'active'
              AND sr.normalized_hash IS NOT NULL
              AND sr.normalized_hash != ''
            ORDER BY sr.file_path, sr.source_revision_id
            """,
            (str(settings.workspace_dir),),
        ).fetchall()
    finally:
        connection.close()


def _load_ai_package_revisions(
    settings: DatabaseSettings,
    revision_ids: tuple[str, ...],
) -> list[sqlite3.Row]:
    requested = _stable_unique(revision_ids)
    connection = open_database(settings.database_path, enable_wal=settings.wal_enabled)
    try:
        validate_database_migrations(connection)
        where = "sr.status = 'active' AND s.status = 'active'"
        params: list[Any] = [str(settings.workspace_dir)]
        if requested:
            placeholders = ",".join("?" for _ in requested)
            where += f" AND sr.source_revision_id IN ({placeholders})"
            params.extend(requested)
        else:
            where += """
                AND (
                    EXISTS (
                        SELECT 1 FROM chunks AS c
                        WHERE c.source_revision_id = sr.source_revision_id
                          AND c.status = 'active'
                    )
                    OR EXISTS (
                        SELECT 1 FROM source_fragments AS f
                        WHERE f.source_revision_id = sr.source_revision_id
                          AND f.status = 'active'
                    )
                )
            """
        rows = connection.execute(
            f"""
            SELECT
                sr.source_revision_id,
                sr.source_id,
                sr.file_path,
                ? AS workspace_dir,
                (
                    SELECT COUNT(*) FROM chunks AS c
                    WHERE c.source_revision_id = sr.source_revision_id
                      AND c.status = 'active'
                ) AS active_chunk_count,
                (
                    SELECT COUNT(*) FROM source_fragments AS f
                    WHERE f.source_revision_id = sr.source_revision_id
                      AND f.status = 'active'
                ) AS active_fragment_count,
                (
                    SELECT COUNT(*) FROM chunks AS c
                    WHERE c.source_revision_id = sr.source_revision_id
                      AND c.status = 'active'
                ) + (
                    SELECT COUNT(*) FROM source_fragments AS f
                    WHERE f.source_revision_id = sr.source_revision_id
                      AND f.status = 'active'
                ) AS active_evidence_count
            FROM source_revisions AS sr
            JOIN sources AS s
                ON s.source_id = sr.source_id
            WHERE {where}
            ORDER BY sr.source_revision_id
            """,
            params,
        ).fetchall()
        if requested:
            found = {row["source_revision_id"] for row in rows}
            missing = [revision_id for revision_id in requested if revision_id not in found]
            if missing:
                raise BatchError("Source revision is not active or was not found: " + ", ".join(missing) + ".")
    finally:
        connection.close()
    return rows


def _load_candidate_batches(
    settings: DatabaseSettings,
    batch_ids: tuple[str, ...],
) -> list[sqlite3.Row]:
    requested = _stable_unique(batch_ids)
    connection = open_database(settings.database_path, enable_wal=settings.wal_enabled)
    try:
        validate_database_migrations(connection)
        if requested:
            placeholders = ",".join("?" for _ in requested)
            rows = connection.execute(
                f"""
                SELECT batch_id, input_path, accepted_count
                FROM candidate_batches
                WHERE batch_id IN ({placeholders})
                ORDER BY batch_id
                """,
                requested,
            ).fetchall()
            found = {row["batch_id"] for row in rows}
            missing = [batch_id for batch_id in requested if batch_id not in found]
            if missing:
                raise BatchError("Candidate batch was not found: " + ", ".join(missing) + ".")
            return rows

        rows = connection.execute(
            """
            SELECT batch_id, input_path, accepted_count
            FROM candidate_batches
            WHERE status = 'completed'
            ORDER BY batch_id
            """
        ).fetchall()
    finally:
        connection.close()
    return rows


def _candidate_input_files(workspace_dir: Path, input_dir: str | Path, pattern: str) -> list[Path]:
    if Path(pattern).is_absolute() or ".." in Path(pattern).parts:
        raise BatchError(f"Candidate pattern must be relative: {pattern}.")
    directory = resolve_workspace_path(workspace_dir, input_dir)
    if not directory.is_dir():
        raise BatchError(f"Candidate input directory is not a directory: {_relative_path_for_error(workspace_dir, directory)}.")
    return sorted(
        (path for path in directory.glob(pattern) if path.is_file()),
        key=lambda path: relative_workspace_path(workspace_dir, path).lower(),
    )


def _relative_existing_dir(workspace_dir: Path, input_dir: str | Path) -> str:
    directory = resolve_workspace_path(workspace_dir, input_dir)
    return relative_workspace_path(workspace_dir, directory)


def _require_database_ready(workspace_dir: str | Path) -> DatabaseSettings:
    settings = resolve_database_settings(workspace_dir)
    ensure_workspace_database_ready(settings)
    connection = open_database(settings.database_path, enable_wal=settings.wal_enabled)
    try:
        validate_database_migrations(connection)
    finally:
        connection.close()
    return settings


def _replace_run_input(settings: DatabaseSettings, run_id: str, payload: dict[str, Any]) -> None:
    connection = open_database(settings.database_path, enable_wal=settings.wal_enabled)
    try:
        validate_database_migrations(connection)
        connection.execute("BEGIN")
        try:
            update_run_input(
                connection,
                workspace_dir=settings.workspace_dir,
                run_id=run_id,
                input_payload=payload,
                updated_at=timestamp_now(None),
            )
        except Exception:
            connection.rollback()
            raise
        else:
            connection.commit()
    finally:
        connection.close()


def _apply_worker_result(
    item: BatchItem,
    *,
    run_id: str,
    worker_result: Any,
    outputs: dict[str, Any],
) -> None:
    item.run_id = run_id
    item.exit_code = worker_result.exit_code
    if worker_result.status != "completed":
        _mark_item_failed(item, _worker_error(worker_result), run_id=run_id, exit_code=worker_result.exit_code)
        return
    item.status = "completed"
    item.error = None
    item.outputs = outputs


def _worker_error(worker_result: Any) -> str:
    error = worker_result.error or f"Worker {worker_result.worker_name} failed."
    try:
        report = json.loads(Path(worker_result.report_path).read_text(encoding="utf-8"))
        workers = report.get("workers")
        if isinstance(workers, list) and workers:
            stderr = str(workers[0].get("stderr") or "").strip()
            worker_error = str(workers[0].get("error") or "").strip()
            if stderr:
                return _short_error(f"{worker_error}: {stderr}" if worker_error else stderr)
            if worker_error:
                return _short_error(worker_error)
    except (OSError, json.JSONDecodeError, TypeError):
        pass
    return _short_error(error)


def _mark_item_failed(
    item: BatchItem,
    error: str,
    *,
    run_id: str | None = None,
    exit_code: int | None = None,
) -> None:
    item.status = "failed"
    item.error = _short_error(error)
    if run_id is not None:
        item.run_id = run_id
    if exit_code is not None:
        item.exit_code = exit_code


def _mark_item_skipped(item: BatchItem, reason: str) -> None:
    item.status = "skipped"
    item.reason = reason
    item.error = None
    item.run_id = None


def _log_batch_item(log_path: Path, run_id: str, item: BatchItem) -> None:
    if item.status == "completed":
        event = "batch_item_completed"
        level = "INFO"
        message = f"Batch item {item.item_id} completed: {item.kind}."
    elif item.status == "failed":
        event = "batch_item_failed"
        level = "ERROR"
        message = f"Batch item {item.item_id} failed: {item.kind}: {item.error}"
    else:
        event = "batch_item_skipped"
        level = "INFO"
        message = f"Batch item {item.item_id} skipped: {item.kind}: {item.reason}"
    log_event(log_path, level=level, event=event, message=message, run_id=run_id)


def _summary(items: list[BatchItem]) -> dict[str, int]:
    return {
        "completed": sum(1 for item in items if item.status == "completed"),
        "failed": sum(1 for item in items if item.status == "failed"),
        "skipped": sum(1 for item in items if item.status == "skipped"),
        "total": len(items),
    }


def _batch_report_path(artifacts: Any) -> Path:
    return artifacts.artifact_dir / "batch_report.json"


def _augment_batch_process_report(
    process_report_path: Path,
    *,
    batch_command: str,
    report_relative: str,
    report: dict[str, Any],
) -> None:
    process_report = json.loads(process_report_path.read_text(encoding="utf-8"))
    process_report.update(
        {
            "batch_command": batch_command,
            "batch_report_path": report_relative,
            "items": report["items"],
            "stop_on_error": report["stop_on_error"],
            "summary": report["summary"],
        }
    )
    write_process_report(process_report_path, process_report)


def _fail_running_batch_after_report_error(workspace_dir: Path, run_id: str, error: str) -> None:
    try:
        fail_run(
            workspace_dir,
            run_id,
            error=f"Batch report failure: {error}",
            output_payload={"error": error},
        )
    except (
        DatabaseConfigurationError,
        DatabaseNotReadyError,
        RunLifecycleError,
        WorkspaceNotInitializedError,
    ):
        return


def _item_id(index: int) -> str:
    return f"BITEM_{index:06d}"


def _stable_unique(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted(dict.fromkeys(str(value) for value in values if str(value))))


def _short_error(error: object, *, limit: int = 500) -> str:
    text = str(error).strip().replace("\r\n", "\n").replace("\r", "\n")
    text = " ".join(line.strip() for line in text.splitlines() if line.strip())
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _relative_path_for_error(workspace_dir: Path, path: Path) -> str:
    try:
        return relative_workspace_path(workspace_dir, path)
    except ValueError:
        return str(path)


__all__ = [
    "BatchError",
    "BatchResult",
    "ai_package_batch",
    "batch_cli_lines",
    "candidates_validate_batch",
    "chunk_dir",
    "facts_merge_batch",
    "process_dir",
]
