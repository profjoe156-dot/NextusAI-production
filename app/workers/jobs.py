import logging
import uuid
from collections.abc import Awaitable, Callable
from typing import cast

from app.db.redis import Cache
from app.db.session import Database
from app.services.news import NewsService
from app.services.premium import PremiumService

logger = logging.getLogger(__name__)
_RELEASE_LOCK = """
if redis.call('get', KEYS[1]) == ARGV[1] then
  return redis.call('del', KEYS[1])
else
  return 0
end
"""


async def with_lock(
    cache: Cache,
    name: str,
    ttl_seconds: int,
    job: Callable[[], Awaitable[None]],
) -> None:
    key = f"nexusai:jobs:lock:{name}"
    token = uuid.uuid4().hex
    acquired = await cache.client.set(key, token, nx=True, ex=ttl_seconds)
    if not acquired:
        logger.info("job_skipped_lock_held", extra={"job": name})
        return
    try:
        await job()
    except Exception:
        logger.exception("job_failed", extra={"job": name})
        raise
    finally:
        await cast(Awaitable[object], cache.client.eval(_RELEASE_LOCK, 1, key, token))


async def refresh_news(database: Database, cache: Cache, feed_urls: list[str]) -> None:
    async def run() -> None:
        async with database.sessions() as session:
            inserted = await NewsService(session).refresh(feed_urls)
            logger.info("news_refresh_completed", extra={"inserted": inserted})

    await with_lock(cache, "refresh_news", 900, run)


async def expire_premium(database: Database, cache: Cache) -> None:
    async def run() -> None:
        async with database.sessions() as session:
            expired = await PremiumService(session).expire_due()
            await session.commit()
            logger.info("premium_expiry_completed", extra={"expired": expired})

    await with_lock(cache, "expire_premium", 300, run)
