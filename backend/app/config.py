from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    app_name: str = "NovaTech AI Knowledge Platform"
    database_url: str = "sqlite+aiosqlite:///./novatech.db"
    qdrant_url: str = ":memory:"
    qdrant_api_key: str | None = None
    qdrant_collection: str = "novatech_documents"
    upload_dir: str = "./uploads"
    max_upload_mb: int = Field(default=20, ge=1, le=100)
    chunk_size: int = Field(default=900, ge=100, le=8000)
    chunk_overlap: int = Field(default=140, ge=0, le=2000)
    embedding_provider: Literal["local", "openai"] = "local"
    embedding_model: str = "text-embedding-3-small"
    embedding_api_key: str | None = None
    embedding_base_url: str = "https://api.openai.com/v1"
    llm_provider: Literal["disabled", "openai"] = "disabled"
    llm_model: str = "gpt-4o-mini"
    llm_api_key: str | None = None
    llm_base_url: str = "https://api.openai.com/v1"
    cors_origins: str = "http://localhost:5173"
    rate_limit_requests: int = Field(default=60, ge=1, le=10000)
    rate_limit_window_seconds: int = Field(default=60, ge=1, le=3600)

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
