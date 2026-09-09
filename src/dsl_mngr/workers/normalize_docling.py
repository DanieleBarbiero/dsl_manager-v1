from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from dsl_mngr.core.docling_adapter import (
    DoclingAdapterError,
    UnsupportedDoclingOption,
    normalize_excel_stream_with_docling,
    normalize_document_with_docling,
)
from dsl_mngr.core.hashing import sha256_file
from dsl_mngr.core.ooxml_preflight import (
    ExcelLimits,
    OoxmlPreflightError,
    WorkbookManifestBuild,
    acquire_source_once,
    build_workbook_manifest,
    catalog_result,
    enforce_output_budget,
    preflight_ooxml,
)
from dsl_mngr.core.workbook_regions import REGION_DETECTOR_ID, REGION_DETECTOR_VERSION
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
    except OoxmlPreflightError as exc:
        _write_error(exc.reason, str(exc))
        return exc.exit_code
    except UnsupportedDoclingOption as exc:
        _write_error("unsupported_docling_option", str(exc), option=exc.option_key)
        return 4
    except (DoclingAdapterError, RuntimeError, ValueError, OSError) as exc:
        _write_error("docling_normalization_failed", str(exc))
        return 5

    _atomic_write_text(output_path, canonical_json(result_payload))
    print("normalize_docling completed")
    return int(result_payload.get("exit_code", 0))


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

    source_name = source_path.name
    is_excel = source_path.suffix.lower() in {".xlsx", ".xlsm"}
    preflight_report: dict[str, Any] | None = None
    workbook_build = None
    excel_limits: ExcelLimits | None = None
    preflight_report_path = output_dir / "ooxml_preflight_report.json"
    workbook_manifest_path = output_dir / "workbook_manifest.json"
    workbook_fragments_path = output_dir / "workbook_fragments.jsonl"
    workbook_report_path = output_dir / "workbook_report.json"
    memory_limit_mode = str(payload.get("memory_limit_mode", "not_applicable"))

    if is_excel:
        expected_source_hash = _required_string(payload, "expected_source_hash")
        excel_limits = ExcelLimits.from_config(_required_dict(payload, "excel_limits"))
        try:
            acquired = acquire_source_once(
                source_path,
                expected_hash=expected_source_hash,
                max_file_bytes=excel_limits.max_file_bytes,
            )
            preflight_cursor, docling_cursor = acquired.cursors()
            checked = preflight_ooxml(
                preflight_cursor,
                original_name=source_name,
                source_hash=acquired.sha256,
                limits=excel_limits,
            )
            workbook_build = build_workbook_manifest(
                acquired.cursor(),
                preflight=checked,
                source_revision_id=source_revision_id,
                fragment_id_by_sequence=_fragment_id_by_sequence(
                    payload.get("fragment_id_by_sequence", {})
                ),
                next_fragment_number=_optional_positive_int(
                    payload, "next_fragment_number", default=1
                ),
            )
            docling_stream_hash = hashlib.sha256(docling_cursor.getbuffer()).hexdigest()
            if docling_stream_hash != acquired.sha256:
                raise OoxmlPreflightError(
                    "source_revision_changed",
                    "Docling cursor bytes differ from the acquired source revision.",
                    status="failed",
                    exit_code=4,
                    source_hash=docling_stream_hash,
                )
            preflight_report = checked.report()
            preflight_report["input"]["docling_stream_hash"] = docling_stream_hash
            _enrich_catalog(
                preflight_report,
                run_id=None,
                source_id=source_id,
                source_revision_id=source_revision_id,
                artifact_paths=[
                    relative_workspace_path(workspace_dir, preflight_report_path)
                ],
            )
            preflight_report["resource_limits"] = {
                "max_output_bytes": excel_limits.max_output_bytes,
                "memory_limit_bytes": excel_limits.worker_memory_bytes,
                "memory_limit_mode": memory_limit_mode,
                "timeout_seconds": excel_limits.worker_timeout_seconds,
            }
            preflight_report["manifest"] = {
                "cells": workbook_build.cell_count,
                "fragments": len(workbook_build.fragments),
                "manifest_hash": workbook_build.manifest_hash,
                "regions": workbook_build.region_count,
                "schema_version": "1",
            }
            normalized = normalize_excel_stream_with_docling(
                docling_cursor,
                original_name=source_name,
                docling_options=docling_options,
            )
            source_hash = acquired.sha256
        except OoxmlPreflightError as exc:
            _write_preflight_failure(
                preflight_report_path,
                exc.report(),
                memory_limit_mode=memory_limit_mode,
                limits=excel_limits,
                source_id=source_id,
                source_revision_id=source_revision_id,
                workspace_dir=workspace_dir,
            )
            raise
        except (DoclingAdapterError, RuntimeError, ValueError, OSError) as exc:
            _write_preflight_failure(
                preflight_report_path,
                _operational_failure_report(str(exc)),
                memory_limit_mode=memory_limit_mode,
                limits=excel_limits,
                source_id=source_id,
                source_revision_id=source_revision_id,
                workspace_dir=workspace_dir,
            )
            raise
    else:
        normalized = normalize_document_with_docling(source_path, docling_options)
        source_hash = sha256_file(source_path)

    normalized_hash = _sha256_text(normalized.markdown)

    markdown_path = output_dir / "normalized.md"
    json_path = output_dir / "normalized.json"
    source_hash_path = output_dir / "source_hash.txt"
    report_path = output_dir / "docling_report.json"

    document = _sanitize_workspace_paths(normalized.document, workspace_dir)
    is_partial = normalized.conversion_status == "partial_success"
    status = "partial" if is_partial else "completed"
    exit_code = 6 if is_partial else 0
    reason = "normalization_partial" if is_partial else None

    output_payload = {
        "docling_report_path": relative_workspace_path(workspace_dir, report_path),
        "docling_version": normalized.docling_version,
        "exit_code": exit_code,
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
        "status": status,
        "worker_name": WORKER_NAME,
        "worker_version": str(worker_config.get("version", WORKER_VERSION)),
    }
    if is_excel:
        output_payload["ooxml_preflight_report_path"] = relative_workspace_path(
            workspace_dir, preflight_report_path
        )
        output_payload["memory_limit_mode"] = memory_limit_mode
        if workbook_build is None:  # pragma: no cover - guarded by successful preflight.
            raise RuntimeError("Workbook manifest was not built after OOXML preflight.")
        output_payload.update(
            {
                "workbook_cell_count": workbook_build.cell_count,
                "workbook_fragment_count": len(workbook_build.fragments),
                "workbook_fragments_hash": workbook_build.fragments_hash,
                "workbook_fragments_path": relative_workspace_path(
                    workspace_dir, workbook_fragments_path
                ),
                "workbook_manifest_hash": workbook_build.manifest_hash,
                "workbook_manifest_path": relative_workspace_path(
                    workspace_dir, workbook_manifest_path
                ),
                "workbook_region_count": workbook_build.region_count,
                "workbook_report_path": relative_workspace_path(
                    workspace_dir, workbook_report_path
                ),
                "workbook_sheet_count": len(workbook_build.manifest["sheets"]),
            }
        )
        if preflight_report is not None:
            preflight_report["catalog"]["artifact_paths"] = sorted(
                [
                    output_payload["ooxml_preflight_report_path"],
                    output_payload["workbook_fragments_path"],
                    output_payload["workbook_manifest_path"],
                    output_payload["workbook_report_path"],
                ]
            )
    report = {
        "catalog": catalog_result(status, reason),
        "conversion_status": normalized.conversion_status,
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
        "status": status,
        "worker_name": WORKER_NAME,
        "worker_version": output_payload["worker_version"],
    }
    if is_excel:
        report["outputs"]["ooxml_preflight_report_path"] = output_payload[
            "ooxml_preflight_report_path"
        ]
        for key in (
            "workbook_fragments_path",
            "workbook_manifest_path",
            "workbook_report_path",
        ):
            report["outputs"][key] = output_payload[key]
    _enrich_catalog(
        report,
        run_id=run_id,
        source_id=source_id,
        source_revision_id=source_revision_id,
        artifact_paths=sorted(
            str(value)
            for key, value in report["outputs"].items()
            if key.endswith("_path")
        ),
        counters={
            "normalized_json_items": len(document),
            "normalized_markdown_bytes": len(normalized.markdown.encode("utf-8")),
        },
    )
    serialized: dict[str, str] = {
        "docling_report.json": canonical_json(report),
        "normalized.json": canonical_json(document),
        "normalized.md": normalized.markdown,
        "source_hash.txt": source_hash + "\n",
    }
    if preflight_report is not None:
        preflight_report["docling"] = {
            "conversion_status": normalized.conversion_status,
            "input_format": "xlsx",
            "version": normalized.docling_version,
        }
        serialized["ooxml_preflight_report.json"] = canonical_json(preflight_report)
    if workbook_build is not None:
        workbook_report = _workbook_report(
            output_payload,
            workbook_build=workbook_build,
            source_hash=source_hash,
            source_id=source_id,
            source_revision_id=source_revision_id,
        )
        serialized.update(
            {
                "workbook_fragments.jsonl": workbook_build.fragments_jsonl,
                "workbook_manifest.json": workbook_build.manifest_json,
                "workbook_report.json": canonical_json(workbook_report),
            }
        )
    if excel_limits is not None:
        try:
            enforce_output_budget(serialized, excel_limits.max_output_bytes)
        except OoxmlPreflightError as exc:
            _write_preflight_failure(
                preflight_report_path,
                exc.report(source_hash=source_hash),
                memory_limit_mode=memory_limit_mode,
                limits=excel_limits,
                source_id=source_id,
                source_revision_id=source_revision_id,
                workspace_dir=workspace_dir,
            )
            raise exc
    _publish_artifacts(output_dir, serialized)
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


def _required_int(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"Missing or invalid worker input field: {key}")
    return value


def _optional_positive_int(payload: dict[str, Any], key: str, *, default: int) -> int:
    if key not in payload:
        return default
    return _required_int(payload, key)


def _fragment_id_by_sequence(value: Any) -> dict[int, str]:
    if not isinstance(value, dict):
        raise ValueError("fragment_id_by_sequence must be an object.")
    result: dict[int, str] = {}
    for raw_sequence, raw_fragment_id in value.items():
        try:
            sequence = int(raw_sequence)
        except (TypeError, ValueError) as exc:
            raise ValueError("fragment_id_by_sequence keys must be integers.") from exc
        if sequence < 1 or not isinstance(raw_fragment_id, str) or not raw_fragment_id:
            raise ValueError("fragment_id_by_sequence contains an invalid entry.")
        result[sequence] = raw_fragment_id
    return result


def _workbook_report(
    output: dict[str, Any],
    *,
    workbook_build: WorkbookManifestBuild,
    source_hash: str,
    source_id: str,
    source_revision_id: str,
) -> dict[str, Any]:
    paths = sorted(
        output[key]
        for key in (
            "workbook_fragments_path",
            "workbook_manifest_path",
            "workbook_report_path",
        )
    )
    status = str(output["status"])
    reason = "normalization_partial" if status == "partial" else None
    catalog = catalog_result(status, reason)
    catalog.update(
        {
            "artifact_paths": paths,
            "counters": {
                "cells": workbook_build.cell_count,
                "fragments": len(workbook_build.fragments),
                "regions": workbook_build.region_count,
                "sheets": len(workbook_build.manifest["sheets"]),
            },
            "subject_ids": {
                "source_id": source_id,
                "source_revision_id": source_revision_id,
            },
        }
    )
    return {
        "catalog": catalog,
        "fragment_detector": {
            "id": REGION_DETECTOR_ID,
            "version": REGION_DETECTOR_VERSION,
        },
        "fragments_hash": workbook_build.fragments_hash,
        "macros_executed": False,
        "manifest_hash": workbook_build.manifest_hash,
        "network_accessed": False,
        "outputs": {
            "workbook_fragments_path": output["workbook_fragments_path"],
            "workbook_manifest_path": output["workbook_manifest_path"],
        },
        "schema_version": "1",
        "source_hash": source_hash,
        "source_id": source_id,
        "source_revision_id": source_revision_id,
        "status": status,
        "structural_source": "workbook_manifest.json",
    }


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


def _publish_artifacts(output_dir: Path, serialized: dict[str, str]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    stage = output_dir / f".normalize_{os.getpid()}_{time.time_ns()}"
    stage.mkdir()
    try:
        for name, text in serialized.items():
            path = stage / name
            path.write_text(text, encoding="utf-8", newline="\n")
        for name in sorted(serialized):
            os.replace(stage / name, output_dir / name)
    finally:
        if stage.exists():
            for child in stage.iterdir():
                child.unlink()
            stage.rmdir()


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{time.time_ns()}.tmp")
    try:
        temporary.write_text(text, encoding="utf-8", newline="\n")
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _write_preflight_failure(
    report_path: Path,
    report: dict[str, Any],
    *,
    memory_limit_mode: str,
    limits: ExcelLimits | None,
    source_id: str,
    source_revision_id: str,
    workspace_dir: Path,
) -> None:
    report["resource_limits"] = {
        "memory_limit_mode": memory_limit_mode,
    }
    if limits is not None:
        report["limits"] = limits.preflight_dict()
        report["resource_limits"].update(
            {
                "max_output_bytes": limits.max_output_bytes,
                "memory_limit_bytes": limits.worker_memory_bytes,
                "timeout_seconds": limits.worker_timeout_seconds,
            }
        )
    _enrich_catalog(
        report,
        run_id=None,
        source_id=source_id,
        source_revision_id=source_revision_id,
        artifact_paths=[relative_workspace_path(workspace_dir, report_path)],
    )
    _atomic_write_text(report_path, canonical_json(report))


def _operational_failure_report(message: str) -> dict[str, Any]:
    return {
        "catalog": catalog_result("failed", "normalization_operational_failure"),
        "external_targets_dereferenced": False,
        "macros_executed": False,
        "message": message,
        "network_accessed": False,
        "status": "failed",
    }


def _enrich_catalog(
    report: dict[str, Any],
    *,
    run_id: str | None,
    source_id: str,
    source_revision_id: str,
    artifact_paths: list[str],
    counters: dict[str, int] | None = None,
) -> None:
    catalog = report["catalog"]
    catalog["artifact_paths"] = artifact_paths
    if counters is not None:
        catalog["counters"] = counters
    catalog["run_id"] = run_id
    catalog["subject_ids"] = {
        "source_id": source_id,
        "source_revision_id": source_revision_id,
    }


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
