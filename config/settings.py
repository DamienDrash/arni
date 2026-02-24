"""ARIIA v1.4 – Application Configuration.

@ARCH/@BACKEND: Pydantic Settings (Sprint 1, Task 1.3)
Loads from .env file or environment variables.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central application configuration (Global/System Scope)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Gateway ---
    environment: str = "development"
    log_level: str = "info"
    gateway_host: str = "0.0.0.0"
    gateway_port: int = 8000
    gateway_public_url: str = ""  # For Webhook registration
    cors_allowed_origins: str = "http://localhost:3000"

    # --- Database & Cache ---
    redis_url: str = "redis://127.0.0.1:6379/0"
    database_url: str = "postgresql+psycopg://ariia:ariia_dev_password@ariia_postgres:5432/ariia"

    # --- OpenAI (System Default / Fallback) ---
    openai_api_key: str = ""

    # --- Security & Auth (Global) ---
    acp_secret: str = "ariia-acp-secret-changeme"
    auth_secret: str = "change-me-long-random-secret"
    auth_token_ttl_hours: int = 12
    oidc_enabled: bool = False

    # --- WhatsApp Bridge (Global Service Config) ---
    bridge_mode: str = "production"
    bridge_port: int = 3000
    bridge_webhook_url: str = "http://localhost:8000/webhook/whatsapp"
    bridge_log_level: str = "silent"
    bridge_auth_dir: str = "/app/data/whatsapp/auth_info_baileys"

    # --- System Admin (Bootstrap) ---
    system_admin_email: str = "admin@ariia.io"
    system_admin_password: str = "Admin!Password2026"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


def get_settings() -> Settings:
    """Factory function for settings singleton."""
    return Settings()
