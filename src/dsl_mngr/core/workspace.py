from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from dsl_mngr.core.config import DEFAULT_CONFIG, dump_simple_yaml


WORKSPACE_DIRS = (
    "configs/workers",
    "corpus/incoming",
    "corpus/active",
    "corpus/deleted",
    "corpus/ignored",
    "ai/outbox",
    "ai/inbox",
    "ai/imported",
    "artifacts/runs",
    "chunks",
    "exports/dsl",
    "exports/dsl_diff",
    "exports/graph",
    "exports/logs",
    "logs",
)

DEFAULT_ENV = """MDW_WORKSPACE_DIR=.
MDW_DB_PATH=workspace.sqlite
MDW_LOG_LEVEL=INFO
MDW_DEFAULT_DOC_PROFILE=docling.no_images
MDW_AI_OUTBOX=./ai/outbox
MDW_AI_INBOX=./ai/inbox
MDW_ENABLE_WAL=true
"""

DEFAULT_DOCLING_NO_IMAGES_PROFILE = """worker:
  name: normalize_docling
  version: 1.0
docling:
  input_formats: pdf,docx,pptx,html,md,txt
  output_normalized_markdown: true
  output_normalized_json: true
  images_enabled: false
  image_export_mode: placeholder
  generate_page_images: false
  generate_picture_images: false
  ocr_enabled: false
  force_full_page_ocr: false
  tables_enabled: true
  tables_mode: auto
  strict_options_fail_on_unsupported_option: true
"""

DEFAULT_DOCLING_CHUNKING_PROFILE = """worker:
  name: chunk_docling
  version: 1.0
chunking:
  strategy: heading_paragraph
  max_chars: 8000
  min_chars: 1
  include_heading_context: true
  preserve_paragraphs: true
  merge_small_paragraphs: true
  strict_options_fail_on_unsupported_option: true
  require_normalized_hash_match: true
  output_chunks_jsonl: true
"""


@dataclass(frozen=True)
class WorkspaceInitResult:
    workspace_dir: Path


def initialize_workspace(workspace_dir: str | Path) -> WorkspaceInitResult:
    workspace_path = Path(workspace_dir).resolve()
    workspace_path.mkdir(parents=True, exist_ok=True)

    for relative_dir in WORKSPACE_DIRS:
        (workspace_path / relative_dir).mkdir(parents=True, exist_ok=True)

    _write_if_missing(workspace_path / ".env", DEFAULT_ENV)
    _write_if_missing(workspace_path / "configs" / "project.yaml", dump_simple_yaml(DEFAULT_CONFIG))
    _write_if_missing(
        workspace_path / "configs" / "workers" / "docling.no_images.yaml",
        DEFAULT_DOCLING_NO_IMAGES_PROFILE,
    )
    _write_if_missing(
        workspace_path / "configs" / "workers" / "docling.chunking.yaml",
        DEFAULT_DOCLING_CHUNKING_PROFILE,
    )
    (workspace_path / "logs" / "app.jsonl").touch(exist_ok=True)

    return WorkspaceInitResult(workspace_dir=workspace_path)


def _write_if_missing(path: Path, content: str) -> None:
    if not path.exists():
        path.write_text(content, encoding="utf-8", newline="\n")
