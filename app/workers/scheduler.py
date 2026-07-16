import asyncio
import logging
import signal

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.redis import Cache
from app.db.session import Database
from app.workers.jobs import expire_premium, refresh_news

logger = logging.getLogger(__name__)


async def serve() -> None:
    settings = get_settings()
    configure_logging(settings)
    database = Database(settings)
    cache = Cache(settings)
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        refresh_news,
        "interval",
        minutes=settings.news_refresh_minutes,
        args=[database, cache, settings.parsed_news_feeds],
        id="refresh_news",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=300,
    )
    scheduler.add_job(
        expire_premium,
        "interval",
        minutes=15,
        args=[database, cache],
        id="expire_premium",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=300,
    )
    if settings.scheduler_enabled:
        scheduler.start()
        logger.info("scheduler_started")
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    try:
        await stop.wait()
    finally:
        if scheduler.running:
            scheduler.shutdown(wait=False)
        await cache.close()
        await database.dispose()
        logger.info("scheduler_stopped")


def main() -> None:
    asyncio.run(serve())


if __name__ == "__main__":
    main()
