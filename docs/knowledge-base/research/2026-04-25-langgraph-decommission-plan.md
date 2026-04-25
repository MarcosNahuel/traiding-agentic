---
date: 2026-04-25
type: decommission-plan
status: ready
related_spec: docs/superpowers/specs/2026-04-24-daily-strategist-agent-design.md
phase: 0.6
---

# LangGraph daily_analyst — Decommission Plan

## Status

LangGraph daily_analyst (`backend/app/services/daily_analyst/`) sigue activo.
Plan de pausa graceful durante el rollout del Claude Strategist Agent.

## Timeline

| Día | Acción | Quién |
|---|---|---|
| Día -7 a Día 0 | Strategist en dry-run en local. LangGraph sigue. | Auto + manual |
| Día 0 (= Strategist 7 días OK) | Set `LANGGRAPH_DAILY_ENABLED=false` en Dokploy env. Redeploy. | Manual usuario |
| Día +1 a +14 | Verificar que `llm_trading_configs` recibe rows solo de `proposed_by='strategist'`. | Manual |
| Día +14 | Si Strategist sigue OK, eliminar `backend/app/services/daily_analyst/` entero. Limpieza imports. | Manual |
| Día +14 | Tabla `llm_audit_reports` queda como histórico read-only. NO se borra. | — |

## Rollback

Si Strategist falla en cualquier momento entre Día 0 y Día +14:
1. Set `LANGGRAPH_DAILY_ENABLED=true` en Dokploy env.
2. Redeploy backend.
3. LangGraph retoma operación normal.

## Riesgo de no-fallback post Día +14

Después de eliminar el código del LangGraph no hay rollback automático.
Si Strategist falla, backend cae a defaults de `config.py` (comportamiento
existente cuando `llm_trading_configs` no tiene `status=active`).

Watchdog Vercel Cron alertará vía Telegram si Strategist >36h sin run.

## Métricas de éxito Strategist (gate para Día 0)

- 7 días seguidos generando eval markdown sin fallar.
- Cada run produce: eval + pending_approval row + Telegram + heartbeat.
- Costo medio <$1.50/día.
- Cero modificaciones a `status=active` por el agente.
- Aprobaciones manuales registradas con razón.
