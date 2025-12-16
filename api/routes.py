from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from . import db
from .mongo_versions import get_version, get_versions, save_version
from .schemas import NoteCreate, NoteOut, NoteRestore, NoteUpdate

router = APIRouter()


@router.post("/notes", response_model=NoteOut)
def create_note(payload: NoteCreate):
    try:
        note = db.insert_note(payload.title, payload.content, payload.tags)
        save_version(note)
        return note
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to create note: {exc}")


@router.get("/notes/{note_id}", response_model=NoteOut)
def get_note(note_id: int):
    try:
        note = db.fetch_note(note_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch note: {exc}")
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
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
    return restored
