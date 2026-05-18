"""ChromaDB-backed embedding store.

Lazily instantiated singleton so we don't pay startup cost in dev.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.config import settings
from app.utils.logger import get_logger

log = get_logger(__name__)

_COLLECTION = "ai_mirror_messages"


@lru_cache(maxsize=1)
def _client() -> chromadb.api.ClientAPI:
    return chromadb.PersistentClient(
        path=settings.chroma_persist_dir,
        settings=ChromaSettings(anonymized_telemetry=False, allow_reset=False),
    )


def get_collection():
    return _client().get_or_create_collection(name=_COLLECTION, metadata={"hnsw:space": "cosine"})


def upsert_messages(
    *,
    ids: list[str],
    documents: list[str],
    metadatas: list[dict[str, Any]],
    embeddings: list[list[float]] | None = None,
) -> None:
    coll = get_collection()
    coll.upsert(ids=ids, documents=documents, metadatas=metadatas, embeddings=embeddings)


def query(
    *,
    text: str,
    top_k: int = 8,
    where: dict[str, Any] | None = None,
) -> dict[str, Any]:
    coll = get_collection()
    return coll.query(query_texts=[text], n_results=top_k, where=where)
