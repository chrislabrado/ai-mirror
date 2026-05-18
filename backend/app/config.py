from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables (or a .env file)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- App ---
    app_env: Literal["local", "dev", "prod"] = "local"
    app_name: str = "AI Mirror"
    app_version: str = "1.1.0"

    # --- Persistence ---
    database_url: str = "sqlite+aiosqlite:///./data/ai_mirror.db"
    chroma_persist_dir: str = "./data/chroma"

    # --- Neo4j ---
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "ai_mirror_local"

    # --- LLM ---
    llm_provider: Literal["openai", "anthropic", "grok", "ollama"] = "openai"
    llm_model: str = "gpt-4o-mini"
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    xai_api_key: str | None = None
    xai_base_url: str = "https://api.x.ai/v1"
    ollama_base_url: str = "http://localhost:11434"

    # --- Embeddings ---
    embedding_provider: Literal["openai", "ollama"] = "openai"
    embedding_model: str = "text-embedding-3-small"

    # --- HTTP ---
    cors_origins: str = "http://localhost:5173,http://localhost:4173"

    # --- Limits ---
    max_upload_mb: int = Field(default=512, description="Per-file upload cap.")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
