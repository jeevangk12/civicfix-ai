import os
import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.session import create_database_engine
from app.main import create_app


@pytest.fixture(scope="session")
def settings():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to run the PostgreSQL integration tests.")
    database = make_url(url).database or ""
    if database not in {
        "civicfix_ai_test", "civicfix_ai_test_phase3", "civicfix_ai_test_phase6", "civicfix_ai_test_phase7",
    } and re.fullmatch(r"civicfix_ai_test_phase8(?:_[a-z0-9_]+)?", database) is None:
        pytest.fail("TEST_DATABASE_URL must point to a dedicated CivicFix AI test database.")
    return Settings(
        _env_file=None,
        app_env="test",
        api_v1_prefix="/api/v1",
        database_url=url,
        cors_origins="http://localhost:5173",
        secret_key="auth-integration-signing-key-for-fixtures-only",
        gemini_model="",
        gemini_api_key="",
    )


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as client:
        yield client


@pytest.fixture
def db(settings):
    engine = create_database_engine(settings)
    try:
        with Session(engine, expire_on_commit=False) as db:
            yield db
    finally:
        engine.dispose()
