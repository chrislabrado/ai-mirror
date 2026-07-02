"""Remote input extraction — ingest conversation files straight from disk.

Instead of uploading an archive, the ``/ingest/remote`` endpoint points the
pipeline at a local root (Claude Code projects, OpenClaw agent sessions, or
an arbitrary allowed path) and ingests matching files in place.

SECURITY: the resolved root MUST live inside one of
``settings.ingest_allowed_root_paths`` — this API must never become an
arbitrary-disk-read primitive.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.ingestion_job import IngestionJob
from app.schemas.ingest import IngestResponse
from app.services.ingestion.base import BaseIngestor
from app.services.ingestion.pipeline import (
    _INGESTORS,
    _detect,
    _get_or_create_source,
    _persist_conversation,
)
from app.utils.logger import get_logger

log = get_logger(__name__)

_PATH_SUFFIXES = frozenset({".json", ".jsonl", ".md", ".markdown", ".html", ".htm"})

# connector → (default root, glob pattern, forced ingestor slug or None for auto)
_CONNECTORS: dict[str, tuple[str, str, str | None]] = {
    "claude_code": ("~/.claude/projects", "**/*.jsonl", "claude_code"),
    "openclaw": ("~/.openclaw/agents", "**/sessions/*.jsonl", "openclaw"),
    "path": ("", "**/*", None),
}


def _validate_root(candidate: str) -> Path:
    """Resolve a root and reject anything outside the allowed roots."""
    root = Path(candidate).expanduser().resolve()
    allowed = settings.ingest_allowed_root_paths
    if not any(root == a or root.is_relative_to(a) for a in allowed):
        raise ValueError(
            f"Root {root} is not inside an allowed ingest root. "
            f"Allowed: {', '.join(str(a) for a in allowed)}"
        )
    if not root.is_dir():
        raise ValueError(f"Root {root} does not exist or is not a directory.")
    return root


def _collect_files(
    root: Path, pattern: str, connector: str, since: datetime | None, limit: int | None
) -> list[Path]:
    files = [
        p
        for p in root.glob(pattern)
        if p.is_file()
        and (connector != "path" or p.suffix.lower() in _PATH_SUFFIXES)
    ]
    if since is not None:
        since_utc = since if since.tzinfo else since.replace(tzinfo=timezone.utc)
        files = [
            p
            for p in files
            if datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc) >= since_utc
        ]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    if limit is not None and limit >= 0:
        files = files[:limit]
    return files


async def run_remote_ingestion(
    *,
    db: AsyncSession,
    connector: str,
    path: str | None,
    since: datetime | None,
    limit: int | None,
    label: str | None,
) -> IngestResponse:
    started = datetime.utcnow()
    if connector not in _CONNECTORS:
        raise ValueError(f"Unknown connector: {connector}")
    default_root, pattern, forced_slug = _CONNECTORS[connector]

    if connector == "path" and not path:
        raise ValueError("Connector 'path' requires an explicit `path`.")
    root = _validate_root(path or default_root)

    files = _collect_files(root, pattern, connector, since, limit)
    log.info(
        "ingest.remote_scan",
        extra={
            "connector": connector,
            "root": str(root),
            "files_matched": len(files),
            "since": since.isoformat() if since else None,
            "limit": limit,
        },
    )
    if not files:
        raise ValueError(f"No matching files found under {root}.")

    # Resolve the ingestor: forced for known connectors, auto-detect for `path`.
    ingestor: BaseIngestor | None = None
    if forced_slug is not None:
        ingestor = _INGESTORS[forced_slug]
    else:
        for candidate in files:
            ingestor = _detect(candidate)
            if ingestor:
                break
    if ingestor is None:
        raise ValueError(f"Could not auto-detect a source for any file under {root}.")

    src = await _get_or_create_source(db, ingestor.source_slug, ingestor.display_name)
    job = IngestionJob(
        source_id=src.id,
        filename=f"remote:{connector}",
        status="running",
        raw_metadata={
            "root": str(root),
            "files_scanned": len(files),
            "files_failed": 0,
            "label": label,
        },
    )
    db.add(job)
    await db.flush()
    log.info(
        "ingest.remote_job_started",
        extra={"job_id": job.id, "connector": connector, "source": src.slug},
    )

    convs_imported = 0
    msgs_imported = 0
    skipped_existing = 0
    file_failures = 0
    try:
        for file in files:
            try:
                if forced_slug is not None:
                    chosen = ingestor
                else:
                    candidate = _detect(file)
                    if candidate is None:
                        continue
                    chosen = candidate
                for nconv in chosen.parse(file):
                    persisted = await _persist_conversation(db, src.id, nconv)
                    if persisted:
                        convs_imported += 1
                        msgs_imported += len(nconv.messages)
                        if convs_imported % 25 == 0:
                            log.info(
                                "ingest.remote_progress",
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
                    "ingest.remote_file_failed",
                    extra={"path": str(file), "error": str(exc), "job_id": job.id},
                )

        job.status = "completed"
        job.conversations_imported = convs_imported
        job.messages_imported = msgs_imported
        job.finished_at = datetime.utcnow()
        job.raw_metadata = {
            "root": str(root),
            "files_scanned": len(files),
            "files_failed": file_failures,
            "label": label,
        }
        log.info(
            "ingest.remote_job_completed",
            extra={
                "job_id": job.id,
                "connector": connector,
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
            "ingest.remote_job_failed",
            extra={"job_id": job.id, "connector": connector, "error": str(exc)},
        )
        raise
    finally:
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
