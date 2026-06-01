"""Poller de Telegram (long-poll getUpdates) — alternativa al webhook, sin HTTPS.

Corre como task de fondo en el bot (always-on). Consulta getUpdates con long-poll,
y por cada mensaje del chat dueño dispara el agente Claude read-only y responde.

Se usa porque la infra del bot es HTTP (sin cert válido) y Telegram exige HTTPS para
webhooks. El polling no tiene ese requisito. Off by default (CHAT_ENABLED=false).
Fail-safe: ningún error corta el loop.
"""
from __future__ import annotations

import asyncio
import logging

import httpx

from ...config import settings
from .chat_agent import answer_question

log = logging.getLogger(__name__)

_API = "https://api.telegram.org/bot{token}"


async def _send(client: httpx.AsyncClient, token: str, chat_id: str, text: str) -> None:
    try:
        await client.post(
            f"{_API.format(token=token)}/sendMessage",
            json={"chat_id": chat_id, "text": text, "disable_web_page_preview": True},
            timeout=20,
        )
    except Exception as e:  # noqa: BLE001
        log.warning("telegram send failed: %s", e)


async def _handle(client: httpx.AsyncClient, token: str, chat_id: str, text: str) -> None:
    """Responde un mensaje (en su propia task → no bloquea el polling de otros)."""
    if text in ("/start", "/help"):
        await _send(client, token, chat_id, _HELP)
        return
    await _send(client, token, chat_id, "🧠 Dejame ver los datos… (un momento)")
    answer = await answer_question(text)
    await _send(client, token, chat_id, answer)


_HELP = (
    "🧠 Soy el Strategist del bot. Preguntame lo que quieras:\n"
    "• ¿Cómo viene el P&L?\n"
    "• ¿Qué posiciones hay abiertas y con qué riesgo?\n"
    "• ¿Por qué pausaste BTC?\n"
    "• ¿Qué régimen de mercado ves hoy?\n\n"
    "Soy read-only: informo y aconsejo; los cambios de config se aprueban con los "
    "botones del informe diario."
)


async def run_poller() -> None:
    """Loop principal: long-poll getUpdates y despacha. Solo si CHAT_ENABLED + config."""
    token = settings.telegram_bot_token
    owner = str(settings.telegram_chat_id or "")
    if not settings.chat_enabled or not token or not owner:
        log.info("telegram poller disabled (chat_enabled=%s, configured=%s)",
                 settings.chat_enabled, bool(token and owner))
        return

    base = _API.format(token=token)
    log.info("telegram poller starting (owner chat=%s)", owner)

    async with httpx.AsyncClient() as client:
        # Limpiar webhook por si quedó seteado (webhook y getUpdates son excluyentes)
        try:
            await client.get(f"{base}/deleteWebhook", params={"drop_pending_updates": "false"}, timeout=15)
        except Exception as e:  # noqa: BLE001
            log.warning("deleteWebhook failed (sigo igual): %s", e)

        offset: int | None = None
        while True:
            try:
                params = {"timeout": 50, "allowed_updates": '["message"]'}
                if offset is not None:
                    params["offset"] = offset
                r = await client.get(f"{base}/getUpdates", params=params, timeout=60)
                data = r.json()
                if not data.get("ok"):
                    log.warning("getUpdates not ok: %s", data)
                    await asyncio.sleep(5)
                    continue

                for upd in data.get("result", []):
                    offset = upd["update_id"] + 1
                    msg = upd.get("message") or {}
                    chat = msg.get("chat") or {}
                    chat_id = str(chat.get("id", ""))
                    text = (msg.get("text") or "").strip()
                    if not text or (owner and chat_id != owner):
                        continue
                    # Cada mensaje se atiende en su propia task (el agente tarda)
                    asyncio.create_task(_handle(client, token, chat_id, text))

            except asyncio.CancelledError:
                log.info("telegram poller cancelled")
                raise
            except Exception as e:  # noqa: BLE001 — nunca cortar el loop
                log.warning("telegram poller error (reintento): %s", e)
                await asyncio.sleep(5)
