from __future__ import annotations

import hashlib
from pathlib import Path

from dsl_mngr.core.config import DEFAULT_CONFIG
from dsl_mngr.core.ooxml_preflight import (
    ExcelLimits,
    acquire_source_once,
    build_workbook_manifest,
    preflight_ooxml,
)


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "fixtures" / "slice_24" / "structural_workbook.xlsx"
GOLDEN = ROOT / "expected" / "expected_slice_24_workbook_manifest.json"


def main() -> int:
    source_hash = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
    limits = ExcelLimits.from_config(dict(DEFAULT_CONFIG["excel"]))
    acquired = acquire_source_once(
        FIXTURE,
        expected_hash=source_hash,
        max_file_bytes=limits.max_file_bytes,
    )
    checked = preflight_ooxml(
        acquired.cursor(),
        original_name=FIXTURE.name,
        source_hash=source_hash,
        limits=limits,
    )
    built = build_workbook_manifest(
        acquired.cursor(),
        preflight=checked,
        source_revision_id="REV_SLICE24_001",
        fragment_id_by_sequence={},
        next_fragment_number=1,
    )
    GOLDEN.write_text(built.manifest_json, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
