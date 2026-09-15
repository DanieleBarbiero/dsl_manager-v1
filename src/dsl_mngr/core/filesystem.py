from __future__ import annotations

import os
import time
from collections.abc import Callable
from pathlib import Path


PERMISSION_ERROR_RETRY_ATTEMPTS = 10
PERMISSION_ERROR_RETRY_INITIAL_DELAY_SECONDS = 0.05
PERMISSION_ERROR_RETRY_MAX_DELAY_SECONDS = 0.5


def replace_file_with_retry(source: Path, destination: Path) -> None:
    """Atomically replace a file, retrying only transient permission failures."""
    _retry_permission_error(lambda: os.replace(source, destination))


def unlink_file_with_retry(path: Path, *, missing_ok: bool = False) -> None:
    """Remove a file, retrying only transient permission failures."""
    _retry_permission_error(lambda: path.unlink(missing_ok=missing_ok))


def _retry_permission_error(operation: Callable[[], None]) -> None:
    delay = PERMISSION_ERROR_RETRY_INITIAL_DELAY_SECONDS
    for attempt in range(PERMISSION_ERROR_RETRY_ATTEMPTS):
        try:
            operation()
            return
        except PermissionError:
            if attempt + 1 == PERMISSION_ERROR_RETRY_ATTEMPTS:
                raise
            time.sleep(delay)
            delay = min(delay * 2, PERMISSION_ERROR_RETRY_MAX_DELAY_SECONDS)
