from __future__ import annotations

import sys
from pathlib import Path

from dsl_mngr.core.local_ui import LocalUiError, create_local_ui_server, local_ui_url


def run_ui_serve_command(args: object) -> int:
    workspace = Path(getattr(args, "workspace"))
    host = getattr(args, "host")
    port = getattr(args, "port")

    try:
        server = create_local_ui_server(workspace, host=host, port=port)
    except (LocalUiError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    effective_port = int(server.server_address[1])
    print(f"Serving DSL Manager UI at {local_ui_url(host, effective_port)}", flush=True)
    print("Press Ctrl+C to stop.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopped.", file=sys.stderr)
        return 0
    finally:
        server.server_close()
    return 0
