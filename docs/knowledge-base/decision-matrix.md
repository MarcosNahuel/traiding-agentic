# Decision Matrix — ¿Qué estrategia usar cuándo?

## Tabla principal

| Régimen actual | Volatilidad (ATR%) | Símbolo | Estrategia recomendada | Config override |
|---|---|---|---|---|
| `trending_up` estable | 0.5% - 3% | ETHUSDT | **01-trend-momentum** | default |
| `trending_up` estable | 0.5% - 3% | BTCUSDT | **01** (BTC tight caps) | `sl=1.0, tp=1.5` |
| `trending_down` conf<80% + RSI<20 | < 5% | ETHUSDT | **02-reversal** (idea) | no implementada |
| `trending_down` conf>85% | cualquiera | cualquiera | **NINGUNA** — blocked | - |
| `ranging_low_vol` | < 1% | BTCUSDT | **01** con caution | `tighter`, considerar pausa |
| `ranging_low_vol` | < 1% | ETHUSDT | **01** default | default |
| `ranging_high_vol` | > 1.5% | cualquiera | **02** o pausa | no implementada |
| `volatile` (crash) | > 5% en 1h | cualquiera | **PAUSAR** | `TRADING_ENABLED=false` |

## Reglas hard (no negociables)

1. **NUNCA BUY si `trending_down` confidence > 85%** (signal_generator.py:334)
2. **NUNCA más de 3 posiciones abiertas simultáneas** (config.py:37)
3. **NUNCA BUY si hold reciente < 180 min (cooldown post-close)** (signal_generator.py:55)
4. **NUNCA ejecutar signal exit antes de MIN_HOLD_MINUTES** excepto SL/TP/time stop (signal_generator.py:47)
5. **NUNCA permitir LLM overrides fuera de LLM_SAFE_BOUNDS** (signal_generator.py:62)

## Reglas soft (ajustables)

- Position size ETH: $100, BTC: $60 (edge-based sizing)
- SL/TP ATR por símbolo (BTC tighter)
- Breakeven gate adaptativo por ATR% del símbolo

## Checklist para reevaluación

Cuando el usuario pida reevaluar:

- [ ] Leer `current-market.md` (regenerar si > 1h)
- [ ] Verificar régimen actual de cada símbolo activo
- [ ] Consultar tabla arriba y seleccionar estrategia
- [ ] Revisar `evaluations/` para ver última decisión y qué cambió
- [ ] Mirar performance últimos 7 días (win rate, PF, DD)
- [ ] Identificar si hay drift (win rate cayendo, PF < 1)
- [ ] Recomendar: mantener, ajustar parámetros, cambiar estrategia, o pausar
- [ ] Guardar decisión en `evaluations/YYYY-MM-DD-HHMM.md`

## Red flags que obligan reevaluación inmediata

- 🚨 **Drawdown > $20** sin recuperación en 48h
- 🚨 **Win rate < 40%** en últimos 20 trades
- 🚨 **Profit factor < 0.8** en últimos 30 trades
- 🚨 **3 SL consecutivos** en el mismo símbolo
- 🚨 **Regime flip súbito** (trending → volatile)
- 🚨 **Slippage > 0.3%** promedio en 5 trades
