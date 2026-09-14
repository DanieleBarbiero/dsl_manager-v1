"""Adapter locale governato per la propagazione temporale di Orione.

L'adapter non legge il database, non contiene SQL e non approva intervalli.
Valida l'interfaccia pubblicata dal laboratorio e delega integralmente al
servizio applicativo ``propagate_temporal_intervals``. L'output e' un singolo
oggetto JSON; gli ID restituiti vanno poi sottoposti alla review CLI comune.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from dsl_mngr.core.temporal import TemporalError
from dsl_mngr.core.temporal_consolidation import propagate_temporal_intervals


POLICIES = ("explicit_copy", "intersection", "aggregation", "conflict")
TARGET_TYPES = ("fact", "relation")
SOURCE_TYPES = ("source_revision", "source_fragment", "candidate_record", "fact", "relation")
SOURCE_PREFIXES = {
    "source_revision": "REV",
    "source_fragment": "FRAG",
    "candidate_record": "CREC",
    "fact": "FACT",
    "relation": "REL",
}
ID_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*_[0-9]{6}$")


class AdapterArgumentError(ValueError):
    """Errore di interfaccia, prima della chiamata al servizio."""


class JsonArgumentParser(argparse.ArgumentParser):
    """Converte anche gli errori argparse nell'unico contratto JSON."""

    def error(self, message: str) -> None:
        raise AdapterArgumentError(message)


def _workspace(value: str) -> Path:
    path = Path(value).expanduser().resolve()
    required = ("configs/project.yaml", "corpus", "artifacts", "workspace.sqlite")
    missing = [name for name in required if not (path / name).exists()]
    if missing:
        raise argparse.ArgumentTypeError(
            f"workspace non inizializzato o incompleto: mancano {', '.join(missing)}"
        )
    return path


def _identifier(label: str, value: str, expected_prefix: str | None = None) -> str:
    if not ID_PATTERN.fullmatch(value):
        raise AdapterArgumentError(f"{label} non ha il formato di un ID DSL Manager: {value}")
    if expected_prefix is not None and not value.startswith(expected_prefix + "_"):
        raise AdapterArgumentError(f"{label} deve iniziare con {expected_prefix}_: {value}")
    return value


def _source_subject(value: str) -> tuple[str, str]:
    subject_type, separator, subject_id = value.partition(":")
    if not separator or not subject_type or not subject_id or ":" in subject_id:
        raise argparse.ArgumentTypeError("--source-subject richiede TYPE:ID")
    if subject_type not in SOURCE_TYPES:
        raise argparse.ArgumentTypeError(
            f"tipo sorgente non ammesso: {subject_type}; usare {', '.join(SOURCE_TYPES)}"
        )
    try:
        _identifier("source-subject ID", subject_id, SOURCE_PREFIXES[subject_type])
    except AdapterArgumentError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc
    return subject_type, subject_id


def _parser() -> argparse.ArgumentParser:
    parser = JsonArgumentParser(
        description="Crea candidati temporal_interval pending tramite il servizio governato DSL Manager."
    )
    parser.add_argument("--workspace", required=True, type=_workspace)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--source-revision-id", required=True)
    parser.add_argument("--target-subject-type", required=True, choices=TARGET_TYPES)
    parser.add_argument("--target-subject-id", required=True)
    parser.add_argument("--source-subject", required=True, action="append", type=_source_subject)
    parser.add_argument("--policy", required=True, choices=POLICIES)
    return parser


def _emit(payload: dict[str, object]) -> None:
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    try:
        args = parser.parse_args(argv)
        run_id = _identifier("run-id", args.run_id, "RUN")
        revision_id = _identifier("source-revision-id", args.source_revision_id, "REV")
        expected_target = "FACT" if args.target_subject_type == "fact" else "REL"
        target_id = _identifier("target-subject-id", args.target_subject_id, expected_target)
        sources = tuple(args.source_subject)
        if not sources:
            raise AdapterArgumentError("almeno un --source-subject e' obbligatorio")
        result = propagate_temporal_intervals(
            args.workspace,
            run_id=run_id,
            source_revision_id=revision_id,
            target_subject_type=args.target_subject_type,
            target_subject_id=target_id,
            source_subjects=sources,
            policy=args.policy,
        )
    except AdapterArgumentError as exc:
        _emit({"status": "error", "reason": "adapter_argument_invalid", "message": str(exc), "exit_code": 2})
        return 2
    except TemporalError as exc:
        exit_code = int(getattr(exc, "exit_code", 3))
        _emit({"status": "error", "reason": exc.reason, "message": str(exc), "exit_code": exit_code})
        return exit_code

    exit_code = 0 if result.candidate_record_ids else 4
    _emit(
        {
            "candidate_record_ids": list(result.candidate_record_ids),
            "conflict_id": result.conflict_id,
            "exit_code": exit_code,
            "policy": result.policy,
            "sources": [f"{kind}:{identifier}" for kind, identifier in sources],
            "status": "candidates_created" if result.candidate_record_ids else "conflict_created",
            "target": {"subject_id": target_id, "subject_type": args.target_subject_type},
        }
    )
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
