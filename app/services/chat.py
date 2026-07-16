from datetime import UTC, datetime
from typing import cast

from openai.types.chat import ChatCompletionMessageParam
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.entities import MessageRole, User, UserStatus
from app.repositories.chat import ChatRepository
from app.services.ai import AIProviderError, AIResult, OpenAIProvider
from app.services.rate_limit import SlidingWindowRateLimiter

SYSTEM_PROMPT = (
    "You are NexusAI, a precise and helpful AI assistant inside Telegram. "
    "Use clear formatting, protect private information, and say when you are uncertain. "
    "Do not claim to have performed actions you cannot perform."
)


class UserBlockedError(Exception):
    pass


class QuotaExceededError(Exception):
    def __init__(self, limit: int) -> None:
        self.limit = limit
        super().__init__(f"Daily quota of {limit} messages reached")


class ChatService:
    def __init__(
        self,
        session: AsyncSession,
        redis: Redis,
        settings: Settings,
        provider: OpenAIProvider,
    ) -> None:
        self.session = session
        self.redis = redis
        self.settings = settings
        self.provider = provider
        self.repo = ChatRepository(session)
        self.rate_limiter = SlidingWindowRateLimiter(redis)

    async def reply(self, user: User, text: str) -> AIResult:
        if user.status == UserStatus.BLOCKED:
            raise UserBlockedError
        text = text.strip()
        if not text or len(text) > self.settings.max_user_message_chars:
            raise ValueError("Message is empty or too long")

        await self.rate_limiter.check(
            f"rl:chat:{user.telegram_id}",
            self.settings.rate_limit_requests,
            self.settings.rate_limit_window_seconds,
        )
        day_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        used = await self.repo.count_daily_requests(user.id, day_start)
        limit = (
            self.settings.premium_daily_messages
            if user.is_premium
            else self.settings.free_daily_messages
        )
        if used >= limit:
            raise QuotaExceededError(limit)

        chat = await self.repo.get_or_create_active_session(user.id)
        history = await self.repo.recent_messages(chat.id, self.settings.chat_history_messages)
        messages: list[ChatCompletionMessageParam] = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(
            cast(
                ChatCompletionMessageParam,
                {"role": item.role.value, "content": item.content},
            )
            for item in history
        )
        messages.append({"role": "user", "content": text})

        result = await self.provider.complete(messages)
        if not result.content:
            raise AIProviderError("The AI provider returned an empty response")
        await self.repo.add_message(chat.id, MessageRole.USER, text)
        await self.repo.add_message(
            chat.id,
            MessageRole.ASSISTANT,
            result.content,
            result.model,
            result.prompt_tokens,
            result.completion_tokens,
        )
        await self.repo.record_usage(
            user.id, result.model, result.prompt_tokens, result.completion_tokens
        )
        await self.session.commit()
        await self.redis.delete(f"quota:{user.id}")
        return result

    async def reset(self, user: User) -> None:
        await self.repo.reset_session(user.id)
        await self.session.commit()
