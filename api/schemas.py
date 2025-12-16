from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class NoteCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., min_length=1)
    tags: Optional[List[str]] = None


class NoteUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    content: Optional[str] = Field(None, min_length=1)
    tags: Optional[List[str]] = None


class NoteRestore(BaseModel):
    version: int = Field(..., ge=1)


class NoteOut(BaseModel):
    id: int
    title: str
    content: str
    tags: List[str]
    created_at: datetime
    updated_at: datetime
