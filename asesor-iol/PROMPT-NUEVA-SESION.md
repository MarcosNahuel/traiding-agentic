# Prompt para retomar en sesión limpia

Copiá y pegá esto como primer mensaje en una sesión nueva de Claude Code (en el repo
`traiding-agentic`):

---

Estoy continuando el **Agente Asesor de Inversiones IOL** (carpeta `asesor-iol/`, branch
`main`). Es un agente multi-agente sobre el Claude Agent SDK + Telegram, modo asesor
human-in-the-loop, broker InvertirOnline (IOL), perfil conservador USD.

**Antes de tocar nada, cargá contexto en este orden:**
1. Leé la spec de cierre: `docs/superpowers/specs/2026-05-31-agente-asesor-iol-cierre.md`
   (estado actual + plan + criterios de aceptación). Y la de diseño:
   `docs/superpowers/specs/2026-05-30-agente-asesor-iol-design.md`.
2. Revisá las memorias del proyecto: `project_asesor_iol_impl_2026-05-30`,
   `project_iol_api_research_2026-05-30`, `project_broker_alternatives_2026-05-30`.
3. Explorá el código en `asesor-iol/src/asesor_iol/` (agents, iol, security, telegram).
4. Corré `cd asesor-iol && pytest -q` para confirmar los 13 tests verdes.

**Objetivo de esta sesión: llevarlo al AGENTE FINAL.** En concreto:

A) **Integrar el MCP oficial de IOL.** Cloná/corré `fernandezpablo85/mcpiol` (o
   `pgallar/iol-mcp`), **listá TODAS las tools que expone** (portafolio, saldos,
   comprar/vender, FCI, cotizaciones, option chains/greeks, vol implícita, stops) y
   conectalo como MCP externo en `ClaudeAgentOptions(mcp_servers=...)`. Recomendación:
   mantener el cliente propio para las ÓRDENES (auditable, detrás del gate) y sumar el
   MCP de IOL para LECTURA/análisis extendido del subagente de datos.
   ⚠️ SEGURIDAD: si exponés cualquier tool de orden del MCP, sumá su nombre
   `mcp__<server>__<tool>` a `ORDER_TOOLS` en `security/gate.py`. Ninguna escritura
   puede saltarse el gate de confirmación.

B) **Analizá todas las funcionalidades** (propias + MCP) y mapeá qué subagente usa cada
   una. Cobertura objetivo: money market USD, CEDEARs, bonos, ON, MEP, opciones.

C) **Completá el agente de conocimiento**: enriquecé el brief
   (`context/refresh_market.py`) con fuentes reales (inflación INDEC, dólar MEP, tasas
   BCRA, riesgo país), con citas, y dejá un cron.

D) **Hardening + tests** de las nuevas tools (gate, límites, audit). Mantené la
   disciplina: ante la duda el agente NO opera; el peor caso es "no hace nada".

**Estado / bloqueantes a tener presente:**
- La **API de IOL puede no estar activada todavía** (daba `401`). Verificá con
  `cd asesor-iol && python scripts/smoke_iol.py`. Si da 401, el dueño debe activarla
  (Mi Cuenta › Personalización › APIs). Mientras tanto, trabajá contra el sandbox
  `api.homo.invertironline.com` o con mocks.
- El bot quizás esté corriendo en background de la sesión anterior (@Traiding77bot). Un
  solo poller por bot (si no, Telegram 409). Verificá/terminá antes de relanzar.
- `.env` ya existe (gitignored) con Telegram + OAuth Max token. Infisical necesita
  re-login (`infisical login`) para guardar secretos; workspaceId
  `928d1115-5299-4fc6-a4a0-f6a225ea1aa6`.
- Windows: usá `PYTHONIOENCODING=utf-8`. Workflow git: branches `feat/`, `--no-ff`, NO
  pushear sin OK.

Usá brainstorming si hay decisiones de diseño abiertas, y escribí/actualizá la spec a
medida que cierres cada parte. Cuando termines, dejá los criterios de aceptación de la
sección 5 de la spec de cierre tildados y los tests verdes.

---
