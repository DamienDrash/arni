"""ARIIA v2.0 – Streaming Parser Base Classes."""
from __future__ import annotations
import mimetypes
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncIterator, Optional
import structlog

logger = structlog.get_logger()


@dataclass
class TextChunk:
    """Einzelner Text-Chunk aus einem Dokument."""
    text: str
    page_num: Optional[int] = None
    section: Optional[str] = None
    char_offset: int = 0
    token_estimate: int = 0
    source_metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        # Grobe Token-Schätzung: 4 Zeichen ≈ 1 Token
        if self.token_estimate == 0:
            self.token_estimate = max(1, len(self.text) // 4)


class StreamingParser(ABC):
    """Abstrakte Basisklasse für alle Dokument-Parser.

    Implementierungen MÜSSEN streaming/iterator-basiert arbeiten.
    Maximales RAM-Budget: 256MB pro Dokument.
    """

    MAX_RAM_MB = 256

    @abstractmethod
    async def parse(self, file_path: Path) -> AsyncIterator[TextChunk]:
        """Parse Dokument und yield einzelne TextChunks.

        Args:
            file_path: Pfad zur temporären Datei (auf Worker-Disk)

        Yields:
            TextChunk: Einzelne Text-Segmente mit Metadaten
        """
        ...

    @classmethod
    def supports_mime(cls, mime_type: str) -> bool:
        return mime_type in cls.SUPPORTED_MIMES


class ParserRegistry:
    """Registry: MIME-Type → StreamingParser-Klasse."""

    _registry: dict[str, type[StreamingParser]] = {}
    _fallback: Optional[type[StreamingParser]] = None

    @classmethod
    def register(cls, *mime_types: str):
        """Dekorator zum Registrieren eines Parsers."""
        def decorator(parser_cls: type[StreamingParser]):
            for mime in mime_types:
                cls._registry[mime] = parser_cls
            return parser_cls
        return decorator

    @classmethod
    def register_fallback(cls, parser_cls: type[StreamingParser]):
        cls._fallback = parser_cls
        return parser_cls

    @classmethod
    def get_parser(cls, mime_type: str) -> StreamingParser:
        """Factory: gibt den passenden Parser zurück."""
        # Normalisierung
        clean_mime = mime_type.split(";")[0].strip().lower()

        parser_cls = cls._registry.get(clean_mime)
        if parser_cls is None:
            logger.warning("parser.fallback_used", mime_type=clean_mime)
            parser_cls = cls._fallback
        if parser_cls is None:
            raise ValueError(f"Kein Parser für MIME-Type: {clean_mime}")

        logger.debug("parser.selected", mime_type=clean_mime, parser=parser_cls.__name__)
        return parser_cls()

    @classmethod
    def supported_mimes(cls) -> list[str]:
        return list(cls._registry.keys())
