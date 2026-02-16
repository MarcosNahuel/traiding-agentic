# 🤖 Trading System Documentation

**Status:** ✅ Implemented
**Environment:** Binance Spot Testnet
**Date:** February 16, 2026

---

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Database Schema](#database-schema)
- [API Endpoints](#api-endpoints)
- [Trading Flow](#trading-flow)
- [Risk Management](#risk-management)
- [Configuration](#configuration)
- [Usage Examples](#usage-examples)
- [Monitoring](#monitoring)

---

## 🎯 Overview

The Trading System is a fully automated trading platform that:

1. **Researches** trading strategies from academic papers and articles
2. **Evaluates** strategies against live market data
3. **Proposes** trades with risk assessment
4. **Executes** approved trades on Binance Testnet
5. **Monitors** portfolio performance and risk metrics

### Key Features

- ✅ **Human-in-the-Loop (HITL):** Trades require approval unless under $100
- ✅ **Risk Manager:** Deterministic validation of all trades
- ✅ **Position Tracking:** Real-time P&L calculation
- ✅ **WebSocket Market Data:** Live price feeds
- ✅ **Telegram Notifications:** Real-time alerts
- ✅ **Automated Trading Loop:** Runs every 5 minutes via Vercel Cron

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     RESEARCH LAYER                          │
│  Source Agent → Reader Agent → Synthesis Agent → Chat      │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                     TRADING LAYER                           │
│                                                             │
│  ┌────────────┐    ┌──────────────┐    ┌───────────────┐ │
│  │  Trading   │───▶│     Risk     │───▶│   Executor    │ │
│  │   Agent    │    │   Manager    │    │   (Binance)   │ │
│  └────────────┘    └──────────────┘    └───────────────┘ │
│        │                  │                     │          │
│        ▼                  ▼                     ▼          │
│  ┌────────────────────────────────────────────────────┐   │
│  │           Trade Proposals (HITL)                   │   │
│  │  draft → validated → approved → executed           │   │
│  └────────────────────────────────────────────────────┘   │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                   MONITORING LAYER                          │
│  Portfolio Tracker │ Risk Events │ Telegram Notifier       │
└─────────────────────────────────────────────────────────────┘
```

---

## 💾 Database Schema

### Tables Created

```sql
-- Trade proposals requiring approval
trade_proposals (
  id, strategy_id, type, symbol, quantity, price,
  order_type, notional, status, risk_score, risk_checks,
  auto_approved, binance_order_id, executed_price,
  executed_quantity, commission, timestamps
)

-- Open and closed positions
positions (
  id, symbol, side, entry_price, entry_quantity,
  current_price, current_quantity, exit_price,
  realized_pnl, unrealized_pnl, status, timestamps
)

-- Risk management alerts
risk_events (
  id, event_type, severity, message, details,
  resolved, timestamps
)

-- Daily account snapshots
account_snapshots (
  id, total_balance, available_balance, daily_pnl,
  peak_balance, current_drawdown, open_positions,
  total_trades, win_rate, snapshot_date
)

-- Real-time market data cache
market_data (
  id, symbol, price, bid_price, ask_price,
  high_24h, low_24h, volume_24h, price_change_24h,
  timestamps
)
```

---

## 🔌 API Endpoints

### Trade Proposals

```bash
# Create new trade proposal
POST /api/trades/proposals
{
  "type": "buy",
  "symbol": "BTCUSDT",
  "quantity": 0.001,
  "orderType": "MARKET",
  "strategyId": "uuid",
  "reasoning": "Strategy suggests buy signal"
}

# List proposals
GET /api/trades/proposals?status=validated&limit=50

# Get specific proposal
GET /api/trades/proposals/[id]

# Approve/reject proposal
PATCH /api/trades/proposals/[id]
{
  "action": "approve",
  "notes": "Looks good"
}

# Cancel proposal
DELETE /api/trades/proposals/[id]
```

### Trade Execution

```bash
# Execute specific proposal
POST /api/trades/execute
{
  "proposalId": "uuid"
}

# Execute all approved proposals
POST /api/trades/execute
{
  "executeAll": true
}
```

### Portfolio

```bash
# Get current portfolio state
GET /api/portfolio
# Returns: balance, positions, P&L, performance metrics

# Get trade history
GET /api/portfolio/history?status=closed&limit=50
```

### Market Data

```bash
# Start WebSocket stream
POST /api/market-data/stream
{
  "action": "start",
  "symbols": ["BTCUSDT", "ETHUSDT"]
}

# Get stream status
GET /api/market-data/stream

# Stop stream
POST /api/market-data/stream
{
  "action": "stop"
}
```

### Cron Jobs

```bash
# Trading loop (runs every 5 minutes via Vercel Cron)
GET /api/cron/trading-loop
# 1. Evaluates strategies
# 2. Creates proposals
# 3. Executes auto-approved trades
# 4. Updates portfolio metrics
```

---

## 🔄 Trading Flow

### 1. Strategy Evaluation

```typescript
// Trading Agent evaluates strategies every 5 minutes
const signals = await evaluateAllStrategies(['BTCUSDT', 'ETHUSDT']);
// Returns: TradeSignal[] with type, confidence, reasoning
```

### 2. Proposal Creation

```typescript
// Create proposal from signal
const proposalId = await createProposalFromSignal(signal);
// Status: 'draft'
```

### 3. Risk Validation

```typescript
// Risk Manager validates proposal
const validation = await validateTradeProposal(proposal);
// Checks: position size, daily loss, drawdown, max positions, etc.
// Status: 'validated' or 'rejected'
```

### 4. Auto-Approval (Optional)

```typescript
// If notional < $100 and all risk checks pass
if (notional < 100 && validation.approved) {
  status = 'approved';
  auto_approved = true;
}
// Status: 'approved'
```

### 5. Human Approval (Required if > $100)

```bash
# User approves via API or Telegram
PATCH /api/trades/proposals/[id]
{ "action": "approve" }
# Status: 'approved'
```

### 6. Execution

```typescript
// Executor places order on Binance
const result = await executeTradeProposal(proposalId);
// Creates/updates position in database
// Status: 'executed'
```

### 7. Position Tracking

```typescript
// Portfolio tracker updates P&L in real-time
const portfolio = await getPortfolioState();
// Returns unrealized P&L for open positions
```

---

## 🛡️ Risk Management

### Risk Limits (DEFAULT_RISK_LIMITS)

```typescript
{
  maxPositionSize: 500,        // Max $500 per trade
  minPositionSize: 10,         // Min $10 per trade
  maxDailyLoss: 200,           // Max -$200/day
  maxDrawdown: 1000,           // Max -$1000 from peak
  maxOpenPositions: 3,         // Max 3 open positions
  maxPositionsPerSymbol: 1,    // Max 1 position per symbol
  minAccountBalance: 1000,     // Min $1000 to trade
  maxAccountUtilization: 0.8,  // Max 80% of balance in positions
  autoApprovalThreshold: 100   // Auto-approve if < $100
}
```

### Risk Checks

Every proposal is validated against:

1. ✅ **Position Size:** Within min/max limits
2. ✅ **Account Balance:** Sufficient funds available
3. ✅ **Daily Loss Limit:** Not exceeded
4. ✅ **Drawdown Limit:** Not exceeded
5. ✅ **Max Open Positions:** Under limit
6. ✅ **Symbol Concentration:** Not overexposed
7. ✅ **Account Utilization:** Under 80%

### Risk Scoring

- Each check contributes to risk score (0-100)
- Higher score = riskier trade
- Critical failures = immediate rejection

### Safety Features

- ✅ **Environment Validation:** Only executes on `spot_testnet`
- ✅ **Dry Run Mode:** Test without real execution
- ✅ **Order Confirmation:** Verifies order placement
- ✅ **Position Limits:** Prevents overexposure
- ✅ **Circuit Breakers:** Stops trading on critical alerts

---

## ⚙️ Configuration

### Environment Variables

```bash
# Binance Testnet (REQUIRED)
BINANCE_TESTNET_API_KEY=your_api_key
BINANCE_TESTNET_SECRET=your_secret
BINANCE_ENV=spot_testnet  # MUST be 'spot_testnet'

# Telegram Notifications (OPTIONAL)
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Supabase (REQUIRED)
NEXT_PUBLIC_SUPABASE_URL=your_url
SUPABASE_SERVICE_ROLE_KEY=your_key

# Google AI (REQUIRED for trading agent)
GOOGLE_AI_API_KEY=your_api_key

# App URL
NEXT_PUBLIC_APP_URL=https://your-app.vercel.app
```

### Vercel Configuration

```json
// vercel.json
{
  "crons": [
    {
      "path": "/api/cron/trading-loop",
      "schedule": "*/5 * * * *"  // Every 5 minutes
    }
  ],
  "functions": {
    "app/api/cron/trading-loop/route.ts": {
      "maxDuration": 60
    },
    "app/api/trades/execute/route.ts": {
      "maxDuration": 30
    }
  }
}
```

---

## 📚 Usage Examples

### Manual Trading

```bash
# 1. Create proposal
curl -X POST http://localhost:3000/api/trades/proposals \
  -H "Content-Type: application/json" \
  -d '{
    "type": "buy",
    "symbol": "BTCUSDT",
    "quantity": 0.001,
    "orderType": "MARKET",
    "reasoning": "Testing manual trade"
  }'

# Response:
{
  "success": true,
  "proposalId": "uuid",
  "status": "approved",  # Auto-approved if < $100
  "autoApproved": true,
  "riskScore": 25
}

# 2. Execute (if not auto-approved)
curl -X POST http://localhost:3000/api/trades/execute \
  -H "Content-Type: application/json" \
  -d '{"proposalId": "uuid"}'

# Response:
{
  "success": true,
  "orderId": 12345,
  "executedPrice": 95000.50,
  "executedQuantity": 0.001
}
```

### Automated Trading

```bash
# The cron job runs automatically every 5 minutes
# You can also trigger it manually:

curl http://localhost:3000/api/cron/trading-loop

# Response:
{
  "success": true,
  "duration": "3.45s",
  "agent": {
    "signalsGenerated": 2,
    "proposalsCreated": 2
  },
  "execution": {
    "executed": 1,
    "failed": 0
  }
}
```

### Portfolio Monitoring

```bash
# Get current state
curl http://localhost:3000/api/portfolio

# Response:
{
  "balance": {
    "total": 10000,
    "available": 9500,
    "locked": 0,
    "inPositions": 500
  },
  "positions": {
    "open": [
      {
        "symbol": "BTCUSDT",
        "side": "long",
        "entryPrice": 95000,
        "currentPrice": 96000,
        "unrealizedPnL": 95.00,
        "unrealizedPnLPercent": 1.05
      }
    ]
  },
  "pnl": {
    "daily": {
      "realized": 50,
      "unrealized": 95,
      "total": 145
    }
  },
  "performance": {
    "totalTrades": 10,
    "winRate": "70.00"
  }
}
```

### Market Data Stream

```bash
# Start WebSocket stream
curl -X POST http://localhost:3000/api/market-data/stream \
  -H "Content-Type: application/json" \
  -d '{
    "action": "start",
    "symbols": ["BTCUSDT", "ETHUSDT"]
  }'

# Check status
curl http://localhost:3000/api/market-data/stream

# Response:
{
  "status": "connected",
  "isRunning": true,
  "symbols": ["btcusdt", "ethusdt"],
  "lastMessageTime": "2026-02-16T12:00:00Z"
}
```

---

## 📊 Monitoring

### Telegram Notifications

If configured, you'll receive notifications for:

- 🟢 New trade proposals (with approve/reject buttons)
- ✅ Trade executions
- 💰 Position closures with P&L
- ⚠️ Risk alerts
- 📊 Daily portfolio summaries
- 🚨 System errors

### Logs

```bash
# Vercel logs
vercel logs --follow

# Local logs
npm run dev  # Watch console for trading activity
```

### Risk Events

```sql
-- Query recent risk events
SELECT * FROM risk_events
WHERE created_at > NOW() - INTERVAL '24 hours'
ORDER BY created_at DESC;

-- Unresolved critical events
SELECT * FROM risk_events
WHERE resolved = false
  AND severity = 'critical'
ORDER BY created_at DESC;
```

### Performance Metrics

```sql
-- Trading performance
SELECT
  COUNT(*) as total_trades,
  SUM(CASE WHEN realized_pnl > 0 THEN 1 ELSE 0 END) as wins,
  SUM(CASE WHEN realized_pnl < 0 THEN 1 ELSE 0 END) as losses,
  SUM(realized_pnl) as total_pnl,
  AVG(realized_pnl) as avg_pnl,
  AVG(realized_pnl_percent) as avg_return_pct
FROM positions
WHERE status = 'closed'
  AND closed_at > NOW() - INTERVAL '30 days';
```

---

## 🚀 Getting Started

### 1. Database Setup

```bash
# Apply migration
npm run db:migrate
# Creates all trading tables
```

### 2. Configure Environment

```bash
# Add to .env.local
BINANCE_TESTNET_API_KEY=...
BINANCE_TESTNET_SECRET=...
BINANCE_ENV=spot_testnet
```

### 3. Test Binance Connection

```bash
# Visit http://localhost:3000/api/binance/test
# Should return connection status and balances
```

### 4. Start Trading Loop (Local)

```bash
# Manually trigger
curl http://localhost:3000/api/cron/trading-loop
```

### 5. Deploy to Vercel

```bash
git push origin master
# Vercel will deploy and start cron job automatically
```

---

## 🔐 Security

- ✅ **Testnet Only:** Hardcoded safety check for `BINANCE_ENV=spot_testnet`
- ✅ **API Key Validation:** Requires valid Binance API keys
- ✅ **Rate Limiting:** Built into Binance API client
- ✅ **Error Handling:** All operations wrapped in try/catch
- ✅ **Audit Trail:** All trades logged in database
- ✅ **HITL Approval:** Trades > $100 require human approval

---

## 📝 TODO

- [ ] Backtesting engine for strategy validation
- [ ] More sophisticated position sizing algorithms
- [ ] Dynamic risk limits based on account balance
- [ ] Multi-timeframe analysis
- [ ] Support for more exchanges (via CCXT)
- [ ] Web UI for trade management
- [ ] Advanced charting and analytics

---

**Status:** Production Ready ✅
**Last Updated:** February 16, 2026
**Maintainer:** Trading Agentic Team
