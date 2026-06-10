# Evaluación 2026-06-10 — Cambio de estrategia: 01-trend-momentum → 03-donchian-bull

- **Trigger:** pedido del usuario ("mejorar para que el sistema dé la mayor ganancia
  posible, de manera autónoma y probando") + propuesta del strategist 2026-05-31
  (`RECOMMEND_PAUSE`, PF 30d 0.31).
- **Método:** backtest lab offline (`scripts/backtest-lab/lab.py`) — réplica fiel de la
  estrategia productiva (régimen, entropy, perfiles, SL/TP ATR, trailing, cooldowns)
  sobre klines 1h reales de Binance. 5 rondas: réplica → arquetipos → master switch →
  sensibilidad → config exacta de prod.

## Decisión

**ADOPTAR `donchian_breakout` + bull filter + chandelier puro como estrategia default**,
solo ETHUSDT, detrás de config (`entry_strategy`, rollback = `legacy`).

## Evidencia clave (24 meses, 2024-06 → 2026-06)

1. **Legacy pierde estructuralmente:** PF 0.50 (592 trades). Coincide con live
   (all-time PF 0.65, mayo 0.31). No es el régimen: es la lógica — compra
   debilidad (RSI<50) con SL 1.2×ATR que el ruido 1h stopea; las entradas en
   `trending_up` son las PEORES (PF 0.30); costos 0.30% ≈ todo el edge bruto.
2. **Ninguna variante de parámetros salva al legacy** (entropy, ADX, MTF,
   ranging-blocks: PF 0.4–0.6). `baseline+bull_filter` tampoco (0.44).
3. **donchian_bull: PF 1.299, idéntico en ambas mitades** (1.294/1.307),
   155 trades, expectancy +$0.19, DD $19.
4. **El bull filter es el componente estructural:** sin él el mismo donchian
   da 0.77. En bear, TODA estrategia long-only pierde → cash es la posición.
5. **Sensibilidad en meseta:** don 40/55/70 → 1.24/1.30/1.37; chandelier
   2.5/3.0/3.5 → 1.05/1.30/1.20; SL 1.5/2.0/2.5 → 1.24/1.30/1.18.
6. **Config exacta de prod validada:** TP cap 15% → PF 1.31 ✔; SMA600 → 1.06 ✘
   (por eso `bull_sma_bars=720` y `kline_backfill_days=45`).
7. **ETH-only:** PF 1.88; BTC PF 0.60 → BTC sigue pausado.

## Cambios de código (rama `feat/donchian-bull-strategy`)

- `config.py`: bloque `entry_strategy` + parámetros donchian/bull/trailing.
- `services/market_state.py` (nuevo): `is_bull_market` (fail-closed),
  `donchian_breakout_level` (excluye vela en formación — sin esto el breakout
  jamás dispararía porque el collector upserta la vela abierta).
- `signal_generator.py`: `_evaluate_donchian_entry` + supresión de signal-exits
  en modo donchian.
- `executor.py`: SL 2×ATR + TP cap 15% para donchian (legacy intacto).
- `trading_loop.py`: trailing `chandelier_pure` (ratchet sin progress gate).
- `strategist/prompts/data_agent.md`: SL>entry en LONG = trailing asegurando
  ganancia (falso positivo del informe 2026-05-31, no un bug).
- Tests: `test_donchian_strategy.py` (19 tests). Suite backend: 248 passed
  (6 fallas preexistentes en main: ml_baselines/daily_analyst, deps locales).

## Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Overfitting de selección de variante | Validación en mitades disjuntas + meseta de sensibilidad + arquetipo clásico (turtle) |
| Bot inactivo largos períodos (bear) | Es la feature, no un bug: mayo 2026 el legacy perdió -28% operando chop |
| DB sin 744 velas en deploy fresco | `is_bull_market` fail-closed (no opera) + backfill 45d |
| Deploy pipeline Dokploy roto (P0 de 2026-05-30) | **Sigue pendiente — sin esto, NADA llega al bot.** Verificar antes de esperar efecto |
| Pocas señales (~3/mes ETH) | Aceptado: frecuencia baja = menos sangrado por costos |

## Próximo checkpoint

Tras 4–6 semanas de operación (o ~12 trades): comparar distribución real vs
backtest (WR ~30%, winners largos). Si WR < 15% o DD > $25 → revisar fills/slippage.
