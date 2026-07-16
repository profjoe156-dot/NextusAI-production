from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import Referral, User
from app.repositories.users import UserRepository
from app.services.premium import PremiumService


@dataclass(slots=True)
class RegistrationResult:
    user: User
    created: bool
    referral_applied: bool


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)

    async def register_or_update(
        self,
        telegram_id: int,
        username: str | None,
        first_name: str,
        last_name: str | None,
        language_code: str | None,
        referral_code: str | None = None,
    ) -> RegistrationResult:
        existing = await self.users.get_by_telegram_id(telegram_id)
        if existing:
            await self.users.touch(existing, username, first_name)
            await self.session.commit()
            return RegistrationResult(existing, False, False)

        referrer = None
        if referral_code:
            referrer = await self.users.get_by_referral_code(referral_code)
            if referrer and referrer.telegram_id == telegram_id:
                referrer = None
        try:
            user = await self.users.create(
                telegram_id,
                username,
                first_name,
                last_name,
                language_code,
                referrer,
            )
            if referrer:
                await PremiumService(self.session).activate(
                    user=referrer,
                    days=3,
                    provider="referral",
                    provider_reference=str(user.id),
                    amount_cents=0,
                    currency="USD",
                )
                referral = await self.session.scalar(
                    select(Referral).where(Referral.invitee_id == user.id)
                )
                if referral:
                    referral.reward_granted = True
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            recovered_user = await self.users.get_by_telegram_id(telegram_id)
            if not recovered_user:
                raise
            return RegistrationResult(recovered_user, False, False)
        return RegistrationResult(user, True, referrer is not None)
