from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_session, require_action_header, require_admin
from app.repositories.admin import AdminRepository
from app.repositories.users import UserRepository
from app.schemas.admin import BlockRequest, PremiumGrantRequest
from app.services.news import NewsService
from app.services.premium import PremiumService

router = APIRouter(tags=["admin"])


@router.get("/admin", response_class=HTMLResponse, include_in_schema=False)
async def dashboard(_: str = Depends(require_admin)) -> HTMLResponse:
    template = (Path(__file__).parents[2] / "templates" / "admin.html").read_text(encoding="utf-8")
    return HTMLResponse(template)


@router.get("/api/admin/stats")
async def stats(
    admin: str = Depends(require_admin), session: AsyncSession = Depends(get_session)
) -> dict:
    return await AdminRepository(session).stats()


@router.get("/api/admin/users")
async def users(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    rows = await UserRepository(session).list_users(limit, offset)
    return [
        {
            "telegram_id": user.telegram_id,
            "username": user.username,
            "first_name": user.first_name,
            "status": user.status.value,
            "is_premium": user.is_premium,
            "premium_until": user.premium_until.isoformat() if user.premium_until else None,
            "created_at": user.created_at.isoformat(),
            "last_seen_at": user.last_seen_at.isoformat() if user.last_seen_at else None,
        }
        for user in rows
    ]


@router.post("/api/admin/users/{telegram_id}/block")
async def set_blocked(
    telegram_id: int,
    payload: BlockRequest,
    _: None = Depends(require_action_header),
    admin: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    repo = UserRepository(session)
    user = await repo.get_by_telegram_id(telegram_id)
    if not user:
        raise HTTPException(404, "User not found")
    await repo.set_blocked(user, payload.blocked)
    await AdminRepository(session).audit(
        admin, "user.block", "user", str(user.id), {"blocked": payload.blocked}
    )
    await session.commit()
    return {"ok": True, "blocked": payload.blocked}


@router.post("/api/admin/users/{telegram_id}/premium")
async def grant_premium(
    telegram_id: int,
    payload: PremiumGrantRequest,
    _: None = Depends(require_action_header),
    admin: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    user = await UserRepository(session).get_by_telegram_id(telegram_id)
    if not user:
        raise HTTPException(404, "User not found")
    subscription = await PremiumService(session).activate(
        user=user,
        days=payload.days,
        provider="admin",
        provider_reference=f"admin:{admin}:{user.id}:{uuid4().hex}",
        amount_cents=0,
        currency="USD",
    )
    await AdminRepository(session).audit(
        admin, "premium.grant", "user", str(user.id), {"days": payload.days}
    )
    await session.commit()
    return {"ok": True, "premium_until": subscription.ends_at.isoformat()}


@router.post("/api/admin/news/refresh")
async def refresh_news(
    request: Request,
    _: None = Depends(require_action_header),
    admin: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    inserted = await NewsService(session).refresh(request.app.state.settings.parsed_news_feeds)
    await AdminRepository(session).audit(admin, "news.refresh", metadata={"inserted": inserted})
    await session.commit()
    return {"ok": True, "inserted": inserted}
