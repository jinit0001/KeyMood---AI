from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.v1.auth.dependencies import get_current_user
from app.domain.auth.entities import User
from app.infrastructure.db.journal_infra import SqlJournalRepository
from app.infrastructure.db.session import get_db
from app.services.journal import JournalService

router = APIRouter(prefix="/journal", tags=["journal"])


class EntryOut(BaseModel):
    id: str
    content: str
    ai_summary: str | None
    linked_emotion_prediction_id: str | None
    tags: list[str]
    created_at: datetime
    updated_at: datetime


class CreateIn(BaseModel):
    content: str = Field(min_length=1, max_length=10_000)
    tags: list[str] = Field(default_factory=list)
    linked_emotion_prediction_id: str | None = None


class UpdateIn(BaseModel):
    content: str | None = Field(default=None, min_length=1, max_length=10_000)
    tags: list[str] | None = None


def get_service(db: Session = Depends(get_db)) -> JournalService:
    return JournalService(SqlJournalRepository(db))


def _out(e) -> EntryOut:
    return EntryOut(id=str(e.id), content=e.content, ai_summary=e.ai_summary,
                     linked_emotion_prediction_id=str(e.linked_emotion_prediction_id) if e.linked_emotion_prediction_id else None,
                     tags=e.tags, created_at=e.created_at, updated_at=e.updated_at)


@router.get("/entries", response_model=list[EntryOut])
def list_entries(limit: int = Query(default=20, ge=1, le=100), offset: int = Query(default=0, ge=0),
                  user: User = Depends(get_current_user), svc: JournalService = Depends(get_service)):
    return [_out(e) for e in svc.list_entries(user.id, limit, offset)]


@router.post("/entries", response_model=EntryOut, status_code=status.HTTP_201_CREATED)
def create_entry(payload: CreateIn, user: User = Depends(get_current_user), svc: JournalService = Depends(get_service)):
    entry = svc.create(user.id, payload.content, payload.tags,
                        UUID(payload.linked_emotion_prediction_id) if payload.linked_emotion_prediction_id else None)
    return _out(entry)


@router.get("/search", response_model=list[EntryOut])
def search_entries(q: str | None = None, tag: str | None = None, limit: int = Query(default=20, ge=1, le=100),
                    offset: int = Query(default=0, ge=0), user: User = Depends(get_current_user),
                    svc: JournalService = Depends(get_service)):
    return [_out(e) for e in svc.search(user.id, q, tag, limit, offset)]


@router.get("/entries/{entry_id}", response_model=EntryOut)
def get_entry(entry_id: UUID, user: User = Depends(get_current_user), svc: JournalService = Depends(get_service)):
    return _out(svc.get(user.id, entry_id))


@router.patch("/entries/{entry_id}", response_model=EntryOut)
def update_entry(entry_id: UUID, payload: UpdateIn, user: User = Depends(get_current_user), svc: JournalService = Depends(get_service)):
    return _out(svc.update(user.id, entry_id, payload.content, payload.tags))


@router.delete("/entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entry(entry_id: UUID, user: User = Depends(get_current_user), svc: JournalService = Depends(get_service)):
    svc.delete(user.id, entry_id)


@router.post("/entries/{entry_id}/summary", response_model=EntryOut, status_code=status.HTTP_202_ACCEPTED)
def request_summary(entry_id: UUID, user: User = Depends(get_current_user), svc: JournalService = Depends(get_service)):
    return _out(svc.request_summary(user.id, entry_id))
