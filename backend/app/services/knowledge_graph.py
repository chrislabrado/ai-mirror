"""Knowledge graph abstraction.

Primary backend: Neo4j over Bolt. Fallback: SQLite triples via the
``entities`` / ``relationships`` tables. The fallback is automatic when
Neo4j cannot be reached, so local dev remains friction-free.
"""
from __future__ import annotations

from typing import Any

from app.config import settings
from app.utils.logger import get_logger

log = get_logger(__name__)

_driver = None  # lazy global


def _get_driver():
    global _driver
    if _driver is not None:
        return _driver
    try:
        from neo4j import GraphDatabase

        _driver = GraphDatabase.driver(
            settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password)
        )
        # Cheap connectivity probe.
        with _driver.session() as s:
            s.run("RETURN 1").consume()
        log.info("kg.neo4j.connected", extra={"uri": settings.neo4j_uri})
    except Exception as exc:  # noqa: BLE001
        log.warning("kg.neo4j.unavailable", extra={"error": str(exc)})
        _driver = None
    return _driver


def neo4j_available() -> bool:
    return _get_driver() is not None


def upsert_triple(subject: str, predicate: str, obj: str, **props: Any) -> None:
    """Idempotent MERGE of (subject) -[predicate]-> (obj).

    Falls through silently when Neo4j is unavailable; SQLite mirroring
    happens via the ORM-side service.
    """
    driver = _get_driver()
    if driver is None:
        return
    cypher = (
        "MERGE (s:Entity {label: $subject}) "
        "MERGE (o:Entity {label: $obj}) "
        "MERGE (s)-[r:REL {predicate: $predicate}]->(o) "
        "SET r += $props"
    )
    with driver.session() as session:
        session.run(cypher, subject=subject, predicate=predicate, obj=obj, props=props)


def query_neighbours(label: str, depth: int = 1, limit: int = 50) -> list[dict[str, Any]]:
    driver = _get_driver()
    if driver is None:
        return []
    cypher = (
        f"MATCH (s:Entity {{label: $label}})-[r:REL*1..{depth}]-(o:Entity) "
        "RETURN s.label AS subject, [rel IN r | rel.predicate] AS path, "
        "o.label AS object LIMIT $limit"
    )
    with driver.session() as session:
        result = session.run(cypher, label=label, limit=limit)
        return [dict(record) for record in result]
