# Agente Asesor IOL — Spec de Cierre (llevar al agente final)

**Fecha:** 2026-05-31
**Branch:** `main` (mergeado) · **Proyecto:** `asesor-iol/`
**Spec base (diseño Fase 1):** `docs/superpowers/specs/2026-05-30-agente-asesor-iol-design.md`

Este documento es **autosuficiente** para retomar en una sesión limpia. Describe qué
está hecho, qué funciona, qué falta, y el plan para dejar el **agente final**.

---

## 1. Resumen del proyecto

Agente asesor de inversiones **conservador USD** sobre **InvertirOnline (IOL)**, modo
**asesor con human-in-the-loop** (la IA propone, el humano confirma cada orden por
Telegram). Multi-agente con Claude Agent SDK (Opus orquestador + subagentes datos y
conocimiento). Proyecto **separado** del bot cripto. Perfil: US$5–20k, plata en
Argentina (fondeo MEP). Decisiones en memorias `project_iol_api_research_2026-05-30`,
`project_broker_alternatives_2026-05-30`, `project_asesor_iol_impl_2026-05-30`.

## 2. Estado actual (qué está hecho y funciona) ✅

- **Código Fase 1 completo** en `asesor-iol/` (ver árbol en README). Arquitectura:
  orquestador (Opus) + subagente `datos` (Opus low-effort, solo lectura/métricas) +
  subagente `conocimiento` (Sonnet, WebSearch + brief, con citas).
- **Cliente IOL propio** async (`iol/client.py`): OAuth2 password grant + refresh de
  token (15 min). Lecturas (portafolio, estado de cuenta, cotización) y escrituras
  (comprar/vender). Expuesto como MCP server in-process (`agents/tools.py`).
- **Seguridad**: gate de confirmación (`security/gate.py`) via `can_use_tool` —
  límites duros (monto/orden, tope diario, símbolos) + aprobación por botón Telegram
  con expiración. Subagentes SIN tools de orden. Audit log SQLite (`state/store.py`).
- **Telegram** (`telegram/bot.py`): long-polling, allowlist de 1 chat, botones
  Confirmar/Cancelar.
- **SDK validado contra la versión instalada**: el `Advisor` construye OK; el gate
  requiere **streaming** → se usa `ClaudeSDKClient` con conexión persistente (fix en
  commit `e27151c`).
- **Bot LIVE y conectado**: @Traiding77bot. `.env` creado (gitignored) con: token de
  Telegram, `TELEGRAM_ALLOWED_CHAT_ID=7825027911`, `CLAUDE_CODE_OAUTH_TOKEN` (plan Max).
- **Tests**: 13 passing (`pytest -q`) — metrics, store, gate (límites/aprobación/
  expiración), iol_client (auth/refresh/no-retry de órdenes).
- **Credenciales IOL válidas** (IOL emite token), pero ver bloqueante abajo.

## 3. Bloqueantes / pendientes conocidos 🚧

1. **API de IOL NO activada** (BLOQUEANTE para datos reales). Las consultas dan
   `401 Authorization denied`. El usuario debe activarla: micuenta.invertironline.com →
   Mi Cuenta › Personalización › APIs (aceptar T&C) + consulta Tipo `Mi cuenta`, Razón
   `Api`. La aprueba IOL (no instantáneo). Verificar con `python scripts/smoke_iol.py`.
2. **Infisical**: el token de la máquina está vencido ("access token is malformed").
   Re-login (`infisical login`) para poder guardar secretos. workspaceId
   `928d1115-5299-4fc6-a4a0-f6a225ea1aa6`.
3. **Paths de endpoints IOL** (`/api/v2/...`) y el shape exacto de los JSON deben
   verificarse contra el Swagger vivo y datos reales una vez activada la API.
4. **Seguridad**: credenciales y tokens se pegaron en chat en sesiones previas →
   **rotar** password de IOL, token de Telegram y OAuth token cuando esté estable.

## 4. Plan para el AGENTE FINAL

### 4.1 Integrar el MCP de IOL (pedido explícito)
- El SDK soporta MCP externos via `ClaudeAgentOptions(mcp_servers={...})` (stdio/HTTP).
- Candidatos: `fernandezpablo85/mcpiol` (Python/uv) o `pgallar/iol-mcp`. Clonar, correr,
  y **listar todas las tools que expone** (balances, portafolio, comprar/vender, FCI,
  cotizaciones, option chains/greeks, volatilidad implícita, stop loss/take profit).
- **Decisión a tomar**: ¿cliente propio (control/auditable, ya hecho) vs MCP oficial
  (más amplitud)? Opción recomendada: **mantener el cliente propio para las órdenes**
  (auditable, detrás del gate) y **sumar el MCP de IOL como fuente de lectura/análisis
  extendido** (greeks, option chains) para el subagente de datos. Conectarlo como MCP
  externo y mapear sus tools.
- **Crítico de seguridad**: si se exponen tools de orden del MCP, agregar sus nombres
  (`mcp__<server>__<tool>`) al set `ORDER_TOOLS` en `security/gate.py` para que pasen
  por el gate. NINGUNA tool de escritura puede saltarse la confirmación.

### 4.2 Analizar TODAS las funcionalidades
- Enumerar tools (propias + MCP) y decidir qué subagente usa cada una (datos = lectura/
  métricas; orquestador = órdenes detrás del gate; conocimiento = sin IOL).
- Mapear cobertura: money market USD, CEDEARs, bonos, ON, MEP, opciones.

### 4.3 Completar el agente de conocimiento
- Enriquecer el brief (`context/refresh_market.py`) con fuentes reales (INDEC inflación,
  dólar MEP, BCRA tasas, riesgo país) y dejar cron. Mantener disciplina de citas.

### 4.4 Validación con IOL activada
- Smoke test de lectura → métricas reales → **una orden mínima real** con confirmación
  → recién ahí uso normal. Probar primero contra sandbox `api.homo.invertironline.com`.

### 4.5 Deploy productivo
- Docker en VPS Hostinger (contenedor separado). Secretos en Infisical (`infisical run`).
- Cron del brief. Logs/healthcheck. Reiniciar bot ante caída (`restart: unless-stopped`).

### 4.6 Hardening + tests
- Tests del gate sobre las tools de orden del MCP (naming nuevo). Revisar manejo de
  errores end-to-end. Considerar pasar el diff por `/jury` antes de confiar plata real.

## 5. Criterios de aceptación del agente final
- [ ] Lee cartera/cotizaciones/métricas reales de IOL (API activada).
- [ ] Responde conversacional con contexto macro **citado**.
- [ ] Propone orden → confirmación por Telegram → ejecuta (gate, límites, audit).
- [ ] MCP de IOL integrado y sus tools mapeadas (órdenes detrás del gate).
- [ ] Desplegado en VPS, secretos en Infisical, brief por cron.
- [ ] Tests verdes + rollout escalonado (lectura → orden mínima → normal).
- [ ] Secretos rotados.

## 6. Comandos útiles
```bash
cd asesor-iol
pytest -q                                   # 13 tests
python scripts/smoke_iol.py                 # valida auth/lectura IOL (necesita API activada)
PYTHONPATH=src python -m asesor_iol.main     # corre el bot (long-polling)
python -m asesor_iol.context.refresh_market  # regenera el brief
```
Notas: en Windows usar `PYTHONIOENCODING=utf-8`. El bot puede estar corriendo en
background de la sesión anterior — verificar/terminar antes de relanzar (un solo
poller por bot, si no Telegram da 409).
