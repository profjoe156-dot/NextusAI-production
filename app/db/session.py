from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings


class Database:
    def __init__(self, settings: Settings) -> None:
        engine_kwargs: dict = {"pool_pre_ping": True}
        if not settings.database_url.startswith("sqlite"):
            engine_kwargs.update(
                pool_size=settings.db_pool_size,
                max_overflow=settings.db_max_overflow,
                pool_recycle=1800,
            )
        self.engine: AsyncEngine = create_async_engine(settings.database_url, **engine_kwargs)
        self.sessions = async_sessionmaker(
            bind=self.engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
        )

    async def dispose(self) -> None:
        await self.engine.dispose()

    async def session(self) -> AsyncIterator[AsyncSession]:
        async with self.sessions() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise


async def get_db_session() -> AsyncIterator[AsyncSession]:
    from app.main import app

    async for session in app.state.database.session():
        yield session
