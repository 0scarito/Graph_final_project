"""Configuration management using Pydantic Settings."""

import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Neo4j Configuration - Required
    neo4j_uri: str = Field(
        default_factory=lambda: os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        description="Neo4j connection URI"
    )
    neo4j_user: str = Field(
        default_factory=lambda: os.getenv("NEO4J_USER", "neo4j"),
        description="Neo4j username"
    )
    neo4j_password: str = Field(
        default_factory=lambda: os.getenv("NEO4J_PASSWORD", "password"),
        description="Neo4j password"
    )

    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Environment
    environment: str = "development"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        validate_default=True,
    )


settings = Settings()
