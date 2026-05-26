from __future__ import annotations

import csv
import io
import json
from collections.abc import Callable, Iterable
from datetime import datetime
from pathlib import Path
from typing import Any


Clock = Callable[[], datetime]
LOG_COLUMNS = ("timestamp", "level", "event", "message", "run_id", "worker")


def log_event(
    log_path: str | Path,
    *,
    level: str,
    event: str,
    message: str,
    run_id: str | None = None,
    worker: str | None = None,
    clock: Clock | None = None,
) -> dict[str, Any]:
    now = clock() if clock else datetime.now().astimezone()
    record: dict[str, Any] = {
        "timestamp": now.isoformat(timespec="seconds"),
        "level": level.upper(),
        "event": event,
        "message": message,
    }
    if run_id is not None:
        record["run_id"] = run_id
    if worker is not None:
        record["worker"] = worker

    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    return record


def read_jsonl_logs(log_path: str | Path) -> list[dict[str, Any]]:
    path = Path(log_path)
    if not path.exists():
        return []

    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSONL record at line {line_number}: {exc.msg}") from exc
        if isinstance(record, dict):
            records.append(record)
    return records


def render_log_table(records: Iterable[dict[str, Any]]) -> str:
    rows = [_row_values(record) for record in records]
    widths = [
        max(len(column), *(len(row[index]) for row in rows)) if rows else len(column)
        for index, column in enumerate(LOG_COLUMNS)
    ]
    header = " | ".join(column.ljust(widths[index]) for index, column in enumerate(LOG_COLUMNS))
    separator = "-+-".join("-" * width for width in widths)
    body = [" | ".join(value.ljust(widths[index]) for index, value in enumerate(row)) for row in rows]
    return "\n".join([header, separator, *body]) + "\n"


def render_log_csv(records: Iterable[dict[str, Any]]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=LOG_COLUMNS, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for record in records:
        writer.writerow({column: record.get(column, "") for column in LOG_COLUMNS})
    return output.getvalue()


def _row_values(record: dict[str, Any]) -> tuple[str, ...]:
    return tuple(str(record.get(column, "")) for column in LOG_COLUMNS)
