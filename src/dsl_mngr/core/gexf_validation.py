from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from importlib import resources
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import urlsplit

from lxml import etree


GEXF_NAMESPACE = "http://gexf.net/1.3"
GEXF_SCHEMA_PACKAGE = "dsl_mngr.resources.gexf"
GEXF_SCHEMA_DIRECTORY = "1.3"
EXPECTED_SCHEMA_HASHES = {
    "gexf.xsd": "a8e1d0a6a5237fc4ce0825692fa3db49fb04d70cf3a84334f7a87c15422c1257",
    "dynamics.xsd": "d5ee084a858baf6efebe210d4799050723bfce71fb44c9ddbf20a53f45be8298",
    "viz.xsd": "e20e40bcfd4531026d4d1c74da5cbadc413ff5b81cf4418ca14f42ea994e2dc4",
}
_NS = {"g": GEXF_NAMESPACE}


class GexfValidationError(RuntimeError):
    def __init__(self, message: str, *, reason: str) -> None:
        super().__init__(message)
        self.reason = reason
        self.exit_code = 3


@dataclass(frozen=True)
class GexfValidationResult:
    xsd_valid: bool
    semantic_valid: bool
    node_count: int
    edge_count: int
    timeformat: str


class _LocalSchemaResolver(etree.Resolver):
    def __init__(self, schemas: dict[str, bytes]) -> None:
        super().__init__()
        self.schemas = schemas

    def resolve(self, url: str, public_id: str | None, context: Any) -> Any:
        del public_id
        name = PurePosixPath(url.replace("\\", "/")).name
        local_urls = {name, f"resource:///{name}"}
        if name not in self.schemas or url not in local_urls:
            raise OSError(f"External XSD resolution denied: {url}")
        return self.resolve_string(
            self.schemas[name],
            context,
            base_url=f"resource:///{name}",
        )


def load_gexf_schema_resources() -> tuple[dict[str, bytes], dict[str, Any]]:
    directory = resources.files(GEXF_SCHEMA_PACKAGE).joinpath(GEXF_SCHEMA_DIRECTORY)
    manifest = json.loads(directory.joinpath("manifest.json").read_text(encoding="utf-8"))
    schemas: dict[str, bytes] = {}
    for name, expected_hash in EXPECTED_SCHEMA_HASHES.items():
        value = directory.joinpath(name).read_bytes()
        actual_hash = hashlib.sha256(value).hexdigest()
        if actual_hash != expected_hash:
            raise GexfValidationError(
                f"Vendored GEXF schema hash mismatch for {name}.",
                reason="gexf_xsd_invalid",
            )
        schemas[name] = value
    if {
        item["file"]: item["sha256"] for item in manifest.get("resources", [])
    } != EXPECTED_SCHEMA_HASHES:
        raise GexfValidationError(
            "Vendored GEXF resource manifest does not match the required hashes.",
            reason="gexf_xsd_invalid",
        )
    return schemas, manifest


def validate_dynamic_gexf(xml: str | bytes) -> GexfValidationResult:
    document = _parse_document(xml)
    _validate_xsd(document)
    return _validate_semantics(document)


def _parse_document(xml: str | bytes) -> etree._Element:
    parser = etree.XMLParser(
        no_network=True,
        load_dtd=False,
        resolve_entities=False,
        recover=False,
        huge_tree=False,
    )
    try:
        return etree.fromstring(
            xml.encode("utf-8") if isinstance(xml, str) else xml,
            parser=parser,
            base_url="resource:///document.gexf",
        )
    except (etree.XMLSyntaxError, ValueError) as exc:
        raise GexfValidationError(
            f"GEXF XML is not well-formed: {exc}.",
            reason="gexf_xsd_invalid",
        ) from exc


def _validate_xsd(document: etree._Element) -> None:
    schemas, _ = load_gexf_schema_resources()
    parser = etree.XMLParser(
        no_network=True,
        load_dtd=False,
        resolve_entities=False,
        recover=False,
        huge_tree=False,
    )
    parser.resolvers.add(_LocalSchemaResolver(schemas))
    try:
        schema_root = etree.fromstring(
            schemas["gexf.xsd"],
            parser=parser,
            base_url="resource:///gexf.xsd",
        )
        schema = etree.XMLSchema(schema_root)
        schema.assertValid(document)
    except (etree.XMLSchemaError, etree.DocumentInvalid, etree.XMLSyntaxError, OSError) as exc:
        raise GexfValidationError(
            f"GEXF 1.3 XSD validation failed: {exc}.",
            reason="gexf_xsd_invalid",
        ) from exc


def _validate_semantics(document: etree._Element) -> GexfValidationResult:
    if document.tag != f"{{{GEXF_NAMESPACE}}}gexf" or document.get("version") != "1.3":
        raise _semantic("GEXF namespace and version must be exactly 1.3.")
    graph_nodes = document.xpath("./g:graph", namespaces=_NS)
    if len(graph_nodes) != 1:
        raise _semantic("GEXF document must contain exactly one graph.")
    graph = graph_nodes[0]
    if graph.get("mode") != "dynamic" or graph.get("timerepresentation") != "interval":
        raise _semantic("GEXF graph must use dynamic interval mode.")
    timeformat = graph.get("timeformat")
    if timeformat not in {"date", "dateTime"}:
        raise _semantic("GEXF graph must use one date or dateTime timeformat.")
    if any(
        element.get("startopen") is not None or element.get("endopen") is not None
        for element in document.iter()
    ):
        raise _semantic("GEXF 1.3 bounds must be inclusive start/end bounds.")

    declarations = _attribute_declarations(graph)
    node_elements = graph.xpath("./g:nodes/g:node", namespaces=_NS)
    edge_elements = graph.xpath("./g:edges/g:edge", namespaces=_NS)
    node_ids = _unique_ordered_ids(node_elements, "node")
    _unique_ordered_ids(edge_elements, "edge")
    node_intervals: dict[str, list[tuple[Any | None, Any | None]]] = {}
    for node in node_elements:
        node_id = str(node.get("id"))
        node_intervals[node_id] = _element_intervals(node, timeformat)
        _validate_attribute_values(node, "node", declarations, timeformat)
    for edge in edge_elements:
        edge_id = str(edge.get("id"))
        source = edge.get("source")
        target = edge.get("target")
        if source not in node_ids or target not in node_ids:
            raise _semantic(f"Edge {edge_id} references an unknown source or target node.")
        intervals = _element_intervals(edge, timeformat)
        _validate_attribute_values(edge, "edge", declarations, timeformat)
        for interval in intervals:
            if not _contained(interval, node_intervals[source]) or not _contained(
                interval, node_intervals[target]
            ):
                raise _semantic(
                    f"Edge {edge_id} interval is outside one or both endpoint bounds."
                )
    return GexfValidationResult(
        xsd_valid=True,
        semantic_valid=True,
        node_count=len(node_elements),
        edge_count=len(edge_elements),
        timeformat=timeformat,
    )


def _unique_ordered_ids(elements: list[etree._Element], kind: str) -> set[str]:
    identifiers = [str(element.get("id") or "") for element in elements]
    if any(not identifier for identifier in identifiers):
        raise _semantic(f"Every {kind} must have a non-empty id.")
    if len(identifiers) != len(set(identifiers)):
        raise _semantic(f"Duplicate {kind} id.")
    if identifiers != sorted(identifiers):
        raise _semantic(f"{kind.capitalize()} elements are not in stable id order.")
    return set(identifiers)


def _element_intervals(
    element: etree._Element,
    timeformat: str,
) -> list[tuple[Any | None, Any | None]]:
    direct = element.get("start") is not None or element.get("end") is not None
    spells = element.xpath("./g:spells/g:spell", namespaces=_NS)
    if direct and spells:
        raise _semantic("An element cannot mix direct interval bounds and spells.")
    raw_intervals = (
        [(element.get("start"), element.get("end"))]
        if direct
        else [(spell.get("start"), spell.get("end")) for spell in spells]
    )
    parsed: list[tuple[Any | None, Any | None]] = []
    for start_text, end_text in raw_intervals:
        if start_text is None and end_text is None:
            raise _semantic("An interval must contain at least one bound.")
        start = _parse_time(start_text, timeformat)
        end = _parse_time(end_text, timeformat)
        if start is not None and end is not None and start > end:
            raise _semantic("An interval start must not be after its end.")
        parsed.append((start, end))
    if parsed != sorted(parsed, key=_interval_sort_key):
        raise _semantic("Intervals are not in stable temporal order.")
    return parsed


def _parse_time(value: str | None, timeformat: str) -> date | datetime | None:
    if value is None:
        return None
    try:
        if timeformat == "date":
            if "T" in value:
                raise ValueError
            return date.fromisoformat(value)
        if "T" not in value:
            raise ValueError
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.utcoffset() is None:
            raise ValueError
        return parsed
    except ValueError as exc:
        raise _semantic(f"Invalid {timeformat} bound: {value}.") from exc


def _interval_sort_key(interval: tuple[Any | None, Any | None]) -> tuple[str, str]:
    start, end = interval
    return ("" if start is None else start.isoformat(), "" if end is None else end.isoformat())


def _contained(
    child: tuple[Any | None, Any | None],
    parents: list[tuple[Any | None, Any | None]],
) -> bool:
    if not parents:
        return True
    child_start, child_end = child
    for parent_start, parent_end in parents:
        starts_inside = parent_start is None or (
            child_start is not None and child_start >= parent_start
        )
        ends_inside = parent_end is None or (child_end is not None and child_end <= parent_end)
        if starts_inside and ends_inside:
            return True
    return False


def _attribute_declarations(graph: etree._Element) -> dict[tuple[str, str], str]:
    declarations: dict[tuple[str, str], str] = {}
    for group in graph.xpath("./g:attributes", namespaces=_NS):
        class_name = group.get("class")
        for declaration in group.xpath("./g:attribute", namespaces=_NS):
            key = (str(class_name), str(declaration.get("id")))
            if key in declarations:
                raise _semantic(f"Duplicate attribute declaration: {key[0]}/{key[1]}.")
            declarations[key] = str(declaration.get("type"))
    return declarations


def _validate_attribute_values(
    element: etree._Element,
    class_name: str,
    declarations: dict[tuple[str, str], str],
    timeformat: str,
) -> None:
    for value in element.xpath("./g:attvalues/g:attvalue", namespaces=_NS):
        identifier = str(value.get("for"))
        declared_type = declarations.get((class_name, identifier))
        if declared_type is None:
            raise _semantic(
                f"Attribute value {class_name}/{identifier} has no matching declaration."
            )
        _validate_typed_value(str(value.get("value")), declared_type)
        for bound_name in ("start", "end"):
            if value.get(bound_name) is not None:
                _parse_time(value.get(bound_name), timeformat)


def _validate_typed_value(value: str, declared_type: str) -> None:
    scalar_type = declared_type.removeprefix("list") if declared_type.startswith("list") else declared_type
    values = _parse_list(value) if declared_type.startswith("list") else [value]
    try:
        for item in values:
            if scalar_type in {"integer", "long", "biginteger", "byte", "short"}:
                integer = int(item)
                if scalar_type == "byte" and not -128 <= integer <= 127:
                    raise ValueError
                if scalar_type == "short" and not -32768 <= integer <= 32767:
                    raise ValueError
                if scalar_type == "integer" and not -(2**31) <= integer <= 2**31 - 1:
                    raise ValueError
                if scalar_type == "long" and not -(2**63) <= integer <= 2**63 - 1:
                    raise ValueError
            elif scalar_type in {"double", "float"}:
                number = float(item)
                if not math.isfinite(number):
                    raise ValueError
            elif scalar_type == "bigdecimal":
                if not Decimal(item).is_finite():
                    raise ValueError
            elif scalar_type == "boolean" and item not in {"true", "false"}:
                raise ValueError
            elif scalar_type == "char" and len(item) != 1:
                raise ValueError
            elif scalar_type == "anyURI":
                parsed = urlsplit(item)
                if any(ord(character) < 32 for character in item) or (
                    parsed.scheme and not parsed.scheme[0].isalpha()
                ):
                    raise ValueError
    except (ValueError, InvalidOperation) as exc:
        raise _semantic(f"Attribute value {value!r} is not valid for type {declared_type}.") from exc


def _parse_list(value: str) -> list[str]:
    if not value.startswith("[") or not value.endswith("]"):
        raise _semantic(f"Invalid list attribute value: {value!r}.")
    inner = value[1:-1].strip()
    return [] if not inner else [item.strip() for item in inner.split(",")]


def _semantic(message: str) -> GexfValidationError:
    return GexfValidationError(message, reason="gexf_semantic_invalid")
