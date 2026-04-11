---
id: 01-trend-momentum
name: Trend-Momentum Multi-Filter
status: active
created: 2026-03-27
last_updated: 2026-04-11
category: trend-following
---

# Trend-Momentum Multi-Filter (estrategia activa)

## Resumen

Entra **long** cuando un símbolo muestra momentum alcista con múltiples filtros técnicos alineados (RSI oversold moderado, ADX con tendencia, baja entropía, régimen no bearish). Sale por señal cuando RSI se vuelve overbought + MACD pierde momentum, o por SL/TP ATR-based.

Es la estrategia **por defecto** del bot. Implementada tras el post-mortem del 5 abr 2026 (ver `../research/2026-04-05-post-mortem-49trades.md`).

## Cuándo funciona mejor

| Condición | Valor |
|---|---|
| Régimen | `trending_up` o `ranging_low_vol` con micro-momentum |
| Volatilidad (ATR%) | 0.5% – 3% |
| Timeframe señal | 1h |
| Símbolos activos | **ETHUSDT** (edge probado), **BTCUSDT** (breakeven, en observación) |
| Símbolos deshabilitados | BNBUSDT (22 trades, WR 23%, -$5.96) |

## Cuándo NO usarla

- Régimen `trending_down` con confianza >85% → entry bloqueada explícitamente
- Volatilidad extrema (ATR > 10% del precio) → SL aberrante, fallback a %
- Mercado puramente ranging de baja volatilidad (ADX < 18) → filtro ADX bloquea
- Después de cierre reciente (<180 min cooldown anti-churn)

## Reglas de entrada (BUY)

| Filtro | Valor | Archivo |
|---|---|---|
| RSI(14) | < 50.0 (clamp 30-55) | `signal_generator.py` |
| ADX(14) | > 20.0 (clamp 18-35) | `signal_generator.py` |
| Entropy ratio | < 0.75 (clamp 0.60-0.80) | `signal_generator.py` |
| MACD histogram | > -200 (testnet relajado) | `signal_generator.py:42` |
| SMA20 vs SMA50 | SMA20 > SMA50 (o override ADX>30 + Hurst>0.55) | `signal_generator.py:338-357` |
| Regime confidence | NO `trending_down` > 85% | `signal_generator.py:334` |
| Volume ratio | > 1.2× SMA20 (disabled en testnet) | `signal_generator.py:361` |
| Autocorrelation lag-1 | Pre-trade confirmation | `signal_generator.py` |
| Open positions | < 3 total | `signal_generator.py:328` |
| Same-symbol positions | = 0 | via risk_manager |
| Post-close cooldown | > 180 min desde último close | `signal_generator.py:55` |
| Signal cooldown | > 180 min desde última signal (clamp 120-360) | `signal_generator.py` |

## Reglas de salida (SELL)

| Tipo | Trigger | Prioridad |
|---|---|---|
| **Hard SL** | Entry - `sl_atr_multiplier` × ATR (capped [0.5%, 3%]) | 1 — fast loop 2s |
| **Hard TP** | Entry + `tp_atr_multiplier` × ATR (capped [1%, 7%]) | 1 — fast loop 2s |
| **Trailing** | Chandelier `highest_high - 2×ATR` cuando progress ≥ 30% | 2 — fast loop 2s |
| **Signal RSI** | RSI > 65 + MACD hist < 50 + breakeven gate + min hold 180min | 3 — slow loop 60s |
| **Signal regime** | `trending_down` conf > 80% + breakeven gate | 3 — slow loop 60s |
| **Signal Hurst** | Hurst < 0.40 + RSI > 55 | 3 — slow loop 60s |
| **Time stop** | age > 24h | 4 — fast loop 2s |

## Parámetros activos (con paths file:line)

### Defaults (config.py)
```python
sl_atr_multiplier = 1.2                # backend/app/config.py:59
tp_atr_multiplier = 2.0                # backend/app/config.py:60
sl_fallback_pct = 0.02                 # backend/app/config.py:61
tp_fallback_pct = 0.04                 # backend/app/config.py:62
buy_entropy_max = 0.75                 # backend/app/config.py:65
buy_adx_min = 20.0                     # backend/app/config.py:66
buy_regime_confidence_min = 85.0       # backend/app/config.py:67
quant_buy_notional_usd = 60.0          # backend/app/config.py:53
quant_symbols = "BTCUSDT,ETHUSDT"      # backend/app/config.py:46
risk_max_open_positions = 3            # backend/app/config.py:37
```

### Overrides por símbolo (2026-04-11)
```python
SYMBOL_SL_ATR_OVERRIDES = {"BTCUSDT": 1.0}     # backend/app/config.py:12
SYMBOL_TP_ATR_OVERRIDES = {"BTCUSDT": 1.5}     # backend/app/config.py:15
SYMBOL_NOTIONAL_OVERRIDES = {"ETHUSDT": 100.0} # backend/app/config.py:22
```

### Anti-churn (hardcoded — LLM no puede cambiarlos)
```python
MIN_HOLD_MINUTES = 180                 # signal_generator.py:47
BREAKEVEN_THRESHOLD_PCT = 0.003        # floor (signal_generator.py:50)
BREAKEVEN_ATR_SCALE = 0.3              # signal_generator.py:53
BREAKEVEN_CEILING_PCT = 0.008          # signal_generator.py:54
POST_CLOSE_COOLDOWN_MINUTES = 180      # signal_generator.py:55
REGIME_EXIT_CONFIDENCE_MIN = 80.0      # signal_generator.py:52
```

### Hard caps SL/TP porcentuales (executor.py)
```python
SL_MAX_DISTANCE_PCT = 0.03             # executor.py:211
TP_MAX_DISTANCE_PCT = 0.07             # executor.py:212
SL_MIN_DISTANCE_PCT = 0.005            # executor.py:213
TP_MIN_DISTANCE_PCT = 0.01             # executor.py:214
```

### Trailing activation
```python
trailing_activation_progress = 0.30    # trading_loop.py:313 (era 0.40, antes 0.65)
chandelier_multiplier_k = 2.0          # trading_loop.py:324
time_stop_hours = 24                   # trading_loop.py:197
```

## Performance histórica

### Pre-fix (2026-02-17 → 2026-04-04) — 49 trades
- Win rate: 36.7%
- Profit factor: ~0.50
- R-mult promedio: -0.28
- P&L: **-$18.74**
- SL hit: 82% / TP hit: 1% / Signal exit: 15%

### Post-fix (2026-04-05 → 2026-04-11) — 13 trades
- Win rate: **76.9%**
- R-mult promedio: **+0.62**
- P&L: **+$15.94**
- SL hit: 56% / TP hit: 12% / Signal exit: 31%
- ETH: 7 trades, WR 86%, +$15.36
- BTC: 6 trades, WR 67% pero P&L ~break-even ($+1.95)

## Links

- Código principal: `backend/app/services/signal_generator.py`
- Exit manager: `backend/app/services/trading_loop.py`
- SL/TP calculation: `backend/app/services/executor.py:217-284`
- Post-mortem que originó: `../research/2026-04-05-post-mortem-49trades.md`
- Análisis y mejoras 2026-04-11: `../research/2026-04-11-improvements-analysis.md`

## Notas

- **SL/TP guardados en DB y verificados por fast loop cada 2s** (no hay OCO nativo en Binance aún — ver `../research/gaps.md`)
- **MIN_HOLD y BREAKEVEN son anti-churn críticos** — no desactivar sin post-mortem
- **LLM overrides pasan por `LLM_SAFE_BOUNDS`** en `signal_generator.py:62-69` — la constitución que el LLM no puede violar
