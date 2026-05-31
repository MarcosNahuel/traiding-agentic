"""Agente conversacional — contestás por Telegram y Claude responde con datos reales.

Read-only: usa los tools del strategist (trades, portfolio, performance, quant, KB,
fear&greed, news, WebSearch) para contestar, pero NO opera ni cambia config.
Mismo patrón SDK que el strategist; fail-safe (si falla, devuelve un mensaje claro).
"""
from __future__ import annotations

import asyncio
import logging
import os

from ...config import settings

log = logging.getLogger(__name__)

_PERSONA = """Sos el "Strategist" de un bot de trading de cripto (Binance Testnet) y hablás con tu dueño por Telegram.

Tu rol: contestar preguntas sobre cómo va el bot, la estrategia, los trades, el régimen de mercado, el P&L, por qué tomaste tal decisión, etc. Sos su copiloto de estrategia.

Tenés tools para consultar datos REALES: trades recientes, portfolio, métricas de performance, snapshot quant por símbolo, ML, Fear&Greed, noticias, el Knowledge Base de estrategias, y WebSearch para contexto macro.

Reglas:
- Contestá en español rioplatense, claro y conciso (es un chat de Telegram, no un informe).
- Usá los tools para responder con datos concretos, no inventes números.
- Sos read-only: NO operás, NO cambiás configuración. Si te piden operar, explicá que las propuestas de cambio van por el flujo de aprobación (botones del strategist diario).
- Si no sabés algo, decilo. Sé honesto sobre la incertidumbre.
- Andá al grano: 2-6 oraciones salvo que pidan detalle."""


async def answer_question(question: str) -> str:
    """Responde una pregunta del usuario. Siempre devuelve texto (fail-safe)."""
    try:
        return await asyncio.wait_for(_run(question), timeout=float(settings.chat_timeout_s))
    except asyncio.TimeoutError:
        return "Me quedé pensando demasiado y corté. Probá preguntarme algo más puntual 🙏"
    except Exception as e:  # noqa: BLE001
        log.exception("chat agent failed")
        return f"Uf, no pude procesarlo ahora (error del agente: {type(e).__name__}). Probá de nuevo en un rato."


async def _run(question: str) -> str:
    from claude_agent_sdk import (  # lazy import
        AssistantMessage,
        ClaudeAgentOptions,
        ClaudeSDKClient,
        TextBlock,
    )

    from .tools import DATA_TOOLS, KNOWLEDGE_TOOLS, create_strategist_server

    if settings.claude_code_oauth_token and not os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"):
        os.environ["CLAUDE_CODE_OAUTH_TOKEN"] = settings.claude_code_oauth_token

    options = ClaudeAgentOptions(
        system_prompt=_PERSONA,
        mcp_servers={"strategist": create_strategist_server()},
        allowed_tools=[*DATA_TOOLS, *KNOWLEDGE_TOOLS],  # read-only; sin submit_decision
        permission_mode="bypassPermissions",
        max_turns=int(settings.chat_max_turns),
        model=settings.strategist_decision_model or "claude-sonnet-4-6",
    )

    answer = ""
    async with ClaudeSDKClient(options=options) as client:
        await client.query(question)
        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        answer += block.text

    return answer.strip() or "No tengo una respuesta clara para eso 🤔"
