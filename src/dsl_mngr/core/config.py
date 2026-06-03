from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any


DEFAULT_CONFIG: dict[str, Any] = {
    "project": {
        "name": "modernization-dsl-workbench-demo",
        "default_language": "it",
        "timezone": "Europe/Rome",
    },
    "database": {
        "path": "workspace.sqlite",
        "wal": True,
        "foreign_keys": True,
    },
    "logging": {
        "app_log_path": "logs/app.jsonl",
        "per_run_logs": True,
        "jsonl": True,
        "level": "INFO",
    },
    "corpus": {
        "active_dir": "corpus/active",
        "incoming_dir": "corpus/incoming",
        "deleted_dir": "corpus/deleted",
        "ignored_dir": "corpus/ignored",
    },
    "ai_handoff": {
        "outbox_dir": "ai/outbox",
        "inbox_dir": "ai/inbox",
        "package_format": "markdown_plus_json",
    },
}


class WorkerProfileError(RuntimeError):
    """Raised when a worker profile cannot be loaded safely."""


ENV_TO_CONFIG_PATH = {
    "MDW_WORKSPACE_DIR": ("workspace", "dir"),
    "MDW_DB_PATH": ("database", "path"),
    "MDW_LOG_LEVEL": ("logging", "level"),
    "MDW_DEFAULT_DOC_PROFILE": ("project", "default_doc_profile"),
    "MDW_AI_OUTBOX": ("ai_handoff", "outbox_dir"),
    "MDW_AI_INBOX": ("ai_handoff", "inbox_dir"),
    "MDW_ENABLE_WAL": ("database", "wal"),
}


def load_config(
    workspace_dir: str | Path,
    cli_options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    workspace_path = Path(workspace_dir)
    config = deepcopy(DEFAULT_CONFIG)

    project_config = workspace_path / "configs" / "project.yaml"
    if project_config.exists():
        _deep_merge(config, parse_simple_yaml(project_config.read_text(encoding="utf-8")))

    env_file = workspace_path / ".env"
    if env_file.exists():
        _apply_env(config, parse_env(env_file.read_text(encoding="utf-8")))

    if cli_options:
        _deep_merge(config, cli_options)

    return config


def load_worker_profile(workspace_dir: str | Path, profile: str) -> dict[str, Any]:
    if not _is_safe_profile_name(profile):
        raise WorkerProfileError(f"Invalid worker profile name: {profile}.")

    profile_path = Path(workspace_dir) / "configs" / "workers" / f"{profile}.yaml"
    if not profile_path.is_file():
        raise WorkerProfileError(f"Worker profile not found: configs/workers/{profile}.yaml.")

    data = parse_simple_yaml(profile_path.read_text(encoding="utf-8"))
    if not isinstance(data.get("worker"), dict):
        raise WorkerProfileError(f"Worker profile {profile} is missing section: worker.")
    if not isinstance(data.get("docling"), dict):
        raise WorkerProfileError(f"Worker profile {profile} is missing section: docling.")
    return data


def parse_env(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _is_safe_profile_name(profile: str) -> bool:
    if not profile or profile in {".", ".."}:
        return False
    path = Path(profile)
    return (
        not path.is_absolute()
        and len(path.parts) == 1
        and "/" not in profile
        and "\\" not in profile
        and ".." not in path.parts
    )


def parse_simple_yaml(text: str) -> dict[str, Any]:
    data: dict[str, Any] = {}
    current_section: str | None = None

    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        if raw_line.startswith((" ", "\t")):
            if current_section is None or ":" not in raw_line:
                continue
            key, value = raw_line.strip().split(":", 1)
            data.setdefault(current_section, {})[key.strip()] = _parse_scalar(value.strip())
            continue
        if raw_line.endswith(":"):
            current_section = raw_line[:-1].strip()
            data.setdefault(current_section, {})
            continue
        if ":" in raw_line:
            key, value = raw_line.split(":", 1)
            data[key.strip()] = _parse_scalar(value.strip())
            current_section = None

    return data


def dump_simple_yaml(data: dict[str, Any]) -> str:
    lines: list[str] = []
    for key, value in data.items():
        if isinstance(value, dict):
            lines.append(f"{key}:")
            for child_key, child_value in value.items():
                lines.append(f"  {child_key}: {_format_scalar(child_value)}")
        else:
            lines.append(f"{key}: {_format_scalar(value)}")
    return "\n".join(lines) + "\n"


def _apply_env(config: dict[str, Any], env_values: dict[str, str]) -> None:
    for env_key, raw_value in env_values.items():
        config_path = ENV_TO_CONFIG_PATH.get(env_key)
        if config_path is None:
            continue
        _set_nested(config, config_path, _parse_scalar(raw_value))


def _deep_merge(target: dict[str, Any], overrides: dict[str, Any]) -> None:
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _deep_merge(target[key], value)
        else:
            target[key] = value


def _set_nested(target: dict[str, Any], keys: tuple[str, ...], value: Any) -> None:
    current = target
    for key in keys[:-1]:
        current = current.setdefault(key, {})
    current[keys[-1]] = value


def _parse_scalar(value: str) -> Any:
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in {"null", "none"}:
        return None
    try:
        return int(value)
    except ValueError:
        return value


def _format_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    return str(value)
