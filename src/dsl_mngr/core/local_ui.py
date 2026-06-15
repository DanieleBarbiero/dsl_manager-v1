from __future__ import annotations

import html
import json
import re
import sqlite3
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, urlencode, urlsplit

from dsl_mngr.core.database import (
    DatabaseConfigurationError,
    DatabaseSettings,
    WorkspaceNotInitializedError,
    resolve_database_settings,
    resolve_workspace_path,
)
from dsl_mngr.core.log_viewer import VIEWER_COLUMNS, record_value, sorted_log_records
from dsl_mngr.core.logging_setup import read_jsonl_logs
from dsl_mngr.core.runs import (
    DatabaseNotReadyError,
    relative_workspace_path,
    run_artifact_paths,
    validate_database_migrations,
)


DEFAULT_UI_HOST = "127.0.0.1"
DEFAULT_UI_PORT = 8765
MAX_LIST_ROWS = 500
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


class LocalUiError(RuntimeError):
    """Raised when the local read-only UI cannot be served."""


class LocalUiWorkspaceError(LocalUiError):
    """Raised when the workspace is not ready for read-only UI access."""


class SafeHtml(str):
    """Small marker for table cells already rendered with escaped HTML."""


@dataclass(frozen=True)
class LocalUiResponse:
    status: int
    headers: tuple[tuple[str, str], ...]
    body: bytes


def create_local_ui_server(
    workspace_dir: str | Path,
    *,
    host: str = DEFAULT_UI_HOST,
    port: int = DEFAULT_UI_PORT,
) -> ThreadingHTTPServer:
    settings = prepare_local_ui_workspace(workspace_dir)
    handler_class = _handler_class(settings.workspace_dir)
    return ThreadingHTTPServer((host, port), handler_class)


def local_ui_url(host: str, port: int) -> str:
    display_host = f"[{host}]" if ":" in host and not host.startswith("[") else host
    return f"http://{display_host}:{port}/"


def prepare_local_ui_workspace(workspace_dir: str | Path) -> DatabaseSettings:
    try:
        settings = resolve_database_settings(workspace_dir)
    except (DatabaseConfigurationError, WorkspaceNotInitializedError) as exc:
        raise LocalUiWorkspaceError(str(exc)) from exc

    if not settings.database_path.is_file():
        raise LocalUiWorkspaceError(
            f"Database is not initialized: {settings.database_path}. "
            "Run 'dsl-manager db init <workspace>' before 'dsl-manager ui serve'."
        )

    connection = open_read_only_database(settings)
    try:
        try:
            validate_database_migrations(connection)
        except DatabaseNotReadyError as exc:
            message = str(exc).replace("dsl-manager run", "dsl-manager ui serve")
            raise LocalUiWorkspaceError(message) from exc
    finally:
        connection.close()
    return settings


def open_read_only_database(settings: DatabaseSettings) -> sqlite3.Connection:
    uri = f"{settings.database_path.resolve().as_uri()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA query_only = ON")
    return connection


def resolve_local_ui_request(
    workspace_dir: str | Path,
    method: str,
    target: str,
) -> LocalUiResponse:
    method_upper = method.upper()
    if method_upper not in {"GET", "HEAD"}:
        return _html_response(
            405,
            "Method Not Allowed",
            _render_page(
                "Method Not Allowed",
                '<p class="empty">Only GET and HEAD are supported.</p>',
                active_path="",
            ),
            method=method_upper,
            extra_headers=(("Allow", "GET, HEAD"),),
        )

    try:
        settings = _validated_settings(workspace_dir)
        parsed = urlsplit(target)
        path = parsed.path or "/"
        query = parse_qs(parsed.query, keep_blank_values=True)
        status, body = _route(settings, path, query)
    except LocalUiWorkspaceError as exc:
        status = 500
        body = _render_page(
            "Workspace Not Ready",
            f'<p class="empty">{_escape(exc)}</p>',
            active_path="",
        )
    except ValueError as exc:
        status = 400
        body = _render_page(
            "Bad Request",
            f'<p class="empty">{_escape(exc)}</p>',
            active_path="",
        )

    return _html_response(status, _status_title(status), body, method=method_upper)


def _validated_settings(workspace_dir: str | Path) -> DatabaseSettings:
    try:
        return prepare_local_ui_workspace(workspace_dir)
    except LocalUiWorkspaceError:
        raise


def _route(
    settings: DatabaseSettings,
    path: str,
    query: dict[str, list[str]],
) -> tuple[int, str]:
    if path == "/":
        return 200, render_dashboard(settings)
    if path == "/runs":
        return 200, render_runs(settings)
    if path.startswith("/runs/"):
        run_id = path.removeprefix("/runs/")
        if not run_id:
            return 404, render_not_found(path)
        return render_run_detail(settings, run_id)
    if path == "/logs":
        return render_logs(settings, query)
    if path == "/rejected-candidates":
        return 200, render_rejected_candidates(settings)
    if path == "/conflicts":
        return 200, render_conflicts(settings)
    if path == "/snapshots":
        return 200, render_snapshots(settings)
    if path == "/diff":
        return render_diff(settings, query)
    return 404, render_not_found(path)


def render_dashboard(settings: DatabaseSettings) -> str:
    with open_read_only_database(settings) as connection:
        validate_database_migrations(connection)
        counts = {
            table_name: _count_rows(connection, table_name)
            for table_name in (
                "sources",
                "source_revisions",
                "chunks",
                "source_fragments",
                "ai_packages",
                "candidate_batches",
                "candidate_records",
                "rejected_candidates",
                "facts",
                "relations",
                "conflicts",
                "dsl_snapshots",
                "graph_exports",
                "runs",
                "worker_runs",
            )
        }
        open_conflicts = connection.execute(
            "SELECT COUNT(*) FROM conflicts WHERE status = 'open'"
        ).fetchone()[0]

    rows = [
        ("Workspace", settings.workspace_dir),
        ("Database", _display_path(settings.workspace_dir, settings.database_path)),
        ("Runs", _link("/runs", counts["runs"])),
        ("Rejected candidates", _link("/rejected-candidates", counts["rejected_candidates"])),
        ("Conflicts", f"{counts['conflicts']} total / {open_conflicts} open"),
        ("DSL snapshots", _link("/snapshots", counts["dsl_snapshots"])),
        ("Facts", counts["facts"]),
        ("Relations", counts["relations"]),
        ("Source revisions", counts["source_revisions"]),
        ("Chunks", counts["chunks"]),
        ("Fragments", counts["source_fragments"]),
        ("AI packages", counts["ai_packages"]),
        ("Graph exports", counts["graph_exports"]),
    ]
    body = "\n".join(
        [
            "<section>",
            "  <h2>Workspace</h2>",
            _definition_list(rows),
            "</section>",
            "<section>",
            "  <h2>Views</h2>",
            "  <ul class=\"link-list\">",
            f"    <li>{_link('/runs', 'Runs')}</li>",
            f"    <li>{_link('/logs', 'Application log')}</li>",
            f"    <li>{_link('/rejected-candidates', 'Rejected candidates')}</li>",
            f"    <li>{_link('/conflicts', 'Conflicts')}</li>",
            f"    <li>{_link('/snapshots', 'DSL snapshots')}</li>",
            f"    <li>{_link('/diff', 'DSL diff')}</li>",
            "  </ul>",
            "</section>",
        ]
    )
    return _render_page("DSL Manager Workspace", body, active_path="/")


def render_runs(settings: DatabaseSettings) -> str:
    with open_read_only_database(settings) as connection:
        validate_database_migrations(connection)
        rows = connection.execute(
            """
            SELECT run_id, run_type, status, started_at, finished_at, parent_run_id
            FROM runs
            ORDER BY started_at DESC, run_id DESC
            LIMIT ?
            """,
            (MAX_LIST_ROWS,),
        ).fetchall()

    table_rows = [
        [
            _link(f"/runs/{quote(row['run_id'], safe='')}", row["run_id"]),
            row["run_type"],
            row["status"],
            row["started_at"],
            row["finished_at"] or "",
            _run_link(row["parent_run_id"]),
            _link("/logs?" + urlencode({"run_id": row["run_id"]}), "log"),
        ]
        for row in rows
    ]
    body = _render_table(
        ("run_id", "run_type", "status", "started_at", "finished_at", "parent_run", "log"),
        table_rows,
        "No runs found.",
    )
    return _render_page("Runs", body, active_path="/runs")


def render_run_detail(settings: DatabaseSettings, run_id: str) -> tuple[int, str]:
    decoded_run_id = _decode_segment(run_id)
    with open_read_only_database(settings) as connection:
        validate_database_migrations(connection)
        run = connection.execute(
            """
            SELECT run_id, run_type, status, started_at, finished_at, parent_run_id,
                   input_json, output_json, created_at, updated_at
            FROM runs
            WHERE run_id = ?
            """,
            (decoded_run_id,),
        ).fetchone()
        if run is None:
            return 404, render_not_found(f"/runs/{decoded_run_id}")
        worker_rows = connection.execute(
            """
            SELECT worker_run_id, worker_name, worker_version, status,
                   input_path, output_path, report_path, log_path,
                   exit_code, duration_ms, started_at, finished_at
            FROM worker_runs
            WHERE run_id = ?
            ORDER BY started_at, worker_run_id
            LIMIT ?
            """,
            (decoded_run_id, MAX_LIST_ROWS),
        ).fetchall()

    artifacts = run_artifact_paths(settings.workspace_dir, decoded_run_id)
    process_report = _read_workspace_text(settings.workspace_dir, artifacts.process_report_path)
    worker_table = _render_table(
        (
            "worker_run_id",
            "worker_name",
            "version",
            "status",
            "input_path",
            "output_path",
            "report_path",
            "log_path",
            "exit_code",
            "duration_ms",
            "started_at",
            "finished_at",
        ),
        [
            [
                row["worker_run_id"],
                row["worker_name"],
                row["worker_version"] or "",
                row["status"],
                _display_path(settings.workspace_dir, row["input_path"] or ""),
                _display_path(settings.workspace_dir, row["output_path"] or ""),
                _display_path(settings.workspace_dir, row["report_path"] or ""),
                _display_path(settings.workspace_dir, row["log_path"] or ""),
                "" if row["exit_code"] is None else row["exit_code"],
                "" if row["duration_ms"] is None else row["duration_ms"],
                row["started_at"],
                row["finished_at"] or "",
            ]
            for row in worker_rows
        ],
        "No worker runs found.",
    )
    body = "\n".join(
        [
            "<section>",
            f"  <h2>{_escape(decoded_run_id)}</h2>",
            _definition_list(
                [
                    ("Type", run["run_type"]),
                    ("Status", run["status"]),
                    ("Started", run["started_at"]),
                    ("Finished", run["finished_at"] or ""),
                    ("Parent run", _run_link(run["parent_run_id"])),
                    ("Artifact dir", artifacts.artifact_dir_relative),
                    ("Run log", _link("/logs?" + urlencode({"run_id": decoded_run_id}), "open")),
                ]
            ),
            "</section>",
            "<section>",
            "  <h2>Input JSON</h2>",
            _json_pre(run["input_json"], "No input JSON recorded."),
            "</section>",
            "<section>",
            "  <h2>Output JSON</h2>",
            _json_pre(run["output_json"], "No output JSON recorded."),
            "</section>",
            "<section>",
            "  <h2>Process report</h2>",
            _json_pre(process_report, "No process report artifact found."),
            "</section>",
            "<section>",
            "  <h2>Worker runs</h2>",
            worker_table,
            "</section>",
        ]
    )
    return 200, _render_page(f"Run {decoded_run_id}", body, active_path="/runs")


def render_logs(
    settings: DatabaseSettings,
    query: dict[str, list[str]],
) -> tuple[int, str]:
    run_id = _first_query_value(query, "run_id")
    if run_id:
        if not _safe_id(run_id):
            raise ValueError("Invalid run_id.")
        log_path = settings.workspace_dir / "artifacts" / "runs" / run_id / "log.jsonl"
        title = f"Log {run_id}"
    else:
        log_path = settings.workspace_dir / "logs" / "app.jsonl"
        title = "Application Log"

    _assert_inside_workspace(settings.workspace_dir, log_path)
    try:
        records = sorted_log_records(read_jsonl_logs(log_path))
    except ValueError as exc:
        body = _render_page(
            title,
            f'<p class="empty">{_escape(exc)}</p>',
            active_path="/logs",
        )
        return 500, body

    display_path = _display_path(settings.workspace_dir, log_path)
    body = "\n".join(
        [
            "<section>",
            f"  <h2>{_escape(title)}</h2>",
            f"  <p class=\"meta\">{_escape(display_path)}</p>",
            _render_log_records(records),
            "</section>",
        ]
    )
    return 200, _render_page(title, body, active_path="/logs")


def render_rejected_candidates(settings: DatabaseSettings) -> str:
    with open_read_only_database(settings) as connection:
        validate_database_migrations(connection)
        rows = connection.execute(
            """
            SELECT batch_id, run_id, line_number, candidate_id, record_type, reason, message
            FROM rejected_candidates
            ORDER BY created_at DESC, batch_id, line_number
            LIMIT ?
            """,
            (MAX_LIST_ROWS,),
        ).fetchall()

    body = _render_table(
        ("batch", "run", "line", "candidate_id", "record_type", "reason", "message"),
        [
            [
                row["batch_id"],
                _run_link(row["run_id"]),
                row["line_number"],
                row["candidate_id"] or "",
                row["record_type"] or "",
                row["reason"],
                row["message"] or "",
            ]
            for row in rows
        ],
        "No rejected candidates found.",
    )
    return _render_page("Rejected Candidates", body, active_path="/rejected-candidates")


def render_conflicts(settings: DatabaseSettings) -> str:
    with open_read_only_database(settings) as connection:
        validate_database_migrations(connection)
        rows = connection.execute(
            """
            SELECT conflict_id, conflict_type, entity_name, property_name,
                   left_fact_id, right_fact_id, left_value, right_value,
                   status, created_at, updated_at
            FROM conflicts
            ORDER BY CASE WHEN status = 'open' THEN 0 ELSE 1 END,
                     updated_at DESC,
                     conflict_id
            LIMIT ?
            """,
            (MAX_LIST_ROWS,),
        ).fetchall()

    body = _render_table(
        (
            "conflict_id",
            "type",
            "entity",
            "property",
            "left_fact",
            "right_fact",
            "left_value",
            "right_value",
            "status",
            "updated_at",
        ),
        [
            [
                row["conflict_id"],
                row["conflict_type"],
                row["entity_name"],
                row["property_name"],
                row["left_fact_id"],
                row["right_fact_id"],
                row["left_value"],
                row["right_value"],
                row["status"],
                row["updated_at"],
            ]
            for row in rows
        ],
        "No conflicts found.",
    )
    return _render_page("Conflicts", body, active_path="/conflicts")


def render_snapshots(settings: DatabaseSettings) -> str:
    with open_read_only_database(settings) as connection:
        validate_database_migrations(connection)
        rows = connection.execute(
            """
            SELECT snapshot_id, run_id, dsl_hash, registry_hash,
                   fact_count, relation_count, conflict_count,
                   status, json_path, yaml_path, markdown_path, created_at
            FROM dsl_snapshots
            ORDER BY created_at DESC, snapshot_id DESC
            LIMIT ?
            """,
            (MAX_LIST_ROWS,),
        ).fetchall()

    body = _render_table(
        (
            "snapshot_id",
            "run",
            "facts",
            "relations",
            "conflicts",
            "dsl_hash",
            "registry_hash",
            "status",
            "json_path",
            "yaml_path",
            "markdown_path",
            "created_at",
        ),
        [
            [
                row["snapshot_id"],
                _run_link(row["run_id"]),
                row["fact_count"],
                row["relation_count"],
                row["conflict_count"],
                _short_hash(row["dsl_hash"]),
                _short_hash(row["registry_hash"]),
                row["status"],
                _display_path(settings.workspace_dir, row["json_path"]),
                _display_path(settings.workspace_dir, row["yaml_path"]),
                _display_path(settings.workspace_dir, row["markdown_path"]),
                row["created_at"],
            ]
            for row in rows
        ],
        "No DSL snapshots found.",
    )
    return _render_page("DSL Snapshots", body, active_path="/snapshots")


def render_diff(
    settings: DatabaseSettings,
    query: dict[str, list[str]],
) -> tuple[int, str]:
    from_snapshot = _first_query_value(query, "from")
    to_snapshot = _first_query_value(query, "to")
    form = _render_diff_form(settings, from_snapshot, to_snapshot)
    if not from_snapshot and not to_snapshot:
        return 200, _render_page("DSL Diff", form, active_path="/diff")
    if not from_snapshot or not to_snapshot:
        body = form + '<p class="empty">Both from and to are required.</p>'
        return 200, _render_page("DSL Diff", body, active_path="/diff")
    if not _safe_id(from_snapshot) or not _safe_id(to_snapshot):
        raise ValueError("Invalid snapshot id.")

    diff_path = _existing_diff_json_path(settings.workspace_dir, from_snapshot, to_snapshot)
    if diff_path is None:
        command = (
            "dsl-manager dsl diff "
            f"{settings.workspace_dir} --from {from_snapshot} --to {to_snapshot}"
        )
        body = "\n".join(
            [
                form,
                '<p class="empty">Diff artifact not found. '
                f"Run <code>{_escape(command)}</code> to produce it.</p>",
            ]
        )
        return 200, _render_page("DSL Diff", body, active_path="/diff")

    raw_text = _read_workspace_text(settings.workspace_dir, diff_path)
    relative_path = relative_workspace_path(settings.workspace_dir, diff_path)
    summary_html = _render_diff_summary(raw_text)
    body = "\n".join(
        [
            form,
            "<section>",
            "  <h2>Existing diff</h2>",
            _definition_list(
                [
                    ("From", from_snapshot),
                    ("To", to_snapshot),
                    ("JSON", relative_path),
                    ("Markdown", _markdown_sibling_path(settings.workspace_dir, diff_path)),
                ]
            ),
            summary_html,
            "  <h3>JSON</h3>",
            _json_pre(raw_text, "Diff JSON is empty."),
            "</section>",
        ]
    )
    return 200, _render_page("DSL Diff", body, active_path="/diff")


def render_not_found(path: str) -> str:
    return _render_page(
        "Not Found",
        f'<p class="empty">No local UI route matches <code>{_escape(path)}</code>.</p>',
        active_path="",
    )


def _handler_class(workspace_dir: Path) -> type[BaseHTTPRequestHandler]:
    class LocalUiRequestHandler(BaseHTTPRequestHandler):
        server_version = "DslManagerLocalUi/1.0"

        def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API.
            self._send_local_ui_response("GET")

        def do_HEAD(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API.
            self._send_local_ui_response("HEAD")

        def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API.
            self._send_local_ui_response("POST")

        def do_PUT(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API.
            self._send_local_ui_response("PUT")

        def do_PATCH(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API.
            self._send_local_ui_response("PATCH")

        def do_DELETE(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API.
            self._send_local_ui_response("DELETE")

        def do_OPTIONS(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API.
            self._send_local_ui_response("OPTIONS")

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _send_local_ui_response(self, method: str) -> None:
            response = resolve_local_ui_request(workspace_dir, method, self.path)
            self.send_response(response.status)
            for header_name, header_value in response.headers:
                self.send_header(header_name, header_value)
            self.end_headers()
            if method != "HEAD":
                self.wfile.write(response.body)

    return LocalUiRequestHandler


def _html_response(
    status: int,
    _title: str,
    body: str,
    *,
    method: str,
    extra_headers: tuple[tuple[str, str], ...] = (),
) -> LocalUiResponse:
    body_bytes = b"" if method == "HEAD" else body.encode("utf-8")
    headers = (
        ("Content-Type", "text/html; charset=utf-8"),
        ("Content-Length", str(len(body_bytes))),
        *extra_headers,
    )
    return LocalUiResponse(status=status, headers=headers, body=body_bytes)


def _render_page(title: str, body: str, *, active_path: str) -> str:
    nav_items = (
        ("/", "Dashboard"),
        ("/runs", "Runs"),
        ("/logs", "Logs"),
        ("/rejected-candidates", "Rejected"),
        ("/conflicts", "Conflicts"),
        ("/snapshots", "Snapshots"),
        ("/diff", "Diff"),
    )
    nav = " ".join(
        _nav_link(href, label, active=active_path == href) for href, label in nav_items
    )
    return "\n".join(
        [
            "<!doctype html>",
            '<html lang="en">',
            "<head>",
            '  <meta charset="utf-8">',
            '  <meta name="viewport" content="width=device-width, initial-scale=1">',
            f"  <title>{_escape(title)}</title>",
            "  <style>",
            "    :root { color-scheme: light; font-family: Arial, sans-serif; }",
            "    body { margin: 0; color: #1f2933; background: #f7f9fb; }",
            "    header { padding: 18px 24px 10px; background: #ffffff; border-bottom: 1px solid #d9e2ec; }",
            "    h1 { margin: 0 0 12px; font-size: 22px; }",
            "    h2 { margin: 20px 0 10px; font-size: 17px; }",
            "    h3 { margin: 16px 0 8px; font-size: 14px; }",
            "    nav a { display: inline-block; margin: 0 8px 8px 0; color: #0b6bcb; text-decoration: none; }",
            "    nav a.active { font-weight: 700; color: #1f2933; }",
            "    main { padding: 4px 24px 28px; }",
            "    section { margin-bottom: 18px; }",
            "    table { width: 100%; border-collapse: collapse; background: #ffffff; font-size: 13px; }",
            "    th, td { border: 1px solid #d9e2ec; padding: 7px 8px; text-align: left; vertical-align: top; }",
            "    th { background: #e9eff5; color: #243b53; position: sticky; top: 0; }",
            "    tr:nth-child(even) td { background: #fbfdff; }",
            "    a { color: #0b6bcb; }",
            "    code, pre { font-family: Consolas, 'Courier New', monospace; }",
            "    pre { overflow: auto; padding: 12px; background: #ffffff; border: 1px solid #d9e2ec; }",
            "    dl { display: grid; grid-template-columns: minmax(140px, 220px) 1fr; gap: 6px 14px; }",
            "    dt { font-weight: 700; color: #243b53; }",
            "    dd { margin: 0; min-width: 0; overflow-wrap: anywhere; }",
            "    form { display: flex; flex-wrap: wrap; gap: 10px; align-items: end; margin: 0 0 12px; }",
            "    label { display: grid; gap: 4px; font-size: 13px; }",
            "    input { padding: 7px 9px; border: 1px solid #b8c2cc; border-radius: 4px; min-width: 190px; }",
            "    button { padding: 8px 12px; border: 1px solid #0b6bcb; border-radius: 4px; background: #0b6bcb; color: white; }",
            "    .empty, .meta { color: #52616b; }",
            "    .link-list { padding-left: 18px; }",
            "  </style>",
            "</head>",
            "<body>",
            "  <header>",
            f"    <h1>{_escape(title)}</h1>",
            f"    <nav>{nav}</nav>",
            "  </header>",
            "  <main>",
            body,
            "  </main>",
            "</body>",
            "</html>",
            "",
        ]
    )


def _nav_link(href: str, label: str, *, active: bool) -> str:
    class_attr = ' class="active"' if active else ""
    return f'<a{class_attr} href="{_escape_attr(href)}">{_escape(label)}</a>'


def _render_table(
    headers: tuple[str, ...],
    rows: list[list[Any]],
    empty_message: str,
) -> str:
    if not rows:
        return f'<p class="empty">{_escape(empty_message)}</p>'
    header_html = "".join(f"<th>{_escape(header)}</th>" for header in headers)
    row_html = []
    for row in rows:
        cells = "".join(_cell(value) for value in row)
        row_html.append(f"    <tr>{cells}</tr>")
    return "\n".join(
        [
            "<table>",
            f"  <thead><tr>{header_html}</tr></thead>",
            "  <tbody>",
            *row_html,
            "  </tbody>",
            "</table>",
        ]
    )


def _cell(value: Any) -> str:
    if isinstance(value, SafeHtml):
        return f"<td>{value}</td>"
    return f"<td>{_escape(value)}</td>"


def _definition_list(rows: list[tuple[str, Any]]) -> str:
    parts = ["<dl>"]
    for term, value in rows:
        rendered_value = value if isinstance(value, SafeHtml) else _escape(value)
        parts.append(f"  <dt>{_escape(term)}</dt><dd>{rendered_value}</dd>")
    parts.append("</dl>")
    return "\n".join(parts)


def _render_log_records(records: list[dict[str, Any]]) -> str:
    rows = [
        [record_value(record, column) for column in VIEWER_COLUMNS]
        for record in records
    ]
    return _render_table(VIEWER_COLUMNS, rows, "No log records found.")


def _render_diff_form(
    settings: DatabaseSettings,
    from_snapshot: str | None,
    to_snapshot: str | None,
) -> str:
    snapshot_options = _snapshot_options(settings)
    datalist = "\n".join(
        f'    <option value="{_escape_attr(snapshot_id)}"></option>'
        for snapshot_id in snapshot_options
    )
    return "\n".join(
        [
            '<form method="get" action="/diff">',
            "  <label>from",
            (
                '    <input name="from" list="snapshot-ids" '
                f'value="{_escape_attr(from_snapshot or "")}">'
            ),
            "  </label>",
            "  <label>to",
            (
                '    <input name="to" list="snapshot-ids" '
                f'value="{_escape_attr(to_snapshot or "")}">'
            ),
            "  </label>",
            '  <button type="submit">Open diff</button>',
            '  <datalist id="snapshot-ids">',
            datalist,
            "  </datalist>",
            "</form>",
        ]
    )


def _snapshot_options(settings: DatabaseSettings) -> list[str]:
    with open_read_only_database(settings) as connection:
        validate_database_migrations(connection)
        rows = connection.execute(
            """
            SELECT snapshot_id
            FROM dsl_snapshots
            ORDER BY created_at DESC, snapshot_id DESC
            LIMIT ?
            """,
            (MAX_LIST_ROWS,),
        ).fetchall()
    return [row["snapshot_id"] for row in rows]


def _render_diff_summary(raw_text: str | None) -> str:
    if not raw_text:
        return ""
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError:
        return '<p class="empty">Diff JSON could not be parsed.</p>'
    if not isinstance(payload, dict):
        return '<p class="empty">Diff JSON is not an object.</p>'
    summary = payload.get("summary")
    metadata = payload.get("metadata")
    rows = []
    if isinstance(metadata, dict):
        rows.extend(
            [
                ("from_snapshot_id", metadata.get("from_snapshot_id", "")),
                ("to_snapshot_id", metadata.get("to_snapshot_id", "")),
                ("has_changes", metadata.get("has_changes", "")),
            ]
        )
    if isinstance(summary, dict):
        rows.extend(
            [
                ("total_changes", summary.get("total_changes", "")),
                ("added", summary.get("added", "")),
                ("removed", summary.get("removed", "")),
                ("modified", summary.get("modified", "")),
            ]
        )
    if not rows:
        return ""
    return "\n".join(["  <h3>Summary</h3>", _definition_list(rows)])


def _existing_diff_json_path(
    workspace_dir: Path,
    from_snapshot: str,
    to_snapshot: str,
) -> Path | None:
    export_dir = resolve_workspace_path(workspace_dir, "exports/dsl_diff")
    candidates = (
        export_dir / f"{from_snapshot}__{to_snapshot}.json",
        export_dir / f"{from_snapshot}_vs_{to_snapshot}.json",
    )
    for candidate in candidates:
        _assert_inside_workspace(workspace_dir, candidate)
        if candidate.is_file():
            return candidate
    return None


def _markdown_sibling_path(workspace_dir: Path, diff_json_path: Path) -> str:
    markdown_path = diff_json_path.with_suffix(".md")
    if markdown_path.is_file():
        return relative_workspace_path(workspace_dir, markdown_path)
    return ""


def _json_pre(raw_json: str | None, empty_message: str) -> str:
    if raw_json in (None, ""):
        return f'<p class="empty">{_escape(empty_message)}</p>'
    try:
        value = json.loads(raw_json)
    except json.JSONDecodeError:
        rendered = raw_json
    else:
        rendered = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
    return f"<pre>{_escape(rendered)}</pre>"


def _read_workspace_text(workspace_dir: Path, path: Path) -> str | None:
    _assert_inside_workspace(workspace_dir, path)
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def _assert_inside_workspace(workspace_dir: Path, path: Path) -> None:
    try:
        path.resolve().relative_to(workspace_dir.resolve())
    except ValueError as exc:
        raise ValueError("Path escapes the workspace.") from exc


def _count_rows(connection: sqlite3.Connection, table_name: str) -> int:
    return int(connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])


def _first_query_value(query: dict[str, list[str]], name: str) -> str | None:
    values = query.get(name, [])
    if not values:
        return None
    value = values[0].strip()
    return value or None


def _safe_id(value: str) -> bool:
    return bool(SAFE_ID_RE.fullmatch(value))


def _decode_segment(value: str) -> str:
    from urllib.parse import unquote

    return unquote(value)


def _run_link(run_id: str | None) -> SafeHtml:
    if not run_id:
        return SafeHtml("")
    return _link(f"/runs/{quote(run_id, safe='')}", run_id)


def _link(href: str, label: Any) -> SafeHtml:
    return SafeHtml(f'<a href="{_escape_attr(href)}">{_escape(label)}</a>')


def _display_path(workspace_dir: Path, value: str | Path) -> str:
    if value in (None, ""):
        return ""
    path_text = str(value).replace("\\", "/")
    path = Path(path_text)
    if path.is_absolute():
        try:
            return path.resolve().relative_to(workspace_dir.resolve()).as_posix()
        except ValueError:
            return path.as_posix()
    return path_text


def _short_hash(value: str) -> str:
    if len(value) <= 16:
        return value
    return f"{value[:12]}..."


def _escape(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return html.escape(str(value), quote=True)


def _escape_attr(value: Any) -> str:
    return _escape(value)


def _status_title(status: int) -> str:
    return {
        200: "OK",
        400: "Bad Request",
        404: "Not Found",
        405: "Method Not Allowed",
        500: "Internal Server Error",
    }.get(status, "Response")
