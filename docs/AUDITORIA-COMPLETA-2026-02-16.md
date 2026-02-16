# Auditoría Completa del Repositorio

Fecha: 2026-02-16  
Repositorio: `D:\OneDrive\GitHub\traiding-agentic`

## 1) Alcance

Se auditó:

- Documentación de plan y estado en `docs/` y `CODEX/`
- Implementación real del código (`app/`, `lib/`, `supabase/`, `backend/`)
- Estado de build, typecheck, lint y pruebas
- Coherencia entre plan declarado y componentes implementados

## 2) Fuentes revisadas

Documentos principales:

- `README.md`
- `CODEX/README.md`
- `CODEX/13-codex-ultima-version-2026-02-15.md`
- `CODEX/10-cambios-sugeridos-finales.md`
- `docs/FINAL-STATUS.md`
- `docs/MISSING-COMPONENTS.md`
- `docs/TRADING-SYSTEM.md`
- `docs/plans/fase-0-foundation.md`
- `docs/plans/fase-1-research-agents.md`
- `docs/plans/fase-2-trading-core.md`
- `docs/plans/fase-3-exchange-hardening.md`
- `docs/02-2026/PLAN-TECNICO-MVP-COMPLETO.md`

## 3) Resumen ejecutivo

Estado general: **parcialmente funcional**, pero **no listo para producción**.

Bloqueantes principales detectados:

1. `pnpm build` falla (resolución de `ws`).
2. `pnpm typecheck` falla (errores de typing en API y trading executor).
3. CI puede fallar por lockfile desalineado (`--frozen-lockfile`).
4. Brecha relevante entre plan (fases 1/2/3) y endpoints/páginas realmente implementados.
5. Inconsistencias de esquema de BD vs código (`risk_events.event_type`, `synthesis_results`, `validation_status`).

Conclusión: hay piezas que funcionan (pipeline de agentes, lint, verificaciones base), pero faltan componentes críticos y correcciones para cumplir el plan MVP completo.

## 4) Estado contra el plan

### Fase 0 - Foundation

Estado: **Parcialmente cumplida**

- OK: estructura Next + Supabase + scripts de verificación base.
- Pendiente: alineación lockfile/dependencias para CI reproducible.
- Pendiente: documentación de variables de entorno completa (trading + Supabase anon key pública).

### Fase 1 - Research Agents

Estado: **Parcial**

- OK: tests de Source/Reader/Synthesis/Chat Agent mayormente pasan.
- Faltan endpoints del plan en `app/api/`:
  - `app/api/chat/route.ts`
  - `app/api/chat/history/route.ts`
  - `app/api/pipeline/run/route.ts`
  - `app/api/pipeline/status/route.ts`
  - `app/api/guides/current/route.ts`
  - `app/api/guides/history/route.ts`
  - `app/api/guides/system-prompt/route.ts`
- Incompleto: chunking + embedding no integrado de punta a punta en la ruta de lectura/extracción.

### Fase 2 - Trading Core

Estado: **Incompleta**

- Existen bases de propuesta/ejecución/riesgo.
- Faltan piezas clave del plan:
  - páginas `/approvals`, `/operations`, `/simulator`, `/history`
  - APIs `/api/orders`, `/api/reconciliation/*`, `/api/risk/breakers*`, `/api/operations/*`, `/api/simulator/*`
  - tablas y trazabilidad completa (`execution_orders`, `reconciliation_runs`, `risk_breaker_events`, `correlation_id`, `client_order_id` end-to-end)

### Fase 3 - Exchange Hardening

Estado: **No cumplida**

- No hay verificación integral de reconciliación operativa y circuit breakers completos.
- No se pudo validar flujo Docker backend en esta auditoría (daemon no disponible).

## 5) Resultado de verificaciones y pruebas

Comandos ejecutados y estado:

- `pnpm lint` -> **OK**
- `pnpm typecheck` -> **FAIL**
- `pnpm build` -> **FAIL**
- `pnpm verify` -> **OK**
- `pnpm test:chunking` -> **OK**
- `pnpm test:ssrf` -> **OK**
- `pnpm test:source-agent` -> **OK**
- `pnpm test:reader-agent` -> **OK**
- `pnpm test:reader-quality` -> **OK con warning funcional (80%, 4/5)**
- `pnpm test:synthesis-agent` -> **OK**
- `pnpm test:chat-agent` -> **OK**
- `pnpm test:quality` -> **OK**
- `pnpm test:auto-synthesis` -> **OK**
- `pnpm test:api` -> **10/11 (1 falla por expectativa desactualizada)**
- `pnpm format:check` -> **FAIL (47 archivos)**

Backend Python:

- `python -m pytest -q` (en `backend`) -> **sin tests ejecutados**
- `python -m compileall backend/app` -> **OK**
- Import app backend en runtime -> **FAIL local por dependencia faltante (`sqlmodel`)**

## 6) Hallazgos críticos (prioridad alta)

1. Build roto por dependencia no resuelta

- Archivo relacionado: `lib/services/market-data-stream.ts`
- Síntoma: `Can't resolve 'ws'` en build.
- Riesgo: no se puede empaquetar/desplegar de forma confiable.

2. Typecheck roto por incompatibilidad de tipos y bug de scope

- Archivos:
  - `app/api/trades/proposals/[id]/route.ts` (firma de params)
  - `lib/trading/executor.ts` (uso de `proposal` fuera de scope en `catch`)
- Riesgo: errores de compilación y potenciales fallos en runtime.

3. Lockfile desalineado con `package.json`

- Archivos:
  - `package.json`
  - `pnpm-lock.yaml`
  - `.github/workflows/ci.yml`
- Síntoma: `pnpm install --frozen-lockfile` falla.
- Riesgo: CI inestable/bloqueada.

4. Desalineación fuerte plan vs implementación

- Falta de endpoints y páginas clave de fases 1-3.
- Riesgo: el sistema no cubre el flujo operativo prometido por el plan.

## 7) Hallazgos importantes (prioridad media)

1. Esquema de riesgo vs eventos emitidos inconsistente

- Migración de `risk_events` restringe `event_type` a lista cerrada.
- Código emite tipos adicionales (`proposal_rejected`, `risk_warning`, `order_executed`, etc.).
- Riesgo: inserciones fallidas y pérdida de auditoría operativa.

2. Auto-synthesis usa tabla no presente

- Archivo: `lib/services/auto-synthesis.ts`
- Tabla esperada: `synthesis_results` (no detectada en migraciones).
- Riesgo: fallos silenciosos o rutas funcionales incompletas.

3. Estrategias con filtro de columna posiblemente inexistente

- Archivo: `lib/agents/trading-agent.ts`
- Filtro por `validation_status` en `strategies_found`.
- Riesgo: el agente de trading puede no encontrar estrategias válidas aunque existan.

4. Inconsistencia de embeddings/dimensionalidad

- Se observó flujo de embedding truncando manualmente, sin configuración consistente centralizada.
- Riesgo: degradación de calidad semántica y consultas vectoriales inestables.

## 8) Hallazgos de documentación/operación

1. Drift de documentación con estructura real

- `README.md` y `docker-compose.yml` asumen `./frontend` (directorio no presente).

2. `.env.example` incompleto

- Faltan variables relevantes de Binance testnet y claves públicas esperadas por cliente web.

3. Estado declarado optimista en documentación

- `docs/FINAL-STATUS.md` marca estado muy superior al observado por build/typecheck y brecha de componentes.

## 9) Qué sí está funcionando hoy

- Lint del proyecto.
- Verificaciones base (`pnpm verify`).
- Gran parte de pruebas de agentes y utilidades.
- Parte relevante del pipeline de investigación y piezas de trading en modo parcial.

## 10) Qué reparar primero (plan recomendado)

### P0 (bloqueante, inmediato)

1. Alinear `pnpm-lock.yaml` con `package.json` y validar `pnpm install --frozen-lockfile`.
2. Corregir `typecheck`:
   - firma de params en `app/api/trades/proposals/[id]/route.ts`
   - scope de `proposal` en `lib/trading/executor.ts`
3. Resolver build de `ws` en `lib/services/market-data-stream.ts` y confirmar `pnpm build`.
4. Corregir test API roto (`pending` vs `completed`) para dejar suite determinística.

### P1 (cumplimiento mínimo de plan MVP)

1. Implementar endpoints faltantes de Fase 1.
2. Completar APIs/páginas críticas de Fase 2 (orders/operations/history/simulator).
3. Alinear esquema y código de `risk_events` + tablas faltantes (`synthesis_results`, etc.).
4. Integrar chunking+embedding end-to-end en pipeline real de lectura.

### P2 (hardening)

1. Normalizar embeddings (dimensión, proveedor y validaciones).
2. Completar reconciliación/circuit breakers con evidencias de pruebas.
3. Agregar tests backend Python reales (actualmente 0 tests).
4. Actualizar documentación para reflejar estado real y procedimientos de despliegue.

## 11) Criterio de “funcionando” para cierre de auditoría

Para considerar el repositorio operativo y alineado al plan:

- `pnpm install --frozen-lockfile` OK
- `pnpm lint`, `pnpm typecheck`, `pnpm build`, `pnpm test:api` en verde
- Endpoints y páginas mínimas de Fase 1-2 implementadas
- Esquema DB y código sin divergencias funcionales
- Evidencia de pruebas backend Python y flujo operacional documentado

## 12) Estado final de esta auditoría

- Auditoría documental + técnica ejecutada.
- Pruebas principales corridas.
- Brechas y reparaciones priorizadas identificadas.
- **No se aplicaron fixes de código en esta etapa** (solo informe).
