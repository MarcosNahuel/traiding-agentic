# Evaluación 2026-06-21 — Cross-sectional momentum: el último lead tampoco tiene edge

- **Trigger:** continuación del jury de estrategias. El ratio-rotation BTC↔ETH mostró que la
  dirección es trend RELATIVO (no mean-reversion) pero sobre 2 activos no pasa DSR. El único
  camino con n suficiente era cross-sectional sobre cesta amplia (`Taming-The-Factor-Zoo`).
  Pedido: "realiza todos los testing y experimentos necesarios para dejarlo funcionando".
- **Método:** `scripts/backtest-lab/xsectional.py` (nuevo) — momentum cross-sectional sobre
  24 alts (1d, 2020-09→2026-06, ~2120 días, descarga de data-api.binance.vision SIN geobloqueo).
  Grid de 24 variantes (lookback × hold × k × long-only/long-short), ejecución **lag-1**, filtro
  de **liquidez** (ADV≥$5M/30d), costos 0.15%/leg, walk-forward por régimen + Deflated Sharpe +
  bear hold-out 2021-2022 **real**. Verificación adversarial multi-modelo (Codex+agy+Claude).

## Decisión

**NO implementar. Cerrar la búsqueda de edge en este lab como `no-edge` (confirmado robusto).**
No reactivar trading real. El bot queda en testnet/observación. El edge no existe en ninguna
de las vías testeadas (donchian-bull DSR 0.06, ratio-rotation DSR 0.13, cross-sectional DSR 0.55/0.51).

## Evidencia (con ejecución realista lag-1 + liquidez)

1. **Long-only** mejor (lb30/h7/k5): Sharpe 0.87 pero es **beta de la burbuja 2021** (+1693%
   ese año), 2022 −73%, **bear hold-out 2021-2022 = −52%**, maxDD 75%. **DSR 0.55.** No pasa.
2. **Long-short (market-neutral, la tesis "ganar en bajas")** mejor (lb30/h14/k5): Sharpe 0.59.
   **Protege en bear** (maxDD 49% vs 75% del LO) pero igual pierde (bear −38%); y se desinfló
   post-burbuja: 2024 −39%, 2025 −41%, 2026 −26%. **DSR 0.51.** No pasa.
3. **El clavo final, independiente del DSR:** el hold-out post-burbuja 2023-2026 (sin 2021)
   entierra ambos — LO −27%, LS −39% acumulado. Pierden plata fuera de la burbuja.
4. `sharpe_obs/periodo` (0.12) < `E[max sharpe por azar entre 24 trials]` (0.11) → el "mejor"
   no se distingue de lo que sacarías buscando al azar.

## Verificación adversarial (Codex + agy/Gemini + Claude) — `confirmado_robusto`

- Los 3 reprodujeron los números exactos end-to-end. **Cero bugs críticos.**
- **Sesgos detectados, TODOS a favor del edge** (corregirlos refuerza el "no"): survivorship
  (universo = sobrevivientes), `fillna(0)` en delistados, long-short sin funding de perps,
  ejecución lag-0. Se aplicaron los fixes ejecutables (lag-1, filtro de liquidez real, maxDD
  contemporáneo) y el veredicto se mantuvo/reforzó (Sharpe LO 1.06→0.87).
- **Punto estadístico (agy):** los 24 trials están correlacionados (ρ≈0.47, n_eff≈2); con
  n_trials=2 el DSR subiría a ~0.98. PERO: (a) el multiple-testing honesto empuja n_trials
  HACIA ARRIBA (universo, fecha, ratio_rotation previo) no a 2; (b) el gate exige además
  bear>0, que falla; (c) el post-burbuja con Sharpe negativo mata el edge sin DSR. No rescata.

## Qué quedó "funcionando"

- Lab de investigación endurecido y **reproducible**: `xsectional.py` (lag-1 + liquidez + DSR +
  hold-out por régimen), `ratio_rotation.py` (doble-slippage corregido), y
  `test_backtest_lab.py` (**7 tests de propiedad: no look-ahead, DSR castiga ruido, filtro de
  liquidez, half-life** — todos verdes).
- Datos descargados y cacheados en `results/xsec/` (24 alts, 5+ años).
- El pipeline para validar CUALQUIER estrategia futura con el gate honesto (DSR≥0.95 + bear>0)
  está listo. El sistema de validación funciona: desinfló 3 "edges" que se veían robustos.

## Ángulos honestos no agotados (baja probabilidad, documentados)

- Universo point-in-time **incluyendo delistados** (mata survivorship de verdad).
- Long-only **beta-neutralizado** (restar la cesta): Claude lo probó → único con bear>0 (+0.40)
  pero Sharpe lejísimo de DSR.
- Vol-targeting + neutralización de beta-BTC rolling. Improbable que cambie el orden de magnitud.
- **Conclusión honesta:** no se prueba que el momentum crypto NO tenga edge en general; sí que
  los diseños accesibles a este lab (cesta de mainstream, retail, costos reales) no lo tienen.

## Ticket abierto (deuda, fuera de scope)

- **`lab.py:331-336` — look-ahead intrabar** (Codex): el motor horario chequea `nxt.low/high`
  (vela i+1) y decide el exit por señal al `row.close` (vela i) en la misma iteración → orden de
  eventos mezclado. Contamina TODOS los backtests horarios del donchian-bull (el PF 1.30 ya era
  dudoso por DSR 0.06; esto agrega otra razón). Corregir el orden de eventos + re-validar donchian
  es un sprint aparte. Ver `research/gaps.md`.
