"""
FinSpectra Application Configuration.
Reads from environment variables with safe defaults for development.
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "FinSpectra"
    app_version: str = "1.0.0"
    environment: Literal["development", "staging", "production"] = "development"
    log_level: str = "INFO"

    # Database
    database_url: str = "sqlite+aiosqlite:///./finspectra.db"

    # Security
    jwt_secret: str = "dev-secret-change-in-production-minimum-32-chars!!"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480

    # CORS
    cors_origins: str = "http://localhost:5173,http://localhost:3000,http://localhost:8000,http://127.0.0.1:8000,*"


    # File Upload
    max_upload_size_mb: int = 50

    # LLM (all optional)
    llm_provider: str = "openai"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    llm_timeout_seconds: int = 30

    # Graph Database (NetworkX in local dev; Neo4j in production)
    graph_backend: Literal["networkx", "neo4j"] = "networkx"
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "finspectra_password"
    neo4j_database: str = "neo4j"

    # Paths
    reports_dir: str = "reports"
    ml_models_dir: str = "backend/app/ml/models"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def llm_available(self) -> bool:
        return bool(self.openai_api_key)

    @property
    def is_sqlite(self) -> bool:
        return "sqlite" in self.database_url


@lru_cache
def get_settings() -> Settings:
    return Settings()
