from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.v1.auth.dependencies import get_current_user, get_current_user_ws
from app.core.exceptions import AppError
from app.infrastructure.db.session import get_db
from app.core.security import jwt as jwt_utils
from app.infrastructure.db.messaging_infra import (
    SqlConversationMemberRepository, SqlConversationQuery, SqlConversationRepository,
    SqlMessageReadRepository, SqlMessageRepository,
)
from app.infrastructure.db.social_infra import SqlFriendshipRepository
from app.services.messaging import MessagingService

router = APIRouter(prefix="/messaging", tags=["messaging"])

# In-memory, single-process WS registry. Documented limitation: a real
# multi-instance deployment needs Redis pub/sub for cross-instance delivery.
_connections: dict[UUID, set[WebSocket]] = {}


class _FriendshipAdapter:
    """Module 8's repository exposes exists(); the messaging service asks are_friends()."""

    def __init__(self, db: Session) -> None:
        self._repo = SqlFriendshipRepository(db)

    def are_friends(self, user_a: UUID, user_b: UUID) -> bool:
        return self._repo.exists(user_a, user_b)


def _service(db: Session) -> MessagingService:
    return MessagingService(
        SqlConversationRepository(db),
        SqlConversationMemberRepository(db),
        SqlMessageRepository(db),
        SqlMessageReadRepository(db),
        _FriendshipAdapter(db),
    )


class CreateConversationIn(BaseModel):
    type: str
    member_ids: list[UUID]
    title: str | None = None


class ConversationOut(BaseModel):
    id: UUID
    type: str
    title: str | None
    created_by: UUID
    created_at: datetime


class MemberOut(BaseModel):
    user_id: UUID
    display_name: str


class LastMessageOut(BaseModel):
    content: str
    sender_id: UUID
    created_at: datetime


class ConversationSummaryOut(BaseModel):
    id: UUID
    type: str
    title: str | None
    created_at: datetime
    members: list[MemberOut]
    last_message: LastMessageOut | None


class MessageIn(BaseModel):
    content: str = ""
    media_id: UUID | None = None


class MessageOut(BaseModel):
    id: UUID
    conversation_id: UUID
    sender_id: UUID
    content: str
    media_id: UUID | None
    created_at: datetime


class MessagesPageOut(BaseModel):
    messages: list[MessageOut]
    has_more: bool


@router.post("/conversations", response_model=ConversationOut, status_code=201)
def create_conversation(body: CreateConversationIn, user=Depends(get_current_user), db: Session = Depends(get_db)):
    svc = _service(db)
    conv = svc.create_conversation(user.id, body.type, body.member_ids, body.title)
    return ConversationOut(**conv.__dict__)


@router.get("/conversations", response_model=list[ConversationSummaryOut])
def list_conversations(user=Depends(get_current_user), db: Session = Depends(get_db)):
    return SqlConversationQuery(db).list_for_user(user.id)


@router.get("/conversations/{conversation_id}/messages", response_model=MessagesPageOut)
def list_messages(
    conversation_id: UUID,
    before: UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc = _service(db)
    msgs, has_more = svc.list_messages(user.id, conversation_id, before, limit)
    return MessagesPageOut(messages=[MessageOut(**m.__dict__) for m in msgs], has_more=has_more)


@router.post("/conversations/{conversation_id}/messages", response_model=MessageOut, status_code=201)
def send_message(
    conversation_id: UUID, body: MessageIn, user=Depends(get_current_user), db: Session = Depends(get_db)
):
    svc = _service(db)
    msg = svc.send_message(user.id, conversation_id, body.content, body.media_id)
    db.commit()
    return MessageOut(**msg.__dict__)


async def _broadcast(user_ids: list[UUID], event: dict) -> None:
    for uid in user_ids:
        for conn in list(_connections.get(uid, set())):
            await conn.send_json(event)


@router.websocket("/ws")
async def chat_ws(websocket: WebSocket, db: Session = Depends(get_db)):
    try:
        user = await get_current_user_ws(websocket, db)
    except (jwt_utils.InvalidTokenError, jwt_utils.TokenExpiredError):
        await websocket.close(code=4401)
        return

    await websocket.accept()
    _connections.setdefault(user.id, set()).add(websocket)
    svc = _service(db)

    try:
        while True:
            event = await websocket.receive_json()
            etype = event.get("type")
            try:
                if etype == "message.send":
                    conv_id = UUID(event["conversation_id"])
                    msg = svc.send_message(user.id, conv_id, event.get("content", ""), event.get("media_id"))
                    db.commit()
                    recipients = svc.member_ids(conv_id)
                    await _broadcast(recipients, {
                        "type": "message.new",
                        "id": str(msg.id),
                        "conversation_id": str(msg.conversation_id),
                        "sender_id": str(msg.sender_id),
                        "content": msg.content,
                        "created_at": msg.created_at.isoformat(),
                    })
                elif etype in ("typing.start", "typing.stop"):
                    conv_id = UUID(event["conversation_id"])
                    if not svc.is_member(conv_id, user.id):
                        continue
                    recipients = [uid for uid in svc.member_ids(conv_id) if uid != user.id]
                    await _broadcast(recipients, {
                        "type": "typing.update",
                        "conversation_id": str(conv_id),
                        "user_id": str(user.id),
                        "typing": etype == "typing.start",
                    })
                elif etype == "message.read":
                    msg_id = UUID(event["message_id"])
                    msg = svc._messages.get(msg_id)
                    if msg and svc.is_member(msg.conversation_id, user.id):
                        svc.mark_read(user.id, msg_id)
                        db.commit()
                        recipients = svc.member_ids(msg.conversation_id)
                        await _broadcast(recipients, {
                            "type": "message.read.update",
                            "message_id": str(msg_id),
                            "user_id": str(user.id),
                        })
            except AppError as exc:
                db.rollback()
                await websocket.send_json({"type": "error", "error": exc.error_code, "message": str(exc)})
            except (KeyError, ValueError, TypeError):
                db.rollback()
                await websocket.send_json({"type": "error", "error": "INVALID_EVENT", "message": "Malformed event"})
    except WebSocketDisconnect:
        pass
    finally:
        conns = _connections.get(user.id)
        if conns is not None:
            conns.discard(websocket)
            if not conns:
                _connections.pop(user.id, None)
