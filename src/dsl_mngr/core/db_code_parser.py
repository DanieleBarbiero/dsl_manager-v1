from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

from dsl_mngr.core.ddl_parser import strip_sql_comments_preserving_offsets


SUPPORTED_DB_CODE_OPTIONS = {
    "dialect",
    "output_fragments_jsonl",
    "parse_calls",
    "parse_procedures",
    "parse_triggers",
    "parse_update_statements",
    "strict_options_fail_on_unsupported_option",
}

IDENTIFIER_RE = r"[A-Za-z_][A-Za-z0-9_$#]*(?:\.[A-Za-z_][A-Za-z0-9_$#]*)*"

SQL_KEYWORDS = {
    "AND",
    "AS",
    "BEGIN",
    "BETWEEN",
    "BY",
    "CALL",
    "CASE",
    "CURRENT_DATE",
    "CURRENT_TIMESTAMP",
    "DATE",
    "DELETE",
    "ELSE",
    "END",
    "EXEC",
    "EXISTS",
    "FOR",
    "FROM",
    "IF",
    "IN",
    "INSERT",
    "INTO",
    "IS",
    "LIKE",
    "NEW",
    "NOT",
    "NULL",
    "OF",
    "OLD",
    "ON",
    "OR",
    "ROW",
    "SELECT",
    "SET",
    "THEN",
    "UPDATE",
    "WHEN",
    "WHERE",
}


class DbCodeParserError(RuntimeError):
    """Raised when SQL code parsing cannot be completed."""


class UnsupportedDbCodeOption(DbCodeParserError):
    """Raised when a strict SQL code profile contains an unsupported option."""

    def __init__(self, option_key: str, message: str | None = None) -> None:
        self.option_key = option_key
        super().__init__(message or f"Unsupported SQL code option: {option_key}.")


@dataclass(frozen=True)
class DbCodeOptions:
    dialect: str = "generic_sql"
    parse_triggers: bool = True
    parse_procedures: bool = True
    parse_update_statements: bool = True
    parse_calls: bool = True
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
class SqlStatement:
    statement_kind: str
    parent_object_name: str
    parent_object_type: str
    reads: tuple[str, ...]
    writes: tuple[str, ...]
    calls: tuple[str, ...]
    span: TextSpan

    def to_dict(self) -> dict[str, Any]:
        return {
            "calls": list(self.calls),
            "parent_object_name": self.parent_object_name,
            "parent_object_type": self.parent_object_type,
            "reads": list(self.reads),
            "statement_kind": self.statement_kind,
            "writes": list(self.writes),
        }


@dataclass(frozen=True)
class SqlTrigger:
    trigger_name: str
    trigger_timing: str
    trigger_event: str
    target_table: str
    reads: tuple[str, ...]
    writes: tuple[str, ...]
    calls: tuple[str, ...]
    statements: tuple[SqlStatement, ...]
    span: TextSpan

    def to_dict(self) -> dict[str, Any]:
        return {
            "calls": list(self.calls),
            "reads": list(self.reads),
            "statements": [statement.to_dict() for statement in self.statements],
            "target_table": self.target_table,
            "trigger_event": self.trigger_event,
            "trigger_name": self.trigger_name,
            "trigger_timing": self.trigger_timing,
            "writes": list(self.writes),
        }


@dataclass(frozen=True)
class SqlProcedure:
    procedure_name: str
    parameters: tuple[str, ...]
    reads: tuple[str, ...]
    writes: tuple[str, ...]
    calls: tuple[str, ...]
    statements: tuple[SqlStatement, ...]
    span: TextSpan

    def to_dict(self) -> dict[str, Any]:
        return {
            "calls": list(self.calls),
            "parameters": list(self.parameters),
            "procedure_name": self.procedure_name,
            "reads": list(self.reads),
            "statements": [statement.to_dict() for statement in self.statements],
            "writes": list(self.writes),
        }


@dataclass(frozen=True)
class DbCodeParseResult:
    dialect: str
    normalized_text: str
    triggers: tuple[SqlTrigger, ...]
    procedures: tuple[SqlProcedure, ...]
    warnings: tuple[dict[str, Any], ...]

    @property
    def trigger_count(self) -> int:
        return len(self.triggers)

    @property
    def procedure_count(self) -> int:
        return len(self.procedures)

    @property
    def statement_count(self) -> int:
        return sum(len(trigger.statements) for trigger in self.triggers) + sum(
            len(procedure.statements) for procedure in self.procedures
        )

    @property
    def reads(self) -> list[str]:
        values = [
            *[read for trigger in self.triggers for read in trigger.reads],
            *[read for procedure in self.procedures for read in procedure.reads],
        ]
        return _ordered_unique(values)

    @property
    def writes(self) -> list[str]:
        values = [
            *[write for trigger in self.triggers for write in trigger.writes],
            *[write for procedure in self.procedures for write in procedure.writes],
        ]
        return _ordered_unique(values)

    @property
    def calls(self) -> list[str]:
        values = [
            *[call for trigger in self.triggers for call in trigger.calls],
            *[call for procedure in self.procedures for call in procedure.calls],
        ]
        return _ordered_unique(values)

    def to_objects(self) -> dict[str, Any]:
        return {
            "procedures": [procedure.to_dict() for procedure in self.procedures],
            "triggers": [trigger.to_dict() for trigger in self.triggers],
            "warnings": list(self.warnings),
        }


def parse_db_code_options(raw_options: dict[str, Any]) -> DbCodeOptions:
    strict = _as_bool(
        raw_options.get("strict_options_fail_on_unsupported_option", True),
        "strict_options_fail_on_unsupported_option",
    )
    unsupported = sorted(set(raw_options) - SUPPORTED_DB_CODE_OPTIONS)
    if unsupported and strict:
        raise UnsupportedDbCodeOption(
            unsupported[0],
            f"unsupported_db_code_option: {unsupported[0]}",
        )

    dialect = str(raw_options.get("dialect", "generic_sql")).strip().lower()
    if dialect != "generic_sql":
        raise UnsupportedDbCodeOption("dialect", f"unsupported_db_code_option: dialect={dialect}")

    return DbCodeOptions(
        dialect=dialect,
        parse_triggers=_as_bool(raw_options.get("parse_triggers", True), "parse_triggers"),
        parse_procedures=_as_bool(raw_options.get("parse_procedures", True), "parse_procedures"),
        parse_update_statements=_as_bool(
            raw_options.get("parse_update_statements", True),
            "parse_update_statements",
        ),
        parse_calls=_as_bool(raw_options.get("parse_calls", True), "parse_calls"),
        strict_options_fail_on_unsupported_option=strict,
        output_fragments_jsonl=_as_bool(
            raw_options.get("output_fragments_jsonl", True),
            "output_fragments_jsonl",
        ),
    )


def parse_db_code_text(text: str, options: DbCodeOptions) -> DbCodeParseResult:
    normalized = normalize_sql_newlines(text)
    if not normalized.strip():
        raise DbCodeParserError("SQL code input is empty.")

    cleaned = strip_sql_comments_preserving_offsets(normalized)
    objects = _find_create_objects(cleaned)
    triggers: list[SqlTrigger] = []
    procedures: list[SqlProcedure] = []
    warnings: list[dict[str, Any]] = []

    for object_kind, start, end in objects:
        if object_kind == "trigger":
            if options.parse_triggers:
                triggers.append(_parse_trigger(normalized, cleaned, start, end, options))
            continue
        if object_kind == "procedure":
            if options.parse_procedures:
                procedures.append(_parse_procedure(normalized, cleaned, start, end, options))
            continue
        warnings.append(
            {
                "code": "unsupported_sql_object",
                "line_start": _line_for_offset(normalized, start),
                "object_kind": object_kind,
            }
        )

    if not triggers and not procedures:
        raise DbCodeParserError("No supported SQL code objects were found.")

    return DbCodeParseResult(
        dialect=options.dialect,
        normalized_text=normalized,
        triggers=tuple(triggers),
        procedures=tuple(procedures),
        warnings=tuple(warnings),
    )


def build_fragment_records(
    parse_result: DbCodeParseResult,
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

    def add_record(
        *,
        fragment_type: str,
        path_or_selector: str,
        span: TextSpan,
        metadata: dict[str, Any],
    ) -> None:
        nonlocal next_fragment_number
        sequence = len(records) + 1
        fragment_id = fragment_id_by_sequence.get(sequence)
        if fragment_id is None:
            fragment_id = _next_fragment_id(next_fragment_number, used_fragment_ids)
            next_fragment_number = int(fragment_id.rsplit("_", 1)[1]) + 1
        used_fragment_ids.add(fragment_id)
        full_metadata = {
            "parser": parser_name,
            "parser_version": parser_version,
            "source_hash": source_hash,
            **metadata,
        }
        records.append(
            {
                "char_end": span.char_end,
                "char_start": span.char_start,
                "fragment_id": fragment_id,
                "fragment_type": fragment_type,
                "line_end": span.line_end,
                "line_start": span.line_start,
                "metadata": full_metadata,
                "path_or_selector": path_or_selector,
                "sequence": sequence,
                "source_revision_id": source_revision_id,
                "status": "active",
                "text": span.text,
                "text_hash": sha256_text(span.text),
            }
        )

    for trigger in parse_result.triggers:
        add_record(
            fragment_type="sql_trigger",
            path_or_selector=f"trigger:{trigger.trigger_name}",
            span=trigger.span,
            metadata={
                "calls": list(trigger.calls),
                "object_type": "trigger",
                "reads": list(trigger.reads),
                "target_table": trigger.target_table,
                "trigger_event": trigger.trigger_event,
                "trigger_name": trigger.trigger_name,
                "trigger_timing": trigger.trigger_timing,
                "writes": list(trigger.writes),
            },
        )
        for index, statement in enumerate(trigger.statements, start=1):
            add_record(
                fragment_type="sql_statement",
                path_or_selector=f"trigger:{trigger.trigger_name}/statement:{index}",
                span=statement.span,
                metadata={
                    "calls": list(statement.calls),
                    "object_type": "statement",
                    "parent_object_name": statement.parent_object_name,
                    "parent_object_type": statement.parent_object_type,
                    "reads": list(statement.reads),
                    "statement_kind": statement.statement_kind,
                    "writes": list(statement.writes),
                },
            )

    for procedure in parse_result.procedures:
        add_record(
            fragment_type="sql_procedure",
            path_or_selector=f"procedure:{procedure.procedure_name}",
            span=procedure.span,
            metadata={
                "calls": list(procedure.calls),
                "object_type": "procedure",
                "parameters": list(procedure.parameters),
                "procedure_name": procedure.procedure_name,
                "reads": list(procedure.reads),
                "writes": list(procedure.writes),
            },
        )
        for index, statement in enumerate(procedure.statements, start=1):
            add_record(
                fragment_type="sql_statement",
                path_or_selector=f"procedure:{procedure.procedure_name}/statement:{index}",
                span=statement.span,
                metadata={
                    "calls": list(statement.calls),
                    "object_type": "statement",
                    "parent_object_name": statement.parent_object_name,
                    "parent_object_type": statement.parent_object_type,
                    "reads": list(statement.reads),
                    "statement_kind": statement.statement_kind,
                    "writes": list(statement.writes),
                },
            )

    return records


def canonical_fragment_json_line(record: dict[str, Any]) -> str:
    return json.dumps(record, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n"


def fragments_jsonl_content(records: list[dict[str, Any]]) -> str:
    return "".join(canonical_fragment_json_line(record) for record in records)


def fragments_jsonl_hash(records: list[dict[str, Any]]) -> str:
    return sha256_text(fragments_jsonl_content(records))


def normalize_sql_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _find_create_objects(cleaned: str) -> list[tuple[str, int, int]]:
    pattern = re.compile(
        r"\bCREATE\s+(?:OR\s+REPLACE\s+)?(?P<kind>TRIGGER|PROCEDURE)\b",
        re.IGNORECASE,
    )
    objects: list[tuple[str, int, int]] = []
    for match in pattern.finditer(cleaned):
        kind = match.group("kind").lower()
        end = _create_object_end(cleaned, match.end())
        objects.append((kind, match.start(), end))
    return sorted(objects, key=lambda item: item[1])


def _create_object_end(cleaned: str, search_start: int) -> int:
    end_match = re.search(r"\bEND\s*;", cleaned[search_start:], re.IGNORECASE)
    if end_match is not None:
        return search_start + end_match.end()
    semicolon = cleaned.find(";", search_start)
    return len(cleaned) if semicolon < 0 else semicolon + 1


def _parse_trigger(
    original: str,
    cleaned: str,
    start: int,
    end: int,
    options: DbCodeOptions,
) -> SqlTrigger:
    segment = cleaned[start:end]
    pattern = re.compile(
        rf"\bCREATE\s+(?:OR\s+REPLACE\s+)?TRIGGER\s+"
        rf"(?P<name>{IDENTIFIER_RE})\s+"
        rf"(?P<timing>BEFORE|AFTER|INSTEAD\s+OF)\s+"
        rf"(?P<event>INSERT|UPDATE|DELETE)"
        rf"(?:\s+OF\s+(?P<columns>.*?))?\s+ON\s+"
        rf"(?P<table>{IDENTIFIER_RE})",
        re.IGNORECASE | re.DOTALL,
    )
    match = pattern.search(segment)
    if match is None:
        raise DbCodeParserError(f"Malformed CREATE TRIGGER near line {_line_for_offset(original, start)}.")

    trigger_name = _normalize_identifier(match.group("name"))
    target_table = _normalize_identifier(match.group("table"))
    trigger_timing = _normalize_spaces(match.group("timing")).upper()
    trigger_event = match.group("event").upper()

    object_span = _span(original, start, end)
    parameters: tuple[str, ...] = ()
    statements = (
        tuple(
            _parse_update_statements(
                original,
                cleaned,
                start,
                end,
                parent_object_name=trigger_name,
                parent_object_type="trigger",
                default_table=target_table,
                parameters=parameters,
            )
        )
        if options.parse_update_statements
        else ()
    )
    trigger_reads = _reads_from_trigger_when(segment, target_table)
    reads = _ordered_unique([*trigger_reads, *[read for statement in statements for read in statement.reads]])
    writes = _ordered_unique([write for statement in statements for write in statement.writes])
    calls = _find_calls(segment) if options.parse_calls else []
    return SqlTrigger(
        trigger_name=trigger_name,
        trigger_timing=trigger_timing,
        trigger_event=trigger_event,
        target_table=target_table,
        reads=tuple(reads),
        writes=tuple(writes),
        calls=tuple(calls),
        statements=statements,
        span=object_span,
    )


def _parse_procedure(
    original: str,
    cleaned: str,
    start: int,
    end: int,
    options: DbCodeOptions,
) -> SqlProcedure:
    segment = cleaned[start:end]
    pattern = re.compile(
        rf"\bCREATE\s+(?:OR\s+REPLACE\s+)?PROCEDURE\s+"
        rf"(?P<name>{IDENTIFIER_RE})",
        re.IGNORECASE | re.DOTALL,
    )
    match = pattern.search(segment)
    if match is None:
        raise DbCodeParserError(f"Malformed CREATE PROCEDURE near line {_line_for_offset(original, start)}.")

    procedure_name = _normalize_identifier(match.group("name"))
    parameter_text = _procedure_parameter_text(segment, match.end())
    parameters = tuple(_parse_parameter_names(parameter_text))
    object_span = _span(original, start, end)
    statements = (
        tuple(
            _parse_update_statements(
                original,
                cleaned,
                start,
                end,
                parent_object_name=procedure_name,
                parent_object_type="procedure",
                default_table=None,
                parameters=parameters,
            )
        )
        if options.parse_update_statements
        else ()
    )
    reads = _ordered_unique(read for statement in statements for read in statement.reads)
    writes = _ordered_unique(write for statement in statements for write in statement.writes)
    calls = _find_calls(segment) if options.parse_calls else []
    return SqlProcedure(
        procedure_name=procedure_name,
        parameters=parameters,
        reads=tuple(reads),
        writes=tuple(writes),
        calls=tuple(calls),
        statements=statements,
        span=object_span,
    )


def _parse_update_statements(
    original: str,
    cleaned: str,
    object_start: int,
    object_end: int,
    *,
    parent_object_name: str,
    parent_object_type: str,
    default_table: str | None,
    parameters: tuple[str, ...],
) -> list[SqlStatement]:
    statements: list[SqlStatement] = []
    segment = cleaned[object_start:object_end]
    pattern = re.compile(rf"\bUPDATE\s+(?P<table>{IDENTIFIER_RE})\s+SET\b", re.IGNORECASE)
    for match in pattern.finditer(segment):
        statement_start = object_start + match.start()
        statement_end = _statement_end(cleaned, object_start + match.end(), object_end)
        statement_text = original[statement_start:statement_end]
        span = _span(original, statement_start, statement_end)
        table_name = _normalize_identifier(match.group("table") or default_table or "")
        writes, reads = _analyze_update_statement(statement_text, table_name, parameters)
        statements.append(
            SqlStatement(
                statement_kind="UPDATE",
                parent_object_name=parent_object_name,
                parent_object_type=parent_object_type,
                reads=tuple(reads),
                writes=tuple(writes),
                calls=(),
                span=span,
            )
        )
    return statements


def _statement_end(cleaned: str, position: int, object_end: int) -> int:
    state: str | None = None
    i = position
    while i < object_end:
        current = cleaned[i]
        next_char = cleaned[i + 1] if i + 1 < object_end else ""
        if state == "single_quote":
            if current == "'" and next_char == "'":
                i += 2
                continue
            if current == "'":
                state = None
            i += 1
            continue
        if current == "'":
            state = "single_quote"
        elif current == ";":
            return i + 1
        i += 1
    return object_end


def _analyze_update_statement(
    statement_text: str,
    table_name: str,
    parameters: tuple[str, ...],
) -> tuple[list[str], list[str]]:
    cleaned_statement = strip_sql_comments_preserving_offsets(statement_text)
    match = re.search(
        rf"\bUPDATE\s+{re.escape(table_name)}\s+SET\s+(?P<set>.*?)(?:\bWHERE\b(?P<where>.*))?$",
        cleaned_statement.strip().rstrip(";"),
        re.IGNORECASE | re.DOTALL,
    )
    if match is None:
        return [], []

    assignments = _split_top_level_commas(match.group("set"))
    writes: list[str] = []
    reads: list[str] = []
    for assignment in assignments:
        left, separator, right = assignment.partition("=")
        if not separator:
            continue
        column_name = _normalize_identifier(left.strip().split(".")[-1])
        if column_name:
            writes.append(f"{table_name}.{column_name}")
        reads.extend(_extract_reads_from_expression(right, table_name, parameters))

    where_text = match.group("where") or ""
    reads.extend(_extract_reads_from_expression(where_text, table_name, parameters))
    return _ordered_unique(writes), _ordered_unique(reads)


def _extract_reads_from_expression(
    expression: str,
    table_name: str,
    parameters: tuple[str, ...],
) -> list[str]:
    expression = _strip_string_literals(expression)
    reads: list[str] = []
    parameter_names = {parameter.upper() for parameter in parameters}

    for match in re.finditer(r"\b(NEW|OLD)\.([A-Za-z_][A-Za-z0-9_$#]*)\b", expression, re.IGNORECASE):
        reads.append(f"{match.group(1).upper()}.{match.group(2).upper()}")

    for match in re.finditer(
        r"\b([A-Za-z_][A-Za-z0-9_$#]*)\.([A-Za-z_][A-Za-z0-9_$#]*)\b",
        expression,
    ):
        owner = match.group(1).upper()
        column = match.group(2).upper()
        if owner in {"NEW", "OLD"}:
            continue
        reads.append(f"{owner}.{column}")

    for match in re.finditer(r"\b[A-Za-z_][A-Za-z0-9_$#]*\b", expression):
        identifier = match.group(0).upper()
        if identifier in SQL_KEYWORDS:
            continue
        if identifier == table_name.upper():
            continue
        previous_char = expression[match.start() - 1] if match.start() > 0 else ""
        next_char = expression[match.end()] if match.end() < len(expression) else ""
        if previous_char == "." or next_char == ".":
            continue
        if identifier in parameter_names:
            reads.append(identifier)
            continue
        reads.append(f"{table_name}.{identifier}")
    return _ordered_unique(reads)


def _reads_from_trigger_when(segment: str, table_name: str) -> list[str]:
    match = re.search(r"\bWHEN\s+(?P<condition>.*?)\bBEGIN\b", segment, re.IGNORECASE | re.DOTALL)
    if match is None:
        return []
    return _extract_reads_from_expression(match.group("condition"), table_name, ())


def _parse_parameter_names(parameter_text: str) -> list[str]:
    if not parameter_text.strip():
        return []
    inner = parameter_text.strip()[1:-1]
    parameters: list[str] = []
    for item in _split_top_level_commas(inner):
        tokens = item.strip().split()
        if not tokens:
            continue
        if tokens[0].upper() in {"IN", "OUT", "INOUT"} and len(tokens) > 1:
            name = tokens[1]
        else:
            name = tokens[0]
        parameters.append(_normalize_identifier(name.lstrip("@:")))
    return parameters


def _procedure_parameter_text(segment: str, position: int) -> str:
    position = _skip_ws(segment, position)
    if position >= len(segment) or segment[position] != "(":
        return ""
    close = _find_matching_paren(segment, position)
    if close is None:
        raise DbCodeParserError("Malformed CREATE PROCEDURE parameter list.")
    return segment[position : close + 1]


def _find_matching_paren(text: str, open_position: int) -> int | None:
    depth = 0
    state: str | None = None
    i = open_position
    while i < len(text):
        current = text[i]
        next_char = text[i + 1] if i + 1 < len(text) else ""
        if state == "single_quote":
            if current == "'" and next_char == "'":
                i += 2
                continue
            if current == "'":
                state = None
            i += 1
            continue
        if current == "'":
            state = "single_quote"
        elif current == "(":
            depth += 1
        elif current == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return None


def _find_calls(segment: str) -> list[str]:
    calls: list[str] = []
    for pattern in (
        rf"\bCALL\s+({IDENTIFIER_RE})\b",
        rf"\bEXEC(?:UTE)?\s+({IDENTIFIER_RE})\b",
    ):
        for match in re.finditer(pattern, segment, re.IGNORECASE):
            calls.append(_normalize_identifier(match.group(1)))
    return _ordered_unique(calls)


def _split_top_level_commas(text: str) -> list[str]:
    items: list[str] = []
    start = 0
    depth = 0
    state: str | None = None
    i = 0
    while i < len(text):
        current = text[i]
        next_char = text[i + 1] if i + 1 < len(text) else ""
        if state == "single_quote":
            if current == "'" and next_char == "'":
                i += 2
                continue
            if current == "'":
                state = None
            i += 1
            continue
        if current == "'":
            state = "single_quote"
        elif current == "(":
            depth += 1
        elif current == ")":
            depth = max(0, depth - 1)
        elif current == "," and depth == 0:
            items.append(text[start:i].strip())
            start = i + 1
        i += 1
    final = text[start:].strip()
    if final:
        items.append(final)
    return items


def _strip_string_literals(text: str) -> str:
    chars = list(text)
    i = 0
    while i < len(chars):
        if chars[i] != "'":
            i += 1
            continue
        chars[i] = " "
        i += 1
        while i < len(chars):
            if chars[i] == "'" and i + 1 < len(chars) and chars[i + 1] == "'":
                chars[i] = " "
                chars[i + 1] = " "
                i += 2
                continue
            if chars[i] == "'":
                chars[i] = " "
                i += 1
                break
            chars[i] = " "
            i += 1
    return "".join(chars)


def _span(text: str, start: int, end: int) -> TextSpan:
    start, end = _trim_offsets(text, start, end)
    return TextSpan(
        text=text[start:end],
        line_start=_line_for_offset(text, start),
        line_end=_line_for_offset(text, max(start, end - 1)),
        char_start=start,
        char_end=end,
    )


def _trim_offsets(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


def _skip_ws(text: str, position: int) -> int:
    while position < len(text) and text[position].isspace():
        position += 1
    return position


def _line_for_offset(text: str, offset: int) -> int:
    return text.count("\n", 0, max(0, offset)) + 1


def _normalize_identifier(value: str) -> str:
    return value.strip().strip('"[]`').upper()


def _normalize_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def _ordered_unique(values: Any) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


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
    raise DbCodeParserError(f"SQL code option {key} must be a boolean.")
