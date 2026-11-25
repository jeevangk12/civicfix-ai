import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from uuid import UUID, uuid4

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app import bootstrap_admin
from app.core.security import password_hasher, token_hash
from app.db.models import (
    AuditLog,
    Department,
    Organization,
    RefreshSession,
    Role,
    ServiceArea,
    StaffDepartmentMembership,
    StaffProfile,
    User,
)
from app.main import create_app

API = "/api/v1"
AUTH = f"{API}/auth"
CSRF = {"X-CivicFix-CSRF": "1"}
COOKIE = "civicfix_refresh"
PASSWORD = "local integration test phrase"


def _account():
    return {"full_name": "Example Citizen", "email": f"{uuid4()}@example.com", "password": PASSWORD}


def _register(client, account):
    result = client.post(f"{AUTH}/register", json=account)
    assert result.status_code == 201, result.text
    return result.json()["data"]


def _login(client, account):
    result = client.post(
        f"{AUTH}/login",
        json={"email": account["email"], "password": account["password"]},
        headers=CSRF,
    )
    assert result.status_code == 200, result.text
    return result


def _bearer(response):
    return {"Authorization": f"Bearer {response.json()['data']['access_token']}"}


def _refresh(client, token=None):
    headers = CSRF if token is None else {**CSRF, "Cookie": f"{COOKIE}={token}"}
    return client.post(f"{AUTH}/refresh", headers=headers)


def _organization(db):
    organization = Organization(name="Integration Test Organization")
    db.add(organization)
    db.flush()
    department = Department(organization_id=organization.id, code="TEST", name="Test Department")
    area = ServiceArea(organization_id=organization.id, name="Test Area")
    db.add_all([department, area])
    db.commit()
    return organization, department, area


def _staff_payload(scope):
    organization, department, area = scope
    return {
        **_account(),
        "full_name": "Example Staff",
        "organization_id": str(organization.id),
        "department_ids": [str(department.id)],
        "service_area_ids": [str(area.id)],
    }


def test_registration_normalizes_email_hashes_password_and_assigns_citizen(client, db):
    account = _account()
    result = _register(client, {**account, "email": account["email"].upper(), "full_name": "  Example Citizen  "})
    assert result["email"] == account["email"]
    assert result["full_name"] == "Example Citizen"
    assert result["role"] == "CITIZEN"
    assert "password_hash" not in result
    user = db.get(User, UUID(result["id"]))
    assert user.password_hash.startswith("$argon2id$")
    assert password_hasher.verify(user.password_hash, PASSWORD)
    assert client.post(f"{AUTH}/register", json=account).status_code == 409
    spoofed = client.post(f"{AUTH}/register", json={**_account(), "role": "ADMIN"})
    assert spoofed.status_code == 422
    assert PASSWORD not in spoofed.text


def test_login_requires_valid_password_and_profile_uses_access_token(client, db):
    account = _account()
    user = _register(client, account)
    credentials = {"email": account["email"], "password": "wrong password"}
    rejected = client.post(f"{AUTH}/login", json=credentials, headers=CSRF)
    unknown = client.post(f"{AUTH}/login", json={**credentials, "email": "unknown@example.com"}, headers=CSRF)
    assert rejected.status_code == unknown.status_code == 401
    assert rejected.json()["error"]["message"] == unknown.json()["error"]["message"]

    result = _login(client, {**account, "email": account["email"].upper()})
    cookie = result.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=strict" in cookie and f"Path={AUTH}" in cookie
    assert result.headers["cache-control"] == "no-store"
    assert set(result.json()["data"]) == {"access_token", "token_type"}
    stored = db.scalar(select(RefreshSession).where(RefreshSession.user_id == UUID(user["id"])))
    assert stored.token_hash == token_hash(client.cookies.get(COOKIE))
    assert client.get(f"{AUTH}/me", headers=_bearer(result)).json()["data"] == user


def test_refresh_rotates_and_reuse_revokes_the_session_family(client, db):
    account = _account()
    user = _register(client, account)
    _login(client, account)
    old_token = client.cookies.get(COOKIE)
    rotated = _refresh(client)
    assert rotated.status_code == 200
    new_token = client.cookies.get(COOKIE)
    assert new_token != old_token
    sessions = db.scalars(select(RefreshSession).where(RefreshSession.user_id == UUID(user["id"]))).all()
    by_hash = {item.token_hash: item for item in sessions}
    assert by_hash[token_hash(old_token)].replaced_by_session_id == by_hash[token_hash(new_token)].id
    assert by_hash[token_hash(old_token)].revoked_at is not None
    assert _refresh(client, old_token).status_code == 401
    assert _refresh(client, new_token).status_code == 401
    assert client.get(f"{AUTH}/me", headers=_bearer(rotated)).status_code == 401


def test_concurrent_refresh_creates_one_replacement(client, settings):
    account = _account()
    _register(client, account)
    _login(client, account)
    old_token = client.cookies.get(COOKIE)
    start = Barrier(2, timeout=10)

    def attempt():
        with TestClient(create_app(settings)) as separate:
            start.wait()
            return _refresh(separate, old_token)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = [executor.submit(attempt) for _ in range(2)]
        responses = [result.result() for result in results]
    assert sorted(response.status_code for response in responses) == [200, 401]
    issued = next(response for response in responses if response.status_code == 200)
    assert client.get(f"{AUTH}/me", headers=_bearer(issued)).status_code == 401


def test_logout_revokes_access_and_refresh_for_the_current_session(client):
    account = _account()
    _register(client, account)
    other_login = _login(client, account)
    login = _login(client, account)
    previous = client.cookies.get(COOKIE)
    result = client.post(f"{AUTH}/logout", headers={**CSRF, **_bearer(login)})
    assert result.status_code == 204 and result.content == b""
    assert client.cookies.get(COOKIE) is None
    assert "Max-Age=0" in result.headers["set-cookie"]
    assert _refresh(client, previous).status_code == 401
    assert client.get(f"{AUTH}/me", headers=_bearer(login)).status_code == 401
    assert client.get(f"{AUTH}/me", headers=_bearer(other_login)).status_code == 200


def test_citizen_cannot_access_staff_or_admin_routes(client, db):
    scope = _organization(db)
    payload = _staff_payload(scope)
    account = _account()
    _register(client, account)
    citizen = _bearer(_login(client, account))
    scope_url = f"{API}/authority/scope/{scope[0].id}"
    assert client.get(scope_url).status_code == 401
    assert client.post(f"{API}/admin/staff", json=payload).status_code == 401
    assert client.get(scope_url, headers=citizen).status_code == 403
    assert client.post(f"{API}/admin/staff", json=payload, headers=citizen).status_code == 403


def test_admin_provisions_staff_and_organization_scope_is_enforced(client, db, settings, monkeypatch):
    account = _account()
    monkeypatch.setenv("DATABASE_URL", str(settings.database_url))
    monkeypatch.setenv("SECRET_KEY", settings.secret_key.get_secret_value())
    monkeypatch.setattr(
        sys, "argv", ["bootstrap_admin", "--email", account["email"], "--name", "Integration Administrator"]
    )
    monkeypatch.setattr(bootstrap_admin, "getpass", lambda _: PASSWORD)
    bootstrap_admin.main()
    admin = db.scalar(select(User).where(User.email == account["email"]))
    assert admin.role == Role.ADMIN
    headers = _bearer(_login(client, account))
    first = _organization(db)
    second = _organization(db)
    payload = _staff_payload(first)
    endpoint = f"{API}/admin/staff"
    for field, foreign_id in (("department_ids", second[1].id), ("service_area_ids", second[2].id)):
        denied = client.post(endpoint, json={**payload, field: [str(foreign_id)]}, headers=headers)
        assert denied.status_code == 422

    created = client.post(endpoint, json=payload, headers=headers)
    assert created.status_code == 201, created.text
    assert client.post(endpoint, json=payload, headers=headers).status_code == 409
    data = created.json()["data"]
    assert data["user"]["role"] == "STAFF"
    staff_id = UUID(data["user"]["id"])
    event = db.scalar(select(AuditLog).where(AuditLog.entity_id == staff_id))
    assert (event.action, event.actor_id, event.organization_id) == ("STAFF_PROVISIONED", admin.id, first[0].id)
    staff_headers = _bearer(_login(client, payload))
    own = client.get(f"{API}/authority/scope/{first[0].id}", headers=staff_headers)
    assert own.status_code == 200
    assert own.json()["data"] == data["scope"]
    assert client.get(f"{API}/authority/scope/{second[0].id}", headers=staff_headers).status_code == 404
    assert client.get(f"{API}/authority/scope/{first[0].id}", headers=headers).status_code == 403
    assert client.post(endpoint, json=_staff_payload(second), headers=staff_headers).status_code == 403

    profile = db.scalar(select(StaffProfile).where(StaffProfile.user_id == staff_id))
    db.add(StaffDepartmentMembership(
        staff_profile_id=profile.id, organization_id=first[0].id, department_id=second[1].id
    ))
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_wrong_type_expiry_and_claims_are_rejected(client, settings):
    account = _account()
    _register(client, account)
    login = _login(client, account)
    refresh = client.cookies.get(COOKIE)
    access = login.json()["data"]["access_token"]
    payload = jwt.decode(
        access, settings.secret_key.get_secret_value(),
        algorithms=["HS256"], audience=settings.jwt_audience, issuer=settings.jwt_issuer
    )
    expired = datetime.now(UTC) - timedelta(seconds=1)
    bad_claims = [
        {"exp": expired},
        {"iss": "another-issuer"},
        {"aud": "another-audience"},
    ]
    tokens = [
        "invalid-token",
        refresh,
        jwt.encode(payload, "different-fixture-secret-for-signature", algorithm="HS256"),
    ] + [
        jwt.encode({**payload, **changes}, settings.secret_key.get_secret_value(), algorithm="HS256")
        for changes in bad_claims
    ]
    for token in tokens:
        assert client.get(f"{AUTH}/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
    assert _refresh(client, access).status_code == 401


def test_account_inactivation_denies_existing_tokens_and_login(client, db):
    account = _account()
    user = _register(client, account)
    login = _login(client, account)
    stored = db.get(User, UUID(user["id"]))
    stored.is_active = False
    db.commit()
    assert client.get(f"{AUTH}/me", headers=_bearer(login)).status_code == 401
    assert _refresh(client).status_code == 401
    assert client.post(
        f"{AUTH}/login", json={"email": account["email"], "password": PASSWORD}, headers=CSRF
    ).status_code == 401


def test_cookie_endpoints_enforce_csrf_and_exact_origin(client):
    account = _account()
    _register(client, account)
    login = _login(client, account)
    assert client.post(f"{AUTH}/refresh").status_code == 403
    assert client.post(f"{AUTH}/refresh", headers={**CSRF, "Origin": "https://other.example"}).status_code == 403
    assert client.post(f"{AUTH}/logout", headers=_bearer(login)).status_code == 403
    allowed = client.post(f"{AUTH}/refresh", headers={**CSRF, "Origin": "http://localhost:5173"})
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert allowed.headers["access-control-allow-credentials"] == "true"


def test_login_rate_limit(client, monkeypatch):
    monkeypatch.setattr("app.api.deps.monotonic", lambda: 1000)
    body = {"email": "unused@example.com", "password": PASSWORD}
    for _ in range(10):
        assert client.post(f"{AUTH}/login", json=body, headers=CSRF).status_code == 401
    rejected = client.post(f"{AUTH}/login", json=body, headers=CSRF)
    assert rejected.status_code == 429
    assert rejected.headers["retry-after"] == "60"
