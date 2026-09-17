from __future__ import annotations

import json
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Iterable, Mapping


RESOLVED = "resolved"
UNRESOLVED = "unresolved"
INCONSISTENT = "inconsistent"


@dataclass(frozen=True)
class StructuralResolution:
    raw_target: str
    canonical_target: str
    status: str
    reason: str
    basis: tuple[str, ...]

    def to_payload(self) -> dict[str, object]:
        return {
            "raw_target": self.raw_target,
            "canonical_target": self.canonical_target,
            "resolution_status": self.status,
            "resolution_reason": self.reason,
            "resolution_basis": list(self.basis),
        }


@dataclass(frozen=True)
class StructuralIndex:
    tables: Mapping[str, frozenset[str]]
    code_units: frozenset[str]

    @classmethod
    def empty(cls) -> StructuralIndex:
        return cls(MappingProxyType({}), frozenset())

    @classmethod
    def from_active_fragments(cls, fragments: Iterable[Mapping[str, Any]]) -> StructuralIndex:
        tables: dict[str, set[str]] = {}
        code_units: set[str] = set()
        for fragment in fragments:
            fragment_type = str(fragment.get("fragment_type") or "")
            metadata = _metadata(fragment.get("metadata_json"))
            if fragment_type == "ddl_table":
                table = _identifier(metadata.get("table_name"))
                if table:
                    tables.setdefault(table, set())
            elif fragment_type == "ddl_column":
                table = _identifier(metadata.get("table_name"))
                column = _identifier(metadata.get("column_name"))
                if table and column:
                    tables.setdefault(table, set()).add(column)
            elif fragment_type in {"sql_function", "sql_procedure", "sql_trigger"}:
                key = {
                    "sql_function": "function_name",
                    "sql_procedure": "procedure_name",
                    "sql_trigger": "trigger_name",
                }[fragment_type]
                unit = _identifier(metadata.get(key))
                if unit:
                    code_units.add(unit)
        frozen_tables = {
            table: frozenset(sorted(columns))
            for table, columns in sorted(tables.items())
        }
        return cls(MappingProxyType(frozen_tables), frozenset(sorted(code_units)))

    def resolve_table(self, raw_target: Any) -> StructuralResolution:
        raw = str(raw_target or "").strip()
        canonical = _identifier(raw)
        if canonical in self.tables:
            return StructuralResolution(
                raw, canonical, RESOLVED, "active_ddl_table", (f"table:{canonical}",)
            )
        return StructuralResolution(
            raw, canonical, UNRESOLVED, "no_active_ddl_table", ()
        )

    def resolve_column(self, raw_target: Any) -> StructuralResolution:
        raw = str(raw_target or "").strip()
        canonical = _identifier(raw)
        if "." not in canonical:
            return StructuralResolution(
                raw, canonical, UNRESOLVED, "unqualified_database_column", ()
            )
        table, column = canonical.rsplit(".", 1)
        if table not in self.tables:
            return StructuralResolution(
                raw, canonical, UNRESOLVED, "no_active_ddl_table", ()
            )
        basis = (f"table:{table}", f"column:{table}.{column}")
        if column in self.tables[table]:
            return StructuralResolution(
                raw, canonical, RESOLVED, "active_ddl_column", basis
            )
        return StructuralResolution(
            raw,
            canonical,
            INCONSISTENT,
            "active_ddl_table_missing_column",
            (f"table:{table}",),
        )

    def resolve_code_unit(self, raw_target: Any) -> StructuralResolution:
        raw = str(raw_target or "").strip()
        canonical = _identifier(raw)
        if canonical in self.code_units:
            return StructuralResolution(
                raw,
                canonical,
                RESOLVED,
                "active_database_code_unit",
                (f"code_unit:{canonical}",),
            )
        return StructuralResolution(
            raw, canonical, UNRESOLVED, "no_active_database_code_unit", ()
        )


def _metadata(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(value or "{}")
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _identifier(value: Any) -> str:
    return str(value or "").strip().strip('"[]`').upper()
