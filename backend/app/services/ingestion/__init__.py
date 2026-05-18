"""Multi-platform ingestion pipeline.

Each parser implements :class:`BaseIngestor` and yields normalised
``NormalisedConversation`` records the pipeline persists.
"""

from app.services.ingestion.base import (
    BaseIngestor,
    NormalisedConversation,
    NormalisedMessage,
)

__all__ = ["BaseIngestor", "NormalisedConversation", "NormalisedMessage"]
