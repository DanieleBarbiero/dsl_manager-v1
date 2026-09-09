from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path


SUPPORT_DIR = Path(__file__).resolve().parent
CORPUS_ROOT = SUPPORT_DIR.parent
REPOSITORY_ROOT = SUPPORT_DIR.parents[4]
ACTIVE_DOCUMENTS = CORPUS_ROOT / "corpus" / "active" / "documenti" / "nuovi_utili"
CONTROLLED = SUPPORT_DIR / "fixture_controllate"

ORIGINS = {
    "matrice_stati_2025.xlsx": (
        REPOSITORY_ROOT / "tests" / "fixtures" / "slice_24" / "structural_workbook.xlsx",
        "8691d24f3b6748d76a51731e6dfe362733cc26c2b8ea84769339832346754081",
    ),
    "calcolo_rate_macro_2025.xlsm": (
        REPOSITORY_ROOT / "tests" / "fixtures" / "slice_24" / "macro_workbook.xlsm",
        "17f2858e53262098f899180d470a5390c3072ba5415e7d59a3cd9a4b2bd4caf4",
    ),
    "workbook_partial_controllato.xlsx": (
        REPOSITORY_ROOT / "tests" / "fixtures" / "slice_25" / "candidate_workbook.xlsx",
        "751848e1c7c91bf7406a35a88d23b62c2b4f6923fcd5fd5db77290e26b6e0498",
    ),
}
MALFORMED_BYTES = b"PK\x03\x04AURORA_MALFORMED_OOXML\n"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    ACTIVE_DOCUMENTS.mkdir(parents=True, exist_ok=True)
    CONTROLLED.mkdir(parents=True, exist_ok=True)
    for name, (source, expected_hash) in ORIGINS.items():
        actual_hash = sha256(source)
        if actual_hash != expected_hash:
            raise RuntimeError(
                f"Fixture origin changed: {source.as_posix()} "
                f"({actual_hash} != {expected_hash})."
            )
        destination = (
            ACTIVE_DOCUMENTS / name
            if name != "workbook_partial_controllato.xlsx"
            else CONTROLLED / name
        )
        shutil.copyfile(source, destination)

    malformed = CONTROLLED / "workbook_malformed_controllato.xlsx"
    malformed.write_bytes(MALFORMED_BYTES)

    tracked_roots = (CORPUS_ROOT / "corpus" / "active", CONTROLLED)
    entries: dict[str, dict[str, int | str]] = {}
    for root in tracked_roots:
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            relative = path.relative_to(CORPUS_ROOT).as_posix()
            entries[relative] = {
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
    payload = {
        "algorithm": "sha256",
        "files": entries,
        "schema_version": "1",
    }
    (SUPPORT_DIR / "checksums.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


if __name__ == "__main__":
    main()
