from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable

from dsl_mngr.core.canonical import canonical_json_artifact_v1
from dsl_mngr.core.config import ProjectConfigError
from dsl_mngr.core.review_config import (
    ReviewConfigError,
    apply_review_profile,
    list_review_profiles_for_workspace,
    set_review_allowlist,
    show_review_configuration,
    validate_review_configuration,
)


def run_config_review_show_command(args: object) -> int:
    return _run(
        Path(getattr(args, "workspace")),
        "review_config_show",
        False,
        show_review_configuration,
    )


def run_config_review_profiles_command(args: object) -> int:
    workspace = Path(getattr(args, "workspace"))
    return _run(
        workspace,
        "review_profiles",
        False,
        lambda current_workspace: {
            "profiles": list_review_profiles_for_workspace(current_workspace)
        },
    )


def run_config_review_apply_profile_command(args: object) -> int:
    profile_id = str(getattr(args, "profile_id"))
    return _run(
        Path(getattr(args, "workspace")),
        "review_profile_applied",
        True,
        lambda workspace: apply_review_profile(
            workspace,
            profile_id=profile_id,
            expected_config_hash=getattr(args, "expect_config_hash", None),
        ),
    )


def run_config_review_set_allowlist_command(args: object) -> int:
    policies = list(getattr(args, "policies", None) or [])
    return _run(
        Path(getattr(args, "workspace")),
        "review_allowlist_set",
        True,
        lambda workspace: set_review_allowlist(
            workspace,
            policies=policies,
            expected_config_hash=getattr(args, "expect_config_hash", None),
        ),
    )


def run_config_validate_command(args: object) -> int:
    return _run(
        Path(getattr(args, "workspace")),
        "config_validated",
        False,
        lambda workspace: validate_review_configuration(
            workspace,
            profile_id=getattr(args, "profile_id", None),
        ),
    )


def _run(
    workspace: Path,
    condition: str,
    mutations: bool,
    operation: Callable[[Path], dict[str, Any]],
) -> int:
    try:
        detail = operation(workspace)
    except (ReviewConfigError, ProjectConfigError, OSError, UnicodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return int(getattr(exc, "exit_code", 2))
    count = len(detail.get("effective_policies", detail.get("policies", detail.get("profiles", []))))
    payload = {
        **detail,
        "artifact_paths": [],
        "catalog_version": "result_catalog_v1",
        "condition": condition,
        "counters": {"items": count},
        "exit_code": 0,
        "mutations": mutations and bool(detail.get("changed", True)),
        "outcome": "success",
        "reason": "success",
        "retryable": False,
        "run_id": None,
        "schema_version": "1",
        "severity": "info",
        "status": "completed",
        "subject_ids": [],
        "summary": f"{condition}: {count} item(s)",
        "workspace": str(workspace.resolve()),
    }
    print(canonical_json_artifact_v1(payload), end="")
    return 0
