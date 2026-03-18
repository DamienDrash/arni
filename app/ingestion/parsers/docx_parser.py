"""DOCX Streaming Parser via python-docx."""
from __future__ import annotations
import asyncio
from pathlib import Path
from typing import AsyncIterator
import structlog
from app.ingestion.parsers.base import ParserRegistry, StreamingParser, TextChunk

logger = structlog.get_logger()

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@ParserRegistry.register(DOCX_MIME, "application/msword")
class DOCXParser(StreamingParser):
    """Streaming DOCX-Parser. Paragraph-Iterator ohne vollständiges RAM-Laden."""

    async def parse(self, file_path: Path) -> AsyncIterator[TextChunk]:
        loop = asyncio.get_event_loop()

        def _iter_paragraphs():
            try:
                from docx import Document
            except ImportError:
                raise RuntimeError("python-docx nicht installiert: pip install python-docx")

            doc = Document(str(file_path))
            current_section = None
            char_offset = 0
            results = []

            for para in doc.paragraphs:
                text = para.text.strip()
                if not text:
                    continue

                # Heading-Erkennung für Section-Metadata
                if para.style.name.startswith("Heading"):
                    current_section = text
                    continue

                if len(text) > 20:
                    results.append((text, current_section, char_offset))
                    char_offset += len(text)

            return results

        paragraphs = await loop.run_in_executor(None, _iter_paragraphs)

        for text, section, char_offset in paragraphs:
            yield TextChunk(
                text=text,
                section=section,
                char_offset=char_offset,
                source_metadata={"parser": "python-docx"},
            )
