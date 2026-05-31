"""Entrypoint: arma el wiring y arranca el bot."""
from __future__ import annotations

import logging
import os

from .agents.orchestrator import Advisor
from .config import load_settings
from .iol.client import IOLClient
from .security.gate import ApprovalBroker
from .state.store import Store
from .telegram.bot import TelegramAdvisorBot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("asesor")


def run() -> None:
    settings = load_settings()
    # Auth del SDK: preferir el token del plan Max (CLAUDE_CODE_OAUTH_TOKEN, $0 marginal);
    # caer a ANTHROPIC_API_KEY solo si no hay token.
    if settings.claude_code_oauth_token:
        os.environ.setdefault("CLAUDE_CODE_OAUTH_TOKEN", settings.claude_code_oauth_token)
    elif settings.anthropic_api_key:
        os.environ.setdefault("ANTHROPIC_API_KEY", settings.anthropic_api_key)
    else:
        log.warning("Sin CLAUDE_CODE_OAUTH_TOKEN ni ANTHROPIC_API_KEY — el SDK fallará al autenticar.")

    store = Store(settings.state_db_path)
    broker = ApprovalBroker()
    iol_client = IOLClient(
        settings.iol_username, settings.iol_password, settings.iol_api_base
    )

    bot = TelegramAdvisorBot(settings, broker)
    advisor = Advisor(settings, iol_client, store, broker, bot.send_confirmation)
    bot.advisor = advisor

    log.info("Asesor IOL listo. Broker=IOL base=%s", settings.iol_api_base)
    try:
        bot.run()
    finally:
        store.close()


if __name__ == "__main__":
    run()
