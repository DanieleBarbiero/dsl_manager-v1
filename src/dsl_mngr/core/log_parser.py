from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any


SUPPORTED_LOG_OPTIONS = {
    "output_fragments_jsonl",
    "parser",
    "strict_options_fail_on_unsupported_option",
}

LOG_LINE_RE = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+"
    r"(?P<level>[A-Z]+)\s+"
    r"(?P<component>\S+)\s+"
    r"(?P<message>.*)$"
)
KEY_VALUE_RE = re.compile(r"\b(?P<key>[A-Za-z_][A-Za-z0-9_]*)=(?P<value>[^\s]+)")


class LogParserError(RuntimeError):
    """Raised when log parsing cannot be completed."""


class UnsupportedLogOption(LogParserError):
    """Raised when a strict log profile contains an unsupported option."""

    def __init__(self, option_key: str, message: str | None = None) -> None:
        self.option_key = option_key
        super().__init__(message or f"Unsupported log option: {option_key}.")


@dataclass(frozen=True)
class LogOptions:
    parser: str = "line_regex"
    strict_options_fail_on_unsupported_option: bool = True
    output_fragments_jsonl: bool = True


@dataclass(frozen=True)
class TextSpan:
    text: str
    line_start: int
    line_end: int
    char_start: int
    char_end: int


@dataclass(frozen=True)
class LogEvent:
    timestamp: str
    level: str
    component: str
    event_kind: str
    message: str
    observed_identifiers: dict[str, str]
    span: TextSpan

    def to_dict(self) -> dict[str, Any]:
        return {
            "component": self.component,
            "event_kind": self.event_kind,
            "level": self.level,
            "message": self.message,
            "observed_identifiers": self.observed_identifiers,
            "timestamp": self.timestamp,
        }


@dataclass(frozen=True)
class LogParseResult:
    normalized_text: str
    events: tuple[LogEvent, ...]
    parser: str
    warnings: tuple[dict[str, Any], ...]

    @property
    def event_count(self) -> int:
        return len(self.events)

    @property
    def warning_count(self) -> int:
        return sum(1 for event in self.events if event.level in {"WARN", "WARNING"})

    @property
    def components(self) -> list[str]:
        return sorted({event.component for event in self.events})

    def to_objects(self) -> dict[str, Any]:
        return {
            "events": [event.to_dict() for event in self.events],
            "warnings": list(self.warnings),
        }


def parse_log_options(raw_options: dict[str, Any]) -> LogOptions:
    strict = _as_bool(
        raw_options.get("strict_options_fail_on_unsupported_option", True),
        "strict_options_fail_on_unsupported_option",
    )
    unsupported = sorted(set(raw_options) - SUPPORTED_LOG_OPTIONS)
    if unsupported and strict:
        raise UnsupportedLogOption(unsupported[0], f"unsupported_log_option: {unsupported[0]}")

    parser = str(raw_options.get("parser", "line_regex")).strip().lower()
    if parser != "line_regex":
        raise UnsupportedLogOption("parser", f"unsupported_log_option: parser={parser}")

    return LogOptions(
        parser=parser,
        strict_options_fail_on_unsupported_option=strict,
        output_fragments_jsonl=_as_bool(
            raw_options.get("output_fragments_jsonl", True),
            "output_fragments_jsonl",
        ),
    )


def parse_log_text(text: str, options: LogOptions) -> LogParseResult:
    normalized = normalize_log_newlines(text)
    if not normalized.strip():
        raise LogParserError("Log input is empty.")

    events: list[LogEvent] = []
    warnings: list[dict[str, Any]] = []
    offset = 0
    for line_number, raw_line in enumerate(normalized.splitlines(keepends=True), start=1):
        line_text = raw_line[:-1] if raw_line.endswith("\n") else raw_line
        line_start = offset
        line_end = offset + len(line_text)
        offset += len(raw_line)
        if not line_text.strip():
            continue
        match = LOG_LINE_RE.match(line_text)
        if match is None:
            warnings.append(
                {
                    "code": "invalid_log_line",
                    "line_start": line_number,
                    "line_text_hash": sha256_text(line_text),
                }
            )
            continue
        message = match.group("message").strip()
        events.append(
            LogEvent(
                timestamp=match.group("timestamp"),
                level=match.group("level").upper(),
                component=match.group("component"),
                event_kind=_event_kind(match.group("level"), message),
                message=message,
                observed_identifiers=_observed_identifiers(message),
                span=TextSpan(
                    text=line_text,
                    line_start=line_number,
                    line_end=line_number,
                    char_start=line_start,
                    char_end=line_end,
                ),
            )
        )

    if not events:
        raise LogParserError("No valid log events were found.")

    return LogParseResult(
        normalized_text=normalized,
        events=tuple(events),
        parser=options.parser,
        warnings=tuple(warnings),
    )


def build_fragment_records(
    parse_result: LogParseResult,
    *,
    source_revision_id: str,
    source_hash: str,
    parser_name: str,
    parser_version: str,
    fragment_id_by_sequence: dict[int, str],
    next_fragment_number: int,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    used_fragment_ids = set(fragment_id_by_sequence.values())

    for event in parse_result.events:
        sequence = len(records) + 1
        fragment_id = fragment_id_by_sequence.get(sequence)
        if fragment_id is None:
            fragment_id = _next_fragment_id(next_fragment_number, used_fragment_ids)
            next_fragment_number = int(fragment_id.rsplit("_", 1)[1]) + 1
        used_fragment_ids.add(fragment_id)
        metadata = {
            "component": event.component,
            "event_kind": event.event_kind,
            "level": event.level,
            "message": event.message,
            "object_type": "log_event",
            "observed_identifiers": event.observed_identifiers,
            "parser": parser_name,
            "parser_version": parser_version,
            "source_hash": source_hash,
            "timestamp": event.timestamp,
        }
        records.append(
            {
                "char_end": event.span.char_end,
                "char_start": event.span.char_start,
                "fragment_id": fragment_id,
                "fragment_type": "log_event",
                "line_end": event.span.line_end,
                "line_start": event.span.line_start,
                "metadata": metadata,
                "path_or_selector": f"log/line:{event.span.line_start}",
                "sequence": sequence,
                "source_revision_id": source_revision_id,
                "status": "active",
                "text": event.span.text,
                "text_hash": sha256_text(event.span.text),
            }
        )

    return records


def canonical_fragment_json_line(record: dict[str, Any]) -> str:
    return json.dumps(record, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n"


def fragments_jsonl_content(records: list[dict[str, Any]]) -> str:
    return "".join(canonical_fragment_json_line(record) for record in records)


def fragments_jsonl_hash(records: list[dict[str, Any]]) -> str:
    return sha256_text(fragments_jsonl_content(records))


def normalize_log_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def component_is_batch_like(component: str) -> bool:
    upper = component.upper()
    return upper.startswith(("BATCH", "JOB", "ETL")) or "_BATCH" in upper or "BATCH_" in upper


def _event_kind(level: str, message: str) -> str:
    lowered = message.strip().lower()
    normalized_level = level.upper()
    if lowered.startswith("start"):
        return "start"
    if lowered.startswith("end"):
        return "end"
    if normalized_level in {"WARN", "WARNING"} or "warning" in lowered or "missing" in lowered:
        return "warning"
    if "processed" in lowered:
        return "processed"
    return "unknown"


def _observed_identifiers(message: str) -> dict[str, str]:
    identifiers: dict[str, str] = {}
    for match in KEY_VALUE_RE.finditer(message):
        identifiers[match.group("key")] = match.group("value").rstrip(".,;")
    return identifiers


def _next_fragment_id(start_number: int, used_fragment_ids: set[str]) -> str:
    number = max(1, start_number)
    while True:
        fragment_id = f"FRAG_{number:06d}"
        if fragment_id not in used_fragment_ids:
            return fragment_id
        number += 1


def _as_bool(value: Any, key: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
    raise LogParserError(f"Log option {key} must be a boolean.")
