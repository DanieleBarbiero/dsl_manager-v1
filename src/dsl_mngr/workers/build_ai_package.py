from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from dsl_mngr.core.ai_package import (
    AI_PACKAGE_STATUS_WAITING,
    AiPackageError,
    UnsupportedAiPackageOption,
    build_content_markdown,
    build_instructions_markdown,
    build_output_template_jsonl,
    build_package_manifest_payload,
    build_source_manifest_payload,
    candidate_schema_payload,
    compute_package_hash,
    file_hash,
    parse_ai_package_options,
)
from dsl_mngr.core.runs import canonical_json, relative_workspace_path, timestamp_now


WORKER_NAME = "build_ai_package"
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
        result_payload = build_package(worker_input, workspace_dir=workspace_dir)
    except UnsupportedAiPackageOption as exc:
        _write_error("unsupported_ai_package_option", str(exc), option=exc.option_key)
        return 4
    except (AiPackageError, RuntimeError, ValueError, OSError, json.JSONDecodeError) as exc:
        _write_error("ai_package_build_failed", str(exc))
        return 5

    output_path.write_text(canonical_json(result_payload), encoding="utf-8", newline="\n")
    print("build_ai_package completed")
    return 0


def build_package(payload: dict[str, Any], *, workspace_dir: Path) -> dict[str, Any]:
    run_id = _required_string(payload, "run_id")
    package_id = _required_string(payload, "package_id")
    output_dir_relative = _required_string(payload, "output_dir")
    profile = _required_string(payload, "profile")
    worker_config = _required_dict(payload, "worker_config")
    raw_options = _required_dict(payload, "ai_package_options")
    source_revisions = _required_dict_list(payload, "source_revisions")
    chunks = _optional_dict_list(payload, "chunks")
    fragments = _optional_dict_list(payload, "fragments")

    options = parse_ai_package_options(raw_options)
    if not options.include_candidate_schema:
        raise AiPackageError("candidate_schema.json is required for AI packages.")
    if not options.include_output_template:
        raise AiPackageError("output_template.jsonl is required for AI packages.")
    if not chunks and not fragments:
        raise AiPackageError("No evidence was provided to the AI package worker.")

    worker_version = str(worker_config.get("version", WORKER_VERSION))
    output_dir = _resolve_relative_path(workspace_dir, output_dir_relative)
    output_dir.mkdir(parents=True, exist_ok=False)

    instructions_path = output_dir / "instructions.md"
    content_path = output_dir / "content.md"
    source_manifest_path = output_dir / "source_manifest.json"
    candidate_schema_path = output_dir / "candidate_schema.json"
    output_template_path = output_dir / "output_template.jsonl"
    package_manifest_path = output_dir / "package_manifest.json"
    package_path = relative_workspace_path(workspace_dir, output_dir)

    instructions_path.write_text(
        build_instructions_markdown(package_id),
        encoding="utf-8",
        newline="\n",
    )
    content_path.write_text(
        build_content_markdown(
            package_id=package_id,
            source_revisions=source_revisions,
            chunks=chunks,
            fragments=fragments,
            max_evidence_chars=options.max_evidence_chars,
        ),
        encoding="utf-8",
        newline="\n",
    )
    source_manifest = build_source_manifest_payload(
        package_id=package_id,
        package_path=package_path,
        source_revisions=source_revisions,
        chunks=chunks,
        fragments=fragments,
    )
    source_manifest_path.write_text(
        canonical_json(source_manifest),
        encoding="utf-8",
        newline="\n",
    )
    candidate_schema_path.write_text(
        canonical_json(candidate_schema_payload()),
        encoding="utf-8",
        newline="\n",
    )
    output_template_path.write_text(
        build_output_template_jsonl(chunks=chunks, fragments=fragments),
        encoding="utf-8",
        newline="\n",
    )

    files = {
        "candidate_schema": {
            "path": relative_workspace_path(workspace_dir, candidate_schema_path),
            "sha256": file_hash(candidate_schema_path),
        },
        "content": {
            "path": relative_workspace_path(workspace_dir, content_path),
            "sha256": file_hash(content_path),
        },
        "instructions": {
            "path": relative_workspace_path(workspace_dir, instructions_path),
            "sha256": file_hash(instructions_path),
        },
        "output_template": {
            "path": relative_workspace_path(workspace_dir, output_template_path),
            "sha256": file_hash(output_template_path),
        },
        "source_manifest": {
            "path": relative_workspace_path(workspace_dir, source_manifest_path),
            "sha256": file_hash(source_manifest_path),
        },
    }
    package_hash = compute_package_hash(files)
    package_manifest = build_package_manifest_payload(
        package_id=package_id,
        run_id=run_id,
        worker_name=WORKER_NAME,
        worker_version=worker_version,
        status=AI_PACKAGE_STATUS_WAITING,
        package_path=package_path,
        source_manifest_path=relative_workspace_path(workspace_dir, source_manifest_path),
        created_at=timestamp_now(None),
        files=files,
        package_hash=package_hash,
        source_revision_count=len(source_revisions),
        chunk_count=len(chunks),
        fragment_count=len(fragments),
    )
    package_manifest_path.write_text(
        canonical_json(package_manifest),
        encoding="utf-8",
        newline="\n",
    )

    return {
        "candidate_schema_path": relative_workspace_path(workspace_dir, candidate_schema_path),
        "chunk_count": len(chunks),
        "content_path": relative_workspace_path(workspace_dir, content_path),
        "exit_code": 0,
        "files": files,
        "fragment_count": len(fragments),
        "instructions_path": relative_workspace_path(workspace_dir, instructions_path),
        "manifest_path": relative_workspace_path(workspace_dir, package_manifest_path),
        "output_template_path": relative_workspace_path(workspace_dir, output_template_path),
        "package_hash": package_hash,
        "package_id": package_id,
        "package_path": package_path,
        "profile": profile,
        "run_id": run_id,
        "source_manifest_path": relative_workspace_path(workspace_dir, source_manifest_path),
        "source_revision_count": len(source_revisions),
        "status": "completed",
        "worker_name": WORKER_NAME,
        "worker_version": worker_version,
    }


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
    if raw.is_absolute() or ".." in raw.parts or "\\" in relative_path:
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


def _required_dict_list(payload: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = payload.get(key)
    if not isinstance(value, list) or not value:
        raise ValueError(f"Missing required worker input field: {key}")
    if not all(isinstance(item, dict) for item in value):
        raise ValueError(f"Worker input field must contain objects: {key}")
    return value


def _optional_dict_list(payload: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = payload.get(key, [])
    if not isinstance(value, list):
        raise ValueError(f"Worker input field must be a list: {key}")
    if not all(isinstance(item, dict) for item in value):
        raise ValueError(f"Worker input field must contain objects: {key}")
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
