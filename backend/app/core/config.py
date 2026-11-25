from decimal import Decimal
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, PostgresDsn, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8-sig",
        extra="ignore",
        hide_input_in_errors=True,
    )

    app_env: Literal["development", "test", "staging", "production"] = "development"
    app_name: str = Field(default="CivicFix AI", min_length=1)
    api_v1_prefix: str = Field(default="/api/v1", pattern=r"^/[\w-]+(?:/[\w-]+)*$")
    database_url: PostgresDsn
    cors_origins: str = "http://localhost:5173"
    secret_key: SecretStr
    jwt_issuer: str = Field(default="civicfix-ai", min_length=1)
    jwt_audience: str = Field(default="civicfix-ai-client", min_length=1)
    access_token_expire_minutes: int = Field(default=15, ge=1, le=30)
    refresh_token_expire_days: int = Field(default=7, ge=1, le=30)
    gemini_api_key: SecretStr = SecretStr("")
    gemini_model: str = Field(default="", pattern=r"^[a-zA-Z0-9._-]{0,120}$")
    gemini_timeout_seconds: float = Field(default=30, gt=0, le=60)
    duplicate_radius_meters: int = Field(default=150, ge=10, le=2000)
    duplicate_window_days: int = Field(default=30, ge=1, le=180)
    duplicate_similarity_threshold: float = Field(default=0.5, gt=0, le=1)
    public_location_grid_degrees: Decimal = Field(default=Decimal("0.01"), ge=Decimal("0.001"), le=Decimal("0.1"), decimal_places=3)
    cloudinary_cloud_name: str = ""
    cloudinary_api_key: SecretStr = SecretStr("")
    cloudinary_api_secret: SecretStr = SecretStr("")
    max_upload_size_mb: int = Field(default=5, ge=1, le=10)
    max_images_per_complaint: int = Field(default=4, ge=1, le=8)

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @field_validator("cors_origins")
    @classmethod
    def validate_origins(cls, value: str) -> str:
        for origin in filter(None, (entry.strip() for entry in value.split(","))):
            url = urlsplit(origin)
            if (
                url.scheme not in {"http", "https"}
                or url.hostname is None
                or url.username is not None
                or origin != f"{url.scheme}://{url.netloc}"
                or "*" in origin
                or any(character.isspace() for character in origin)
            ):
                raise ValueError("CORS_ORIGINS must contain exact HTTP or HTTPS origins")
            _ = url.port
        return value

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value().encode()) < 32:
            raise ValueError("SECRET_KEY must be a random secret of at least 32 bytes")
        return value

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, url: PostgresDsn) -> PostgresDsn:
        if url.scheme != "postgresql+psycopg" or not url.path or url.path == "/":
            raise ValueError("Use a postgresql+psycopg URL with a database name")
        return url

    @field_validator("database_url", mode="before")
    @classmethod
    def use_psycopg_for_managed_urls(cls, value: object) -> object:
        if isinstance(value, str) and value.startswith(("postgresql://", "postgres://")):
            return "postgresql+psycopg://" + value.split("://", 1)[1]
        return value
