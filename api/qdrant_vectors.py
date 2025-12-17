import hashlib
import os
import re
from typing import Any, Dict, List, Optional

from qdrant_client import QdrantClient
from qdrant_client.http import models as rest


def sanitize_suffix(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]", "_", name)


def get_client() -> QdrantClient:
    return QdrantClient(
        host=os.getenv("QDRANT_HOST", "localhost"),
        port=int(os.getenv("QDRANT_PORT", "6333")),
        timeout=3.0,
    )


def get_collection_name() -> str:
    # Можно принудительно указать коллекцию в .env (например, выданную преподавателем)
    override = os.getenv("QDRANT_COLLECTION")
    if override:
        return override

    base = "notes_vectors"
    student = os.getenv("STUDENT_NAME", "").strip()
    return f"{base}_{sanitize_suffix(student.lower())}" if student else base


def _get_existing_vector_size(client: QdrantClient, col: str) -> Optional[int]:
    try:
        info = client.get_collection(col)
        return info.config.params.vectors.size
    except Exception:
        return None


def get_vector_size(client: Optional[QdrantClient] = None) -> int:
    # Приоритет: QDRANT_VECTOR_SIZE из .env -> размер существующей коллекции -> дефолт 128
    env_size = os.getenv("QDRANT_VECTOR_SIZE")
    if env_size:
        try:
            return int(env_size)
        except ValueError:
            pass

    if client is None:
        client = get_client()
    col = get_collection_name()
    size = _get_existing_vector_size(client, col)
    if size:
        return size

    return 128


def ensure_collection() -> None:
    client = get_client()
    col = get_collection_name()
    existing = client.get_collections()
    names = [c.name for c in existing.collections]
    if col in names:
        return
    # Если указана коллекция явно и её нет — не создаём новую, а сигнализируем ошибку
    if os.getenv("QDRANT_COLLECTION"):
        raise ValueError(f"Qdrant collection '{col}' not found. Please create it or fix QDRANT_COLLECTION.")

    size = get_vector_size(client)
    client.create_collection(
        collection_name=col,
        vectors_config=rest.VectorParams(size=size, distance=rest.Distance.COSINE),
    )


def embed_text(text: str, size: int) -> List[float]:
    """
    Простая детерминированная "хэш-эмбеддинг":
    - Разбиваем текст на токены, приводим к нижнему регистру.
    - Для каждого токена считаем md5, индекс = hash % size, знак = по биту хеша.
    - Получаем "мешок слов" фиксированной длины.
    - Нормализуем вектор до длины 1 (если все нули, оставляем).
    """
    tokens = re.findall(r"[a-zA-Z0-9а-яА-ЯёЁ]+", text.lower())
    vec = [0.0] * size
    for tok in tokens:
        h = hashlib.md5(tok.encode("utf-8")).digest()
        idx = int.from_bytes(h[:4], "big") % size
        sign = 1 if h[4] % 2 == 0 else -1
        vec[idx] += sign * 1.0
    # L2 нормализация
    norm = sum(x * x for x in vec) ** 0.5
    if norm > 0:
        vec = [x / norm for x in vec]
    return vec


def embed_note(note: Dict[str, Any]) -> List[float]:
    parts = [
        note.get("title", ""),
        note.get("content", ""),
        " ".join(note.get("tags", []) or []),
    ]
    text = "\n".join(parts)
    client = get_client()
    size = get_vector_size(client)
    return embed_text(text, size)


def upsert_note_vector(note: Dict[str, Any]) -> None:
    ensure_collection()
    client = get_client()
    col = get_collection_name()
    vec = embed_note(note)
    payload = {
        "note_id": note["id"],
        "title": note.get("title"),
        "tags": note.get("tags", []),
    }
    client.upsert(
        collection_name=col,
        points=[
            rest.PointStruct(
                id=note["id"],
                vector=vec,
                payload=payload,
            )
        ],
    )


def search_similar(note: Dict[str, Any], limit: int = 5) -> List[Dict[str, Any]]:
    ensure_collection()
    client = get_client()
    col = get_collection_name()
    vec = embed_note(note)
    res = client.search(collection_name=col, query_vector=vec, limit=limit)
    results: List[Dict[str, Any]] = []
    for r in res:
        # note_id: берем из payload, если нет — из id точки
        note_id = None
        if r.payload and "note_id" in r.payload:
            note_id = r.payload.get("note_id")
        if note_id is None and r.id is not None:
            note_id = r.id
        # если вообще нет id, пропускаем такую точку
        if note_id is None:
            continue
        results.append(
            {
                "score": r.score,
                "note_id": note_id,
                "title": r.payload.get("title") if r.payload else None,
                "tags": r.payload.get("tags") if r.payload else None,
            }
        )
    return results


def delete_note_vector(note_id: int) -> None:
    client = get_client()
    col = get_collection_name()
    try:
        client.delete(collection_name=col, points_selector=[note_id])
    except Exception:
        # Если коллекции нет или точка не найдена — просто игнорируем
        pass
