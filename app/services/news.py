import asyncio
import logging
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

import feedparser
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import NewsItem

logger = logging.getLogger(__name__)


class NewsService:
    """Fetch and persist public RSS/Atom sources with URL deduplication."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def refresh(self, feed_urls: list[str]) -> int:
        inserted = 0
        timeout = httpx.Timeout(15.0, connect=5.0)
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": "NexusAI-News/1.0"},
        ) as client:
            for feed_url in feed_urls:
                try:
                    response = await client.get(feed_url)
                    response.raise_for_status()
                    if len(response.content) > 5_000_000:
                        raise ValueError("Feed exceeded 5 MB")
                    feed = await asyncio.to_thread(feedparser.loads, response.content)
                    source = feed.feed.get("title") or urlparse(feed_url).netloc
                    for entry in feed.entries[:30]:
                        url = str(entry.get("link", "")).strip()
                        title = str(entry.get("title", "")).strip()
                        if not url or not title:
                            continue
                        exists = await self.session.scalar(
                            select(NewsItem.id).where(NewsItem.source_url == url)
                        )
                        if exists:
                            continue
                        published = self._published_at(entry)
                        summary = str(entry.get("summary", "")).strip()
                        # Telegram receives plain, bounded summaries; source HTML is not trusted.
                        import re

                        summary = re.sub(r"<[^>]+>", " ", summary)
                        summary = re.sub(r"\s+", " ", summary)[:1000]
                        self.session.add(
                            NewsItem(
                                title=title[:500],
                                summary=summary,
                                source_name=str(source)[:160],
                                source_url=url[:2048],
                                published_at=published,
                            )
                        )
                        inserted += 1
                    await self.session.commit()
                except Exception:
                    await self.session.rollback()
                    logger.exception("News feed refresh failed", extra={"feed_url": feed_url})
        return inserted

    @staticmethod
    def _published_at(entry) -> datetime:
        for field in ("published", "updated"):
            value = entry.get(field)
            if value:
                try:
                    parsed = parsedate_to_datetime(value)
                    if parsed.tzinfo is None:
                        parsed = parsed.replace(tzinfo=UTC)
                    return parsed.astimezone(UTC)
                except (TypeError, ValueError, OverflowError):
                    pass
        return datetime.now(UTC)
