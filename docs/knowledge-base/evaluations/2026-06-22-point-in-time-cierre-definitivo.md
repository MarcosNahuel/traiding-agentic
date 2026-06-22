# Evaluación 2026-06-22 — Point-in-time (anti-survivorship) + beta-neutral: cierre definitivo

- **Trigger:** el usuario pidió el "último experimento honesto" — el único ángulo que la auditoría
  del 2026-06-21 dejó abierto: cross-sectional con universo **point-in-time** (incluyendo monedas
  delistadas, mata el survivorship) + **beta-neutralización** (aísla alpha del beta de mercado).
- **Método:** `scripts/backtest-lab/xsectional.py` extendido. Universo = 24 sobrevivientes +
  6 delistados (LUNA, FTT, SRM, WAVES, ANT, OCEAN). LUNA/FTT cortados en su colapso (no capturar
  el relisting espurio). Manejo de delisting (la muerte cuenta como pérdida, no retorno 0).
  3 familias: long-only, long-short (market-neutral), long-only beta-neutral. DSR + bear hold-out.

## Decisión

**CERRAR DEFINITIVAMENTE la búsqueda de edge algorítmico en cripto.** Las 4 vías están agotadas
con rigor de validación: donchian (DSR 0.06), ratio-rotation (0.13), cross-sectional sobrevivientes
(0.51-0.55), cross-sectional point-in-time (0.25-0.56). El momentum cross-sectional tuvo alpha en
2021-2022 y **se arbitró** — en 2024-2026 está muerto (Sharpe 0.06-0.10). No reactivar trading.

## Evidencia

1. **LO** mejor Sharpe 1.0: beta de burbuja (2021 +2848%), bear −11.8%, **DSR 0.56.** No pasa.
2. **LS (market-neutral)** Sharpe 0.82, bear hold-out **+206%** (Sharpe 1.49) — pero ver punto 4.
   **DSR 0.38**, alpha muerto post-2022 (2024 0%, 2025 −38%, 2026 −29%).
3. **BN (alpha puro)** Sharpe 0.66, bear +116%, pero **el alpha se evapora post-2022** (bull
   2023-25 −1.2%), **DSR 0.25.** No pasa.
4. **El +206% en bear es mayormente humo no-ejecutable** (verificación determinista propia):

   | Universo | Bear 2021-22 totRet | Sharpe |
   |---|---|---|
   | Completo (30) | +206% | 1.49 |
   | Sin LUNA ni FTT (28) | +87% | 1.00 |
   | Solo sobrevivientes (24) | +26% | 0.54 |

   El **58% del bear viene de shortear LUNA/FTT en su colapso** — NO ejecutable: durante el
   desplome de Terra (may-2022) Binance suspendió/deslistó LUNA, funding de shorts impagable,
   sin liquidez para cubrir. El market-neutral protege en crisis, pero +26% (real) ≠ +206% (papel).
5. **Punto decisivo (independiente del bear):** en 2024-2026 todas las familias están muertas —
   LS Sharpe 0.10 (−7.4%), BN Sharpe 0.06 (−3.2%), PF ~1.0. Aunque el bear fuera real, **hoy no
   hay nada que operar.**

## Verificación

- Auditoría LLM multi-modelo (workflow) **falló por 529 Overloaded** (Codex devolvió placeholder,
  agy/Claude/síntesis caídos). NO se usó para concluir.
- La **verificación determinista propia** (descomposición del bear por universo + período reciente)
  es más fuerte que opinión de LLM: aritmética reproducible sobre los datos.
- Tests del lab: 7/7 verdes tras los cambios (delisting + beta-neutral).

## Qué se aprendió (valor del experimento)

- El **survivorship NO era el problema oculto** — incluir delistados mejoró el bear (el momentum
  captura colapsos vía short) pero no rescató el DSR.
- El **market-neutral SÍ protege en crisis** (real, modesto: +26% sobrevivientes), pero la parte
  espectacular era no-ejecutable.
- El **momentum crypto se arbitró**: tuvo edge en la era de dispersión 2021-2022, no en el
  mercado correlacionado-maduro de 2023-2026.
- **Conclusión estructural:** el edge algorítmico accesible a retail en cripto (long-only spot o
  long-short perps, momentum/breakout/reversión) no sobrevive validación honesta hoy. Cerrar.

## Artefactos

- `scripts/backtest-lab/xsectional.py` (point-in-time + delisting + beta-neutral)
- `results/xsectional_2026-06-22_*.json`
- Datos delistados en `results/xsec/` (gitignored)
