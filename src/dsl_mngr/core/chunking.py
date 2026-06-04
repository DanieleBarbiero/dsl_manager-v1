from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any


SUPPORTED_CHUNKING_OPTIONS = {
    "include_heading_context",
    "max_chars",
    "merge_small_paragraphs",
    "min_chars",
    "output_chunks_jsonl",
    "preserve_paragraphs",
    "require_normalized_hash_match",
    "strategy",
    "strict_options_fail_on_unsupported_option",
}


class ChunkingError(RuntimeError):
    """Raised when deterministic chunking cannot be completed."""


class UnsupportedChunkingOption(ChunkingError):
    """Raised when a strict chunking profile contains an unsupported option."""

    def __init__(self, option_key: str, message: str | None = None) -> None:
        self.option_key = option_key
        super().__init__(message or f"Unsupported chunking option: {option_key}.")


@dataclass(frozen=True)
class ChunkingOptions:
    strategy: str = "heading_paragraph"
    max_chars: int = 8000
    min_chars: int = 1
    include_heading_context: bool = True
    preserve_paragraphs: bool = True
    merge_small_paragraphs: bool = True
    strict_options_fail_on_unsupported_option: bool = True
    require_normalized_hash_match: bool = True
    output_chunks_jsonl: bool = True


@dataclass(frozen=True)
class MarkdownBlock:
    text: str
    start_char: int
    end_char: int
    heading_path: tuple[str, ...]
    is_heading: bool


@dataclass(frozen=True)
class ChunkCandidate:
    sequence: int
    text: str
    text_hash: str
    start_char: int | None
    end_char: int | None
    heading_path: tuple[str, ...]


def parse_chunking_options(raw_options: dict[str, Any]) -> ChunkingOptions:
    strict = _as_bool(
        raw_options.get("strict_options_fail_on_unsupported_option", True),
        "strict_options_fail_on_unsupported_option",
    )
    unsupported = sorted(set(raw_options) - SUPPORTED_CHUNKING_OPTIONS)
    if unsupported and strict:
        raise UnsupportedChunkingOption(
            unsupported[0],
            f"unsupported_chunking_option: {unsupported[0]}",
        )

    strategy = str(raw_options.get("strategy", "heading_paragraph"))
    if strategy != "heading_paragraph":
        raise UnsupportedChunkingOption("strategy", f"unsupported_chunking_option: strategy={strategy}")

    max_chars = _as_int(raw_options.get("max_chars", 8000), "max_chars")
    min_chars = _as_int(raw_options.get("min_chars", 1), "min_chars")
    if max_chars < 1:
        raise ChunkingError("max_chars must be greater than zero.")
    if min_chars < 1:
        raise ChunkingError("min_chars must be greater than zero.")
    if min_chars > max_chars:
        raise ChunkingError("min_chars must not be greater than max_chars.")

    return ChunkingOptions(
        strategy=strategy,
        max_chars=max_chars,
        min_chars=min_chars,
        include_heading_context=_as_bool(
            raw_options.get("include_heading_context", True),
            "include_heading_context",
        ),
        preserve_paragraphs=_as_bool(raw_options.get("preserve_paragraphs", True), "preserve_paragraphs"),
        merge_small_paragraphs=_as_bool(
            raw_options.get("merge_small_paragraphs", True),
            "merge_small_paragraphs",
        ),
        strict_options_fail_on_unsupported_option=strict,
        require_normalized_hash_match=_as_bool(
            raw_options.get("require_normalized_hash_match", True),
            "require_normalized_hash_match",
        ),
        output_chunks_jsonl=_as_bool(raw_options.get("output_chunks_jsonl", True), "output_chunks_jsonl"),
    )


def chunk_markdown(markdown: str, options: ChunkingOptions) -> list[ChunkCandidate]:
    if options.strategy != "heading_paragraph":
        raise UnsupportedChunkingOption("strategy", f"unsupported_chunking_option: strategy={options.strategy}")

    normalized = normalize_markdown_newlines(markdown)
    if not normalized.strip():
        raise ChunkingError("normalized.md is empty; cannot create non-empty chunks.")

    blocks = _parse_markdown_blocks(normalized)
    if not options.include_heading_context:
        non_heading_blocks = [block for block in blocks if not block.is_heading]
        if non_heading_blocks:
            blocks = non_heading_blocks
    if not blocks:
        raise ChunkingError("normalized.md does not contain chunkable text.")

    chunk_blocks: list[list[MarkdownBlock]] = []
    current: list[MarkdownBlock] = []

    for block in blocks:
        if _assembled_length([block]) > options.max_chars:
            if current:
                chunk_blocks.append(current)
                current = []
            for split_block in _split_large_block(block, options.max_chars):
                chunk_blocks.append([split_block])
            continue

        candidate = [*current, block]
        if current and _assembled_length(candidate) > options.max_chars:
            chunk_blocks.append(current)
            current = [block]
        else:
            current = candidate

    if current:
        chunk_blocks.append(current)

    chunks: list[ChunkCandidate] = []
    for sequence, blocks_for_chunk in enumerate(chunk_blocks, start=1):
        text = _assemble_blocks(blocks_for_chunk)
        if len(text.strip()) < options.min_chars:
            continue
        chunks.append(
            ChunkCandidate(
                sequence=sequence,
                text=text,
                text_hash=sha256_text(text),
                start_char=blocks_for_chunk[0].start_char,
                end_char=blocks_for_chunk[-1].end_char,
                heading_path=blocks_for_chunk[-1].heading_path,
            )
        )

    if not chunks:
        raise ChunkingError("normalized.md produced no non-empty chunks.")
    return chunks


def build_chunk_record(
    *,
    chunk_id: str,
    candidate: ChunkCandidate,
    source_revision_id: str,
    metadata_base: dict[str, Any],
) -> dict[str, Any]:
    metadata = {
        **metadata_base,
        "end_char": candidate.end_char,
        "heading_path": list(candidate.heading_path),
        "source_text_kind": "normalized_markdown",
        "start_char": candidate.start_char,
    }
    return {
        "chunk_id": chunk_id,
        "metadata": metadata,
        "sequence": candidate.sequence,
        "source_revision_id": source_revision_id,
        "status": "active",
        "text": candidate.text,
        "text_hash": candidate.text_hash,
    }


def canonical_chunk_json_line(record: dict[str, Any]) -> str:
    return json.dumps(record, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n"


def canonical_metadata_json(metadata: dict[str, Any]) -> str:
    return json.dumps(metadata, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def chunks_jsonl_content(records: list[dict[str, Any]]) -> str:
    return "".join(canonical_chunk_json_line(record) for record in records)


def chunks_jsonl_hash(records: list[dict[str, Any]]) -> str:
    return sha256_text(chunks_jsonl_content(records))


def normalize_markdown_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _parse_markdown_blocks(text: str) -> list[MarkdownBlock]:
    blocks: list[MarkdownBlock] = []
    heading_stack: list[str] = []
    paragraph_start: int | None = None
    paragraph_end: int | None = None

    def flush_paragraph() -> None:
        nonlocal paragraph_start, paragraph_end
        if paragraph_start is None or paragraph_end is None:
            return
        block_text = _normalize_block_text(text[paragraph_start:paragraph_end])
        if block_text.strip():
            blocks.append(
                MarkdownBlock(
                    text=block_text,
                    start_char=paragraph_start,
                    end_char=paragraph_end,
                    heading_path=tuple(heading_stack),
                    is_heading=False,
                )
            )
        paragraph_start = None
        paragraph_end = None

    position = 0
    for line in text.splitlines(keepends=True):
        line_start = position
        line_end = position + len(line)
        position = line_end

        if not line.strip():
            flush_paragraph()
            continue

        heading = _parse_heading(line)
        if heading is not None:
            flush_paragraph()
            level, title = heading
            heading_stack = heading_stack[: max(0, level - 1)]
            heading_stack.append(title)
            blocks.append(
                MarkdownBlock(
                    text=_normalize_block_text(line),
                    start_char=line_start,
                    end_char=line_end,
                    heading_path=tuple(heading_stack),
                    is_heading=True,
                )
            )
            continue

        if paragraph_start is None:
            paragraph_start = line_start
        paragraph_end = line_end

    flush_paragraph()
    return blocks


def _parse_heading(line: str) -> tuple[int, str] | None:
    match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line.strip())
    if match is None:
        return None
    return len(match.group(1)), match.group(2).strip()


def _normalize_block_text(text: str) -> str:
    return text.strip("\n") + "\n"


def _assemble_blocks(blocks: list[MarkdownBlock]) -> str:
    parts = [block.text.strip("\n") for block in blocks if block.text.strip()]
    return "\n\n".join(parts).strip() + "\n"


def _assembled_length(blocks: list[MarkdownBlock]) -> int:
    return len(_assemble_blocks(blocks))


def _split_large_block(block: MarkdownBlock, max_chars: int) -> list[MarkdownBlock]:
    raw_text = block.text.strip("\n")
    pieces: list[MarkdownBlock] = []
    consumed = 0
    while consumed < len(raw_text):
        remaining = raw_text[consumed:]
        if len(remaining) + 1 <= max_chars:
            piece = remaining
        else:
            split_at = _find_split_point(remaining, max_chars - 1)
            piece = remaining[:split_at]

        leading = len(piece) - len(piece.lstrip())
        trailing = len(piece.rstrip())
        clean_piece = piece.strip()
        if clean_piece:
            start = block.start_char + consumed + leading
            end = block.start_char + consumed + trailing
            pieces.append(
                MarkdownBlock(
                    text=clean_piece + "\n",
                    start_char=start,
                    end_char=end,
                    heading_path=block.heading_path,
                    is_heading=block.is_heading,
                )
            )
        consumed += len(piece)
        while consumed < len(raw_text) and raw_text[consumed].isspace():
            consumed += 1

    return pieces


def _find_split_point(text: str, limit: int) -> int:
    if limit <= 0:
        return 1
    limit = min(limit, len(text))
    for marker in ("\n", ". ", " "):
        index = text.rfind(marker, 0, limit + 1)
        if index > 0:
            return index + (1 if marker == "\n" else len(marker))
    return limit


def _as_bool(value: Any, key: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
    raise ChunkingError(f"Chunking option {key} must be a boolean.")


def _as_int(value: Any, key: str) -> int:
    if isinstance(value, bool):
        raise ChunkingError(f"Chunking option {key} must be an integer.")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ChunkingError(f"Chunking option {key} must be an integer.") from exc
