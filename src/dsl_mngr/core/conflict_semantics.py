from __future__ import annotations

from dataclasses import dataclass
from typing import Any


CONFLICT_SEMANTICS_CATALOG_VERSION = "1"
SINGLE_VALUE = "single_value"
MULTI_VALUE = "multi_value"
EVENT = "event"


@dataclass(frozen=True)
class ConflictSemanticsRule:
    fact_type: str
    property_name: str
    semantics: str

    def to_payload(self) -> dict[str, str]:
        return {
            "fact_type": self.fact_type,
            "property_name": self.property_name,
            "semantics": self.semantics,
        }


# The tuple is the versioned, deterministic catalog.  Exact matches take
# precedence over wildcard properties.  Unknown facts deliberately retain the
# historical single-value behavior.
CONFLICT_SEMANTICS_CATALOG: tuple[ConflictSemanticsRule, ...] = (
    ConflictSemanticsRule("entity_alias", "*", MULTI_VALUE),
    ConflictSemanticsRule("log_event", "*", EVENT),
)


def fact_conflict_semantics(fact_type: Any, property_name: Any) -> str:
    normalized_fact_type = _normalize(fact_type)
    normalized_property = _normalize(property_name)
    exact: str | None = None
    wildcard: str | None = None
    for rule in CONFLICT_SEMANTICS_CATALOG:
        if _normalize(rule.fact_type) != normalized_fact_type:
            continue
        if rule.property_name == "*":
            wildcard = rule.semantics
        elif _normalize(rule.property_name) == normalized_property:
            exact = rule.semantics
    return exact or wildcard or SINGLE_VALUE


def conflict_semantics_payload() -> dict[str, object]:
    return {
        "catalog_version": CONFLICT_SEMANTICS_CATALOG_VERSION,
        "default": SINGLE_VALUE,
        "rules": [rule.to_payload() for rule in CONFLICT_SEMANTICS_CATALOG],
    }


def _normalize(value: Any) -> str:
    return str(value or "").strip().casefold()
