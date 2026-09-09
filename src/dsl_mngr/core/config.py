from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any


DEFAULT_CONFIG: dict[str, Any] = {
    "project": {
        "name": "dsl-manager",
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
    "review": {
        "default_actor_id": "",
        "automatic_policies": [],
    },
    "derive": {
        "rule_set_version": "1",
    },
    "excel": {
        "max_file_bytes": 67108864,
        "max_zip_entries": 20000,
        "max_uncompressed_bytes": 536870912,
        "max_compression_ratio": 100,
        "max_xml_part_bytes": 33554432,
        "max_sheets": 256,
        "max_cells": 2000000,
        "max_regions": 10000,
        "max_relationships": 50000,
        "max_output_bytes": 268435456,
        "worker_timeout_seconds": 120,
        "worker_memory_bytes": 1073741824,
    },
    "temporal": {
        "max_evidence_per_source": 100000,
        "max_intervals_per_subject": 1000,
        "default_timeformat": "date",
        "unknown_timezone_policy": "pending",
    },
    "gexf": {
        "schema_version": "1.3",
        "validator_dependency": "lxml==6.1.2",
    },
}


EXCEL_HARD_MAXIMA = {
    "max_file_bytes": 268435456,
    "max_zip_entries": 100000,
    "max_uncompressed_bytes": 2147483648,
    "max_compression_ratio": 1000,
    "max_xml_part_bytes": 134217728,
    "max_sheets": 1024,
    "max_cells": 10000000,
    "max_regions": 50000,
    "max_relationships": 250000,
    "max_output_bytes": 1073741824,
    "worker_timeout_seconds": 600,
    "worker_memory_bytes": 4294967296,
}

TEMPORAL_HARD_MAXIMA = {
    "max_evidence_per_source": 1000000,
    "max_intervals_per_subject": 10000,
}


class WorkerProfileError(RuntimeError):
    """Raised when a worker profile cannot be loaded safely."""


class ProjectConfigError(RuntimeError):
    """Raised when project configuration violates a typed contract."""


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

    _validate_slice_20_config(config)
    _validate_excel_config(config)
    _validate_temporal_config(config)
    _validate_gexf_config(config)
    return config


def load_worker_profile(
    workspace_dir: str | Path,
    profile: str,
    *,
    required_sections: tuple[str, ...] = ("worker", "docling"),
) -> dict[str, Any]:
    if not _is_safe_profile_name(profile):
        raise WorkerProfileError(f"Invalid worker profile name: {profile}.")

    profile_path = Path(workspace_dir) / "configs" / "workers" / f"{profile}.yaml"
    if not profile_path.is_file():
        raise WorkerProfileError(f"Worker profile not found: configs/workers/{profile}.yaml.")

    data = parse_simple_yaml(profile_path.read_text(encoding="utf-8"))
    for section in required_sections:
        if not isinstance(data.get(section), dict):
            raise WorkerProfileError(f"Worker profile {profile} is missing section: {section}.")
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
    if len(value) >= 2 and value[0] == value[-1] == '"':
        try:
            parsed_string = json.loads(value)
        except json.JSONDecodeError:
            return value
        if isinstance(parsed_string, str):
            return parsed_string
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in {"null", "none"}:
        return None
    if value.startswith("[") and value.endswith("]"):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return value
        if isinstance(parsed, list):
            return parsed
    try:
        return int(value)
    except ValueError:
        return value


def _format_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, list):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if isinstance(value, str):
        try:
            int(value)
        except ValueError:
            return value
        return json.dumps(value)
    return str(value)


def _validate_slice_20_config(config: dict[str, Any]) -> None:
    review = config.get("review")
    derive = config.get("derive")
    if not isinstance(review, dict):
        raise ProjectConfigError("review configuration must be a mapping.")
    if not isinstance(review.get("default_actor_id"), str):
        raise ProjectConfigError("review.default_actor_id must be a string.")
    policies = review.get("automatic_policies")
    if not isinstance(policies, list) or not all(
        isinstance(item, str) and item.strip() for item in policies
    ):
        raise ProjectConfigError(
            "review.automatic_policies must be a list of non-empty policy identifiers."
        )
    if not isinstance(derive, dict):
        raise ProjectConfigError("derive configuration must be a mapping.")
    rule_set_version = derive.get("rule_set_version")
    if not isinstance(rule_set_version, str) or not rule_set_version.strip():
        raise ProjectConfigError("derive.rule_set_version must be a non-empty string.")


def _validate_excel_config(config: dict[str, Any]) -> None:
    excel = config.get("excel")
    if not isinstance(excel, dict):
        raise ProjectConfigError("excel configuration must be a mapping.")
    for key, hard_maximum in EXCEL_HARD_MAXIMA.items():
        value = excel.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ProjectConfigError(f"excel.{key} must be a positive integer.")
        if value > hard_maximum:
            raise ProjectConfigError(
                f"excel.{key} exceeds the hard maximum of {hard_maximum}."
            )


def _validate_temporal_config(config: dict[str, Any]) -> None:
    temporal = config.get("temporal")
    if not isinstance(temporal, dict):
        raise ProjectConfigError("temporal configuration must be a mapping.")
    for key, hard_maximum in TEMPORAL_HARD_MAXIMA.items():
        value = temporal.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ProjectConfigError(f"temporal.{key} must be a positive integer.")
        if value > hard_maximum:
            raise ProjectConfigError(
                f"temporal.{key} exceeds the hard maximum of {hard_maximum}."
            )
    if temporal.get("default_timeformat") not in {"date", "dateTime"}:
        raise ProjectConfigError("temporal.default_timeformat must be date or dateTime.")
    if temporal.get("unknown_timezone_policy") != "pending":
        raise ProjectConfigError(
            "temporal.unknown_timezone_policy must remain pending in schema 2."
        )


def _validate_gexf_config(config: dict[str, Any]) -> None:
    gexf = config.get("gexf")
    if not isinstance(gexf, dict):
        raise ProjectConfigError("gexf configuration must be a mapping.")
    if gexf.get("schema_version") != "1.3":
        raise ProjectConfigError("gexf.schema_version must be 1.3.")
    if gexf.get("validator_dependency") != "lxml==6.1.2":
        raise ProjectConfigError("gexf.validator_dependency must be lxml==6.1.2.")
