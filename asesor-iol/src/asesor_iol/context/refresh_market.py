"""Genera/actualiza el brief de contexto de mercado que lee el agente de conocimiento.

Reusa la idea de `scripts/refresh-market-context.py` del bot cripto: un markdown
liviano y fresco con el panorama macro. En Fase 1 es un placeholder con estructura;
se puede enriquecer con fuentes (BCRA, dólar MEP, inflación) en una capa siguiente.

Uso (cron, ej. cada 6h):  python -m asesor_iol.context.refresh_market
"""
from __future__ import annotations

import datetime as _dt
from pathlib import Path

from ..config import load_settings

TEMPLATE = """\
# Brief de contexto de mercado (Argentina · USD conservador)

_Actualizado: {ts}_

## Cómo usar este brief
El agente de conocimiento lee este archivo como punto de partida. Toda cifra debe
re-verificarse con WebSearch antes de afirmarse al usuario (las fuentes cambian).

## Panorama (completar con fuentes)
- Inflación mensual: TBD (fuente: INDEC)
- Dólar MEP: TBD (fuente: mercado)
- Tasas / plazo fijo: TBD (fuente: BCRA)
- Riesgo país: TBD
- Notas relevantes: TBD

## Recordatorios de perfil
- Conservador en USD: priorizar preservación de capital.
- Instrumentos típicos: money market USD, CEDEARs diversificados, ON dólar.
- Evitar apalancamiento y alta volatilidad.
"""


def refresh() -> Path:
    settings = load_settings()
    path = Path(settings.market_context_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    ts = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    path.write_text(TEMPLATE.format(ts=ts), encoding="utf-8")
    return path


if __name__ == "__main__":
    p = refresh()
    print(f"Brief actualizado: {p}")
