import time

from redis.asyncio import Redis


class RateLimitExceeded(Exception):
    def __init__(self, retry_after: int) -> None:
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded; retry in {retry_after}s")


class SlidingWindowRateLimiter:
    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    async def check(self, key: str, limit: int, window_seconds: int) -> None:
        now = time.time()
        member = f"{now:.6f}"
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.zremrangebyscore(key, 0, now - window_seconds)
            pipe.zadd(key, {member: now})
            pipe.zcard(key)
            pipe.expire(key, window_seconds + 1)
            _, _, count, _ = await pipe.execute()
        if int(count) > limit:
            await self.redis.zrem(key, member)
            oldest = await self.redis.zrange(key, 0, 0, withscores=True)
            retry_after = max(1, int(window_seconds - (now - oldest[0][1]))) if oldest else 1
            raise RateLimitExceeded(retry_after)
