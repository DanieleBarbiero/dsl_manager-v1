from __future__ import annotations

import re
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dsl_mngr.core.config import WorkerProfileError, load_config, load_worker_profile
from dsl_mngr.core.database import (
    DatabaseConfigurationError,
    DatabaseSettings,
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
    relative_workspace_path,
    start_run,
    validate_database_migrations,
)
from dsl_mngr.core.source_registry import CorpusScanError, scan_corpus
from dsl_mngr.core.worker_runner import WorkerRunResult, WorkerRunnerError, run_worker
from dsl_mngr.workers import normalize_docling


def run_corpus_scan_command(args: object) -> int:
    workspace = Path(getattr(args, "workspace"))
    corpus_path = getattr(args, "corpus_path", None)

    try:
        result = scan_corpus(workspace, corpus_path=corpus_path)
    except (CorpusScanError, DatabaseConfigurationError, WorkspaceNotInitializedError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    log_event(
        _resolve_app_log_path(result.workspace_dir),
        level="INFO",
        event="corpus_scan_completed",
        message=(
            f"Corpus scan completed for {result.corpus_dir}; "
            f"added={result.added}; modified={result.modified}; "
            f"deleted={result.deleted}; unchanged={result.unchanged}"
        ),
    )

    print(f"Added: {result.added}")
    print(f"Modified: {result.modified}")
    print(f"Deleted: {result.deleted}")
    print(f"Unchanged: {result.unchanged}")
    return 0


@dataclass(frozen=True)
class RevisionContext:
    source_id: str
    source_revision_id: str
    file_path: str
    content_hash: str


@dataclass(frozen=True)
class NormalizeResult:
    run_id: str
    source_id: str
    source_revision_id: str
    normalized_hash: str
    normalized_markdown_path: str
    normalized_json_path: str
    docling_report_path: str
    worker_result: WorkerRunResult


class CorpusNormalizeError(RuntimeError):
    """Raised when a source revision cannot be normalized."""


def run_corpus_normalize_command(args: object) -> int:
    workspace = Path(getattr(args, "workspace"))
    revision_id = getattr(args, "revision")
    profile = getattr(args, "profile", None) or "docling.no_images"

    try:
        result = normalize_source_revision(
            workspace,
            source_revision_id=revision_id,
            profile=profile,
        )
    except (
        CorpusNormalizeError,
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
            "Error: Normalization failed for "
            f"{revision_id}; run={result.run_id}; exit_code={result.worker_result.exit_code}.",
            file=sys.stderr,
        )
        return 2

    print(f"Run: {result.run_id}")
    print(f"Revision: {result.source_revision_id}")
    print(f"Source: {result.source_id}")
    print(f"Normalized hash: {result.normalized_hash}")
    print(f"Markdown: {result.normalized_markdown_path}")
    print(f"JSON: {result.normalized_json_path}")
    print(f"Report: {result.docling_report_path}")
    return 0


def normalize_source_revision(
    workspace_dir: str | Path,
    *,
    source_revision_id: str,
    profile: str,
) -> NormalizeResult:
    settings = resolve_database_settings(workspace_dir)
    revision = _load_revision_context(settings, source_revision_id)
    input_path = _resolve_revision_file(settings.workspace_dir, revision.file_path)
    profile_config = load_worker_profile(settings.workspace_dir, profile)
    worker_config = dict(profile_config["worker"])
    docling_options = dict(profile_config["docling"])
    worker_version = str(worker_config.get("version", "1.0"))

    output_dir = f"normalized/{revision.source_id}/{revision.source_revision_id}"
    worker_input = {
        "docling_options": docling_options,
        "input_path": relative_workspace_path(settings.workspace_dir, input_path),
        "output_dir": output_dir,
        "profile": profile,
        "source_id": revision.source_id,
        "source_revision_id": revision.source_revision_id,
        "worker_config": worker_config,
    }
    started = start_run(
        settings.workspace_dir,
        run_type="normalize",
        input_payload=worker_input,
        cli_options={
            "docling": docling_options,
            "profile": {"name": profile},
            "worker": worker_config,
        },
    )

    try:
        worker_result = run_worker(
            settings.workspace_dir,
            run_id=started.record.run_id,
            worker_name="normalize_docling",
            worker_path=Path(normalize_docling.__file__).resolve(),
            worker_version=worker_version,
            input_payload=worker_input,
            apply_mutations=_update_normalized_hash_mutation(revision),
        )
    except Exception as exc:
        fail_run(
            settings.workspace_dir,
            started.record.run_id,
            error=f"Normalization orchestration failed: {exc}",
        )
        raise

    app_log_path = _resolve_app_log_path(settings.workspace_dir)
    if worker_result.status != "completed":
        log_event(
            app_log_path,
            level="ERROR",
            event="corpus_normalization_failed",
            message=(
                f"Normalization failed for revision {source_revision_id}; "
                f"run={started.record.run_id}; exit_code={worker_result.exit_code}"
            ),
            run_id=started.record.run_id,
            worker="normalize_docling",
        )
        return NormalizeResult(
            run_id=started.record.run_id,
            source_id=revision.source_id,
            source_revision_id=revision.source_revision_id,
            normalized_hash="",
            normalized_markdown_path="",
            normalized_json_path="",
            docling_report_path="",
            worker_result=worker_result,
        )

    output = worker_result.output or {}
    normalized_hash = _required_output_hash(output, "normalized_hash")
    normalized_markdown_path = _required_output_path(output, "normalized_markdown_path")
    normalized_json_path = _required_output_path(output, "normalized_json_path")
    docling_report_path = _required_output_path(output, "docling_report_path")
    log_event(
        app_log_path,
        level="INFO",
        event="corpus_normalization_completed",
        message=(
            f"Normalization completed for revision {source_revision_id}; "
            f"source={revision.source_id}; normalized_hash={normalized_hash}"
        ),
        run_id=started.record.run_id,
        worker="normalize_docling",
    )
    return NormalizeResult(
        run_id=started.record.run_id,
        source_id=revision.source_id,
        source_revision_id=revision.source_revision_id,
        normalized_hash=normalized_hash,
        normalized_markdown_path=normalized_markdown_path,
        normalized_json_path=normalized_json_path,
        docling_report_path=docling_report_path,
        worker_result=worker_result,
    )


def _resolve_app_log_path(workspace_dir: Path) -> Path:
    config = load_config(workspace_dir)
    logging_config = config.get("logging", {})
    configured_path = logging_config.get("app_log_path", "logs/app.jsonl")
    return resolve_workspace_path(workspace_dir, configured_path)


def _load_revision_context(
    settings: DatabaseSettings,
    source_revision_id: str,
) -> RevisionContext:
    if not settings.database_path.is_file():
        raise DatabaseNotReadyError(
            f"Database is not initialized: {settings.database_path}. "
            "Run 'dsl-manager db init <workspace>' before 'dsl-manager corpus normalize'."
        )

    connection = open_database(settings.database_path, enable_wal=settings.wal_enabled)
    try:
        validate_database_migrations(connection)
        row = connection.execute(
            """
            SELECT
                sr.source_revision_id,
                sr.source_id,
                sr.file_path,
                sr.content_hash,
                s.source_id AS existing_source_id
            FROM source_revisions AS sr
            JOIN sources AS s
                ON s.source_id = sr.source_id
            WHERE sr.source_revision_id = ?
            """,
            (source_revision_id,),
        ).fetchone()
    finally:
        connection.close()

    if row is None:
        raise CorpusNormalizeError(f"Source revision not found: {source_revision_id}.")
    if row["existing_source_id"] is None:
        raise CorpusNormalizeError(
            f"Source revision {source_revision_id} does not belong to an existing source."
        )
    return RevisionContext(
        source_id=row["source_id"],
        source_revision_id=row["source_revision_id"],
        file_path=row["file_path"],
        content_hash=row["content_hash"],
    )


def _resolve_revision_file(workspace_dir: Path, file_path: str) -> Path:
    raw_path = Path(file_path)
    if raw_path.is_absolute():
        raise CorpusNormalizeError(f"Source revision path must be relative: {file_path}.")
    if ".." in raw_path.parts:
        raise CorpusNormalizeError(f"Source revision path escapes the workspace: {file_path}.")

    try:
        resolved = resolve_workspace_path(workspace_dir, file_path)
    except DatabaseConfigurationError as exc:
        raise CorpusNormalizeError(
            f"Source revision path escapes the workspace: {file_path}."
        ) from exc
    if not resolved.is_file():
        raise CorpusNormalizeError(f"Source revision file does not exist: {file_path}.")
    return resolved


def _update_normalized_hash_mutation(revision: RevisionContext):
    def apply(connection: sqlite3.Connection, output: dict[str, Any]) -> None:
        if output.get("source_id") != revision.source_id:
            raise CorpusNormalizeError("Worker output source_id is incoherent.")
        if output.get("source_revision_id") != revision.source_revision_id:
            raise CorpusNormalizeError("Worker output source_revision_id is incoherent.")
        if output.get("source_hash") != revision.content_hash:
            raise CorpusNormalizeError("Worker output source_hash does not match the registry.")

        normalized_hash = _required_output_hash(output, "normalized_hash")
        for key in (
            "docling_report_path",
            "input_path",
            "normalized_json_path",
            "normalized_markdown_path",
            "source_hash_path",
        ):
            _required_output_path(output, key)

        connection.execute(
            """
            UPDATE source_revisions
            SET normalized_hash = ?
            WHERE source_revision_id = ?
            """,
            (normalized_hash, revision.source_revision_id),
        )

    return apply


def _required_output_hash(output: dict[str, Any], key: str) -> str:
    value = output.get(key)
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise CorpusNormalizeError(f"Worker output field is invalid: {key}.")
    return value


def _required_output_path(output: dict[str, Any], key: str) -> str:
    value = output.get(key)
    if not isinstance(value, str) or not value:
        raise CorpusNormalizeError(f"Worker output field is missing: {key}.")
    if "\\" in value or Path(value).is_absolute() or ".." in Path(value).parts:
        raise CorpusNormalizeError(f"Worker output path is not workspace-relative: {key}.")
    return value
