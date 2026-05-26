from __future__ import annotations

from collections.abc import Sequence

from dsl_mngr.cli.app import main as cli_main


def greet() -> str:
    return "hello from dsl_mngr"


def main(argv: Sequence[str] | None = None) -> int:
    return cli_main(argv)
