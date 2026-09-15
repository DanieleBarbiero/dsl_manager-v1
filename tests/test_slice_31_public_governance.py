from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from dsl_mngr.cli.app import build_parser, main
from dsl_mngr.core import filesystem, review_config
from dsl_mngr.core.review_config import (
    ReviewConfigError,
    apply_review_profile,
    set_review_allowlist,
    show_review_configuration,
)
from dsl_mngr.core.workspace import initialize_workspace


def test_slice_31_review_config_retries_transient_replace_permission_error(
    tmp_path, monkeypatch
):
    destination = tmp_path / "project.yaml"
    original_replace = filesystem.os.replace
    replace_calls: list[tuple[Path, Path]] = []
    delays: list[float] = []

    def flaky_replace(temporary: Path, path: Path) -> None:
        replace_calls.append((temporary, path))
        if len(replace_calls) < 3:
            raise PermissionError("temporary Windows config lock")
        original_replace(temporary, path)

    monkeypatch.setattr(filesystem.os, "replace", flaky_replace)
    monkeypatch.setattr(filesystem.time, "sleep", delays.append)

    review_config._atomic_write(destination, "review:\n")

    assert len(replace_calls) == 3
    assert len({temporary for temporary, _ in replace_calls}) == 1
    assert delays == [0.05, 0.1]
    assert destination.read_text(encoding="utf-8") == "review:\n"
    assert not replace_calls[0][0].exists()


def test_slice_31_review_profile_preserves_unrelated_yaml_and_is_noop(tmp_path):
    workspace = tmp_path / "workspace"
    initialize_workspace(workspace)
    project = workspace / "configs" / "project.yaml"
    original = project.read_text(encoding="utf-8")
    project.write_text("# sentinel\n" + original, encoding="utf-8", newline="\n")

    before = show_review_configuration(workspace)
    assert before["effective_policies"] == []
    result = apply_review_profile(
        workspace,
        profile_id="conservative/1",
        expected_config_hash=before["config_hash"],
    )
    updated = project.read_text(encoding="utf-8")
    assert result["changed"] is True
    assert "# sentinel" in updated
    assert "database:" in updated and "excel:" in updated and "temporal:" in updated
    assert len(result["effective_policies"]) == 13
    assert "explicit_excel_reference_pending/1" not in result["effective_policies"]
    replay = apply_review_profile(
        workspace,
        profile_id="conservative/1",
        expected_config_hash=result["config_hash"],
    )
    assert replay["changed"] is False
    assert project.read_text(encoding="utf-8") == updated

    with pytest.raises(ReviewConfigError) as stale:
        set_review_allowlist(
            workspace,
            policies=[],
            expected_config_hash="0" * 64,
        )
    assert stale.value.reason == "config_hash_mismatch"
    assert project.read_text(encoding="utf-8") == updated


def test_slice_31_config_cli_clear_validate_and_entrypoint_parity(tmp_path, capsys):
    workspace = tmp_path / "workspace"
    initialize_workspace(workspace)
    assert main(
        [
            "config",
            "review",
            "apply-profile",
            str(workspace),
            "--profile",
            "conservative/1",
        ]
    ) == 0
    capsys.readouterr()
    assert main(["config", "review", "set-allowlist", str(workspace)]) == 0
    cleared = json.loads(capsys.readouterr().out)
    assert cleared["effective_policies"] == []
    assert main(["config", "validate", str(workspace)]) == 0
    validated = json.loads(capsys.readouterr().out)
    assert validated["valid"] is True
    assert validated["profiles"][0]["id"] == "conservative/1"

    parsed = build_parser().parse_args(
        ["config", "review", "set-allowlist", str(workspace)]
    )
    assert parsed.policies is None
    module = subprocess.run(
        [sys.executable, "-m", "dsl_mngr", "config", "review", "show", str(workspace)],
        check=False,
        capture_output=True,
        text=True,
    )
    console = subprocess.run(
        [
            str(Path(sys.executable).with_name("dsl-manager.exe")),
            "config",
            "review",
            "show",
            str(workspace),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert module.returncode == console.returncode == 0
    assert json.loads(module.stdout) == json.loads(console.stdout)


def test_slice_31_config_rejects_unknown_pending_and_duplicate_policies(tmp_path):
    workspace = tmp_path / "workspace"
    initialize_workspace(workspace)
    with pytest.raises(ReviewConfigError) as unknown:
        set_review_allowlist(workspace, policies=["missing/1"])
    assert unknown.value.reason == "review_policy_not_found"
    with pytest.raises(ReviewConfigError) as pending:
        set_review_allowlist(
            workspace, policies=["explicit_excel_reference_pending/1"]
        )
    assert pending.value.reason == "review_policy_not_automatic"
    with pytest.raises(ReviewConfigError) as duplicate:
        set_review_allowlist(
            workspace,
            policies=["explicit_ddl_table_only/1", "explicit_ddl_table_only/1"],
        )
    assert duplicate.value.reason == "review_policy_duplicate"
