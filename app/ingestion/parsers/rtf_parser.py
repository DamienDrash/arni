"""ARIIA v2.0 – RTF Streaming Parser.

Verwendet striprtf zur reinen Text-Extraktion aus RTF-Dokumenten.
Kein HTML-Rendering, kein Cloud-Call – vollständig lokal.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import AsyncIterator

import structlog

from app.ingestion.parsers.base import ParserRegistry, StreamingParser, TextChunk

logger = structlog.get_logger()


@ParserRegistry.register(
    "application/rtf",
    "text/rtf",
)
class RTFParser(StreamingParser):
    """Parser für RTF-Dokumente via striprtf.

    Liest die Datei vollständig ein und entfernt RTF-Steuerzeichen.
    Gibt Absätze als einzelne TextChunks zurück.
    """

    async def parse(self, file_path: Path) -> AsyncIterator[TextChunk]:
        loop = asyncio.get_event_loop()
        paragraphs = await loop.run_in_executor(None, self._extract_paragraphs, file_path)
        char_offset = 0
        for para in paragraphs:
            yield TextChunk(
                text=para,
                char_offset=char_offset,
                source_metadata={"parser": "rtf"},
            )
            char_offset += len(para)

    @staticmethod
    def _extract_paragraphs(file_path: Path) -> list[str]:
        try:
            from striprtf.striprtf import rtf_to_text  # type: ignore[import]
        except ImportError:
            raise RuntimeError("striprtf nicht installiert: pip install striprtf")

        raw = file_path.read_bytes()
        # RTF-Dateien sind meist Latin-1 oder UTF-8 mit BOM
        for enc in ("utf-8-sig", "latin-1", "cp1252"):
            try:
                rtf_content = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        else:
            rtf_content = raw.decode("latin-1", errors="replace")

        plain = rtf_to_text(rtf_content)

        paragraphs = []
        for line in plain.splitlines():
            line = line.strip()
            if len(line) > 10:
                paragraphs.append(line)

        return paragraphs
