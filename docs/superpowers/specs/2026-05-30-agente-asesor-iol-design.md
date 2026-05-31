# Agente Asesor de Inversiones IOL — Diseño (Fase 1: Base + Conversacional)

**Fecha:** 2026-05-30
**Estado:** Aprobado (brainstorming) → implementación
**Branch:** `feat/asesor-iol-base`

## Contexto y objetivo

Construir un **agente asesor de inversiones** que opere sobre **InvertirOnline (IOL)**, en modo **asesor con human-in-the-loop** (la IA propone, el humano confirma cada orden por Telegram). Perfil del usuario: **conservador en USD, US$5.000–20.000, plata en Argentina** (fondeo local vía MEP).

Proyecto **nuevo y separado** del bot cripto (Binance), que está acoplado a Binance en 12 archivos sin abstracción de broker y cuya lógica no transfiere a equities argentinas.

### Por qué IOL
Investigado y validado (deep-research + Codex). IOL es el **único broker argentino con API oficial documentada (OAuth2) + MCP oficial** (human-in-the-loop por diseño). Alternativas: Cocos (API no oficial/frágil, sin MCP), Balanz/Allaria/Rava (cerrados), Tradier/IBKR (mejores APIs pero requieren fondeo USD offshore). Con la plata en Argentina, IOL gana por fondeo local sin fricción.

### Por qué NO arbitraje ni generador de estrategias
Arbitraje retail automatizado (MEP/CCL, CEDEAR-ADR) es inviable (settlement T+1/T+2, parking regulatorio cambiante, comisiones, latencia de polling). El "generador de estrategias" se descarta: para conservador USD el edge es **conductual** (asignación sensata + disciplina), no predictivo. Repetir maquinaria cuantitativa sería el error del bot cripto (complejidad sin edge).

## Visión completa (norte) y construcción por capas

**Norte:** sistema multi-agente (orquestador conversacional + datos + conocimiento + oportunidades + memoria macro).

**Construcción por capas:**
1. **Fase 1 — Base + Conversacional** (este spec): orquestador + agente de datos IOL + agente de conocimiento (contexto liviano) + Telegram + gate de confirmación.
2. Fase 2 — Vigía de oportunidades (escaneo + alertas).
3. Fase 3 — Gestor proactivo (asignación objetivo + rebalanceo propuesto).
4. Después — RAG/memoria macro pesada (optimización de contexto, no capacidad nueva).

## Arquitectura (Fase 1)

Corre en el **VPS Hostinger, contenedor separado** del bot cripto.

```
                    ┌──────────────────────────┐
        Telegram ◀──▶│  ORQUESTADOR (Opus)      │  juicio + decisión + charla
                    └──────────┬───────────────┘
                   despacha    │    despacha
              ┌────────────────┴────────────────┐
              ▼                                  ▼
   ┌─────────────────────┐          ┌──────────────────────────┐
   │ AGENTE DATOS         │          │ AGENTE CONOCIMIENTO       │
   │ (Haiku/Sonnet)       │          │ (Sonnet)                  │
   │ · tools IOL (read)   │          │ · WebSearch + brief       │
   │ · métricas           │          │ · macro con CITAS         │
   │ · SOLO HECHOS        │          │ · sin acceso a IOL        │
   └─────────────────────┘          └──────────────────────────┘
              │                                  │
              └──────────► al orquestador ◄──────┘
                    (sintetiza → propone → 🔒 gate confirmación → IOL)
```

### Componentes
1. **Telegram I/O** (`python-telegram-bot`, long-polling): recibe mensajes, envía respuestas, botones inline Confirmar/Cancelar.
2. **Orquestador** (`query`/`ClaudeSDKClient` del `claude-agent-sdk`, modelo Opus): decide qué subagentes/tools usar, sintetiza, propone.
3. **Agente Datos** (`AgentDefinition`, Haiku/Sonnet): tools de lectura IOL + cálculo de métricas. **Sin tools de orden.** Reporta hechos, no recomienda.
4. **Agente Conocimiento** (`AgentDefinition`, Sonnet): WebSearch + lectura del brief de contexto. **Sin acceso a IOL.** Siempre con citas.
5. **Cliente IOL** (`iol_client.py`, `httpx` async): auth OAuth2 password grant, refresh de token (15 min), endpoints (portafolio, estado de cuenta, cotizaciones, comprar/vender/cancelar). Expuesto como tools in-process (`@tool` + `create_sdk_mcp_server`).
6. **Gate de confirmación** (hook `PreToolUse`): intercepta toda tool de orden → Telegram con detalle → espera tu botón → permite/bloquea. Aplica límites duros antes de mostrar.
7. **Audit log** (hook `PostToolUse`): cada tool call append-only a SQLite.
8. **Brief de contexto** (`refresh_market.py` + cron): genera `market-context.md`.

### Modelos (mixtos)
- Orquestador: **Opus** (juicio).
- Datos: **Haiku** (o Sonnet si las métricas requieren más) — barato, mucho JSON.
- Conocimiento: **Sonnet** — research + síntesis con citas.

## Flujos

**A — Consulta/asesoramiento (lectura, sin riesgo):** usuario pregunta → orquestador despacha Datos (cartera/métricas) + Conocimiento (macro) → sintetiza respuesta fundamentada con citas.

**B — Orden con confirmación:** orquestador llama `place_buy/sell` → **hook PreToolUse intercepta** → valida límites duros → Telegram con detalle (símbolo, monto, precio aprox, impacto) + botones → usuario confirma → recién ahí se ejecuta en IOL → reporta resultado/ID. Sin confirmación en N minutos → expira.

## Seguridad (crítico: maneja la cuenta real)

### Mínimo privilegio por agente
| Agente | Puede | No puede |
|---|---|---|
| Conocimiento | WebSearch, leer brief | Tocar IOL |
| Datos | Leer cartera/cotizaciones/saldos | Comprar/vender/cancelar |
| Orquestador | Leer + proponer órdenes | Ejecutar sin pasar por el gate |

### Defensas
- **Gate de confirmación** obligatorio (PreToolUse) en toda orden. Sin tap → no ejecuta.
- **Límites duros** (config): monto máx por orden, tope diario, símbolos permitidos. Validados por el hook antes de mostrar el botón.
- **Audit log** append-only (PostToolUse): timestamp, params, resultado.
- **Secretos** en env vars / `.env` fuera del git: credenciales IOL (máxima sensibilidad), API key Anthropic, token Telegram. `setting_sources=[]` para no cargar configs del filesystem.

### Manejo de errores (fail-safe: ante la duda, no opera)
| Falla | Respuesta |
|---|---|
| Token IOL expiró | Auto-refresh; si falla → avisa y frena |
| API IOL error/timeout | Nunca asume éxito; reporta; **nunca reintenta una orden** (riesgo doble-ejecución) |
| Orden duplicada | Idempotencia con ID único |
| LLM/agente alucina | Fail-closed: sin confirmación no hay orden |
| Telegram caído | Peor caso "no pasa nada" → seguro |

**Principio rector:** el peor caso debe ser "no hace nada", nunca "operó algo no querido".

## Stack
- Python 3.11, `claude-agent-sdk`, `python-telegram-bot` (async), `httpx` async, `pydantic-settings`.
- Estado: **SQLite** (órdenes pendientes + audit), durable, sin infra extra. Migrable a Supabase después.
- Brief de contexto: script + cron (reusa patrón `refresh-market-context.py`).
- Deploy: Docker, contenedor separado en Hostinger.

## Testing
- Unit (`pytest`): `iol_client` con HTTP mockeado (refresh token, errores, parsing); métricas.
- **Gate**: órdenes bloqueadas sin aprobación, permitidas con aprobación, expiran por timeout, respetan límites duros.
- **Permisos**: Datos y Conocimiento no pueden llamar tools de orden.
- Dry-run: tools de orden stubbeadas → probar conversación sin tocar IOL.
- Integración IOL: lecturas contra sandbox (`api.homo.invertironline.com`); escrituras BETA → paper primero, después orden real mínima.
- E2E manual escalonado: (1) solo lectura → (2) orden mínima real → (3) uso normal.

## Fuera de alcance (Fase 1)
Research/RAG pesado, memoria macro persistente, vigía de oportunidades, gestor proactivo/rebalanceo, generador de estrategias.

## Referencias de SDK (validadas deep-research + Codex, mayo 2026)
- Paquete `claude-agent-sdk` (Python ≥3.10). Entradas: `query()`, `ClaudeSDKClient`, `ClaudeAgentOptions`, `AgentDefinition`, `tool`, `create_sdk_mcp_server`, `HookMatcher`.
- Subagentes con modelo distinto por `AgentDefinition.model`. Delegación de **un solo nivel**.
- Tools custom in-process via `@tool` + `create_sdk_mcp_server`, naming `mcp__<server>__<tool>`.
- Hooks: `PreToolUse`, `PostToolUse`, etc. Permission modes. `setting_sources=[]` para headless.
- Built-in: Read/Write/Edit/Bash/Glob/Grep/WebSearch/WebFetch/AskUserQuestion.
