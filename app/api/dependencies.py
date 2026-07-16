import hmac
from collections.abc import AsyncIterator

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_password

security = HTTPBasic(auto_error=False)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.database.sessions() as session:
        yield session


def require_admin(
    request: Request,
    credentials: HTTPBasicCredentials | None = Depends(security),
) -> str:
    settings = request.app.state.settings
    valid = (
        credentials is not None
        and hmac.compare_digest(credentials.username, settings.admin_username)
        and verify_password(credentials.password, settings.admin_password_hash.get_secret_value())
    )
    if not valid or credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid administrator credentials",
            headers={"WWW-Authenticate": "Basic realm=NexusAI Admin"},
        )
    return credentials.username


def require_action_header(request: Request) -> None:
    if request.headers.get("X-Admin-Action") != "NexusAI":
        raise HTTPException(status_code=403, detail="Missing admin action confirmation header")
