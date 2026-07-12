"""
Open-Brain Backend — Application Configuration

Loads all settings from environment variables via pydantic-settings.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List
import json


class Settings(BaseSettings):
    """Application settings loaded from .env file."""

    # --- Application ---
    app_name: str = "Open-Brain"
    app_version: str = "1.0.0"
    debug: bool = False

    # --- Database ---
    database_url: str = "postgresql+asyncpg://openbrain:openbrain_secret@postgres:5432/openbrain_db"

    # --- Redis ---
    redis_url: str = "redis://redis:6379/0"

    # --- JWT ---
    jwt_secret_key: str = "change-me-to-a-random-64-char-string"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days
    refresh_token_expire_days: int = 7

    # --- CORS ---
    cors_origins: str = '["http://localhost:3000","http://localhost:8080"]'

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from JSON string."""
        try:
            return json.loads(self.cors_origins)
        except (json.JSONDecodeError, TypeError):
            return ["*"]

    # --- AI Providers ---
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"
    ollama_api_key: str = ""

    # --- SMTP (OTP Emails) ---
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = "openbrainofficial@gmail.com"
    smtp_use_tls: bool = True
    smtp_mock: bool = True  # When True (or smtp_host is empty), OTPs are logged to console

    # --- OTP ---
    otp_expire_minutes: int = 5

    # --- Rate Limiting ---
    rate_limit_requests_per_minute: int = 30
    rate_limit_ai_requests_per_minute: int = 10

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }


# Singleton settings instance
settings = Settings()
