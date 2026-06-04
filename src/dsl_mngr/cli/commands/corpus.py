from __future__ import annotations

import re
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dsl_mngr.core.chunk_registry import (
    ChunkRegistryError,
    load_chunk_id_seed,
    persist_worker_chunks,
)
from dsl_mngr.core.chunking import normalize_markdown_newlines, sha256_text
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
    timestamp_now,
    validate_database_migrations,
)
from dsl_mngr.core.source_registry import CorpusScanError, scan_corpus
from dsl_mngr.core.worker_runner import WorkerRunResult, WorkerRunnerError, run_worker
from dsl_mngr.workers import chunk_docling, normalize_docling


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


@dataclass(frozen=True)
class ChunkRevisionContext:
    source_id: str
    source_revision_id: str
    file_path: str
    content_hash: str
    normalized_hash: str


@dataclass(frozen=True)
class NormalizedInputPaths:
    normalized_markdown_path: Path
    normalized_json_path: Path
    source_hash_path: Path
    normalized_markdown_relative: str
    normalized_json_relative: str
    source_hash_relative: str


@dataclass(frozen=True)
class ChunkResult:
    run_id: str
    source_id: str
    source_revision_id: str
    chunk_count: int
    chunks_hash: str
    chunks_jsonl_path: str
    chunk_report_path: str
    worker_result: WorkerRunResult


class CorpusNormalizeError(RuntimeError):
    """Raised when a source revision cannot be normalized."""


class CorpusChunkError(RuntimeError):
    """Raised when a source revision cannot be chunked."""


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


def run_corpus_chunk_command(args: object) -> int:
    workspace = Path(getattr(args, "workspace"))
    revision_id = getattr(args, "revision")
    profile = getattr(args, "profile", None) or "docling.chunking"

    try:
        result = chunk_source_revision(
            workspace,
            source_revision_id=revision_id,
            profile=profile,
        )
    except (
        ChunkRegistryError,
        CorpusChunkError,
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
            "Error: Chunking failed for "
            f"{revision_id}; run={result.run_id}; exit_code={result.worker_result.exit_code}.",
            file=sys.stderr,
        )
        return 2

    print(f"Run: {result.run_id}")
    print(f"Revision: {result.source_revision_id}")
    print(f"Source: {result.source_id}")
    print(f"Chunks: {result.chunk_count}")
    print(f"Chunks hash: {result.chunks_hash}")
    print(f"Chunks JSONL: {result.chunks_jsonl_path}")
    print(f"Report: {result.chunk_report_path}")
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


def chunk_source_revision(
    workspace_dir: str | Path,
    *,
    source_revision_id: str,
    profile: str,
) -> ChunkResult:
    settings = resolve_database_settings(workspace_dir)
    revision = _load_chunk_revision_context(settings, source_revision_id)
    normalized_paths = _resolve_normalized_input_paths(settings.workspace_dir, revision)
    _validate_normalized_inputs(revision, normalized_paths)

    profile_config = load_worker_profile(
        settings.workspace_dir,
        profile,
        required_sections=("worker", "chunking"),
    )
    worker_config = dict(profile_config["worker"])
    chunking_options = dict(profile_config["chunking"])
    worker_version = str(worker_config.get("version", "1.0"))

    seed = _load_chunk_id_seed(settings, revision.source_revision_id)
    output_dir = f"chunks/{revision.source_id}/{revision.source_revision_id}"
    worker_input = {
        "chunk_id_by_sequence": {str(key): value for key, value in seed.chunk_id_by_sequence.items()},
        "chunking_options": chunking_options,
        "next_chunk_number": seed.next_chunk_number,
        "normalized_hash": revision.normalized_hash,
        "normalized_json_path": normalized_paths.normalized_json_relative,
        "normalized_markdown_path": normalized_paths.normalized_markdown_relative,
        "output_dir": output_dir,
        "profile": profile,
        "source_hash": revision.content_hash,
        "source_hash_path": normalized_paths.source_hash_relative,
        "source_id": revision.source_id,
        "source_revision_id": revision.source_revision_id,
        "worker_config": worker_config,
    }
    started = start_run(
        settings.workspace_dir,
        run_type="chunk",
        input_payload=worker_input,
        cli_options={
            "chunking": chunking_options,
            "profile": {"name": profile},
            "worker": worker_config,
        },
    )

    try:
        worker_result = run_worker(
            settings.workspace_dir,
            run_id=started.record.run_id,
            worker_name="chunk_docling",
            worker_path=Path(chunk_docling.__file__).resolve(),
            worker_version=worker_version,
            input_payload=worker_input,
            apply_mutations=_persist_chunks_mutation(
                settings.workspace_dir,
                revision,
                normalized_paths,
            ),
        )
    except Exception as exc:
        fail_run(
            settings.workspace_dir,
            started.record.run_id,
            error=f"Chunk orchestration failed: {exc}",
        )
        raise

    app_log_path = _resolve_app_log_path(settings.workspace_dir)
    if worker_result.status != "completed":
        log_event(
            app_log_path,
            level="ERROR",
            event="corpus_chunking_failed",
            message=(
                f"Chunking failed for revision {source_revision_id}; "
                f"run={started.record.run_id}; exit_code={worker_result.exit_code}"
            ),
            run_id=started.record.run_id,
            worker="chunk_docling",
        )
        return ChunkResult(
            run_id=started.record.run_id,
            source_id=revision.source_id,
            source_revision_id=revision.source_revision_id,
            chunk_count=0,
            chunks_hash="",
            chunks_jsonl_path="",
            chunk_report_path="",
            worker_result=worker_result,
        )

    output = worker_result.output or {}
    chunks_hash = _required_chunk_output_hash(output, "chunks_hash")
    chunks_jsonl_path = _required_chunk_output_path(output, "chunks_jsonl_path")
    chunk_report_path = _required_chunk_output_path(output, "chunk_report_path")
    chunk_count = _required_output_int(output, "chunk_count")
    log_event(
        app_log_path,
        level="INFO",
        event="corpus_chunking_completed",
        message=(
            f"Chunking completed for revision {source_revision_id}; "
            f"source={revision.source_id}; chunks={chunk_count}; chunks_hash={chunks_hash}"
        ),
        run_id=started.record.run_id,
        worker="chunk_docling",
    )
    return ChunkResult(
        run_id=started.record.run_id,
        source_id=revision.source_id,
        source_revision_id=revision.source_revision_id,
        chunk_count=chunk_count,
        chunks_hash=chunks_hash,
        chunks_jsonl_path=chunks_jsonl_path,
        chunk_report_path=chunk_report_path,
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


def _load_chunk_revision_context(
    settings: DatabaseSettings,
    source_revision_id: str,
) -> ChunkRevisionContext:
    if not settings.database_path.is_file():
        raise DatabaseNotReadyError(
            f"Database is not initialized: {settings.database_path}. "
            "Run 'dsl-manager db init <workspace>' before 'dsl-manager corpus chunk'."
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
                sr.normalized_hash,
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
        raise CorpusChunkError(f"Source revision not found: {source_revision_id}.")
    if row["existing_source_id"] is None:
        raise CorpusChunkError(
            f"Source revision {source_revision_id} does not belong to an existing source."
        )
    normalized_hash = row["normalized_hash"]
    if not isinstance(normalized_hash, str) or not normalized_hash:
        raise CorpusChunkError(
            f"Source revision {source_revision_id} is not normalized. "
            "Run 'dsl-manager corpus normalize <workspace> --revision "
            f"{source_revision_id}' before 'dsl-manager corpus chunk'."
        )
    if not re.fullmatch(r"[0-9a-f]{64}", normalized_hash):
        raise CorpusChunkError(f"Source revision {source_revision_id} has an invalid normalized_hash.")
    return ChunkRevisionContext(
        source_id=row["source_id"],
        source_revision_id=row["source_revision_id"],
        file_path=row["file_path"],
        content_hash=row["content_hash"],
        normalized_hash=normalized_hash,
    )


def _resolve_normalized_input_paths(
    workspace_dir: Path,
    revision: ChunkRevisionContext,
) -> NormalizedInputPaths:
    base = f"normalized/{revision.source_id}/{revision.source_revision_id}"
    markdown_relative = f"{base}/normalized.md"
    json_relative = f"{base}/normalized.json"
    source_hash_relative = f"{base}/source_hash.txt"
    return NormalizedInputPaths(
        normalized_markdown_path=_resolve_required_workspace_file(
            workspace_dir,
            markdown_relative,
            "normalized.md",
        ),
        normalized_json_path=_resolve_required_workspace_file(
            workspace_dir,
            json_relative,
            "normalized.json",
        ),
        source_hash_path=_resolve_required_workspace_file(
            workspace_dir,
            source_hash_relative,
            "source_hash.txt",
        ),
        normalized_markdown_relative=markdown_relative,
        normalized_json_relative=json_relative,
        source_hash_relative=source_hash_relative,
    )


def _resolve_required_workspace_file(workspace_dir: Path, relative_path: str, label: str) -> Path:
    raw_path = Path(relative_path)
    if raw_path.is_absolute() or ".." in raw_path.parts:
        raise CorpusChunkError(f"{label} path must be relative to the workspace: {relative_path}.")
    try:
        resolved = resolve_workspace_path(workspace_dir, relative_path)
    except DatabaseConfigurationError as exc:
        raise CorpusChunkError(f"{label} path escapes the workspace: {relative_path}.") from exc
    if not resolved.is_file():
        raise CorpusChunkError(f"{label} is missing: {relative_path}.")
    return resolved


def _validate_normalized_inputs(
    revision: ChunkRevisionContext,
    paths: NormalizedInputPaths,
) -> None:
    source_hash = paths.source_hash_path.read_text(encoding="utf-8").strip()
    if source_hash != revision.content_hash:
        raise CorpusChunkError(
            "source_hash.txt does not match source_revisions.content_hash for "
            f"{revision.source_revision_id}."
        )

    markdown = normalize_markdown_newlines(
        paths.normalized_markdown_path.read_text(encoding="utf-8")
    )
    markdown_hash = sha256_text(markdown)
    if markdown_hash != revision.normalized_hash:
        raise CorpusChunkError(
            "normalized.md hash does not match source_revisions.normalized_hash for "
            f"{revision.source_revision_id}."
        )


def _load_chunk_id_seed(settings: DatabaseSettings, source_revision_id: str):
    connection = open_database(settings.database_path, enable_wal=settings.wal_enabled)
    try:
        validate_database_migrations(connection)
        return load_chunk_id_seed(connection, source_revision_id)
    finally:
        connection.close()


def _persist_chunks_mutation(
    workspace_dir: Path,
    revision: ChunkRevisionContext,
    paths: NormalizedInputPaths,
):
    def apply(connection: sqlite3.Connection, output: dict[str, Any]) -> None:
        persist_worker_chunks(
            connection,
            workspace_dir=workspace_dir,
            output=output,
            expected_source_id=revision.source_id,
            expected_source_revision_id=revision.source_revision_id,
            expected_normalized_hash=revision.normalized_hash,
            expected_normalized_markdown_path=paths.normalized_markdown_relative,
            expected_normalized_json_path=paths.normalized_json_relative,
            timestamp=timestamp_now(None),
        )

    return apply


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


def _required_chunk_output_hash(output: dict[str, Any], key: str) -> str:
    value = output.get(key)
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise CorpusChunkError(f"Worker output field is invalid: {key}.")
    return value


def _required_chunk_output_path(output: dict[str, Any], key: str) -> str:
    value = output.get(key)
    if not isinstance(value, str) or not value:
        raise CorpusChunkError(f"Worker output field is missing: {key}.")
    if "\\" in value or Path(value).is_absolute() or ".." in Path(value).parts:
        raise CorpusChunkError(f"Worker output path is not workspace-relative: {key}.")
    return value


def _required_output_int(output: dict[str, Any], key: str) -> int:
    value = output.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise CorpusChunkError(f"Worker output field is invalid: {key}.")
    return value
