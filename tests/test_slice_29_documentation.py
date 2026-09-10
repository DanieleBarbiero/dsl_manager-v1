from __future__ import annotations

import argparse
import re
from pathlib import Path
from urllib.parse import unquote

from dsl_mngr.cli.app import build_parser


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
ACTIVE_DOCUMENTS = (
    Path(".kb/documenti/documenti tecnici/analisi_tecnica_dsl_manager.md"),
    Path(".kb/documenti/documenti tecnici/contratti_manifest_dsl_manager.md"),
    Path(".kb/documenti/manuali/manuale_utente_dsl_manager.md"),
    Path(".kb/documenti/manuali/outline_dsl_manager_flow_from_input_to_output_riassunto.md"),
    Path(
        ".kb/projects/corpus aurora/corpus_mock_aurora_prestiti/"
        "materiale_di_supporto/guida_dsl_manager_powershell_v_02.md"
    ),
    Path(
        ".kb/projects/corpus aurora/corpus_mock_aurora_prestiti/"
        "materiale_di_supporto/guida_dsl_manager_cmd_v_02.md"
    ),
    Path(".kb/projects/corpus aurora/prompt_aurora+guida.md"),
    Path(".kb/projects/slicing/slice_29/dsl_manager_slice_29_report.md"),
)
MARKDOWN_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
TABLE_COMMAND = re.compile(r"^\| `([^`]+)` \|", re.MULTILINE)
NON_ZERO_PADDED_ORDERED_PATH = re.compile(
    r"(?:slice_|dsl_manager_slice_)([0-9])(?![0-9])",
    re.IGNORECASE,
)


def _read(relative_path: Path) -> str:
    return (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")


def _leaf_parsers(
    parser: argparse.ArgumentParser,
    prefix: tuple[str, ...] = (),
) -> dict[str, argparse.ArgumentParser]:
    subparser_actions = [
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    ]
    if not subparser_actions:
        return {" ".join(prefix): parser}
    result: dict[str, argparse.ArgumentParser] = {}
    for action in subparser_actions:
        for name, child in action.choices.items():
            result.update(_leaf_parsers(child, (*prefix, name)))
    return result


def test_slice_29_local_links_and_ordered_names_resolve() -> None:
    failures: list[str] = []
    for relative_path in ACTIVE_DOCUMENTS:
        document = REPOSITORY_ROOT / relative_path
        assert document.is_file(), relative_path.as_posix()
        text = document.read_text(encoding="utf-8")
        assert not NON_ZERO_PADDED_ORDERED_PATH.search(text), relative_path.as_posix()
        for match in MARKDOWN_LINK.finditer(text):
            target = match.group(1).strip().strip("<>")
            if target.startswith(("#", "http://", "https://", "mailto:")):
                continue
            local_target = unquote(target.split("#", 1)[0])
            resolved = (document.parent / local_target).resolve()
            if not resolved.exists():
                failures.append(f"{relative_path.as_posix()} -> {target}")
    assert failures == []


def test_slice_29_manual_command_catalog_matches_parser() -> None:
    manual = _read(
        Path(".kb/documenti/manuali/manuale_utente_dsl_manager.md")
    )
    command_section = manual.split("## 4. Catalogo dei comandi pubblici", 1)[1]
    command_section = command_section.split("## 5. Elaborazione per tipo di file", 1)[0]
    documented = set(TABLE_COMMAND.findall(command_section))
    observed = set(_leaf_parsers(build_parser()))
    assert documented == observed


def test_slice_29_documented_options_exist_in_help() -> None:
    parsers = _leaf_parsers(build_parser())
    expected_options = {
        "batch consolidate": {
            "--path",
            "--strict-review",
            "--reconcile",
            "--stop-on-error",
            "--resume",
        },
        "candidates review confirm": {
            "--reason",
            "--actor-id",
            "--expected-head-decision-id",
            "--idempotency-key",
        },
        "candidates review reject": {"--reason", "--actor-id"},
        "candidates review correct": {
            "--reason",
            "--actor-id",
            "--payload",
            "--evidence-ref",
        },
        "ai package": {"--revision", "--profile"},
        "ai package-batch": {"--revision", "--profile", "--stop-on-error"},
        "ai import": {"--package", "--input", "--allow-stale"},
        "facts merge": {"--batch", "--strict-review"},
        "facts reconcile": {"--reconciliation-id", "--strict"},
        "dsl render": {"--output-dir", "--schema-version", "--allow-incomplete"},
        "dsl diff": {"--from", "--to", "--output-dir", "--cross-schema"},
        "graph export": {
            "--snapshot-id",
            "--dynamic",
            "--timeformat",
            "--allow-incomplete",
            "--temporal-output-mode",
        },
    }
    for command, options in expected_options.items():
        help_text = parsers[command].format_help()
        assert options <= set(re.findall(r"--[a-z][a-z-]+", help_text)), command


def test_slice_29_normative_safety_statements_and_known_gaps() -> None:
    consolidated = "\n".join(_read(path) for path in ACTIVE_DOCUMENTS).lower()
    normalized = re.sub(r"\s+", " ", consolidated)
    required = (
        "non è un'approvazione",
        "foglia corrente",
        "non viene convertito",
        "non sono automaticamente verità di dominio",
        "la sola xsd non basta",
        "timestamp del filesystem",
        "--allow-incomplete",
        "schema 1",
        "result_catalog_v1",
        "catalog_version: 1",
        "nodi+archi gexf",
        "migrazioni v7-v10",
    )
    for statement in required:
        assert statement in normalized, statement

    assert not re.search(r"\bpending\s+(?:è|e'|sono)\s+mergeabil", normalized)
    historical_prompt = _read(Path(".kb/projects/corpus aurora/prompt_aurora+guida.md"))
    normalized_prompt = re.sub(r"\s+", " ", historical_prompt)
    assert "questo file conserva la richiesta che ha originato" in normalized_prompt
    assert "riferimenti sotto" in normalized_prompt


def test_slice_29_aurora_v2_guides_cover_governed_ai_handoff() -> None:
    guide_paths = (
        Path(
            ".kb/projects/corpus aurora/corpus_mock_aurora_prestiti/"
            "materiale_di_supporto/guida_dsl_manager_powershell_v_02.md"
        ),
        Path(
            ".kb/projects/corpus aurora/corpus_mock_aurora_prestiti/"
            "materiale_di_supporto/guida_dsl_manager_cmd_v_02.md"
        ),
    )
    required = (
        "ai package",
        "waiting_for_ai_candidates",
        "candidate_schema.json",
        "source_manifest.json",
        "ai_response_aurora_controllata.jsonl",
        "ai inbox scan",
        "ai import",
        "stale allowed: false",
        "cand_aurora_ai_ddl_table_001",
        "cand_aurora_ai_ddl_question_001",
        "aurora-ai-reviewer",
        "facts merge",
        "non esegue questo invio",
    )
    for guide_path in guide_paths:
        guide = _read(guide_path).lower()
        for statement in required:
            assert statement in guide, (guide_path.as_posix(), statement)
