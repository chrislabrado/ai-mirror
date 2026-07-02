"""Top-level ingestion pipeline.

1. Persist the upload to disk.
2. If a ZIP, walk its entries; otherwise treat the file as a single payload.
3. Auto-detect the source unless explicitly provided, run the parser,
   and persist normalised conversations + messages.
"""
from __future__ import annotations

import shutil
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation, Source
from app.models.ingestion_job import IngestionJob
from app.models.message import Message
from app.schemas.ingest import IngestResponse
from app.services.ingestion.base import BaseIngestor, NormalisedConversation
from app.services.ingestion.chatgpt import ChatGPTIngestor
from app.services.ingestion.claude import ClaudeIngestor
from app.services.ingestion.claude_code import ClaudeCodeIngestor
from app.services.ingestion.gemini import GeminiIngestor
from app.services.ingestion.grok import GrokIngestor
from app.services.ingestion.local import LocalModelIngestor
from app.services.ingestion.openclaw import OpenClawIngestor
from app.services.ingestion.perplexity import PerplexityIngestor
from app.utils.logger import get_logger

log = get_logger(__name__)


_INGESTORS: dict[str, BaseIngestor] = {
    "chatgpt": ChatGPTIngestor(),
    "claude": ClaudeIngestor(),
    "claude_code": ClaudeCodeIngestor(),
    "openclaw": OpenClawIngestor(),
    "grok": GrokIngestor(),
    "gemini": GeminiIngestor(),
    "perplexity": PerplexityIngestor(),
    "local": LocalModelIngestor(),
}


def _detect(file: Path) -> BaseIngestor | None:
    try:
        head = file.read_text(encoding="utf-8", errors="ignore")[:65536]
    except OSError:
        return None
    for ing in _INGESTORS.values():
        if ing.detect(file, head):
            return ing
    return None


async def _get_or_create_source(db: AsyncSession, slug: str, display_name: str) -> Source:
    result = await db.execute(select(Source).where(Source.slug == slug))
    src = result.scalar_one_or_none()
    if src is None:
        src = Source(slug=slug, display_name=display_name)
        db.add(src)
        await db.flush()
    return src


def _expand_inputs(saved: Path, scratch: Path) -> list[Path]:
    if saved.suffix.lower() == ".zip":
        with zipfile.ZipFile(saved) as zf:
            zf.extractall(scratch)
        return [
            p for p in scratch.rglob("*")
            if p.is_file() and p.suffix.lower() in {".json", ".jsonl", ".md", ".markdown", ".html", ".htm"}
        ]
    return [saved]


async def run_ingestion(
    *,
    db: AsyncSession,
    upload: UploadFile,
    source: str,
    label: str | None,
) -> IngestResponse:
    started = datetime.utcnow()
    scratch_dir = Path(tempfile.mkdtemp(prefix="ai_mirror_ingest_"))
    saved_path = scratch_dir / (upload.filename or "upload.bin")
    with saved_path.open("wb") as f:
        shutil.copyfileobj(upload.file, f)
    upload_bytes = saved_path.stat().st_size
    log.info(
        "ingest.upload_received",
        extra={
            "upload_filename": upload.filename or saved_path.name,
            "size_bytes": upload_bytes,
            "size_mb": round(upload_bytes / (1024 * 1024), 2),
            "requested_source": source,
            "label": label,
        },
    )

    inputs = _expand_inputs(saved_path, scratch_dir)
    if not inputs:
        raise ValueError("Archive contained no JSON or Markdown files.")
    if saved_path.suffix.lower() == ".zip":
        log.info("ingest.archive_expanded", extra={"file_count": len(inputs)})

    # Resolve ingestor (one per upload; auto-detect across inputs if needed)
    ingestor: BaseIngestor | None = None
    if source != "auto":
        ingestor = _INGESTORS.get(source)
        if ingestor is None:
            raise ValueError(f"Unknown source: {source}")
    else:
        for path in inputs:
            ingestor = _detect(path)
            if ingestor:
                break
    if ingestor is None:
        raise ValueError(
            "Could not auto-detect source. Specify `source` explicitly "
            "(chatgpt | claude | grok | gemini | perplexity | local)."
        )
    log.info(
        "ingest.source_resolved",
        extra={"source_slug": ingestor.source_slug, "auto_detected": source == "auto"},
    )

    src = await _get_or_create_source(db, ingestor.source_slug, ingestor.display_name)
    job = IngestionJob(
        source_id=src.id,
        filename=upload.filename or saved_path.name,
        status="running",
        raw_metadata={"label": label} if label else None,
    )
    db.add(job)
    await db.flush()
    log.info("ingest.job_started", extra={"job_id": job.id, "source": src.slug})

    convs_imported = 0
    msgs_imported = 0
    skipped_existing = 0
    file_failures = 0
    try:
        for path in inputs:
            try:
                if source == "auto":
                    candidate = _detect(path)
                    if candidate is None:
                        continue
                    chosen = candidate
                else:
                    chosen = ingestor
                for nconv in chosen.parse(path):
                    persisted = await _persist_conversation(db, src.id, nconv)
                    if persisted:
                        convs_imported += 1
                        msgs_imported += len(nconv.messages)
                        if convs_imported % 25 == 0:
                            log.info(
                                "ingest.progress",
                                extra={
                                    "job_id": job.id,
                                    "conversations": convs_imported,
                                    "messages": msgs_imported,
                                },
                            )
                    else:
                        skipped_existing += 1
            except Exception as exc:  # noqa: BLE001
                file_failures += 1
                log.warning(
                    "ingest.file_failed",
                    extra={"path": str(path), "error": str(exc), "job_id": job.id},
                )

        job.status = "completed"
        job.conversations_imported = convs_imported
        job.messages_imported = msgs_imported
        job.finished_at = datetime.utcnow()
        log.info(
            "ingest.job_completed",
            extra={
                "job_id": job.id,
                "source": src.slug,
                "conversations_imported": convs_imported,
                "messages_imported": msgs_imported,
                "skipped_existing": skipped_existing,
                "file_failures": file_failures,
                "duration_seconds": (job.finished_at - started).total_seconds(),
            },
        )
    except Exception as exc:  # noqa: BLE001
        job.status = "failed"
        job.error = str(exc)
        job.finished_at = datetime.utcnow()
        log.error(
            "ingest.job_failed",
            extra={"job_id": job.id, "source": src.slug, "error": str(exc)},
        )
        raise
    finally:
        shutil.rmtree(scratch_dir, ignore_errors=True)
        await db.flush()

    return IngestResponse(
        job_id=job.id,
        source=src.slug,
        filename=job.filename,
        status=job.status,
        conversations_imported=job.conversations_imported,
        messages_imported=job.messages_imported,
        started_at=job.started_at,
        finished_at=job.finished_at,
        error=job.error,
    )


_CHROMA_DOC_MAX = 3000  # characters — keeps Chroma fast


async def _persist_conversation(
    db: AsyncSession, source_id: int, nconv: NormalisedConversation
) -> bool:
    if not nconv.messages:
        return False

    if nconv.external_id:
        existing = await db.execute(
            select(Conversation).where(
                Conversation.source_id == source_id,
                Conversation.external_id == nconv.external_id,
            )
        )
        if existing.scalar_one_or_none() is not None:
            return False

    conv = Conversation(
        source_id=source_id,
        external_id=nconv.external_id,
        title=nconv.title,
        started_at=nconv.started_at,
        ended_at=nconv.ended_at,
        message_count=len(nconv.messages),
        raw_metadata=nconv.raw_metadata,
    )
    db.add(conv)
    await db.flush()

    persisted_messages: list[Message] = [
        Message(
            conversation_id=conv.id,
            sequence=m.sequence,
            role=m.role,
            content=m.content,
            message_at=m.message_at,
            raw_metadata=m.raw_metadata,
        )
        for m in nconv.messages
    ]
    db.add_all(persisted_messages)
    await db.flush()  # ensures .id is populated on every Message

    # --- Push messages into ChromaDB for semantic retrieval ---
    try:
        from app.services.embeddings import upsert_messages  # lazy import

        # Resolve source slug for metadata
        from app.models.conversation import Source as _Source
        src_result = await db.execute(
            select(_Source).where(_Source.id == source_id)
        )
        src = src_result.scalar_one_or_none()
        source_slug = src.slug if src else str(source_id)

        ids: list[str] = []
        documents: list[str] = []
        metadatas: list[dict] = []

        for msg in persisted_messages:
            ids.append(f"msg-{msg.id}")
            documents.append(msg.content[:_CHROMA_DOC_MAX])
            meta: dict = {
                "message_id": msg.id,
                "conversation_id": conv.id,
                "source_slug": source_slug,
                "role": msg.role,
                "sequence": msg.sequence,
            }
            if msg.message_at is not None:
                meta["message_at_iso"] = msg.message_at.isoformat()
            metadatas.append(meta)

        upsert_messages(ids=ids, documents=documents, metadatas=metadatas)
        log.debug(
            "ingest.chroma_upserted",
            extra={"conversation_id": conv.id, "messages": len(ids)},
        )
    except Exception as exc:  # noqa: BLE001
        log.warning(
            "ingest.chroma_upsert_failed",
            extra={"conversation_id": conv.id, "error": str(exc)},
        )

    return True
