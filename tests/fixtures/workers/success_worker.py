from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    input_payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    output_payload = {
        "result": {
            "accepted": True,
            "input_keys": sorted(input_payload),
        },
        "run_id": input_payload["run_id"],
        "status": "ok",
        "worker_name": input_payload["worker_name"],
    }
    Path(args.output).write_text(
        json.dumps(output_payload, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print("success worker completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
