# Strategy 02 (Reversal Oversold) — Backtest Evaluation — 2026-06-02

- **Trigger:** usuario pidió "analizá las estrategias y adecualas si no están dando resultados".
- **Camino elegido:** implementar Strategy 02 (mean-reversal oversold) **backtest-first, gated OFF** — activar solo si el backtest valida edge.
- **Decisión:** `REJECT` — la reversión NO tiene edge. **No se implementa en el hot-path.**
- **Método:** `scripts/backtest-reversal.py` (datos públicos de Binance, simulador event-driven con SL/TP intrabar, fees 0.1%/lado + slippage 0.05%/lado).

## Por qué se evaluó

El doc `strategies/02-reversal-oversold.md` proponía formalizar el patrón "comprar oversold extremo contra-tendencia" motivado por **un solo trade** de +8.40% (ETH, 2026-04-11, RSI=16.7 en downtrend 66.8%). El propio doc advertía: *"Selection bias: un solo trade exitoso no valida la estrategia"* y *"Catching falling knives"*. Este backtest pone a prueba esa hipótesis sobre data real antes de tocar producción.

## Resultados (ETH+BTC, 1h, 240d full / 60d bear, datos a 2026-06-03)

| Ventana | Símbolo | Estrategia | Trades | WR% | PF | ret% | DD% | exp% | SL hits |
|---|---|---|---|---|---|---|---|---|---|
| full | ETHUSDT | mean_reversion_v2 | 10 | 30.0 | 0.441 | −6.6 | −8.9 | −0.66 | 0 |
| full | ETHUSDT | rsi_reversal | 56 | 46.4 | 0.747 | −19.1 | −31.9 | −0.33 | 0 |
| full | ETHUSDT | **deep_oversold_02** | 19 | 36.8 | **0.411** | −13.5 | −14.3 | −0.74 | 9 |
| bear | ETHUSDT | mean_reversion_v2 | 2 | 50.0 | 0.036 | −2.2 | −2.3 | −1.08 | 0 |
| bear | ETHUSDT | rsi_reversal | 12 | 50.0 | 3.173 | +8.1 | −1.5 | +0.67 | 0 |
| bear | ETHUSDT | deep_oversold_02 | 1 | 0.0 | 0.0 | −0.1 | 0.0 | −0.13 | 0 |
| full | BTCUSDT | mean_reversion_v2 | 5 | 20.0 | 0.012 | −4.7 | −4.4 | −0.95 | 0 |
| full | BTCUSDT | rsi_reversal | 52 | 30.8 | 0.316 | −45.8 | −46.5 | −1.14 | 0 |
| full | BTCUSDT | **deep_oversold_02** | 18 | 33.3 | **0.302** | −11.5 | −10.0 | −0.67 | 8 |
| bear | BTCUSDT | rsi_reversal | 11 | 27.3 | 0.170 | −13.0 | −13.8 | −1.23 | 0 |
| bear | BTCUSDT | deep_oversold_02 | 4 | 25.0 | 0.118 | −3.0 | −3.4 | −0.76 | 2 |

**Gate de activación:** PF>1.2 y expectancy>0 en AMBAS ventanas, con ≥20 trades.
**Lo pasa: ninguna.**

## Conclusiones

1. **`deep_oversold_02` (RSI<20) pierde en todas las ventanas con muestra suficiente** — PF 0.41 (ETH) / 0.30 (BTC). Casi la mitad de los trades (9/19 ETH, 8/18 BTC) mueren por SL: es *catching falling knives* confirmado empíricamente.
2. **El +8.40% del 11-abr fue suerte (selection bias)**, tal como el doc sospechaba. No es replicable como estrategia.
3. La única celda positiva (ETH bear, `rsi_reversal` PF 3.17, +8.1%) tiene solo **12 trades** y está dominada por time-stops (11/12), no por la tesis de reversión — ruido/overfit al rebote reciente. No concluyente.
4. **Combinado con la evidencia previa** (trend-momentum PF 30d 0.31, ya autobloqueado en `trending_down`): el régimen actual **no tiene una estrategia long con edge**. La acción correcta no es agregar una estrategia, es **no operar long este régimen** — que es lo que la 01 ya hace y lo que el Daily Strategist viene recomendando (PAUSE, conf 0.88 el 2026-06-02).

## Acciones

- ✅ `scripts/backtest-reversal.py` queda como harness reutilizable (backtest-first para futuras hipótesis).
- ✅ `strategies/02-reversal-oversold.md` → status `rejected` (backtest-negative).
- ❌ NO se implementa Strategy 02 en `signal_generator`. No es código muerto que perdería plata.
- ⏸️ Recomendación operativa: mantener el autobloqueo de la 01 / formalizar la pausa hasta flip a `trending_up`. La próxima búsqueda de edge debería explorar otros ejes (timeframe, short-side, o esperar régimen favorable), siempre backtest-first.

---
*Evidencia generada con `python scripts/backtest-reversal.py --days 240 --bear-days 60`. Reproducible.*
