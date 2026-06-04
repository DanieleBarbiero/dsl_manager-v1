from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dsl_mngr.core.chunking import (
    canonical_metadata_json,
    chunks_jsonl_content,
    chunks_jsonl_hash,
    sha256_text,
)
from dsl_mngr.core.database import DatabaseConfigurationError, resolve_workspace_path
from dsl_mngr.core.runs import canonical_json, next_id


class ChunkRegistryError(RuntimeError):
    """Raised when chunk records cannot be persisted safely."""


@dataclass(frozen=True)
class ChunkIdSeed:
    chunk_id_by_sequence: dict[int, str]
    next_chunk_number: int


@dataclass(frozen=True)
class PersistedChunks:
    chunk_count: int
    chunks_hash: str
    chunks_jsonl_path: str
    chunk_report_path: str


REQUIRED_METADATA_KEYS = {
    "chunker",
    "chunker_version",
    "end_char",
    "heading_path",
    "normalized_hash",
    "normalized_json_path",
    "normalized_markdown_path",
    "source_text_kind",
    "start_char",
    "strategy",
}


def load_chunk_id_seed(connection: sqlite3.Connection, source_revision_id: str) -> ChunkIdSeed:
    rows = connection.execute(
        """
        SELECT chunk_id, sequence, status
        FROM chunks
        WHERE source_revision_id = ?
        ORDER BY
            sequence,
            CASE status WHEN 'active' THEN 0 ELSE 1 END,
            chunk_id
        """,
        (source_revision_id,),
    ).fetchall()
    by_sequence: dict[int, str] = {}
    for row in rows:
        by_sequence.setdefault(int(row["sequence"]), row["chunk_id"])

    next_chunk_id = next_id(connection, "chunks", "chunk_id", "CHK")
    next_number = int(next_chunk_id.rsplit("_", 1)[1])
    return ChunkIdSeed(chunk_id_by_sequence=by_sequence, next_chunk_number=next_number)


def persist_worker_chunks(
    connection: sqlite3.Connection,
    *,
    workspace_dir: Path,
    output: dict[str, Any],
    expected_source_id: str,
    expected_source_revision_id: str,
    expected_normalized_hash: str,
    expected_normalized_markdown_path: str,
    expected_normalized_json_path: str,
    timestamp: str,
) -> PersistedChunks:
    if output.get("source_id") != expected_source_id:
        raise ChunkRegistryError("Worker output source_id is incoherent.")
    if output.get("source_revision_id") != expected_source_revision_id:
        raise ChunkRegistryError("Worker output source_revision_id is incoherent.")
    if output.get("normalized_hash") != expected_normalized_hash:
        raise ChunkRegistryError("Worker output normalized_hash is incoherent.")
    if output.get("normalized_markdown_path") != expected_normalized_markdown_path:
        raise ChunkRegistryError("Worker output normalized_markdown_path is incoherent.")
    if output.get("normalized_json_path") != expected_normalized_json_path:
        raise ChunkRegistryError("Worker output normalized_json_path is incoherent.")

    chunks_jsonl_path = _required_output_path(output, "chunks_jsonl_path")
    chunk_report_path = _required_output_path(output, "chunk_report_path")
    chunks_path = _resolve_relative_file(workspace_dir, chunks_jsonl_path)
    report_path = _resolve_relative_file(workspace_dir, chunk_report_path)
    records = _required_records(output)

    content = chunks_jsonl_content(records)
    actual_hash = chunks_jsonl_hash(records)
    if output.get("chunks_hash") != actual_hash:
        raise ChunkRegistryError("Worker output chunks_hash does not match canonical chunks.")
    if output.get("chunk_count") != len(records):
        raise ChunkRegistryError("Worker output chunk_count does not match chunks length.")

    existing_by_sequence = load_chunk_id_seed(connection, expected_source_revision_id).chunk_id_by_sequence
    produced_sequences: list[int] = []
    for expected_sequence, record in enumerate(records, start=1):
        chunk_id = _validate_record(
            record,
            expected_sequence=expected_sequence,
            expected_source_revision_id=expected_source_revision_id,
            expected_normalized_hash=expected_normalized_hash,
            expected_normalized_markdown_path=expected_normalized_markdown_path,
            expected_normalized_json_path=expected_normalized_json_path,
        )
        reused_chunk_id = existing_by_sequence.get(expected_sequence)
        if reused_chunk_id is not None and reused_chunk_id != chunk_id:
            raise ChunkRegistryError(
                f"Chunk sequence {expected_sequence} must reuse {reused_chunk_id}, got {chunk_id}."
            )
        _upsert_chunk(connection, record, timestamp=timestamp)
        produced_sequences.append(expected_sequence)

    if produced_sequences:
        placeholders = ",".join("?" for _ in produced_sequences)
        connection.execute(
            f"""
            UPDATE chunks
            SET status = 'stale'
            WHERE source_revision_id = ?
              AND status = 'active'
              AND sequence NOT IN ({placeholders})
            """,
            (expected_source_revision_id, *produced_sequences),
        )

    chunks_path.parent.mkdir(parents=True, exist_ok=True)
    chunks_path.write_text(content, encoding="utf-8", newline="\n")
    _write_chunk_report(
        report_path,
        output=output,
        records=records,
        chunks_hash=actual_hash,
    )
    return PersistedChunks(
        chunk_count=len(records),
        chunks_hash=actual_hash,
        chunks_jsonl_path=chunks_jsonl_path,
        chunk_report_path=chunk_report_path,
    )


def _required_records(output: dict[str, Any]) -> list[dict[str, Any]]:
    value = output.get("chunks")
    if not isinstance(value, list) or not value:
        raise ChunkRegistryError("Worker output chunks must be a non-empty list.")
    if not all(isinstance(record, dict) for record in value):
        raise ChunkRegistryError("Worker output chunks must contain JSON objects.")
    return value


def _validate_record(
    record: dict[str, Any],
    *,
    expected_sequence: int,
    expected_source_revision_id: str,
    expected_normalized_hash: str,
    expected_normalized_markdown_path: str,
    expected_normalized_json_path: str,
) -> str:
    chunk_id = record.get("chunk_id")
    if not isinstance(chunk_id, str) or not re.fullmatch(r"CHK_[0-9]{6}", chunk_id):
        raise ChunkRegistryError("Chunk record has invalid chunk_id.")
    if record.get("source_revision_id") != expected_source_revision_id:
        raise ChunkRegistryError("Chunk record source_revision_id is incoherent.")
    if record.get("sequence") != expected_sequence:
        raise ChunkRegistryError("Chunk sequences must be consecutive and start at 1.")
    if record.get("status") != "active":
        raise ChunkRegistryError("Chunk record status must be active.")

    text = record.get("text")
    if not isinstance(text, str) or not text.strip():
        raise ChunkRegistryError("Chunk text must be non-empty.")
    if "\r" in text:
        raise ChunkRegistryError("Chunk text must use LF newlines only.")
    if not text.endswith("\n"):
        raise ChunkRegistryError("Chunk text must end with a newline.")
    if record.get("text_hash") != sha256_text(text):
        raise ChunkRegistryError("Chunk text_hash does not match chunk text.")

    metadata = record.get("metadata")
    if not isinstance(metadata, dict):
        raise ChunkRegistryError("Chunk metadata must be an object.")
    missing = sorted(REQUIRED_METADATA_KEYS - set(metadata))
    if missing:
        raise ChunkRegistryError(f"Chunk metadata is missing: {', '.join(missing)}.")
    if metadata.get("normalized_hash") != expected_normalized_hash:
        raise ChunkRegistryError("Chunk metadata normalized_hash is incoherent.")
    if metadata.get("normalized_markdown_path") != expected_normalized_markdown_path:
        raise ChunkRegistryError("Chunk metadata normalized_markdown_path is incoherent.")
    if metadata.get("normalized_json_path") != expected_normalized_json_path:
        raise ChunkRegistryError("Chunk metadata normalized_json_path is incoherent.")
    if metadata.get("source_text_kind") != "normalized_markdown":
        raise ChunkRegistryError("Chunk metadata source_text_kind is incoherent.")
    if not isinstance(metadata.get("heading_path"), list):
        raise ChunkRegistryError("Chunk metadata heading_path must be a list.")
    for key in ("normalized_markdown_path", "normalized_json_path"):
        _validate_relative_path_text(metadata.get(key), f"metadata.{key}")
    for key in ("start_char", "end_char"):
        value = metadata.get(key)
        if value is not None and (not isinstance(value, int) or value < 0):
            raise ChunkRegistryError(f"Chunk metadata {key} must be a non-negative integer or null.")
    start_char = metadata.get("start_char")
    end_char = metadata.get("end_char")
    if isinstance(start_char, int) and isinstance(end_char, int) and start_char > end_char:
        raise ChunkRegistryError("Chunk metadata start_char must not exceed end_char.")
    return chunk_id


def _upsert_chunk(
    connection: sqlite3.Connection,
    record: dict[str, Any],
    *,
    timestamp: str,
) -> None:
    chunk_id = record["chunk_id"]
    source_revision_id = record["source_revision_id"]
    sequence = int(record["sequence"])
    owner = connection.execute(
        """
        SELECT chunk_id, source_revision_id, sequence
        FROM chunks
        WHERE chunk_id = ?
        """,
        (chunk_id,),
    ).fetchone()
    if owner is not None and (
        owner["source_revision_id"] != source_revision_id or int(owner["sequence"]) != sequence
    ):
        raise ChunkRegistryError(f"Chunk id {chunk_id} already belongs to another revision or sequence.")

    metadata_json = canonical_metadata_json(record["metadata"])
    if owner is None:
        connection.execute(
            """
            INSERT INTO chunks (
                chunk_id,
                source_revision_id,
                sequence,
                text,
                text_hash,
                metadata_json,
                status,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                chunk_id,
                source_revision_id,
                sequence,
                record["text"],
                record["text_hash"],
                metadata_json,
                "active",
                timestamp,
            ),
        )
        return

    connection.execute(
        """
        UPDATE chunks
        SET text = ?,
            text_hash = ?,
            metadata_json = ?,
            status = ?
        WHERE chunk_id = ?
        """,
        (
            record["text"],
            record["text_hash"],
            metadata_json,
            "active",
            chunk_id,
        ),
    )


def _write_chunk_report(
    path: Path,
    *,
    output: dict[str, Any],
    records: list[dict[str, Any]],
    chunks_hash: str,
) -> None:
    report = {
        "chunk_count": len(records),
        "chunks": [
            {
                "chunk_id": record["chunk_id"],
                "end_char": record["metadata"]["end_char"],
                "heading_path": record["metadata"]["heading_path"],
                "sequence": record["sequence"],
                "start_char": record["metadata"]["start_char"],
                "status": record["status"],
                "text_hash": record["text_hash"],
            }
            for record in records
        ],
        "chunks_hash": chunks_hash,
        "input": {
            "normalized_hash": output["normalized_hash"],
            "normalized_json_path": output["normalized_json_path"],
            "normalized_markdown_path": output["normalized_markdown_path"],
            "source_hash": output.get("source_hash"),
            "source_hash_path": output.get("source_hash_path"),
            "source_id": output["source_id"],
            "source_revision_id": output["source_revision_id"],
        },
        "outputs": {
            "chunk_report_path": output["chunk_report_path"],
            "chunks_jsonl_path": output["chunks_jsonl_path"],
        },
        "profile": output["profile"],
        "run_id": output["run_id"],
        "status": "completed",
        "strategy": output["strategy"],
        "worker_name": output["worker_name"],
        "worker_version": output["worker_version"],
    }
    path.write_text(canonical_json(report), encoding="utf-8", newline="\n")


def _required_output_path(output: dict[str, Any], key: str) -> str:
    value = output.get(key)
    if not isinstance(value, str) or not value:
        raise ChunkRegistryError(f"Worker output field is missing: {key}.")
    _validate_relative_path_text(value, key)
    return value


def _validate_relative_path_text(value: Any, key: str) -> None:
    if not isinstance(value, str) or not value:
        raise ChunkRegistryError(f"Path field is invalid: {key}.")
    path = Path(value)
    if "\\" in value or path.is_absolute() or ".." in path.parts:
        raise ChunkRegistryError(f"Path is not workspace-relative: {key}.")


def _resolve_relative_file(workspace_dir: Path, relative_path: str) -> Path:
    try:
        return resolve_workspace_path(workspace_dir, relative_path)
    except DatabaseConfigurationError as exc:
        raise ChunkRegistryError(f"Output path escapes the workspace: {relative_path}.") from exc
