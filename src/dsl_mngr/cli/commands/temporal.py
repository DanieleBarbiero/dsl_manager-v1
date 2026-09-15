from __future__ import annotations

import sys
from pathlib import Path

from dsl_mngr.core.canonical import canonical_json_artifact_v1
from dsl_mngr.core.database import DatabaseConfigurationError, WorkspaceNotInitializedError
from dsl_mngr.core.runs import DatabaseNotReadyError, RunLifecycleError, complete_run, fail_run, start_run
from dsl_mngr.core.temporal import TemporalError
from dsl_mngr.core.temporal_consolidation import propagate_temporal_intervals


def run_temporal_propagate_command(args: object) -> int:
    workspace = Path(getattr(args, "workspace"))
    try:
        source_subjects = tuple(
            _parse_subject(value) for value in (getattr(args, "source_subjects", None) or [])
        )
    except TemporalError as exc:
        return _error_payload(exc, workspace=workspace)

    started = None
    try:
        started = start_run(
            workspace,
            run_type="temporal_propagation",
            input_payload={
                "policy": getattr(args, "policy"),
                "source_revision_id": getattr(args, "source_revision_id"),
                "source_subjects": [list(value) for value in source_subjects],
                "target_subject_id": getattr(args, "target_subject_id"),
                "target_subject_type": getattr(args, "target_subject_type"),
            },
        )
        result = propagate_temporal_intervals(
            workspace,
            run_id=started.record.run_id,
            source_revision_id=str(getattr(args, "source_revision_id")),
            target_subject_type=str(getattr(args, "target_subject_type")),
            target_subject_id=str(getattr(args, "target_subject_id")),
            source_subjects=source_subjects,
            policy=str(getattr(args, "policy")),
        )
        conflict = result.conflict_id is not None
        exit_code = 4 if conflict else 0
        payload = {
            "artifact_paths": [
                started.artifacts.output_path_relative,
                started.artifacts.process_report_path_relative,
                started.artifacts.log_path_relative,
            ],
            "candidate_batch_ids": list(result.candidate_batch_ids),
            "candidate_record_ids": list(result.candidate_record_ids),
            "catalog_version": "result_catalog_v1",
            "condition": "temporal_propagation_conflict" if conflict else "temporal_propagation",
            "conflict_id": result.conflict_id,
            "counters": {
                "candidate_batches": len(result.candidate_batch_ids),
                "candidate_records": len(result.candidate_record_ids),
                "conflicts": int(conflict),
            },
            "exit_code": exit_code,
            "mutations": True,
            "outcome": "conflict" if conflict else "success",
            "policy": result.policy,
            "reason": "governed_temporal_conflict" if conflict else "success",
            "retryable": False,
            "run_id": started.record.run_id,
            "schema_version": "1",
            "severity": "warning" if conflict else "info",
            "status": "completed",
            "subject_ids": [
                str(getattr(args, "source_revision_id")),
                str(getattr(args, "target_subject_id")),
                *result.candidate_record_ids,
                *result.candidate_batch_ids,
            ],
        }
        complete_run(workspace, started.record.run_id, output_payload=payload)
        print(
            canonical_json_artifact_v1(
                {**payload, "workspace": str(workspace.resolve())}
            ),
            end="",
        )
        return exit_code
    except (
        DatabaseConfigurationError,
        DatabaseNotReadyError,
        RunLifecycleError,
        TemporalError,
        WorkspaceNotInitializedError,
    ) as exc:
        if started is not None:
            try:
                fail_run(
                    workspace,
                    started.record.run_id,
                    error=str(exc),
                    output_payload={"reason": getattr(exc, "reason", "temporal_propagation_failed")},
                )
            except RunLifecycleError:
                pass
        return _error_payload(
            exc,
            run_id=started.record.run_id if started else None,
            workspace=workspace,
        )


def _parse_subject(value: str) -> tuple[str, str]:
    if value.count(":") != 1:
        raise TemporalError(
            f"Invalid source subject {value!r}; expected TYPE:ID.",
            reason="temporal_source_invalid",
        )
    subject_type, subject_id = value.split(":", 1)
    if not subject_type or not subject_id:
        raise TemporalError(
            f"Invalid source subject {value!r}; expected TYPE:ID.",
            reason="temporal_source_invalid",
        )
    return subject_type, subject_id


def _error_payload(
    exc: Exception,
    *,
    run_id: str | None = None,
    workspace: Path | None = None,
) -> int:
    exit_code = int(getattr(exc, "exit_code", 2))
    payload = {
        "artifact_paths": [],
        "catalog_version": "result_catalog_v1",
        "condition": "temporal_propagation_failed",
        "counters": {},
        "error": str(exc),
        "exit_code": exit_code,
        "mutations": False,
        "outcome": "failed",
        "reason": getattr(exc, "reason", "temporal_propagation_failed"),
        "retryable": False,
        "run_id": run_id,
        "schema_version": "1",
        "severity": "error",
        "status": "failed",
        "subject_ids": [],
    }
    if workspace is not None:
        payload["workspace"] = str(workspace.resolve())
    print(canonical_json_artifact_v1(payload), end="")
    print(f"Error: {exc}", file=sys.stderr)
    return exit_code
