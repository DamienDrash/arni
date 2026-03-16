"""ARIIA v2.0 – Semantic Chunker.

Tiktoken-basiertes Chunking mit Overlap.
Target: 512 Tokens/Chunk, 50 Token Overlap.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Iterator
import structlog

logger = structlog.get_logger()

TARGET_TOKENS = 512
OVERLAP_TOKENS = 50
MIN_CHUNK_TOKENS = 20


@dataclass
class SemanticChunk:
    """Finaler Chunk bereit für Embedding."""
    text: str
    chunk_index: int
    page_num: int | None
    section: str | None
    char_offset: int
    token_count: int
    source_metadata: dict = field(default_factory=dict)


class SemanticChunker:
    """Tiktoken-basierter Chunker mit konfigurierbarer Größe und Overlap."""

    def __init__(
        self,
        target_tokens: int = TARGET_TOKENS,
        overlap_tokens: int = OVERLAP_TOKENS,
        model: str = "text-embedding-3-small",
    ):
        self.target_tokens = target_tokens
        self.overlap_tokens = overlap_tokens
        self._enc = None
        self._model = model

    def _get_encoder(self):
        if self._enc is None:
            try:
                import tiktoken
                self._enc = tiktoken.encoding_for_model(self._model)
            except Exception:
                import tiktoken
                self._enc = tiktoken.get_encoding("cl100k_base")
        return self._enc

    def _count_tokens(self, text: str) -> int:
        try:
            return len(self._get_encoder().encode(text))
        except Exception:
            return len(text) // 4

    def chunk_text_chunks(self, text_chunks) -> Iterator[SemanticChunk]:
        """Konvertiert TextChunks in SemanticChunks mit korrekter Größe."""
        buffer_text = ""
        buffer_tokens = 0
        chunk_index = 0
        last_page = None
        last_section = None
        last_offset = 0
        last_metadata: dict = {}

        for tc in text_chunks:
            tc_tokens = self._count_tokens(tc.text)

            if tc.page_num is not None:
                last_page = tc.page_num
            if tc.section is not None:
                last_section = tc.section
            last_metadata = tc.source_metadata

            # Wenn aktueller Chunk zu groß für Buffer → flush
            if buffer_tokens + tc_tokens > self.target_tokens and buffer_text:
                yield SemanticChunk(
                    text=buffer_text.strip(),
                    chunk_index=chunk_index,
                    page_num=last_page,
                    section=last_section,
                    char_offset=last_offset,
                    token_count=buffer_tokens,
                    source_metadata=last_metadata,
                )
                chunk_index += 1

                # Overlap: letzten Teil behalten
                if self.overlap_tokens > 0:
                    enc = self._get_encoder()
                    try:
                        tokens = enc.encode(buffer_text)
                        overlap_text = enc.decode(tokens[-self.overlap_tokens:])
                        buffer_text = overlap_text + " " + tc.text
                        buffer_tokens = self._count_tokens(buffer_text)
                    except Exception:
                        buffer_text = tc.text
                        buffer_tokens = tc_tokens
                else:
                    buffer_text = tc.text
                    buffer_tokens = tc_tokens
            else:
                buffer_text = (buffer_text + " " + tc.text).strip() if buffer_text else tc.text
                buffer_tokens += tc_tokens

            last_offset = tc.char_offset

        # Restlicher Buffer
        if buffer_text.strip() and buffer_tokens >= MIN_CHUNK_TOKENS:
            yield SemanticChunk(
                text=buffer_text.strip(),
                chunk_index=chunk_index,
                page_num=last_page,
                section=last_section,
                char_offset=last_offset,
                token_count=buffer_tokens,
                source_metadata=last_metadata,
            )
