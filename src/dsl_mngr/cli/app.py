from __future__ import annotations

import argparse
from collections.abc import Sequence

from dsl_mngr.cli.commands.candidates import run_candidates_validate_command
from dsl_mngr.cli.commands.corpus import (
    run_corpus_chunk_command,
    run_corpus_normalize_command,
    run_corpus_parse_db_code_command,
    run_corpus_parse_ddl_command,
    run_corpus_parse_log_command,
    run_corpus_parse_xml_form_command,
    run_corpus_scan_command,
)
from dsl_mngr.cli.commands.db import run_db_init_command
from dsl_mngr.cli.commands.dsl import run_dsl_diff_command, run_dsl_render_command
from dsl_mngr.cli.commands.facts import run_facts_merge_command
from dsl_mngr.cli.commands.init import run_init_command
from dsl_mngr.cli.commands.log import run_log_table_command
from dsl_mngr.cli.commands.run import run_start_command, run_status_command


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

    corpus_parser = subparsers.add_parser("corpus", help="Manage source corpus files.")
    corpus_subparsers = corpus_parser.add_subparsers(dest="corpus_command", required=True)
    scan_parser = corpus_subparsers.add_parser("scan", help="Scan active corpus sources.")
    scan_parser.add_argument(
        "workspace",
        nargs="?",
        default=".",
        help="Workspace directory. Defaults to the current directory.",
    )
    scan_parser.add_argument(
        "--path",
        "--corpus-dir",
        dest="corpus_path",
        help="Optional corpus directory path relative to the workspace.",
    )
    scan_parser.set_defaults(func=run_corpus_scan_command)
    normalize_parser = corpus_subparsers.add_parser(
        "normalize",
        help="Normalize a source revision with Docling.",
    )
    normalize_parser.add_argument(
        "workspace",
        help="Workspace directory.",
    )
    normalize_parser.add_argument(
        "--revision",
        required=True,
        help="Source revision id, for example REV_000001.",
    )
    normalize_parser.add_argument(
        "--profile",
        default="docling.no_images",
        help="Worker profile under configs/workers. Defaults to docling.no_images.",
    )
    normalize_parser.set_defaults(func=run_corpus_normalize_command)
    chunk_parser = corpus_subparsers.add_parser(
        "chunk",
        help="Create stable chunks from a normalized source revision.",
    )
    chunk_parser.add_argument(
        "workspace",
        help="Workspace directory.",
    )
    chunk_parser.add_argument(
        "--revision",
        required=True,
        help="Source revision id, for example REV_000001.",
    )
    chunk_parser.add_argument(
        "--profile",
        default="docling.chunking",
        help="Worker profile under configs/workers. Defaults to docling.chunking.",
    )
    chunk_parser.set_defaults(func=run_corpus_chunk_command)
    parse_ddl_parser = corpus_subparsers.add_parser(
        "parse-ddl",
        help="Parse DDL from a source revision into structural fragments.",
    )
    parse_ddl_parser.add_argument(
        "workspace",
        help="Workspace directory.",
    )
    parse_ddl_parser.add_argument(
        "--revision",
        required=True,
        help="Source revision id, for example REV_000001.",
    )
    parse_ddl_parser.add_argument(
        "--profile",
        default="ddl.default",
        help="Worker profile under configs/workers. Defaults to ddl.default.",
    )
    parse_ddl_parser.set_defaults(func=run_corpus_parse_ddl_command)
    parse_xml_form_parser = corpus_subparsers.add_parser(
        "parse-xml-form",
        help="Parse XML forms from a source revision into structural fragments.",
    )
    parse_xml_form_parser.add_argument(
        "workspace",
        help="Workspace directory.",
    )
    parse_xml_form_parser.add_argument(
        "--revision",
        required=True,
        help="Source revision id, for example REV_000001.",
    )
    parse_xml_form_parser.add_argument(
        "--profile",
        default="xml_form.default",
        help="Worker profile under configs/workers. Defaults to xml_form.default.",
    )
    parse_xml_form_parser.set_defaults(func=run_corpus_parse_xml_form_command)
    parse_db_code_parser = corpus_subparsers.add_parser(
        "parse-db-code",
        help="Parse SQL procedures and triggers from a source revision into structural fragments.",
    )
    parse_db_code_parser.add_argument(
        "workspace",
        help="Workspace directory.",
    )
    parse_db_code_parser.add_argument(
        "--revision",
        required=True,
        help="Source revision id, for example REV_000001.",
    )
    parse_db_code_parser.add_argument(
        "--profile",
        default="db_code.default",
        help="Worker profile under configs/workers. Defaults to db_code.default.",
    )
    parse_db_code_parser.set_defaults(func=run_corpus_parse_db_code_command)
    parse_log_parser = corpus_subparsers.add_parser(
        "parse-log",
        help="Parse line-based logs from a source revision into observed event fragments.",
    )
    parse_log_parser.add_argument(
        "workspace",
        help="Workspace directory.",
    )
    parse_log_parser.add_argument(
        "--revision",
        required=True,
        help="Source revision id, for example REV_000001.",
    )
    parse_log_parser.add_argument(
        "--profile",
        default="log.default",
        help="Worker profile under configs/workers. Defaults to log.default.",
    )
    parse_log_parser.set_defaults(func=run_corpus_parse_log_command)

    candidates_parser = subparsers.add_parser("candidates", help="Validate candidate records.")
    candidates_subparsers = candidates_parser.add_subparsers(
        dest="candidates_command",
        required=True,
    )
    validate_parser = candidates_subparsers.add_parser(
        "validate",
        help="Import and validate JSONL candidate records.",
    )
    validate_parser.add_argument(
        "workspace",
        help="Workspace directory.",
    )
    validate_parser.add_argument(
        "--input",
        dest="input_path",
        required=True,
        help="Candidate JSONL path inside the workspace.",
    )
    validate_parser.set_defaults(func=run_candidates_validate_command)

    facts_parser = subparsers.add_parser("facts", help="Merge validated facts and relations.")
    facts_subparsers = facts_parser.add_subparsers(dest="facts_command", required=True)
    facts_merge_parser = facts_subparsers.add_parser(
        "merge",
        help="Merge accepted candidate facts and relations.",
    )
    facts_merge_parser.add_argument(
        "workspace",
        help="Workspace directory.",
    )
    facts_merge_parser.add_argument(
        "--batch",
        dest="batch_id",
        required=True,
        help="Candidate batch id, for example CBATCH_000001.",
    )
    facts_merge_parser.set_defaults(func=run_facts_merge_command)

    dsl_parser = subparsers.add_parser("dsl", help="Render DSL snapshots.")
    dsl_subparsers = dsl_parser.add_subparsers(dest="dsl_command", required=True)
    dsl_render_parser = dsl_subparsers.add_parser(
        "render",
        help="Render the current registry as a DSL snapshot.",
    )
    dsl_render_parser.add_argument(
        "workspace",
        help="Workspace directory.",
    )
    dsl_render_parser.add_argument(
        "--output-dir",
        help="Optional output directory inside the workspace. Defaults to exports/dsl.",
    )
    dsl_render_parser.set_defaults(func=run_dsl_render_command)
    dsl_diff_parser = dsl_subparsers.add_parser(
        "diff",
        help="Compare two persisted DSL snapshots.",
    )
    dsl_diff_parser.add_argument(
        "workspace",
        help="Workspace directory.",
    )
    dsl_diff_parser.add_argument(
        "--from",
        dest="from_snapshot_id",
        required=True,
        help="Source snapshot id, for example DSL_000001.",
    )
    dsl_diff_parser.add_argument(
        "--to",
        dest="to_snapshot_id",
        required=True,
        help="Target snapshot id, for example DSL_000002.",
    )
    dsl_diff_parser.add_argument(
        "--output-dir",
        help="Optional output directory inside the workspace. Defaults to exports/dsl_diff.",
    )
    dsl_diff_parser.set_defaults(func=run_dsl_diff_command)

    run_parser = subparsers.add_parser("run", help="Manage reproducible runs.")
    run_subparsers = run_parser.add_subparsers(dest="run_command", required=True)
    start_parser = run_subparsers.add_parser("start", help="Start a run.")
    start_parser.add_argument(
        "workspace",
        nargs="?",
        default=".",
        help="Workspace directory. Defaults to the current directory.",
    )
    start_parser.add_argument(
        "--type",
        dest="run_type",
        default="test",
        help="Run type. The minimal slice supports at least 'test'.",
    )
    start_parser.add_argument(
        "--parent-run-id",
        help="Optional parent run id.",
    )
    start_parser.set_defaults(func=run_start_command)

    status_parser = run_subparsers.add_parser("status", help="Show run status.")
    status_parser.add_argument(
        "workspace_or_run_id",
        help="Workspace directory, or the run id when workspace is omitted.",
    )
    status_parser.add_argument(
        "run_id",
        nargs="?",
        help="Run id, for example RUN_000001.",
    )
    status_parser.set_defaults(func=run_status_command)

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
