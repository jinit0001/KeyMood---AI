from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.auth.dependencies import get_current_user, get_current_user_ws
from app.core.security import jwt as jwt_utils
from app.domain.auth.entities import User
from app.infrastructure.db.models.user_profile import UserProfileModel
from app.infrastructure.db.session import get_db
from app.infrastructure.db.social_infra import SqlFriendRequestRepository, SqlFriendshipRepository
from app.services.social import SocialService

router = APIRouter(prefix="/social", tags=["social"])

# In-memory presence registry, one process only — a real deployment
# with multiple server instances would need this in Redis pub/sub
# instead. Documented limitation, not silently pretended to scale.
_online: dict[UUID, set[WebSocket]] = {}


class RequestIn(BaseModel):
    receiver_id: str


class RequestOut(BaseModel):
    id: str
    sender_id: str
    receiver_id: str
    status: str
    created_at: datetime
    responded_at: datetime | None


class FriendshipOut(BaseModel):
    id: str
    user_id_a: str
    user_id_b: str
    created_at: datetime


def get_service(db: Session = Depends(get_db)) -> SocialService:
    return SocialService(SqlFriendshipRepository(db), SqlFriendRequestRepository(db))


def _req_out(r) -> RequestOut:
    return RequestOut(id=str(r.id), sender_id=str(r.sender_id), receiver_id=str(r.receiver_id),
                       status=r.status, created_at=r.created_at, responded_at=r.responded_at)


@router.get("/friends", response_model=list[str])
def list_friends(limit: int = Query(default=20, ge=1, le=100), offset: int = Query(default=0, ge=0),
                  user: User = Depends(get_current_user), svc: SocialService = Depends(get_service)):
    return [str(fid) for fid in svc.list_friends(user.id, limit, offset)]


@router.get("/names", response_model=dict[str, str])
def display_names(ids: list[UUID] = Query(default=[], max_length=100), user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    """Resolve user ids -> display names (friends list, request senders, etc.).
    Authenticated only; returns display_name and nothing else."""
    if not ids:
        return {}
    rows = db.execute(select(UserProfileModel.user_id, UserProfileModel.display_name)
                      .where(UserProfileModel.user_id.in_(ids))).all()
    return {str(uid): name for uid, name in rows}


@router.delete("/friends/{friend_id}", status_code=204)
def remove_friend(friend_id: UUID, user: User = Depends(get_current_user), svc: SocialService = Depends(get_service)):
    svc.remove_friend(user.id, friend_id)


@router.post("/requests", response_model=RequestOut, status_code=201)
def send_request(payload: RequestIn, user: User = Depends(get_current_user), svc: SocialService = Depends(get_service)):
    return _req_out(svc.send_request(user.id, UUID(payload.receiver_id)))


@router.get("/requests", response_model=list[RequestOut])
def list_requests(status: str | None = None, user: User = Depends(get_current_user), svc: SocialService = Depends(get_service)):
    return [_req_out(r) for r in svc.list_requests(user.id, status)]


@router.post("/requests/{request_id}/accept", response_model=FriendshipOut)
def accept_request(request_id: UUID, user: User = Depends(get_current_user), svc: SocialService = Depends(get_service)):
    f = svc.accept(user.id, request_id)
    return FriendshipOut(id=str(f.id), user_id_a=str(f.user_id_a), user_id_b=str(f.user_id_b), created_at=f.created_at)


@router.post("/requests/{request_id}/decline", response_model=RequestOut)
def decline_request(request_id: UUID, user: User = Depends(get_current_user), svc: SocialService = Depends(get_service)):
    return _req_out(svc.decline(user.id, request_id))


@router.websocket("/presence")
async def presence(websocket: WebSocket, db: Session = Depends(get_db)):
    try:
        user = await get_current_user_ws(websocket, db)
    except (jwt_utils.InvalidTokenError, jwt_utils.TokenExpiredError):
        await websocket.close(code=4401)
        return

    await websocket.accept()
    svc = get_service(db)
    friend_ids = svc.list_friends(user.id)

    _online.setdefault(user.id, set()).add(websocket)
    await websocket.send_json({"online_friends": [str(f) for f in friend_ids if f in _online]})
    for fid in friend_ids:
        for conn in _online.get(fid, set()):
            await conn.send_json({"event": "friend_online", "user_id": str(user.id)})

    try:
        while True:
            await websocket.receive_text()  # presence has no client->server messages; just keeps the connection open
    except WebSocketDisconnect:
        _online[user.id].discard(websocket)
        if not _online[user.id]:
            del _online[user.id]
            for fid in friend_ids:
                for conn in _online.get(fid, set()):
                    await conn.send_json({"event": "friend_offline", "user_id": str(user.id)})
