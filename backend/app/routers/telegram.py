"""Webhook conversacional de Telegram — le escribís al bot y el agente Claude responde.

Telegram es EL canal de comunicación con el agente que decide la estrategia.
Flujo: Telegram → POST /telegram/webhook → ack 200 rápido → (background) el agente
read-only contesta con datos reales → reply al mismo chat.

Seguridad:
- Header X-Telegram-Bot-Api-Secret-Token debe coincidir con TELEGRAM_WEBHOOK_SECRET.
- Solo se atiende al chat dueño (TELEGRAM_CHAT_ID); el resto se ignora en silencio.
- Gating CHAT_ENABLED (requiere Node+CLI en la imagen + CLAUDE_CODE_OAUTH_TOKEN).
"""
from __future__ import annotations

import hmac
import logging
import os

from fastapi import APIRouter, BackgroundTasks, Request

from ..config import settings
from ..services.strategist.chat_agent import answer_question
from ..services.telegram_notifier import send_telegram_to

log = logging.getLogger(__name__)
router = APIRouter()

_HELP = (
    "🧠 Soy el Strategist del bot. Preguntame lo que quieras:\n"
    "• ¿Cómo viene el P&L?\n"
    "• ¿Por qué pausaste BTC?\n"
    "• ¿Qué posiciones hay abiertas y con qué riesgo?\n"
    "• ¿Qué régimen de mercado ves hoy?\n\n"
    "Soy read-only: informo y aconsejo, pero los cambios de config se aprueban con "
    "los botones del informe diario."
)


async def _process(chat_id: str, text: str) -> None:
    """Corre el agente y responde. Fuera del request → no bloquea el ack a Telegram."""
    try:
        answer = await answer_question(text)
    except Exception as e:  # noqa: BLE001 — el agente ya es fail-safe, esto es doble red
        log.exception("telegram chat processing failed")
        answer = f"No pude procesarlo ahora ({type(e).__name__}). Probá de nuevo."
    await send_telegram_to(chat_id, answer)


@router.get("/telegram/diag")
async def telegram_diag() -> dict:
    """Diag del entorno del Agent SDK dentro del contenedor (versiones, no secretos)."""
    import asyncio as _asyncio
    import shutil

    async def _run(cmd: list[str]) -> str:
        try:
            proc = await _asyncio.create_subprocess_exec(
                *cmd, stdout=_asyncio.subprocess.PIPE, stderr=_asyncio.subprocess.STDOUT
            )
            out, _ = await _asyncio.wait_for(proc.communicate(), timeout=20)
            return (out.decode(errors="replace").strip())[:500]
        except Exception as e:  # noqa: BLE001
            return f"ERR {type(e).__name__}: {e}"

    return {
        "chat_enabled": settings.chat_enabled,
        "oauth_token_set": bool(settings.claude_code_oauth_token),
        "which_node": shutil.which("node"),
        "which_claude": shutil.which("claude"),
        "which_git": shutil.which("git"),
        "node_version": await _run(["node", "--version"]),
        "claude_version": await _run(["claude", "--version"]),
        "home": os.environ.get("HOME"),
    }


@router.post("/telegram/webhook")
async def telegram_webhook(request: Request, background: BackgroundTasks) -> dict:
    # 1) validar secreto del webhook (Telegram lo manda en este header)
    secret = settings.telegram_webhook_secret
    if secret:
        got = request.headers.get("x-telegram-bot-api-secret-token", "")
        if not hmac.compare_digest(got, secret):
            return {"ok": True}  # ignorar en silencio (no revelar)

    if not settings.chat_enabled:
        return {"ok": True}

    try:
        update = await request.json()
    except Exception:  # noqa: BLE001
        return {"ok": True}

    message = update.get("message") or update.get("edited_message") or {}
    chat = message.get("chat") or {}
    chat_id = str(chat.get("id", ""))
    text = (message.get("text") or "").strip()

    # 2) solo el dueño; resto ignorado
    owner = str(settings.telegram_chat_id or "")
    if not chat_id or (owner and chat_id != owner):
        return {"ok": True}

    if not text:
        return {"ok": True}

    # 3) comandos rápidos (responden ya, sin gastar el agente)
    if text in ("/start", "/help"):
        await send_telegram_to(chat_id, _HELP)
        return {"ok": True}

    # 4) ack inmediato + procesar en background (el agente tarda; Telegram no espera)
    await send_telegram_to(chat_id, "🧠 Dejame ver los datos… (un momento)")
    background.add_task(_process, chat_id, text)
    return {"ok": True}
