"""Plain Text / Markdown Streaming Parser."""
from __future__ import annotations
import asyncio
from pathlib import Path
from typing import AsyncIterator
import structlog
from app.ingestion.parsers.base import ParserRegistry, StreamingParser, TextChunk

logger = structlog.get_logger()


@ParserRegistry.register("text/plain", "text/markdown", "text/x-markdown")
class TextParser(StreamingParser):
    """Line-by-line Text-Parser. Minimaler RAM-Footprint."""

    PARAGRAPH_MIN_CHARS = 50

    async def parse(self, file_path: Path) -> AsyncIterator[TextChunk]:
        loop = asyncio.get_event_loop()

        def _iter_paragraphs():
            results = []
            char_offset = 0
            current_para_lines = []

            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    if line.strip() == "":
                        if current_para_lines:
                            para = "\n".join(current_para_lines).strip()
                            if len(para) >= self.PARAGRAPH_MIN_CHARS:
                                results.append((para, char_offset))
                                char_offset += len(para)
                            current_para_lines = []
                    else:
                        current_para_lines.append(line.rstrip())

                if current_para_lines:
                    para = "\n".join(current_para_lines).strip()
                    if len(para) >= self.PARAGRAPH_MIN_CHARS:
                        results.append((para, char_offset))

            return results

        paragraphs = await loop.run_in_executor(None, _iter_paragraphs)

        for text, char_offset in paragraphs:
            yield TextChunk(
                text=text,
                char_offset=char_offset,
                source_metadata={"parser": "text"},
            )
