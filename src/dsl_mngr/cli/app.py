from __future__ import annotations

import argparse
from collections.abc import Sequence

from dsl_mngr.cli.commands.ai import (
    run_ai_import_command,
    run_ai_inbox_scan_command,
    run_ai_package_command,
    run_ai_package_batch_command,
)
from dsl_mngr.cli.commands.batch import (
    run_batch_chunk_dir_command,
    run_batch_process_dir_command,
)
from dsl_mngr.cli.commands.candidates import run_candidates_validate_command
from dsl_mngr.cli.commands.candidates import run_candidates_validate_batch_command
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
from dsl_mngr.cli.commands.facts import run_facts_merge_batch_command
from dsl_mngr.cli.commands.graph import run_graph_export_command
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

    batch_parser = subparsers.add_parser("batch", help="Run batch orchestration commands.")
    batch_subparsers = batch_parser.add_subparsers(dest="batch_command", required=True)
    batch_process_parser = batch_subparsers.add_parser(
        "process-dir",
        help="Scan and process source files in a directory.",
    )
    batch_process_parser.add_argument("workspace", help="Workspace directory.")
    batch_process_parser.add_argument(
        "--path",
        dest="corpus_path",
        default="corpus/active",
        help="Corpus directory path relative to the workspace. Defaults to corpus/active.",
    )
    batch_process_parser.add_argument(
        "--stop-on-error",
        action="store_true",
        help="Stop the batch at the first failed item.",
    )
    batch_process_parser.set_defaults(func=run_batch_process_dir_command)

    batch_chunk_parser = batch_subparsers.add_parser(
        "chunk-dir",
        help="Chunk multiple normalized source revisions.",
    )
    batch_chunk_parser.add_argument("workspace", help="Workspace directory.")
    batch_chunk_parser.add_argument(
        "--revision",
        action="append",
        help="Source revision id to chunk. Can be repeated.",
    )
    batch_chunk_parser.add_argument(
        "--profile",
        default="docling.chunking",
        help="Worker profile under configs/workers. Defaults to docling.chunking.",
    )
    batch_chunk_parser.add_argument(
        "--stop-on-error",
        action="store_true",
        help="Stop the batch at the first failed item.",
    )
    batch_chunk_parser.set_defaults(func=run_batch_chunk_dir_command)

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
    validate_batch_parser = candidates_subparsers.add_parser(
        "validate-batch",
        help="Import and validate multiple JSONL candidate files.",
    )
    validate_batch_parser.add_argument("workspace", help="Workspace directory.")
    validate_batch_parser.add_argument(
        "--input-dir",
        default="ai/inbox",
        help="Candidate input directory inside the workspace. Defaults to ai/inbox.",
    )
    validate_batch_parser.add_argument(
        "--pattern",
        default="*.jsonl",
        help="Glob pattern inside input-dir. Defaults to *.jsonl.",
    )
    validate_batch_parser.add_argument(
        "--stop-on-error",
        action="store_true",
        help="Stop the batch at the first failed item.",
    )
    validate_batch_parser.set_defaults(func=run_candidates_validate_batch_command)

    ai_parser = subparsers.add_parser("ai", help="Prepare and import AI handoff packages.")
    ai_subparsers = ai_parser.add_subparsers(dest="ai_command", required=True)
    ai_package_parser = ai_subparsers.add_parser(
        "package",
        help="Build a deterministic outbox package for an external AI tool.",
    )
    ai_package_parser.add_argument(
        "workspace",
        help="Workspace directory.",
    )
    ai_package_parser.add_argument(
        "--revision",
        action="append",
        help="Source revision id to include. Can be repeated.",
    )
    ai_package_parser.add_argument(
        "--profile",
        default="ai_package.default",
        help="Worker profile under configs/workers. Defaults to ai_package.default.",
    )
    ai_package_parser.set_defaults(func=run_ai_package_command)
    ai_package_batch_parser = ai_subparsers.add_parser(
        "package-batch",
        help="Build one AI package per source revision with active evidence.",
    )
    ai_package_batch_parser.add_argument("workspace", help="Workspace directory.")
    ai_package_batch_parser.add_argument(
        "--revision",
        action="append",
        help="Source revision id to package. Can be repeated.",
    )
    ai_package_batch_parser.add_argument(
        "--profile",
        default="ai_package.default",
        help="Worker profile under configs/workers. Defaults to ai_package.default.",
    )
    ai_package_batch_parser.add_argument(
        "--stop-on-error",
        action="store_true",
        help="Stop the batch at the first failed item.",
    )
    ai_package_batch_parser.set_defaults(func=run_ai_package_batch_command)

    ai_inbox_parser = ai_subparsers.add_parser("inbox", help="Inspect AI inbox files.")
    ai_inbox_subparsers = ai_inbox_parser.add_subparsers(
        dest="ai_inbox_command",
        required=True,
    )
    ai_inbox_scan_parser = ai_inbox_subparsers.add_parser(
        "scan",
        help="List candidate JSONL files and package stale status.",
    )
    ai_inbox_scan_parser.add_argument(
        "workspace",
        help="Workspace directory.",
    )
    ai_inbox_scan_parser.set_defaults(func=run_ai_inbox_scan_command)

    ai_import_parser = ai_subparsers.add_parser(
        "import",
        help="Import externally produced AI candidates from the inbox.",
    )
    ai_import_parser.add_argument(
        "workspace",
        help="Workspace directory.",
    )
    ai_import_parser.add_argument(
        "--package",
        dest="package_id",
        required=True,
        help="AI package id, for example AIPKG_000001.",
    )
    ai_import_parser.add_argument(
        "--input",
        dest="input_path",
        help="Optional candidate JSONL path inside the workspace.",
    )
    ai_import_parser.add_argument(
        "--allow-stale",
        action="store_true",
        help="Import even if the AI package is stale.",
    )
    ai_import_parser.set_defaults(func=run_ai_import_command)

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
    facts_merge_batch_parser = facts_subparsers.add_parser(
        "merge-batch",
        help="Merge multiple completed candidate batches.",
    )
    facts_merge_batch_parser.add_argument("workspace", help="Workspace directory.")
    facts_merge_batch_parser.add_argument(
        "--batch",
        dest="batch_id",
        action="append",
        help="Candidate batch id to merge. Can be repeated.",
    )
    facts_merge_batch_parser.add_argument(
        "--stop-on-error",
        action="store_true",
        help="Stop the batch at the first failed item.",
    )
    facts_merge_batch_parser.set_defaults(func=run_facts_merge_batch_command)

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

    graph_parser = subparsers.add_parser("graph", help="Export graph views from DSL snapshots.")
    graph_subparsers = graph_parser.add_subparsers(dest="graph_command", required=True)
    graph_export_parser = graph_subparsers.add_parser(
        "export",
        help="Export a persisted DSL snapshot as a GEXF graph.",
    )
    graph_export_parser.add_argument(
        "workspace",
        help="Workspace directory.",
    )
    graph_export_parser.add_argument(
        "--snapshot",
        dest="snapshot_id",
        required=True,
        help="DSL snapshot id, for example DSL_000001.",
    )
    graph_export_parser.add_argument(
        "--format",
        default="gexf",
        help="Export format. Only gexf is supported in v1.",
    )
    graph_export_parser.add_argument(
        "--output-dir",
        help="Optional output directory inside the workspace. Defaults to exports/graph.",
    )
    graph_export_parser.add_argument(
        "--strict-orphans",
        action="store_true",
        help="Fail when a relation references a missing entity.",
    )
    graph_export_parser.set_defaults(func=run_graph_export_command)

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
