from collections.abc import AsyncIterator
from typing import Any

from redis.asyncio import Redis

from app.core.config import Settings


class Cache:
    def __init__(self, settings: Settings) -> None:
        self.client: Redis = Redis.from_url(
            settings.redis_url, encoding="utf-8", decode_responses=True, health_check_interval=30
        )

    async def close(self) -> None:
        await self.client.aclose()

    async def ping(self) -> bool:
        return bool(await self.client.ping())

    async def get_json(self, key: str) -> Any | None:
        import json

        value = await self.client.get(key)
        return json.loads(value) if value else None

    async def set_json(self, key: str, value: Any, ttl: int) -> None:
        import json

        await self.client.set(key, json.dumps(value, default=str), ex=ttl)


async def get_redis() -> AsyncIterator[Redis]:
    from app.main import app

    yield app.state.cache.client
