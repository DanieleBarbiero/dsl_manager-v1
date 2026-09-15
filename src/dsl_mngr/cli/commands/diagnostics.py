from __future__ import annotations

import sys
from pathlib import Path

from dsl_mngr.core.canonical import canonical_json_artifact_v1
from dsl_mngr.core.database import DatabaseConfigurationError, WorkspaceNotInitializedError
from dsl_mngr.core.normalization_diagnostics import (
    NormalizationDiagnosticError,
    run_controlled_normalization_diagnostic,
)
from dsl_mngr.core.runs import DatabaseNotReadyError, RunLifecycleError
from dsl_mngr.core.worker_runner import WorkerRunnerError


def run_normalization_diagnostic_command(args: object) -> int:
    try:
        result = run_controlled_normalization_diagnostic(
            Path(getattr(args, "workspace")),
            source_revision_id=str(getattr(args, "revision_id")),
            scenario=str(getattr(args, "scenario")),
        )
    except (
        DatabaseConfigurationError,
        DatabaseNotReadyError,
        NormalizationDiagnosticError,
        RunLifecycleError,
        WorkerRunnerError,
        WorkspaceNotInitializedError,
    ) as exc:
        exit_code = int(getattr(exc, "exit_code", 2))
        payload = {
            "artifact_paths": [],
            "catalog_version": "result_catalog_v1",
            "condition": "normalization_diagnostic_failed",
            "counters": {},
            "error": str(exc),
            "exit_code": exit_code,
            "mutations": False,
            "outcome": "failed",
            "reason": getattr(exc, "reason", "normalization_diagnostic_failed"),
            "retryable": False,
            "run_id": None,
            "schema_version": "1",
            "severity": "error",
            "status": "failed",
            "subject_ids": [],
            "workspace": str(Path(getattr(args, "workspace")).resolve()),
        }
        print(canonical_json_artifact_v1(payload), end="")
        print(f"Error: {exc}", file=sys.stderr)
        return exit_code

    payload = {
        **result.payload,
        "catalog_version": "result_catalog_v1",
        "condition": "controlled_normalization_partial",
        "counters": {"artifacts": len(result.payload["artifact_paths"])},
        "mutations": False,
        "outcome": "partial",
        "retryable": False,
        "schema_version": "1",
        "severity": "warning",
        "subject_ids": [result.payload["source_revision_id"]],
        "worker_exit_code": result.worker.exit_code,
        "workspace": str(Path(getattr(args, "workspace")).resolve()),
    }
    print(canonical_json_artifact_v1(payload), end="")
    return 6
