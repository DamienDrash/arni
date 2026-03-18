"""ARIIA v2.0 – OpenDocument Streaming Parser (ODT / ODS / ODP).

Verwendet odfpy zur Text-Extraktion aus OpenDocument-Formaten.
ODT: Textdokumente (Writer)
ODS: Tabellen (Calc) — liest Zellinhalte zeilenweise
ODP: Präsentationen (Impress) — liest Folieninhalte
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import AsyncIterator

import structlog

from app.ingestion.parsers.base import ParserRegistry, StreamingParser, TextChunk

logger = structlog.get_logger()


@ParserRegistry.register(
    "application/vnd.oasis.opendocument.text",
    "application/vnd.oasis.opendocument.spreadsheet",
    "application/vnd.oasis.opendocument.presentation",
)
class ODTParser(StreamingParser):
    """Parser für OpenDocument-Formate (ODT/ODS/ODP) via odfpy.

    Extrahiert alle Textknoten aus dem Dokument-XML-Baum.
    Unterstützt Writer-Absätze, Calc-Tabellenzellen und Impress-Folien.
    """

    async def parse(self, file_path: Path) -> AsyncIterator[TextChunk]:
        loop = asyncio.get_event_loop()
        texts = await loop.run_in_executor(None, self._extract_texts, file_path)
        char_offset = 0
        for text, page_num in texts:
            yield TextChunk(
                text=text,
                page_num=page_num,
                char_offset=char_offset,
                source_metadata={"parser": "odt", "suffix": file_path.suffix.lower()},
            )
            char_offset += len(text)

    @staticmethod
    def _extract_texts(file_path: Path) -> list[tuple[str, int | None]]:
        try:
            from odf.opendocument import load as odf_load  # type: ignore[import]
            from odf import text as odf_text, table as odf_table  # type: ignore[import]
            from odf.element import Element  # type: ignore[import]
        except ImportError:
            raise RuntimeError("odfpy nicht installiert: pip install odfpy")

        def get_text(element: Element) -> str:
            """Rekursiv alle Textknoten eines Elements zusammenführen."""
            result = []
            if element.nodeType == element.TEXT_NODE:
                result.append(element.data)
            for child in element.childNodes:
                result.append(get_text(child))
            return "".join(result)

        doc = odf_load(str(file_path))
        suffix = file_path.suffix.lower()
        results: list[tuple[str, int | None]] = []

        if suffix == ".ods":
            # Calc: Zeile für Zeile durch alle Tabellen
            for sheet_num, sheet in enumerate(
                doc.spreadsheet.getElementsByType(odf_table.Table), start=1
            ):
                for row in sheet.getElementsByType(odf_table.TableRow):
                    cells = []
                    for cell in row.getElementsByType(odf_table.TableCell):
                        cell_text = get_text(cell).strip()
                        if cell_text:
                            cells.append(cell_text)
                    if cells:
                        results.append((" | ".join(cells), sheet_num))

        elif suffix == ".odp":
            # Impress: Folie für Folie
            from odf.presentation import Page  # type: ignore[import]
            for slide_num, slide in enumerate(
                doc.presentation.getElementsByType(Page), start=1
            ):
                for para in slide.getElementsByType(odf_text.P):
                    line = get_text(para).strip()
                    if len(line) > 10:
                        results.append((line, slide_num))

        else:
            # ODT (Writer): Absatz für Absatz
            for para in doc.text.getElementsByType(odf_text.P):
                line = get_text(para).strip()
                if len(line) > 10:
                    results.append((line, None))

        return results
