import json
import os
from typing import Any, Dict, List, Optional, Tuple

import redis


def get_client() -> redis.Redis:
    return redis.Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        db=int(os.getenv("REDIS_DB", "0")),
        decode_responses=True,  # работаем со строками
        socket_connect_timeout=3,
        socket_timeout=3,
    )


NOTE_TTL = int(os.getenv("REDIS_NOTE_TTL", "120"))  # секунд
POPULAR_KEY = os.getenv("REDIS_POPULAR_KEY", "popular_notes")


def cache_note(note: Dict[str, Any]) -> None:
    """Сохранить заметку в кэш (JSON) с TTL."""
    client = get_client()
    key = f"note:{note['id']}"
    client.setex(key, NOTE_TTL, json.dumps(note, default=str))


def get_cached_note(note_id: int) -> Optional[Dict[str, Any]]:
    client = get_client()
    raw = client.get(f"note:{note_id}")
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


def bump_popularity(note_id: int, inc: float = 1.0) -> None:
    """Увеличить счётчик популярности (sorted set)."""
    client = get_client()
    client.zincrby(POPULAR_KEY, inc, note_id)


def get_top_popular(limit: int = 10) -> List[Tuple[int, float]]:
    """Вернуть список (note_id, score) по убыванию."""
    client = get_client()
    items = client.zrevrange(POPULAR_KEY, 0, limit - 1, withscores=True)
    return [(int(note_id), score) for note_id, score in items]
