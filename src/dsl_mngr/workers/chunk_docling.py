from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from dsl_mngr.core.chunking import (
    ChunkingError,
    UnsupportedChunkingOption,
    build_chunk_record,
    chunk_markdown,
    chunks_jsonl_content,
    chunks_jsonl_hash,
    normalize_markdown_newlines,
    parse_chunking_options,
    sha256_text,
)
from dsl_mngr.core.runs import canonical_json, relative_workspace_path


WORKER_NAME = "chunk_docling"
WORKER_VERSION = "1.0"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve()

    try:
        payload = json.loads(input_path.read_text(encoding="utf-8"))
        workspace_dir = _workspace_dir_from_input(input_path)
        worker_input = _worker_input(payload)
        result_payload = chunk(worker_input, workspace_dir=workspace_dir)
    except UnsupportedChunkingOption as exc:
        _write_error("unsupported_chunking_option", str(exc), option=exc.option_key)
        return 4
    except (ChunkingError, RuntimeError, ValueError, OSError, json.JSONDecodeError) as exc:
        _write_error("chunking_failed", str(exc))
        return 5

    output_path.write_text(canonical_json(result_payload), encoding="utf-8", newline="\n")
    print("chunk_docling completed")
    return 0


def chunk(payload: dict[str, Any], *, workspace_dir: Path) -> dict[str, Any]:
    run_id = _required_string(payload, "run_id")
    source_id = _required_string(payload, "source_id")
    source_revision_id = _required_string(payload, "source_revision_id")
    normalized_hash = _required_string(payload, "normalized_hash")
    normalized_markdown_path = _required_string(payload, "normalized_markdown_path")
    normalized_json_path = _required_string(payload, "normalized_json_path")
    source_hash_path = _required_string(payload, "source_hash_path")
    output_dir_relative = _required_string(payload, "output_dir")
    profile = _required_string(payload, "profile")
    worker_config = _required_dict(payload, "worker_config")
    chunking_options = _required_dict(payload, "chunking_options")

    options = parse_chunking_options(chunking_options)
    worker_version = str(worker_config.get("version", WORKER_VERSION))

    markdown_path = _resolve_relative_path(workspace_dir, normalized_markdown_path)
    json_path = _resolve_relative_path(workspace_dir, normalized_json_path)
    source_hash_file = _resolve_relative_path(workspace_dir, source_hash_path)
    output_dir = _resolve_relative_path(workspace_dir, output_dir_relative)

    if not markdown_path.is_file():
        raise ValueError(f"normalized.md not found: {normalized_markdown_path}")
    if not json_path.is_file():
        raise ValueError(f"normalized.json not found: {normalized_json_path}")
    if not source_hash_file.is_file():
        raise ValueError(f"source_hash.txt not found: {source_hash_path}")

    markdown_text = normalize_markdown_newlines(markdown_path.read_text(encoding="utf-8"))
    markdown_hash = sha256_text(markdown_text)
    if options.require_normalized_hash_match and markdown_hash != normalized_hash:
        raise ValueError("normalized.md hash does not match source_revisions.normalized_hash.")

    json.loads(json_path.read_text(encoding="utf-8"))
    source_hash = source_hash_file.read_text(encoding="utf-8").strip()
    expected_source_hash = payload.get("source_hash")
    if isinstance(expected_source_hash, str) and expected_source_hash and source_hash != expected_source_hash:
        raise ValueError("source_hash.txt does not match source_revisions.content_hash.")

    candidates = chunk_markdown(markdown_text, options)
    chunk_id_by_sequence = _chunk_id_by_sequence(payload.get("chunk_id_by_sequence"))
    next_chunk_number = _required_int(payload, "next_chunk_number")
    used_chunk_ids = set(chunk_id_by_sequence.values())

    metadata_base = {
        "chunker": WORKER_NAME,
        "chunker_version": worker_version,
        "normalized_hash": normalized_hash,
        "normalized_json_path": normalized_json_path,
        "normalized_markdown_path": normalized_markdown_path,
        "strategy": options.strategy,
    }
    records: list[dict[str, Any]] = []
    for candidate in candidates:
        chunk_id = chunk_id_by_sequence.get(candidate.sequence)
        if chunk_id is None:
            chunk_id = _next_chunk_id(next_chunk_number, used_chunk_ids)
            next_chunk_number = int(chunk_id.rsplit("_", 1)[1]) + 1
        used_chunk_ids.add(chunk_id)
        records.append(
            build_chunk_record(
                chunk_id=chunk_id,
                candidate=candidate,
                source_revision_id=source_revision_id,
                metadata_base=metadata_base,
            )
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    chunks_jsonl_path = output_dir / "chunks.jsonl"
    report_path = output_dir / "chunk_report.json"
    content = chunks_jsonl_content(records)
    chunks_hash = chunks_jsonl_hash(records)
    if options.output_chunks_jsonl:
        chunks_jsonl_path.write_text(content, encoding="utf-8", newline="\n")

    output_payload = {
        "chunk_count": len(records),
        "chunk_report_path": relative_workspace_path(workspace_dir, report_path),
        "chunks": records,
        "chunks_hash": chunks_hash,
        "chunks_jsonl_path": relative_workspace_path(workspace_dir, chunks_jsonl_path),
        "exit_code": 0,
        "normalized_hash": normalized_hash,
        "normalized_json_path": normalized_json_path,
        "normalized_markdown_path": normalized_markdown_path,
        "profile": profile,
        "run_id": run_id,
        "source_hash": source_hash,
        "source_hash_path": source_hash_path,
        "source_id": source_id,
        "source_revision_id": source_revision_id,
        "status": "completed",
        "strategy": options.strategy,
        "worker_name": WORKER_NAME,
        "worker_version": worker_version,
    }
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
            "normalized_hash": normalized_hash,
            "normalized_json_path": normalized_json_path,
            "normalized_markdown_path": normalized_markdown_path,
            "source_hash": source_hash,
            "source_hash_path": source_hash_path,
            "source_id": source_id,
            "source_revision_id": source_revision_id,
        },
        "outputs": {
            "chunk_report_path": output_payload["chunk_report_path"],
            "chunks_jsonl_path": output_payload["chunks_jsonl_path"],
        },
        "profile": profile,
        "resolved_config": {
            "chunking": chunking_options,
            "worker": worker_config,
        },
        "run_id": run_id,
        "status": "completed",
        "strategy": options.strategy,
        "worker_name": WORKER_NAME,
        "worker_version": worker_version,
    }
    report_path.write_text(canonical_json(report), encoding="utf-8", newline="\n")
    return output_payload


def _worker_input(payload: dict[str, Any]) -> dict[str, Any]:
    nested = payload.get("input")
    if isinstance(nested, dict):
        return {**payload, **nested}
    return payload


def _workspace_dir_from_input(input_path: Path) -> Path:
    try:
        return input_path.parent.parent.parent.parent.resolve()
    except IndexError as exc:
        raise ValueError(f"Cannot infer workspace from input artifact: {input_path}") from exc


def _resolve_relative_path(workspace_dir: Path, relative_path: str) -> Path:
    raw = Path(relative_path)
    if raw.is_absolute() or ".." in raw.parts:
        raise ValueError(f"Path must be relative to the workspace: {relative_path}")
    resolved = (workspace_dir / raw).resolve()
    try:
        resolved.relative_to(workspace_dir.resolve())
    except ValueError as exc:
        raise ValueError(f"Path escapes the workspace: {relative_path}") from exc
    return resolved


def _chunk_id_by_sequence(value: Any) -> dict[int, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("chunk_id_by_sequence must be an object.")
    result: dict[int, str] = {}
    for raw_sequence, raw_chunk_id in value.items():
        sequence = int(raw_sequence)
        if not isinstance(raw_chunk_id, str) or not raw_chunk_id:
            raise ValueError("chunk_id_by_sequence values must be non-empty strings.")
        result[sequence] = raw_chunk_id
    return result


def _next_chunk_id(start_number: int, used_chunk_ids: set[str]) -> str:
    number = max(1, start_number)
    while True:
        chunk_id = f"CHK_{number:06d}"
        if chunk_id not in used_chunk_ids:
            return chunk_id
        number += 1


def _required_string(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Missing required worker input field: {key}")
    return value


def _required_dict(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"Missing required worker input field: {key}")
    return value


def _required_int(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    if isinstance(value, bool):
        raise ValueError(f"Missing required worker input field: {key}")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Missing required worker input field: {key}") from exc


def _write_error(error_type: str, message: str, *, option: str | None = None) -> None:
    payload: dict[str, Any] = {
        "error_type": error_type,
        "message": message,
        "worker_name": WORKER_NAME,
    }
    if option is not None:
        payload["option"] = option
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True), file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
