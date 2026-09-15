from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from importlib import resources
from pathlib import Path
from typing import Any

from dsl_mngr.core.candidate_derivation import ALL_DERIVATION_RULE_CATALOG
from dsl_mngr.core.canonical import canonical_sha256_v1
from dsl_mngr.core.config import (
    ProjectConfigError,
    load_config,
    parse_simple_yaml,
    resolve_config_text,
)
from dsl_mngr.core.filesystem import replace_file_with_retry, unlink_file_with_retry
from dsl_mngr.core.logging_setup import log_event


BUILTIN_PROFILE_IDS = ("conservative/1",)
_PROFILE_RESOURCE = {"conservative/1": "conservative_1.json"}
_REVIEW_LINE = re.compile(r"^review\s*:\s*(?:#.*)?$")
_POLICY_LINE = re.compile(r"^(?P<indent>[ \t]+)automatic_policies\s*:")


class ReviewConfigError(RuntimeError):
    def __init__(self, message: str, *, reason: str = "review_config_invalid", exit_code: int = 2):
        super().__init__(message)
        self.reason = reason
        self.exit_code = exit_code


def list_review_profiles() -> list[dict[str, Any]]:
    return [_load_profile(profile_id) for profile_id in BUILTIN_PROFILE_IDS]


def list_review_profiles_for_workspace(
    workspace_dir: str | Path,
) -> list[dict[str, Any]]:
    workspace = Path(workspace_dir).resolve()
    _project_config(workspace)
    profiles = list_review_profiles()
    _log(workspace, "review_profiles_listed", "Built-in review profiles listed.")
    return profiles


def show_review_configuration(workspace_dir: str | Path) -> dict[str, Any]:
    workspace = Path(workspace_dir).resolve()
    path, raw = _project_config(workspace)
    resolved = load_config(workspace)
    policies = _validate_policy_list(resolved["review"]["automatic_policies"])
    parsed = parse_simple_yaml(raw)
    review_override = parsed.get("review")
    origin = (
        "workspace"
        if isinstance(review_override, dict) and "automatic_policies" in review_override
        else "default"
    )
    payload = {
        "canonical_order": policies,
        "config_hash": _hash_text(raw),
        "effective_policies": policies,
        "origin": origin,
        "policy_hash": canonical_sha256_v1(policies),
        "project_config_path": str(path),
    }
    _log(workspace, "review_config_shown", f"Review configuration shown ({origin}).")
    return payload


def validate_review_configuration(
    workspace_dir: str | Path,
    *,
    profile_id: str | None = None,
) -> dict[str, Any]:
    workspace = Path(workspace_dir).resolve()
    _, raw = _project_config(workspace)
    resolved = resolve_config_text(workspace, raw)
    policies = _validate_policy_list(resolved["review"]["automatic_policies"])
    profiles = list_review_profiles()
    if profile_id is not None:
        selected = _load_profile(profile_id)
        profiles = [selected]
    payload = {
        "config_hash": _hash_text(raw),
        "policies": policies,
        "policy_hash": canonical_sha256_v1(policies),
        "profiles": profiles,
        "valid": True,
    }
    _log(workspace, "review_config_validated", "Review configuration is valid.")
    return payload


def apply_review_profile(
    workspace_dir: str | Path,
    *,
    profile_id: str,
    expected_config_hash: str | None = None,
) -> dict[str, Any]:
    profile = _load_profile(profile_id)
    result = set_review_allowlist(
        workspace_dir,
        policies=profile["policies"],
        expected_config_hash=expected_config_hash,
    )
    result["profile_id"] = profile_id
    result["profile_hash"] = profile["profile_hash"]
    return result


def set_review_allowlist(
    workspace_dir: str | Path,
    *,
    policies: list[str],
    expected_config_hash: str | None = None,
) -> dict[str, Any]:
    workspace = Path(workspace_dir).resolve()
    path, raw = _project_config(workspace)
    current_hash = _hash_text(raw)
    if expected_config_hash is not None and expected_config_hash != current_hash:
        raise ReviewConfigError(
            "Project configuration changed since it was read.",
            reason="config_hash_mismatch",
            exit_code=4,
        )
    canonical_policies = _validate_policy_list(policies)
    updated = _replace_automatic_policies(raw, canonical_policies)
    resolved = resolve_config_text(workspace, updated)
    _validate_policy_list(resolved["review"]["automatic_policies"])
    changed = updated.encode("utf-8") != raw.encode("utf-8")
    if changed:
        _atomic_write(path, updated)
    new_hash = _hash_text(updated)
    _log(
        workspace,
        "review_allowlist_updated" if changed else "review_allowlist_unchanged",
        f"Review allowlist contains {len(canonical_policies)} policies.",
    )
    return {
        "changed": changed,
        "config_hash": new_hash,
        "effective_policies": canonical_policies,
        "policy_hash": canonical_sha256_v1(canonical_policies),
        "previous_config_hash": current_hash,
    }


def _load_profile(profile_id: str) -> dict[str, Any]:
    resource_name = _PROFILE_RESOURCE.get(profile_id)
    if resource_name is None:
        raise ReviewConfigError(
            f"Unknown built-in review profile: {profile_id}.",
            reason="review_profile_not_found",
        )
    text = (
        resources.files("dsl_mngr.resources.review_profiles")
        .joinpath(resource_name)
        .read_text(encoding="utf-8")
    )
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ReviewConfigError("Built-in review profile is invalid JSON.") from exc
    expected_id, expected_version = profile_id.split("/", 1)
    if (
        not isinstance(payload, dict)
        or payload.get("profile_id") != expected_id
        or payload.get("profile_version") != expected_version
        or not isinstance(payload.get("description"), str)
    ):
        raise ReviewConfigError(f"Built-in review profile is invalid: {profile_id}.")
    policies = _validate_policy_list(payload.get("policies"))
    canonical = {
        "description": payload["description"],
        "policies": policies,
        "profile_id": payload["profile_id"],
        "profile_version": payload["profile_version"],
    }
    return {
        **canonical,
        "id": profile_id,
        "profile_hash": canonical_sha256_v1(canonical),
    }


def _validate_policy_list(value: Any) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise ReviewConfigError("review.automatic_policies must be a list of policy ids.")
    if len(set(value)) != len(value):
        raise ReviewConfigError(
            "review.automatic_policies contains duplicates.",
            reason="review_policy_duplicate",
        )
    policy_contracts = {
        rule.automatic_review_policy: rule
        for rule in ALL_DERIVATION_RULE_CATALOG.values()
    }
    for policy in value:
        contract = policy_contracts.get(policy)
        if contract is None:
            raise ReviewConfigError(
                f"Unknown automatic review policy: {policy}.",
                reason="review_policy_not_found",
            )
        if not contract.automatic_review_allowed:
            raise ReviewConfigError(
                f"Policy is not eligible for automatic review: {policy}.",
                reason="review_policy_not_automatic",
            )
    return sorted(value)


def _project_config(workspace: Path) -> tuple[Path, str]:
    path = workspace / "configs" / "project.yaml"
    if not path.is_file():
        raise ReviewConfigError(f"Project configuration not found: {path}.")
    try:
        return path, path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ReviewConfigError(f"Project configuration cannot be read: {path}.") from exc


def _replace_automatic_policies(text: str, policies: list[str]) -> str:
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines(keepends=True)
    review_index = next(
        (
            index
            for index, line in enumerate(lines)
            if _REVIEW_LINE.match(line.rstrip("\r\n"))
        ),
        None,
    )
    rendered = f"  automatic_policies: {json.dumps(policies, ensure_ascii=False)}{newline}"
    if review_index is None:
        separator = "" if not text or text.endswith(("\n", "\r")) else newline
        return f"{text}{separator}review:{newline}{rendered}"

    section_end = len(lines)
    for index in range(review_index + 1, len(lines)):
        line = lines[index]
        if line.strip() and not line.startswith((" ", "\t", "#")):
            section_end = index
            break
    policy_index = next(
        (
            index
            for index in range(review_index + 1, section_end)
            if _POLICY_LINE.match(lines[index].rstrip("\r\n"))
        ),
        None,
    )
    if policy_index is None:
        lines.insert(section_end, rendered)
        return "".join(lines)

    match = _POLICY_LINE.match(lines[policy_index].rstrip("\r\n"))
    assert match is not None
    rendered = f"{match.group('indent')}automatic_policies: " \
        f"{json.dumps(policies, ensure_ascii=False)}{newline}"
    block_end = policy_index + 1
    while block_end < section_end:
        candidate = lines[block_end]
        stripped = candidate.strip()
        indent = len(candidate) - len(candidate.lstrip(" \t"))
        if stripped.startswith("-") and indent > len(match.group("indent")):
            block_end += 1
            continue
        if not stripped or stripped.startswith("#"):
            block_end += 1
            continue
        break
    preserved_comments = [
        line
        for line in lines[policy_index + 1:block_end]
        if not line.strip() or line.strip().startswith("#")
    ]
    lines[policy_index:block_end] = [rendered, *preserved_comments]
    return "".join(lines)


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        replace_file_with_retry(temporary, path)
    except BaseException:
        try:
            unlink_file_with_retry(temporary, missing_ok=True)
        except OSError:
            pass
        raise
    else:
        unlink_file_with_retry(temporary, missing_ok=True)


def _log(workspace: Path, event: str, message: str) -> None:
    try:
        config = load_config(workspace)
        relative = str(config["logging"]["app_log_path"])
    except (ProjectConfigError, OSError, UnicodeError):
        relative = "logs/app.jsonl"
    log_event(workspace / relative, level="INFO", event=event, message=message)
