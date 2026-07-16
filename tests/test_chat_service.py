from unittest.mock import AsyncMock

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.entities import ChatMessage, ChatSession, UsageEvent, User, UserStatus
from app.services.ai import AIResult
from app.services.chat import ChatService, QuotaExceededError, UserBlockedError


class FakeRedis:
    def __init__(self) -> None:
        self.deleted: list[str] = []

    async def delete(self, key: str) -> int:
        self.deleted.append(key)
        return 1


class StubProvider:
    def __init__(self, content: str = "A useful answer") -> None:
        self.content = content
        self.calls: list[list[dict[str, str]]] = []

    async def complete(self, messages: list[dict[str, str]]) -> AIResult:
        self.calls.append(messages)
        return AIResult(
            content=self.content,
            model="test-model",
            prompt_tokens=11,
            completion_tokens=7,
        )


async def create_user(session: AsyncSession, telegram_id: int = 4001) -> User:
    user = User(
        telegram_id=telegram_id,
        username=f"user-{telegram_id}",
        first_name="Chat",
        referral_code=f"CHAT{telegram_id}",
    )
    session.add(user)
    await session.commit()
    return user


@pytest.mark.asyncio
async def test_reply_persists_messages_usage_and_enforces_quota(
    session: AsyncSession, settings: Settings
) -> None:
    user = await create_user(session)
    redis = FakeRedis()
    provider = StubProvider()
    service = ChatService(session, redis, settings, provider)  # type: ignore[arg-type]
    service.rate_limiter.check = AsyncMock()

    result = await service.reply(user, "  Explain retrieval-augmented generation.  ")

    assert result.content == "A useful answer"
    assert provider.calls[0][0]["role"] == "system"
    assert provider.calls[0][-1] == {
        "role": "user",
        "content": "Explain retrieval-augmented generation.",
    }
    assert await session.scalar(select(func.count()).select_from(ChatMessage)) == 2
    assert await session.scalar(select(func.count()).select_from(UsageEvent)) == 1
    assert redis.deleted == [f"quota:{user.id}"]

    with pytest.raises(QuotaExceededError) as error:
        await service.reply(user, "A second request")
    assert error.value.limit == settings.free_daily_messages
    assert len(provider.calls) == 1


@pytest.mark.asyncio
async def test_reply_rejects_blocked_and_invalid_messages(
    session: AsyncSession, settings: Settings
) -> None:
    user = await create_user(session, telegram_id=4002)
    redis = FakeRedis()
    provider = StubProvider()
    service = ChatService(session, redis, settings, provider)  # type: ignore[arg-type]
    service.rate_limiter.check = AsyncMock()

    user.status = UserStatus.BLOCKED
    with pytest.raises(UserBlockedError):
        await service.reply(user, "Hello")
    service.rate_limiter.check.assert_not_awaited()

    user.status = UserStatus.ACTIVE
    with pytest.raises(ValueError, match="empty or too long"):
        await service.reply(user, "   ")
    with pytest.raises(ValueError, match="empty or too long"):
        await service.reply(user, "x" * (settings.max_user_message_chars + 1))
    assert provider.calls == []


@pytest.mark.asyncio
async def test_reset_rotates_the_active_conversation(
    session: AsyncSession, settings: Settings
) -> None:
    user = await create_user(session, telegram_id=4003)
    service = ChatService(session, FakeRedis(), settings, StubProvider())  # type: ignore[arg-type]
    service.rate_limiter.check = AsyncMock()

    await service.reply(user, "First conversation")
    original = await session.scalar(
        select(ChatSession).where(ChatSession.user_id == user.id, ChatSession.is_active.is_(True))
    )
    assert original is not None

    await service.reset(user)
    active_sessions = list(
        (
            await session.scalars(
                select(ChatSession).where(
                    ChatSession.user_id == user.id, ChatSession.is_active.is_(True)
                )
            )
        ).all()
    )
    assert len(active_sessions) == 1
    assert active_sessions[0].id != original.id
