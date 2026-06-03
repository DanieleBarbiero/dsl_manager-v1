from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from dsl_mngr.core.docling_adapter import (
    DoclingAdapterError,
    UnsupportedDoclingOption,
    normalize_document_with_docling,
)
from dsl_mngr.core.hashing import sha256_file
from dsl_mngr.core.runs import canonical_json, relative_workspace_path


WORKER_NAME = "normalize_docling"
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
        result_payload = normalize(worker_input, workspace_dir=workspace_dir)
    except UnsupportedDoclingOption as exc:
        _write_error("unsupported_docling_option", str(exc), option=exc.option_key)
        return 4
    except (DoclingAdapterError, RuntimeError, ValueError, OSError) as exc:
        _write_error("docling_normalization_failed", str(exc))
        return 5

    output_path.write_text(canonical_json(result_payload), encoding="utf-8", newline="\n")
    print("normalize_docling completed")
    return 0


def normalize(payload: dict[str, Any], *, workspace_dir: Path) -> dict[str, Any]:
    run_id = _required_string(payload, "run_id")
    source_id = _required_string(payload, "source_id")
    source_revision_id = _required_string(payload, "source_revision_id")
    input_path_relative = _required_string(payload, "input_path")
    output_dir_relative = _required_string(payload, "output_dir")
    profile = _required_string(payload, "profile")
    worker_config = _required_dict(payload, "worker_config")
    docling_options = _required_dict(payload, "docling_options")

    source_path = _resolve_relative_path(workspace_dir, input_path_relative)
    output_dir = _resolve_relative_path(workspace_dir, output_dir_relative)
    if not source_path.is_file():
        raise ValueError(f"Input source file not found: {input_path_relative}")

    normalized = normalize_document_with_docling(source_path, docling_options)
    source_hash = sha256_file(source_path)
    normalized_hash = _sha256_text(normalized.markdown)

    output_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = output_dir / "normalized.md"
    json_path = output_dir / "normalized.json"
    source_hash_path = output_dir / "source_hash.txt"
    report_path = output_dir / "docling_report.json"

    document = _sanitize_workspace_paths(normalized.document, workspace_dir)
    markdown_path.write_text(normalized.markdown, encoding="utf-8", newline="\n")
    json_path.write_text(canonical_json(document), encoding="utf-8", newline="\n")
    source_hash_path.write_text(source_hash + "\n", encoding="utf-8", newline="\n")

    output_payload = {
        "docling_report_path": relative_workspace_path(workspace_dir, report_path),
        "docling_version": normalized.docling_version,
        "exit_code": 0,
        "input_path": input_path_relative,
        "normalized_hash": normalized_hash,
        "normalized_json_path": relative_workspace_path(workspace_dir, json_path),
        "normalized_markdown_path": relative_workspace_path(workspace_dir, markdown_path),
        "profile": profile,
        "run_id": run_id,
        "source_hash": source_hash,
        "source_hash_path": relative_workspace_path(workspace_dir, source_hash_path),
        "source_id": source_id,
        "source_revision_id": source_revision_id,
        "status": "completed",
        "worker_name": WORKER_NAME,
        "worker_version": str(worker_config.get("version", WORKER_VERSION)),
    }
    report = {
        "docling_version": normalized.docling_version,
        "input": {
            "input_path": input_path_relative,
            "source_hash": source_hash,
            "source_id": source_id,
            "source_revision_id": source_revision_id,
        },
        "outputs": {
            "docling_report_path": output_payload["docling_report_path"],
            "normalized_hash": normalized_hash,
            "normalized_json_path": output_payload["normalized_json_path"],
            "normalized_markdown_path": output_payload["normalized_markdown_path"],
            "source_hash_path": output_payload["source_hash_path"],
        },
        "profile": profile,
        "resolved_config": {
            "docling": normalized.resolved_options,
            "worker": worker_config,
        },
        "run_id": run_id,
        "status": "completed",
        "worker_name": WORKER_NAME,
        "worker_version": output_payload["worker_version"],
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


def _sha256_text(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sanitize_workspace_paths(value: Any, workspace_dir: Path) -> Any:
    if isinstance(value, dict):
        return {key: _sanitize_workspace_paths(child, workspace_dir) for key, child in value.items()}
    if isinstance(value, list):
        return [_sanitize_workspace_paths(child, workspace_dir) for child in value]
    if isinstance(value, str):
        workspace_native = str(workspace_dir.resolve())
        workspace_posix = workspace_dir.resolve().as_posix()
        return value.replace(workspace_native, "<workspace>").replace(workspace_posix, "<workspace>")
    return value


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
