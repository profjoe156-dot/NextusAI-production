from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import Referral, Subscription, SubscriptionStatus, User
from app.services.premium import PremiumService
from app.services.users import UserService


@pytest.mark.asyncio
async def test_registration_and_referral_reward_are_idempotent(session: AsyncSession) -> None:
    service = UserService(session)
    inviter_result = await service.register_or_update(
        telegram_id=1001,
        username="inviter",
        first_name="Inviter",
        last_name=None,
        language_code="en",
    )

    invitee_result = await service.register_or_update(
        telegram_id=1002,
        username="invitee",
        first_name="Invitee",
        last_name=None,
        language_code="en",
        referral_code=inviter_result.user.referral_code,
    )
    assert invitee_result.created is True
    assert invitee_result.referral_applied is True

    await session.refresh(inviter_result.user)
    assert inviter_result.user.is_premium is True
    assert inviter_result.user.premium_until is not None

    referral = await session.scalar(
        select(Referral).where(Referral.invitee_id == invitee_result.user.id)
    )
    assert referral is not None
    assert referral.reward_granted is True
    assert referral.reward_days == 3

    repeated = await service.register_or_update(
        telegram_id=1002,
        username="invitee-renamed",
        first_name="Invitee",
        last_name=None,
        language_code="en",
        referral_code=inviter_result.user.referral_code,
    )
    assert repeated.created is False
    assert repeated.referral_applied is False
    assert repeated.user.username == "invitee-renamed"

    referral_count = await session.scalar(select(func.count()).select_from(Referral))
    reward_count = await session.scalar(
        select(func.count()).select_from(Subscription).where(Subscription.provider == "referral")
    )
    assert referral_count == 1
    assert reward_count == 1


@pytest.mark.asyncio
async def test_premium_activation_stacks_and_normalizes_currency(session: AsyncSession) -> None:
    user = User(
        telegram_id=2001,
        username="premium-user",
        first_name="Premium",
        referral_code="PREMIUM1",
    )
    session.add(user)
    await session.flush()

    service = PremiumService(session)
    first = await service.activate(
        user=user,
        days=30,
        provider="admin",
        provider_reference="grant-one",
        amount_cents=999,
        currency="usd-extra",
    )
    first_end = user.premium_until
    assert first_end is not None

    second = await service.activate(
        user=user,
        days=10,
        provider="admin",
        provider_reference="grant-two",
        amount_cents=500,
        currency="eur",
    )
    await session.commit()

    assert user.is_premium is True
    assert second.ends_at - first_end == timedelta(days=10)
    assert first.currency == "USD"
    assert second.currency == "EUR"


@pytest.mark.asyncio
async def test_expire_due_updates_user_and_subscription(session: AsyncSession) -> None:
    user = User(
        telegram_id=3001,
        username="expired-user",
        first_name="Expired",
        referral_code="EXPIRED1",
    )
    session.add(user)
    await session.flush()

    service = PremiumService(session)
    subscription = await service.activate(
        user=user,
        days=30,
        provider="admin",
        provider_reference="expired-grant",
        amount_cents=0,
        currency="USD",
    )
    past = datetime.now(UTC) - timedelta(minutes=1)
    user.premium_until = past
    subscription.ends_at = past
    await session.commit()

    expired = await service.expire_due()
    await session.commit()
    await session.refresh(user)
    await session.refresh(subscription)

    assert expired == 1
    assert user.is_premium is False
    assert subscription.status == SubscriptionStatus.EXPIRED
