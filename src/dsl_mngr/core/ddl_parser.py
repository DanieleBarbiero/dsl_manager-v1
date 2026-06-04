from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any


SUPPORTED_DDL_OPTIONS = {
    "dialect",
    "output_fragments_jsonl",
    "parse_create_table",
    "parse_foreign_keys",
    "parse_indexes",
    "parse_primary_keys",
    "parse_unique_constraints",
    "strict_options_fail_on_unsupported_option",
    "unsupported_statement_policy",
}


class DdlParserError(RuntimeError):
    """Raised when DDL parsing cannot be completed."""


class UnsupportedDdlOption(DdlParserError):
    """Raised when a strict DDL profile contains an unsupported option."""

    def __init__(self, option_key: str, message: str | None = None) -> None:
        self.option_key = option_key
        super().__init__(message or f"Unsupported DDL option: {option_key}.")


@dataclass(frozen=True)
class DdlOptions:
    dialect: str = "generic_sql"
    parse_create_table: bool = True
    parse_primary_keys: bool = True
    parse_foreign_keys: bool = True
    parse_unique_constraints: bool = True
    parse_indexes: bool = True
    strict_options_fail_on_unsupported_option: bool = True
    unsupported_statement_policy: str = "warn"
    output_fragments_jsonl: bool = True


@dataclass(frozen=True)
class DdlColumn:
    name: str
    data_type: str
    nullable: bool | None
    default: str | None
    primary_key: bool
    unique: bool
    text: str
    line_start: int
    line_end: int
    char_start: int
    char_end: int


@dataclass(frozen=True)
class DdlConstraint:
    constraint_kind: str
    constraint_name: str | None
    columns: tuple[str, ...]
    references_table: str | None
    references_columns: tuple[str, ...]
    text: str
    line_start: int
    line_end: int
    char_start: int
    char_end: int


@dataclass(frozen=True)
class DdlIndex:
    index_name: str
    table_name: str
    columns: tuple[str, ...]
    unique: bool
    text: str
    line_start: int
    line_end: int
    char_start: int
    char_end: int


@dataclass(frozen=True)
class DdlTable:
    table_name: str
    schema_name: str | None
    full_name: str
    columns: tuple[DdlColumn, ...]
    constraints: tuple[DdlConstraint, ...]
    text: str
    line_start: int
    line_end: int
    char_start: int
    char_end: int


@dataclass(frozen=True)
class DdlParseResult:
    dialect: str
    normalized_text: str
    tables: tuple[DdlTable, ...]
    indexes: tuple[DdlIndex, ...]
    warnings: tuple[dict[str, Any], ...]

    @property
    def table_count(self) -> int:
        return len(self.tables)

    @property
    def column_count(self) -> int:
        return sum(len(table.columns) for table in self.tables)

    @property
    def foreign_key_count(self) -> int:
        return sum(
            1
            for table in self.tables
            for constraint in table.constraints
            if constraint.constraint_kind == "foreign_key"
        )

    def to_objects(self) -> dict[str, Any]:
        return {
            "indexes": [index_to_dict(index) for index in self.indexes],
            "tables": [table_to_dict(table) for table in self.tables],
            "warnings": list(self.warnings),
        }


def parse_ddl_options(raw_options: dict[str, Any]) -> DdlOptions:
    strict = _as_bool(
        raw_options.get("strict_options_fail_on_unsupported_option", True),
        "strict_options_fail_on_unsupported_option",
    )
    unsupported = sorted(set(raw_options) - SUPPORTED_DDL_OPTIONS)
    if unsupported and strict:
        raise UnsupportedDdlOption(unsupported[0], f"unsupported_ddl_option: {unsupported[0]}")

    dialect = str(raw_options.get("dialect", "generic_sql"))
    if dialect != "generic_sql":
        raise UnsupportedDdlOption("dialect", f"unsupported_ddl_option: dialect={dialect}")

    policy = str(raw_options.get("unsupported_statement_policy", "warn")).strip().lower()
    if policy not in {"warn", "ignore", "fail"}:
        raise UnsupportedDdlOption(
            "unsupported_statement_policy",
            f"unsupported_ddl_option: unsupported_statement_policy={policy}",
        )

    return DdlOptions(
        dialect=dialect,
        parse_create_table=_as_bool(raw_options.get("parse_create_table", True), "parse_create_table"),
        parse_primary_keys=_as_bool(raw_options.get("parse_primary_keys", True), "parse_primary_keys"),
        parse_foreign_keys=_as_bool(raw_options.get("parse_foreign_keys", True), "parse_foreign_keys"),
        parse_unique_constraints=_as_bool(
            raw_options.get("parse_unique_constraints", True),
            "parse_unique_constraints",
        ),
        parse_indexes=_as_bool(raw_options.get("parse_indexes", True), "parse_indexes"),
        strict_options_fail_on_unsupported_option=strict,
        unsupported_statement_policy=policy,
        output_fragments_jsonl=_as_bool(
            raw_options.get("output_fragments_jsonl", True),
            "output_fragments_jsonl",
        ),
    )


def parse_ddl_text(text: str, options: DdlOptions) -> DdlParseResult:
    normalized = normalize_sql_newlines(text)
    if not normalized.strip():
        raise DdlParserError("DDL input is empty.")

    cleaned = strip_sql_comments_preserving_offsets(normalized)
    warnings = _unsupported_statement_warnings(cleaned, normalized, options)
    if options.unsupported_statement_policy == "fail" and warnings:
        first = warnings[0]
        raise DdlParserError(
            f"Unsupported DDL statement near line {first['line_start']}: {first['statement_preview']}"
        )

    tables = _parse_create_tables(normalized, cleaned, options) if options.parse_create_table else []
    indexes = _parse_create_indexes(normalized, cleaned, options) if options.parse_indexes else []
    if not tables and not indexes:
        raise DdlParserError("No supported DDL objects were found.")

    return DdlParseResult(
        dialect=options.dialect,
        normalized_text=normalized,
        tables=tuple(tables),
        indexes=tuple(indexes),
        warnings=tuple(warnings),
    )


def build_fragment_records(
    parse_result: DdlParseResult,
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
        text: str,
        line_start: int,
        line_end: int,
        char_start: int,
        char_end: int,
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
            "dialect": parse_result.dialect,
            "parser": parser_name,
            "parser_version": parser_version,
            "source_hash": source_hash,
            **metadata,
        }
        records.append(
            {
                "char_end": char_end,
                "char_start": char_start,
                "fragment_id": fragment_id,
                "fragment_type": fragment_type,
                "line_end": line_end,
                "line_start": line_start,
                "metadata": full_metadata,
                "path_or_selector": path_or_selector,
                "sequence": sequence,
                "source_revision_id": source_revision_id,
                "status": "active",
                "text": text,
                "text_hash": sha256_text(text),
            }
        )

    for table in parse_result.tables:
        add_record(
            fragment_type="ddl_table",
            path_or_selector=f"table:{table.full_name}",
            text=table.text,
            line_start=table.line_start,
            line_end=table.line_end,
            char_start=table.char_start,
            char_end=table.char_end,
            metadata={
                "columns": [column.name for column in table.columns],
                "foreign_keys": [
                    {
                        "columns": list(constraint.columns),
                        "constraint_name": constraint.constraint_name,
                        "references_columns": list(constraint.references_columns),
                        "references_table": constraint.references_table,
                    }
                    for constraint in table.constraints
                    if constraint.constraint_kind == "foreign_key"
                ],
                "object_type": "table",
                "primary_key": _primary_key_columns(table),
                "schema_name": table.schema_name,
                "statement_kind": "create_table",
                "table_name": table.full_name,
            },
        )
        for column in table.columns:
            add_record(
                fragment_type="ddl_column",
                path_or_selector=f"table:{table.full_name}/column:{column.name}",
                text=column.text,
                line_start=column.line_start,
                line_end=column.line_end,
                char_start=column.char_start,
                char_end=column.char_end,
                metadata={
                    "column_name": column.name,
                    "data_type": column.data_type,
                    "default": column.default,
                    "nullable": column.nullable,
                    "object_type": "column",
                    "statement_kind": "create_table",
                    "table_name": table.full_name,
                    "unique": column.unique,
                },
            )
        for constraint in table.constraints:
            add_record(
                fragment_type="ddl_constraint",
                path_or_selector=_constraint_selector(table.full_name, constraint),
                text=constraint.text,
                line_start=constraint.line_start,
                line_end=constraint.line_end,
                char_start=constraint.char_start,
                char_end=constraint.char_end,
                metadata={
                    "columns": list(constraint.columns),
                    "constraint_kind": constraint.constraint_kind,
                    "constraint_name": constraint.constraint_name,
                    "object_type": "constraint",
                    "references_columns": list(constraint.references_columns),
                    "references_table": constraint.references_table,
                    "statement_kind": "create_table",
                    "table_name": table.full_name,
                },
            )

    for index in parse_result.indexes:
        kind = "unique_index" if index.unique else "index"
        add_record(
            fragment_type="ddl_constraint",
            path_or_selector=f"table:{index.table_name}/{kind}:{index.index_name}",
            text=index.text,
            line_start=index.line_start,
            line_end=index.line_end,
            char_start=index.char_start,
            char_end=index.char_end,
            metadata={
                "columns": list(index.columns),
                "constraint_kind": kind,
                "constraint_name": index.index_name,
                "object_type": "index",
                "statement_kind": "create_index",
                "table_name": index.table_name,
            },
        )

    return records


def canonical_fragment_json_line(record: dict[str, Any]) -> str:
    return json.dumps(record, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n"


def canonical_metadata_json(metadata: dict[str, Any]) -> str:
    return json.dumps(metadata, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def fragments_jsonl_content(records: list[dict[str, Any]]) -> str:
    return "".join(canonical_fragment_json_line(record) for record in records)


def fragments_jsonl_hash(records: list[dict[str, Any]]) -> str:
    return sha256_text(fragments_jsonl_content(records))


def normalize_sql_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def strip_sql_comments_preserving_offsets(text: str) -> str:
    chars = list(text)
    i = 0
    state: str | None = None
    while i < len(chars):
        current = chars[i]
        next_char = chars[i + 1] if i + 1 < len(chars) else ""

        if state == "single_quote":
            if current == "'" and next_char == "'":
                i += 2
                continue
            if current == "'":
                state = None
            i += 1
            continue
        if state == "double_quote":
            if current == '"':
                state = None
            i += 1
            continue
        if state == "bracket":
            if current == "]":
                state = None
            i += 1
            continue
        if state == "backtick":
            if current == "`":
                state = None
            i += 1
            continue

        if current == "'":
            state = "single_quote"
            i += 1
            continue
        if current == '"':
            state = "double_quote"
            i += 1
            continue
        if current == "[":
            state = "bracket"
            i += 1
            continue
        if current == "`":
            state = "backtick"
            i += 1
            continue

        if current == "-" and next_char == "-":
            chars[i] = " "
            chars[i + 1] = " "
            i += 2
            while i < len(chars) and chars[i] != "\n":
                chars[i] = " "
                i += 1
            continue
        if current == "/" and next_char == "*":
            chars[i] = " "
            chars[i + 1] = " "
            i += 2
            while i < len(chars):
                if chars[i] == "*" and i + 1 < len(chars) and chars[i + 1] == "/":
                    chars[i] = " "
                    chars[i + 1] = " "
                    i += 2
                    break
                if chars[i] != "\n":
                    chars[i] = " "
                i += 1
            continue
        i += 1
    return "".join(chars)


def table_to_dict(table: DdlTable) -> dict[str, Any]:
    return {
        "columns": [column_to_dict(column) for column in table.columns],
        "constraints": [constraint_to_dict(constraint) for constraint in table.constraints],
        "full_name": table.full_name,
        "line_end": table.line_end,
        "line_start": table.line_start,
        "schema_name": table.schema_name,
        "table_name": table.table_name,
    }


def column_to_dict(column: DdlColumn) -> dict[str, Any]:
    return {
        "data_type": column.data_type,
        "default": column.default,
        "name": column.name,
        "nullable": column.nullable,
        "primary_key": column.primary_key,
        "unique": column.unique,
    }


def constraint_to_dict(constraint: DdlConstraint) -> dict[str, Any]:
    return {
        "columns": list(constraint.columns),
        "constraint_kind": constraint.constraint_kind,
        "constraint_name": constraint.constraint_name,
        "references_columns": list(constraint.references_columns),
        "references_table": constraint.references_table,
    }


def index_to_dict(index: DdlIndex) -> dict[str, Any]:
    return {
        "columns": list(index.columns),
        "index_name": index.index_name,
        "table_name": index.table_name,
        "unique": index.unique,
    }


def _parse_create_tables(original: str, cleaned: str, options: DdlOptions) -> list[DdlTable]:
    tables: list[DdlTable] = []
    pattern = re.compile(r"\bCREATE\s+TABLE\b", re.IGNORECASE)
    position = 0
    while True:
        match = pattern.search(cleaned, position)
        if match is None:
            break
        try:
            table, statement_end = _parse_create_table_at(original, cleaned, match.start(), options)
        except DdlParserError:
            raise
        tables.append(table)
        position = max(statement_end, match.end())
    return tables


def _parse_create_table_at(
    original: str,
    cleaned: str,
    start: int,
    options: DdlOptions,
) -> tuple[DdlTable, int]:
    position = _skip_ws(cleaned, re.match(r"\bCREATE\s+TABLE\b", cleaned[start:], re.IGNORECASE).end() + start)
    if re.match(r"IF\s+NOT\s+EXISTS\b", cleaned[position:], re.IGNORECASE):
        position = _skip_ws(cleaned, position + re.match(r"IF\s+NOT\s+EXISTS\b", cleaned[position:], re.IGNORECASE).end())

    table_name, name_end = _parse_qualified_identifier(cleaned, position)
    position = _skip_ws(cleaned, name_end)
    if position >= len(cleaned) or cleaned[position] != "(":
        raise DdlParserError(f"Malformed CREATE TABLE near line {_line_for_offset(original, start)}.")
    close_paren = _find_matching_paren(cleaned, position)
    if close_paren is None:
        raise DdlParserError(f"Malformed CREATE TABLE near line {_line_for_offset(original, start)}.")

    statement_end = _statement_end(cleaned, close_paren + 1)
    table_text = original[start:statement_end].strip()
    table_start, table_end = _trim_offsets(original, start, statement_end)
    table_parts = table_name.split(".")
    schema_name = ".".join(table_parts[:-1]) if len(table_parts) > 1 else None
    short_name = table_parts[-1]

    columns: list[DdlColumn] = []
    constraints: list[DdlConstraint] = []
    for item_start, item_end in _split_top_level_items(cleaned, position + 1, close_paren):
        item_start, item_end = _trim_offsets(original, item_start, item_end)
        if item_start >= item_end:
            continue
        item_text = original[item_start:item_end].strip()
        constraint = _parse_table_constraint(
            item_text,
            table_name=table_name,
            original=original,
            item_start=item_start,
            item_end=item_end,
            options=options,
        )
        if constraint is not None:
            constraints.append(constraint)
            continue
        column, inline_constraints = _parse_column_definition(
            item_text,
            table_name=table_name,
            original=original,
            item_start=item_start,
            item_end=item_end,
            options=options,
        )
        columns.append(column)
        constraints.extend(inline_constraints)

    if not columns:
        raise DdlParserError(f"CREATE TABLE {table_name} has no columns.")

    return (
        DdlTable(
            table_name=short_name,
            schema_name=schema_name,
            full_name=table_name,
            columns=tuple(columns),
            constraints=tuple(constraints),
            text=table_text,
            line_start=_line_for_offset(original, table_start),
            line_end=_line_for_offset(original, max(table_start, table_end - 1)),
            char_start=table_start,
            char_end=table_end,
        ),
        statement_end,
    )


def _parse_column_definition(
    item_text: str,
    *,
    table_name: str,
    original: str,
    item_start: int,
    item_end: int,
    options: DdlOptions,
) -> tuple[DdlColumn, list[DdlConstraint]]:
    column_name, name_end = _parse_qualified_identifier(item_text, 0)
    if "." in column_name:
        raise DdlParserError(f"Column name must not be qualified: {column_name}.")
    rest = item_text[name_end:].strip()
    if not rest:
        raise DdlParserError(f"Column {column_name} has no data type.")

    data_type = _extract_data_type(rest)
    nullable: bool | None = None
    if re.search(r"\bNOT\s+NULL\b", rest, re.IGNORECASE):
        nullable = False
    elif re.search(r"\bNULL\b", rest, re.IGNORECASE):
        nullable = True
    default = _extract_default(rest)
    inline_primary_key = bool(re.search(r"\bPRIMARY\s+KEY\b", rest, re.IGNORECASE))
    inline_unique = bool(re.search(r"\bUNIQUE\b", rest, re.IGNORECASE))

    constraints: list[DdlConstraint] = []
    if inline_primary_key and options.parse_primary_keys:
        constraints.append(
            _inline_constraint(
                "primary_key",
                table_name,
                (column_name,),
                original,
                item_start,
                item_end,
                item_text,
            )
        )
    if inline_unique and options.parse_unique_constraints:
        constraints.append(
            _inline_constraint(
                "unique",
                table_name,
                (column_name,),
                original,
                item_start,
                item_end,
                item_text,
            )
        )

    inline_fk = _parse_inline_foreign_key(
        rest,
        table_name=table_name,
        column_name=column_name,
        original=original,
        item_start=item_start,
        item_end=item_end,
        item_text=item_text,
        options=options,
    )
    if inline_fk is not None:
        constraints.append(inline_fk)

    return (
        DdlColumn(
            name=column_name,
            data_type=data_type,
            nullable=nullable,
            default=default,
            primary_key=inline_primary_key,
            unique=inline_unique,
            text=item_text,
            line_start=_line_for_offset(original, item_start),
            line_end=_line_for_offset(original, max(item_start, item_end - 1)),
            char_start=item_start,
            char_end=item_end,
        ),
        constraints,
    )


def _parse_table_constraint(
    item_text: str,
    *,
    table_name: str,
    original: str,
    item_start: int,
    item_end: int,
    options: DdlOptions,
) -> DdlConstraint | None:
    working = item_text.strip()
    constraint_name: str | None = None
    match = re.match(r"CONSTRAINT\b", working, re.IGNORECASE)
    if match is not None:
        position = _skip_ws(working, match.end())
        constraint_name, position = _parse_qualified_identifier(working, position)
        working = working[position:].strip()

    if re.match(r"PRIMARY\s+KEY\b", working, re.IGNORECASE):
        if not options.parse_primary_keys:
            return None
        columns = _first_parenthesized_identifier_list(working)
        return DdlConstraint(
            constraint_kind="primary_key",
            constraint_name=constraint_name or _default_constraint_name("pk", table_name, columns),
            columns=tuple(columns),
            references_table=None,
            references_columns=(),
            text=item_text,
            line_start=_line_for_offset(original, item_start),
            line_end=_line_for_offset(original, max(item_start, item_end - 1)),
            char_start=item_start,
            char_end=item_end,
        )

    if re.match(r"FOREIGN\s+KEY\b", working, re.IGNORECASE):
        if not options.parse_foreign_keys:
            return None
        columns, references_table, references_columns = _parse_foreign_key_constraint(working)
        return DdlConstraint(
            constraint_kind="foreign_key",
            constraint_name=constraint_name
            or _default_constraint_name("fk", table_name, (*columns, references_table, *references_columns)),
            columns=tuple(columns),
            references_table=references_table,
            references_columns=tuple(references_columns),
            text=item_text,
            line_start=_line_for_offset(original, item_start),
            line_end=_line_for_offset(original, max(item_start, item_end - 1)),
            char_start=item_start,
            char_end=item_end,
        )

    if re.match(r"UNIQUE\b", working, re.IGNORECASE):
        if not options.parse_unique_constraints:
            return None
        columns = _first_parenthesized_identifier_list(working)
        return DdlConstraint(
            constraint_kind="unique",
            constraint_name=constraint_name or _default_constraint_name("uq", table_name, columns),
            columns=tuple(columns),
            references_table=None,
            references_columns=(),
            text=item_text,
            line_start=_line_for_offset(original, item_start),
            line_end=_line_for_offset(original, max(item_start, item_end - 1)),
            char_start=item_start,
            char_end=item_end,
        )

    if constraint_name is not None:
        raise DdlParserError(f"Unsupported table constraint in {table_name}: {item_text[:80]}.")
    return None


def _parse_inline_foreign_key(
    rest: str,
    *,
    table_name: str,
    column_name: str,
    original: str,
    item_start: int,
    item_end: int,
    item_text: str,
    options: DdlOptions,
) -> DdlConstraint | None:
    if not options.parse_foreign_keys:
        return None
    match = re.search(r"\bREFERENCES\b", rest, re.IGNORECASE)
    if match is None:
        return None
    position = _skip_ws(rest, match.end())
    references_table, position = _parse_qualified_identifier(rest, position)
    position = _skip_ws(rest, position)
    references_columns: list[str] = []
    if position < len(rest) and rest[position] == "(":
        close = _find_matching_paren(rest, position)
        if close is None:
            raise DdlParserError(f"Malformed inline foreign key on {table_name}.{column_name}.")
        references_columns = _identifier_list_from_text(rest[position + 1 : close])
    return DdlConstraint(
        constraint_kind="foreign_key",
        constraint_name=_default_constraint_name("fk", table_name, (column_name, references_table, *references_columns)),
        columns=(column_name,),
        references_table=references_table,
        references_columns=tuple(references_columns),
        text=item_text,
        line_start=_line_for_offset(original, item_start),
        line_end=_line_for_offset(original, max(item_start, item_end - 1)),
        char_start=item_start,
        char_end=item_end,
    )


def _inline_constraint(
    kind: str,
    table_name: str,
    columns: tuple[str, ...],
    original: str,
    item_start: int,
    item_end: int,
    item_text: str,
) -> DdlConstraint:
    prefix = "pk" if kind == "primary_key" else "uq"
    return DdlConstraint(
        constraint_kind=kind,
        constraint_name=_default_constraint_name(prefix, table_name, columns),
        columns=columns,
        references_table=None,
        references_columns=(),
        text=item_text,
        line_start=_line_for_offset(original, item_start),
        line_end=_line_for_offset(original, max(item_start, item_end - 1)),
        char_start=item_start,
        char_end=item_end,
    )


def _parse_create_indexes(original: str, cleaned: str, options: DdlOptions) -> list[DdlIndex]:
    indexes: list[DdlIndex] = []
    pattern = re.compile(r"\bCREATE\s+(UNIQUE\s+)?INDEX\b", re.IGNORECASE)
    position = 0
    while True:
        match = pattern.search(cleaned, position)
        if match is None:
            break
        index, statement_end = _parse_create_index_at(original, cleaned, match.start())
        indexes.append(index)
        position = max(statement_end, match.end())
    return indexes


def _parse_create_index_at(original: str, cleaned: str, start: int) -> tuple[DdlIndex, int]:
    match = re.match(r"\bCREATE\s+(UNIQUE\s+)?INDEX\b", cleaned[start:], re.IGNORECASE)
    if match is None:
        raise DdlParserError("Internal parser error: CREATE INDEX expected.")
    unique = bool(match.group(1))
    position = _skip_ws(cleaned, start + match.end())
    index_name, position = _parse_qualified_identifier(cleaned, position)
    on_match = re.match(r"\s+ON\b", cleaned[position:], re.IGNORECASE)
    if on_match is None:
        raise DdlParserError(f"Malformed CREATE INDEX near line {_line_for_offset(original, start)}.")
    position = _skip_ws(cleaned, position + on_match.end())
    table_name, position = _parse_qualified_identifier(cleaned, position)
    position = _skip_ws(cleaned, position)
    if position >= len(cleaned) or cleaned[position] != "(":
        raise DdlParserError(f"Malformed CREATE INDEX near line {_line_for_offset(original, start)}.")
    close = _find_matching_paren(cleaned, position)
    if close is None:
        raise DdlParserError(f"Malformed CREATE INDEX near line {_line_for_offset(original, start)}.")
    columns = tuple(_identifier_list_from_text(cleaned[position + 1 : close]))
    statement_end = _statement_end(cleaned, close + 1)
    index_start, index_end = _trim_offsets(original, start, statement_end)
    return (
        DdlIndex(
            index_name=index_name,
            table_name=table_name,
            columns=columns,
            unique=unique,
            text=original[index_start:index_end].strip(),
            line_start=_line_for_offset(original, index_start),
            line_end=_line_for_offset(original, max(index_start, index_end - 1)),
            char_start=index_start,
            char_end=index_end,
        ),
        statement_end,
    )


def _parse_foreign_key_constraint(text: str) -> tuple[list[str], str, list[str]]:
    local_columns = _first_parenthesized_identifier_list(text)
    first_open = text.find("(")
    first_close = _find_matching_paren(text, first_open)
    if first_close is None:
        raise DdlParserError("Malformed FOREIGN KEY constraint.")
    references_match = re.search(r"\bREFERENCES\b", text[first_close + 1 :], re.IGNORECASE)
    if references_match is None:
        raise DdlParserError("FOREIGN KEY constraint is missing REFERENCES.")
    position = first_close + 1 + references_match.end()
    position = _skip_ws(text, position)
    references_table, position = _parse_qualified_identifier(text, position)
    position = _skip_ws(text, position)
    references_columns: list[str] = []
    if position < len(text) and text[position] == "(":
        close = _find_matching_paren(text, position)
        if close is None:
            raise DdlParserError("Malformed FOREIGN KEY referenced columns.")
        references_columns = _identifier_list_from_text(text[position + 1 : close])
    return local_columns, references_table, references_columns


def _first_parenthesized_identifier_list(text: str) -> list[str]:
    open_paren = text.find("(")
    if open_paren < 0:
        raise DdlParserError(f"Expected column list in constraint: {text[:80]}.")
    close_paren = _find_matching_paren(text, open_paren)
    if close_paren is None:
        raise DdlParserError(f"Malformed column list in constraint: {text[:80]}.")
    return _identifier_list_from_text(text[open_paren + 1 : close_paren])


def _identifier_list_from_text(text: str) -> list[str]:
    columns: list[str] = []
    for start, end in _split_top_level_items(text, 0, len(text)):
        item = text[start:end].strip()
        if not item:
            continue
        name, position = _parse_qualified_identifier(item, 0)
        remainder = item[position:].strip()
        if remainder:
            name = item.strip()
        columns.append(name)
    return columns


def _extract_data_type(rest: str) -> str:
    positions = [
        match.start()
        for pattern in (
            r"\bNOT\s+NULL\b",
            r"\bNULL\b",
            r"\bDEFAULT\b",
            r"\bPRIMARY\s+KEY\b",
            r"\bUNIQUE\b",
            r"\bREFERENCES\b",
            r"\bCHECK\b",
            r"\bCOLLATE\b",
        )
        for match in [re.search(pattern, rest, re.IGNORECASE)]
        if match is not None
    ]
    end = min(positions) if positions else len(rest)
    data_type = rest[:end].strip()
    if not data_type:
        raise DdlParserError(f"Column data type is missing in: {rest[:80]}.")
    return data_type


def _extract_default(rest: str) -> str | None:
    match = re.search(r"\bDEFAULT\b", rest, re.IGNORECASE)
    if match is None:
        return None
    start = match.end()
    end = len(rest)
    for pattern in (
        r"\bNOT\s+NULL\b",
        r"\bNULL\b",
        r"\bPRIMARY\s+KEY\b",
        r"\bUNIQUE\b",
        r"\bREFERENCES\b",
        r"\bCHECK\b",
        r"\bCOLLATE\b",
    ):
        next_match = re.search(pattern, rest[start:], re.IGNORECASE)
        if next_match is not None:
            end = min(end, start + next_match.start())
    default = rest[start:end].strip()
    return default or None


def _unsupported_statement_warnings(
    cleaned: str,
    original: str,
    options: DdlOptions,
) -> list[dict[str, Any]]:
    if options.unsupported_statement_policy == "ignore":
        return []
    warnings: list[dict[str, Any]] = []
    for start, end in _split_sql_statements(cleaned):
        segment = cleaned[start:end].strip()
        if not segment:
            continue
        if re.match(r"CREATE\s+TABLE\b", segment, re.IGNORECASE):
            continue
        if options.parse_indexes and re.match(r"CREATE\s+(UNIQUE\s+)?INDEX\b", segment, re.IGNORECASE):
            continue
        preview = " ".join(original[start:end].strip().split())[:120]
        warnings.append(
            {
                "code": "unsupported_statement",
                "line_start": _line_for_offset(original, start),
                "statement_preview": preview,
            }
        )
    return warnings


def _split_sql_statements(text: str) -> list[tuple[int, int]]:
    statements: list[tuple[int, int]] = []
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
        if state == "double_quote":
            if current == '"':
                state = None
            i += 1
            continue
        if state == "bracket":
            if current == "]":
                state = None
            i += 1
            continue
        if state == "backtick":
            if current == "`":
                state = None
            i += 1
            continue
        if current == "'":
            state = "single_quote"
        elif current == '"':
            state = "double_quote"
        elif current == "[":
            state = "bracket"
        elif current == "`":
            state = "backtick"
        elif current == "(":
            depth += 1
        elif current == ")":
            depth = max(0, depth - 1)
        elif current == ";" and depth == 0:
            statements.append((start, i + 1))
            start = i + 1
        i += 1
    if text[start:].strip():
        statements.append((start, len(text)))
    return statements


def _split_top_level_items(text: str, start: int, end: int) -> list[tuple[int, int]]:
    items: list[tuple[int, int]] = []
    item_start = start
    depth = 0
    state: str | None = None
    i = start
    while i < end:
        current = text[i]
        next_char = text[i + 1] if i + 1 < end else ""
        if state == "single_quote":
            if current == "'" and next_char == "'":
                i += 2
                continue
            if current == "'":
                state = None
            i += 1
            continue
        if state == "double_quote":
            if current == '"':
                state = None
            i += 1
            continue
        if state == "bracket":
            if current == "]":
                state = None
            i += 1
            continue
        if state == "backtick":
            if current == "`":
                state = None
            i += 1
            continue
        if current == "'":
            state = "single_quote"
        elif current == '"':
            state = "double_quote"
        elif current == "[":
            state = "bracket"
        elif current == "`":
            state = "backtick"
        elif current == "(":
            depth += 1
        elif current == ")":
            depth = max(0, depth - 1)
        elif current == "," and depth == 0:
            items.append((item_start, i))
            item_start = i + 1
        i += 1
    items.append((item_start, end))
    return items


def _parse_qualified_identifier(text: str, position: int) -> tuple[str, int]:
    parts: list[str] = []
    current = _skip_ws(text, position)
    while True:
        part, current = _parse_identifier(text, current)
        parts.append(part)
        current = _skip_ws(text, current)
        if current >= len(text) or text[current] != ".":
            break
        current = _skip_ws(text, current + 1)
    return ".".join(parts), current


def _parse_identifier(text: str, position: int) -> tuple[str, int]:
    if position >= len(text):
        raise DdlParserError("Expected SQL identifier.")
    current = text[position]
    if current == "[":
        end = text.find("]", position + 1)
        if end < 0:
            raise DdlParserError("Unclosed bracket quoted identifier.")
        return text[position + 1 : end], end + 1
    if current == '"':
        end = text.find('"', position + 1)
        if end < 0:
            raise DdlParserError("Unclosed double quoted identifier.")
        return text[position + 1 : end], end + 1
    if current == "`":
        end = text.find("`", position + 1)
        if end < 0:
            raise DdlParserError("Unclosed backtick quoted identifier.")
        return text[position + 1 : end], end + 1
    match = re.match(r"[A-Za-z_][A-Za-z0-9_$#]*", text[position:])
    if match is None:
        raise DdlParserError(f"Expected SQL identifier near: {text[position:position + 40]!r}.")
    return match.group(0), position + match.end()


def _find_matching_paren(text: str, open_position: int) -> int | None:
    if open_position < 0 or open_position >= len(text) or text[open_position] != "(":
        return None
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
        if state == "double_quote":
            if current == '"':
                state = None
            i += 1
            continue
        if state == "bracket":
            if current == "]":
                state = None
            i += 1
            continue
        if state == "backtick":
            if current == "`":
                state = None
            i += 1
            continue
        if current == "'":
            state = "single_quote"
        elif current == '"':
            state = "double_quote"
        elif current == "[":
            state = "bracket"
        elif current == "`":
            state = "backtick"
        elif current == "(":
            depth += 1
        elif current == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return None


def _statement_end(text: str, position: int) -> int:
    current = _skip_ws(text, position)
    if current < len(text) and text[current] == ";":
        return current + 1
    return position


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


def _primary_key_columns(table: DdlTable) -> list[str]:
    for constraint in table.constraints:
        if constraint.constraint_kind == "primary_key":
            return list(constraint.columns)
    return [column.name for column in table.columns if column.primary_key]


def _constraint_selector(table_name: str, constraint: DdlConstraint) -> str:
    columns = ",".join(constraint.columns)
    if constraint.constraint_kind == "foreign_key":
        if constraint.references_table and constraint.references_columns:
            refs = ",".join(f"{constraint.references_table}.{col}" for col in constraint.references_columns)
        else:
            refs = constraint.references_table or ""
        return f"table:{table_name}/foreign_key:{columns}->{refs}"
    if constraint.constraint_kind == "primary_key":
        return f"table:{table_name}/primary_key:{columns}"
    if constraint.constraint_kind == "unique":
        return f"table:{table_name}/unique:{columns}"
    return f"table:{table_name}/constraint:{constraint.constraint_name or constraint.constraint_kind}"


def _default_constraint_name(prefix: str, table_name: str, values: tuple[str, ...] | list[str]) -> str:
    tokens = [table_name.replace(".", "_"), *(value.replace(".", "_") for value in values)]
    return "_".join([prefix, *tokens])


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
    raise DdlParserError(f"DDL option {key} must be a boolean.")
