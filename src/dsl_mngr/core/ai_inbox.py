from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dsl_mngr.core.ai_package import (
    AI_PACKAGE_STATUS_IMPORTED,
    AI_PACKAGE_STATUS_STALE,
    AiPackageError,
    StaleCheck,
    check_ai_package_stale,
    get_ai_package_record,
    update_ai_package_status,
    write_ai_import_process_report,
)
from dsl_mngr.core.candidate_import import (
    CandidateImportError,
    CandidateImportResult,
    import_candidate_file,
    prepare_candidate_input_file,
)
from dsl_mngr.core.config import load_config
from dsl_mngr.core.database import (
    DatabaseConfigurationError,
    open_database,
    resolve_database_settings,
    resolve_workspace_path,
)
from dsl_mngr.core.runs import (
    DatabaseNotReadyError,
    RunLifecycleError,
    complete_run,
    fail_run,
    start_run,
    timestamp_now,
    validate_database_migrations,
)


PACKAGE_ID_RE = re.compile(r"^AIPKG_[0-9]{6}$")
CANDIDATE_FILE_RE = re.compile(r"^(AIPKG_[0-9]{6})_candidates[.]jsonl$")


class AiInboxError(RuntimeError):
    """Raised when AI inbox scan or import cannot be completed."""


class AiPackageStaleError(AiInboxError):
    """Raised when a package is stale and import was not explicitly allowed."""

    def __init__(self, stale_check: StaleCheck) -> None:
        reason = stale_check.reason or "stale"
        super().__init__(f"AI package {stale_check.package_id} is stale: {reason}.")
        self.stale_check = stale_check


@dataclass(frozen=True)
class InboxScanItem:
    package_id: str
    candidate_file: str
    package_exists: bool
    is_stale: bool
    reason: str | None


@dataclass(frozen=True)
class AiImportResult:
    package_id: str
    run_id: str
    batch_id: str
    input_path: str
    total_records: int
    accepted_count: int
    rejected_count: int
    stale_allowed: bool
    stale_reason: str | None

    @classmethod
    def from_candidate_result(
        cls,
        *,
        package_id: str,
        candidate_result: CandidateImportResult,
        stale_allowed: bool,
        stale_reason: str | None,
    ) -> "AiImportResult":
        return cls(
            package_id=package_id,
            run_id=candidate_result.run_id,
            batch_id=candidate_result.batch_id,
            input_path=candidate_result.input_path,
            total_records=candidate_result.total_records,
            accepted_count=candidate_result.accepted_count,
            rejected_count=candidate_result.rejected_count,
            stale_allowed=stale_allowed,
            stale_reason=stale_reason,
        )

    def to_output_payload(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted_count,
            "accepted_count": self.accepted_count,
            "batch_id": self.batch_id,
            "input_path": self.input_path,
            "package_id": self.package_id,
            "rejected": self.rejected_count,
            "rejected_count": self.rejected_count,
            "run_id": self.run_id,
            "stale_allowed": self.stale_allowed,
            "stale_reason": self.stale_reason,
            "total": self.total_records,
            "total_records": self.total_records,
        }


def scan_ai_inbox(workspace_dir: str | Path) -> list[InboxScanItem]:
    settings = resolve_database_settings(workspace_dir)
    _ensure_database_ready(settings)
    inbox_dir = _resolve_ai_inbox_dir(settings.workspace_dir)
    items: list[InboxScanItem] = []
    for path in sorted(inbox_dir.iterdir(), key=lambda item: item.name.lower()):
        if not path.is_file():
            continue
        match = CANDIDATE_FILE_RE.fullmatch(path.name)
        if match is None:
            continue
        package_id = match.group(1)
        stale_check = check_ai_package_stale(settings, package_id)
        items.append(
            InboxScanItem(
                package_id=package_id,
                candidate_file=path.relative_to(settings.workspace_dir).as_posix(),
                package_exists=stale_check.exists,
                is_stale=stale_check.is_stale,
                reason=stale_check.reason,
            )
        )
    return items


def import_ai_candidates(
    workspace_dir: str | Path,
    *,
    package_id: str,
    input_path: str | Path | None = None,
    allow_stale: bool = False,
) -> AiImportResult:
    if PACKAGE_ID_RE.fullmatch(package_id) is None:
        raise AiInboxError(f"Invalid AI package id: {package_id}.")

    settings = resolve_database_settings(workspace_dir)
    _ensure_database_ready(settings)
    package_record = _load_existing_package(settings, package_id)
    manifest_path = resolve_workspace_path(settings.workspace_dir, package_record.manifest_path)
    if not manifest_path.is_file():
        raise AiInboxError(f"Package manifest is missing: {package_record.manifest_path}.")

    candidate_input = _prepare_ai_candidate_input(settings.workspace_dir, package_id, input_path)
    stale_check = check_ai_package_stale(settings, package_id)
    if stale_check.is_stale and not allow_stale:
        _mark_package_stale(settings, package_id, stale_check.reason)
        raise AiPackageStaleError(stale_check)

    started = start_run(
        settings.workspace_dir,
        run_type="candidate_import",
        input_payload={
            "input_path": candidate_input.relative_path,
            "package_id": package_id,
            "stale_allowed": allow_stale,
            "stale_check": {
                "is_stale": stale_check.is_stale,
                "reason": stale_check.reason,
            },
        },
    )
    try:
        candidate_result = import_candidate_file(
            settings.workspace_dir,
            run_id=started.record.run_id,
            input_path=candidate_input.path,
        )
        result = AiImportResult.from_candidate_result(
            package_id=package_id,
            candidate_result=candidate_result,
            stale_allowed=allow_stale,
            stale_reason=stale_check.reason if stale_check.is_stale else None,
        )
        complete_run(
            settings.workspace_dir,
            started.record.run_id,
            output_payload=result.to_output_payload(),
        )
        _mark_package_imported(settings, package_id, result.stale_reason)
        write_ai_import_process_report(
            settings.workspace_dir,
            run_id=result.run_id,
            package_id=result.package_id,
            input_path=result.input_path,
            batch_id=result.batch_id,
            total_records=result.total_records,
            accepted_count=result.accepted_count,
            rejected_count=result.rejected_count,
            stale_allowed=result.stale_allowed,
            stale_reason=result.stale_reason,
        )
        return result
    except (CandidateImportError, DatabaseConfigurationError, RunLifecycleError) as exc:
        try:
            fail_run(
                settings.workspace_dir,
                started.record.run_id,
                error=str(exc),
                output_payload={"error": str(exc), "package_id": package_id},
            )
        except (DatabaseConfigurationError, DatabaseNotReadyError, RunLifecycleError):
            pass
        raise


def _ensure_database_ready(settings: Any) -> None:
    if not settings.database_path.is_file():
        raise AiInboxError(
            f"Database is not initialized: {settings.database_path}. "
            "Run 'dsl-manager db init <workspace>' before using AI inbox commands."
        )
    connection = open_database(settings.database_path, enable_wal=settings.wal_enabled)
    try:
        validate_database_migrations(connection)
    finally:
        connection.close()


def _resolve_ai_inbox_dir(workspace_dir: Path) -> Path:
    config = load_config(workspace_dir)
    ai_config = config.get("ai_handoff", {})
    configured_path = ai_config.get("inbox_dir", "ai/inbox")
    inbox_dir = resolve_workspace_path(workspace_dir, configured_path)
    if not inbox_dir.is_dir():
        raise AiInboxError(f"AI inbox directory is missing: {inbox_dir}.")
    return inbox_dir


def _load_existing_package(settings: Any, package_id: str):
    connection = open_database(settings.database_path, enable_wal=settings.wal_enabled)
    try:
        validate_database_migrations(connection)
        record = get_ai_package_record(connection, package_id)
    finally:
        connection.close()
    if record is None:
        raise AiInboxError(f"AI package is not registered: {package_id}.")
    return record


def _prepare_ai_candidate_input(
    workspace_dir: Path,
    package_id: str,
    input_path: str | Path | None,
):
    if input_path is None:
        input_path = f"ai/inbox/{package_id}_candidates.jsonl"
    return prepare_candidate_input_file(workspace_dir, input_path)


def _mark_package_stale(settings: Any, package_id: str, reason: str | None) -> None:
    connection = open_database(settings.database_path, enable_wal=settings.wal_enabled)
    try:
        validate_database_migrations(connection)
        connection.execute("BEGIN")
        try:
            update_ai_package_status(
                connection,
                package_id=package_id,
                status=AI_PACKAGE_STATUS_STALE,
                stale_reason=reason,
                timestamp=timestamp_now(None),
            )
        except Exception:
            connection.rollback()
            raise
        else:
            connection.commit()
    finally:
        connection.close()


def _mark_package_imported(settings: Any, package_id: str, stale_reason: str | None) -> None:
    connection = open_database(settings.database_path, enable_wal=settings.wal_enabled)
    try:
        validate_database_migrations(connection)
        connection.execute("BEGIN")
        try:
            update_ai_package_status(
                connection,
                package_id=package_id,
                status=AI_PACKAGE_STATUS_IMPORTED,
                stale_reason=stale_reason,
                timestamp=timestamp_now(None),
            )
        except Exception:
            connection.rollback()
            raise
        else:
            connection.commit()
    finally:
        connection.close()
