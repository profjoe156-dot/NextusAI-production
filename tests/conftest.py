from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.base import Base
from app.db.session import Database


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        environment="test",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'nexusai-test.db'}",
        redis_url="redis://localhost:6379/15",
        telegram_bot_token="123456:TEST_TOKEN",
        telegram_webhook_secret="test-webhook-secret",
        openai_api_key="test-openai-key",
        secret_key="test-secret-key-with-sufficient-entropy-for-signed-cookies",
        admin_password_hash="not-used-in-service-tests",
        free_daily_messages=1,
        premium_daily_messages=3,
        rate_limit_requests=10,
        rate_limit_window_seconds=60,
        scheduler_enabled=False,
    )


@pytest.fixture
async def database(settings: Settings) -> AsyncIterator[Database]:
    database = Database(settings)
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    try:
        yield database
    finally:
        await database.dispose()


@pytest.fixture
async def session(database: Database) -> AsyncIterator[AsyncSession]:
    async with database.sessions() as session:
        yield session
