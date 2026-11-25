from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.core.config import Settings
from app.main import create_app


def test_health_reports_api_liveness() -> None:
    settings = Settings(
        _env_file=None,
        app_env="test",
        api_v1_prefix="/api/v1",
        database_url="postgresql+psycopg://test:test@127.0.0.1:1/civicfix_ai_test",
        secret_key="health-test-signing-key-for-fixtures-only",
    )
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_queries_database_and_keeps_errors_private(client, monkeypatch):
    ready = client.get("/api/v1/ready")
    assert ready.status_code == 200 and ready.json() == {"status": "ready"}
    assert ready.headers["cache-control"] == "no-store"

    def unavailable():
        raise OperationalError(None, None, RuntimeError("synthetic connection details"))

    monkeypatch.setattr(client.app.state.database_engine, "connect", unavailable)
    failed = client.get("/api/v1/ready")
    assert failed.status_code == 503 and failed.json() == {"status": "unavailable"}
    assert client.get("/api/v1/health").status_code == 200


def test_managed_postgres_url_selects_psycopg():
    settings = Settings(
        _env_file=None,
        database_url="postgresql://test:test@managed.example.com:5432/civicfix_staging?sslmode=require",
        secret_key="test-signing-key-for-managed-url-validation",
    )
    assert str(settings.database_url) == (
        "postgresql+psycopg://test:test@managed.example.com:5432/civicfix_staging?sslmode=require"
    )
