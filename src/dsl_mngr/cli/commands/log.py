from __future__ import annotations

import sys

from dsl_mngr.core.log_viewer import (
    infer_output_format,
    load_log_input,
    render_viewer_csv,
    render_viewer_html,
    render_viewer_table,
    resolve_output_path,
    write_text_output,
)
from dsl_mngr.core.logging_setup import render_log_csv


def run_log_table_command(args: object) -> int:
    target = getattr(args, "target", getattr(args, "workspace", "."))
    explicit_format = getattr(args, "format", None)
    output = getattr(args, "output")

    try:
        log_input = load_log_input(target)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    output_path = resolve_output_path(output, log_input.workspace_dir)
    output_format = infer_output_format(explicit_format, output_path)

    if output_format == "html":
        rendered = render_viewer_html(log_input, output_path=output_path)
    elif output_format == "csv":
        rendered = render_log_csv(log_input.records)
    else:
        rendered = render_viewer_table(log_input.records)

    if output_path:
        write_text_output(output_path, rendered)
    else:
        print(rendered, end="")

    return 0


def run_log_csv_command(args: object) -> int:
    target = getattr(args, "target", ".")
    output = getattr(args, "output")

    try:
        log_input = load_log_input(target)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    output_path = resolve_output_path(output, log_input.workspace_dir)
    rendered = render_viewer_csv(log_input.records)

    if output_path:
        write_text_output(output_path, rendered)
    else:
        print(rendered, end="")

    return 0
