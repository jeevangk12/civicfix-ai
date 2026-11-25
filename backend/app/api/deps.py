from collections.abc import Callable, Iterator
from dataclasses import dataclass
from threading import Lock
from time import monotonic
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import TokenClaims, read_token
from app.db.models import Role, User
from app.services.auth import active_user

CSRF_HEADER = "X-CivicFix-CSRF"
_bearer = HTTPBearer(auto_error=False)


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_db(request: Request) -> Iterator[Session]:
    with Session(request.app.state.database_engine, expire_on_commit=False) as session:
        yield session


Config = Annotated[Settings, Depends(get_settings)]
Database = Annotated[Session, Depends(get_db)]


@dataclass(frozen=True)
class AuthenticatedUser:
    user: User
    claims: TokenClaims


def unauthorized() -> HTTPException:
    return HTTPException(401, "Authentication failed.", headers={"WWW-Authenticate": "Bearer"})


def get_authenticated(
    db: Database, settings: Config, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]
) -> AuthenticatedUser:
    claims = read_token(settings, credentials.credentials, "access") if credentials is not None else None
    user = active_user(db, claims) if claims is not None else None
    if claims is None or user is None:
        raise unauthorized()
    return AuthenticatedUser(user, claims)


CurrentUser = Annotated[AuthenticatedUser, Depends(get_authenticated)]


def require_role(role: Role) -> Callable[..., User]:
    def check_role(current: CurrentUser) -> User:
        if current.user.role != role:
            raise HTTPException(403, "You do not have access to this resource.")
        return current.user

    return check_role


def require_csrf(request: Request, settings: Config) -> None:
    origin = request.headers.get("origin")
    if request.headers.get(CSRF_HEADER) != "1" or (origin is not None and origin not in settings.allowed_origins):
        raise HTTPException(403, "The request failed the CSRF check.")


class RequestRateLimiter:
    def __init__(self) -> None:
        self.lock = Lock()
        self.window = -1
        self.counts: dict[tuple[str, str], int] = {}

    def check(self, request: Request, action: str, limit: int) -> None:
        peer = request.client.host if request.client is not None else ""
        key = (action, peer)
        with self.lock:
            window = int(monotonic() // 60)
            if window != self.window:
                self.counts.clear()
                self.window = window
            used = self.counts.get(key, 0)
            if used >= limit:
                raise HTTPException(429, "Too many requests.", headers={"Retry-After": "60"})
            self.counts[key] = used + 1
