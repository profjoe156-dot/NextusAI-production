from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import AITool, NewsItem, Prompt


class ContentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def categories(self, model) -> list[str]:
        result = await self.session.execute(
            select(model.category)
            .where(model.is_active.is_(True))
            .distinct()
            .order_by(model.category)
        )
        return list(result.scalars())

    async def list_tools(self, category: str | None = None, limit: int = 20) -> list[AITool]:
        query = select(AITool).where(AITool.is_active.is_(True))
        if category:
            query = query.where(AITool.category == category)
        query = query.order_by(AITool.is_featured.desc(), AITool.name).limit(limit)
        return list((await self.session.execute(query)).scalars())

    async def list_prompts(
        self, category: str | None = None, include_premium: bool = False, limit: int = 20
    ) -> list[Prompt]:
        query = select(Prompt).where(Prompt.is_active.is_(True))
        if category:
            query = query.where(Prompt.category == category)
        if not include_premium:
            query = query.where(Prompt.is_premium.is_(False))
        query = query.order_by(Prompt.is_featured.desc(), Prompt.title).limit(limit)
        return list((await self.session.execute(query)).scalars())

    async def get_prompt(self, prompt_id) -> Prompt | None:
        return await self.session.get(Prompt, prompt_id)

    async def latest_news(self, limit: int = 10) -> list[NewsItem]:
        result = await self.session.execute(
            select(NewsItem)
            .where(NewsItem.is_published.is_(True))
            .order_by(NewsItem.published_at.desc())
            .limit(limit)
        )
        return list(result.scalars())
