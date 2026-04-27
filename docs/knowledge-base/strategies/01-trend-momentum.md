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

Entra **long** cuando un símbolo muestra momentum alcista con múltiples filtros técnicos alineados (RSI moderado, ADX con tendencia, baja entropía, régimen compatible). Desde 2026-04-21 la entrada es **regime-aware**: en laterales sólo entra si detecta un micro-breakout real, y además pausa temporalmente un símbolo tras una racha de pérdidas.

Es la estrategia **por defecto** del bot. Implementada tras el post-mortem del 5 abr 2026 (ver `../research/2026-04-05-post-mortem-49trades.md`).

## Cuándo funciona mejor

| Condición | Valor |
|---|---|
| Régimen | `trending_up` o `ranging_low_vol` con micro-breakout confirmado |
| Volatilidad (ATR%) | 0.5% – 3% |
| Timeframe señal | 1h |
| Símbolos activos | **ETHUSDT** |
| Símbolos en pausa | **BTCUSDT** (breakeven noise, pausa táctica) |
| Símbolos deshabilitados | BNBUSDT (22 trades, WR 23%, -$5.96) |

## Cuándo NO usarla

- Régimen `trending_down` con confianza >85% → entry bloqueada explícitamente
- Régimen `ranging_high_vol` o `volatile` → blocked
- Mercado puramente ranging de baja volatilidad sin breakout hints → blocked
- Después de cierre reciente (<180 min cooldown anti-churn)
- Después de 3 trades perdedores consecutivos en <24h para el mismo símbolo

## Reglas de entrada (BUY)

| Filtro | Valor | Archivo |
|---|---|---|
| RSI(14) | < 50.0 (clamp 30-55) | `signal_generator.py` |
| ADX(14) | > 20.0 (clamp 18-35) | `signal_generator.py` |
| Entropy ratio | < 0.75 (clamp 0.60-0.80) | `signal_generator.py` |
| MACD histogram | > -50 (era -200, filtra entradas con momentum negativo) | `signal_generator.py:44` |
| SMA20 vs SMA50 | SMA20 > SMA50 (o override ADX>30 + Hurst>0.55) | `signal_generator.py:338-357` |
| Regime confidence | NO `trending_down` > 85% | `signal_generator.py:334` |
| Perfil `range-caution` | `RSI<=47`, `ADX>=21`, `>=1` breakout hint | `signal_generator.py` |
| Perfil `range-breakout` | `RSI<=45`, `ADX>=22`, `>=2` breakout hints | `signal_generator.py` |
| Breakout hints | PPO>0, AC1>0.02, Volume ratio>=1.05 | `signal_generator.py` |
| Open positions | < 3 total | `signal_generator.py:328` |
| Same-symbol positions | = 0 | via risk_manager |
| Post-close cooldown | > 180 min desde último close | `signal_generator.py:55` |
| Signal cooldown | > 180 min desde última signal (clamp 120-360) | `signal_generator.py` |
| Loss streak pause | 3 losers consecutivos → pausa 24h | `signal_generator.py` |

## Reglas de salida (SELL)

| Tipo | Trigger | Prioridad |
|---|---|---|
| **Hard SL** | Entry - `sl_atr_multiplier` × ATR (capped [0.5%, 2%]) | 1 — fast loop 2s |
| **Hard TP** | Entry + `tp_atr_multiplier` × ATR (capped [1.8%, 7%]) | 1 — fast loop 2s |
| **Trailing** | Chandelier `highest_high - 1.5×ATR` cuando progress ≥ 40% | 2 — fast loop 2s |
| **Signal RSI** | RSI > 70 + MACD hist < 50 + breakeven gate (1%) + min hold 180min | 3 — slow loop 60s |
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
quant_symbols = "ETHUSDT"              # backend/app/config.py:46
risk_max_open_positions = 3            # backend/app/config.py:37
```

### Overrides por símbolo (2026-04-27)
```python
SYMBOL_SL_ATR_OVERRIDES = {"BTCUSDT": 1.0, "ETHUSDT": 0.9}  # backend/app/config.py:13
SYMBOL_TP_ATR_OVERRIDES = {"BTCUSDT": 1.5}                   # backend/app/config.py:17
SYMBOL_NOTIONAL_OVERRIDES = {"ETHUSDT": 80.0}                # backend/app/config.py:25
```

### Anti-churn (hardcoded — LLM no puede cambiarlos)
```python
MIN_HOLD_MINUTES = 180                 # signal_generator.py:49
BREAKEVEN_THRESHOLD_PCT = 0.010        # floor 1.0% (era 0.3%) — signal_generator.py:52
BREAKEVEN_ATR_SCALE = 0.3              # signal_generator.py:56
BREAKEVEN_CEILING_PCT = 0.025          # ceiling 2.5% (era 0.8%) — signal_generator.py:57
POST_CLOSE_COOLDOWN_MINUTES = 180      # signal_generator.py:75
REGIME_EXIT_CONFIDENCE_MIN = 80.0      # signal_generator.py:72
```

### Hard caps SL/TP porcentuales (executor.py)
```python
SL_MAX_DISTANCE_PCT = 0.020            # 2% max (era 3%) — executor.py:211
TP_MAX_DISTANCE_PCT = 0.07             # executor.py:212
SL_MIN_DISTANCE_PCT = 0.005            # executor.py:213
TP_MIN_DISTANCE_PCT = 0.018            # 1.8% min (era 1%) — executor.py:214
```

### Trailing activation
```python
trailing_activation_progress = 0.40    # trading_loop.py (era 0.30 — subido para activar en ganancia significativa)
chandelier_multiplier_k = 1.5          # trading_loop.py (era 2.0 — más apretado = protege más ganancia)
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
- **Desde 2026-04-21 el bot distingue `ranging_low_vol` vs `ranging_high_vol`** y usa perfiles distintos de entrada; esto cierra una brecha entre la KB y el código productivo
