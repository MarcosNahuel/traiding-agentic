# Auditoria Completa - Trading Agentic System (Codex)
Fecha: 2026-02-16
Repositorio: `D:\OneDrive\GitHub\traiding-agentic`
Alcance: Backend Next.js, Supabase, Binance Testnet, agentes AI, frontend, DevOps y testing.

## 1. Resumen Ejecutivo
Estado general: 2/5 estrellas.

Top 3 issues criticos a corregir de inmediato:
1. Endpoints de trading/cron mutables sin autenticacion/autorizacion.
2. Exposicion de secretos y metadatos sensibles (endpoints diagnosticos + tokens en docs).
3. Build roto por dependencia faltante (`lucide-react`), bloquea despliegue estable.

Top 3 mejoras de mayor impacto:
1. Cerrar superficie publica con auth, RBAC, rate limit y proteccion de cron.
2. Corregir consistencia de datos con idempotencia y locks en ejecucion.
3. Unificar esquema y codigo (`chat_history`, `trading_guides` vs `synthesis_results`, `validation_status`).

Evidencia ejecutada:
- `pnpm lint`: OK.
- `pnpm typecheck`: FAIL (`Cannot find module 'lucide-react'`).
- `pnpm build`: FAIL (`Module not found: lucide-react`).
- `pnpm test:ssrf`: OK (9/9).
- `pnpm test:api`: FAIL (0/11, harness inestable y stack no listo).
- `pnpm audit --prod`: 0 vulnerabilidades reportadas.

## 2. Issues Detallados

[P0] Endpoints criticos mutables sin auth  
Ubicacion: `app/api/trades/execute/route.ts`, `app/api/trades/proposals/route.ts`, `app/api/trades/proposals/[id]/route.ts`, `app/api/market-data/stream/route.ts`, `app/api/pipeline/run/route.ts`, `app/api/sources/route.ts`  
Problema: no hay validacion de identidad/rol en endpoints que mutan estado o ejecutan acciones operativas.  
Riesgo: ejecucion no autorizada de ordenes y manipulacion de flujo.  
Solucion: middleware auth global + RBAC por endpoint + auditoria por actor.  
Prioridad: Critico.

[P0] HITL bypass operativo  
Ubicacion: `app/api/trades/proposals/[id]/route.ts`, `app/api/trades/execute/route.ts`, `app/api/cron/trading-loop/route.ts`, `vercel.json`  
Problema: cualquier cliente puede aprobar/rechazar/ejecutar; cron sin secreto de verificacion.  
Riesgo: se elimina el control humano en practica.  
Solucion: proteger aprobaciones/ejecucion por rol operador y validar secreto en cron.  
Prioridad: Critico.

[P0] Exposicion de secretos y datos sensibles  
Ubicacion: `app/api/diagnostic/route.ts`, `app/api/diagnostic/jwt/route.ts`, `app/api/binance/test/route.ts`, `docs/MISSING-COMPONENTS.md`, `docs/PRODUCTION-TEST-REPORT.md`, `docs/TESTING-SUMMARY-FOR-USER.md`  
Problema: endpoints diagnosticos publicos y secretos/token en documentacion versionada.  
Riesgo: compromiso de cuentas y abuso de infraestructura.  
Solucion: retirar/proteger endpoints de diagnostico, rotar secretos, limpiar historial sensible.  
Prioridad: Critico.

[P0] Build bloqueado por dependencia faltante  
Ubicacion: `app/page.tsx`, `package.json`  
Problema: `lucide-react` se importa pero no esta instalado.  
Riesgo: build/deploy fallan.  
Solucion: agregar dependencia o remover importaciones.  
Prioridad: Critico.

[P0] Race condition en ejecucion de propuestas  
Ubicacion: `lib/trading/executor.ts`  
Problema: chequeo de estado y ejecucion sin lock/idempotency atomica.  
Riesgo: doble ejecucion de la misma propuesta.  
Solucion: transicion atomica (`approved -> executing`) + idempotency key + lock por propuesta.  
Prioridad: Critico.

[P0] Inconsistencia en posiciones parcialmente cerradas  
Ubicacion: `lib/trading/executor.ts`, `lib/trading/risk-manager.ts`, `app/api/portfolio/route.ts`  
Problema: `partially_closed` no se trata consistentemente como posicion abierta.  
Riesgo: riesgo/portfolio incompletos y cierres fallidos.  
Solucion: normalizar consultas y semantica de estados de posicion.  
Prioridad: Critico.

[P1] Tabla `chat_history` usada pero no migrada  
Ubicacion: `app/api/chat/route.ts`, `app/api/chat/history/route.ts`, `supabase/migrations/001_initial_schema.sql`  
Problema: codigo usa `chat_history`, esquema crea `chat_messages`.  
Riesgo: 500 en entornos limpios.  
Solucion: alinear tabla unica y migrar.  
Prioridad: Alto.

[P1] `validation_status` inconsistente en trading loop  
Ubicacion: `lib/agents/trading-agent.ts`, `supabase/migrations/20260216_fix_schema_issues.sql`  
Problema: codigo filtra `approved` mientras schema permite otros estados.  
Riesgo: no se generan señales.  
Solucion: unificar contrato de estados.  
Prioridad: Alto.

[P1] Split-brain de guias (`trading_guides` vs `synthesis_results`)  
Ubicacion: `lib/agents/synthesis-agent.ts`, `app/api/guides/current/route.ts`, `app/api/guides/history/route.ts`, `app/api/pipeline/status/route.ts`  
Problema: dos tablas para un mismo concepto.  
Riesgo: UI inconsistente y datos desalineados.  
Solucion: definir tabla canonica y migrar.  
Prioridad: Alto.

[P1] Enum de `risk_events` incompleto + logging silencioso  
Ubicacion: `lib/trading/executor.ts`, `app/api/trades/proposals/[id]/route.ts`, `lib/trading/risk-manager.ts`, `supabase/migrations/20260216_fix_schema_issues.sql`  
Problema: se emiten eventos no contemplados en constraint y no se controla error en insert.  
Riesgo: perdida de trazabilidad.  
Solucion: corregir nombres, ampliar enum, manejar error de insercion con alerta.  
Prioridad: Alto.

[P1] Orden exchange y persistencia DB no atomicas  
Ubicacion: `lib/trading/executor.ts`  
Problema: el flujo puede marcar ejecutado y fallar al sincronizar posicion.  
Riesgo: desalineacion exchange/DB.  
Solucion: saga/outbox + reconciliacion periodica.  
Prioridad: Alto.

[P1] Sin rate limiting en endpoints costosos  
Ubicacion: `app/api/chat/route.ts`, `app/api/sources/route.ts`, `app/api/guides/synthesize/route.ts`, `app/api/market-data/stream/route.ts`  
Problema: endpoints publicos de alto costo sin cuotas.  
Riesgo: abuso y costos elevados.  
Solucion: rate limit por IP/usuario + cuotas.  
Prioridad: Alto.

[P1] CI no corre en rama activa  
Ubicacion: `.github/workflows/ci.yml`  
Problema: workflow escucha `main`, repo activo en `master`.  
Riesgo: cambios rotos sin validacion.  
Solucion: ajustar triggers a rama real.  
Prioridad: Alto.

[P1] Portfolio API con N+1 y trabajo pesado en request de lectura  
Ubicacion: `app/api/portfolio/route.ts`  
Problema: fetch por posicion + updates dentro de lectura + consultas globales costosas.  
Riesgo: latencia y timeouts.  
Solucion: precomputar agregados y mover updates a job.  
Prioridad: Alto.

[P1] Crecimiento no acotado de `market_data`  
Ubicacion: `lib/services/market-data-stream.ts`, `supabase/migrations/20260216_create_trading_tables.sql`  
Problema: insercion continua sin retention automatizada.  
Riesgo: bloat de DB.  
Solucion: politica de retencion y/o particionado.  
Prioridad: Alto.

[P2] SSRF hardening incompleto  
Ubicacion: `lib/utils/fetcher.ts`, `app/api/sources/route.ts`, `lib/utils/jina-fetcher.ts`  
Problema: bloqueo por hostname sin resolucion DNS; camino Jina evita parte del control.  
Riesgo: bypass parcial SSRF.  
Solucion: validacion DNS/IP real + allowlist por dominio.  
Prioridad: Medio.

[P2] Validacion runtime y tipado inconsistentes  
Ubicacion: multiples handlers (`app/api/*`) y core trading (`lib/trading/*`)  
Problema: uso extendido de `any` y parseo sin esquema unificado.  
Riesgo: errores silenciosos.  
Solucion: normalizar input/output con `zod` y reducir `any` en core.  
Prioridad: Medio.

[P2] Testing fragil (sin framework unificado/coverage)  
Ubicacion: `scripts/test-api-routes.ts`, `package.json`  
Problema: tests ad-hoc sin cobertura formal ni pipeline de regresion robusta.  
Riesgo: baja confiabilidad en cambios.  
Solucion: Vitest/Jest + Playwright + coverage gate en CI.  
Prioridad: Medio.

[P2] README desactualizado respecto a arquitectura actual  
Ubicacion: `README.md`  
Problema: describe estructura vieja (FastAPI/frontend separado) distinta al estado actual.  
Riesgo: onboarding y operacion incorrectos.  
Solucion: actualizar README con stack real y runbook actual.  
Prioridad: Medio.

[P3] UX operativa mejorable en pantallas criticas  
Ubicacion: `app/trades/page.tsx`, `components/ui/AppShell.tsx`  
Problema: `confirm/prompt/alert` y navegacion no optimizada para movil.  
Riesgo: errores humanos y friccion operativa.  
Solucion: modales controlados y nav responsive colapsable.  
Prioridad: Bajo.

## 3. Metricas
- Total de issues: 20
- P0: 6
- P1: 9
- P2: 4
- P3: 1
- Cobertura de tests estimada: 10-20% de flujos criticos.
- Deuda tecnica estimada: 12-18 dias (1 dev full-time) para base production-ready minima.

## 4. Recomendaciones

Quick wins:
1. Rotar secretos expuestos y cerrar endpoints diagnosticos en produccion.
2. Corregir build (`lucide-react`) y activar CI en rama correcta.
3. Implementar auth + RBAC + rate limit en todos los endpoints mutables.
4. Unificar schema/codigo de `chat_history` y `validation_status`.

Refactorings necesarios:
1. Ejecucion de trades con idempotencia, locks y reconciliacion.
2. Unificacion de modelo de guias.
3. Normalizacion completa del lifecycle de posiciones.

Features faltantes para produccion:
1. Autenticacion operativa real y trazabilidad por usuario.
2. Cuotas/rate limiting y circuit breakers.
3. Observabilidad con logs estructurados y tracking de errores.

Herramientas recomendadas:
1. `zod` para todos los contratos de API.
2. Sentry/OpenTelemetry para monitoreo.
3. Redis/Upstash para rate-limit y locks.
4. Vitest + Playwright con coverage gates.

