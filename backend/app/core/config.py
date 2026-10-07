"""Application configuration settings."""
import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration with environment variable support."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    environment: str = "development"
    host: str = "127.0.0.1"
    port: int = 8000
    demo_mode: bool = True

    # Security keys
    secret_key: str = "human-approval-dev-session-key-must-be-32-chars-long"
    receipt_signing_key: str = "human-approval-dev-receipt-key-must-be-32-chars"

    # SQLite Database
    database_path: str = "backend/data/approval_console.db"

    # Keycloak OIDC Authentication Settings
    oidc_issuer_url: str = "http://127.0.0.1:8080/realms/approval-console"
    oidc_client_id: str = "approval-console-client"
    oidc_client_secret: str = "approval-console-local-secret"
    oidc_redirect_uri: str = "http://127.0.0.1:8000/api/auth/callback"
    oidc_scopes: str = "openid email profile roles"

    # Grounded LLM Advisory Provider Settings
    llm_provider: str = "openai-compatible"  # openai-compatible | anthropic | gemini | ollama
    llm_model: str = "qwen3.8-27b"
    llm_base_url: str = "https://llm.chris-vo.com/v1"
    llm_api_key: Optional[str] = None
    llm_timeout_seconds: float = 15.0

    def validate_runtime_safety(self) -> None:
        """Enforces security boundaries: demo mode is strictly refused in production."""
        is_prod = self.environment.strip().lower() == "production"
        if is_prod and self.demo_mode:
            raise ValueError(
                "Security Violation: DEMO_MODE=true is strictly forbidden when ENVIRONMENT=production."
            )
        if is_prod and (self.host != "127.0.0.1" and not self.host.startswith("localhost")):
            # If bound to external interface in production, ensure secret keys are not defaults
            if "dev-session-key" in self.secret_key or "dev-receipt-key" in self.receipt_signing_key:
                raise ValueError("Security Violation: Production deployments require strong non-default SECRET_KEY.")


settings = Settings()
settings.validate_runtime_safety()
