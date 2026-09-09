from __future__ import annotations

import sys
from pathlib import Path

from dsl_mngr.core.batch import BatchError, batch_cli_lines, chunk_dir, process_dir
from dsl_mngr.core.batch_consolidation import (
    BatchConsolidationError,
    consolidate_batch,
)
from dsl_mngr.core.canonical import canonical_json_v1
from dsl_mngr.core.config import ProjectConfigError, WorkerProfileError
from dsl_mngr.core.database import DatabaseConfigurationError, WorkspaceNotInitializedError
from dsl_mngr.core.runs import DatabaseNotReadyError, RunLifecycleError
from dsl_mngr.core.source_registry import CorpusScanError
from dsl_mngr.core.worker_runner import WorkerRunnerError


def run_batch_process_dir_command(args: object) -> int:
    workspace = Path(getattr(args, "workspace"))
    corpus_path = getattr(args, "corpus_path", None)
    stop_on_error = bool(getattr(args, "stop_on_error", False))

    try:
        result = process_dir(
            workspace,
            corpus_path=corpus_path,
            stop_on_error=stop_on_error,
        )
    except (
        BatchError,
        CorpusScanError,
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


def run_batch_chunk_dir_command(args: object) -> int:
    workspace = Path(getattr(args, "workspace"))
    revisions = tuple(getattr(args, "revision", None) or ())
    profile = getattr(args, "profile", None) or "docling.chunking"
    stop_on_error = bool(getattr(args, "stop_on_error", False))

    try:
        result = chunk_dir(
            workspace,
            revision_ids=revisions,
            profile=profile,
            stop_on_error=stop_on_error,
        )
    except (
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


def run_batch_consolidate_command(args: object) -> int:
    workspace = Path(getattr(args, "workspace"))
    try:
        payload = consolidate_batch(
            workspace,
            corpus_path=getattr(args, "corpus_path", "corpus/active"),
            strict_review=bool(getattr(args, "strict_review", False)),
            reconcile=bool(getattr(args, "reconcile", False)),
            stop_on_error=bool(getattr(args, "stop_on_error", False)),
            resume_run_id=getattr(args, "resume_run_id", None),
        )
    except (
        BatchConsolidationError,
        BatchError,
        CorpusScanError,
        DatabaseConfigurationError,
        DatabaseNotReadyError,
        ProjectConfigError,
        RunLifecycleError,
        WorkerProfileError,
        WorkerRunnerError,
        WorkspaceNotInitializedError,
    ) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return int(getattr(exc, "exit_code", 2))

    print(canonical_json_v1(payload))
    return int(payload["exit_code"])
