from __future__ import annotations

import argparse
import sys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.parse_args()

    print("failure worker stdout")
    print("failure worker stderr", file=sys.stderr)
    return 7


if __name__ == "__main__":
    raise SystemExit(main())
