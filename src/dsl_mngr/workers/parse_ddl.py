from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from dsl_mngr.core.ddl_parser import (
    DdlParserError,
    UnsupportedDdlOption,
    build_fragment_records,
    fragments_jsonl_content,
    fragments_jsonl_hash,
    parse_ddl_options,
    parse_ddl_text,
)
from dsl_mngr.core.runs import canonical_json, relative_workspace_path


WORKER_NAME = "parse_ddl"
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
        result_payload = parse(worker_input, workspace_dir=workspace_dir)
    except UnsupportedDdlOption as exc:
        _write_error("unsupported_ddl_option", str(exc), option=exc.option_key)
        return 4
    except (DdlParserError, RuntimeError, ValueError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        _write_error("ddl_parsing_failed", str(exc))
        return 5

    output_path.write_text(canonical_json(result_payload), encoding="utf-8", newline="\n")
    print("parse_ddl completed")
    return 0


def parse(payload: dict[str, Any], *, workspace_dir: Path) -> dict[str, Any]:
    run_id = _required_string(payload, "run_id")
    source_id = _required_string(payload, "source_id")
    source_revision_id = _required_string(payload, "source_revision_id")
    source_hash = _required_string(payload, "source_hash")
    input_path_relative = _required_string(payload, "input_path")
    output_dir_relative = _required_string(payload, "output_dir")
    profile = _required_string(payload, "profile")
    worker_config = _required_dict(payload, "worker_config")
    ddl_options = _required_dict(payload, "ddl_options")

    options = parse_ddl_options(ddl_options)
    worker_version = str(worker_config.get("version", WORKER_VERSION))

    source_path = _resolve_relative_path(workspace_dir, input_path_relative)
    output_dir = _resolve_relative_path(workspace_dir, output_dir_relative)
    if not source_path.is_file():
        raise ValueError(f"Input source file not found: {input_path_relative}")

    actual_source_hash = _sha256_file(source_path)
    if actual_source_hash != source_hash:
        raise ValueError(
            "Source file hash does not match source_revisions.content_hash; "
            "rerun 'dsl-manager corpus scan' before parsing DDL."
        )

    ddl_text = source_path.read_text(encoding="utf-8")
    parse_result = parse_ddl_text(ddl_text, options)
    fragment_id_by_sequence = _fragment_id_by_sequence(payload.get("fragment_id_by_sequence"))
    next_fragment_number = _required_int(payload, "next_fragment_number")
    records = build_fragment_records(
        parse_result,
        source_revision_id=source_revision_id,
        source_hash=source_hash,
        parser_name=WORKER_NAME,
        parser_version=worker_version,
        fragment_id_by_sequence=fragment_id_by_sequence,
        next_fragment_number=next_fragment_number,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    fragments_jsonl_path = output_dir / "fragments.jsonl"
    report_path = output_dir / "ddl_report.json"
    fragments_hash = fragments_jsonl_hash(records)
    if options.output_fragments_jsonl:
        fragments_jsonl_path.write_text(
            fragments_jsonl_content(records),
            encoding="utf-8",
            newline="\n",
        )

    output_payload = {
        "column_count": parse_result.column_count,
        "ddl_objects": parse_result.to_objects(),
        "ddl_options": ddl_options,
        "ddl_report_path": relative_workspace_path(workspace_dir, report_path),
        "dialect": options.dialect,
        "exit_code": 0,
        "foreign_key_count": parse_result.foreign_key_count,
        "fragment_count": len(records),
        "fragments": records,
        "fragments_hash": fragments_hash,
        "fragments_jsonl_path": relative_workspace_path(workspace_dir, fragments_jsonl_path),
        "input_path": input_path_relative,
        "profile": profile,
        "run_id": run_id,
        "source_hash": actual_source_hash,
        "source_id": source_id,
        "source_revision_id": source_revision_id,
        "status": "completed",
        "table_count": parse_result.table_count,
        "warnings": list(parse_result.warnings),
        "worker_config": worker_config,
        "worker_name": WORKER_NAME,
        "worker_version": worker_version,
    }
    report = {
        "column_count": parse_result.column_count,
        "ddl_objects": parse_result.to_objects(),
        "dialect": options.dialect,
        "foreign_key_count": parse_result.foreign_key_count,
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
            "input_path": input_path_relative,
            "source_hash": actual_source_hash,
            "source_id": source_id,
            "source_revision_id": source_revision_id,
        },
        "outputs": {
            "ddl_report_path": output_payload["ddl_report_path"],
            "fragments_jsonl_path": output_payload["fragments_jsonl_path"],
        },
        "profile": profile,
        "resolved_config": {
            "ddl": ddl_options,
            "worker": worker_config,
        },
        "run_id": run_id,
        "status": "completed",
        "table_count": parse_result.table_count,
        "warnings": list(parse_result.warnings),
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


def _fragment_id_by_sequence(value: Any) -> dict[int, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("fragment_id_by_sequence must be an object.")
    result: dict[int, str] = {}
    for raw_sequence, raw_fragment_id in value.items():
        sequence = int(raw_sequence)
        if not isinstance(raw_fragment_id, str) or not raw_fragment_id:
            raise ValueError("fragment_id_by_sequence values must be non-empty strings.")
        result[sequence] = raw_fragment_id
    return result


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


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
