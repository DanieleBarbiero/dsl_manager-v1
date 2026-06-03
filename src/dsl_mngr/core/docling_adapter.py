from __future__ import annotations

from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any


SUPPORTED_DOCLING_OPTIONS = {
    "force_full_page_ocr",
    "generate_page_images",
    "generate_picture_images",
    "image_export_mode",
    "images_enabled",
    "input_formats",
    "ocr_enabled",
    "output_normalized_json",
    "output_normalized_markdown",
    "strict_options_fail_on_unsupported_option",
    "tables_enabled",
    "tables_mode",
}


INPUT_FORMAT_ALIASES = {
    "docx": "DOCX",
    "html": "HTML",
    "htm": "HTML",
    "md": "MD",
    "pdf": "PDF",
    "pptx": "PPTX",
    "text": "MD",
    "txt": "MD",
}


class DoclingAdapterError(RuntimeError):
    """Raised when Docling normalization fails."""


class UnsupportedDoclingOption(DoclingAdapterError):
    """Raised when a worker profile contains an unsupported Docling option."""

    def __init__(self, option_key: str) -> None:
        super().__init__(f"unsupported_docling_option: {option_key}")
        self.option_key = option_key


@dataclass(frozen=True)
class DoclingNormalizationResult:
    markdown: str
    document: dict[str, Any]
    docling_version: str
    resolved_options: dict[str, Any]


def normalize_document_with_docling(
    input_path: str | Path,
    docling_options: dict[str, Any],
) -> DoclingNormalizationResult:
    resolved_options = resolve_docling_options(docling_options)

    imports = _load_docling_imports()
    converter = imports["DocumentConverter"](
        allowed_formats=_allowed_input_formats(imports["InputFormat"], resolved_options),
        format_options=_format_options(imports, resolved_options),
    )
    result = converter.convert(Path(input_path))
    markdown = normalize_markdown(result.document.export_to_markdown())
    document = result.document.export_to_dict()

    return DoclingNormalizationResult(
        markdown=markdown,
        document=document,
        docling_version=_docling_version(),
        resolved_options=resolved_options,
    )


def resolve_docling_options(options: dict[str, Any]) -> dict[str, Any]:
    strict = bool(options.get("strict_options_fail_on_unsupported_option", True))
    unsupported = sorted(set(options) - SUPPORTED_DOCLING_OPTIONS)
    if unsupported and strict:
        raise UnsupportedDoclingOption(unsupported[0])

    resolved = {
        "force_full_page_ocr": bool(options.get("force_full_page_ocr", False)),
        "generate_page_images": bool(options.get("generate_page_images", False)),
        "generate_picture_images": bool(options.get("generate_picture_images", False)),
        "image_export_mode": str(options.get("image_export_mode", "placeholder")),
        "images_enabled": bool(options.get("images_enabled", False)),
        "input_formats": _parse_input_formats(options.get("input_formats", "pdf,docx,pptx,html,md,txt")),
        "ocr_enabled": bool(options.get("ocr_enabled", False)),
        "output_normalized_json": bool(options.get("output_normalized_json", True)),
        "output_normalized_markdown": bool(options.get("output_normalized_markdown", True)),
        "strict_options_fail_on_unsupported_option": strict,
        "tables_enabled": bool(options.get("tables_enabled", True)),
        "tables_mode": str(options.get("tables_mode", "auto")).lower(),
    }

    if resolved["images_enabled"]:
        raise UnsupportedDoclingOption("images_enabled")
    if resolved["generate_page_images"]:
        raise UnsupportedDoclingOption("generate_page_images")
    if resolved["generate_picture_images"]:
        raise UnsupportedDoclingOption("generate_picture_images")
    if resolved["image_export_mode"] != "placeholder":
        raise UnsupportedDoclingOption("image_export_mode")
    if not resolved["output_normalized_markdown"]:
        raise UnsupportedDoclingOption("output_normalized_markdown")
    if not resolved["output_normalized_json"]:
        raise UnsupportedDoclingOption("output_normalized_json")
    if resolved["tables_mode"] not in {"auto", "accurate", "fast"}:
        raise UnsupportedDoclingOption("tables_mode")

    return resolved


def normalize_markdown(markdown: str) -> str:
    normalized = markdown.replace("\r\n", "\n").replace("\r", "\n")
    return normalized if normalized.endswith("\n") else normalized + "\n"


def _parse_input_formats(value: Any) -> list[str]:
    if isinstance(value, str):
        parts = [part.strip().lower() for part in value.split(",")]
    elif isinstance(value, list):
        parts = [str(part).strip().lower() for part in value]
    else:
        raise UnsupportedDoclingOption("input_formats")

    formats = []
    for part in parts:
        if not part:
            continue
        mapped = INPUT_FORMAT_ALIASES.get(part)
        if mapped is None:
            raise UnsupportedDoclingOption("input_formats")
        if mapped not in formats:
            formats.append(mapped)
    if not formats:
        raise UnsupportedDoclingOption("input_formats")
    return formats


def _allowed_input_formats(input_format: Any, resolved_options: dict[str, Any]) -> list[Any]:
    return [getattr(input_format, name) for name in resolved_options["input_formats"]]


def _format_options(imports: dict[str, Any], resolved_options: dict[str, Any]) -> dict[Any, Any]:
    input_format = imports["InputFormat"]
    simple_options = imports["ConvertPipelineOptions"](
        allow_external_plugins=False,
        do_chart_extraction=False,
        do_picture_classification=False,
        do_picture_description=False,
        enable_remote_services=False,
    )
    pdf_options = imports["PdfPipelineOptions"](
        allow_external_plugins=False,
        do_chart_extraction=False,
        do_code_enrichment=False,
        do_formula_enrichment=False,
        do_ocr=resolved_options["ocr_enabled"],
        do_picture_classification=False,
        do_picture_description=False,
        do_table_structure=resolved_options["tables_enabled"],
        enable_remote_services=False,
        generate_page_images=False,
        generate_picture_images=False,
    )
    if hasattr(pdf_options, "generate_table_images"):
        pdf_options.generate_table_images = False
    if hasattr(pdf_options, "generate_parsed_pages"):
        pdf_options.generate_parsed_pages = False
    if hasattr(pdf_options, "ocr_options") and hasattr(pdf_options.ocr_options, "force_full_page_ocr"):
        pdf_options.ocr_options.force_full_page_ocr = resolved_options["force_full_page_ocr"]

    _apply_table_mode(imports, pdf_options, resolved_options["tables_mode"])

    options: dict[Any, Any] = {}
    if input_format.PDF in _allowed_input_formats(input_format, resolved_options):
        options[input_format.PDF] = imports["PdfFormatOption"](pipeline_options=pdf_options)
    if input_format.DOCX in _allowed_input_formats(input_format, resolved_options):
        options[input_format.DOCX] = imports["WordFormatOption"](pipeline_options=simple_options)
    if input_format.PPTX in _allowed_input_formats(input_format, resolved_options):
        options[input_format.PPTX] = imports["PowerpointFormatOption"](pipeline_options=simple_options)
    if input_format.HTML in _allowed_input_formats(input_format, resolved_options):
        options[input_format.HTML] = imports["HTMLFormatOption"](pipeline_options=simple_options)
    if input_format.MD in _allowed_input_formats(input_format, resolved_options):
        options[input_format.MD] = imports["MarkdownFormatOption"](pipeline_options=simple_options)
    return options


def _apply_table_mode(imports: dict[str, Any], pdf_options: Any, mode: str) -> None:
    if mode == "auto":
        return
    table_options = getattr(pdf_options, "table_structure_options", None)
    if table_options is None or not hasattr(table_options, "mode"):
        raise UnsupportedDoclingOption("tables_mode")
    table_former_mode = imports["TableFormerMode"]
    if mode == "accurate":
        table_options.mode = table_former_mode.ACCURATE
    elif mode == "fast" and hasattr(table_former_mode, "FAST"):
        table_options.mode = table_former_mode.FAST
    else:
        raise UnsupportedDoclingOption("tables_mode")


def _load_docling_imports() -> dict[str, Any]:
    try:
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import (
            ConvertPipelineOptions,
            PdfPipelineOptions,
            TableFormerMode,
        )
        from docling.document_converter import (
            DocumentConverter,
            HTMLFormatOption,
            MarkdownFormatOption,
            PdfFormatOption,
            PowerpointFormatOption,
            WordFormatOption,
        )
    except Exception as exc:  # pragma: no cover - defensive around external dependency.
        raise DoclingAdapterError(f"docling_import_failed: {exc}") from exc

    return {
        "ConvertPipelineOptions": ConvertPipelineOptions,
        "DocumentConverter": DocumentConverter,
        "HTMLFormatOption": HTMLFormatOption,
        "InputFormat": InputFormat,
        "MarkdownFormatOption": MarkdownFormatOption,
        "PdfFormatOption": PdfFormatOption,
        "PdfPipelineOptions": PdfPipelineOptions,
        "PowerpointFormatOption": PowerpointFormatOption,
        "TableFormerMode": TableFormerMode,
        "WordFormatOption": WordFormatOption,
    }


def _docling_version() -> str:
    try:
        return version("docling")
    except PackageNotFoundError:
        return "unknown"
