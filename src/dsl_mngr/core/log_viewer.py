from __future__ import annotations

import csv
import html
import io
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dsl_mngr.core.logging_setup import read_jsonl_logs


VIEWER_COLUMNS = (
    "timestamp",
    "level",
    "run_id",
    "worker",
    "event",
    "source_id",
    "source_revision_id",
    "message",
    "duration_ms",
    "exit_code",
)


@dataclass(frozen=True)
class LogInput:
    log_path: Path
    records: list[dict[str, Any]]
    workspace_dir: Path | None
    display_path: str


def load_log_input(target: str | Path) -> LogInput:
    target_path = Path(target).expanduser()
    log_path, workspace_dir = resolve_log_target(target_path)
    display_path = display_log_path(log_path, workspace_dir)
    try:
        records = sorted_log_records(read_jsonl_logs(log_path))
    except ValueError as exc:
        raise ValueError(f"{display_path}: {exc}") from exc
    return LogInput(
        log_path=log_path,
        records=records,
        workspace_dir=workspace_dir,
        display_path=display_path,
    )


def resolve_log_target(target_path: Path) -> tuple[Path, Path | None]:
    if target_path.exists() and target_path.is_dir():
        workspace_dir = target_path.resolve()
        return workspace_dir / "logs" / "app.jsonl", workspace_dir

    if target_path.suffix.lower() != ".jsonl" and not target_path.exists():
        workspace_dir = target_path.resolve()
        return workspace_dir / "logs" / "app.jsonl", workspace_dir

    log_path = target_path.resolve()
    return log_path, infer_workspace_from_log_path(log_path)


def infer_workspace_from_log_path(log_path: Path) -> Path | None:
    if log_path.name == "app.jsonl" and log_path.parent.name == "logs":
        return log_path.parent.parent

    if (
        log_path.name == "log.jsonl"
        and log_path.parent.name.startswith("RUN_")
        and log_path.parent.parent.name == "runs"
        and log_path.parent.parent.parent.name == "artifacts"
    ):
        return log_path.parent.parent.parent.parent

    return None


def display_log_path(log_path: Path, workspace_dir: Path | None) -> str:
    if workspace_dir is None:
        return log_path.as_posix()
    try:
        return log_path.resolve().relative_to(workspace_dir.resolve()).as_posix()
    except ValueError:
        return log_path.name


def resolve_output_path(output: str | Path | None, workspace_dir: Path | None) -> Path | None:
    if output is None:
        return None

    output_path = Path(output).expanduser()
    if output_path.is_absolute() or workspace_dir is None:
        return output_path
    return workspace_dir / output_path


def infer_output_format(explicit_format: str | None, output_path: Path | None) -> str:
    if explicit_format:
        return explicit_format
    if output_path is not None and output_path.suffix.lower() in {".html", ".htm"}:
        return "html"
    return "table"


def write_text_output(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def sorted_log_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    indexed = list(enumerate(records))
    indexed.sort(key=lambda item: _record_sort_key(item[0], item[1]))
    return [record for _, record in indexed]


def render_viewer_table(records: list[dict[str, Any]]) -> str:
    rows = [[record_value(record, column) for column in VIEWER_COLUMNS] for record in records]
    widths = [
        max(len(column), *(len(row[index]) for row in rows)) if rows else len(column)
        for index, column in enumerate(VIEWER_COLUMNS)
    ]
    header = " | ".join(column.ljust(widths[index]) for index, column in enumerate(VIEWER_COLUMNS))
    separator = "-+-".join("-" * width for width in widths)
    body = [" | ".join(value.ljust(widths[index]) for index, value in enumerate(row)) for row in rows]
    return "\n".join([header, separator, *body]) + "\n"


def render_viewer_csv(records: list[dict[str, Any]]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=VIEWER_COLUMNS, lineterminator="\n")
    writer.writeheader()
    for record in records:
        writer.writerow({column: record_value(record, column) for column in VIEWER_COLUMNS})
    return output.getvalue()


def render_viewer_html(
    log_input: LogInput,
    *,
    output_path: Path | None = None,
) -> str:
    rows = [_render_html_row(record, log_input.workspace_dir, output_path) for record in log_input.records]
    if not rows:
        rows.append(
            '<tr class="empty-row"><td colspan="11">No log records.</td></tr>'
        )

    headers = "".join(f"<th>{html.escape(column)}</th>" for column in (*VIEWER_COLUMNS, "artifacts"))
    return "\n".join(
        [
            "<!doctype html>",
            '<html lang="en">',
            "<head>",
            '  <meta charset="utf-8">',
            "  <title>DSL Manager Log Viewer</title>",
            "  <style>",
            "    :root { color-scheme: light; font-family: Arial, sans-serif; }",
            "    body { margin: 24px; color: #1f2933; background: #f7f9fb; }",
            "    h1 { margin: 0 0 6px; font-size: 22px; font-weight: 700; }",
            "    .meta { margin: 0 0 18px; color: #52616b; font-size: 13px; }",
            "    input { box-sizing: border-box; width: min(520px, 100%); padding: 8px 10px; border: 1px solid #b8c2cc; border-radius: 4px; margin-bottom: 14px; }",
            "    table { width: 100%; border-collapse: collapse; background: #ffffff; font-size: 13px; }",
            "    th, td { border: 1px solid #d9e2ec; padding: 7px 8px; text-align: left; vertical-align: top; }",
            "    th { background: #e9eff5; color: #243b53; position: sticky; top: 0; }",
            "    tr:nth-child(even) td { background: #fbfdff; }",
            "    .level { font-weight: 700; }",
            "    .level-info { color: #0b6bcb; }",
            "    .level-warning, .level-warn { color: #9a5b00; }",
            "    .level-error, .level-critical { color: #b42318; }",
            "    .level-debug { color: #52616b; }",
            "    .artifacts a { margin-right: 8px; color: #0b6bcb; }",
            "    .empty-row td { color: #52616b; text-align: center; }",
            "  </style>",
            "</head>",
            "<body>",
            "  <h1>DSL Manager Log Viewer</h1>",
            f'  <p class="meta">{html.escape(log_input.display_path)}</p>',
            '  <input type="search" data-log-filter placeholder="Filter logs" aria-label="Filter logs">',
            "  <table>",
            f"    <thead><tr>{headers}</tr></thead>",
            "    <tbody>",
            *rows,
            "    </tbody>",
            "  </table>",
            "  <script>",
            "    const filter = document.querySelector('[data-log-filter]');",
            "    const rows = Array.from(document.querySelectorAll('tbody tr[data-search]'));",
            "    filter.addEventListener('input', () => {",
            "      const needle = filter.value.toLowerCase();",
            "      for (const row of rows) {",
            "        row.hidden = !row.dataset.search.includes(needle);",
            "      }",
            "    });",
            "  </script>",
            "</body>",
            "</html>",
            "",
        ]
    )


def record_value(record: dict[str, Any], column: str) -> str:
    if column == "event":
        value = record.get("event", record.get("event_type", ""))
    else:
        value = record.get(column, "")
    return stringify_value(value)


def stringify_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return str(value)


def _render_html_row(
    record: dict[str, Any],
    workspace_dir: Path | None,
    output_path: Path | None,
) -> str:
    values = [record_value(record, column) for column in VIEWER_COLUMNS]
    search_text = " ".join(values).lower()
    cells = []
    for column, value in zip(VIEWER_COLUMNS, values, strict=True):
        if column == "level":
            level_class = _level_class(value)
            cells.append(
                f'<td class="level {level_class}">{html.escape(value)}</td>'
            )
        else:
            cells.append(f"<td>{html.escape(value)}</td>")
    cells.append(
        f'<td class="artifacts">{_render_artifact_links(record, workspace_dir, output_path)}</td>'
    )
    return (
        f'      <tr data-search="{html.escape(search_text, quote=True)}">'
        f'{"".join(cells)}</tr>'
    )


def _render_artifact_links(
    record: dict[str, Any],
    workspace_dir: Path | None,
    output_path: Path | None,
) -> str:
    run_id = stringify_value(record.get("run_id", ""))
    if not run_id or workspace_dir is None:
        return ""

    run_dir = workspace_dir / "artifacts" / "runs" / run_id
    links = []
    for filename, label in (
        ("process_report.json", "report"),
        ("log.jsonl", "log"),
    ):
        artifact_path = run_dir / filename
        if artifact_path.exists():
            href = _relative_href(artifact_path, workspace_dir, output_path)
            links.append(
                f'<a href="{html.escape(href, quote=True)}">{html.escape(label)}</a>'
            )
    return " ".join(links)


def _relative_href(artifact_path: Path, workspace_dir: Path, output_path: Path | None) -> str:
    base_dir = output_path.parent if output_path is not None else workspace_dir
    try:
        relative_path = os.path.relpath(artifact_path.resolve(), base_dir.resolve())
    except ValueError:
        relative_path = artifact_path.resolve().relative_to(workspace_dir.resolve()).as_posix()
    return relative_path.replace(os.sep, "/")


def _level_class(level: str) -> str:
    normalized = "".join(character.lower() for character in level if character.isalnum() or character == "_")
    if not normalized:
        normalized = "unknown"
    return f"level-{normalized}"


def _record_sort_key(index: int, record: dict[str, Any]) -> tuple[int, str, int]:
    timestamp = stringify_value(record.get("timestamp", ""))
    try:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        return (1, timestamp, index)

    if parsed.tzinfo is not None:
        sortable = parsed.astimezone(timezone.utc).isoformat()
    else:
        sortable = parsed.isoformat()
    return (0, sortable, index)
