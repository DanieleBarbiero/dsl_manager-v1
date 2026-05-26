from __future__ import annotations

from pathlib import Path

from dsl_mngr.core.logging_setup import read_jsonl_logs, render_log_csv, render_log_table


def run_log_table_command(args: object) -> int:
    workspace = Path(getattr(args, "workspace"))
    output_format = getattr(args, "format")
    output = getattr(args, "output")

    records = read_jsonl_logs(workspace / "logs" / "app.jsonl")
    rendered = render_log_csv(records) if output_format == "csv" else render_log_table(records)

    if output:
        Path(output).write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")

    return 0
