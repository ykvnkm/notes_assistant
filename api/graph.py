import os
from functools import lru_cache
from typing import List

from neo4j import GraphDatabase


@lru_cache(maxsize=1)
def get_driver():
    uri = f"bolt://{os.getenv('NEO4J_HOST', 'localhost')}:{os.getenv('NEO4J_PORT', '7687')}"
    auth = (
        os.getenv("NEO4J_USER", "neo4j"),
        os.getenv("NEO4J_PASSWORD", "secret123"),
    )
    return GraphDatabase.driver(uri, auth=auth)


@lru_cache(maxsize=1)
def ensure_constraints() -> None:
    drv = get_driver()
    with drv.session() as session:
        session.run(
            "CREATE CONSTRAINT note_id_unique IF NOT EXISTS FOR (n:Note) REQUIRE n.note_id IS UNIQUE"
        ).consume()
        session.run(
            "CREATE CONSTRAINT tag_name_unique IF NOT EXISTS FOR (t:Tag) REQUIRE t.name IS UNIQUE"
        ).consume()


def upsert_note_with_tags(note: dict) -> None:
    """
    Создаёт/обновляет узел Note и связи с Tag для списка tags.
    Note хранит note_id, title, tags (для удобства) — основное хранилище остаётся в Postgres.
    """
    ensure_constraints()
    drv = get_driver()
    tags = note.get("tags") or []
    with drv.session() as session:
        session.run(
            """
            MERGE (n:Note {note_id: $id})
            SET n.title = $title,
                n.tags = $tags
            WITH n
            UNWIND $tags AS tag
                MERGE (t:Tag {name: tag})
                MERGE (n)-[:TAGGED_WITH]->(t)
            """,
            id=note["id"],
            title=note.get("title", ""),
            tags=tags,
        )


def delete_note(note_id: int) -> None:
    ensure_constraints()
    drv = get_driver()
    with drv.session() as session:
        session.run(
            """
            MATCH (n:Note {note_id: $id})
            DETACH DELETE n
            """,
            id=note_id,
        )


def get_notes_by_tag(tag: str, limit: int = 20) -> List[int]:
    ensure_constraints()
    drv = get_driver()
    with drv.session() as session:
        res = session.run(
            """
            MATCH (t:Tag {name: $tag})<-[:TAGGED_WITH]-(n:Note)
            RETURN n.note_id AS note_id
            LIMIT $limit
            """,
            tag=tag,
            limit=limit,
        )
        return [r["note_id"] for r in res]


def list_tags(limit: int = 100) -> List[str]:
    ensure_constraints()
    drv = get_driver()
    with drv.session() as session:
        res = session.run(
            """
            MATCH (t:Tag)
            RETURN t.name AS name
            ORDER BY name
            LIMIT $limit
            """,
            limit=limit,
        )
        return [r["name"] for r in res]
