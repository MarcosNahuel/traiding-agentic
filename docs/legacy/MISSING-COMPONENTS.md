# 🔧 Componentes Faltantes - Trading Agentic

**Fecha:** 16 de Febrero, 2026
**Estado actual:** Backend research funcionando ✅, Trading execution pendiente ⏳

---

## 📊 ESTADO ACTUAL

### ✅ Implementado (Backend Research)

1. **Sistema de Papers**
   - ✅ Agregar sources (URLs, PDFs con Jina AI)
   - ✅ Source Agent (evaluación automática)
   - ✅ Reader Agent (extracción de estrategias)
   - ✅ Synthesis Agent (generación de guías)
   - ✅ Chat Agent (consultas interactivas)
   - ✅ Auto-synthesis (trigger automático después de 5 papers)

2. **Base de Datos**
   - ✅ Supabase configurado
   - ✅ Tablas: sources, strategies_found, trading_guides, agent_logs
   - ✅ Embeddings para estrategias
   - ✅ Chunking automático

3. **API Endpoints**
   - ✅ `/api/sources` - CRUD de papers
   - ✅ `/api/strategies` - Listado de estrategias
   - ✅ `/api/guides` - Guías sintetizadas
   - ✅ `/api/health` - Health check

4. **Infrastructure**
   - ✅ Vercel Pro deployment (300s timeouts)
   - ✅ GitHub CI/CD
   - ✅ Environment variables configuradas
   - ✅ Jina AI Reader integrado

---

## ❌ FALTANTE (Trading Execution)

### 1. 🔗 Conexión con Binance Testnet

**Estado:** No implementado
**Prioridad:** 🔴 ALTA

#### Qué falta:

**A. Configuración de Binance Testnet**
```typescript
// lib/exchanges/binance-testnet.ts

export const BINANCE_CONFIG = {
  REST_BASE: "https://testnet.binance.vision",
  WS_BASE: "wss://stream.testnet.binance.vision/ws",
  API_KEY: process.env.BINANCE_TESTNET_API_KEY,
  API_SECRET: process.env.BINANCE_TESTNET_SECRET,
};
```

**Variables de entorno faltantes:**
```env
BINANCE_TESTNET_API_KEY=
BINANCE_TESTNET_SECRET=
BINANCE_ENV=spot_testnet  # Validación de seguridad
```

**B. Market Data Stream (WebSocket)**
```typescript
// lib/exchanges/market-data.ts

// Conectar a Binance WebSocket para datos en tiempo real
const ws = new WebSocket('wss://stream.testnet.binance.vision/ws/btcusdt@kline_1m');

// Recibir candlesticks en tiempo real
// Almacenar en DB para análisis
```

**C. Order Execution Adapter**
```typescript
// lib/exchanges/execution-adapter.ts

// Enviar órdenes a Binance Testnet
// Validar BINANCE_ENV antes de cada orden
// Logging de todas las operaciones
// Manejo de errores y reintentos
```

---

### 2. 📋 Trade Proposals (HITL - Human in the Loop)

**Estado:** No implementado
**Prioridad:** 🔴 ALTA

#### Qué falta:

**A. Tabla en Supabase**
```sql
CREATE TABLE trade_proposals (
  id UUID PRIMARY KEY,
  strategy_id UUID REFERENCES strategies_found(id),
  type TEXT, -- 'buy' | 'sell'
  symbol TEXT, -- 'BTC/USDT'
  quantity DECIMAL,
  price DECIMAL,
  notional DECIMAL, -- quantity * price
  status TEXT, -- 'draft' | 'validated' | 'approved' | 'rejected' | 'executed'
  risk_score DECIMAL,
  auto_approved BOOLEAN,
  approval_threshold DECIMAL, -- $100 default
  reasoning TEXT, -- LLM explanation
  created_at TIMESTAMP,
  approved_at TIMESTAMP,
  executed_at TIMESTAMP,
  order_id TEXT -- Binance order ID
);
```

**B. API Endpoint**
```typescript
// app/api/trades/proposals/route.ts

POST /api/trades/proposals
// LLM crea propuesta, Risk Manager valida
// Si < $100 → auto-approve
// Si >= $100 → requiere aprobación manual

GET /api/trades/proposals
// Lista propuestas pendientes de aprobación

PATCH /api/trades/proposals/[id]
// Aprobar/rechazar propuesta
```

---

### 3. 🛡️ Risk Manager (Determinista)

**Estado:** No implementado
**Prioridad:** 🔴 ALTA

#### Qué falta:

**A. Reglas de Riesgo**
```typescript
// lib/trading/risk-manager.ts

export interface RiskLimits {
  maxPositionSize: number; // Max $500 por trade
  maxDailyLoss: number; // Max -$200/día
  maxDrawdown: number; // Max -$1000 desde peak
  maxOpenPositions: number; // Max 3 posiciones simultáneas
  minAccountBalance: number; // Min $1000 para operar
}

export function validateTradeProposal(
  proposal: TradeProposal,
  currentPositions: Position[],
  accountBalance: number
): ValidationResult {
  // Validar todas las reglas
  // Retornar aprobado/rechazado + razón
}
```

**B. Tabla en Supabase**
```sql
CREATE TABLE risk_events (
  id UUID PRIMARY KEY,
  event_type TEXT, -- 'limit_hit' | 'drawdown_alert' | 'margin_call'
  severity TEXT, -- 'warning' | 'critical'
  details JSONB,
  resolved BOOLEAN,
  created_at TIMESTAMP
);
```

---

### 4. 📊 Portfolio Tracker

**Estado:** No implementado
**Prioridad:** 🟡 MEDIA

#### Qué falta:

**A. Tabla de Posiciones**
```sql
CREATE TABLE positions (
  id UUID PRIMARY KEY,
  symbol TEXT, -- 'BTC/USDT'
  side TEXT, -- 'long' | 'short'
  entry_price DECIMAL,
  quantity DECIMAL,
  current_price DECIMAL,
  pnl DECIMAL, -- profit/loss actual
  pnl_percent DECIMAL,
  opened_at TIMESTAMP,
  closed_at TIMESTAMP,
  status TEXT -- 'open' | 'closed'
);
```

**B. API Endpoints**
```typescript
GET /api/portfolio
// Estado actual del portfolio
// Balance, posiciones abiertas, PnL total

GET /api/portfolio/history
// Historial de trades
// Performance metrics
```

---

### 5. 🤖 Trading Agent (Executor)

**Estado:** No implementado
**Prioridad:** 🟡 MEDIA

#### Qué falta:

**A. Agent que ejecuta estrategias**
```typescript
// lib/agents/trading-agent.ts

export async function executeStrategy(
  strategyId: string,
  marketData: MarketData
): Promise<TradeProposal> {
  // 1. Analizar condiciones de mercado actuales
  // 2. Verificar si estrategia aplica
  // 3. Calcular tamaño de posición
  // 4. Crear TradeProposal
  // 5. Enviar a Risk Manager
}
```

**B. Cron Job / Scheduler**
```typescript
// app/api/cron/trading-loop/route.ts

export async function GET() {
  // Ejecutar cada 1 minuto
  // 1. Obtener market data
  // 2. Evaluar todas las estrategias activas
  // 3. Crear proposals si hay oportunidades
  // 4. Actualizar posiciones abiertas
}
```

En vercel.json:
```json
{
  "crons": [
    {
      "path": "/api/cron/trading-loop",
      "schedule": "* * * * *" // Cada minuto
    }
  ]
}
```

---

### 6. 📱 Telegram Bot (Notificaciones)

**Estado:** Parcialmente implementado
**Prioridad:** 🟢 BAJA

#### Qué falta:

**A. Token configurado pero sin implementación**
```env
TELEGRAM_BOT_TOKEN=8540887019:AAGrshOGOVLsjgpsekKx7xV7eO5TzHsIVTg
TELEGRAM_CHAT_ID=  # ← FALTA
```

**B. Servicio de notificaciones**
```typescript
// lib/services/telegram-notifier.ts

export async function notifyTradeProposal(proposal: TradeProposal) {
  // Enviar mensaje con detalles
  // Botones inline para aprobar/rechazar
}

export async function notifyTradeExecuted(trade: Trade) {
  // Confirmar ejecución
}

export async function notifyRiskAlert(alert: RiskEvent) {
  // Alertas de riesgo
}
```

---

### 7. 🎨 Frontend Pages

**Estado:** No implementado (solo homepage)
**Prioridad:** 🟡 MEDIA

#### Páginas faltantes (ya documentadas):
- `/sources` - Gestión de papers ⏳
- `/strategies` - Explorador de estrategias ⏳
- `/guides` - Visualizador de guías ⏳
- `/chat` - Chat con AI ⏳
- `/logs` - Monitor de actividad ⏳
- `/portfolio` - Dashboard de trading ⏳ (NUEVO)
- `/trades` - Historial y proposals ⏳ (NUEVO)

---

## 🎯 ROADMAP RECOMENDADO

### Fase 1: Trading Infrastructure (1-2 semanas)

**Prioridad: Fundaciones**

1. ✅ Crear cuenta en Binance Testnet
2. ✅ Obtener API keys
3. ✅ Configurar environment variables
4. ✅ Implementar Binance adapter básico
5. ✅ WebSocket para market data
6. ✅ Tabla trade_proposals
7. ✅ API endpoint para proposals
8. ✅ Risk Manager básico

**Objetivo:** Poder crear y aprobar trade proposals manualmente

---

### Fase 2: Automation (1 semana)

**Prioridad: Trading Agent**

1. ✅ Trading Agent (evalúa estrategias)
2. ✅ Cron job para trading loop
3. ✅ Auto-ejecución de proposals aprobados
4. ✅ Portfolio tracker
5. ✅ Tabla positions

**Objetivo:** Sistema ejecutando trades automáticamente

---

### Fase 3: Monitoring & Safety (3-5 días)

**Prioridad: Seguridad**

1. ✅ Risk events logging
2. ✅ Telegram notifications
3. ✅ Emergency stop button
4. ✅ Performance metrics
5. ✅ Alertas de drawdown

**Objetivo:** Sistema seguro y monitoreado

---

### Fase 4: Frontend (1 semana)

**Prioridad: UX**

1. ✅ Páginas de research (/sources, /strategies, /guides)
2. ✅ Dashboard de portfolio
3. ✅ Panel de trade proposals
4. ✅ Logs en tiempo real
5. ✅ Chat interface

**Objetivo:** UI completa para operar

---

## 📝 CHECKLIST INMEDIATO

### Para empezar hoy:

- [ ] Crear cuenta Binance Testnet
- [ ] Obtener API keys (API key + Secret)
- [ ] Agregar a .env.local y Vercel
- [ ] Crear directorio `lib/exchanges/`
- [ ] Implementar binance-testnet.ts
- [ ] Crear tabla trade_proposals en Supabase
- [ ] Endpoint POST /api/trades/proposals
- [ ] Risk Manager básico

---

## 🔧 COMPONENTES AUXILIARES FALTANTES

### 1. Logging Estructurado
- Winston o Pino para logs
- Diferentes niveles (info, warn, error)
- Streaming a servicio externo (opcional)

### 2. Error Monitoring
- Sentry para errores en producción
- Alertas automáticas

### 3. Rate Limiting
- Protección de APIs
- Límites por IP/usuario

### 4. Authentication
- Supabase Auth para login
- Protección de endpoints sensibles
- Roles (admin, trader, viewer)

### 5. Backtesting Engine
- Probar estrategias con datos históricos
- Antes de ejecutar en testnet

---

## 💰 COSTOS ESTIMADOS

### Free Tier:
- ✅ Binance Testnet: Gratis
- ✅ Supabase: $0/mes (hasta 500MB)
- ✅ Vercel Pro: $20/mes (ya tienes)
- ✅ Jina AI: Gratis (20 req/hora)

### Opcional:
- Sentry: $0-26/mes
- Better Stack (logs): $0-20/mes
- Premium data providers: $50+/mes

**Total mínimo:** $20/mes (solo Vercel Pro)

---

## 🎓 RECURSOS

### Binance Testnet:
- Docs: https://testnet.binance.vision/
- API Docs: https://binance-docs.github.io/apidocs/spot/en/

### Librerías útiles:
- `ccxt`: Exchange integration library
- `ws`: WebSocket client
- `decimal.js`: Precisión numérica para trading

---

## ✨ BONUS: Quick Start

### 1. Obtener Binance Testnet Keys

```bash
# 1. Ir a https://testnet.binance.vision/
# 2. Registrarse con email
# 3. Generate API Key
# 4. Copiar API Key y Secret
```

### 2. Configurar en Vercel

```bash
vercel env add BINANCE_TESTNET_API_KEY production
vercel env add BINANCE_TESTNET_SECRET production
vercel env add BINANCE_ENV production  # valor: spot_testnet
```

### 3. Primera integración (5 min)

```typescript
// test-binance.ts
import fetch from 'node-fetch';

const API_KEY = process.env.BINANCE_TESTNET_API_KEY;
const url = 'https://testnet.binance.vision/api/v3/ticker/price?symbol=BTCUSDT';

const response = await fetch(url, {
  headers: { 'X-MBX-APIKEY': API_KEY }
});

const data = await response.json();
console.log('BTC Price:', data.price);
```

---

**Última actualización:** 16 de Febrero, 2026
**Próximo paso:** Configurar Binance Testnet
