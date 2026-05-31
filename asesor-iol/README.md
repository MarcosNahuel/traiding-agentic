# Asesor IOL — Agente Asesor de Inversiones

Agente asesor de inversiones sobre **InvertirOnline (IOL)** en modo **asesor con
human-in-the-loop**: la IA analiza y propone, **vos confirmás cada orden por Telegram**.
Perfil: conservador en USD, fondeo local (MEP). Proyecto separado del bot cripto.

Diseño completo: [`docs/superpowers/specs/2026-05-30-agente-asesor-iol-design.md`](../docs/superpowers/specs/2026-05-30-agente-asesor-iol-design.md)

## Arquitectura (Fase 1 — Base + Conversacional)

```
Telegram ◀▶ Orquestador (Opus) ──┬─▶ Agente Datos (Haiku/Sonnet)  · tools IOL, métricas, SOLO hechos
                                 └─▶ Agente Conocimiento (Sonnet) · WebSearch + brief, CON citas
                         │
                         ▼
            Cliente IOL (OAuth2) ── 🔒 gate de confirmación ── IOL API
```

- **Orquestador**: decide y conversa.
- **Datos**: trae hechos/métricas de tu cuenta. Sin permiso para operar.
- **Conocimiento**: contexto macro con fuentes. Sin acceso a tu cuenta.
- **Gate**: toda orden pasa por confirmación humana + límites duros. Ante la duda, no opera.

## Seguridad

- Mínimo privilegio por agente (los subagentes **no pueden** mandar órdenes).
- Gate de confirmación obligatorio (`can_use_tool`) en `place_buy/place_sell`.
- Límites duros: monto máx/orden, tope diario, símbolos permitidos.
- Audit log append-only (SQLite). Allowlist de un solo chat de Telegram.
- Secretos en `.env` (nunca al git). `setting_sources=[]` (headless).

## Setup

```bash
cd asesor-iol
cp .env.example .env          # completá credenciales IOL, Anthropic, Telegram
pip install -e ".[dev]"
```

Conseguí tu `TELEGRAM_ALLOWED_CHAT_ID` con @userinfobot. Activá la API en IOL
(Mi Cuenta > Personalización > APIs). Para probar lecturas sin riesgo, usá el
sandbox: `IOL_API_BASE=https://api.homo.invertironline.com`.

## Correr

```bash
# Brief de contexto (cron recomendado, ej. cada 6h)
python -m asesor_iol.context.refresh_market

# Bot
asesor-iol            # o: python -m asesor_iol.main

# Docker (VPS)
docker compose up -d --build
```

## Tests

```bash
pytest -q
```

Los tests de `metrics`, `store`, `gate` e `iol_client` corren sin red ni SDK.
Validan la lógica de seguridad (límites, aprobación, expiración) y el parsing/refresh.

## Rollout escalonado (recomendado)

1. **Solo lectura**: apuntá a sandbox, preguntale por tu cartera y cotizaciones.
2. **Una orden mínima real**: confirmá una compra chica y verificá en IOL.
3. **Uso normal**: recién cuando confíes en el flujo.

## Estado

Fase 1 (Base + Conversacional). Pendiente al desplegar: verificar paths exactos de
endpoints IOL contra el Swagger vivo, y firmas del `claude-agent-sdk` instalado
(`can_use_tool`, hooks) — están marcadas con NOTA en el código.

Capas siguientes: vigía de oportunidades → gestor proactivo → RAG/memoria macro.
