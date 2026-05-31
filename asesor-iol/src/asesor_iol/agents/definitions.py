"""Definiciones de subagentes (modelos mixtos + permisos por agente).

Mínimo privilegio:
- datos: solo tools de lectura IOL. SIN tools de orden.
- conocimiento: solo WebSearch/WebFetch. SIN acceso a IOL.
"""
from __future__ import annotations

from claude_agent_sdk import AgentDefinition  # type: ignore

from ..config import Settings
from . import prompts


def build_agents(settings: Settings) -> dict[str, AgentDefinition]:
    return {
        "datos": AgentDefinition(
            description="Trae hechos y métricas de la cuenta IOL. Usalo para cartera, saldos, cotizaciones y métricas.",
            prompt=prompts.DATA_AGENT,
            model=settings.model_data,
            effort=settings.effort_data,
            tools=[
                "mcp__iol__get_portfolio",
                "mcp__iol__get_account_state",
                "mcp__iol__get_metrics",
                "mcp__iol__get_quote",
            ],
        ),
        "conocimiento": AgentDefinition(
            description="Trae contexto macro con citas. Usalo para inflación, dólar, tasas, noticias.",
            prompt=prompts.KNOWLEDGE_AGENT,
            model=settings.model_knowledge,
            tools=["WebSearch", "WebFetch", "Read"],
        ),
    }
