import asyncio
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from telegram import Bot

from app.api.routes.webhooks import router as webhook_router
from app.core.config import Settings
from app.core.security import (
    hash_password,
    make_session_token,
    new_csrf_token,
    read_session_token,
    verify_password,
    verify_secret,
)


def test_settings_normalize_railway_database_and_webhook_urls() -> None:
    settings = Settings(
        public_base_url="https://nexus.example/",
        database_url="postgresql://user:pass@db.example/nexus",
        telegram_webhook_path="telegram-updates",
    )

    assert settings.database_url.startswith("postgresql+asyncpg://")
    assert settings.public_base_url == "https://nexus.example"
    assert settings.telegram_webhook_path == "/telegram-updates"
    assert settings.webhook_url == "https://nexus.example/telegram-updates"


def test_settings_reject_insecure_production_configuration() -> None:
    with pytest.raises(ValueError, match="placeholders"):
        Settings(environment="production")

    with pytest.raises(ValueError, match="TELEGRAM_WEBHOOK_SECRET"):
        Settings(telegram_webhook_secret="not allowed!")


def test_settings_accept_hardened_production_configuration() -> None:
    settings = Settings(
        environment="production",
        public_base_url="https://nexus.example",
        cookie_secure=True,
        telegram_bot_token="123456:production-bot-token",
        telegram_webhook_secret="valid_production_secret",
        openai_api_key="sk-production-value",
        admin_username="nexus-operator",
        admin_password_hash=("$argon2id$v=19$m=65536,t=3,p=4$eGFtcGxlc2FsdA$eGFtcGxlaGFzaA"),
        secret_key="s" * 64,
    )

    assert settings.environment == "production"
    assert settings.cookie_secure is True


def test_password_and_signed_admin_session_helpers(settings: Settings) -> None:
    password_hash = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", password_hash) is True
    assert verify_password("wrong", password_hash) is False
    assert verify_password("password", "not-an-argon2-hash") is False
    assert verify_secret("known", "known") is True
    assert verify_secret(None, "known") is False

    csrf_token = new_csrf_token()
    token = make_session_token(settings, settings.admin_username, csrf_token)
    assert read_session_token(settings, token) == {
        "sub": settings.admin_username,
        "csrf": csrf_token,
    }
    assert read_session_token(settings, f"{token}tampered") is None


@pytest.mark.asyncio
async def test_webhook_rejects_bad_secret_and_queues_valid_update(settings: Settings) -> None:
    app = FastAPI()
    app.state.settings = settings
    queue: asyncio.Queue = asyncio.Queue()
    app.state.telegram = SimpleNamespace(
        bot=Bot(settings.telegram_bot_token.get_secret_value()),
        update_queue=queue,
    )
    app.include_router(webhook_router, prefix=settings.telegram_webhook_path)
    transport = httpx.ASGITransport(app=app)
    payload = {
        "update_id": 9001,
        "message": {
            "message_id": 1,
            "date": 1_700_000_000,
            "chat": {"id": 1234, "type": "private"},
            "from": {"id": 1234, "is_bot": False, "first_name": "Test"},
            "text": "/start",
        },
    }

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        rejected = await client.post(
            settings.telegram_webhook_path,
            headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"},
            json=payload,
        )
        accepted = await client.post(
            settings.telegram_webhook_path,
            headers={
                "X-Telegram-Bot-Api-Secret-Token": (
                    settings.telegram_webhook_secret.get_secret_value()
                )
            },
            json=payload,
        )

    assert rejected.status_code == 403
    assert accepted.status_code == 202
    queued = queue.get_nowait()
    assert queued.update_id == payload["update_id"]
    assert queued.effective_message.text == "/start"
