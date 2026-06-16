# Evaluación 2026-06-16 — Validación OOS: el edge donchian-bull NO sobrevive

- **Trigger:** pedido del usuario ("revisá cómo están los trading, si dan ganancia
  entrá en bucle de control de logs y mejorá las fallas"). La condición *"si dan
  ganancia"* **no se cumple** → en vez del bucle de operación se hizo diagnóstico +
  validación, alineado con la regla data-driven (no features sin edge probado).
- **Método:** (1) reconocimiento sobre la DB real (positions, risk_events, configs);
  (2) sprint diagnóstico ultracode read-only (26 agentes, 4 dimensiones +
  verificación adversarial); (3) validación OOS nueva (`scripts/backtest-lab/oos_validate.py`):
  walk-forward anclado + Probabilistic/Deflated Sharpe (Bailey & López de Prado) +
  breakdown por año.

## Decisión

1. **NO reactivar trading real.** El PF 1.30/1.88 in-sample es overfitting de
   selección, no edge. Dejar el bot en testnet acumulando trades OOS reales
   (hacen falta >100 trades ETH en vivo).
2. **NO modificar la estrategia.** Ninguna de las 15 variantes pasa el filtro DSR.
   Cualquier "mejora" de params sería elegir otro overfit.
3. **NO tocar el `bull_filter`.** Es by-design (el bot plano en bear es lo correcto),
   y es el único componente que aporta — pero aporta *defensa de capital*, no alpha.
4. **Arreglar el bug de dust** (independiente del edge) → PR #4.

## Evidencia clave

1. **Resultados reales (testnet):** acumulado legacy ~−29 USDT. La estrategia nueva
   (donchian-bull, ETH-only, activa desde 06-10) tomó **1 trade en 6 días** (+0.34)
   y luego **10.140 rechazos `bull_filter_bear=1`**: el bot no operó. Vivo pero plano.
2. **Deflated Sharpe = 0.06** (24m ETH). El Sharpe/trade observado (0.157) es *menor*
   que el E[max Sharpe por azar] entre 15 trials (0.299). PSR-vs-0 = 0.955 es la trampa
   clásica: mira una estrategia e ignora que se eligió entre ~28 variantes.
3. **Ninguna variante sobrevive:** de las 15 del lab, mejores DSR = momentum_trail_bull
   0.138 y donchian_bull 0.064; el resto ≈0. Sin `bull_filter` todas pierden fuerte
   (baseline −93, cur_rr −131).
4. **El PnL es concentración, no edge:** walk-forward OOS +$24.85 viene **todo de un
   trimestre** (2025-06, +$32); los dos trimestres recientes: +$5 y **−$10.4**.
   Por año: 2024 +$5.7, 2025 +$44.9 (todo el profit), **2026 YTD −$4.15 (ya pierde)**.
5. **Selección estable (lo único bueno):** donchian_bull fue elegida 4/4 folds — es
   consistentemente "la mejor disponible", pero "la mejor disponible" no tiene edge
   significativo.

## Revisión de la decisión 2026-06-10

La evaluación previa listó "overfitting de selección de variante" con mitigación
"validación en mitades disjuntas + meseta de sensibilidad". **Esa mitigación era
insuficiente:** las mitades A/B pertenecen al *mismo* período de optimización y ambas
eran visibles al elegir la ganadora. La validación OOS genuina (hold-out temporal +
corrección por multiple-testing) muestra que el edge no se distingue del azar. La
estabilidad de la meseta de sensibilidad sigue siendo cierta — pero estabilidad ≠ edge.

## Bug de dust (P0) — corregido en PR #4

- **Root cause:** `trading_loop._execute_sl_tp` (fast-loop, auto-approved, saltea
  validación) armaba `SELL MARKET` con la cantidad residual (0.0001 ETH ≈ $0.18) sin
  chequear minNotional → Binance 400 → como la posición seguía `open`, el loop la
  regeneraba cada tick: **6697 `execution_error` critical** (05-31 → 06-09).
- **Fix:** `binance_utils.meets_min_notional/is_dust` (NOTIONAL=5 USDT);
  `_execute_sl_tp` hace write-off (cierra sin orden) si la venta sería dust;
  `risk_manager` rechaza exits dust (defensa en profundidad). `test_dust_writeoff.py`.
- Latente hoy (bot plano, 0 capital en riesgo) pero limpia el ruido de críticos.

## Pendiente

- **Bear 2022 (test de régimen más fuerte):** el entorno de dev no llega a Binance
  (proxy intercepta TLS → 403). Correr desde máquina con red:
  ```
  python scripts/backtest-lab/oos_validate.py --months 60 --symbol ETHUSDT \
    --train-min-months 18 --step-months 6 --min-train-trades 10
  ```
  Esto confirma si el `bull_filter` realmente saca al bot del mercado en un bear
  secular (separa alpha de breakout de beta-timing "crypto subió y estuvimos long").

## Próximo checkpoint

No tocar params ni reactivar real hasta: (a) el bear 2022 confirme que el bull_filter
protege, **y** (b) >100 trades ETH OOS en vivo con DSR > 0.95. Sin ambas, la posición
correcta es testnet + cash.
