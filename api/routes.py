from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from . import cache, db, qdrant_vectors
from .mongo_versions import get_version, get_versions, save_version
from .schemas import NoteCreate, NoteOut, NoteRestore, NoteUpdate

router = APIRouter()


@router.post("/notes", response_model=NoteOut)
def create_note(payload: NoteCreate):
    try:
        note = db.insert_note(payload.title, payload.content, payload.tags)
        save_version(note)
        try:
            cache.cache_note(note)
        except Exception:
            pass  # кэш не критичен
        qdrant_vectors.upsert_note_vector(note)  # если Qdrant недоступен — увидим ошибку в логах
        return note
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to create note: {exc}")


@router.get("/notes/popular")
def popular_notes(limit: int = 10):
    try:
        top = cache.get_top_popular(limit)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read popularity: {exc}")

    result = []
    for note_id, score in top:
        # берём из кэша или базы
        note = cache.get_cached_note(note_id)
        if not note:
            note = db.fetch_note(note_id)
        if note:
            result.append({"note": note, "score": score})
        else:
            result.append({"note_id": note_id, "score": score, "error": "not found"})
    return result


@router.get("/notes/{note_id}", response_model=NoteOut)
def get_note(note_id: int):
    # сначала пробуем кэш
    cached = cache.get_cached_note(note_id)
    if cached:
        try:
            cache.bump_popularity(note_id)
        except Exception:
            pass
        return cached

    try:
        note = db.fetch_note(note_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch note: {exc}")
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    try:
        cache.cache_note(note)
        cache.bump_popularity(note_id)
    except Exception:
        pass
    return note


@router.put("/notes/{note_id}", response_model=NoteOut)
def update_note(note_id: int, payload: NoteUpdate):
    try:
        note = db.update_note(note_id, payload.title, payload.content, payload.tags)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to update note: {exc}")
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    try:
        save_version(note)
    except Exception as exc:
        # не ломаем основной ответ, просто логируем деталь в detail
        raise HTTPException(status_code=500, detail=f"Note updated, but failed to save version: {exc}")
    try:
        cache.cache_note(note)
    except Exception:
        pass
    qdrant_vectors.upsert_note_vector(note)
    return note


@router.get("/notes", response_model=List[NoteOut])
def list_notes(q: Optional[str] = Query(None, description="Search query"), limit: int = 20, offset: int = 0):
    try:
        notes = db.search_notes(q, limit=limit, offset=offset)
        return notes
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to list notes: {exc}")




@router.get("/notes/{note_id}/versions")
def list_versions(note_id: int, limit: int = 20):
    try:
        versions = get_versions(note_id, limit=limit)
        return versions
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch versions: {exc}")


@router.post("/notes/{note_id}/restore", response_model=NoteOut)
def restore_note(note_id: int, payload: NoteRestore):
    try:
        version_doc = get_version(note_id, payload.version)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read version: {exc}")
    if not version_doc:
        raise HTTPException(status_code=404, detail="Version not found")

    try:
        restored = db.update_note(
            note_id,
            version_doc.get("title"),
            version_doc.get("content"),
            version_doc.get("tags"),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to restore note: {exc}")
    if not restored:
        raise HTTPException(status_code=404, detail="Note not found")

    try:
        save_version(restored)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Note restored, but failed to save new version: {exc}"
        )
    try:
        cache.cache_note(restored)
    except Exception:
        pass
    qdrant_vectors.upsert_note_vector(restored)
    return restored


@router.get("/notes/{note_id}/similar")
def similar_notes(note_id: int, limit: int = 5):
    try:
        note = db.fetch_note(note_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch note: {exc}")
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    try:
        raw = qdrant_vectors.search_similar(note, limit=limit + 1)  # +1, чтобы можно было потом отфильтровать саму заметку
        filtered = []
        for r in raw:
            rid = r.get("note_id")
            if rid is None:
                continue
            # пропускаем саму заметку, если она попала в выдачу
            if rid == note_id:
                continue
            # пробуем подтянуть детали заметки
            details = db.fetch_note(int(rid))
            if not details:
                continue
            filtered.append({"score": r.get("score"), "note": details})
            if len(filtered) == limit:
                break
        return filtered
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to search similar: {exc}")
