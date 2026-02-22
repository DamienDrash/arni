"""ARIIA v1.4 – Application Configuration.

@ARCH/@BACKEND: Pydantic Settings (Sprint 1, Task 1.3)
Loads from .env file or environment variables.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central application configuration."""

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
    gateway_public_url: str = ""  # For Webhook registration (e.g. https://ariia.getimpulse.de)
    cors_allowed_origins: str = "http://localhost:3000"

    # --- Redis ---
    # Redis runs on the same VPS → internal 127.0.0.1
    redis_url: str = "redis://127.0.0.1:6379/0"

    # --- OpenAI (Sprint 2) ---
    openai_api_key: str = ""

    # --- WhatsApp / Meta (Sprint 3) ---
    meta_verify_token: str = ""
    meta_access_token: str = ""
    meta_phone_number_id: str = ""
    meta_app_secret: str = ""  # HMAC-SHA256 webhook signature verification

    # --- Telegram Bot (Sprint 3) ---
    telegram_bot_token: str = ""
    telegram_admin_chat_id: str = ""
    telegram_webhook_secret: str = ""

    # --- ACP (Sprint 6a) ---
    acp_secret: str = "ariia-acp-secret-changeme"
    auth_secret: str = "change-me-long-random-secret"
    auth_token_ttl_hours: int = 12
    oidc_enabled: bool = False

    # --- WhatsApp Bridge (Sprint 8) ---
    bridge_mode: str = "production"  # 'self' = dev (self-chat only), 'production' = all incoming
    bridge_port: int = 3000
    bridge_webhook_url: str = "http://localhost:8000/webhook/whatsapp"
    bridge_log_level: str = "silent"
    bridge_auth_dir: str = "/app/data/whatsapp/auth_info_baileys"

    # --- Video/Voice (Sprint 5) ---
    elevenlabs_api_key: str = ""

    # --- Magicline (Sprint 10) ---
    magicline_base_url: str = ""
    magicline_api_key: str = ""
    magicline_studio_id: str = ""
    # magicline_tenant_id was removed — now configured per-tenant via Settings table (S3.1)

    # --- SMTP / Verification Mail ---
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_from_name: str = "Ariia"
    smtp_use_starttls: bool = True
    verification_email_subject: str = "Dein ARIIA Verifizierungscode"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


def get_settings() -> Settings:
    """Factory function for settings singleton."""
    return Settings()
