from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from dsl_mngr.core.runs import canonical_json, relative_workspace_path


WORKER_NAME = "controlled_partial_normalization"
WORKER_VERSION = "1.0"
SCENARIO_ID = "controlled_partial_success/1"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    input_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve()
    try:
        payload = json.loads(input_path.read_text(encoding="utf-8"))
        nested = payload.get("input")
        worker_input = {**payload, **nested} if isinstance(nested, dict) else payload
        workspace = input_path.parent.parent.parent.parent.resolve()
        result = run_controlled_partial(worker_input, workspace_dir=workspace)
        output_path.write_text(canonical_json(result), encoding="utf-8", newline="\n")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"controlled diagnostic failed: {exc}")
        return 5
    print("controlled partial diagnostic completed")
    return 6


def run_controlled_partial(payload: dict[str, Any], *, workspace_dir: Path) -> dict[str, Any]:
    run_id = _required(payload, "run_id")
    scenario = _required(payload, "scenario")
    if scenario != SCENARIO_ID:
        raise ValueError(f"Unsupported controlled diagnostic scenario: {scenario}")
    source_hash = _required(payload, "source_hash")
    input_path = _relative(workspace_dir, _required(payload, "input_path"))
    output_dir = _relative(workspace_dir, _required(payload, "output_dir"))
    if hashlib.sha256(input_path.read_bytes()).hexdigest() != source_hash:
        raise ValueError("Registered source bytes changed before the diagnostic worker ran.")
    output_dir.mkdir(parents=True, exist_ok=True)

    preview_path = output_dir / "controlled_preview.txt"
    report_path = output_dir / "diagnostic_report.json"
    preview_path.write_text(
        "CONTROLLED PARTIAL SUCCESS\nNo production normalization was published.\n",
        encoding="utf-8",
        newline="\n",
    )
    artifacts = [
        relative_workspace_path(workspace_dir, preview_path),
        relative_workspace_path(workspace_dir, report_path),
    ]
    reasons = [
        "controlled_partial_success",
        "production_state_preserved",
        "retry_not_requested",
    ]
    result = {
        "artifact_paths": artifacts,
        "controlled_simulation": True,
        "exit_code": 6,
        "input_hash": source_hash,
        "macros_executed": False,
        "network_accessed": False,
        "reason": "controlled_partial_success",
        "reasons": reasons,
        "retry": {"attempt": 1, "maximum_attempts": 1, "resume_supported": False},
        "run_id": run_id,
        "scenario": scenario,
        "status": "partial",
        "worker_name": WORKER_NAME,
        "worker_version": WORKER_VERSION,
    }
    report_path.write_text(canonical_json(result), encoding="utf-8", newline="\n")
    return result


def _required(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Missing diagnostic worker field: {key}")
    return value


def _relative(workspace: Path, value: str) -> Path:
    raw = Path(value)
    if raw.is_absolute() or ".." in raw.parts:
        raise ValueError(f"Diagnostic path must be workspace-relative: {value}")
    result = (workspace / raw).resolve()
    result.relative_to(workspace.resolve())
    return result


if __name__ == "__main__":
    raise SystemExit(main())
