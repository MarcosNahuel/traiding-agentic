# Auditoria Completa de Funcionamiento, Transacciones y Ganancia

Fecha de auditoria: 2026-02-25  
Repositorio: `D:\OneDrive\GitHub\traiding-agentic`

---

## 1. Objetivo del documento

Este documento responde exactamente a estos puntos solicitados:
- Auditar funcionamiento completo del sistema
- Verificar si las transacciones son correctas
- Verificar si la ganancia reflejada es correcta
- Definir como pasarlo a operacion real con dinero
- Revisar ejecucion, codigo y base de datos

---

## 2. Alcance auditado

Se audito de punta a punta:
- Frontend Next.js (rutas API y paginas operativas)
- Backend Python FastAPI (proposals, execute, portfolio, quant, reconciliation)
- Integracion Binance (testnet/proxy)
- Supabase (schema, estados, consistencia de datos)
- Motor de PnL (realized/unrealized), comisiones y snapshots
- Calidad tecnica de entrega (`build`, `typecheck`, `lint`, `pytest`)

---

## 3. Metodologia y evidencia

### 3.1 Validacion de calidad tecnica

Resultados de comandos:
- `npm run typecheck` -> FAIL
- `npm run build` -> FAIL
- `npm run lint` -> OK
- `python -m pytest -q` en `backend/` -> FAIL

Fallas principales de build/typecheck:
- Import inexistente `runBacktestBenchmark` en [benchmark route](D:/OneDrive/GitHub/traiding-agentic/app/api/quant/backtest/benchmark/route.ts:4)
- Import inexistente `getBacktestPresets` en [presets route](D:/OneDrive/GitHub/traiding-agentic/app/api/quant/backtest/presets/route.ts:3)
- Esos exports no existen en [python backend client](D:/OneDrive/GitHub/traiding-agentic/lib/trading/python-backend.ts:92)

### 3.2 Validacion operativa en datos reales (Supabase)

Consultas directas sobre DB del entorno configurado en `.env`:
- Conteos por estado en `trade_proposals`
- Conteos por estado en `positions`
- Conteos de `risk_events` por tipo
- Recalculo de PnL desde precios/cantidades guardadas
- Validacion de links `entry_proposal_id` / `exit_proposal_id`
- Verificacion de actividad en `reconciliation_runs`

### 3.3 Validacion de formulas de PnL en codigo

Puntos auditados:
- PnL abierto en [executor.py](D:/OneDrive/GitHub/traiding-agentic/backend/app/services/executor.py:141)
- PnL cerrado en [executor.py](D:/OneDrive/GitHub/traiding-agentic/backend/app/services/executor.py:182)
- Recalculo de portfolio en [portfolio.py](D:/OneDrive/GitHub/traiding-agentic/backend/app/services/portfolio.py:22)

---

## 4. Resultado ejecutivo

Estado actual: **NO apto para pasar a dinero real**.

Motivos ejecutivos:
1. Operacion de ejecucion degradada: errores masivos de ordenes
2. Build/typecheck rotos (no desplegable con calidad de produccion)
3. Inconsistencias de esquema vs runtime en estados/eventos
4. Riesgos de seguridad y de control operativo

Respuesta concreta:
- Transacciones hoy: **no correctas operativamente** (mucha tasa de error)
- Ganancia mostrada: **formula consistente en los pocos trades historicos cerrados**, pero no representa un sistema sano ni escalable

---

## 5. Verificacion de transacciones

### 5.1 Datos observados en base

Conteos medidos:
- `trade_proposals` total: **42721**
- `positions` total: **3** (2 open, 1 closed)
- `risk_events` total: **42726**
- `reconciliation_runs` total: **8946**

Distribucion de proposals:
- `executed`: **4**
- `error`: **42708**
- `rejected`: **9**
- `dead_letter`: **0**
- `approved`: **0**
- `validated`: **0**
- `draft`: **0**

Ultimas 24 horas:
- `trade_proposals.error`: **7223**
- `trade_proposals.executed`: **0**
- `risk_events.execution_error`: **7232**
- `risk_events.order_executed`: **0**

Error dominante:
- `400 Bad Request` al endpoint del proxy Binance para ordenes `SELL` de `ETHUSDT`.

### 5.2 Conclusion de transacciones

El pipeline transaccional **no esta sano**.  
Aunque hay reconciliacion frecuente y sin divergencias recientes, eso no compensa que la ejecucion de propuestas esta fallando en volumen muy alto.

---

## 6. Verificacion de ganancia (PnL)

### 6.1 Recalculo sobre posiciones existentes

Se recalculo en DB:
- `open_unrealized_mismatches = 0`
- `closed_realized_mismatches = 0`
- `closed_realized_pct_mismatches = 0`

Interpretacion:
- En el set actual (muy pequeno), los valores guardados coinciden con la formula implementada.

### 6.2 Resultado observado de closed trades

Closed trades actuales:
- `closed = 1`
- `totalRealizedPnl = 0.98129`
- `avgReturnPct = 1.4441%`

### 6.3 Limite de validez

Este PnL no es estadisticamente suficiente para afirmar que la estrategia o el bot ganan de forma robusta porque:
1. Muestra de trades cerrados muy baja
2. Ultima ejecucion exitosa: 2026-02-17
3. Errores de ejecucion masivos en periodo reciente

### 6.4 Riesgos de calculo detectados en codigo

#### Riesgo A - Orden de calculo en cierre
- `realized_pnl` se calcula antes de clamp de cantidad cuando `exit_qty > entry_qty`:
  - [executor.py](D:/OneDrive/GitHub/traiding-agentic/backend/app/services/executor.py:182)
  - [executor.py](D:/OneDrive/GitHub/traiding-agentic/backend/app/services/executor.py:185)

Impacto: PnL potencialmente incorrecto en ese edge-case.

#### Riesgo B - Cierre parcial de posiciones
- Se busca posicion solo con `status=open`:
  - [executor.py](D:/OneDrive/GitHub/traiding-agentic/backend/app/services/executor.py:172)
- Si pasa a `partially_closed`, puede quedar fuera del flujo normal de cierre y calculo:
  - [executor.py](D:/OneDrive/GitHub/traiding-agentic/backend/app/services/executor.py:190)
  - [portfolio.py](D:/OneDrive/GitHub/traiding-agentic/backend/app/services/portfolio.py:22)

Impacto: riesgos de posicion "atascada" o metrica inconsistente.

#### Riesgo C - Comisiones multi-asset
- Modelo resta comision como valor directo de PnL sin conversion por asset:
  - [executor.py](D:/OneDrive/GitHub/traiding-agentic/backend/app/services/executor.py:141)
  - [portfolio.py](D:/OneDrive/GitHub/traiding-agentic/backend/app/services/portfolio.py:35)

Impacto: en real, con comisiones no cero y assets mixtos, el net PnL puede desviarse si no se normaliza a USDT.

---

## 7. Auditoria de ejecucion y arquitectura operativa

### 7.1 Doble motor de ejecucion

Hay dos caminos:
- Python backend (cuando `PYTHON_BACKEND_URL` esta activo)
- Fallback Next.js local

Esto incrementa riesgo de drift funcional (reglas distintas en rutas distintas).

### 7.2 Loop de ejecucion

Loop Python:
- se inicia al levantar backend en [main.py](D:/OneDrive/GitHub/traiding-agentic/backend/app/main.py:49)
- corre cada 60s con quant + execute + portfolio + reconciliation en [trading_loop.py](D:/OneDrive/GitHub/traiding-agentic/backend/app/services/trading_loop.py:20)

Cron Next:
- cada 5 minutos en [vercel.json](D:/OneDrive/GitHub/traiding-agentic/vercel.json:32)
- llama trading agent y execute en [cron route](D:/OneDrive/GitHub/traiding-agentic/app/api/cron/trading-loop/route.ts:43)

Riesgo: doble orquestacion y potencial duplicidad/noise de proposals si no se separan roles por entorno.

---

## 8. Auditoria de base de datos y consistencia de schema

### 8.1 Estado de proposals no alineado al 100%

Schema original de `trade_proposals.status`:
- [create migration](D:/OneDrive/GitHub/traiding-agentic/supabase/migrations/20260216_create_trading_tables.sql:27)
- Permite: `draft, validated, approved, rejected, executed, error`

Codigo usa estados extra:
- `dead_letter` en [executor.py](D:/OneDrive/GitHub/traiding-agentic/backend/app/services/executor.py:103)
- `cancelled` en [dead_letter.py](D:/OneDrive/GitHub/traiding-agentic/backend/app/routers/dead_letter.py:61)

Riesgo: si DB no tiene constraint actualizado, pueden fallar updates.

### 8.2 Event types de risk_events con riesgo de overwrite

`20260216_fix_schema_issues.sql` incluye:
- `execution_blocked`, `proposal_cancelled`, `position_opened`, `risk_warning`
  - [lineas](D:/OneDrive/GitHub/traiding-agentic/supabase/migrations/20260216_fix_schema_issues.sql:31)

`20260217_quant_engine_tables.sql` redefine check sin varios de esos tipos:
- [lineas](D:/OneDrive/GitHub/traiding-agentic/supabase/migrations/20260217_quant_engine_tables.sql:218)

Riesgo: inserciones de eventos pueden romper segun orden de migracion aplicado.

### 8.3 validation_status inconsistente entre componentes

Valores permitidos segun migracion:
- `pending, validated, rejected, needs_review`
  - [fix schema](D:/OneDrive/GitHub/traiding-agentic/supabase/migrations/20260216_fix_schema_issues.sql:98)

Trading agent filtra `approved`:
- [trading-agent.ts](D:/OneDrive/GitHub/traiding-agentic/lib/agents/trading-agent.ts:242)

Otro endpoint usa `validated`:
- [pipeline/status route](D:/OneDrive/GitHub/traiding-agentic/app/api/pipeline/status/route.ts:53)

Riesgo: estrategias no entran en evaluacion aunque existan.

---

## 9. Seguridad y hardening

### 9.1 Secreto hardcodeado

Se detecto API key hardcodeada en:
- [generate_maxi_pdf.py](D:/OneDrive/GitHub/traiding-agentic/docs/02-2026/generate_maxi_pdf.py:14)

Accion obligatoria:
1. Rotar la clave en origen
2. Eliminarla del repo
3. Moverla a variable de entorno segura

### 9.2 Auth backend puede quedar abierta

Si `BACKEND_SECRET` esta vacio, middleware deja pasar:
- [main.py](D:/OneDrive/GitHub/traiding-agentic/backend/app/main.py:24)

Accion obligatoria:
- Hacer secreto obligatorio en produccion y fallar startup si no existe.

---

## 10. Como pasar a dinero real (plan realista)

### Fase 0 - Condiciones minimas (bloqueante)

1. Arreglar ejecucion de ordenes (`400 Bad Request`) y demostrar estabilidad.
2. Dejar `typecheck/build/lint/tests` en verde.
3. Unificar motor de ejecucion para evitar drift.
4. Corregir:
   - PnL clamp order
   - posicion parcial
   - comisiones por asset normalizadas
5. Cerrar brechas de schema:
   - estados de proposal
   - event_type risk_events
   - validation_status coherente
6. Hardening de seguridad:
   - sin secretos en codigo
   - backend auth obligatoria
   - rotacion de claves

### Fase 1 - Shadow mode (sin dinero real)

Objetivo:
- Generar senales y decisiones en tiempo real, pero sin ejecutar real.
- Comparar expected fills vs mercado.

Duracion minima:
- 2 semanas de estabilidad.

KPIs minimos:
- Error de ejecucion simulada < 1%
- Reconciliacion sin divergencias criticas
- Sin dead letters pendientes

### Fase 2 - Capital minimo real (risk capped)

Condiciones de arranque:
- Position size minimo (micro-notional)
- Limite de perdida diaria hard
- Kill switch externo y manual

KPI de continuidad:
- Win rate y PF positivos en ventana movil
- Drawdown controlado bajo umbral acordado
- Alertas de riesgo sin acumulacion no resuelta

### Fase 3 - Escalado gradual

Solo si fases 0-2 son estables:
- Incremento escalonado de tamano
- Revisiones semanales obligatorias
- Gate de rollback automatico ante desviaciones

---

## 11. Checklist de go-live (dinero real)

Todos deben ser SI:
- [ ] `npm run build` OK
- [ ] `npm run typecheck` OK
- [ ] `python -m pytest -q` OK
- [ ] Error rate de ejecucion <1% por 14 dias
- [ ] Cero divergencias criticas de reconciliacion por 14 dias
- [ ] Cero dead letters pendientes
- [ ] Comisiones normalizadas y auditables en USDT
- [ ] Auditoria de seguridad cerrada
- [ ] Estrategias con estado de validacion coherente
- [ ] Runbook de incidentes y rollback probado

Si uno falla, no pasar a real.

---

## 12. Respuesta final a tus 3 preguntas

### 12.1 "Las transacciones que me da son correctas?"

Hoy, **no** a nivel operativo general.  
Hay un volumen muy alto de propuestas en error y casi nulas ejecuciones recientes.

### 12.2 "La ganancia que refleja esta bien?"

En los pocos registros cerrados actuales, **la formula coincide** con lo guardado.  
Pero esa ganancia **no es un indicador confiable de rendimiento real** del sistema por falta de volumen sano y por fallas masivas de ejecucion.

### 12.3 "Como pasarlo a realidad / invertir plata real?"

No pasar ahora.  
Primero cerrar bloqueantes de ejecucion, calidad tecnica, consistencia de datos y seguridad.  
Luego shadow mode, luego capital minimo, y solo despues escalado gradual con KPIs.

---

## 13. Estado de esta auditoria

Auditoria completada con evidencia tecnica de:
- Codigo
- Ejecucion
- Base de datos
- Criterios de produccion real

Resultado: sistema con componentes valiosos, pero todavia en estado pre-produccion para dinero real.
