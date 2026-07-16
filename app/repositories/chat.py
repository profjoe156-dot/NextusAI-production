from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import ChatMessage, ChatSession, MessageRole, UsageEvent


class ChatRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_or_create_active_session(self, user_id) -> ChatSession:
        result = await self.session.execute(
            select(ChatSession)
            .where(ChatSession.user_id == user_id, ChatSession.is_active.is_(True))
            .order_by(ChatSession.updated_at.desc())
            .limit(1)
        )
        chat = result.scalar_one_or_none()
        if chat:
            return chat
        chat = ChatSession(user_id=user_id, title="New conversation", is_active=True)
        self.session.add(chat)
        await self.session.flush()
        return chat

    async def reset_session(self, user_id) -> ChatSession:
        await self.session.execute(
            update(ChatSession)
            .where(ChatSession.user_id == user_id, ChatSession.is_active.is_(True))
            .values(is_active=False)
        )
        chat = ChatSession(user_id=user_id, title="New conversation", is_active=True)
        self.session.add(chat)
        await self.session.flush()
        return chat

    async def recent_messages(self, session_id, limit: int) -> list[ChatMessage]:
        result = await self.session.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(limit)
        )
        return list(reversed(list(result.scalars())))

    async def add_message(
        self,
        session_id,
        role: MessageRole,
        content: str,
        model: str | None = None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
    ) -> ChatMessage:
        message = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            created_at=datetime.now(UTC),
        )
        self.session.add(message)
        await self.session.flush()
        return message

    async def record_usage(
        self,
        user_id,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> None:
        self.session.add(
            UsageEvent(
                user_id=user_id,
                event_type="ai_chat",
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                created_at=datetime.now(UTC),
            )
        )
        await self.session.flush()

    async def count_daily_requests(self, user_id, day_start: datetime) -> int:
        value = await self.session.scalar(
            select(func.count())
            .select_from(UsageEvent)
            .where(
                UsageEvent.user_id == user_id,
                UsageEvent.event_type == "ai_chat",
                UsageEvent.created_at >= day_start,
            )
        )
        return int(value or 0)
