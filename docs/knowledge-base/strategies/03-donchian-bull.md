# 03 — Donchian Breakout + Bull Filter (ACTIVA desde 2026-06-10)

## Tesis

Comprar **fuerza** (breakout del máximo de 55 velas 1h), solo cuando el régimen
macro es alcista, y dejar correr al winner con trailing chandelier. Es la
estrategia turtle clásica adaptada a spot crypto.

Reemplaza a `01-trend-momentum`, que compraba **debilidad** (RSI<50) con SL
ajustado — backtest 24 meses: PF 0.50 (pierde estructuralmente; los costos de
0.30% round-trip se comen el edge bruto ≈ 0).

## Reglas

**Entrada (LONG):**
1. Master switch alcista: `close > SMA(720 velas 1h)` **y** SMA subiendo
   (vs 24 velas atrás). Sin esto → bot en cash. *Es el componente que más
   PF aporta: sin él 0.77, con él 1.30.*
2. Breakout: precio actual > máximo de las últimas 55 velas 1h **cerradas**
   (la vela en formación se excluye).
3. Régimen `low_liquidity` bloqueado; pausa por loss-streak (3 → 24h) activa.
4. Cooldowns estándar (señal 180min + post-close 180min).

**Salida:**
- SL inicial: `entry − 2×ATR(14)` (clamp 0.5%–3%).
- TP: cap lejano 15% (no es el exit esperado).
- Trailing chandelier puro: `SL = max(SL, precio − 3×ATR)` en cada tick,
  sin gate de progreso. **Sin exits por señal** (RSI overbought cortaba los
  winners que pagan la estrategia).

## Evidencia (backtest lab, 24 meses 2024-06 → 2026-06, BTC+ETH 1h)

| Métrica | Valor |
|---|---|
| Profit factor | **1.299** (mitad A: 1.294 / mitad B: 1.307) |
| Trades | 155 (>100, muestra suficiente según regla KB) |
| Win rate | 28.4% (pocos winners grandes — perfil trend-following normal) |
| Expectancy | +$0.186/trade (notional $60–80) |
| Max drawdown | $19.41 |
| Sensibilidad | Donchian 40/55/70, chandelier 2.5–3.5, SL 1.5–2.5: todo PF > 1.05 (meseta) |
| TP cap 15% | PF 1.313 (no daña) |
| SMA600 en vez de 720 | PF cae a 1.06 → **se requiere SMA720** (45d backfill) |

**Por símbolo:** ETHUSDT PF 1.88 (+$46, DD $12) / BTCUSDT PF 0.60 (pierde).
→ **Operar SOLO ETHUSDT** (`quant_symbols=ETHUSDT`, ya era el default).
BTC queda en pausa también bajo esta estrategia.

Reproducir: `python scripts/backtest-lab/lab.py --months 24 [--sensitivity|--prod]`
Resultados crudos: `scripts/backtest-lab/results/`.

## Config (backend/app/config.py)

```
entry_strategy=donchian_breakout   donchian_entry_bars=55
bull_filter_enabled=True           bull_sma_bars=720  bull_slope_bars=24
donchian_sl_atr_mult=2.0           donchian_tp_max_pct=0.15
trail_mode=chandelier_pure         trail_chandelier_mult=3.0
kline_backfill_days=45
```

Rollback: `ENTRY_STRATEGY=legacy` restaura el comportamiento anterior completo.

## Límites honestos

- **No garantiza ganancia**: PF 1.3 es expectativa positiva histórica, no
  certeza futura. En bear el bot NO opera (eso ya es ganancia vs. el legacy,
  que sangró -28% en mayo 2026 operando chop).
- Backtest asume fills a precio de SL/TP con slippage 0.05% — gaps reales
  pueden ser peores.
- ETH-only son 67 trades en 24 meses (~3/mes): pocas señales, paciencia.
- Riesgo de selección de variante: mitigado con validación en mitades
  disjuntas + sensibilidad en meseta + arquetipo clásico (no parámetro-minado).
