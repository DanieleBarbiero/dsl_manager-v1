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


DDL_FRAGMENT_TYPES = {"ddl_table", "ddl_column", "ddl_constraint"}
XML_FORM_FRAGMENT_TYPES = {"xml_form", "xml_field", "xml_button"}
ALLOWED_FRAGMENT_TYPES = DDL_FRAGMENT_TYPES | XML_FORM_FRAGMENT_TYPES

COMMON_REQUIRED_METADATA_KEYS = {
    "object_type",
    "parser",
    "parser_version",
    "source_hash",
}

DDL_REQUIRED_METADATA_KEYS = {
    "dialect",
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

    worker_name = _required_worker_name(output)
    fragments_jsonl_path = _required_output_path(output, "fragments_jsonl_path")
    report_path_key = _report_path_key(worker_name)
    report_path_value = _required_output_path(output, report_path_key)
    fragments_path = _resolve_relative_file(workspace_dir, fragments_jsonl_path)
    report_path = _resolve_relative_file(workspace_dir, report_path_value)
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

    _classify_unknown_source(connection, expected_source_id, worker_name, timestamp)

    fragments_path.parent.mkdir(parents=True, exist_ok=True)
    fragments_path.write_text(fragments_jsonl_content(records), encoding="utf-8", newline="\n")
    if worker_name == "parse_ddl":
        _write_ddl_report(
            report_path,
            output=output,
            records=records,
            fragments_hash=actual_hash,
        )
    elif worker_name == "parse_xml_form":
        _write_xml_form_report(
            report_path,
            output=output,
            records=records,
            fragments_hash=actual_hash,
        )
    return PersistedFragments(
        fragment_count=len(records),
        fragments_hash=actual_hash,
        fragments_jsonl_path=fragments_jsonl_path,
        ddl_report_path=report_path_value,
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
    missing = sorted(COMMON_REQUIRED_METADATA_KEYS - set(metadata))
    if missing:
        raise FragmentRegistryError(f"Fragment metadata is missing: {', '.join(missing)}.")
    if metadata.get("source_hash") != expected_source_hash:
        raise FragmentRegistryError("Fragment metadata source_hash is incoherent.")
    if not isinstance(metadata.get("parser_version"), str) or not metadata["parser_version"]:
        raise FragmentRegistryError("Fragment metadata parser_version is invalid.")

    parser = metadata.get("parser")
    if parser == "parse_ddl":
        _validate_ddl_metadata(record, metadata)
    elif parser == "parse_xml_form":
        _validate_xml_form_metadata(record, metadata)
    else:
        raise FragmentRegistryError("Fragment metadata parser is incoherent.")
    return fragment_id


def _validate_ddl_metadata(record: dict[str, Any], metadata: dict[str, Any]) -> None:
    if record.get("fragment_type") not in DDL_FRAGMENT_TYPES:
        raise FragmentRegistryError("DDL fragment has unsupported fragment_type.")
    missing = sorted(DDL_REQUIRED_METADATA_KEYS - set(metadata))
    if missing:
        raise FragmentRegistryError(f"DDL fragment metadata is missing: {', '.join(missing)}.")
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


def _validate_xml_form_metadata(record: dict[str, Any], metadata: dict[str, Any]) -> None:
    fragment_type = record.get("fragment_type")
    if fragment_type not in XML_FORM_FRAGMENT_TYPES:
        raise FragmentRegistryError("XML form fragment has unsupported fragment_type.")

    object_type = metadata.get("object_type")
    if fragment_type == "xml_form":
        if object_type != "form":
            raise FragmentRegistryError("xml_form fragment metadata object_type must be form.")
        for key in ("form_name", "table_references", "edit_relations"):
            if key not in metadata:
                raise FragmentRegistryError(f"Form fragment metadata is missing {key}.")
        if not isinstance(metadata.get("form_name"), str) or not metadata["form_name"]:
            raise FragmentRegistryError("Form fragment metadata form_name is invalid.")
        if not isinstance(metadata.get("table_references"), list):
            raise FragmentRegistryError("Form fragment metadata table_references must be a list.")
        if not isinstance(metadata.get("edit_relations"), list):
            raise FragmentRegistryError("Form fragment metadata edit_relations must be a list.")
        return

    if fragment_type == "xml_field":
        if object_type != "field":
            raise FragmentRegistryError("xml_field fragment metadata object_type must be field.")
        for key in ("form_name", "field_name", "required"):
            if key not in metadata:
                raise FragmentRegistryError(f"Field fragment metadata is missing {key}.")
        if not isinstance(metadata.get("form_name"), str) or not metadata["form_name"]:
            raise FragmentRegistryError("Field fragment metadata form_name is invalid.")
        if not isinstance(metadata.get("field_name"), str) or not metadata["field_name"]:
            raise FragmentRegistryError("Field fragment metadata field_name is invalid.")
        if not isinstance(metadata.get("required"), bool):
            raise FragmentRegistryError("Field fragment metadata required must be a boolean.")
        has_table = isinstance(metadata.get("table_name"), str) and bool(metadata.get("table_name"))
        has_column = isinstance(metadata.get("column_name"), str) and bool(metadata.get("column_name"))
        if has_table and has_column and metadata.get("mapping_type") != "form_field_to_column":
            raise FragmentRegistryError("Field mapping metadata is missing mapping_type.")
        return

    if fragment_type == "xml_button":
        if object_type != "button":
            raise FragmentRegistryError("xml_button fragment metadata object_type must be button.")
        for key in ("action_kind", "button_name", "form_name"):
            if key not in metadata:
                raise FragmentRegistryError(f"Button fragment metadata is missing {key}.")
        if metadata.get("action_kind") not in {"save", "confirm", "delete", "cancel", "unknown"}:
            raise FragmentRegistryError("Button fragment metadata action_kind is invalid.")
        if not isinstance(metadata.get("button_name"), str) or not metadata["button_name"]:
            raise FragmentRegistryError("Button fragment metadata button_name is invalid.")
        if not isinstance(metadata.get("form_name"), str) or not metadata["form_name"]:
            raise FragmentRegistryError("Button fragment metadata form_name is invalid.")
        return

    raise FragmentRegistryError("XML form fragment metadata is incoherent.")


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


def _classify_unknown_source(
    connection: sqlite3.Connection,
    source_id: str,
    worker_name: str,
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
    if worker_name == "parse_ddl":
        source_type = "ddl"
        source_subtype = "mixed_ddl"
    elif worker_name == "parse_xml_form":
        source_type = "xml_form"
        source_subtype = "form"
    else:
        raise FragmentRegistryError(f"Unsupported fragment worker: {worker_name}.")
    connection.execute(
        """
        UPDATE sources
        SET source_type = ?,
            source_subtype = ?,
            authority_level = ?,
            updated_at = ?
        WHERE source_id = ?
        """,
        (source_type, source_subtype, "technical_structure", timestamp, source_id),
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


def _write_xml_form_report(
    path: Path,
    *,
    output: dict[str, Any],
    records: list[dict[str, Any]],
    fragments_hash: str,
) -> None:
    report = {
        "button_count": output["button_count"],
        "edit_relation_count": output["edit_relation_count"],
        "edit_relations": output["edit_relations"],
        "field_count": output["field_count"],
        "form_count": output["form_count"],
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
            "fragments_jsonl_path": output["fragments_jsonl_path"],
            "xml_form_report_path": output["xml_form_report_path"],
        },
        "parser": output["parser"],
        "profile": output["profile"],
        "required_field_count": output["required_field_count"],
        "resolved_config": {
            "worker": output.get("worker_config", {}),
            "xml_form": output.get("xml_form_options", {}),
        },
        "run_id": output["run_id"],
        "status": "completed",
        "table_column_references": output.get("table_column_references", []),
        "table_reference_count": output["table_reference_count"],
        "warnings": output.get("warnings", []),
        "worker_name": output["worker_name"],
        "worker_version": output["worker_version"],
        "xml_form_objects": output["xml_form_objects"],
    }
    path.write_text(canonical_json(report), encoding="utf-8", newline="\n")


def _required_worker_name(output: dict[str, Any]) -> str:
    value = output.get("worker_name")
    if value not in {"parse_ddl", "parse_xml_form"}:
        raise FragmentRegistryError("Worker output worker_name is unsupported.")
    return value


def _report_path_key(worker_name: str) -> str:
    if worker_name == "parse_ddl":
        return "ddl_report_path"
    if worker_name == "parse_xml_form":
        return "xml_form_report_path"
    raise FragmentRegistryError(f"Unsupported fragment worker: {worker_name}.")


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
