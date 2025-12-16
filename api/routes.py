from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from . import db
from .schemas import NoteCreate, NoteOut

router = APIRouter()


@router.post("/notes", response_model=NoteOut)
def create_note(payload: NoteCreate):
    try:
        note = db.insert_note(payload.title, payload.content, payload.tags)
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


@router.get("/notes", response_model=List[NoteOut])
def list_notes(q: Optional[str] = Query(None, description="Search query"), limit: int = 20, offset: int = 0):
    try:
        notes = db.search_notes(q, limit=limit, offset=offset)
        return notes
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to list notes: {exc}")
