import hmac
import secrets
from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.core.config import Settings

_password_hasher = PasswordHasher()


def verify_secret(provided: str | None, expected: str) -> bool:
    if provided is None:
        return False
    return hmac.compare_digest(provided, expected)


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def make_session_token(settings: Settings, username: str, csrf_token: str) -> str:
    serializer = URLSafeTimedSerializer(
        settings.secret_key.get_secret_value(), salt="admin-session"
    )
    return serializer.dumps({"sub": username, "csrf": csrf_token})


def read_session_token(settings: Settings, token: str) -> dict[str, str] | None:
    serializer = URLSafeTimedSerializer(
        settings.secret_key.get_secret_value(), salt="admin-session"
    )
    try:
        data = serializer.loads(token, max_age=settings.admin_session_minutes * 60)
    except (BadSignature, SignatureExpired):
        return None
    if not isinstance(data, dict) or "sub" not in data or "csrf" not in data:
        return None
    return data


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def subscription_expiry(days: int = 30) -> datetime:
    return datetime.now(UTC) + timedelta(days=days)
