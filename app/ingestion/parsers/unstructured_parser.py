"""Unstructured.io Fallback Parser für unbekannte Formate."""
from __future__ import annotations
import asyncio
from pathlib import Path
from typing import AsyncIterator
import structlog
from app.ingestion.parsers.base import ParserRegistry, StreamingParser, TextChunk

logger = structlog.get_logger()


@ParserRegistry.register_fallback
class UnstructuredParser(StreamingParser):
    """Catch-All Parser via unstructured[local]. Unterstützt 30+ Formate.
    Kein Cloud-Call - rein lokal.
    """

    async def parse(self, file_path: Path) -> AsyncIterator[TextChunk]:
        loop = asyncio.get_event_loop()

        def _parse():
            try:
                from unstructured.partition.auto import partition
            except ImportError:
                raise RuntimeError(
                    "unstructured nicht installiert: pip install 'unstructured[local]'"
                )

            elements = partition(filename=str(file_path))
            results = []
            char_offset = 0

            for el in elements:
                text = str(el).strip()
                if len(text) > 20:
                    results.append((text, char_offset))
                    char_offset += len(text)

            return results

        elements = await loop.run_in_executor(None, _parse)

        for text, char_offset in elements:
            yield TextChunk(
                text=text,
                char_offset=char_offset,
                source_metadata={"parser": "unstructured"},
            )
