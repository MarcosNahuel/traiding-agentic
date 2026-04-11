---
date: 2026-04-05
type: post-mortem
author: previous session (commit b9ed674)
severity: critical
---

# Post-Mortem — 49 trades, -$18.74

## TL;DR

Entre 2026-02-17 y 2026-04-04, el bot ejecutó 49 trades cerrados con pérdida total de **$18.74** (WR 36.7%, PF 0.50). El LLM daily analyst configuró parámetros tan laxos que efectivamente **desactivó los filtros** de entropy, RSI, ADX y cooldown.

## Root causes

1. **LLM config destruyó filtros**
   - `buy_entropy_max = 0.93` (default era 0.75) → permite entradas en mercados ruidosos
   - `buy_rsi_max = 60` (default 50) → entradas tarde en subida
   - `buy_adx_min = 12` (default 20) → entradas sin tendencia
   - `signal_cooldown_minutes = 30` (default 180) → churn masivo

2. **ATR sin caps porcentuales**
   - SL calculado `price - k*ATR` sin límite → SL iba de 0.5% a **20%** del precio
   - TP similar: 1% a **40%**
   - Trades se mantenían 44-117 horas con SL gigantes, acumulando -3% a -7%

3. **Hold time error permitía exits prematuros**
   - Excepción en DB query → fallback permitía exit inmediato
   - Debería haber sido "fail closed" (bloquear exit si no hay datos)

4. **BNBUSDT activo**
   - 22 trades, WR 23%, -$5.96 → peor símbolo por amplio margen

## 6 Fixes aplicados (commit b9ed674)

1. **executor.py:207-284** — Hard caps SL/TP porcentuales:
   - `SL_MIN_DISTANCE_PCT = 0.005` (0.5%)
   - `SL_MAX_DISTANCE_PCT = 0.03` (3%)
   - `TP_MIN_DISTANCE_PCT = 0.01` (1%)
   - `TP_MAX_DISTANCE_PCT = 0.07` (7%)
   - Función `_clamp_sl_tp()` que valida y reporta clamps

2. **signal_generator.py:62-82** — Safe bounds para LLM overrides:
   ```python
   LLM_SAFE_BOUNDS = {
       "buy_rsi_max":             (30.0, 55.0),
       "buy_adx_min":             (18.0, 35.0),
       "buy_entropy_max":         (0.60, 0.80),
       "sell_rsi_min":            (60.0, 75.0),
       "signal_cooldown_minutes": (120, 360),
       "max_open_positions":      (1, 3),
   }
   ```
   - Función `_clamp_llm_value()` rechaza overrides destructivos

3. **config.py** — Defaults reforzados:
   - `sl_atr_multiplier`: 1.0 → **1.2**
   - `tp_atr_multiplier`: 2.5 → **2.0**
   - `tp_fallback_pct`: 0.05 → **0.04**

4. **trading_loop.py:189-213** — Time stop más corto:
   - Era 48h → **24h**
   - Trailing activation: 65% → **40%**

5. **signal_generator.py:275** — Hold time fail-closed:
   - Ahora bloquea exit si la DB query falla
   - Antes permitía exit con fallback

6. **Supabase** — Config LLM anterior borrada (superseded)

## Validación post-fix

### Resultados 2026-04-05 → 2026-04-11 (13 trades)
- Win rate: **76.9%** (+40 pts)
- R-mult: **+0.62** (+0.90)
- P&L: **+$15.94** (+$34.68)
- SL hit %: 82% → 56% (-26 pts)
- TP hit %: 1% → 12% (+11 pts)
- Signal exit %: 15% → 31% (+16 pts)

**El post-mortem fue efectivo.**

## Lecciones

1. **LLM config needs a constitution** — guardrails duros que no puede cruzar
2. **ATR sin caps es peligroso** — siempre validar que el resultado es razonable
3. **Fail-closed > fail-open** — en trading, el default en error debe ser "no actuar"
4. **Post-mortems con data real** cambian la conversación vs debate teórico
5. **Un símbolo puede hundir el P&L completo** — BNB solo fue 45% de los trades pero 32% de la pérdida

## Links

- Commit: b9ed674 (2026-04-05)
- Archivos modificados: executor.py, signal_generator.py, config.py, trading_loop.py
- Data fuente: `positions` table en Supabase
