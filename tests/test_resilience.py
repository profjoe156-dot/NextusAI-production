from unittest.mock import AsyncMock

import pytest

from app.services.rate_limit import RateLimitExceeded, SlidingWindowRateLimiter
from app.workers.jobs import with_lock


class FakePipeline:
    def __init__(self, count: int) -> None:
        self.count = count
        self.commands: list[tuple[str, tuple[object, ...]]] = []

    async def __aenter__(self) -> "FakePipeline":
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    def zremrangebyscore(self, *args: object) -> "FakePipeline":
        self.commands.append(("zremrangebyscore", args))
        return self

    def zadd(self, *args: object) -> "FakePipeline":
        self.commands.append(("zadd", args))
        return self

    def zcard(self, *args: object) -> "FakePipeline":
        self.commands.append(("zcard", args))
        return self

    def expire(self, *args: object) -> "FakePipeline":
        self.commands.append(("expire", args))
        return self

    async def execute(self) -> list[object]:
        return [0, 1, self.count, True]


class FakeRateLimitRedis:
    def __init__(self, count: int, oldest: list[tuple[bytes, float]] | None = None) -> None:
        self.pipe = FakePipeline(count)
        self.oldest = oldest or []
        self.removed: list[tuple[str, str]] = []

    def pipeline(self, transaction: bool = True) -> FakePipeline:
        assert transaction is True
        return self.pipe

    async def zrem(self, key: str, member: str) -> int:
        self.removed.append((key, member))
        return 1

    async def zrange(
        self, key: str, start: int, end: int, *, withscores: bool
    ) -> list[tuple[bytes, float]]:
        assert (key, start, end, withscores) == ("rate:user", 0, 0, True)
        return self.oldest


@pytest.mark.asyncio
async def test_sliding_window_allows_requests_at_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.rate_limit.time.time", lambda: 1000.0)
    redis = FakeRateLimitRedis(count=3)
    limiter = SlidingWindowRateLimiter(redis)  # type: ignore[arg-type]

    await limiter.check("rate:user", limit=3, window_seconds=60)

    assert redis.removed == []
    assert [name for name, _ in redis.pipe.commands] == [
        "zremrangebyscore",
        "zadd",
        "zcard",
        "expire",
    ]


@pytest.mark.asyncio
async def test_sliding_window_removes_rejected_member_and_reports_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.services.rate_limit.time.time", lambda: 1000.0)
    redis = FakeRateLimitRedis(count=4, oldest=[(b"old", 970.0)])
    limiter = SlidingWindowRateLimiter(redis)  # type: ignore[arg-type]

    with pytest.raises(RateLimitExceeded) as error:
        await limiter.check("rate:user", limit=3, window_seconds=60)

    assert error.value.retry_after == 30
    assert redis.removed == [("rate:user", "1000.000000")]


class FakeLockClient:
    def __init__(self, acquired: bool) -> None:
        self.acquired = acquired
        self.set_calls: list[tuple[object, ...]] = []
        self.eval_calls: list[tuple[object, ...]] = []

    async def set(self, *args: object, **kwargs: object) -> bool:
        self.set_calls.append((*args, kwargs))
        return self.acquired

    async def eval(self, *args: object) -> int:
        self.eval_calls.append(args)
        return 1


class FakeCache:
    def __init__(self, acquired: bool) -> None:
        self.client = FakeLockClient(acquired)


@pytest.mark.asyncio
async def test_distributed_job_lock_skips_when_held() -> None:
    cache = FakeCache(acquired=False)
    job = AsyncMock()

    await with_lock(cache, "news", 120, job)  # type: ignore[arg-type]

    job.assert_not_awaited()
    assert cache.client.eval_calls == []


@pytest.mark.asyncio
async def test_distributed_job_lock_runs_and_releases_after_failure() -> None:
    cache = FakeCache(acquired=True)
    job = AsyncMock(side_effect=RuntimeError("worker failed"))

    with pytest.raises(RuntimeError, match="worker failed"):
        await with_lock(cache, "news", 120, job)  # type: ignore[arg-type]

    job.assert_awaited_once()
    assert len(cache.client.eval_calls) == 1
    assert cache.client.eval_calls[0][2].startswith("nexusai:jobs:lock:news")
