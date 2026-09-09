from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dsl_mngr.core.canonical import canonical_json_artifact_v1, canonical_json_v1
from dsl_mngr.core.runs import next_id


class WorkbookRegistryError(RuntimeError):
    """Raised when workbook artifacts cannot be persisted safely."""


@dataclass(frozen=True)
class PersistedWorkbook:
    manifest_id: str
    manifest_hash: str
    sheet_count: int
    cell_count: int
    region_count: int
    fragment_count: int


def persist_workbook_output(
    connection: sqlite3.Connection,
    *,
    workspace_dir: Path,
    output: dict[str, Any],
    expected_source_id: str,
    expected_source_revision_id: str,
    expected_source_hash: str,
    timestamp: str,
) -> PersistedWorkbook:
    _require_equal(output, "source_id", expected_source_id)
    _require_equal(output, "source_revision_id", expected_source_revision_id)
    _require_equal(output, "source_hash", expected_source_hash)

    manifest_path_value = _required_relative_path(output, "workbook_manifest_path")
    fragments_path_value = _required_relative_path(output, "workbook_fragments_path")
    _required_relative_path(output, "workbook_report_path")
    manifest_path = _resolve_file(workspace_dir, manifest_path_value)
    fragments_path = _resolve_file(workspace_dir, fragments_path_value)
    manifest_bytes = manifest_path.read_bytes()
    fragments_bytes = fragments_path.read_bytes()
    manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()
    fragments_hash = hashlib.sha256(fragments_bytes).hexdigest()
    _require_equal(output, "workbook_manifest_hash", manifest_hash)
    _require_equal(output, "workbook_fragments_hash", fragments_hash)

    try:
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WorkbookRegistryError("workbook_manifest.json is not valid UTF-8 JSON.") from exc
    if not isinstance(manifest, dict):
        raise WorkbookRegistryError("workbook_manifest.json must contain an object.")
    if manifest_bytes.decode("utf-8") != canonical_json_artifact_v1(manifest):
        raise WorkbookRegistryError("workbook_manifest.json is not canonical_json_v1.")

    fragments = _load_fragments(fragments_bytes)
    source_revision = manifest.get("source_revision")
    if not isinstance(source_revision, dict):
        raise WorkbookRegistryError("Workbook manifest source_revision is invalid.")
    _require_equal(source_revision, "id", expected_source_revision_id)
    _require_equal(source_revision, "content_hash", expected_source_hash)
    _require_equal(manifest, "schema_version", "1")

    sheets = manifest.get("sheets")
    warnings = manifest.get("warnings")
    if not isinstance(sheets, list) or not all(isinstance(item, dict) for item in sheets):
        raise WorkbookRegistryError("Workbook manifest sheets must be a list of objects.")
    if not isinstance(warnings, list) or not all(isinstance(item, dict) for item in warnings):
        raise WorkbookRegistryError("Workbook manifest warnings must be a list of objects.")
    expected_sheet_count = len(sheets)
    expected_cell_count = sum(len(_required_list(sheet, "cells")) for sheet in sheets)
    expected_region_count = sum(len(_required_list(sheet, "regions")) for sheet in sheets)
    if len(fragments) != expected_region_count:
        raise WorkbookRegistryError("Every workbook region must have one fragment.")
    for key, expected in (
        ("workbook_sheet_count", expected_sheet_count),
        ("workbook_cell_count", expected_cell_count),
        ("workbook_region_count", expected_region_count),
        ("workbook_fragment_count", len(fragments)),
    ):
        _require_equal(output, key, expected)

    existing_manifest = connection.execute(
        """
        SELECT manifest_id
        FROM workbook_manifests
        WHERE source_revision_id = ?
        """,
        (expected_source_revision_id,),
    ).fetchone()
    manifest_id = (
        existing_manifest["manifest_id"]
        if existing_manifest is not None
        else next_id(connection, "workbook_manifests", "manifest_id", "WBMAN")
    )
    warnings_json = canonical_json_v1(warnings)
    status = output.get("status")
    if status not in {"completed", "partial"}:
        raise WorkbookRegistryError("Workbook output status is invalid.")
    connection.execute(
        """
        INSERT INTO workbook_manifests (
            manifest_id, source_revision_id, schema_version, content_hash,
            manifest_hash, artifact_path, status, warnings_json
        )
        VALUES (?, ?, '1', ?, ?, ?, ?, ?)
        ON CONFLICT(source_revision_id) DO UPDATE SET
            schema_version = excluded.schema_version,
            content_hash = excluded.content_hash,
            manifest_hash = excluded.manifest_hash,
            artifact_path = excluded.artifact_path,
            status = excluded.status,
            warnings_json = excluded.warnings_json
        """,
        (
            manifest_id,
            expected_source_revision_id,
            expected_source_hash,
            manifest_hash,
            manifest_path_value,
            status,
            warnings_json,
        ),
    )

    existing_sheet_ids = {
        int(row["sheet_index"]): row["sheet_id"]
        for row in connection.execute(
            "SELECT sheet_id, sheet_index FROM workbook_sheets WHERE manifest_id = ?",
            (manifest_id,),
        )
    }
    existing_region_ids = {
        (int(row["sheet_index"]), int(row["ordinal"])): row["region_id"]
        for row in connection.execute(
            """
            SELECT ws.sheet_index, wr.ordinal, wr.region_id
            FROM workbook_regions wr
            JOIN workbook_sheets ws ON ws.sheet_id = wr.sheet_id
            WHERE ws.manifest_id = ?
            """,
            (manifest_id,),
        )
    }
    connection.execute(
        """
        DELETE FROM workbook_regions
        WHERE sheet_id IN (
            SELECT sheet_id FROM workbook_sheets WHERE manifest_id = ?
        )
        """,
        (manifest_id,),
    )
    connection.execute("DELETE FROM workbook_sheets WHERE manifest_id = ?", (manifest_id,))

    fragments_by_id = _persist_fragments(
        connection,
        fragments,
        source_revision_id=expected_source_revision_id,
        source_hash=expected_source_hash,
        manifest_hash=manifest_hash,
        timestamp=timestamp,
    )
    for sheet in sheets:
        sheet_index = _required_non_negative_int(sheet, "index")
        sheet_id = existing_sheet_ids.get(sheet_index)
        if sheet_id is None:
            sheet_id = next_id(connection, "workbook_sheets", "sheet_id", "WBSHEET")
        dimensions = sheet.get("dimensions")
        if not isinstance(dimensions, dict):
            raise WorkbookRegistryError("Workbook sheet dimensions are invalid.")
        connection.execute(
            """
            INSERT INTO workbook_sheets (
                sheet_id, manifest_id, sheet_index, name, visibility,
                relationship_id, part_name, max_row, max_column
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                sheet_id,
                manifest_id,
                sheet_index,
                _required_string(sheet, "name"),
                _required_string(sheet, "visibility"),
                _required_string(sheet, "relationship_id"),
                _required_string(sheet, "part_name"),
                _required_non_negative_int(dimensions, "max_row"),
                _required_non_negative_int(dimensions, "max_column"),
            ),
        )
        for region in _required_list(sheet, "regions"):
            if not isinstance(region, dict):
                raise WorkbookRegistryError("Workbook region must be an object.")
            fragment_id = _required_string(region, "fragment_id")
            if fragment_id not in fragments_by_id:
                raise WorkbookRegistryError("Workbook region fragment_id is unknown.")
            region_ordinal = _required_positive_int(region, "ordinal")
            region_id = existing_region_ids.get((sheet_index, region_ordinal))
            if region_id is None:
                region_id = next_id(
                    connection,
                    "workbook_regions",
                    "region_id",
                    "WBREG",
                )
            connection.execute(
                """
                INSERT INTO workbook_regions (
                    region_id, sheet_id, ordinal, start_cell, end_cell,
                    region_kind, region_hash, fragment_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    region_id,
                    sheet_id,
                    region_ordinal,
                    _required_string(region, "start_cell"),
                    _required_string(region, "end_cell"),
                    _required_string(region, "region_kind"),
                    _required_hash(region, "region_hash"),
                    fragment_id,
                ),
            )

    return PersistedWorkbook(
        manifest_id=manifest_id,
        manifest_hash=manifest_hash,
        sheet_count=expected_sheet_count,
        cell_count=expected_cell_count,
        region_count=expected_region_count,
        fragment_count=len(fragments),
    )


def _load_fragments(data: bytes) -> list[dict[str, Any]]:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise WorkbookRegistryError("Workbook fragments are not UTF-8.") from exc
    fragments: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(keepends=True), start=1):
        if not line.endswith("\n") or line.endswith("\r\n"):
            raise WorkbookRegistryError("Workbook fragment JSONL must use one LF per record.")
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise WorkbookRegistryError(
                f"Workbook fragment line {line_number} is invalid JSON."
            ) from exc
        if not isinstance(payload, dict) or line != canonical_json_v1(payload) + "\n":
            raise WorkbookRegistryError(
                f"Workbook fragment line {line_number} is not canonical_json_v1."
            )
        fragments.append(payload)
    return fragments


def _persist_fragments(
    connection: sqlite3.Connection,
    fragments: list[dict[str, Any]],
    *,
    source_revision_id: str,
    source_hash: str,
    manifest_hash: str,
    timestamp: str,
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    produced_ids: list[str] = []
    for sequence, fragment in enumerate(fragments, start=1):
        fragment_id = _required_string(fragment, "fragment_id")
        if not re.fullmatch(r"FRAG_[0-9]{6}", fragment_id):
            raise WorkbookRegistryError("Workbook fragment_id is invalid.")
        _require_equal(fragment, "fragment_type", "excel_region")
        _require_equal(fragment, "sequence", sequence)
        _require_equal(fragment, "source_revision_id", source_revision_id)
        semantic = {
            key: value
            for key, value in fragment.items()
            if key
            not in {
                "fragment_id",
                "fragment_type",
                "sequence",
                "source_revision_id",
                "fragment_hash",
            }
        }
        semantic_text = canonical_json_v1(semantic)
        semantic_hash = hashlib.sha256(semantic_text.encode("utf-8")).hexdigest()
        _require_equal(fragment, "fragment_hash", semantic_hash)
        locator = fragment.get("locator")
        sheet = fragment.get("sheet")
        if not isinstance(locator, dict) or not isinstance(sheet, dict):
            raise WorkbookRegistryError("Workbook fragment locator or sheet is invalid.")
        path_or_selector = (
            f"{_required_string(locator, 'part_name')}#{_required_string(locator, 'range')}"
        )
        metadata = {
            "detector": fragment.get("detector"),
            "end_cell": _required_string(fragment, "end_cell"),
            "manifest_hash": manifest_hash,
            "object_type": "excel_region",
            "parser": "workbook_manifest",
            "parser_version": "1",
            "region_hash": _required_hash(fragment, "region_hash"),
            "sheet_index": _required_non_negative_int(sheet, "index"),
            "sheet_name": _required_string(sheet, "name"),
            "source_hash": source_hash,
            "start_cell": _required_string(fragment, "start_cell"),
        }
        owner = connection.execute(
            "SELECT source_revision_id, sequence FROM source_fragments WHERE fragment_id = ?",
            (fragment_id,),
        ).fetchone()
        if owner is not None and (
            owner["source_revision_id"] != source_revision_id
            or int(owner["sequence"]) != sequence
        ):
            raise WorkbookRegistryError("Workbook fragment_id belongs to another record.")
        values = (
            fragment_id,
            source_revision_id,
            sequence,
            path_or_selector,
            semantic_text,
            semantic_hash,
            canonical_json_v1(metadata),
        )
        if owner is None:
            connection.execute(
                """
                INSERT INTO source_fragments (
                    fragment_id, source_revision_id, fragment_type, sequence,
                    path_or_selector, line_start, line_end, char_start, char_end,
                    text, text_hash, metadata_json, status, created_at
                )
                VALUES (?, ?, 'excel_region', ?, ?, NULL, NULL, NULL, NULL,
                        ?, ?, ?, 'active', ?)
                """,
                (*values, timestamp),
            )
        else:
            connection.execute(
                """
                UPDATE source_fragments
                SET fragment_type = 'excel_region', path_or_selector = ?,
                    line_start = NULL, line_end = NULL, char_start = NULL,
                    char_end = NULL, text = ?, text_hash = ?, metadata_json = ?,
                    status = 'active'
                WHERE fragment_id = ?
                """,
                (path_or_selector, semantic_text, semantic_hash, canonical_json_v1(metadata), fragment_id),
            )
        produced_ids.append(fragment_id)
        result[fragment_id] = fragment
    if produced_ids:
        placeholders = ",".join("?" for _ in produced_ids)
        connection.execute(
            f"""
            UPDATE source_fragments
            SET status = 'stale'
            WHERE source_revision_id = ? AND fragment_type = 'excel_region'
              AND fragment_id NOT IN ({placeholders})
            """,
            (source_revision_id, *produced_ids),
        )
    else:
        connection.execute(
            """
            UPDATE source_fragments
            SET status = 'stale'
            WHERE source_revision_id = ? AND fragment_type = 'excel_region'
            """,
            (source_revision_id,),
        )
    return result


def _resolve_file(workspace_dir: Path, relative_path: str) -> Path:
    path = (workspace_dir / relative_path).resolve()
    try:
        path.relative_to(workspace_dir.resolve())
    except ValueError as exc:
        raise WorkbookRegistryError("Workbook artifact path escapes the workspace.") from exc
    if not path.is_file():
        raise WorkbookRegistryError(f"Workbook artifact is missing: {relative_path}.")
    return path


def _required_relative_path(payload: dict[str, Any], key: str) -> str:
    value = _required_string(payload, key)
    path = Path(value)
    if path.is_absolute() or "\\" in value or ".." in path.parts:
        raise WorkbookRegistryError(f"Workbook output path is invalid: {key}.")
    return value


def _required_list(payload: dict[str, Any], key: str) -> list[Any]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise WorkbookRegistryError(f"Workbook field must be a list: {key}.")
    return value


def _required_string(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise WorkbookRegistryError(f"Workbook field must be a non-empty string: {key}.")
    return value


def _required_hash(payload: dict[str, Any], key: str) -> str:
    value = _required_string(payload, key)
    if not re.fullmatch(r"[0-9a-f]{64}", value):
        raise WorkbookRegistryError(f"Workbook field must be a SHA-256 hash: {key}.")
    return value


def _required_non_negative_int(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise WorkbookRegistryError(f"Workbook field must be a non-negative integer: {key}.")
    return value


def _required_positive_int(payload: dict[str, Any], key: str) -> int:
    value = _required_non_negative_int(payload, key)
    if value < 1:
        raise WorkbookRegistryError(f"Workbook field must be a positive integer: {key}.")
    return value


def _require_equal(payload: dict[str, Any], key: str, expected: Any) -> None:
    if payload.get(key) != expected:
        raise WorkbookRegistryError(f"Workbook field is incoherent: {key}.")
