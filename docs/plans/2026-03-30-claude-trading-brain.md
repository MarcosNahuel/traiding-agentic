# Plan: Claude Trading Brain — Agente Autónomo de Estrategia

> Fecha: 2026-03-30
> Autor: Nahuel Albornoz + Claude
> Estado: APROBADO PARA IMPLEMENTACIÓN
> Testnet: Binance Spot Testnet (sin riesgo real)

---

## Contexto

### Qué tenemos hoy
- **Python backend** funcionando: signal_generator, risk_manager, executor, trading_loop (60s + 2s)
- **Daily Analyst** con Gemini (LangGraph): ajusta parámetros pero es limitado
- **13 documentos de estrategias** (trend, mean-reversion, breakout, etc.)
- **69 tests** passing
- **strategy.py es PLACEHOLDER** — `evaluate_and_maybe_trade()` devuelve None
- **TradingConfigOverride** con Pydantic bounds (seguro para LLM)
- **4 bugs críticos** de la auditoría 2026-03-13

### Qué queremos
Claude Agent SDK como **cerebro estratégico autónomo** que:
1. Investiga mercados diariamente (noticias, sentiment, macro, on-chain)
2. Decide qué estrategia aplicar según condiciones
3. Ajusta parámetros del engine Python (RSI, ADX, entropy, SL/TP, symbols)
4. Explica sus decisiones a Nahuel (que está aprendiendo trading)
5. Ejecuta todo en Testnet — sin riesgo real
6. Aprende de sus resultados (post-market audit)

### Referencia: Cómo otros lo hacen (verificado 2026-03-30)

| Proyecto | Stars | Qué decide el LLM | Ejecución | URL |
|----------|-------|--------------------|-----------|-----|
| **TradingAgents** | 44.6K | Multi-agent debate: 4 analysts + bull/bear + trader + risk | Simulada | github.com/TauricResearch/TradingAgents |
| **ai-hedge-fund** | 43K | 12 investor personas (Buffett, Burry, etc.) + portfolio mgr | Simulada | github.com/virattt/ai-hedge-fund |
| **AlpacaTradingAgent** | - | 5 analysts + debate + trader decide | **Broker real (Alpaca)** | github.com/huygiatrng/AlpacaTradingAgent |
| **AgenticTrading** | - | DAG planner + orquestador + memory (Neo4j) | Backtesting | github.com/Open-Finance-Lab/AgenticTrading |
| **FinMem** | - | 3 capas memoria cognitiva (working/episodic/semantic) | Simulada | github.com/pipiku915/FinMem-LLM-StockTrading |
| **FinRobot** | - | Market Forecaster + Trade Strategist (Financial CoT) | Mixta | github.com/AI4Finance-Foundation/FinRobot |

**Patrón que seguimos: "Strategy Selector" (LLM Alpha Mining paper, arXiv:2409.06289)**
- El LLM recibe condiciones de mercado y ELIGE qué algoritmo Python ejecutar
- El LLM NO ejecuta el trade directamente — selecciona estrategia + parámetros
- Código determinístico ejecuta mecánicamente
- Resultado del paper: +53.17% cumulative return vs -13.22% del benchmark

**Benchmark NexusTrade (2026):** Claude Opus 4.1 ganó como MEJOR LLM para generar
estrategias de trading (score 0.95/1, 72% scores perfectos, superando GPT-5 y Gemini).

**StockBench (arXiv:2510.02209):** En test real con 20 stocks, la mayoría de LLMs
superan buy-and-hold modestamente. Los mejores: Kimi-K2 (+1.9%), Qwen3 (+2.4%).
Agentes sufren más en downturns — confirma necesidad de risk management robusto.

---

## Arquitectura

```
┌─────────────────────────────────────────────────────────────────┐
│  CLAUDE AGENT SDK (PC local, Max subscription)                  │
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────────────┐   │
│  │ RESEARCHER   │  │ SENTIMENT   │  │ STRATEGIST           │   │
│  │ (subagent)   │  │ (subagent)  │  │ (orquestador)        │   │
│  │              │  │             │  │                      │   │
│  │ WebSearch    │  │ WebSearch   │  │ Lee outputs de       │   │
│  │ WebFetch     │  │ Fear&Greed  │  │ Researcher+Sentiment │   │
│  │ OpenBB data  │  │ Reddit      │  │                      │   │
│  │ CoinDesk     │  │ Twitter/X   │  │ Lee 13 estrategias   │   │
│  │ Papers       │  │ Whale txns  │  │ docs/estrategias/    │   │
│  │              │  │             │  │                      │   │
│  │ Output:      │  │ Output:     │  │ Lee performance      │   │
│  │ market_data  │  │ sentiment   │  │ últimos 7 días       │   │
│  │ JSON         │  │ JSON        │  │                      │   │
│  └─────────────┘  └─────────────┘  │ DECIDE:              │   │
│                                     │ - Config override     │   │
│                                     │ - Símbolos activos    │   │
│                                     │ - Razón explicada     │   │
│                                     │ - Brief educativo     │   │
│                                     └──────────────────────┘   │
│                              │                                  │
│                    ┌─────────▼──────────┐                       │
│                    │  Structured Output  │                       │
│                    │  TradingDecision    │                       │
│                    └─────────┬──────────┘                       │
├──────────────────────────────┼──────────────────────────────────┤
│  SUPABASE                    │                                  │
│  daily_decisions ◄───────────┘                                  │
│  quant_config_override ◄─── config_bridge.py lee cada 60s      │
├─────────────────────────────────────────────────────────────────┤
│  PYTHON BACKEND (VPS)                                           │
│  signal_generator.py → _get_thresholds() → lee config override  │
│  → genera proposals → risk_manager valida → executor ejecuta    │
│  → trading_loop monitorea SL/TP cada 2s                         │
├─────────────────────────────────────────────────────────────────┤
│  TELEGRAM + WHATSAPP (Super Yo)                                 │
│  ← Brief diario + explicación educativa para Nahuel             │
│  ← Alertas de trades ejecutados                                 │
│  ← Audit nocturno (qué salió bien/mal y por qué)               │
└─────────────────────────────────────────────────────────────────┘
```

### Flujo completo (1 día típico)

### Principio central: Claude DIRIGE, Python EJECUTA, Nahuel OBSERVA

Claude tiene autonomía total sobre la estrategia. Solo comunica a Nahuel lo que
está haciendo y por qué. Nahuel no necesita aprobar — solo aprende.

```
06:00 ART │ ═══ ANÁLISIS MATUTINO (proactivo) ═══
          │
          │ Cron trigger (n8n o local)
          │
06:01     │ RESEARCHER subagent (paralelo):
          │   → WebSearch "BTC outlook today site:coindesk.com"
          │   → WebSearch "crypto macro events this week"
          │   → WebFetch Fear & Greed Index API
          │   → WebFetch OpenBB macro data
          │   → Leer últimas noticias relevantes
          │
06:01     │ SENTIMENT subagent (paralelo):
          │   → WebSearch "bitcoin sentiment reddit today"
          │   → WebSearch "whale alert bitcoin large transactions"
          │   → WebFetch top posts r/cryptocurrency
          │   → Análisis de tono: bullish/bearish/neutral
          │
06:03     │ STRATEGIST (orquestador):
          │   → Lee outputs de Researcher + Sentiment
          │   → GET /api/quant/snapshot (Python backend)
          │   → GET /api/portfolio (posiciones abiertas)
          │   → GET /api/trades/recent (performance 7 días)
          │   → Lee docs/estrategias/ (13 documentos de referencia)
          │   → Lee CONOCIMIENTO-NAHUEL papers relevantes
          │
06:05     │ DECISIÓN MATUTINA:
          │   → Structured Output → Supabase daily_decisions
          │   → Config override → Supabase quant_config_override
          │   → Mensaje a Nahuel: "Buenos días. Hoy opero BTC y ETH..."
          │
06:05→    │ ═══ EJECUCIÓN MECÁNICA (Python autónomo) ═══
          │
          │ Python backend opera según los parámetros de Claude:
          │   → Lee config override cada 60s
          │   → Genera señales según parámetros
          │   → Ejecuta trades
          │   → Monitorea SL/TP cada 2s
          │   → Notifica cada trade a Nahuel: "Compré 0.01 BTC a $84,500"
          │
──────────│ ═══ RE-ANÁLISIS REACTIVO (Python despierta a Claude) ═══
          │
          │ TRIGGERS para despertar a Claude:
          │   1. Drawdown diario > 5% del balance
          │   2. 2+ SL consecutivos en la misma sesión
          │   3. Pérdida individual > 2% del balance
          │   4. Fear & Greed cambió más de 15 puntos
          │   5. Flash crash detectado (precio cae >3% en 15 min)
          │
          │ Python envía POST a Claude Agent SDK con:
          │   → Qué pasó (trades perdidos, drawdown actual)
          │   → Estado actual del portfolio
          │   → Datos de mercado en tiempo real
          │
          │ CLAUDE RE-ANALIZA:
          │   → WebSearch "qué pasó en crypto ahora"
          │   → Analiza: ¿fue mala estrategia o evento externo?
          │   → NUEVA DECISIÓN:
          │     a) Cambiar parámetros (más conservador)
          │     b) Pausar trading el resto del día
          │     c) Cambiar símbolos activos
          │     d) Mantener estrategia (pérdida normal)
          │   → UPDATE quant_config_override en Supabase
          │   → Mensaje a Nahuel: "Perdimos $45 en ETH por [razón].
          │     Ajusté SL más tight y desactivé ETH por hoy..."
          │
00:05     │ ═══ AUDIT NOCTURNO ═══
          │
          │ Claude analiza:
          │   → Todos los trades del día
          │   → Compara decisión matutina vs realidad
          │   → Si hubo re-análisis: evalúa si la corrección funcionó
          │   → Genera lecciones aprendidas
          │   → Mensaje a Nahuel: "Hoy: 3 trades, 2 wins, 1 loss.
          │     PnL: +$32. Sharpe semanal: 0.7. Aprendimos que..."
```

### Diagrama del loop reactivo

```
                    ┌──────────────────┐
                    │  CLAUDE DECIDE   │
                    │  (mañana 06:00)  │
                    └────────┬─────────┘
                             │
                    config override → Supabase
                             │
                    ┌────────▼─────────┐
              ┌────►│  PYTHON EJECUTA  │◄────┐
              │     │  (todo el día)   │     │
              │     └────────┬─────────┘     │
              │              │               │
              │     ┌────────▼─────────┐     │
              │     │  ¿Va todo bien?  │     │
              │     └────────┬─────────┘     │
              │         SI/  \NO             │
              │          /    \               │
              │   sigue   ┌────▼─────────┐   │
              │  operando │ DESPIERTA A  │   │
              │           │ CLAUDE       │   │
              │           │              │   │
              │           │ Re-investiga │   │
              │           │ Re-decide    │   │
              │           │ Notifica     │   │
              │           └────┬─────────┘   │
              │                │              │
              │       nuevo config override   │
              │                │              │
              └────────────────┘──────────────┘
```

---

## Modelo de Decisión de Claude

### Input (lo que Claude recibe)

```json
{
  "market_research": {
    "top_news": ["Fed mantiene tasas", "BTC ETF inflows $500M"],
    "macro": { "dxy": 104.2, "sp500_futures": "+0.3%", "vix": 18.5 },
    "events_this_week": ["FOMC minutes miércoles", "BTC options expiry viernes"]
  },
  "sentiment": {
    "fear_greed_index": 62,
    "fear_greed_label": "Greed",
    "reddit_tone": "moderately_bullish",
    "whale_activity": "accumulation",
    "funding_rates": { "BTCUSDT": 0.01, "ETHUSDT": 0.008 }
  },
  "technical": {
    "BTCUSDT": {
      "price": 84500, "rsi": 42, "macd_hist": 120, "adx": 28,
      "regime": "trending_up", "entropy": 0.65,
      "support": 82000, "resistance": 87500,
      "atr": 1200
    },
    "ETHUSDT": { ... },
    "BNBUSDT": { ... }
  },
  "portfolio": {
    "balance_usdt": 10000,
    "open_positions": 1,
    "daily_pnl": -12.50,
    "7day_win_rate": 0.55,
    "7day_sharpe": 0.8
  },
  "strategies_available": [
    "trend_momentum_v2: BUY cuando ADX>20 + RSI<50 + regime=trending_up",
    "mean_reversion_v2: BUY cuando RSI<30 + regime=ranging + timeout 48h",
    "bbands_breakout_v2: BUY en squeeze + volumen confirmación"
  ]
}
```

### Output (lo que Claude decide)

```json
{
  "decision_date": "2026-03-30",
  "market_assessment": "Mercado en tendencia alcista moderada...",
  "chosen_strategy": "trend_momentum_v2",
  "strategy_reasoning": "ADX en 28 confirma tendencia. RSI en 42 no sobrecomprado...",

  "config_override": {
    "buy_rsi_max": 48,
    "buy_adx_min": 22,
    "buy_entropy_max": 0.75,
    "sell_rsi_min": 68,
    "sl_atr_multiplier": 1.2,
    "tp_atr_multiplier": 2.0,
    "risk_multiplier": 0.8,
    "max_open_positions": 3,
    "quant_symbols": "BTCUSDT,ETHUSDT",
    "signal_cooldown_minutes": 120,
    "reasoning": "Ajusto SL más tight por evento FOMC miércoles..."
  },

  "risk_warnings": [
    "FOMC minutes miércoles puede generar volatilidad",
    "Options expiry viernes — posible pin a $85K"
  ],

  "learning_brief": {
    "concept_of_the_day": "ATR (Average True Range)",
    "explanation": "El ATR mide cuánto se mueve un activo en promedio...",
    "how_we_use_it": "Hoy pusimos SL a 1.2×ATR = $1,440 debajo del entry...",
    "real_example": "Si compramos BTC a $84,500, el SL queda en $83,060"
  },

  "confidence": 0.72,
  "sources_consulted": 15
}
```

### Hard Bounds (no negociables)

Claude NO puede salirse de estos rangos (Pydantic los clampea):

| Parámetro | Min | Max | Default |
|-----------|-----|-----|---------|
| buy_rsi_max | 30 | 65 | 50 |
| buy_adx_min | 10 | 40 | 20 |
| buy_entropy_max | 0.50 | 0.95 | 0.85 |
| sell_rsi_min | 55 | 80 | 65 |
| sl_atr_multiplier | 0.5 | 3.0 | 1.0 |
| tp_atr_multiplier | 0.8 | 4.0 | 1.5 |
| risk_multiplier | 0.25 | 2.0 | 1.0 |
| max_open_positions | 1 | 8 | 5 |

---

## Componente Educativo: "Trading Coach"

Claude no solo decide — te enseña. Cada brief diario incluye:

### Concepto del Día
Explica UN concepto de trading relevante a la decisión de hoy:
- Qué es RSI y por qué lo usamos
- Qué significa "regime trending_up"
- Cómo funciona un Stop Loss basado en ATR
- Qué es el Fear & Greed Index
- Por qué diversificamos en 3 símbolos

### Trade Explicado
Cuando se ejecuta un trade:
- "Compré BTC a $84,500 porque: RSI=42 (no sobrecomprado), ADX=28 (tendencia fuerte), el Fear & Greed está en 62 (confianza moderada)"
- "Puse SL en $83,060 (1.2×ATR debajo) para limitar la pérdida a ~$72"
- "El TP está en $86,900 (2.0×ATR arriba), potencial ganancia ~$120"
- "Risk/Reward = 1:1.67 — arriesgo $72 para ganar $120"

### Lección Post-Trade
Cuando se cierra un trade:
- "El trade de BTC cerró en TP (+$120). La tendencia alcista se confirmó como esperábamos"
- "El trade de ETH cerró en SL (-$45). El FOMC generó volatilidad que no anticipamos. Lección: ser más conservador antes de eventos macro"

---

## Implementación: 7 Tareas

### Task 1: Script principal Claude Agent SDK
**Archivo:** `scripts/claude-trading-brain.py`
**Qué hace:** Orquesta los 3 subagentes y genera la decisión diaria
**Dependencias:** `claude-agent-sdk`, conexión a Supabase, acceso a Python backend API

```python
# Pseudocódigo del flujo principal
async def daily_trading_brain():
    # 1. Research + Sentiment en paralelo (subagentes)
    # 2. Fetch datos técnicos del Python backend
    # 3. Strategist sintetiza y decide
    # 4. Structured output → Supabase
    # 5. Brief educativo → Telegram + WhatsApp
    # 6. Log en CONOCIMIENTO-NAHUEL
```

### Task 2: Custom tools para el Agent SDK
**Archivo:** `scripts/trading-tools.py`
**Tools:**

| Tool | Qué hace |
|------|----------|
| `get_quant_snapshot` | GET /api/quant/analysis/{symbol} del backend |
| `get_portfolio` | GET /api/portfolio del backend |
| `get_recent_trades` | GET /api/trades/recent del backend |
| `save_decision` | INSERT en Supabase daily_decisions |
| `save_config_override` | INSERT en Supabase quant_config_override |
| `notify_telegram` | Envía brief por Telegram |
| `read_strategy_docs` | Lee docs/estrategias/ del repo |
| `get_backtest_results` | GET /api/quant/backtest del backend |

### Task 3: Subagente Researcher
**Definición en AgentDefinition:**
- Tools: WebSearch, WebFetch
- Prompt: "Investigá las noticias y datos macro más relevantes para crypto hoy"
- Output: JSON con news, macro, events

### Task 4: Subagente Sentiment
**Definición en AgentDefinition:**
- Tools: WebSearch, WebFetch
- Prompt: "Analizá el sentimiento del mercado crypto hoy"
- Output: JSON con fear_greed, reddit_tone, whale_activity

### Task 5: System prompt del Strategist
**Archivo:** `scripts/prompts/strategist.md`
**Contenido:**
- Identidad: "Sos un analista cuantitativo de crypto que trabaja para Nahuel"
- Reglas: "NUNCA recomendes leverage alto. Siempre explicá tu razonamiento"
- Contexto: Resume las 13 estrategias disponibles
- Output format: TradingDecision JSON schema
- Educación: "Nahuel está aprendiendo trading. Explicá cada concepto"

### Task 6: Cron trigger
**Opciones (elegir una):**
- n8n workflow: trigger a las 06:00 ART → HTTP request a script local
- Windows Task Scheduler: ejecuta `python scripts/claude-trading-brain.py`
- Script Python con schedule: `while True: sleep until 06:00`

### Task 7: Reactive trigger (Python → Claude)
**Archivo backend:** `backend/app/services/claude_trigger.py`
**Qué hace:** Detecta condiciones adversas y despierta a Claude para re-analizar

```python
# Triggers que despiertan a Claude:
TRIGGERS = {
    "drawdown_daily_pct": 5.0,      # Drawdown diario > 5%
    "consecutive_sl_hits": 2,        # 2+ Stop Loss seguidos
    "single_loss_pct": 2.0,         # Pérdida individual > 2% balance
    "fear_greed_shift": 15,          # Fear&Greed cambió >15 puntos
    "flash_crash_pct": 3.0,         # Precio cae >3% en 15 min
}
```

**Integración con trading_loop.py:**
- Después de cada SL hit → evaluar triggers
- Después de cada reconciliation → evaluar drawdown
- Si trigger se activa → POST a endpoint local de Claude Agent SDK
- Claude re-investiga, re-decide, y actualiza config_override
- Python recoge nueva config en el siguiente tick (60s)

**Endpoint local (PC de Nahuel):**
```
POST http://localhost:3333/api/reactive-analysis
Body: { trigger, portfolio_state, recent_trades, market_snapshot }
```

### Task 8: Post-market audit
**Archivo:** `scripts/claude-post-market-audit.py`
**Trigger:** 00:05 UTC (21:05 ART)
**Qué hace:**
- Lee trades del día desde Supabase
- Compara decisión matutina vs resultados reales
- Si hubo re-análisis reactivo: evalúa si la corrección fue acertada
- Genera lecciones aprendidas
- Envía audit nocturno por Telegram/WhatsApp
- Guarda feedback para mejorar decisiones futuras

### Task 9: Notificación continua a Nahuel
**Canal:** Telegram (primario) + WhatsApp (via Super Yo)
**Mensajes automáticos:**

| Evento | Mensaje ejemplo |
|--------|----------------|
| Brief matutino | "Buenos días. Hoy opero BTC+ETH. Mercado alcista, F&G=62..." |
| Trade ejecutado | "Compré 0.01 BTC a $84,500. SL=$83,060. TP=$86,900" |
| SL hit | "SL tocado en BTC. Perdimos $72 (-0.72%). Normal, sigue la estrategia" |
| TP hit | "TP alcanzado en ETH! Ganamos $120 (+1.2%)" |
| Re-análisis | "2 SL seguidos. Re-analicé: FOMC causó volatilidad. Pauso ETH, ajusto BTC..." |
| Audit nocturno | "Hoy: +$32 neto. 2W/1L. Sharpe 7d=0.7. Concepto: qué es RSI..." |

---

## Fix de Bugs Críticos (Pre-requisito)

Antes de activar el brain, hay que resolver los 4 bugs de la auditoría:

| # | Bug | Fix | Archivo |
|---|-----|-----|---------|
| 1 | Ejecución duplicada | Atomic claim: UPDATE WHERE status='approved' RETURNING | executor.py |
| 2 | Partial fills rompen modelo | Status `partially_closed` + reconciliation | executor.py, positions |
| 3 | is_exit bloqueado por balance | Exit bypass total (solo validar quantity) | risk_manager.py |
| 4 | LIMIT orders sin state machine | Order state tracking: NEW→FILLED/PARTIAL/CANCELED | executor.py |

---

## Dependencias a instalar

```bash
# En la PC local (donde corre Claude Agent SDK)
pip install claude-agent-sdk
# O: npm install @anthropic-ai/claude-agent-sdk (si preferís TypeScript)

# El backend Python (VPS) NO necesita cambios de dependencias
# Solo necesita los endpoints API que ya existen
```

---

## Configuración

### Variables de entorno nuevas (PC local)

```env
# Claude (ya autenticado con Max via `claude login`)
# No necesita ANTHROPIC_API_KEY

# Backend API
TRADING_BACKEND_URL=http://161.35.54.238:8000
BACKEND_SECRET=<mismo que el VPS>

# Supabase (directo para escribir decisiones)
SUPABASE_URL=https://zaqpiuwacinvebfttygm.supabase.co
SUPABASE_KEY=<service_role_key>

# Telegram
TELEGRAM_BOT_TOKEN=<mismo>
TELEGRAM_CHAT_ID=<mismo>

# CONOCIMIENTO-NAHUEL (para leer papers)
KNOWLEDGE_BASE_PATH=D:/OneDrive/GitHub/CONOCIMIENTO-NAHUEL
```

---

## Métricas de Éxito (Testnet)

| Métrica | Target (30 días) | Cómo medimos |
|---------|-------------------|--------------|
| Win Rate | > 50% | trades ganadores / total |
| Sharpe Ratio | > 0.5 | retorno ajustado por riesgo |
| Max Drawdown | < 20% | peor caída desde pico |
| Trades/día | 2-5 | actividad saludable |
| Brief diario | 100% | Claude envía brief cada día |
| Explicación calidad | Nahuel entiende | feedback subjetivo |

### Regla de Mainnet
**Solo pasar a mainnet cuando:**
1. 30 días consecutivos en testnet
2. Sharpe > 0.5
3. Max drawdown < 15%
4. Win rate > 45%
5. Nahuel se siente cómodo con las decisiones

---

## Timeline

| Día | Tarea | Entregable |
|-----|-------|-----------|
| 1 | Fix bugs críticos (Task 0) | 4 fixes + tests |
| 2 | Script principal + custom tools (Tasks 1-2) | claude-trading-brain.py funcional |
| 3 | Subagentes + system prompt (Tasks 3-5) | Investigación autónoma funcionando |
| 4 | Reactive trigger en Python (Task 7) | Python despierta a Claude ante pérdidas |
| 5 | Cron + post-market audit + notificaciones (Tasks 6, 8, 9) | Loop completo |
| 6 | Testing end-to-end | Primera decisión real en testnet |
| 7-37 | Paper trading (30 días) | Claude dirige, Nahuel observa y aprende |

---

## Riesgos y Mitigaciones

| Riesgo | Impacto | Mitigación |
|--------|---------|-----------|
| Claude hallucina datos de mercado | Decisión basada en info falsa | Verificar con datos del backend Python (fuente de verdad) |
| Claude se vuelve demasiado agresivo | Pérdidas grandes en testnet | Hard bounds en Pydantic + max_open_positions ≤ 8 |
| PC apagada = sin decisión matutina | Backend usa defaults | Default config si no hay override del día |
| Binance Testnet caído | No se puede operar | Graceful degradation, retry logic |
| Costos de API (si se usa API key) | Presupuesto excedido | max_budget_usd en Agent SDK + monitoring |

---

## Glosario para Nahuel

| Término | Qué significa | Ejemplo |
|---------|--------------|---------|
| **RSI** | Indicador que mide si algo está sobrecomprado (>70) o sobrevendido (<30) | RSI=42 → "neutral, no caro" |
| **ADX** | Fuerza de la tendencia. >25 = tendencia fuerte | ADX=28 → "hay tendencia clara" |
| **ATR** | Cuánto se mueve el precio en promedio | ATR=1200 → "BTC se mueve ~$1200/día" |
| **SL (Stop Loss)** | Precio donde vendemos para limitar pérdida | "Si BTC baja a $83K, vendemos" |
| **TP (Take Profit)** | Precio donde vendemos para tomar ganancia | "Si BTC sube a $87K, vendemos" |
| **Regime** | Estado del mercado: trending up/down/ranging | "trending_up = está subiendo" |
| **Entropy** | Cuánto ruido tiene el mercado. Menos = más predecible | entropy=0.65 → "señal clara" |
| **Sharpe Ratio** | Ganancia ajustada por riesgo. >1 = bueno | Sharpe=0.8 → "decente" |
| **Drawdown** | Peor caída desde el máximo | -15% → "caímos 15% del pico" |
| **Fear & Greed** | Sentimiento del mercado crypto (0-100) | 62 = "Greed moderado" |

---

## Aprobación

- [x] Nahuel aprueba el plan (2026-03-30)
- [ ] Fix bugs críticos completados
- [ ] Script Claude Agent SDK funcional
- [ ] Primera decisión diaria ejecutada en testnet
- [ ] 30 días de paper trading completados
- [ ] Métricas de éxito alcanzadas
- [ ] Decisión de mainnet
