import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes.admin import router as admin_router
from app.api.routes.health import router as health_router
from app.api.routes.webhooks import router as webhook_router
from app.bot.application import build_telegram_application
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.redis import Cache
from app.db.session import Database
from app.observability import RequestContextMiddleware
from app.services.ai import OpenAIProvider

settings = get_settings()
configure_logging(settings)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    database = Database(settings)
    cache = Cache(settings)
    ai_provider = OpenAIProvider(settings)
    telegram = build_telegram_application(settings)
    telegram.bot_data.update(
        settings=settings,
        database=database,
        cache=cache,
        ai_provider=ai_provider,
    )
    app.state.settings = settings
    app.state.database = database
    app.state.cache = cache
    app.state.ai_provider = ai_provider
    app.state.telegram = telegram
    await telegram.initialize()
    await telegram.start()
    if settings.environment != "test":
        await telegram.bot.set_webhook(
            url=settings.webhook_url,
            secret_token=settings.telegram_webhook_secret.get_secret_value(),
            max_connections=settings.telegram_max_connections,
            drop_pending_updates=settings.telegram_drop_pending_updates,
            allowed_updates=["message", "callback_query", "pre_checkout_query"],
        )
        logger.info("telegram_webhook_configured", extra={"url": settings.webhook_url})
    try:
        yield
    finally:
        await telegram.stop()
        await telegram.shutdown()
        await ai_provider.close()
        await cache.close()
        await database.dispose()


app = FastAPI(
    title="NexusAI API",
    version="1.0.0",
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url=None,
    lifespan=lifespan,
)
app.add_middleware(RequestContextMiddleware)
app.include_router(health_router)
app.include_router(admin_router)
app.include_router(webhook_router, prefix=settings.telegram_webhook_path)


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    return {"service": "NexusAI", "status": "online"}
