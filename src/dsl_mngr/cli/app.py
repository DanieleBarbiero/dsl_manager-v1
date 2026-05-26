from __future__ import annotations

import argparse
from collections.abc import Sequence

from dsl_mngr.cli.commands.db import run_db_init_command
from dsl_mngr.cli.commands.init import run_init_command
from dsl_mngr.cli.commands.log import run_log_table_command


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dsl-manager")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Initialize a local workspace.")
    init_parser.add_argument(
        "workspace",
        nargs="?",
        default=".",
        help="Workspace directory. Defaults to the current directory.",
    )
    init_parser.set_defaults(func=run_init_command)

    db_parser = subparsers.add_parser("db", help="Manage the local SQLite database.")
    db_subparsers = db_parser.add_subparsers(dest="db_command", required=True)
    db_init_parser = db_subparsers.add_parser("init", help="Initialize or migrate SQLite.")
    db_init_parser.add_argument(
        "workspace",
        nargs="?",
        default=".",
        help="Workspace directory. Defaults to the current directory.",
    )
    db_init_parser.set_defaults(func=run_db_init_command)

    log_parser = subparsers.add_parser("log", help="Read application logs.")
    log_subparsers = log_parser.add_subparsers(dest="log_command", required=True)
    table_parser = log_subparsers.add_parser("table", help="Render logs as a table or CSV.")
    table_parser.add_argument(
        "workspace",
        nargs="?",
        default=".",
        help="Workspace directory. Defaults to the current directory.",
    )
    table_parser.add_argument(
        "--format",
        choices=("table", "csv"),
        default="table",
        help="Output format.",
    )
    table_parser.add_argument(
        "--output",
        help="Optional output path. Prints to stdout when omitted.",
    )
    table_parser.set_defaults(func=run_log_table_command)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)
