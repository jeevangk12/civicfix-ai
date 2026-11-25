from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from logging import getLogger
from typing import Literal

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api import access, admin, auth, complaints, dashboards, engagement, evidence, intelligence, public_map
from app.api.deps import CSRF_HEADER, RequestRateLimiter
from app.api.responses import install_api_responses
from app.core.config import Settings
from app.db.session import create_database_engine
from app.services.evidence import CloudinaryEvidence
from app.services.gemini import GeminiClient

logger = getLogger(__name__)


class HealthResponse(BaseModel):
    status: Literal["ok"]


class ReadinessResponse(BaseModel):
    status: Literal["ready", "unavailable"]


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings if settings is not None else Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_database_engine(config)
        app.state.database_engine = engine
        try:
            yield
        finally:
            engine.dispose()

    development = config.app_env == "development"
    app = FastAPI(
        title=config.app_name,
        lifespan=lifespan,
        docs_url="/docs" if development else None,
        redoc_url=None,
        openapi_url="/openapi.json" if development else None,
    )
    app.state.settings = config
    app.state.gemini = GeminiClient(config) if config.gemini_model and config.gemini_api_key.get_secret_value() else None
    app.state.evidence = CloudinaryEvidence(config)
    app.state.rate_limiter = RequestRateLimiter()
    install_api_responses(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.allowed_origins,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Authorization", "Content-Type", CSRF_HEADER, "Idempotency-Key"],
        allow_credentials=True,
    )

    @app.get(f"{config.api_v1_prefix}/health")
    def health() -> HealthResponse:
        return HealthResponse(status="ok")

    @app.get(f"{config.api_v1_prefix}/ready", responses={503: {"model": ReadinessResponse}})
    def ready(request: Request, response: Response) -> ReadinessResponse:
        response.headers["Cache-Control"] = "no-store"
        try:
            with request.app.state.database_engine.connect() as connection:
                connection.execute(text("SELECT 1")).scalar_one()
            return ReadinessResponse(status="ready")
        except SQLAlchemyError:
            logger.warning("Database readiness check failed")
            response.status_code = 503
            return ReadinessResponse(status="unavailable")

    app.include_router(auth.router, prefix=config.api_v1_prefix)
    app.include_router(access.router, prefix=config.api_v1_prefix)
    app.include_router(admin.router, prefix=config.api_v1_prefix)
    app.include_router(complaints.router, prefix=config.api_v1_prefix)
    app.include_router(complaints.authority_router, prefix=config.api_v1_prefix)
    app.include_router(intelligence.router, prefix=config.api_v1_prefix)
    app.include_router(public_map.router, prefix=config.api_v1_prefix)
    app.include_router(complaints.public_router, prefix=config.api_v1_prefix)
    app.include_router(engagement.router, prefix=config.api_v1_prefix)
    app.include_router(evidence.router, prefix=config.api_v1_prefix)
    app.include_router(dashboards.router, prefix=config.api_v1_prefix)
    return app
