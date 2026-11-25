from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hmac import compare_digest
from secrets import token_urlsafe
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import TokenClaims, issue_token, password_hasher, read_token, token_hash, verify_password
from app.db.models import RefreshSession, Role, User

_DUMMY_HASH = password_hasher.hash(token_urlsafe(32))


class EmailInUse(Exception):
    pass


class InvalidCredentials(Exception):
    pass


@dataclass(frozen=True)
class SessionTokens:
    access: str
    refresh: str
    expires_at: datetime


def add_user(db: Session, full_name: str, email: str, password: str, role: Role) -> User:
    user = User(full_name=full_name, email=email.casefold(), password_hash=password_hasher.hash(password), role=role)
    db.add(user)
    try:
        db.flush()
    except IntegrityError as error:
        if getattr(getattr(error.orig, "diag", None), "constraint_name", None) == "uq_users_email":
            raise EmailInUse from error
        raise
    return user


def _active_session_conditions(claims: TokenClaims, now: datetime) -> tuple:
    return (
        RefreshSession.user_id == claims.user_id,
        RefreshSession.family_id == claims.family_id,
        RefreshSession.revoked_at.is_(None),
        RefreshSession.expires_at > now,
    )


def active_user(db: Session, claims: TokenClaims) -> User | None:
    active_session = select(RefreshSession.id).where(*_active_session_conditions(claims, datetime.now(UTC)))
    return db.scalar(select(User).where(User.id == claims.user_id, User.is_active, active_session.exists()))


def _revoke_family(db: Session, claims: TokenClaims, now: datetime) -> None:
    db.execute(update(RefreshSession).where(*_active_session_conditions(claims, now)).values(revoked_at=now))
    db.commit()


def logout(db: Session, claims: TokenClaims) -> None:
    db.get(User, claims.user_id, with_for_update=True)
    _revoke_family(db, claims, datetime.now(UTC))


def _new_session(
    db: Session, settings: Settings, user_id: UUID, family_id: UUID, now: datetime, expires_at: datetime
) -> tuple[RefreshSession, SessionTokens]:
    refresh_claims = TokenClaims(user_id, family_id, uuid4())
    access_claims = TokenClaims(user_id, family_id, uuid4())
    refresh = issue_token(settings, refresh_claims, "refresh", now, expires_at)
    access_expires_at = min(expires_at, now + timedelta(minutes=settings.access_token_expire_minutes))
    access = issue_token(settings, access_claims, "access", now, access_expires_at)
    stored = RefreshSession(
        id=refresh_claims.token_id,
        user_id=user_id,
        family_id=family_id,
        token_hash=token_hash(refresh),
        expires_at=expires_at,
    )
    db.add(stored)
    return stored, SessionTokens(access, refresh, expires_at)


def login(db: Session, settings: Settings, email: str, password: str) -> SessionTokens:
    user = db.scalar(select(User).where(User.email == email.casefold()))
    valid = verify_password(user.password_hash if user is not None else _DUMMY_HASH, password)
    if not valid or user is None or not user.is_active:
        raise InvalidCredentials

    now = datetime.now(UTC)
    _, tokens = _new_session(
        db, settings, user.id, uuid4(), now, now + timedelta(days=settings.refresh_token_expire_days)
    )
    db.commit()
    return tokens


def rotate_session(db: Session, settings: Settings, refresh: str) -> SessionTokens:
    claims = read_token(settings, refresh, "refresh")
    if claims is None:
        raise InvalidCredentials

    # Lock the account consistently across refresh and logout, including across API workers.
    user = db.get(User, claims.user_id, with_for_update=True)
    stored = db.get(RefreshSession, claims.token_id)
    now = datetime.now(UTC)
    if (
        user is None
        or not user.is_active
        or stored is None
        or stored.user_id != claims.user_id
        or stored.family_id != claims.family_id
        or stored.expires_at <= now
        or not compare_digest(stored.token_hash, token_hash(refresh))
    ):
        raise InvalidCredentials
    if stored.revoked_at is not None:
        if stored.replaced_by_session_id is not None:
            _revoke_family(db, claims, now)
        raise InvalidCredentials

    replacement, tokens = _new_session(db, settings, user.id, stored.family_id, now, stored.expires_at)
    db.flush()
    stored.revoked_at = now
    stored.replaced_by_session_id = replacement.id
    db.commit()
    return tokens
