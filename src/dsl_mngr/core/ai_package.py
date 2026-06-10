from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dsl_mngr.core.candidate_validation import (
    ALLOWED_ASSERTION_TYPES,
    ALLOWED_CONFIDENCE,
    ALLOWED_RECORD_TYPES,
    COMMON_REQUIRED_FIELDS,
    SPECIFIC_REQUIRED_FIELDS,
)
from dsl_mngr.core.database import DatabaseConfigurationError, DatabaseSettings, open_database
from dsl_mngr.core.runs import (
    canonical_json,
    next_id,
    relative_workspace_path,
    run_artifact_paths,
    timestamp_now,
    validate_database_migrations,
    write_process_report,
)


AI_PACKAGE_STATUS_WAITING = "waiting_for_ai_candidates"
AI_PACKAGE_STATUS_IMPORTED = "imported"
AI_PACKAGE_STATUS_STALE = "stale"
WORKER_NAME = "build_ai_package"
WORKER_VERSION = "1.0"

SUPPORTED_AI_PACKAGE_OPTIONS = {
    "include_chunks",
    "include_fragments",
    "include_candidate_schema",
    "include_output_template",
    "max_evidence_chars",
    "strict_options_fail_on_unsupported_option",
    "package_format",
}


class AiPackageError(RuntimeError):
    """Raised when an AI package cannot be prepared or verified safely."""


class UnsupportedAiPackageOption(AiPackageError):
    """Raised by the worker for strict unsupported ai_package options."""

    def __init__(self, option_key: str) -> None:
        super().__init__(f"Unsupported AI package option: {option_key}.")
        self.option_key = option_key


@dataclass(frozen=True)
class AiPackageOptions:
    include_chunks: bool = True
    include_fragments: bool = True
    include_candidate_schema: bool = True
    include_output_template: bool = True
    max_evidence_chars: int = 20000
    strict_options_fail_on_unsupported_option: bool = True
    package_format: str = "markdown_plus_json"


@dataclass(frozen=True)
class PreparedAiPackage:
    package_id: str
    output_dir: str
    worker_input: dict[str, Any]
    source_revision_count: int
    chunk_count: int
    fragment_count: int


@dataclass(frozen=True)
class AiPackageRecord:
    package_id: str
    run_id: str
    package_path: str
    manifest_path: str
    content_path: str
    instructions_path: str
    candidate_schema_path: str
    output_template_path: str
    package_hash: str
    source_revision_count: int
    chunk_count: int
    fragment_count: int
    status: str
    stale_reason: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class StaleCheck:
    package_id: str
    exists: bool
    is_stale: bool
    reason: str | None
    details: dict[str, Any]


def next_ai_package_id(connection: sqlite3.Connection) -> str:
    return next_id(connection, "ai_packages", "package_id", "AIPKG")


def prepare_ai_package_input(
    settings: DatabaseSettings,
    *,
    package_id: str,
    revision_ids: tuple[str, ...],
    profile: str,
    worker_config: dict[str, Any],
    ai_package_options: dict[str, Any],
) -> PreparedAiPackage:
    if not settings.database_path.is_file():
        raise AiPackageError(
            f"Database is not initialized: {settings.database_path}. "
            "Run 'dsl-manager db init <workspace>' before 'dsl-manager ai package'."
        )

    include_chunks = _option_bool(ai_package_options, "include_chunks", True)
    include_fragments = _option_bool(ai_package_options, "include_fragments", True)

    connection = open_database(settings.database_path, enable_wal=settings.wal_enabled)
    try:
        validate_database_migrations(connection)
        source_revisions = _load_source_revisions(
            connection,
            revision_ids=revision_ids,
            include_chunks=include_chunks,
            include_fragments=include_fragments,
        )
        revision_id_tuple = tuple(row["source_revision_id"] for row in source_revisions)
        chunks = _load_active_chunks(connection, revision_id_tuple) if include_chunks else []
        fragments = (
            _load_active_fragments(connection, revision_id_tuple) if include_fragments else []
        )
    finally:
        connection.close()

    if not chunks and not fragments:
        raise AiPackageError("No active chunks or fragments are available for AI packaging.")

    output_dir = f"ai/outbox/{package_id}"
    worker_input = {
        "ai_package_options": ai_package_options,
        "chunks": chunks,
        "fragments": fragments,
        "output_dir": output_dir,
        "package_id": package_id,
        "profile": profile,
        "source_revisions": source_revisions,
        "worker_config": worker_config,
    }
    return PreparedAiPackage(
        package_id=package_id,
        output_dir=output_dir,
        worker_input=worker_input,
        source_revision_count=len(source_revisions),
        chunk_count=len(chunks),
        fragment_count=len(fragments),
    )


def persist_ai_package_output(
    connection: sqlite3.Connection,
    *,
    workspace_dir: Path,
    output: dict[str, Any],
    expected_package_id: str,
    expected_run_id: str,
    expected_source_revision_count: int,
    expected_chunk_count: int,
    expected_fragment_count: int,
    timestamp: str,
) -> AiPackageRecord:
    if output.get("package_id") != expected_package_id:
        raise AiPackageError("Worker output package_id is incoherent.")
    if output.get("run_id") != expected_run_id:
        raise AiPackageError("Worker output run_id is incoherent.")
    if output.get("status") != "completed":
        raise AiPackageError("Worker output status must be completed.")

    package_path = _required_relative_path(output, "package_path")
    manifest_path = _required_relative_path(output, "manifest_path")
    source_manifest_path = _required_relative_path(output, "source_manifest_path")
    content_path = _required_relative_path(output, "content_path")
    instructions_path = _required_relative_path(output, "instructions_path")
    candidate_schema_path = _required_relative_path(output, "candidate_schema_path")
    output_template_path = _required_relative_path(output, "output_template_path")
    package_hash = _required_sha256(output, "package_hash")

    if output.get("source_revision_count") != expected_source_revision_count:
        raise AiPackageError("Worker output source_revision_count is incoherent.")
    if output.get("chunk_count") != expected_chunk_count:
        raise AiPackageError("Worker output chunk_count is incoherent.")
    if output.get("fragment_count") != expected_fragment_count:
        raise AiPackageError("Worker output fragment_count is incoherent.")

    package_dir = _resolve_workspace_path(workspace_dir, package_path)
    if not package_dir.is_dir():
        raise AiPackageError(f"Package directory is missing: {package_path}.")

    paths = {
        "candidate_schema": candidate_schema_path,
        "content": content_path,
        "instructions": instructions_path,
        "output_template": output_template_path,
        "source_manifest": source_manifest_path,
    }
    for relative_path in (*paths.values(), manifest_path):
        if not _resolve_workspace_path(workspace_dir, relative_path).is_file():
            raise AiPackageError(f"Package file is missing: {relative_path}.")

    package_manifest = _read_json_file(workspace_dir, manifest_path)
    source_manifest = _read_json_file(workspace_dir, source_manifest_path)
    _validate_source_manifest(
        source_manifest,
        expected_package_id=expected_package_id,
        expected_package_path=package_path,
        expected_source_revision_count=expected_source_revision_count,
        expected_chunk_count=expected_chunk_count,
        expected_fragment_count=expected_fragment_count,
    )
    _validate_package_manifest(
        package_manifest,
        expected_package_id=expected_package_id,
        expected_run_id=expected_run_id,
        expected_package_path=package_path,
        expected_source_manifest_path=source_manifest_path,
        expected_package_hash=package_hash,
        expected_source_revision_count=expected_source_revision_count,
        expected_chunk_count=expected_chunk_count,
        expected_fragment_count=expected_fragment_count,
    )
    _validate_manifest_file_hashes(workspace_dir, package_manifest, paths)

    actual_package_hash = compute_package_hash_from_manifest(package_manifest)
    if actual_package_hash != package_hash:
        raise AiPackageError("Package hash does not match manifest file hashes.")

    connection.execute(
        """
        INSERT INTO ai_packages (
            package_id,
            run_id,
            package_path,
            manifest_path,
            content_path,
            instructions_path,
            candidate_schema_path,
            output_template_path,
            package_hash,
            source_revision_count,
            chunk_count,
            fragment_count,
            status,
            stale_reason,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)
        """,
        (
            expected_package_id,
            expected_run_id,
            package_path,
            manifest_path,
            content_path,
            instructions_path,
            candidate_schema_path,
            output_template_path,
            package_hash,
            expected_source_revision_count,
            expected_chunk_count,
            expected_fragment_count,
            AI_PACKAGE_STATUS_WAITING,
            timestamp,
            timestamp,
        ),
    )
    return AiPackageRecord(
        package_id=expected_package_id,
        run_id=expected_run_id,
        package_path=package_path,
        manifest_path=manifest_path,
        content_path=content_path,
        instructions_path=instructions_path,
        candidate_schema_path=candidate_schema_path,
        output_template_path=output_template_path,
        package_hash=package_hash,
        source_revision_count=expected_source_revision_count,
        chunk_count=expected_chunk_count,
        fragment_count=expected_fragment_count,
        status=AI_PACKAGE_STATUS_WAITING,
        stale_reason=None,
        created_at=timestamp,
        updated_at=timestamp,
    )


def get_ai_package_record(
    connection: sqlite3.Connection,
    package_id: str,
) -> AiPackageRecord | None:
    row = connection.execute(
        """
        SELECT
            package_id,
            run_id,
            package_path,
            manifest_path,
            content_path,
            instructions_path,
            candidate_schema_path,
            output_template_path,
            package_hash,
            source_revision_count,
            chunk_count,
            fragment_count,
            status,
            stale_reason,
            created_at,
            updated_at
        FROM ai_packages
        WHERE package_id = ?
        """,
        (package_id,),
    ).fetchone()
    if row is None:
        return None
    return AiPackageRecord(
        package_id=row["package_id"],
        run_id=row["run_id"],
        package_path=row["package_path"],
        manifest_path=row["manifest_path"],
        content_path=row["content_path"],
        instructions_path=row["instructions_path"],
        candidate_schema_path=row["candidate_schema_path"],
        output_template_path=row["output_template_path"],
        package_hash=row["package_hash"],
        source_revision_count=int(row["source_revision_count"]),
        chunk_count=int(row["chunk_count"]),
        fragment_count=int(row["fragment_count"]),
        status=row["status"],
        stale_reason=row["stale_reason"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def check_ai_package_stale(
    settings: DatabaseSettings,
    package_id: str,
) -> StaleCheck:
    if not settings.database_path.is_file():
        raise AiPackageError(
            f"Database is not initialized: {settings.database_path}. "
            "Run 'dsl-manager db init <workspace>' before checking AI packages."
        )

    connection = open_database(settings.database_path, enable_wal=settings.wal_enabled)
    try:
        validate_database_migrations(connection)
        record = get_ai_package_record(connection, package_id)
        if record is None:
            return StaleCheck(
                package_id=package_id,
                exists=False,
                is_stale=True,
                reason="package_not_registered",
                details={},
            )
        manifest_path = _resolve_workspace_path(settings.workspace_dir, record.manifest_path)
        if not manifest_path.is_file():
            return StaleCheck(
                package_id=package_id,
                exists=True,
                is_stale=True,
                reason="package_manifest_missing",
                details={"manifest_path": record.manifest_path},
            )
        package_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        source_manifest_path = package_manifest.get("source_manifest_path")
        if not isinstance(source_manifest_path, str):
            source_manifest_path = f"{record.package_path}/source_manifest.json"
        source_manifest_file = _resolve_workspace_path(settings.workspace_dir, source_manifest_path)
        if not source_manifest_file.is_file():
            return StaleCheck(
                package_id=package_id,
                exists=True,
                is_stale=True,
                reason="source_manifest_missing",
                details={"source_manifest_path": source_manifest_path},
            )
        source_manifest = json.loads(source_manifest_file.read_text(encoding="utf-8"))
        stale = _check_source_manifest_stale(connection, source_manifest)
    finally:
        connection.close()

    if stale is None:
        return StaleCheck(
            package_id=package_id,
            exists=True,
            is_stale=False,
            reason=None,
            details={},
        )
    reason, details = stale
    return StaleCheck(
        package_id=package_id,
        exists=True,
        is_stale=True,
        reason=reason,
        details=details,
    )


def update_ai_package_status(
    connection: sqlite3.Connection,
    *,
    package_id: str,
    status: str,
    stale_reason: str | None,
    timestamp: str,
) -> None:
    connection.execute(
        """
        UPDATE ai_packages
        SET status = ?,
            stale_reason = ?,
            updated_at = ?
        WHERE package_id = ?
        """,
        (status, stale_reason, timestamp, package_id),
    )


def write_ai_package_process_report(
    workspace_dir: str | Path,
    output_payload: dict[str, Any],
) -> None:
    artifacts = run_artifact_paths(workspace_dir, output_payload["run_id"])
    report = json.loads(artifacts.process_report_path.read_text(encoding="utf-8"))
    report.update(
        {
            "chunk_count": output_payload.get("chunk_count"),
            "content_path": output_payload.get("content_path"),
            "fragment_count": output_payload.get("fragment_count"),
            "manifest_path": output_payload.get("manifest_path"),
            "package_hash": output_payload.get("package_hash"),
            "package_id": output_payload.get("package_id"),
            "package_path": output_payload.get("package_path"),
            "source_revision_count": output_payload.get("source_revision_count"),
        }
    )
    write_process_report(artifacts.process_report_path, report)


def write_ai_import_process_report(
    workspace_dir: str | Path,
    *,
    run_id: str,
    package_id: str,
    input_path: str,
    batch_id: str,
    total_records: int,
    accepted_count: int,
    rejected_count: int,
    stale_allowed: bool,
    stale_reason: str | None,
) -> None:
    artifacts = run_artifact_paths(workspace_dir, run_id)
    report = json.loads(artifacts.process_report_path.read_text(encoding="utf-8"))
    report.update(
        {
            "accepted_count": accepted_count,
            "batch_id": batch_id,
            "input_path": input_path,
            "package_id": package_id,
            "rejected_count": rejected_count,
            "stale_allowed": stale_allowed,
            "stale_reason": stale_reason,
            "total_records": total_records,
        }
    )
    write_process_report(artifacts.process_report_path, report)


def parse_ai_package_options(raw_options: dict[str, Any]) -> AiPackageOptions:
    strict = _as_bool(raw_options.get("strict_options_fail_on_unsupported_option", True))
    unsupported = sorted(set(raw_options) - SUPPORTED_AI_PACKAGE_OPTIONS)
    if strict and unsupported:
        raise UnsupportedAiPackageOption(unsupported[0])

    package_format = str(raw_options.get("package_format", "markdown_plus_json"))
    if package_format != "markdown_plus_json":
        raise AiPackageError(f"Unsupported AI package format: {package_format}.")

    max_evidence_chars = _as_positive_int(raw_options.get("max_evidence_chars", 20000))
    return AiPackageOptions(
        include_chunks=_as_bool(raw_options.get("include_chunks", True)),
        include_fragments=_as_bool(raw_options.get("include_fragments", True)),
        include_candidate_schema=_as_bool(raw_options.get("include_candidate_schema", True)),
        include_output_template=_as_bool(raw_options.get("include_output_template", True)),
        max_evidence_chars=max_evidence_chars,
        strict_options_fail_on_unsupported_option=strict,
        package_format=package_format,
    )


def build_instructions_markdown(package_id: str) -> str:
    return "\n".join(
        (
            f"# AI Package Handoff {package_id}",
            "",
            "You are an external AI tool. Treat this package as read-only evidence.",
            "",
            "Rules:",
            "- Do not update databases, registries, DSL snapshots, or project files.",
            "- Produce only JSONL candidate records.",
            "- Use only evidence blocks present in content.md.",
            "- Copy source_revision_id, chunk_id, and fragment_id exactly as provided.",
            "- Set evidence_text to text contained literally in the referenced evidence.",
            "- Use record_type candidate_fact, candidate_relation, candidate_mapping, candidate_conflict, or candidate_question.",
            "- Do not invent evidence.",
            "- Prefer assertion_type explicit for declarative text.",
            "- Use assertion_type observed for logs or runtime events.",
            "- Use assertion_type inferred only when inference is truly required.",
            "- Use assertion_type ambiguous for ambiguity.",
            "",
            "Expected output path:",
            "",
            f"```text\nai/inbox/{package_id}_candidates.jsonl\n```",
            "",
        )
    )


def build_content_markdown(
    *,
    package_id: str,
    source_revisions: list[dict[str, Any]],
    chunks: list[dict[str, Any]],
    fragments: list[dict[str, Any]],
    max_evidence_chars: int,
) -> str:
    source_by_revision = {
        revision["source_revision_id"]: revision for revision in source_revisions
    }
    lines: list[str] = [
        f"# AI Package Content {package_id}",
        "",
        "Use only the evidence blocks below.",
        "",
    ]
    for chunk in chunks:
        source = source_by_revision[chunk["source_revision_id"]]
        text, truncated = _evidence_text(chunk["text"], max_evidence_chars)
        lines.extend(
            [
                f"## Evidence {chunk['chunk_id']}",
                "",
                f"- source_id: {source['source_id']}",
                f"- source_revision_id: {source['source_revision_id']}",
                f"- source_path: {source['file_path']}",
                f"- source_type: {source['source_type']}",
                f"- authority_level: {source['authority_level']}",
                "- evidence_kind: chunk",
                f"- chunk_id: {chunk['chunk_id']}",
                f"- sequence: {chunk['sequence']}",
                f"- text_hash: {chunk['text_hash']}",
                f"- truncated: {_format_bool(truncated)}",
                "",
                _fenced_text(text),
                "",
            ]
        )
    for fragment in fragments:
        source = source_by_revision[fragment["source_revision_id"]]
        text, truncated = _evidence_text(fragment["text"], max_evidence_chars)
        lines.extend(
            [
                f"## Evidence {fragment['fragment_id']}",
                "",
                f"- source_id: {source['source_id']}",
                f"- source_revision_id: {source['source_revision_id']}",
                f"- source_path: {source['file_path']}",
                f"- source_type: {source['source_type']}",
                f"- authority_level: {source['authority_level']}",
                "- evidence_kind: fragment",
                f"- fragment_id: {fragment['fragment_id']}",
                f"- fragment_type: {fragment['fragment_type']}",
                f"- path_or_selector: {fragment['path_or_selector']}",
                f"- sequence: {fragment['sequence']}",
                f"- text_hash: {fragment['text_hash']}",
                f"- truncated: {_format_bool(truncated)}",
                "",
                _fenced_text(text),
                "",
            ]
        )
    return "\n".join(lines)


def build_source_manifest_payload(
    *,
    package_id: str,
    package_path: str,
    source_revisions: list[dict[str, Any]],
    chunks: list[dict[str, Any]],
    fragments: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "chunks": [
            {
                "chunk_id": chunk["chunk_id"],
                "sequence": chunk["sequence"],
                "source_revision_id": chunk["source_revision_id"],
                "status": chunk["status"],
                "text_hash": chunk["text_hash"],
            }
            for chunk in chunks
        ],
        "counts": {
            "chunks": len(chunks),
            "fragments": len(fragments),
            "source_revisions": len(source_revisions),
        },
        "fragments": [
            {
                "fragment_id": fragment["fragment_id"],
                "fragment_type": fragment["fragment_type"],
                "sequence": fragment["sequence"],
                "source_revision_id": fragment["source_revision_id"],
                "status": fragment["status"],
                "text_hash": fragment["text_hash"],
            }
            for fragment in fragments
        ],
        "package_id": package_id,
        "package_path": package_path,
        "source_revisions": [
            {
                "content_hash": revision["content_hash"],
                "current_revision_id": revision["current_revision_id"],
                "file_path": revision["file_path"],
                "revision_status": revision["revision_status"],
                "source_id": revision["source_id"],
                "source_revision_id": revision["source_revision_id"],
            }
            for revision in source_revisions
        ],
    }


def candidate_schema_payload() -> dict[str, Any]:
    common_required = ("record_type", *COMMON_REQUIRED_FIELDS)
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "additionalProperties": True,
        "allowed_record_types": sorted(ALLOWED_RECORD_TYPES),
        "anyOf": [{"required": ["chunk_id"]}, {"required": ["fragment_id"]}],
        "common_required_fields": list(common_required),
        "description": "Handoff schema aligned with dsl_mngr candidate_validation.",
        "properties": {
            "assertion_type": {"enum": sorted(ALLOWED_ASSERTION_TYPES), "type": "string"},
            "candidate_id": {"type": "string"},
            "chunk_id": {"type": ["string", "null"]},
            "confidence": {"enum": sorted(ALLOWED_CONFIDENCE), "type": "string"},
            "evidence_text": {"type": "string"},
            "fragment_id": {"type": ["string", "null"]},
            "record_type": {"enum": sorted(ALLOWED_RECORD_TYPES), "type": "string"},
            "source_revision_id": {"type": "string"},
        },
        "record_specific_required_fields": {
            key: list(value) for key, value in sorted(SPECIFIC_REQUIRED_FIELDS.items())
        },
        "required": list(common_required),
        "title": "DSL Manager AI Candidate JSONL Record",
        "type": "object",
    }


def build_output_template_jsonl(
    *,
    chunks: list[dict[str, Any]],
    fragments: list[dict[str, Any]],
) -> str:
    records: list[dict[str, Any]] = []
    if chunks:
        chunk = chunks[0]
        records.append(
            {
                "assertion_type": "explicit",
                "candidate_id": "CAND_REPLACE_FACT_001",
                "chunk_id": chunk["chunk_id"],
                "confidence": "medium",
                "entity_name": "REPLACE_ENTITY",
                "evidence_text": _sample_evidence_text(chunk["text"]),
                "fact_type": "REPLACE_FACT_TYPE",
                "fragment_id": None,
                "property_name": "REPLACE_PROPERTY",
                "property_value": "REPLACE_VALUE",
                "record_type": "candidate_fact",
                "source_revision_id": chunk["source_revision_id"],
            }
        )
    elif fragments:
        fragment = fragments[0]
        records.append(
            {
                "assertion_type": "explicit",
                "candidate_id": "CAND_REPLACE_FACT_001",
                "chunk_id": None,
                "confidence": "medium",
                "entity_name": "REPLACE_ENTITY",
                "evidence_text": _sample_evidence_text(fragment["text"]),
                "fact_type": "REPLACE_FACT_TYPE",
                "fragment_id": fragment["fragment_id"],
                "property_name": "REPLACE_PROPERTY",
                "property_value": "REPLACE_VALUE",
                "record_type": "candidate_fact",
                "source_revision_id": fragment["source_revision_id"],
            }
        )

    if fragments:
        fragment = fragments[0]
        records.append(
            {
                "assertion_type": "explicit",
                "candidate_id": "CAND_REPLACE_RELATION_001",
                "chunk_id": None,
                "confidence": "medium",
                "evidence_text": _sample_evidence_text(fragment["text"]),
                "fragment_id": fragment["fragment_id"],
                "record_type": "candidate_relation",
                "relation_type": "REPLACE_RELATION",
                "source_entity": "REPLACE_SOURCE_ENTITY",
                "source_revision_id": fragment["source_revision_id"],
                "target_entity": "REPLACE_TARGET_ENTITY",
            }
        )

    evidence = chunks[0] if chunks else fragments[0]
    records.append(
        {
            "assertion_type": "ambiguous",
            "candidate_id": "CAND_REPLACE_QUESTION_001",
            "chunk_id": evidence.get("chunk_id"),
            "confidence": "low",
            "evidence_text": _sample_evidence_text(evidence["text"]),
            "fragment_id": evidence.get("fragment_id"),
            "question_text": "REPLACE_WITH_A_QUESTION_ABOUT_THE_REFERENCED_EVIDENCE",
            "question_type": "clarification",
            "record_type": "candidate_question",
            "source_revision_id": evidence["source_revision_id"],
            "subject": "REPLACE_SUBJECT",
        }
    )
    return "".join(
        json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records
    )


def build_package_manifest_payload(
    *,
    package_id: str,
    run_id: str,
    worker_name: str,
    worker_version: str,
    status: str,
    package_path: str,
    source_manifest_path: str,
    created_at: str,
    files: dict[str, dict[str, str]],
    package_hash: str,
    source_revision_count: int,
    chunk_count: int,
    fragment_count: int,
) -> dict[str, Any]:
    return {
        "chunk_count": chunk_count,
        "created_at": created_at,
        "files": files,
        "fragment_count": fragment_count,
        "package_hash": package_hash,
        "package_id": package_id,
        "package_path": package_path,
        "run_id": run_id,
        "source_manifest_path": source_manifest_path,
        "source_revision_count": source_revision_count,
        "stale_check": {
            "is_stale": False,
            "reason": None,
        },
        "status": status,
        "worker_name": worker_name,
        "worker_version": worker_version,
    }


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def compute_package_hash(files: dict[str, dict[str, str]]) -> str:
    payload = {
        "files": [
            {"label": label, "path": value["path"], "sha256": value["sha256"]}
            for label, value in sorted(files.items())
        ]
    }
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def compute_package_hash_from_manifest(package_manifest: dict[str, Any]) -> str:
    files = package_manifest.get("files")
    if not isinstance(files, dict):
        raise AiPackageError("Package manifest files must be an object.")
    normalized: dict[str, dict[str, str]] = {}
    for label, value in files.items():
        if not isinstance(label, str) or not isinstance(value, dict):
            raise AiPackageError("Package manifest files are invalid.")
        path = value.get("path")
        sha256 = value.get("sha256")
        if not isinstance(path, str) or not isinstance(sha256, str):
            raise AiPackageError("Package manifest file entry is invalid.")
        normalized[label] = {"path": path, "sha256": sha256}
    return compute_package_hash(normalized)


def _load_source_revisions(
    connection: sqlite3.Connection,
    *,
    revision_ids: tuple[str, ...],
    include_chunks: bool,
    include_fragments: bool,
) -> list[dict[str, Any]]:
    requested = tuple(sorted(dict.fromkeys(revision_ids)))
    if requested:
        placeholders = ",".join("?" for _ in requested)
        rows = connection.execute(
            f"""
            SELECT
                sr.source_revision_id,
                sr.source_id,
                sr.content_hash,
                sr.file_path,
                sr.status AS revision_status,
                s.current_revision_id,
                s.source_type,
                s.authority_level
            FROM source_revisions AS sr
            JOIN sources AS s
                ON s.source_id = sr.source_id
            WHERE sr.source_revision_id IN ({placeholders})
              AND sr.status = 'active'
              AND s.status = 'active'
            ORDER BY sr.source_revision_id
            """,
            requested,
        ).fetchall()
        found = {row["source_revision_id"] for row in rows}
        missing = [revision_id for revision_id in requested if revision_id not in found]
        if missing:
            raise AiPackageError(
                "Source revision is not active or was not found: "
                + ", ".join(missing)
                + "."
            )
        return [_revision_row_to_manifest(row) for row in rows]

    rows = connection.execute(
        """
        SELECT
            sr.source_revision_id,
            sr.source_id,
            sr.content_hash,
            sr.file_path,
            sr.status AS revision_status,
            s.current_revision_id,
            s.source_type,
            s.authority_level
        FROM source_revisions AS sr
        JOIN sources AS s
            ON s.source_id = sr.source_id
        WHERE sr.status = 'active'
          AND s.status = 'active'
          AND (
            (? = 1 AND EXISTS (
                SELECT 1
                FROM chunks AS c
                WHERE c.source_revision_id = sr.source_revision_id
                  AND c.status = 'active'
            ))
            OR (? = 1 AND EXISTS (
                SELECT 1
                FROM source_fragments AS f
                WHERE f.source_revision_id = sr.source_revision_id
                  AND f.status = 'active'
            ))
          )
        ORDER BY sr.source_revision_id
        """,
        (1 if include_chunks else 0, 1 if include_fragments else 0),
    ).fetchall()
    return [_revision_row_to_manifest(row) for row in rows]


def _revision_row_to_manifest(row: sqlite3.Row) -> dict[str, Any]:
    file_path = _manifest_relative_path(row["file_path"], "source revision file_path")
    return {
        "authority_level": row["authority_level"],
        "content_hash": row["content_hash"],
        "current_revision_id": row["current_revision_id"],
        "file_path": file_path,
        "revision_status": row["revision_status"],
        "source_id": row["source_id"],
        "source_revision_id": row["source_revision_id"],
        "source_type": row["source_type"],
    }


def _load_active_chunks(
    connection: sqlite3.Connection,
    revision_ids: tuple[str, ...],
) -> list[dict[str, Any]]:
    if not revision_ids:
        return []
    placeholders = ",".join("?" for _ in revision_ids)
    rows = connection.execute(
        f"""
        SELECT
            chunk_id,
            source_revision_id,
            sequence,
            text,
            text_hash,
            status
        FROM chunks
        WHERE status = 'active'
          AND source_revision_id IN ({placeholders})
        ORDER BY source_revision_id, sequence, chunk_id
        """,
        revision_ids,
    ).fetchall()
    return [
        {
            "chunk_id": row["chunk_id"],
            "sequence": int(row["sequence"]),
            "source_revision_id": row["source_revision_id"],
            "status": row["status"],
            "text": _normalize_newlines(row["text"]),
            "text_hash": row["text_hash"],
        }
        for row in rows
    ]


def _load_active_fragments(
    connection: sqlite3.Connection,
    revision_ids: tuple[str, ...],
) -> list[dict[str, Any]]:
    if not revision_ids:
        return []
    placeholders = ",".join("?" for _ in revision_ids)
    rows = connection.execute(
        f"""
        SELECT
            fragment_id,
            source_revision_id,
            fragment_type,
            sequence,
            path_or_selector,
            text,
            text_hash,
            status
        FROM source_fragments
        WHERE status = 'active'
          AND source_revision_id IN ({placeholders})
        ORDER BY source_revision_id, sequence, fragment_id
        """,
        revision_ids,
    ).fetchall()
    return [
        {
            "fragment_id": row["fragment_id"],
            "fragment_type": row["fragment_type"],
            "path_or_selector": row["path_or_selector"],
            "sequence": int(row["sequence"]),
            "source_revision_id": row["source_revision_id"],
            "status": row["status"],
            "text": _normalize_newlines(row["text"]),
            "text_hash": row["text_hash"],
        }
        for row in rows
    ]


def _validate_source_manifest(
    payload: dict[str, Any],
    *,
    expected_package_id: str,
    expected_package_path: str,
    expected_source_revision_count: int,
    expected_chunk_count: int,
    expected_fragment_count: int,
) -> None:
    if payload.get("package_id") != expected_package_id:
        raise AiPackageError("source_manifest package_id is incoherent.")
    if payload.get("package_path") != expected_package_path:
        raise AiPackageError("source_manifest package_path is incoherent.")
    counts = payload.get("counts")
    if not isinstance(counts, dict):
        raise AiPackageError("source_manifest counts are missing.")
    expected = {
        "chunks": expected_chunk_count,
        "fragments": expected_fragment_count,
        "source_revisions": expected_source_revision_count,
    }
    for key, value in expected.items():
        if counts.get(key) != value:
            raise AiPackageError(f"source_manifest count is incoherent: {key}.")


def _validate_package_manifest(
    payload: dict[str, Any],
    *,
    expected_package_id: str,
    expected_run_id: str,
    expected_package_path: str,
    expected_source_manifest_path: str,
    expected_package_hash: str,
    expected_source_revision_count: int,
    expected_chunk_count: int,
    expected_fragment_count: int,
) -> None:
    checks = {
        "chunk_count": expected_chunk_count,
        "fragment_count": expected_fragment_count,
        "package_hash": expected_package_hash,
        "package_id": expected_package_id,
        "package_path": expected_package_path,
        "run_id": expected_run_id,
        "source_manifest_path": expected_source_manifest_path,
        "source_revision_count": expected_source_revision_count,
        "status": AI_PACKAGE_STATUS_WAITING,
        "worker_name": WORKER_NAME,
    }
    for key, expected in checks.items():
        if payload.get(key) != expected:
            raise AiPackageError(f"package_manifest field is incoherent: {key}.")
    stale_check = payload.get("stale_check")
    if not isinstance(stale_check, dict) or stale_check.get("is_stale") is not False:
        raise AiPackageError("package_manifest stale_check must start as not stale.")


def _validate_manifest_file_hashes(
    workspace_dir: Path,
    package_manifest: dict[str, Any],
    expected_paths: dict[str, str],
) -> None:
    files = package_manifest.get("files")
    if not isinstance(files, dict):
        raise AiPackageError("package_manifest files are missing.")
    for label, expected_path in sorted(expected_paths.items()):
        entry = files.get(label)
        if not isinstance(entry, dict):
            raise AiPackageError(f"package_manifest file entry is missing: {label}.")
        if entry.get("path") != expected_path:
            raise AiPackageError(f"package_manifest file path is incoherent: {label}.")
        expected_hash = entry.get("sha256")
        if not isinstance(expected_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
            raise AiPackageError(f"package_manifest file hash is invalid: {label}.")
        actual_hash = file_hash(_resolve_workspace_path(workspace_dir, expected_path))
        if actual_hash != expected_hash:
            raise AiPackageError(f"package_manifest file hash mismatch: {label}.")


def _read_json_file(workspace_dir: Path, relative_path: str) -> dict[str, Any]:
    path = _resolve_workspace_path(workspace_dir, relative_path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AiPackageError(f"Package JSON file is invalid: {relative_path}.") from exc
    if not isinstance(payload, dict):
        raise AiPackageError(f"Package JSON file must be an object: {relative_path}.")
    return payload


def _check_source_manifest_stale(
    connection: sqlite3.Connection,
    source_manifest: dict[str, Any],
) -> tuple[str, dict[str, Any]] | None:
    source_revisions = source_manifest.get("source_revisions", [])
    if not isinstance(source_revisions, list):
        return ("source_manifest_invalid", {"field": "source_revisions"})
    for revision in source_revisions:
        if not isinstance(revision, dict):
            return ("source_manifest_invalid", {"field": "source_revisions"})
        revision_id = revision.get("source_revision_id")
        row = connection.execute(
            """
            SELECT
                sr.source_revision_id,
                sr.status,
                sr.content_hash,
                s.current_revision_id
            FROM source_revisions AS sr
            JOIN sources AS s
                ON s.source_id = sr.source_id
            WHERE sr.source_revision_id = ?
            """,
            (revision_id,),
        ).fetchone()
        if row is None:
            return ("source_revision_missing", {"source_revision_id": revision_id})
        if row["current_revision_id"] != revision_id:
            return ("source_revision_not_current", {"source_revision_id": revision_id})
        if row["status"] != "active":
            return ("source_revision_not_active", {"source_revision_id": revision_id})
        if row["content_hash"] != revision.get("content_hash"):
            return ("source_revision_hash_changed", {"source_revision_id": revision_id})

    chunks = source_manifest.get("chunks", [])
    if not isinstance(chunks, list):
        return ("source_manifest_invalid", {"field": "chunks"})
    for chunk in chunks:
        if not isinstance(chunk, dict):
            return ("source_manifest_invalid", {"field": "chunks"})
        chunk_id = chunk.get("chunk_id")
        row = connection.execute(
            """
            SELECT chunk_id, status, text_hash
            FROM chunks
            WHERE chunk_id = ?
            """,
            (chunk_id,),
        ).fetchone()
        if row is None:
            return ("chunk_missing", {"chunk_id": chunk_id})
        if row["status"] != "active":
            return ("chunk_not_active", {"chunk_id": chunk_id})
        if row["text_hash"] != chunk.get("text_hash"):
            return ("chunk_hash_changed", {"chunk_id": chunk_id})

    fragments = source_manifest.get("fragments", [])
    if not isinstance(fragments, list):
        return ("source_manifest_invalid", {"field": "fragments"})
    for fragment in fragments:
        if not isinstance(fragment, dict):
            return ("source_manifest_invalid", {"field": "fragments"})
        fragment_id = fragment.get("fragment_id")
        row = connection.execute(
            """
            SELECT fragment_id, status, text_hash
            FROM source_fragments
            WHERE fragment_id = ?
            """,
            (fragment_id,),
        ).fetchone()
        if row is None:
            return ("fragment_missing", {"fragment_id": fragment_id})
        if row["status"] != "active":
            return ("fragment_not_active", {"fragment_id": fragment_id})
        if row["text_hash"] != fragment.get("text_hash"):
            return ("fragment_hash_changed", {"fragment_id": fragment_id})
    return None


def _required_relative_path(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise AiPackageError(f"Worker output field is missing: {key}.")
    return _manifest_relative_path(value, key)


def _required_sha256(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise AiPackageError(f"Worker output hash is invalid: {key}.")
    return value


def _manifest_relative_path(value: str, label: str) -> str:
    path = Path(value)
    if not value or "\\" in value or path.is_absolute() or ".." in path.parts:
        raise AiPackageError(f"Path is not workspace-relative: {label}.")
    return path.as_posix()


def _resolve_workspace_path(workspace_dir: Path, relative_path: str) -> Path:
    _manifest_relative_path(relative_path, relative_path)
    resolved = (workspace_dir / relative_path).resolve()
    try:
        resolved.relative_to(workspace_dir.resolve())
    except ValueError as exc:
        raise DatabaseConfigurationError(
            f"Path escapes the workspace: {relative_path}"
        ) from exc
    return resolved


def _option_bool(raw_options: dict[str, Any], key: str, default: bool) -> bool:
    return _as_bool(raw_options.get(key, default))


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
    raise AiPackageError(f"Expected boolean AI package option, got: {value!r}.")


def _as_positive_int(value: Any) -> int:
    if isinstance(value, bool):
        raise AiPackageError("max_evidence_chars must be a positive integer.")
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise AiPackageError("max_evidence_chars must be a positive integer.") from exc
    if number < 1:
        raise AiPackageError("max_evidence_chars must be a positive integer.")
    return number


def _normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _evidence_text(text: str, max_evidence_chars: int) -> tuple[str, bool]:
    normalized = _normalize_newlines(text)
    if len(normalized) <= max_evidence_chars:
        return normalized, False
    return normalized[:max_evidence_chars], True


def _fenced_text(text: str) -> str:
    fence = "````" if "```" in text else "```"
    suffix = "" if text.endswith("\n") else "\n"
    return f"{fence}text\n{text}{suffix}{fence}"


def _sample_evidence_text(text: str) -> str:
    normalized = _normalize_newlines(text)
    for line in normalized.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped[:240]
    return normalized.strip()[:240]


def _format_bool(value: bool) -> str:
    return "true" if value else "false"
