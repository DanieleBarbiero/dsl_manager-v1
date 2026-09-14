from __future__ import annotations

import sys
from collections.abc import Sequence
from typing import TextIO

from dsl_mngr.cli.app import main as cli_main


def greet() -> str:
    return "hello from dsl_mngr"


def main(argv: Sequence[str] | None = None) -> int:
    _configure_utf8_output(sys.stdout)
    _configure_utf8_output(sys.stderr)
    return cli_main(argv)


def _configure_utf8_output(stream: TextIO) -> None:
    reconfigure = getattr(stream, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8", errors="strict")
