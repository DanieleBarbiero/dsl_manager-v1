from __future__ import annotations

import tomllib
from importlib.metadata import version as distribution_version
from pathlib import Path

import pytest

from dsl_mngr import __version__
from dsl_mngr.cli.app import build_parser


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_DOCUMENTS = (
    Path(".kb/documenti/documenti tecnici/analisi_tecnica_dsl_manager.md"),
    Path(".kb/documenti/documenti tecnici/contratti_manifest_dsl_manager.md"),
    Path(".kb/documenti/manuali/manuale_utente_dsl_manager.md"),
    Path(".kb/documenti/manuali/outline_dsl_manager_flow_from_input_to_output_riassunto.md"),
)


def _project_version() -> str:
    with (REPOSITORY_ROOT / "pyproject.toml").open("rb") as stream:
        pyproject = tomllib.load(stream)
    return str(pyproject["project"]["version"])


def test_release_version_has_one_runtime_source() -> None:
    expected = _project_version()

    assert distribution_version("dsl_mngr") == expected
    assert __version__ == expected


def test_canonical_documents_reference_the_release() -> None:
    marker = f"Release applicativa di riferimento: **{_project_version()}**."

    for relative_path in CANONICAL_DOCUMENTS:
        text = (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        assert marker in text, relative_path.as_posix()


def test_cli_version_matches_the_release(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exit_info:
        build_parser().parse_args(["--version"])

    assert exit_info.value.code == 0
    assert capsys.readouterr().out.strip() == f"dsl-manager {_project_version()}"
