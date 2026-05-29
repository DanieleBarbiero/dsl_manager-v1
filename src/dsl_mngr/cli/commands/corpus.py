from __future__ import annotations

import sys
from pathlib import Path

from dsl_mngr.core.config import load_config
from dsl_mngr.core.database import (
    DatabaseConfigurationError,
    WorkspaceNotInitializedError,
    resolve_workspace_path,
)
from dsl_mngr.core.logging_setup import log_event
from dsl_mngr.core.source_registry import CorpusScanError, scan_corpus


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


def _resolve_app_log_path(workspace_dir: Path) -> Path:
    config = load_config(workspace_dir)
    logging_config = config.get("logging", {})
    configured_path = logging_config.get("app_log_path", "logs/app.jsonl")
    return resolve_workspace_path(workspace_dir, configured_path)
