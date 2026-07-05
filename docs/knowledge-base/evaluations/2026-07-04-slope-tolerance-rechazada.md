# Evaluación 2026-07-04 — Tolerancia de pendiente del bull filter: RECHAZADA + observabilidad

- **Trigger:** el usuario pidió "correcciones para que el bot siga operando". Diagnóstico
  previo: 25 días sin operar (último trade 2026-06-10). Primera pregunta honesta —
  ¿es un bug o abstención correcta?

## Diagnóstico (systematic-debugging)

**NO es un bug.** El `bull_filter` de `03-donchian-bull` exige dos cosas: (1) `close > SMA720`
(media de 30 días en velas 1h) y (2) esa SMA **subiendo** vs 24 velas atrás. ETH cayó y arrastró
su SMA720 de $1838 → $1667 en dos semanas (-9%), así que la condición 2 fue "no" todo ese tiempo
→ bot en cash **por diseño** (sin el filtro, PF del backtest cae de 1.30 a 0.77).

Estado actual (2026-07-04): precio $1765.90, SMA720 $1667.63 (precio **+5.9%** sobre la media),
pero la SMA se movió **-0.0036%** en 24h (plana muerta) → condición 2 falla por un pelo. Punto de
inflexión: la media está por dar vuelta y el bot retoma solo en días si ETH aguanta.

## Hipótesis testeada: ¿la pendiente ESTRICTA (`>`) es demasiado frágil en inflexiones?

Ronda `--slope` en el backtest lab (24 meses, BTC+ETH). Se comparó `donchian_bull` (pendiente
estricta) contra tolerancias que aceptan una SMA plana o cayendo ≤t% en 24 velas.

| Variante | Trades | PF | PnL | DD | PF(A) / PF(B) |
|---|---|---|---|---|---|
| **donchian_bull (estricta, prod)** | 155 | **1.299** | **+$28.87** | $19.41 | 1.294 / 1.307 |
| slope_t10 (tolera −0.1%/24v) | 177 | 1.048 | +$5.62 | $24.21 | 1.008 / 1.095 |
| slope_t20 (tolera −0.2%/24v) | 188 | 1.061 | +$7.52 | $25.73 | 1.038 / 1.09 |
| slope_t50 (tolera −0.5%/24v) | 203 | 1.01 | +$1.28 | $35.70 | 0.99 / 1.035 |

## Decisión

**RECHAZAR la tolerancia. NO se toca el filtro.** Aflojar la pendiente agrega trades (155→203)
pero son trades basura: el PF se desploma de 1.30 a ~1.05 (apenas sobre breakeven), el PnL de
+$28.87 a casi cero, y el drawdown **empeora** ($19→$36). Es la trampa de parámetro-minado que el
KB advierte — la abstención de 25 días es la disciplina que produce el edge, no un defecto.

## Qué SÍ se entregó (mejora de funcionamiento sin comprometer el edge)

1. **Robustez verificada:** el camino de disparo de la entrada donchian ya está cubierto por tests
   (`test_donchian_entry_submits_on_breakout_in_bull`) — cuando el filtro dé vuelta, el bot dispara
   bien. 22/22 tests de la estrategia verdes.
2. **Observabilidad:** nueva `market_state.bull_market_diagnostics()` + telemetría enriquecida en
   `signal_generator`. El `risk_events` ahora dice *por qué* está en cash y *cuán cerca* de operar:
   `bull_filter_bear=1 | ETHUSDT: precio +5.9% vs SMA, pendiente -0.0036% (falta subir)`
   en vez del opaco `bull_filter_bear=1`. 3 tests nuevos.

## Verificación

- Backtest determinista reproducible: `python scripts/backtest-lab/lab.py --months 24 --slope`.
- Resultados crudos: `scripts/backtest-lab/results/lab_results_2026-07-05_0200.json`.
- Tests: 22/22 verdes en `test_donchian_strategy.py`. (7 fallos en la suite completa son
  pre-existentes y ajenos: `xgboost` no instalado local + test de settings con API key del `.env`.)

## Artefactos

- `scripts/backtest-lab/lab.py` (ronda `--slope`: columnas `bull_t10/t20/t50` + `slope_variants()`)
- `backend/app/services/market_state.py` (`bull_market_diagnostics`)
- `backend/app/services/signal_generator.py` (telemetría bull filter en el tick de rechazos)
- `backend/tests/test_donchian_strategy.py` (+3 tests)
