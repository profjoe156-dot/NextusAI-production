from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import AuditLog, ChatMessage, Subscription, UsageEvent, User


class AdminRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def stats(self) -> dict[str, int]:
        since = datetime.now(UTC) - timedelta(days=1)
        users = await self.session.scalar(select(func.count()).select_from(User))
        premium = await self.session.scalar(
            select(func.count()).select_from(User).where(User.is_premium.is_(True))
        )
        active_24h = await self.session.scalar(
            select(func.count()).select_from(User).where(User.last_seen_at >= since)
        )
        ai_requests_24h = await self.session.scalar(
            select(func.count())
            .select_from(UsageEvent)
            .where(UsageEvent.event_type == "ai_chat", UsageEvent.created_at >= since)
        )
        messages = await self.session.scalar(select(func.count()).select_from(ChatMessage))
        subscriptions = await self.session.scalar(select(func.count()).select_from(Subscription))
        return {
            "users": int(users or 0),
            "premium_users": int(premium or 0),
            "active_24h": int(active_24h or 0),
            "ai_requests_24h": int(ai_requests_24h or 0),
            "messages": int(messages or 0),
            "subscriptions": int(subscriptions or 0),
        }

    async def audit(
        self,
        actor: str,
        action: str,
        target_type: str | None = None,
        target_id: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        self.session.add(
            AuditLog(
                actor=actor,
                action=action,
                target_type=target_type,
                target_id=target_id,
                metadata_json=metadata or {},
                created_at=datetime.now(UTC),
            )
        )
        await self.session.flush()
