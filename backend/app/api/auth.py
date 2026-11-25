from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response

from app.api.deps import Config, CurrentUser, Database, require_csrf, unauthorized
from app.api.responses import success
from app.core.config import Settings
from app.db.models import Role
from app.schemas.auth import AccessToken, AccountInput, DataResponse, LoginInput, UserDetails
from app.services import auth

router = APIRouter(prefix="/auth", tags=["authentication"])
_REFRESH_COOKIE = "civicfix_refresh"
_csrf_dependencies = [Depends(require_csrf)]


def _cookie_options(settings: Settings) -> dict:
    return {
        "path": f"{settings.api_v1_prefix}/auth",
        "httponly": True,
        "secure": settings.app_env not in {"development", "test"},
        "samesite": "strict",
    }


def _token_response(
    request: Request, response: Response, settings: Settings, tokens: auth.SessionTokens
) -> DataResponse[AccessToken]:
    response.headers["Cache-Control"] = "no-store"
    response.set_cookie(
        _REFRESH_COOKIE,
        tokens.refresh,
        max_age=max(0, int((tokens.expires_at - datetime.now(UTC)).total_seconds())),
        **_cookie_options(settings),
    )
    return success(request, AccessToken(access_token=tokens.access))


@router.post("/register", status_code=201)
def register(request: Request, payload: AccountInput, db: Database) -> DataResponse[UserDetails]:
    request.app.state.rate_limiter.check(request, "register", 10)
    try:
        user = auth.add_user(db, payload.full_name, payload.email, payload.password, Role.CITIZEN)
    except auth.EmailInUse:
        raise HTTPException(409, "An account already uses this email.") from None
    db.commit()
    return success(request, UserDetails.model_validate(user))


@router.post("/login", dependencies=_csrf_dependencies)
def login(
    request: Request, response: Response, payload: LoginInput, db: Database, settings: Config
) -> DataResponse[AccessToken]:
    request.app.state.rate_limiter.check(request, "login", 10)
    try:
        tokens = auth.login(db, settings, payload.email, payload.password)
    except auth.InvalidCredentials:
        raise unauthorized() from None
    return _token_response(request, response, settings, tokens)


@router.post("/refresh", dependencies=_csrf_dependencies)
def refresh(
    request: Request,
    response: Response,
    db: Database,
    settings: Config,
    refresh_cookie: Annotated[str | None, Cookie(alias=_REFRESH_COOKIE)] = None,
) -> DataResponse[AccessToken]:
    request.app.state.rate_limiter.check(request, "refresh", 30)
    if refresh_cookie is None:
        raise unauthorized()
    try:
        tokens = auth.rotate_session(db, settings, refresh_cookie)
    except auth.InvalidCredentials:
        raise unauthorized() from None
    return _token_response(request, response, settings, tokens)


@router.post("/logout", status_code=204, dependencies=_csrf_dependencies)
def logout(response: Response, db: Database, settings: Config, current: CurrentUser) -> None:
    auth.logout(db, current.claims)
    response.delete_cookie(_REFRESH_COOKIE, **_cookie_options(settings))


@router.get("/me")
def me(request: Request, current: CurrentUser) -> DataResponse[UserDetails]:
    return success(request, UserDetails.model_validate(current.user))
