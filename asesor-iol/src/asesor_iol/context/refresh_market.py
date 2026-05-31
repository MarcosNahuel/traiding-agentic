"""Genera/actualiza el brief de contexto de mercado que lee el agente de conocimiento.

Reusa la idea de `scripts/refresh-market-context.py` del bot cripto: un markdown
liviano y fresco con el panorama macro argentino para un inversor conservador en USD.

Diseño deliberado: el brief NO hardcodea cifras (se desactualizan en horas). En su
lugar lista, para cada indicador, la **fuente autoritativa con URL** y cómo leerla.
El agente de conocimiento usa esto como mapa de fuentes y SIEMPRE re-verifica el
valor vigente con WebSearch antes de afirmárselo al usuario (disciplina de citas).

Uso (cron, ej. cada 6h):  python -m asesor_iol.context.refresh_market
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from pathlib import Path

from ..config import load_settings


@dataclass(frozen=True)
class Source:
    indicador: str
    como_leer: str
    fuente: str
    url: str


# Fuentes autoritativas (citas). Cambiar acá si una fuente se cae o se reemplaza.
SOURCES: list[Source] = [
    Source(
        "Inflación (IPC mensual e interanual)",
        "Tomar el último dato del IPC Nacional publicado; mirar mensual y la variación i.a.",
        "INDEC — IPC",
        "https://www.indec.gob.ar/indec/web/Nivel4-Tema-3-5-31",
    ),
    Source(
        "Dólar MEP (AL30 / GD30)",
        "Calculado como ARS/USD vía bono (comprar en pesos, vender la especie D). Comparar con CCL.",
        "Ámbito / BYMA",
        "https://www.ambito.com/contenidos/dolar-mep.html",
    ),
    Source(
        "Dólar CCL (contado con liqui)",
        "Referencia para fuga/valuación; brecha vs MEP y oficial.",
        "Ámbito",
        "https://www.ambito.com/contenidos/dolar.html",
    ),
    Source(
        "Tasa de política monetaria y plazo fijo (BADLAR)",
        "Tasa de referencia del BCRA y BADLAR bancos privados (rendimiento en pesos).",
        "BCRA — Principales variables",
        "https://www.bcra.gob.ar/PublicacionesEstadisticas/Principales_variables.asp",
    ),
    Source(
        "Riesgo país (EMBI Argentina)",
        "Spread soberano en puntos básicos; proxy de acceso al crédito y apetito por bonos AR.",
        "Ámbito / JP Morgan EMBI",
        "https://www.ambito.com/contenidos/riesgo-pais.html",
    ),
    Source(
        "Reservas internacionales y tipo de cambio oficial",
        "Nivel de reservas brutas BCRA y A3500 (mayorista). Señal de presión cambiaria.",
        "BCRA — Principales variables",
        "https://www.bcra.gob.ar/PublicacionesEstadisticas/Principales_variables.asp",
    ),
]


def _render(ts: str) -> str:
    fuentes_md = "\n".join(
        f"### {s.indicador}\n"
        f"- **Cómo leerlo:** {s.como_leer}\n"
        f"- **Fuente:** {s.fuente} — {s.url}\n"
        f"- **Valor vigente:** _re-verificar con WebSearch (no hardcodeado)_\n"
        for s in SOURCES
    )
    return f"""\
# Brief de contexto de mercado (Argentina · USD conservador)

_Actualizado: {ts}_

## Cómo usar este brief
El agente de conocimiento lee este archivo como **mapa de fuentes autoritativas**,
no como verdad congelada. Toda cifra debe **re-verificarse con WebSearch contra la
fuente citada** antes de afirmarse al usuario (las cifras macro argentinas cambian a
diario). Cada afirmación al usuario debe venir con su fuente.

## Indicadores y fuentes (citas)
{fuentes_md}
## Recordatorios de perfil
- Conservador en USD: priorizar **preservación de capital** sobre maximizar retorno.
- Instrumentos típicos: money market USD (FCI t+0 en dólares), CEDEARs diversificados,
  ON dólar (corporativos hard-dollar), bonos soberanos USD según riesgo país.
- Fondeo desde Argentina vía **MEP** (AL30/GD30). Atención al parking regulatorio vigente.
- Evitar apalancamiento, opciones especulativas y concentración alta.

## Lecturas que el agente de datos puede traer de IOL (solo lectura)
- Cartera, saldos por moneda, métricas (cash %, concentración).
- Cotización puntual, **panel** (universo CEDEARs/acciones), **chain de opciones**
  (sin greeks/IV — se calcularían aparte), **serie histórica** OHLC.
"""


def refresh() -> Path:
    settings = load_settings()
    path = Path(settings.market_context_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    ts = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    path.write_text(_render(ts), encoding="utf-8")
    return path


if __name__ == "__main__":
    p = refresh()
    print(f"Brief actualizado: {p}")
