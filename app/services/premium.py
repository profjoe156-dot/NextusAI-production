from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import Subscription, SubscriptionStatus, User


class PremiumService:
    """Provider-neutral premium lifecycle service."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def activate(
        self,
        user: User,
        days: int,
        provider: str,
        provider_reference: str | None,
        amount_cents: int,
        currency: str,
    ) -> Subscription:
        now = datetime.now(UTC)
        current_until = user.premium_until
        if current_until and current_until.tzinfo is None:
            current_until = current_until.replace(tzinfo=UTC)
        starts_at = max(current_until or now, now)
        ends_at = starts_at + timedelta(days=days)
        subscription = Subscription(
            user_id=user.id,
            status=SubscriptionStatus.ACTIVE,
            plan_code="premium_monthly",
            provider=provider,
            provider_reference=provider_reference,
            amount_cents=amount_cents,
            currency=currency.upper()[:3],
            starts_at=now,
            ends_at=ends_at,
        )
        user.is_premium = True
        user.premium_until = ends_at
        self.session.add(subscription)
        await self.session.flush()
        return subscription

    async def expire_due(self) -> int:
        now = datetime.now(UTC)
        result = await self.session.execute(
            select(User).where(
                User.is_premium.is_(True),
                User.premium_until.is_not(None),
                User.premium_until <= now,
            )
        )
        users = list(result.scalars())
        for user in users:
            user.is_premium = False
        await self.session.execute(
            update(Subscription)
            .where(
                Subscription.status == SubscriptionStatus.ACTIVE,
                Subscription.ends_at <= now,
            )
            .values(status=SubscriptionStatus.EXPIRED)
        )
        await self.session.flush()
        return len(users)
