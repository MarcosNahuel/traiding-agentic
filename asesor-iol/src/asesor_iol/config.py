"""Configuración tipada del asesor. Lee de env vars / .env (nunca del git)."""
from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # IOL (credenciales de la cuenta real)
    iol_username: str
    iol_password: str
    iol_api_base: str = "https://api.invertironline.com"

    # Anthropic — preferí el token Max (CLAUDE_CODE_OAUTH_TOKEN, $0 marginal); API key opcional como fallback
    claude_code_oauth_token: str = ""
    anthropic_api_key: str = ""

    # Telegram
    telegram_bot_token: str
    telegram_allowed_chat_id: int

    # Modelos mixtos (aliases del CLI: opus/sonnet/haiku) + effort por agente
    model_orchestrator: str = "opus"
    model_data: str = "opus"          # data-analytics también en Opus...
    effort_data: str = "low"          # ...pero low-effort: razona mejor sin gastar de más
    model_knowledge: str = "sonnet"

    # Límites duros
    max_order_amount: float = 2000.0
    max_daily_amount: float = 5000.0
    allowed_symbols: str = ""
    order_confirmation_timeout_min: int = 10

    # Estado / contexto
    state_db_path: str = "./data/asesor.db"
    market_context_path: str = "./data/market-context.md"

    @property
    def allowed_symbols_set(self) -> set[str]:
        return {s.strip().upper() for s in self.allowed_symbols.split(",") if s.strip()}


def load_settings() -> Settings:
    """Carga settings. Falla temprano y claro si falta algo crítico."""
    return Settings()  # type: ignore[call-arg]
