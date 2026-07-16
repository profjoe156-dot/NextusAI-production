import secrets
import string
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import Referral, User, UserStatus


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        result = await self.session.execute(select(User).where(User.telegram_id == telegram_id))
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id) -> User | None:
        return await self.session.get(User, user_id)

    async def get_by_referral_code(self, code: str) -> User | None:
        result = await self.session.execute(select(User).where(User.referral_code == code.upper()))
        return result.scalar_one_or_none()

    async def create(
        self,
        telegram_id: int,
        username: str | None,
        first_name: str,
        last_name: str | None,
        language_code: str | None,
        referred_by: User | None = None,
    ) -> User:
        alphabet = string.ascii_uppercase + string.digits
        for _ in range(10):
            code = "".join(secrets.choice(alphabet) for _ in range(8))
            exists = await self.session.scalar(
                select(func.count()).select_from(User).where(User.referral_code == code)
            )
            if not exists:
                break
        else:
            raise RuntimeError("Could not allocate a referral code")

        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name or "NexusAI user",
            last_name=last_name,
            language_code=language_code,
            referral_code=code,
            referred_by_id=referred_by.id if referred_by else None,
            last_seen_at=datetime.now(UTC),
        )
        self.session.add(user)
        await self.session.flush()
        if referred_by:
            self.session.add(
                Referral(
                    inviter_id=referred_by.id,
                    invitee_id=user.id,
                    reward_days=3,
                    created_at=datetime.now(UTC),
                )
            )
        return user

    async def touch(self, user: User, username: str | None, first_name: str) -> None:
        user.username = username
        user.first_name = first_name or user.first_name
        user.last_seen_at = datetime.now(UTC)
        await self.session.flush()

    async def referral_count(self, user_id) -> int:
        return int(
            await self.session.scalar(
                select(func.count()).select_from(Referral).where(Referral.inviter_id == user_id)
            )
            or 0
        )

    async def list_users(self, limit: int = 100, offset: int = 0) -> list[User]:
        result = await self.session.execute(
            select(User).order_by(User.created_at.desc()).limit(limit).offset(offset)
        )
        return list(result.scalars())

    async def set_blocked(self, user: User, blocked: bool) -> None:
        user.status = UserStatus.BLOCKED if blocked else UserStatus.ACTIVE
        await self.session.flush()
