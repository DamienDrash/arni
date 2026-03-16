"""PDF Streaming Parser via pdfplumber."""
from __future__ import annotations
import asyncio
from pathlib import Path
from typing import AsyncIterator
import structlog
from app.ingestion.parsers.base import ParserRegistry, StreamingParser, TextChunk

logger = structlog.get_logger()


@ParserRegistry.register("application/pdf")
class PDFParser(StreamingParser):
    """Streaming PDF-Parser. Verarbeitet Seite für Seite ohne vollständiges RAM-Laden."""

    MIN_PAGE_TEXT_LENGTH = 50  # Seiten mit weniger Text überspringen (Bilder etc.)

    async def parse(self, file_path: Path) -> AsyncIterator[TextChunk]:
        loop = asyncio.get_event_loop()

        def _iter_pages():
            try:
                import pdfplumber
            except ImportError:
                raise RuntimeError("pdfplumber nicht installiert: pip install pdfplumber")

            with pdfplumber.open(str(file_path)) as pdf:
                for page_num, page in enumerate(pdf.pages, start=1):
                    text = page.extract_text() or ""
                    if len(text.strip()) < self.MIN_PAGE_TEXT_LENGTH:
                        continue
                    yield page_num, text

        char_offset = 0
        # Seiten in Executor um Event-Loop nicht zu blockieren
        pages = await loop.run_in_executor(None, lambda: list(_iter_pages()))

        for page_num, text in pages:
            # Seite in Absätze aufteilen
            paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
            for para in paragraphs:
                if len(para) > 20:  # Zu kurze Fragmente ignorieren
                    yield TextChunk(
                        text=para,
                        page_num=page_num,
                        char_offset=char_offset,
                        source_metadata={"parser": "pdfplumber"},
                    )
                    char_offset += len(para)
