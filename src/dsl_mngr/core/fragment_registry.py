from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dsl_mngr.core.database import DatabaseConfigurationError, resolve_workspace_path
from dsl_mngr.core.ddl_parser import (
    canonical_metadata_json,
    fragments_jsonl_content,
    fragments_jsonl_hash,
    sha256_text,
)
from dsl_mngr.core.runs import canonical_json, next_id


class FragmentRegistryError(RuntimeError):
    """Raised when source fragments cannot be persisted safely."""


@dataclass(frozen=True)
class FragmentIdSeed:
    fragment_id_by_sequence: dict[int, str]
    next_fragment_number: int


@dataclass(frozen=True)
class PersistedFragments:
    fragment_count: int
    fragments_hash: str
    fragments_jsonl_path: str
    ddl_report_path: str


ALLOWED_FRAGMENT_TYPES = {"ddl_table", "ddl_column", "ddl_constraint"}

REQUIRED_METADATA_KEYS = {
    "dialect",
    "object_type",
    "parser",
    "parser_version",
    "source_hash",
    "statement_kind",
}


def load_fragment_id_seed(connection: sqlite3.Connection, source_revision_id: str) -> FragmentIdSeed:
    rows = connection.execute(
        """
        SELECT fragment_id, sequence, status
        FROM source_fragments
        WHERE source_revision_id = ?
        ORDER BY
            sequence,
            CASE status WHEN 'active' THEN 0 ELSE 1 END,
            fragment_id
        """,
        (source_revision_id,),
    ).fetchall()
    by_sequence: dict[int, str] = {}
    for row in rows:
        by_sequence.setdefault(int(row["sequence"]), row["fragment_id"])

    next_fragment_id = next_id(connection, "source_fragments", "fragment_id", "FRAG")
    next_number = int(next_fragment_id.rsplit("_", 1)[1])
    return FragmentIdSeed(fragment_id_by_sequence=by_sequence, next_fragment_number=next_number)


def persist_worker_fragments(
    connection: sqlite3.Connection,
    *,
    workspace_dir: Path,
    output: dict[str, Any],
    expected_source_id: str,
    expected_source_revision_id: str,
    expected_source_hash: str,
    expected_input_path: str,
    timestamp: str,
) -> PersistedFragments:
    if output.get("source_id") != expected_source_id:
        raise FragmentRegistryError("Worker output source_id is incoherent.")
    if output.get("source_revision_id") != expected_source_revision_id:
        raise FragmentRegistryError("Worker output source_revision_id is incoherent.")
    if output.get("source_hash") != expected_source_hash:
        raise FragmentRegistryError("Worker output source_hash is incoherent.")
    if output.get("input_path") != expected_input_path:
        raise FragmentRegistryError("Worker output input_path is incoherent.")

    fragments_jsonl_path = _required_output_path(output, "fragments_jsonl_path")
    ddl_report_path = _required_output_path(output, "ddl_report_path")
    fragments_path = _resolve_relative_file(workspace_dir, fragments_jsonl_path)
    report_path = _resolve_relative_file(workspace_dir, ddl_report_path)
    records = _required_records(output)

    actual_hash = fragments_jsonl_hash(records)
    if output.get("fragments_hash") != actual_hash:
        raise FragmentRegistryError("Worker output fragments_hash does not match canonical fragments.")
    if output.get("fragment_count") != len(records):
        raise FragmentRegistryError("Worker output fragment_count does not match fragments length.")

    existing_by_sequence = load_fragment_id_seed(
        connection,
        expected_source_revision_id,
    ).fragment_id_by_sequence
    produced_sequences: list[int] = []
    for expected_sequence, record in enumerate(records, start=1):
        fragment_id = _validate_record(
            record,
            expected_sequence=expected_sequence,
            expected_source_revision_id=expected_source_revision_id,
            expected_source_hash=expected_source_hash,
        )
        reused_fragment_id = existing_by_sequence.get(expected_sequence)
        if reused_fragment_id is not None and reused_fragment_id != fragment_id:
            raise FragmentRegistryError(
                f"Fragment sequence {expected_sequence} must reuse {reused_fragment_id}, got {fragment_id}."
            )
        _upsert_fragment(connection, record, timestamp=timestamp)
        produced_sequences.append(expected_sequence)

    if produced_sequences:
        placeholders = ",".join("?" for _ in produced_sequences)
        connection.execute(
            f"""
            UPDATE source_fragments
            SET status = 'stale'
            WHERE source_revision_id = ?
              AND status = 'active'
              AND sequence NOT IN ({placeholders})
            """,
            (expected_source_revision_id, *produced_sequences),
        )

    _classify_unknown_source_as_ddl(connection, expected_source_id, timestamp)

    fragments_path.parent.mkdir(parents=True, exist_ok=True)
    fragments_path.write_text(fragments_jsonl_content(records), encoding="utf-8", newline="\n")
    _write_ddl_report(
        report_path,
        output=output,
        records=records,
        fragments_hash=actual_hash,
    )
    return PersistedFragments(
        fragment_count=len(records),
        fragments_hash=actual_hash,
        fragments_jsonl_path=fragments_jsonl_path,
        ddl_report_path=ddl_report_path,
    )


def _required_records(output: dict[str, Any]) -> list[dict[str, Any]]:
    value = output.get("fragments")
    if not isinstance(value, list) or not value:
        raise FragmentRegistryError("Worker output fragments must be a non-empty list.")
    if not all(isinstance(record, dict) for record in value):
        raise FragmentRegistryError("Worker output fragments must contain JSON objects.")
    return value


def _validate_record(
    record: dict[str, Any],
    *,
    expected_sequence: int,
    expected_source_revision_id: str,
    expected_source_hash: str,
) -> str:
    fragment_id = record.get("fragment_id")
    if not isinstance(fragment_id, str) or not re.fullmatch(r"FRAG_[0-9]{6}", fragment_id):
        raise FragmentRegistryError("Fragment record has invalid fragment_id.")
    if record.get("source_revision_id") != expected_source_revision_id:
        raise FragmentRegistryError("Fragment record source_revision_id is incoherent.")
    if record.get("sequence") != expected_sequence:
        raise FragmentRegistryError("Fragment sequences must be consecutive and start at 1.")
    if record.get("status") != "active":
        raise FragmentRegistryError("Fragment record status must be active.")
    if record.get("fragment_type") not in ALLOWED_FRAGMENT_TYPES:
        raise FragmentRegistryError("Fragment record has unsupported fragment_type.")

    path_or_selector = record.get("path_or_selector")
    if not isinstance(path_or_selector, str) or not path_or_selector.strip():
        raise FragmentRegistryError("Fragment path_or_selector must be non-empty.")
    if "\\" in path_or_selector:
        raise FragmentRegistryError("Fragment path_or_selector must use stable separators.")

    text = record.get("text")
    if not isinstance(text, str) or not text.strip():
        raise FragmentRegistryError("Fragment text must be non-empty.")
    if "\r" in text:
        raise FragmentRegistryError("Fragment text must use LF newlines only.")
    if record.get("text_hash") != sha256_text(text):
        raise FragmentRegistryError("Fragment text_hash does not match fragment text.")

    for key in ("line_start", "line_end"):
        value = record.get(key)
        if not isinstance(value, int) or value < 1:
            raise FragmentRegistryError(f"Fragment {key} must be a positive integer.")
    if record["line_start"] > record["line_end"]:
        raise FragmentRegistryError("Fragment line_start must not exceed line_end.")

    for key in ("char_start", "char_end"):
        value = record.get(key)
        if not isinstance(value, int) or value < 0:
            raise FragmentRegistryError(f"Fragment {key} must be a non-negative integer.")
    if record["char_start"] >= record["char_end"]:
        raise FragmentRegistryError("Fragment char_start must be lower than char_end.")

    metadata = record.get("metadata")
    if not isinstance(metadata, dict):
        raise FragmentRegistryError("Fragment metadata must be an object.")
    missing = sorted(REQUIRED_METADATA_KEYS - set(metadata))
    if missing:
        raise FragmentRegistryError(f"Fragment metadata is missing: {', '.join(missing)}.")
    if metadata.get("source_hash") != expected_source_hash:
        raise FragmentRegistryError("Fragment metadata source_hash is incoherent.")
    if metadata.get("parser") != "parse_ddl":
        raise FragmentRegistryError("Fragment metadata parser is incoherent.")
    if metadata.get("dialect") != "generic_sql":
        raise FragmentRegistryError("Fragment metadata dialect is incoherent.")

    object_type = metadata.get("object_type")
    if object_type == "table" and not isinstance(metadata.get("table_name"), str):
        raise FragmentRegistryError("Table fragment metadata is missing table_name.")
    if object_type == "column":
        for key in ("table_name", "column_name", "data_type", "nullable"):
            if key not in metadata:
                raise FragmentRegistryError(f"Column fragment metadata is missing {key}.")
    if object_type in {"constraint", "index"}:
        for key in ("table_name", "constraint_kind", "columns"):
            if key not in metadata:
                raise FragmentRegistryError(f"Constraint fragment metadata is missing {key}.")
        if not isinstance(metadata.get("columns"), list):
            raise FragmentRegistryError("Constraint fragment metadata columns must be a list.")
    return fragment_id


def _upsert_fragment(
    connection: sqlite3.Connection,
    record: dict[str, Any],
    *,
    timestamp: str,
) -> None:
    fragment_id = record["fragment_id"]
    source_revision_id = record["source_revision_id"]
    sequence = int(record["sequence"])
    owner = connection.execute(
        """
        SELECT fragment_id, source_revision_id, sequence
        FROM source_fragments
        WHERE fragment_id = ?
        """,
        (fragment_id,),
    ).fetchone()
    if owner is not None and (
        owner["source_revision_id"] != source_revision_id or int(owner["sequence"]) != sequence
    ):
        raise FragmentRegistryError(
            f"Fragment id {fragment_id} already belongs to another revision or sequence."
        )

    metadata_json = canonical_metadata_json(record["metadata"])
    values = (
        fragment_id,
        source_revision_id,
        record["fragment_type"],
        sequence,
        record["path_or_selector"],
        record["line_start"],
        record["line_end"],
        record["char_start"],
        record["char_end"],
        record["text"],
        record["text_hash"],
        metadata_json,
        "active",
    )
    if owner is None:
        connection.execute(
            """
            INSERT INTO source_fragments (
                fragment_id,
                source_revision_id,
                fragment_type,
                sequence,
                path_or_selector,
                line_start,
                line_end,
                char_start,
                char_end,
                text,
                text_hash,
                metadata_json,
                status,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (*values, timestamp),
        )
        return

    connection.execute(
        """
        UPDATE source_fragments
        SET fragment_type = ?,
            path_or_selector = ?,
            line_start = ?,
            line_end = ?,
            char_start = ?,
            char_end = ?,
            text = ?,
            text_hash = ?,
            metadata_json = ?,
            status = ?
        WHERE fragment_id = ?
        """,
        (
            record["fragment_type"],
            record["path_or_selector"],
            record["line_start"],
            record["line_end"],
            record["char_start"],
            record["char_end"],
            record["text"],
            record["text_hash"],
            metadata_json,
            "active",
            fragment_id,
        ),
    )


def _classify_unknown_source_as_ddl(
    connection: sqlite3.Connection,
    source_id: str,
    timestamp: str,
) -> None:
    row = connection.execute(
        """
        SELECT source_type
        FROM sources
        WHERE source_id = ?
        """,
        (source_id,),
    ).fetchone()
    if row is None:
        raise FragmentRegistryError(f"Source not found: {source_id}.")
    if row["source_type"] != "unknown":
        return
    connection.execute(
        """
        UPDATE sources
        SET source_type = ?,
            source_subtype = ?,
            authority_level = ?,
            updated_at = ?
        WHERE source_id = ?
        """,
        ("ddl", "mixed_ddl", "technical_structure", timestamp, source_id),
    )


def _write_ddl_report(
    path: Path,
    *,
    output: dict[str, Any],
    records: list[dict[str, Any]],
    fragments_hash: str,
) -> None:
    report = {
        "column_count": output["column_count"],
        "ddl_objects": output["ddl_objects"],
        "dialect": output["dialect"],
        "foreign_key_count": output["foreign_key_count"],
        "fragment_count": len(records),
        "fragments": [
            {
                "fragment_id": record["fragment_id"],
                "fragment_type": record["fragment_type"],
                "path_or_selector": record["path_or_selector"],
                "sequence": record["sequence"],
                "status": record["status"],
                "text_hash": record["text_hash"],
            }
            for record in records
        ],
        "fragments_hash": fragments_hash,
        "input": {
            "input_path": output["input_path"],
            "source_hash": output["source_hash"],
            "source_id": output["source_id"],
            "source_revision_id": output["source_revision_id"],
        },
        "outputs": {
            "ddl_report_path": output["ddl_report_path"],
            "fragments_jsonl_path": output["fragments_jsonl_path"],
        },
        "profile": output["profile"],
        "resolved_config": {
            "ddl": output.get("ddl_options", {}),
            "worker": output.get("worker_config", {}),
        },
        "run_id": output["run_id"],
        "status": "completed",
        "table_count": output["table_count"],
        "warnings": output.get("warnings", []),
        "worker_name": output["worker_name"],
        "worker_version": output["worker_version"],
    }
    path.write_text(canonical_json(report), encoding="utf-8", newline="\n")


def _required_output_path(output: dict[str, Any], key: str) -> str:
    value = output.get(key)
    if not isinstance(value, str) or not value:
        raise FragmentRegistryError(f"Worker output field is missing: {key}.")
    _validate_relative_path_text(value, key)
    return value


def _validate_relative_path_text(value: Any, key: str) -> None:
    if not isinstance(value, str) or not value:
        raise FragmentRegistryError(f"Path field is invalid: {key}.")
    path = Path(value)
    if "\\" in value or path.is_absolute() or ".." in path.parts:
        raise FragmentRegistryError(f"Path is not workspace-relative: {key}.")


def _resolve_relative_file(workspace_dir: Path, relative_path: str) -> Path:
    try:
        return resolve_workspace_path(workspace_dir, relative_path)
    except DatabaseConfigurationError as exc:
        raise FragmentRegistryError(f"Output path escapes the workspace: {relative_path}.") from exc
