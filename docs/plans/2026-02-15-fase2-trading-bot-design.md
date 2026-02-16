# Fase 2: Trading Bot Operativo — Plan de Implementacion

**Proyecto:** traiding-agentic
**Fecha:** 2026-02-15
**Duracion:** Semanas 5-12 (post Fase 1)
**Estado:** Aprobado, incorporado al plan tecnico
**Origen:** Brainstorming basado en CODEX/12 + deep-research-report (2)

---

## 1. Objetivo

Construir un trading bot que ejecute operaciones BTC/USDT en paper trading, alimentado por la Guia Maestra generada en Fase 1. Incluye HITL (Human-in-the-Loop), simulador local, circuit breakers, reconciliacion y observabilidad operativa.

## 2. Decisiones de Diseno (Brainstorming)

| Decision | Elegida | Descartada | Razon |
|---|---|---|---|
| HITL level | Hibrido (auto < $100, manual >= $100) | Full approval / Full autonomo | Balance velocidad y control |
| Event sourcing | Logs inmutables + correlation_id | Hash chain blockchain | YAGNI para MVP |
| Simulador | Si, con replay datos historicos | Directo a Binance | Mas seguro, permite backtesting |
| Graduacion sim→exchange | 7 dias estables, Sharpe>0, errors<1% | 3 dias | Mejor confidence operativa |
| Circuit breakers | Avanzados (trading + infra + LLM) | Basicos | Elegido explicitamente |
| Threshold HITL | $100 USDT | $50 | Ajustado por usuario |
| Notificaciones | Push + email | Solo dashboard | Pedido por usuario |
| Framework | Vercel AI SDK (se mantiene) | LangGraph | Decision previa |
| Embedding | gemini-embedding-001 (se mantiene) | text-embeddings-002 | Decision ronda 2 |
| Index | HNSW (se mantiene) | IVFFlat | Decision ronda 1 |

## 3. Arquitectura Fase 2

```
Market Data (Binance WS)
    |
    v
Indicators Engine (SMA, RSI, BBands, Volume, ATR)
    |
    v
Strategy Advisor (Gemini + Guia Maestra)
    |
    v
TradeProposal (draft)
    |
    v
Risk Manager + Circuit Breakers
    |
    +--[rechazado]--> Log + fin
    |
    +--[validado]
        |
        +--[< $100]--> auto_approved --> BrokerAdapter
        +--[>= $100]--> pending_approval --> Push notification
                            |
                            +--[aprobado]--> BrokerAdapter
                            +--[rechazado]--> Log + fin
                            +--[5min timeout]--> expired + fin
    |
    v
BrokerAdapter (simulated | spot_testnet | demo_futures)
    |
    v
Reconciliacion (cada 60s)
    |
    v
Metricas + Observabilidad
```

## 4. Entornos Binance

| Scope | REST base | WebSocket base |
|---|---|---|
| Spot Testnet | `https://testnet.binance.vision` | `wss://stream.testnet.binance.vision/ws` |
| Futures Demo (USDT-M) | `https://demo-fapi.binance.com` | `wss://fstream.binancefuture.com` |

El execution-adapter valida `BINANCE_ENV` en runtime. Si no es `spot_testnet` o `demo_futures`, rechaza toda orden.

## 5. Market Data

```typescript
// WebSocket a Binance Testnet (klines 1m)
const ws = new WebSocket('wss://stream.testnet.binance.vision/ws/btcusdt@kline_1m');

// Buffer de 200 velas para indicadores
// Solo procesar cuando vela cierra (isClosed: true)
```

## 6. Indicators Engine

```typescript
interface Indicators {
  sma_10: number;        // Simple Moving Average 10 periodos
  sma_50: number;        // Simple Moving Average 50 periodos
  rsi_14: number;        // Relative Strength Index
  bb_upper: number;      // Bollinger Band superior
  bb_lower: number;      // Bollinger Band inferior
  bb_middle: number;     // Bollinger Band medio
  volume_avg_20: number; // Volumen promedio 20 periodos
  volume_ratio: number;  // Volumen actual / promedio
  atr_14: number;        // Average True Range
}
```

## 7. Strategy Advisor

Cada 5 minutos:
1. Recopilar indicadores actuales
2. Cargar guia maestra (system prompt generado por Synthesis Agent)
3. Preguntar a Gemini que estrategia aplicar
4. Generar TradeProposal (nunca orden directa)

## 8. Trade Proposal Workflow (HITL Hibrido)

### Maquina de estados
```
draft → validated → auto_approved → executed | failed
                  → pending_approval → approved → executed | failed
                                     → rejected
                                     → expired
                  → risk_rejected
                  → cancelled (manual)
```

### Flujo
1. LLM genera propuesta (draft)
2. Risk Manager valida limites
   - Rechazado → status: risk_rejected, fin
   - Valido → status: validated
3. Evaluar threshold HITL:
   - notional < $100 → auto_approved → ejecutar
   - notional >= $100 → pending_approval → push notification
4. Operador en /approvals:
   - Aprobar → approved → ejecutar
   - Rechazar → rejected, loguear razon
   - No responde en 5 min → expired
5. Ejecucion:
   - Generar client_order_id (UUID)
   - Enviar al BrokerAdapter activo
   - Status: executed | failed
   - Loguear con correlation_id

### Configuracion
```env
AUTO_APPROVE_THRESHOLD_USDT=100
HITL_SLA_SECONDS=300
HITL_NOTIFICATIONS=push,email
```

## 9. Simulated Broker Adapter

### Interface comun
```typescript
interface BrokerAdapter {
  placeOrder(proposal: ValidatedProposal): Promise<OrderResult>;
  cancelOrder(orderId: string): Promise<CancelResult>;
  getOpenOrders(): Promise<Order[]>;
  getPositions(): Promise<Position[]>;
  getBalance(): Promise<Balance>;
  getOrderStatus(orderId: string): Promise<OrderStatus>;
}
```

### Implementaciones
- `SimulatedBroker` — local, slippage configurable, replay historico
- `BinanceSpotTestnet` — Spot Testnet
- `BinanceFuturesDemo` — Futures Demo

### Simulador config
```typescript
interface SimulatorConfig {
  initialBalanceUsdt: number;     // default 10000
  slippageBps: number;            // default 5 (0.05%)
  simulatedLatencyMs: number;     // default 100
  replayMode: boolean;            // alimentar con klines historicas
  replayDataPath?: string;        // CSV/JSON de klines
  replaySpeedMultiplier?: number; // 1x = real, 10x = rapido
}
```

Seleccion via env: `BROKER_ADAPTER=simulated|spot_testnet|demo_futures`

### Criterio de graduacion a Binance Testnet
1. Minimo 7 dias estable en simulador
2. Sin circuit breakers criticos activados
3. Sharpe ratio > 0
4. Error rate < 1%
5. Reconciliacion sin divergencias por 48h

## 10. Risk Manager + Circuit Breakers

### Risk Manager base
```typescript
interface RiskLimits {
  maxDailyLossPct: 2;
  maxPositionSizeBTC: 0.001;
  maxOpenPositions: 1;
  stopLossPct: 1.5;
  takeProfitPct: 3;
  maxLeverage: 1;
  cooldownAfterLossMinutes: 30;
}
```

### Circuit Breakers avanzados
```typescript
interface CircuitBreakers {
  // Trading
  maxConsecutiveLosses: 3;
  maxDailyLossPct: 2;

  // Infrastructure
  maxSlippageBps: 20;
  latencyGuardMs: 5000;
  maxOrderRejectionsPerHour: 5;

  // LLM
  maxLlmErrorsPerHour: 10;
  maxDailyLlmCostUsd: 5;
}
```

### Acciones por breaker

| Breaker | Accion primaria | Accion secundaria |
|---|---|---|
| maxConsecutiveLosses | Bloquear ordenes | Alerta push |
| maxDailyLossPct | Bloquear + cerrar posiciones | Alerta + log PnL |
| maxSlippageBps | Pausar 15 min | Review manual |
| latencyGuardMs | Pausar trading | Check salud exchange |
| maxOrderRejectionsPerHour | Bloquear ordenes | Investigar causa |
| maxLlmErrorsPerHour | Pausar agentes LLM | Fallback a ultima decision |
| maxDailyLlmCostUsd | Pausar agentes LLM | Alerta presupuesto |

## 11. Reconciliacion e Idempotencia

### Idempotencia
- Cada propuesta genera `client_order_id` (UUID v4)
- UNIQUE constraint en execution_orders
- Exchange ignora duplicados

### Reconciliacion (cada 60s)
1. Consultar ordenes/posiciones en exchange
2. Comparar con estado en DB
3. Detectar divergencias (ordenes huerfanas, missing)
4. Reparar y alertar

### Dead-letter
- Orden falla 3 veces → status dead_letter
- Requiere intervencion manual
- Alerta push inmediata

## 12. Logs Inmutables + Observabilidad

### Logs
- `correlation_id` (UUID): traza proposal → order → fill → reconciliation
- `actor` (agent|human|system|breaker)
- DELETE bloqueado via RLS (inmutabilidad)
- Campos: tokens_input, tokens_output, estimated_cost_usd

### Metricas operativas (pagina /operations)

| Metrica | Descripcion |
|---|---|
| proposal_to_approval_ms | Tiempo hasta aprobacion |
| approval_to_execution_ms | Tiempo hasta ejecucion |
| fill_rate | % propuestas ejecutadas |
| rejection_rate | % rechazadas |
| slippage_bps_realized | Slippage real vs esperado |
| breaker_trigger_count | Activaciones breakers/dia |
| llm_tokens_cost_daily | Costo LLM diario/agente |
| reconciliation_divergences | Divergencias por run |
| sharpe_ratio_rolling | Sharpe 30 dias |
| win_rate | % trades ganadores |

## 13. Modelo de Datos

### Tablas nuevas
| Tabla | Proposito |
|---|---|
| `trade_proposals` | Propuestas del LLM (11 estados, HITL, risk check) |
| `execution_orders` | Ordenes enviadas (client_order_id UNIQUE, fill info, slippage) |
| `reconciliation_runs` | Resultados de reconciliacion (divergencias, balance) |
| `risk_breaker_events` | Activaciones de breakers (trigger, threshold, resolucion) |

Todas con RLS habilitado + service_role_full_access.

### Campos clave
- `trade_proposals`: correlation_id, status (11 estados), notional_usdt, indicators_snapshot, guide_version, expires_at
- `execution_orders`: client_order_id (UNIQUE), fill_price, slippage_bps, retry_count, dead_letter status
- `risk_breaker_events`: breaker_category (trading|infrastructure|llm), resolved_at (null = activo)

## 14. API Routes

```
# Trade Proposals (HITL)
POST   /api/proposals              - Crear propuesta
GET    /api/proposals              - Listar (?status=pending_approval)
GET    /api/proposals/[id]         - Detalle con ordenes
POST   /api/proposals/[id]/approve - Aprobar
POST   /api/proposals/[id]/reject  - Rechazar

# Execution
GET    /api/orders                 - Listar ordenes
GET    /api/orders/[id]            - Detalle con fill

# Reconciliation
POST   /api/reconciliation/run     - Trigger manual
GET    /api/reconciliation/history - Historial
GET    /api/reconciliation/latest  - Ultima

# Risk & Breakers
GET    /api/risk/breakers          - Estado actual
GET    /api/risk/breakers/history  - Historial activaciones
POST   /api/risk/breakers/[name]/resolve - Resolver manual

# Operations & Metrics
GET    /api/operations/metrics     - KPIs
GET    /api/operations/pnl         - PnL diario/acumulado
GET    /api/operations/health      - Health check

# Simulator
POST   /api/simulator/config       - Configurar
POST   /api/simulator/replay       - Iniciar replay
GET    /api/simulator/status        - Estado
```

## 15. Frontend

| Ruta | Contenido |
|---|---|
| `/approvals` | Cola HITL: propuestas pendientes, timer SLA, aprobar/rechazar |
| `/trading` | Dashboard live: precio BTC, posicion, PnL, ultimo trade |
| `/operations` | Centro ops: breakers (verde/rojo), metricas, reconciliacion, logs con correlation_id |
| `/history` | Historial proposals + orders + fills, exportar CSV |
| `/simulator` | Config simulador, replay historicos, resultados backtesting |

## 16. Estructura de Archivos (Fase 2)

```
lib/
  trading/
    broker-adapter.ts               # Interface BrokerAdapter
    simulated-broker.ts             # Broker simulado local
    binance-spot-testnet.ts         # Adapter Binance Spot
    binance-futures-demo.ts         # Adapter Binance Futures
    proposal-workflow.ts            # Maquina de estados TradeProposal
    reconciliation.ts               # Reconciliacion periodica
    replay-engine.ts                # Replay datos historicos
  utils/
    indicators.ts                   # Technical indicators
    risk-manager.ts                 # Risk limits
    circuit-breakers.ts             # Circuit breakers avanzados
components/
  approvals/                        # HITL approval queue
  operations/                       # Operations center
  simulator/                        # Simulator config + replay
  trading/                          # Live trading dashboard
app/
  approvals/page.tsx
  trading/page.tsx
  operations/page.tsx
  history/page.tsx
  simulator/page.tsx
  api/
    proposals/...
    orders/...
    reconciliation/...
    risk/...
    operations/...
    simulator/...
```

## 17. Testing

### Unit
- Transicion de estados HITL (todos los caminos)
- Circuit breakers: activacion y desactivacion por tipo
- SimulatedBroker: fill con slippage, balance, posiciones
- Idempotencia: doble submit con mismo client_order_id
- Reconciliacion: deteccion de divergencias

### Integration
- Propuesta → auto-approve → ejecucion simulada → log
- Propuesta → pending_approval → approve → ejecucion
- Propuesta → risk_rejected (breaker activo)
- Reconciliacion contra SimulatedBroker con divergencia
- Dead-letter: orden falla 3x → alerta

### E2E
- /approvals: ver pendiente, aprobar, verificar ejecucion
- /operations: metricas y estado breakers
- /simulator: configurar y ejecutar replay
- Propuesta → aprobacion → ejecucion → aparece en /history

## 18. Roadmap

### Semana 5-6: Trading Core
- [ ] SimulatedBroker con slippage y latencia
- [ ] BrokerAdapter interface
- [ ] TradeProposal workflow completo
- [ ] Risk Manager + circuit breakers
- [ ] API: proposals CRUD + approve/reject
- [ ] /approvals con timer SLA y push notifications
- [ ] Strategy Advisor (Gemini + Guia Maestra) → proposals
- [ ] Tests: HITL, idempotencia, breakers

### Semana 7-8: Ejecucion + Reconciliacion
- [ ] Idempotencia con client_order_id
- [ ] Reconciliacion periodica (60s)
- [ ] Dead-letter para ordenes fallidas
- [ ] BinanceSpotTestnet adapter
- [ ] BinanceFuturesDemo adapter
- [ ] API: orders, reconciliation, risk breakers
- [ ] /operations con metricas
- [ ] Tests: reconciliacion, retry/backoff

### Semana 9-10: Observabilidad + Simulador Avanzado
- [ ] Replay datos historicos en SimulatedBroker
- [ ] /simulator con config y backtesting
- [ ] Metricas completas (Sharpe, fill rate, slippage, costs)
- [ ] /history con exportacion CSV
- [ ] Push notifications (email + browser push)
- [ ] Criterio graduacion automatico

### Semana 11-12: Hardening + Piloto
- [ ] 7 dias simulador estable
- [ ] Migrar a Binance Testnet (volumenes minimos)
- [ ] Monitoreo breakers en produccion demo
- [ ] Playbooks de fallo y runbooks
- [ ] Review seguridad y permisos

## 19. Definition of Done

- [ ] No hay ejecucion sin TradeProposal workflow
- [ ] HITL funcional: ordenes > $100 requieren aprobacion humana
- [ ] Push notifications para aprobaciones y breakers
- [ ] Simulador estable 7 dias
- [ ] Reconciliacion automatica sin divergencias 48h
- [ ] Idempotencia validada por tests
- [ ] Circuit breakers operativos (trading + infra + LLM)
- [ ] Trazabilidad completa por correlation_id
- [ ] Metricas visibles en /operations
- [ ] Sharpe ratio > 0 en simulador
- [ ] Error rate < 1% sostenido 7 dias

## 20. Variables de Entorno

```env
# Binance router
BINANCE_ENV=spot_testnet   # spot_testnet | demo_futures
TRADING_ENABLED=false      # Kill switch global

# Spot Testnet
BINANCE_SPOT_BASE_URL=https://testnet.binance.vision
BINANCE_SPOT_WS_URL=wss://stream.testnet.binance.vision/ws

# Futures Demo
BINANCE_FUTURES_BASE_URL=https://demo-fapi.binance.com
BINANCE_FUTURES_WS_URL=wss://fstream.binancefuture.com

# Credenciales
BINANCE_API_KEY=
BINANCE_API_SECRET=

# HITL
AUTO_APPROVE_THRESHOLD_USDT=100
HITL_SLA_SECONDS=300
HITL_NOTIFICATIONS=push,email

# Broker Adapter
BROKER_ADAPTER=simulated   # simulated | spot_testnet | demo_futures

# Circuit Breakers
MAX_DAILY_LLM_COST_USD=5
MAX_CONSECUTIVE_LOSSES=3
```

## 21. Items Descartados (con justificacion)

| Item del report | Razon de descarte |
|---|---|
| LangGraph interrupts para HITL | Usamos Vercel AI SDK, HITL via estados en DB + API routes |
| text-embeddings-002 de OpenAI | Migrado a gemini-embedding-001 (Ronda 2 CODEX) |
| IVFFlat con nlist~100 | Migrado a HNSW (Ronda 1 CODEX) |
| Hash chain event sourcing | Overkill, logs inmutables con correlation_id suficiente |
| SQLite para tests | Supabase con RLS, tests contra DB real o mock |
| Redis/RabbitMQ para queues | MVP con Vercel background functions o inngest. Redis si escala |
