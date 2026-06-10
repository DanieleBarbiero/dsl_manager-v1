from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any


SUPPORTED_XML_FORM_OPTIONS = {
    "infer_edit_relations",
    "malformed_xml_policy",
    "output_fragments_jsonl",
    "parse_buttons",
    "parse_fields",
    "parse_required_fields",
    "parse_table_column_references",
    "parser",
    "require_root_form",
    "strict_options_fail_on_unsupported_option",
}


class XmlFormParserError(RuntimeError):
    """Raised when XML form parsing cannot be completed."""


class UnsupportedXmlFormOption(XmlFormParserError):
    """Raised when a strict XML form profile contains an unsupported option."""

    def __init__(self, option_key: str, message: str | None = None) -> None:
        self.option_key = option_key
        super().__init__(message or f"Unsupported XML form option: {option_key}.")


@dataclass(frozen=True)
class XmlFormOptions:
    parser: str = "elementtree"
    require_root_form: bool = True
    parse_fields: bool = True
    parse_buttons: bool = True
    parse_required_fields: bool = True
    parse_table_column_references: bool = True
    infer_edit_relations: bool = True
    strict_options_fail_on_unsupported_option: bool = True
    malformed_xml_policy: str = "fail"
    output_fragments_jsonl: bool = True


@dataclass(frozen=True)
class TextSpan:
    text: str
    line_start: int
    line_end: int
    char_start: int
    char_end: int


@dataclass(frozen=True)
class XmlField:
    name: str
    label: str | None
    table_name: str | None
    column_name: str | None
    required: bool
    span: TextSpan

    def to_dict(self) -> dict[str, Any]:
        return {
            "column_name": self.column_name,
            "label": self.label,
            "name": self.name,
            "required": self.required,
            "table_name": self.table_name,
        }


@dataclass(frozen=True)
class XmlButton:
    name: str
    label: str | None
    action_kind: str
    span: TextSpan

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_kind": self.action_kind,
            "label": self.label,
            "name": self.name,
        }


@dataclass(frozen=True)
class XmlForm:
    name: str
    title: str | None
    fields: tuple[XmlField, ...]
    buttons: tuple[XmlButton, ...]
    table_column_references: tuple[dict[str, str], ...]
    edit_relations: tuple[dict[str, Any], ...]
    span: TextSpan

    def to_dict(self) -> dict[str, Any]:
        return {
            "buttons": [button.to_dict() for button in self.buttons],
            "edit_relations": list(self.edit_relations),
            "fields": [field.to_dict() for field in self.fields],
            "name": self.name,
            "table_column_references": list(self.table_column_references),
            "table_references": self.table_references,
            "title": self.title,
        }

    @property
    def required_field_count(self) -> int:
        return sum(1 for field in self.fields if field.required)

    @property
    def table_references(self) -> list[str]:
        return sorted({reference["table_name"] for reference in self.table_column_references})


@dataclass(frozen=True)
class XmlFormParseResult:
    normalized_text: str
    forms: tuple[XmlForm, ...]
    parser: str
    warnings: tuple[dict[str, Any], ...]

    @property
    def form_count(self) -> int:
        return len(self.forms)

    @property
    def field_count(self) -> int:
        return sum(len(form.fields) for form in self.forms)

    @property
    def required_field_count(self) -> int:
        return sum(form.required_field_count for form in self.forms)

    @property
    def button_count(self) -> int:
        return sum(len(form.buttons) for form in self.forms)

    @property
    def table_reference_count(self) -> int:
        return sum(len(form.table_references) for form in self.forms)

    @property
    def edit_relation_count(self) -> int:
        return sum(len(form.edit_relations) for form in self.forms)

    def to_objects(self) -> dict[str, Any]:
        return {
            "forms": [form.to_dict() for form in self.forms],
            "warnings": list(self.warnings),
        }

    def edit_relations(self) -> list[dict[str, Any]]:
        return [
            relation
            for form in self.forms
            for relation in form.edit_relations
        ]


def parse_xml_form_options(raw_options: dict[str, Any]) -> XmlFormOptions:
    strict = _as_bool(
        raw_options.get("strict_options_fail_on_unsupported_option", True),
        "strict_options_fail_on_unsupported_option",
    )
    unsupported = sorted(set(raw_options) - SUPPORTED_XML_FORM_OPTIONS)
    if unsupported and strict:
        raise UnsupportedXmlFormOption(
            unsupported[0],
            f"unsupported_xml_form_option: {unsupported[0]}",
        )

    parser = str(raw_options.get("parser", "elementtree")).strip().lower()
    if parser != "elementtree":
        raise UnsupportedXmlFormOption("parser", f"unsupported_xml_form_option: parser={parser}")

    malformed_policy = str(raw_options.get("malformed_xml_policy", "fail")).strip().lower()
    if malformed_policy != "fail":
        raise UnsupportedXmlFormOption(
            "malformed_xml_policy",
            f"unsupported_xml_form_option: malformed_xml_policy={malformed_policy}",
        )

    return XmlFormOptions(
        parser=parser,
        require_root_form=_as_bool(raw_options.get("require_root_form", True), "require_root_form"),
        parse_fields=_as_bool(raw_options.get("parse_fields", True), "parse_fields"),
        parse_buttons=_as_bool(raw_options.get("parse_buttons", True), "parse_buttons"),
        parse_required_fields=_as_bool(
            raw_options.get("parse_required_fields", True),
            "parse_required_fields",
        ),
        parse_table_column_references=_as_bool(
            raw_options.get("parse_table_column_references", True),
            "parse_table_column_references",
        ),
        infer_edit_relations=_as_bool(
            raw_options.get("infer_edit_relations", True),
            "infer_edit_relations",
        ),
        strict_options_fail_on_unsupported_option=strict,
        malformed_xml_policy=malformed_policy,
        output_fragments_jsonl=_as_bool(
            raw_options.get("output_fragments_jsonl", True),
            "output_fragments_jsonl",
        ),
    )


def parse_xml_form_text(text: str, options: XmlFormOptions) -> XmlFormParseResult:
    normalized = normalize_xml_newlines(text)
    if not normalized.strip():
        raise XmlFormParserError("XML form input is empty.")

    try:
        root = ET.fromstring(normalized)
    except ET.ParseError as exc:
        raise XmlFormParserError(f"Malformed XML form input: {exc}.") from exc

    root_tag = _local_tag(root.tag)
    if options.require_root_form and root_tag != "form":
        raise XmlFormParserError("XML form root element must be <form>.")

    form_elements = [root] if root_tag == "form" else [
        element for element in root.iter() if _local_tag(element.tag) == "form"
    ]
    if not form_elements:
        raise XmlFormParserError("No <form> element was found.")

    forms: list[XmlForm] = []
    form_cursor = 0
    for form_element in form_elements:
        form = _parse_form_element(
            normalized,
            form_element,
            options,
            start_cursor=form_cursor,
        )
        forms.append(form)
        form_cursor = form.span.char_end

    return XmlFormParseResult(
        normalized_text=normalized,
        forms=tuple(forms),
        parser=options.parser,
        warnings=(),
    )


def build_fragment_records(
    parse_result: XmlFormParseResult,
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

    for form in parse_result.forms:
        form_selector = f"/form[@name='{_selector_escape(form.name)}']"
        add_record(
            fragment_type="xml_form",
            path_or_selector=form_selector,
            span=form.span,
            metadata={
                "button_count": len(form.buttons),
                "edit_relations": list(form.edit_relations),
                "field_count": len(form.fields),
                "form_name": form.name,
                "object_type": "form",
                "required_field_count": form.required_field_count,
                "table_column_references": list(form.table_column_references),
                "table_references": form.table_references,
                **({"title": form.title} if form.title is not None else {}),
            },
        )

        for field in form.fields:
            field_metadata: dict[str, Any] = {
                "field_name": field.name,
                "form_name": form.name,
                "object_type": "field",
                "required": field.required,
            }
            if field.label is not None:
                field_metadata["label"] = field.label
            if field.table_name is not None:
                field_metadata["table_name"] = field.table_name
            if field.column_name is not None:
                field_metadata["column_name"] = field.column_name
            if field.table_name is not None and field.column_name is not None:
                field_metadata["mapping_type"] = "form_field_to_column"
            add_record(
                fragment_type="xml_field",
                path_or_selector=f"{form_selector}/field[@name='{_selector_escape(field.name)}']",
                span=field.span,
                metadata=field_metadata,
            )

        for button in form.buttons:
            button_metadata: dict[str, Any] = {
                "action_kind": button.action_kind,
                "button_name": button.name,
                "form_name": form.name,
                "object_type": "button",
            }
            if button.label is not None:
                button_metadata["label"] = button.label
            add_record(
                fragment_type="xml_button",
                path_or_selector=f"{form_selector}/button[@name='{_selector_escape(button.name)}']",
                span=button.span,
                metadata=button_metadata,
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


def normalize_xml_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _parse_form_element(
    normalized: str,
    form_element: ET.Element[str],
    options: XmlFormOptions,
    *,
    start_cursor: int,
) -> XmlForm:
    form_name = _required_attribute(form_element, "name", "form.name")
    title = _optional_attribute(form_element, "title")
    form_span = _find_element_span(normalized, "form", form_name, start_cursor=start_cursor)

    fields: list[XmlField] = []
    if options.parse_fields:
        field_cursor = form_span.char_start
        for field_element in form_element.iter():
            if _local_tag(field_element.tag) != "field":
                continue
            field = _parse_field_element(
                normalized,
                field_element,
                options,
                start_cursor=field_cursor,
            )
            fields.append(field)
            field_cursor = field.span.char_end

    buttons: list[XmlButton] = []
    if options.parse_buttons:
        button_cursor = form_span.char_start
        for button_element in form_element.iter():
            if _local_tag(button_element.tag) != "button":
                continue
            button = _parse_button_element(
                normalized,
                button_element,
                start_cursor=button_cursor,
            )
            buttons.append(button)
            button_cursor = button.span.char_end

    table_column_references = (
        _table_column_references(fields)
        if options.parse_table_column_references
        else ()
    )
    edit_relations = (
        _edit_relations(form_name, fields)
        if options.infer_edit_relations and options.parse_table_column_references
        else ()
    )

    return XmlForm(
        name=form_name,
        title=title,
        fields=tuple(fields),
        buttons=tuple(buttons),
        table_column_references=table_column_references,
        edit_relations=edit_relations,
        span=form_span,
    )


def _parse_field_element(
    normalized: str,
    field_element: ET.Element[str],
    options: XmlFormOptions,
    *,
    start_cursor: int,
) -> XmlField:
    field_name = _required_attribute(field_element, "name", "field.name")
    required = False
    if options.parse_required_fields:
        required = _required_attribute_as_bool(field_element.get("required"), "field.required")
    return XmlField(
        name=field_name,
        label=_optional_attribute(field_element, "label"),
        table_name=_optional_attribute(field_element, "table"),
        column_name=_optional_attribute(field_element, "column"),
        required=required,
        span=_find_element_span(normalized, "field", field_name, start_cursor=start_cursor),
    )


def _parse_button_element(
    normalized: str,
    button_element: ET.Element[str],
    *,
    start_cursor: int,
) -> XmlButton:
    button_name = _required_attribute(button_element, "name", "button.name")
    label = _optional_attribute(button_element, "label")
    return XmlButton(
        name=button_name,
        label=label,
        action_kind=_infer_action_kind(button_name, label),
        span=_find_element_span(normalized, "button", button_name, start_cursor=start_cursor),
    )


def _table_column_references(fields: list[XmlField]) -> tuple[dict[str, str], ...]:
    references = [
        {
            "column_name": field.column_name,
            "field_name": field.name,
            "table_name": field.table_name,
        }
        for field in fields
        if field.table_name is not None and field.column_name is not None
    ]
    return tuple(references)


def _edit_relations(form_name: str, fields: list[XmlField]) -> tuple[dict[str, Any], ...]:
    by_table: dict[str, list[str]] = {}
    for field in fields:
        if field.table_name is None or field.column_name is None:
            continue
        by_table.setdefault(field.table_name, []).append(field.name)
    return tuple(
        {
            "field_names": by_table[table_name],
            "relation_type": "edits",
            "source_form": form_name,
            "target_table": table_name,
        }
        for table_name in sorted(by_table)
    )


def _find_element_span(
    text: str,
    tag_name: str,
    name_value: str,
    *,
    start_cursor: int,
) -> TextSpan:
    tag_pattern = re.compile(rf"<\s*{re.escape(tag_name)}\b[^>]*>", re.IGNORECASE)
    for match in tag_pattern.finditer(text, max(0, start_cursor)):
        tag_text = match.group(0)
        if not _tag_has_name(tag_text, name_value):
            continue
        if tag_text.rstrip().endswith("/>"):
            start, end = match.start(), match.end()
        else:
            closing_pattern = re.compile(rf"</\s*{re.escape(tag_name)}\s*>", re.IGNORECASE)
            closing = closing_pattern.search(text, match.end())
            if closing is None:
                raise XmlFormParserError(f"Element <{tag_name}> has no closing tag.")
            start, end = match.start(), closing.end()
        fragment_text = text[start:end]
        return TextSpan(
            text=fragment_text,
            line_start=_line_for_offset(text, start),
            line_end=_line_for_offset(text, max(start, end - 1)),
            char_start=start,
            char_end=end,
        )
    raise XmlFormParserError(f"Could not locate text span for <{tag_name} name={name_value!r}>.")


def _tag_has_name(tag_text: str, name_value: str) -> bool:
    return re.search(
        rf"\bname\s*=\s*(['\"]){re.escape(name_value)}\1",
        tag_text,
        re.IGNORECASE,
    ) is not None


def _required_attribute(element: ET.Element[str], name: str, label: str) -> str:
    value = element.get(name)
    if value is None or not value.strip():
        raise XmlFormParserError(f"Missing required XML form attribute: {label}.")
    return value.strip()


def _optional_attribute(element: ET.Element[str], name: str) -> str | None:
    value = element.get(name)
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _required_attribute_as_bool(value: str | None, label: str) -> bool:
    if value is None or not value.strip():
        return False
    lowered = value.strip().lower()
    if lowered in {"1", "true", "yes"}:
        return True
    if lowered in {"0", "false", "no"}:
        return False
    raise XmlFormParserError(f"XML boolean attribute {label} has unsupported value: {value}.")


def _infer_action_kind(name: str, label: str | None) -> str:
    upper_name = name.strip().upper()
    lowered_label = (label or "").strip().lower()
    if upper_name in {"SAVE", "SALVA"} or "salva" in lowered_label:
        return "save"
    if upper_name in {"CONFIRM", "CONFERMA"} or "conferma" in lowered_label:
        return "confirm"
    if upper_name in {"DELETE", "ELIMINA"} or "elimina" in lowered_label:
        return "delete"
    if upper_name in {"CANCEL", "ANNULLA"} or "annulla" in lowered_label:
        return "cancel"
    return "unknown"


def _local_tag(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag


def _line_for_offset(text: str, offset: int) -> int:
    return text.count("\n", 0, max(0, offset)) + 1


def _next_fragment_id(start_number: int, used_fragment_ids: set[str]) -> str:
    number = max(1, start_number)
    while True:
        fragment_id = f"FRAG_{number:06d}"
        if fragment_id not in used_fragment_ids:
            return fragment_id
        number += 1


def _selector_escape(value: str) -> str:
    return value.replace("'", "&apos;")


def _as_bool(value: Any, key: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
    raise XmlFormParserError(f"XML form option {key} must be a boolean.")
