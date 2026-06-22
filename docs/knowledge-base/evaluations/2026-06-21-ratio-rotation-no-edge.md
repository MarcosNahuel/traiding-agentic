# Evaluación 2026-06-21 — Ratio-rotation BTC↔ETH: ni pairs ni su espejo pasan el DSR

- **Trigger:** pedido del usuario — investigar repos de KidQuant (Pairs-Trading-With-Python,
  Taming-The-Factor-Zoo) con jury multi-modelo (Codex+Gemini/agy+Claude) para "encontrar la
  estrategia ganadora". Tesis del usuario: *"incluso en bajas se gana con market-neutral /
  ciclos diarios"* (convergencia del spread, ortogonal a la dirección).
- **Método:** (1) jury multi-modelo sobre los repos; (2) experimento de costo/riesgo cero
  `scripts/backtest-lab/ratio_rotation.py` sobre los parquets 24m ya cacheados
  (BTC+ETH 1h, 2024-06→2026-06, 17.280 velas). Dos modos × dos señales × grid 9 =
  36 trials, con costos reales del lab (0.15%/leg) y Deflated Sharpe sobre el ganador.

## Decisión

1. **NO implementar pairs trading clásico (mean-reversion del ratio).** Muerto en BTC-ETH:
   el ratio NO revierte en escala explotable (half-life ~83 días, y varía 2× entre mitades →
   no estacionario). La mean-reversion compra "ETH barato" mientras ETH se desploma vs BTC.
2. **NO implementar el momentum del spread** pese a su PF aparente: **no pasa el DSR** (0.13).
3. **NO migrar a perps todavía.** El gate del jury (edge market-neutral robusto) no se cumple.
4. **Próximo lead con potencial real:** cross-sectional momentum sobre una **cesta amplia**
   (10-20 alts), no 2 activos — donde el trend-factor tiene n suficiente y respaldo académico
   (esto es lo de `Taming-The-Factor-Zoo`). Requiere datos nuevos + más historia + DSR.

## Evidencia clave

1. **Benchmarks (neto):** BTC −6.1%, ETH −54.4%, 50/50 −$30.54 sobre el período. ETH
   underperformó masivamente a BTC → cualquier "edge" que sea "estar en BTC" es beta/régimen.
2. **Mean-reversion (la tesis del usuario / pairs clásico) PIERDE sistemático:** spread
   long/short PF 0.25–0.49 (Sharpe −1.5 a −3.4); rotation long-only PF 0.39–0.79. Todas las
   9 variantes, ambas mitades. El half-life de 83h… 83 **días** lo explica: no hay reversión.
3. **El espejo (momentum/trend del spread) gana donde la reversión pierde** — confirma que el
   par es tendencial, no mean-reverting (y valida que la simulación no tiene bug de signo).
   Mejor: `momentum spread w720/z1.5` → PF 2.128, Sharpe 1.16, +$77, DD $26, **robusto A/B
   (PF_A 2.27 / PF_B 2.00)**.
4. **PERO no sobrevive el multiple testing:** Deflated Sharpe con n_trials=36 honesto →
   `sharpe_obs/trade=0.188 < E[max por azar]=0.316` → **DSR = 0.134** (gate 0.95).
   `PSR_vs_0=0.947` es la trampa clásica (mira una estrategia, ignora que se eligió entre 36).
   Idéntico patrón a donchian_bull (DSR 0.06) y al notebook de KidQuant (255 windows in-sample).
5. **Muestra insuficiente + un solo régimen:** n=37 trades del ganador, todos en el régimen
   secular ETH-debilidad 2024-26. Por trimestre es mixto (rojos: 2024-Q4 −$26, 2025-Q4 −$14).
   Con 37 trades el IC del Sharpe cruza 0 holgado.

## Veredicto del jury (Codex+agy+Claude)

Pairs trading clásico = inviable (equities, requiere short, cointegración crypto frágil, 4
patas empeoran costos). Los repos de KidQuant son in-sample sin OOS — el overfit que el DSR
caza. La tesis market-neutral es cierta en teoría pero los Sharpe altos de papers asumen short
gratis + fees de derivados, no 0.15%/lado spot. (Codex no entregó reporte; veredicto sobre 2/3.)

## Qué quedó probado

- La dirección correcta NO es mean-reversion (pairs) sino **trend/momentum relativo** — pero
  sobre 2 activos y 1 régimen no alcanza para edge estadístico.
- El sistema de validación (DSR + robustez A/B + half-life) funciona: desinfló un PF 2.1 que
  se veía robusto. **El fallo no es la metodología; sería volver a operar tras un DSR bajo.**

## Pendiente

1. **Hold-out bear 2021-2022 real:** los parquets 24m no llegan; descargar desde máquina con
   red (el proxy de dev bloquea Binance). Confirma si el momentum del spread es alpha o
   "ETH-bajó-y-le-pegamos".
2. **Cross-sectional sobre cesta (10-20 alts, 5 años):** el único camino con n suficiente para
   que el trend-factor pase DSR. Descargar universo + adaptar `ratio_rotation` a ranking
   cross-sectional + validar con `oos_validate`. Es trabajo de datos, no de params.

## Artefactos

- `scripts/backtest-lab/ratio_rotation.py` (nuevo, standalone, no toca prod)
- `scripts/backtest-lab/results/ratio_rotation_2026-06-21_*.json`
