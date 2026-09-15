from __future__ import annotations

import hashlib
import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dsl_mngr.core.config import load_config
from dsl_mngr.core.database import open_database, resolve_database_settings, resolve_workspace_path
from dsl_mngr.core.ooxml_preflight import ExcelLimits, OoxmlPreflightError, preflight_ooxml
from dsl_mngr.core.runs import start_run, validate_database_migrations
from dsl_mngr.core.worker_runner import WorkerRunResult, run_worker
from dsl_mngr.workers import controlled_partial_normalization


SCENARIO_ID = "controlled_partial_success/1"
ALLOWED_SUFFIXES = {".htm", ".html", ".markdown", ".md", ".txt", ".xlsx"}


class NormalizationDiagnosticError(RuntimeError):
    def __init__(self, message: str, *, reason: str = "normalization_diagnostic_invalid", exit_code: int = 3):
        super().__init__(message)
        self.reason = reason
        self.exit_code = exit_code


@dataclass(frozen=True)
class NormalizationDiagnosticResult:
    run_id: str
    worker: WorkerRunResult
    payload: dict[str, Any]


def run_controlled_normalization_diagnostic(
    workspace_dir: str | Path,
    *,
    source_revision_id: str,
    scenario: str,
) -> NormalizationDiagnosticResult:
    if scenario != SCENARIO_ID:
        raise NormalizationDiagnosticError(
            f"Unsupported normalization diagnostic scenario: {scenario}.",
            reason="diagnostic_scenario_not_allowed",
        )
    settings = resolve_database_settings(workspace_dir)
    revision = _load_revision(settings, source_revision_id)
    source_path = resolve_workspace_path(settings.workspace_dir, str(revision["file_path"]))
    config = load_config(settings.workspace_dir)
    max_file_bytes = int(config["excel"]["max_file_bytes"])
    try:
        if source_path.stat().st_size > max_file_bytes:
            raise NormalizationDiagnosticError(
                f"Diagnostic source exceeds the {max_file_bytes}-byte input budget.",
                reason="diagnostic_input_budget_exceeded",
            )
        source_bytes = source_path.read_bytes()
    except OSError as exc:
        raise NormalizationDiagnosticError(
            f"Registered source cannot be read: {revision['file_path']}.",
            reason="diagnostic_source_unreadable",
        ) from exc
    actual_hash = hashlib.sha256(source_bytes).hexdigest()
    if actual_hash != str(revision["content_hash"]):
        raise NormalizationDiagnosticError(
            "Registered source bytes do not match source_revisions.content_hash.",
            reason="source_revision_changed",
            exit_code=4,
        )
    suffix = source_path.suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise NormalizationDiagnosticError(
            f"Source format is not allowed for controlled diagnostics: {suffix or '<none>'}.",
            reason="diagnostic_format_not_allowed",
        )
    preflight = _safe_preflight(settings.workspace_dir, source_path, source_bytes, actual_hash)
    state_before = _production_state_hash(settings)

    started = start_run(
        settings.workspace_dir,
        run_type="normalization_diagnostic",
        input_payload={
            "controlled_simulation": True,
            "scenario": scenario,
            "source_revision_id": source_revision_id,
        },
    )
    output_dir = (
        f"artifacts/runs/{started.record.run_id}/diagnostics/normalization"
    )
    excel = config["excel"]
    worker = run_worker(
        settings.workspace_dir,
        run_id=started.record.run_id,
        worker_name=controlled_partial_normalization.WORKER_NAME,
        worker_version=controlled_partial_normalization.WORKER_VERSION,
        worker_path=Path(controlled_partial_normalization.__file__).resolve(),
        input_payload={
            "controlled_simulation": True,
            "input_path": str(revision["file_path"]),
            "output_dir": output_dir,
            "preflight": preflight,
            "scenario": scenario,
            "source_hash": actual_hash,
            "source_revision_id": source_revision_id,
        },
        accepted_exit_codes=(6,),
        timeout_seconds=min(float(excel["worker_timeout_seconds"]), 60.0),
        max_output_bytes=min(int(excel["max_output_bytes"]), 1_048_576),
        memory_limit_bytes=min(int(excel["worker_memory_bytes"]), 536_870_912),
    )
    if worker.status != "partial" or worker.exit_code != 6 or worker.output is None:
        raise NormalizationDiagnosticError(
            worker.error or "Controlled partial diagnostic did not reach partial status.",
            reason="controlled_partial_failed",
            exit_code=5,
        )
    state_after = _production_state_hash(settings)
    if state_after != state_before:
        raise NormalizationDiagnosticError(
            "Controlled diagnostic changed production normalization state.",
            reason="diagnostic_production_mutation",
            exit_code=5,
        )
    payload = {
        **worker.output,
        "preflight": preflight,
        "production_state_hash_after": state_after,
        "production_state_hash_before": state_before,
        "source_revision_id": source_revision_id,
    }
    return NormalizationDiagnosticResult(started.record.run_id, worker, payload)


def _load_revision(settings: Any, source_revision_id: str) -> Any:
    connection = open_database(settings.database_path, enable_wal=settings.wal_enabled)
    try:
        validate_database_migrations(connection)
        row = connection.execute(
            """
            SELECT source_revision_id, source_id, file_path, content_hash, normalized_hash
            FROM source_revisions WHERE source_revision_id = ?
            """,
            (source_revision_id,),
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        raise NormalizationDiagnosticError(
            f"Source revision not found: {source_revision_id}.",
            reason="unknown_source_revision",
        )
    return row


def _safe_preflight(
    workspace: Path,
    source_path: Path,
    source_bytes: bytes,
    source_hash: str,
) -> dict[str, Any]:
    if source_path.suffix.lower() != ".xlsx":
        return {
            "external_relationships": 0,
            "macros_present": False,
            "network_accessed": False,
            "status": "completed",
        }
    limits = ExcelLimits.from_config(load_config(workspace)["excel"])
    try:
        result = preflight_ooxml(
            io.BytesIO(source_bytes),
            original_name=source_path.name,
            source_hash=source_hash,
            limits=limits,
        )
    except OoxmlPreflightError as exc:
        raise NormalizationDiagnosticError(
            str(exc), reason=exc.reason, exit_code=exc.exit_code
        ) from exc
    macro_or_ole = any(
        "vba" in content_type.lower()
        or "oleobject" in content_type.lower()
        or "embeddings/" in name.lower()
        for name, content_type in result.part_content_types
    )
    if result.external_relationships or macro_or_ole:
        raise NormalizationDiagnosticError(
            "Controlled diagnostics reject external relationships, macros, and OLE parts.",
            reason="diagnostic_active_content_rejected",
        )
    return {
        "external_relationships": result.external_relationships,
        "macros_present": False,
        "network_accessed": False,
        "status": "completed",
    }


def _production_state_hash(settings: Any) -> str:
    connection = open_database(settings.database_path, enable_wal=settings.wal_enabled)
    try:
        state = {
            "candidate_records": connection.execute("SELECT COUNT(*) FROM candidate_records").fetchone()[0],
            "chunks": connection.execute("SELECT COUNT(*) FROM chunks").fetchone()[0],
            "facts": connection.execute("SELECT COUNT(*) FROM facts").fetchone()[0],
            "normalized_hashes": connection.execute(
                "SELECT source_revision_id, normalized_hash FROM source_revisions ORDER BY source_revision_id"
            ).fetchall(),
            "relations": connection.execute("SELECT COUNT(*) FROM relations").fetchone()[0],
            "source_fragments": connection.execute("SELECT COUNT(*) FROM source_fragments").fetchone()[0],
            "workbook_manifests": connection.execute("SELECT COUNT(*) FROM workbook_manifests").fetchone()[0],
        }
    finally:
        connection.close()
    serializable = {
        **state,
        "normalized_hashes": [list(row) for row in state["normalized_hashes"]],
    }
    return hashlib.sha256(
        json.dumps(serializable, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
