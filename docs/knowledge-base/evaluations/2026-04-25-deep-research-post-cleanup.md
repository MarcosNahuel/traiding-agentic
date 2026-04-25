# Deep Research - Trading Agentic Bot

Fecha: 2026-04-25  
Estado: post-cleanup, pre-mainnet  
Repo: `github.com/MarcosNahuel/traiding-agentic`  
Branch asumida: `main`

## Resumen Ejecutivo

El sistema tiene una base de ingenieria razonable para operar en testnet: FastAPI backend, Supabase compartida, ejecucion directa contra Binance Spot Testnet, reconciliacion, circuit breaker, SL/TP fail-closed con drift check, risk events, cooldown persistente y un set amplio de indicadores. El problema no es que falten piezas basicas de bot. El problema es que todavia no existe una capa de evaluacion y observabilidad suficientemente rigurosa para separar un edge real de ruido, ni una arquitectura de estrategia que aproveche las fuentes de alpha mas defendibles en crypto spot 1h.

Con 80 trades cerrados, win rate 47.5%, P&L practicamente flat con drift negativo, 78% de exits por SL y ningun variant rentable en replay V0-V3, la conclusion honesta es: la familia actual Trend-Momentum Multi-Filter no tiene edge demostrado. Partial exit no es el bottleneck. El foco debe moverse a calidad de entradas, evaluacion walk-forward y seleccion dinamica de activos.

La recomendacion de mayor impacto para un dev solo + Claude es:

1. Corregir el pipeline de CI/CD para que `main` este protegido por tests antes de build/deploy.
2. Implementar un reporte walk-forward reproducible con OOS rolling, PBO y Deflated Sharpe.
3. Congelar estrategia/version/config por run y guardar trazabilidad completa decision -> proposal -> order -> fill -> position -> exit.
4. Integrar derivatives data como veto/filtro, no como señal magica.
5. Pivotar entradas hacia cross-sectional momentum/lead-lag en 5 simbolos liquidos, con router por regimen.
6. Mantener mainnet bloqueado hasta pasar un gate cuantitativo explicito.

---

## Bloque 1 - Workflow / Operacional

### Tabla de Prioridades

| Prioridad | Gap concreto | Accion recomendada | Costo estimado |
|---|---|---|---:|
| P0 | CI no protege `main`: `ci.yml` corre sobre `master`; `main` solo build/push backend | Cambiar CI a `main`, hacer que Docker build dependa de pytest/lint/build, y bloquear deploy si falla replay critico | 0.5-1 dia |
| P0 | Riesgo de usar vela no cerrada en live y backtest | Persistir `is_closed`, filtrar `close_time < now - safety_lag`, y hacer que backtest/live usen la misma regla | 1 dia |
| P0 | Trazabilidad incompleta de decision a ejecucion | Agregar `decision_trace_id` con snapshot de indicadores, regimen, thresholds, version estrategia, precio fuente, proposal, order, fill y exit | 2-4 dias |
| P0 | Backtesting actual no decide capital | Crear runner rolling OOS + PBO/DSR + sensibilidad fees/slippage, no solo benchmark single-window | 4-7 dias |
| P1 | Riesgo runtime basado en notional, no en perdida potencial al stop | Implementar `portfolio_risk_at_stop_usd = sum((entry - SL) * qty)` y ATR sizing real | 2-3 dias |
| P1 | `derivatives_snapshot` no existe integrado | Crear cliente read-only Binance Futures y usarlo como veto/filtro | 2-4 dias |
| P1 | Observabilidad de ejecucion incompleta | Medir slippage, fill latency, order unknown, retry/dead-letter, divergencias de reconciliacion | 2-3 dias |
| P2 | Falta data catalog reproducible | Guardar raw + normalized data versionada por run, estilo catalogo Parquet | 1-2 semanas |
| P2 | No hay control estadistico de data snooping | Registrar todos los trials, tambien los fallidos, con dataset hash y config hash | 3-5 dias |

### a) Observabilidad y Diagnostico

El sistema ya tiene elementos valiosos: `risk_events`, reconciliacion periodica, dead letters, cooldown persistente, signal rejection counters y diagnosticos de drift. Eso lo diferencia de un bot amateur. Pero antes de mainnet falta una capa de observabilidad orientada a auditoria cuantitativa, no solo a logs.

El dashboard critico debe mostrar el funnel completo por simbolo y por vela:

`symbols_seen -> indicators_ok -> regime_allowed -> entry_profile_passed -> risk_passed -> proposal_created -> order_filled -> exit_reason`.

Hoy el sistema puede decir que hubo rechazos, pero todavia no alcanza para contestar con precision: "BTCUSDT en la vela 2026-04-25 14:00 UTC fue bloqueado porque entropy_ratio=0.812 con threshold=0.80, strategy_version=X, config_hash=Y". Esa respuesta debe salir de la base, no de reconstruir logs a mano.

Metricas P0:

| Categoria | Metrica | Umbral de alerta |
|---|---|---|
| Data freshness | `kline_lag_seconds` por simbolo/timeframe | 1h lag > 75 min |
| Data correctness | `open_candle_used_count` | cualquier valor > 0 |
| Precio | `price_source_drift_bps` direct vs proxy/fallback | > 30 bps warning, > 100 bps critical |
| Loop runtime | `fast_loop_gap_seconds` | > 10s en fast loop |
| Senales | `signal_eval_duration_ms` | p95 > 5s |
| Exchange | `binance_latency_ms` | p95 > 2s |
| DB | `supabase_latency_ms` | p95 > 2s |
| Ejecucion | `order_submit_to_fill_ms` | > 30s critical |
| Ejecucion | `slippage_bps` por fill | p95 > 20 bps |
| Ejecucion | `commission_bps` real | cambio inesperado |
| Estado | `reconciliation_divergences` | cualquier valor > 0 |
| Riesgo | `risk_at_stop_usd` agregado | > budget diario |
| Performance | `strategy_version_pnl`, `regime_pnl`, `symbol_pnl` | rolling PF < 1 |

Alertas concretas:

- Kline atrasada o incompleta.
- Señal generada sobre vela no cerrada.
- Direct price fetch falla 3 ticks consecutivos.
- Divergencia Binance vs DB.
- Orden en estado unknown mas de 30s.
- Dead letter.
- Slippage p95 > 20 bps.
- Daily realized loss > 1R portfolio.
- Drawdown live > 2x max drawdown OOS esperado.
- Tres losers consecutivos por simbolo, ya existe parcialmente.

La unidad de auditoria debe ser `decision_trace_id`. Cada propuesta debe guardar:

- `decision_trace_id`
- `strategy_family`
- `strategy_version`
- `config_hash`
- `dataset_snapshot_id` o latest candle ids usados
- indicadores usados
- regimen y confianza
- derivatives snapshot si aplica
- thresholds efectivos, incluyendo overrides del LLM ya clampeados
- precio usado y fuente
- risk checks
- motivo de aceptacion o rechazo

Sin esto, cada sprint termina discutiendo intuiciones. Con esto, cada cambio se puede medir.

### b) Walk-forward / Backtesting

El backtester actual basado en VectorBT es util como smoke test y barrido rapido. VectorBT esta diseñado para analizar muchas estrategias rapido mediante pandas/NumPy, Numba y Rust ([vectorbt docs](https://vectorbt.dev/)). Ese poder es util, pero tambien aumenta el riesgo de selection bias si no se registran todos los trials.

Arquitectura propuesta:

| Tabla/artefacto | Contenido |
|---|---|
| `research_runs` | `run_id`, dataset hash, rango temporal, universo, fees, slippage, codigo git SHA, strategy registry version |
| `variant_results` | una fila por variante probada, incluso perdedora |
| `oos_folds` | train/validation/test dates, metrics, trades, equity, DSR, PSR, PBO inputs |
| `trade_replay_events` | entry, exit, MFE, MAE, +1R touch, -1R touch, exit counterfactual |
| `data_snapshots` | simbolos, timeframe, source endpoint, row count, gap count, checksum |

Protocolo minimo:

1. Dataset congelado: 12-24 meses de klines production Binance, no testnet.
2. Universe congelado por run: primero 5 simbolos liquidos.
3. Rolling OOS:
   - 180 dias train.
   - 30 dias validation.
   - 30 dias test.
   - embargo de 24-48h entre ventanas para evitar leakage por labels cercanos.
4. Final holdout untouched de 90 dias.
5. Costos:
   - fee base 10 bps round-trip si aplica a spot.
   - slippage fijo conservador 5-10 bps.
   - stress slippage 20 bps.
6. Reportar por fold:
   - total trades
   - expectancy por trade
   - Profit Factor
   - Sharpe
   - Sortino
   - max drawdown
   - hit rate
   - exposure time
   - turnover
   - avg MAE/MFE
   - % trades que tocan +1R antes de -1R
   - performance por regimen y simbolo

Para controlar overfitting:

- PBO con Combinatorially Symmetric Cross Validation o CPCV.
- Deflated Sharpe Ratio para corregir multiples pruebas y no-normalidad.
- Registrar numero efectivo de trials.
- No elegir variante por mejor Sharpe aislado; elegir por estabilidad entre folds.

La literatura sigue siendo relevante aunque los papers de PBO/DSR sean previos a 2023. Bailey y Lopez de Prado proponen Deflated Sharpe para corregir selection bias, backtest overfitting y no-normalidad ([SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551)). Un paper 2024 compara metodos OOS en la era ML y encuentra superioridad de CPCV para mitigar overfitting, con menor PBO y mejor DSR ([ScienceDirect 2024](https://www.sciencedirect.com/science/article/abs/pii/S0950705124011110)).

### c) Risk Management Runtime

El runtime tiene controles correctos para un sistema testnet: max open positions, max per symbol, account balance, utilization, daily loss, entropy, regimen, position sizing y SL/TP fail-closed. Pero faltan chequeos que importan cuando hay dinero real:

| Chequeo ausente | Por que importa | Implementacion |
|---|---|---|
| Riesgo agregado al stop | Notional no mide perdida esperada | `sum(max(entry - stop, 0) * qty)` por portfolio |
| Correlacion / BTC beta | 5 posiciones crypto pueden ser una sola apuesta | Cap de exposicion BTC-equivalent |
| Liquidez pre-trade | Slippage puede borrar edge | Chequear depth/top of book contra notional |
| Idempotency key | Evita duplicados ante timeout/retry | `newClientOrderId = decision_trace_id` |
| Order unknown handling | Binance puede no confirmar estado inmediatamente | Estado `unknown`, reconciliar antes de reintentar |
| Exchange filters | Evita rechazos por step size/min notional | Cachear `exchangeInfo` y validar pre-order |
| Kill switch persistente | Reinicio no debe olvidar estado critico | `runtime_locks` en DB |
| Circuit breaker portfolio | 3 losers por simbolo no cubre drawdown agregado | Lock por dia y por estrategia |
| Position age by strategy | Time stop debe ser parte de la estrategia versionada | Guardar max hold en proposal |

Hummingbot tiene un patron operativo importante: sus conectores trackean la orden antes o durante el submit para no perder estado si la API se demora o falla ([Hummingbot architecture](https://hummingbot.org/blog/hummingbot-architecture---part-1/)). Para este repo, el equivalente es que `execute_proposal` cree/registre un estado `order_pending_ack` con `clientOrderId` antes del submit y que reconciliacion lo cierre.

### d) CI/CD y Deploys

Gap concreto observado: `.github/workflows/ci.yml` corre en `master`, pero el proyecto usa `main`. El workflow que si escucha `main` es `build-backend.yml` y solo construye/pushea imagen. Resultado: se puede deployar backend sin que corra pytest en la branch real. Esto es P0.

Pipeline recomendado:

1. En push/PR a `main`:
   - frontend lint/typecheck/build.
   - backend pytest.
   - tests criticos de trading: signal generator, executor atomic, SL/TP, reconciliation, drift guard, backtester strategies.
   - replay smoke fijo con dataset chico congelado.
2. Solo si todo pasa:
   - build Docker.
   - tag por SHA y `latest`.
3. Dokploy:
   - deploy por SHA.
   - post-deploy smoke:
     - `/health`
     - Supabase read/write test
     - Binance testnet `/time`
     - price fetch direct
     - no open divergences
4. Rollback:
   - mantener ultimo SHA estable.
   - no depender solo de `latest`.

Tambien conviene agregar un job nocturno manual/cron de research:

- backfill data.
- gap check.
- walk-forward report.
- publicar `.md` en `docs/knowledge-base/evaluations/`.
- no modificar thresholds automaticamente.

### e) Data Pipeline

El riesgo mas concreto es usar velas abiertas. `collect_latest` trae las ultimas 3 klines y `compute_indicators` toma la ultima fila. Binance Spot API documenta klines/candlesticks y market data endpoints ([Binance Spot API](https://developers.binance.com/docs/binance-spot-api-docs/rest-api/market-data-endpoints)). En live, la ultima vela puede no estar cerrada. En backtest, una vela OHLC completa incluye el high/low final. Esa diferencia puede producir lookahead involuntario.

Cambios:

- Agregar `is_closed BOOLEAN`.
- Calcular `is_closed = close_time < now_utc - interval_safety_lag`.
- `compute_indicators` debe usar solo closed candles.
- `run_backtest` debe usar el mismo loader.
- `technical_indicators.candle_time` debe corresponder a vela cerrada.

Validaciones:

| Validacion | Regla |
|---|---|
| OHLC | `low <= open, close <= high`; `high >= low` |
| Timestamp | monotonicidad exacta por interval |
| Gaps | contar missing candles |
| Duplicados | unique `(symbol, interval, open_time)` ya existe, pero reportar upserts |
| Volumen | flag `volume=0` o `quote_volume=0` |
| Drift historico | comparar exits con kline close/high/low |
| Source | guardar endpoint/base URL |
| Freshness | latest closed candle por simbolo |

Para derivatives data, Binance provee endpoints oficiales de funding, open interest y long/short ratio:

- Funding history: `GET /fapi/v1/fundingRate` ([docs](https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Get-Funding-Rate-History)).
- Open Interest: `GET /fapi/v1/openInterest` ([docs](https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Open-Interest)).
- Top trader long/short ratio: `GET /futures/data/topLongShortPositionRatio` ([docs](https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Top-Trader-Long-Short-Ratio)).

Algunos endpoints historicos tienen ventanas limitadas, por eso no alcanza con "lo consulto cuando lo necesito". Hay que persistir snapshots cada hora.

---

## Bloque 2 - Estrategia / Alpha

### Tabla de Prioridades

| Prioridad | Alpha a probar | Evidencia | Como implementarlo sin overfit | Costo |
|---|---|---|---|---:|
| P0 | Cross-sectional momentum / lead-lag en 5-10 simbolos | ML cross-section crypto 2024; cross-crypto predictability 2024 | Ranking long-only: top 1-2 activos, cash si score debil | 1 semana |
| P0 | Derivatives veto, no señal primaria | Funding/OI/long-short oficiales + papers funding | Percentiles rolling, no thresholds optimizados | 2-4 dias |
| P1 | Router por regimen | Momentum crypto sufre crash tails; regimen importa | Estrategia separada por regimen, P&L por regimen | 1-2 semanas |
| P1 | Mean-reversion en ranging | Reversal crypto 2024/2025 | Z-score/Bollinger + ADX bajo + funding crowding veto | 1 semana |
| P1 | ML meta-labeling LightGBM | Modelos simples funcionan bien en crypto cross-section | Predecir `hit +1R before -1R`, no `next logret` | 2 semanas |
| P2 | Funding cash-and-carry real | Funding arbitrage 2025 | Requiere Futures Demo, hedge, margin, liquidation logic | 3+ semanas |
| P2 | On-chain USDT/ETH flows | arXiv 2024 encuentra poder predictivo 1-6h | Solo si hay fuente barata y estable | 2-3 semanas |

### a) Estrategias Especificas con Evidencia

El primer pivot no deberia ser "mas filtros sobre BTC/ETH". El bot ya tiene RSI, ADX, MACD, ATR, SMA, EMA, Bollinger, Hurst, autocorrelacion, PPO, volume ratio y entropy. Agregar otro indicador tecnico probablemente solo aumenta grados de libertad. El cambio mas prometedor es pasar de time-series sobre dos simbolos a cross-sectional sobre un universo chico y liquido.

#### 1. Cross-sectional momentum long-only

Un paper 2024 sobre machine learning y cross-section de crypto usa mas de 500 coins/tokens, 40 caracteristicas y ocho modelos. Sus hallazgos principales son practicos para este bot:

- La predictibilidad existe en la cross-section.
- Los modelos simples son competitivos.
- Las variables importantes son precio, alpha pasado, momentum e iliquidez.
- El alpha viene principalmente del long leg, no del short leg.

Fuente: [Machine learning and the cross-section of cryptocurrency returns, International Review of Financial Analysis, 2024](https://www.sciencedirect.com/science/article/pii/S1057521924001765).

Esto encaja con spot long-only. En vez de preguntar "BTC sube?", preguntar "entre BTC, ETH, SOL, BNB, XRP, cual tiene mejor drift relativo ahora?".

Implementacion:

- Universo inicial: `BTCUSDT`, `ETHUSDT`, `SOLUSDT`, `BNBUSDT`, `XRPUSDT`.
- Features 1h:
  - retorno 1h, 3h, 6h, 12h, 24h
  - momentum rank cross-sectional
  - realized volatility 24h/72h
  - volume ratio
  - Amihud proxy o quote_volume inverse
  - distancia a SMA20/50
  - BTC lagged return
  - ETH lagged return
  - funding percentile si existe
- Señal:
  - comprar top 1 o top 2 si score > percentil 70 historico.
  - no comprar si todos los scores son debiles.
  - max 1 posicion por simbolo.
  - rebalance solo en vela cerrada.

No optimizar 20 thresholds. Usar ranking y percentiles rolling.

#### 2. Cross-cryptocurrency lead-lag

Un paper 2024 encuentra evidencia de que retornos rezagados de otras criptomonedas predicen retornos del activo focal, usando datos de Binance. La explicacion es difusion gradual de informacion y spillovers entre monedas.

Fuente: [Cross-cryptocurrency return predictability, Journal of Economic Dynamics and Control, 2024](https://www.sciencedirect.com/science/article/pii/S0165188924000551).

Implementacion simple:

- Para cada simbolo, calcular:
  - `btc_ret_1h_lag`
  - `eth_ret_1h_lag`
  - `market_ret_1h_lag` equal-weight del universo
  - `sector_or_peer_ret_lag` si luego hay mas simbolos
- Usar esos features en scoring o LightGBM.
- No operar si BTC y ETH tienen señales opuestas fuertes.

#### 3. Interacciones simples entre momentum, liquidez y riesgo

Un paper 2025 sobre interacciones cross-sectional en crypto encuentra numerosos efectos significativos, con especial importancia de liquidez, riesgo y retornos pasados.

Fuente: [Cross-sectional interactions in cryptocurrency returns, International Review of Financial Analysis, 2025](https://www.sciencedirect.com/science/article/abs/pii/S1057521924007415).

Para este bot:

`score = momentum_rank * liquidity_ok * volatility_not_extreme * regime_allowed`.

La idea es no aprender una red compleja con poca muestra, sino convertir evidencia robusta en filtros simples y auditables.

#### 4. Mean-reversion en regimen ranging

El bot detecta `ranging_low_vol` y `ranging_high_vol`, pero la estrategia activa sigue siendo trend-momentum con perfiles. Eso mezcla hipotesis distintas. La evidencia reciente muestra que reversals y atencion importan en crypto.

Fuente: [The reversal in the cryptocurrency market before and during the Covid-19 pandemic, PLOS ONE, 2024](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0304377).

Implementacion:

- Solo activa en `ranging_low_vol`.
- Entry:
  - z-score close vs SMA50 < -2
  - RSI < 30-35
  - ADX < 18-20
  - Bollinger lower touch
  - volume not dead
- Exit:
  - z-score vuelve a -0.25/0
  - RSI > 50-55
  - max hold 12-24h
  - stop por z-score extremo o ATR
- En `ranging_high_vol`, default cash hasta tener OOS propio.

#### 5. ML meta-labeling con LightGBM

El repo ya tiene LightGBM y walk-forward basico. El problema es el target. Predecir `logret_next` en 1h suele ser ruidoso. Dado que el diagnostico local encontro que 49% de trades toca +1R antes de cerrar, el target natural es:

`label = 1 si toca +1R antes de -1R dentro de N barras; 0 si no`.

Esto convierte ML en filtro de entradas, no en generador libre de señales.

Features:

- Indicadores existentes.
- Regimen.
- MFE/MAE historico por setup.
- Cross-sectional rank.
- Derivatives snapshot percentiles.
- Time features: hora UTC, dia semana.

Restricciones:

- Modelo simple: LightGBM o Logistic Regression.
- Walk-forward con embargo.
- Calibration plot.
- Threshold elegido en validation, evaluado en test.
- No usar transformers por ahora. Hay papers de transformers para crypto ([arXiv 2024](https://arxiv.org/abs/2403.03606)), pero para un dev solo son mas riesgo operacional y de overfit que ventaja.

### b) Confluencia con Derivatives Data

Derivatives data no debe entrar como oraculo. Debe entrar como veto y contexto de crowding.

Campos minimos de `derivatives_snapshot`:

- `funding_rate_current`
- `funding_rate_8h_avg`
- `funding_rate_24h_avg`
- `funding_percentile_90d`
- `oi_current`
- `oi_change_1h`
- `oi_change_24h`
- `long_short_ratio`
- `long_short_percentile_30d`
- `snapshot_at`
- `source_status`

Reglas sugeridas:

| Situacion | Accion |
|---|---|
| Funding > p90, long/short > p85, OI 24h sube, precio pierde momentum | Veto a nuevo long |
| Breakout spot + OI sube + funding entre p30-p75 | Confirmacion, no señal primaria |
| Funding < p10 + OI deja de subir + precio estabiliza | Permitir mean-reversion si regimen acompaña |
| Posicion long abierta + funding extremo positivo + OI sube + PPO cae | Subir trailing o bloquear add-ons |
| Derivatives data stale | No usar como confirmacion; si estrategia depende de eso, fail-closed |

Funding cash-and-carry es atractivo, pero no es el siguiente paso. Un paper 2025 reporta beneficios de funding arbitrage y baja correlacion con HODL ([Blockchain: Research and Applications, 2025](https://www.sciencedirect.com/science/article/pii/S2096720925000818)). Otro paper estudia predictibilidad de funding rates con modelos DAR y encuentra predictibilidad out-of-sample, pero time-varying ([SSRN 2025](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5576424)). Para capturarlo se necesita Futures Demo, short perp, long spot, margin, liquidation monitoring, borrow/carry accounting, funding accrual y reconciliacion de dos venues. Eso es 3+ semanas.

### c) Diversificacion de Simbolos

Si, vale abrir de 2 a 5 simbolos. No abriria a 10 de entrada. Con 2 simbolos, el bot no puede explotar cross-section y queda demasiado expuesto a que BTC/ETH esten en regimen malo para trend-momentum. Con 5 simbolos liquidos se puede rankear sin entrar en microcaps.

Universo inicial:

- BTCUSDT
- ETHUSDT
- SOLUSDT
- BNBUSDT
- XRPUSDT

Criterio dinamico mensual:

| Filtro | Regla |
|---|---|
| Liquidez | top USDT spot por quote volume |
| Spread | spread estimado bajo o depth suficiente para notional |
| Data | 365 dias completos 1h sin gaps graves |
| Tradability | min notional y step size compatibles |
| Correlacion | no agregar activos que solo dupliquen BTC sin alpha relativo |
| Riesgo evento | excluir simbolos con delisting/maintenance/anomalias |

No perseguir small caps al inicio. La evidencia academica indica que mucho alpha se concentra en activos dificiles de tradear, pero ese alpha puede no sobrevivir a slippage, gaps y ejecucion para un bot chico sin infraestructura de microestructura.

### d) Regime-Conditional Strategies

Si: pasar de "una estrategia con perfiles" a "router de estrategias".

Propuesta:

| Regimen | Estrategia activa | Default |
|---|---|---|
| `trending_up` | cross-sectional momentum + trend follow | trade permitido |
| `trending_down` | spot long-only en cash, salvo reversal validado | cash |
| `ranging_low_vol` | mean-reversion | trade permitido con setup propio |
| `ranging_high_vol` | no operar hasta OOS propio | cash |
| `volatile` | no operar | cash |
| `low_liquidity` | no operar | cash |

Cada proposal debe guardar `strategy_family`:

- `xs_momentum`
- `range_reversion`
- `trend_breakout`
- `ml_meta_label_filter`
- `risk_exit`

Y cada reporte debe mostrar:

- PF por `strategy_family`.
- PF por regimen.
- PF por simbolo.
- Sharpe OOS por fold.
- drawdown contribution.

Si una familia solo gana en un regimen especifico, el router lo debe reflejar. Si no hay al menos 30-50 trades OOS por regimen, no se declara edge por regimen.

---

## Bloque 3 - Decision Gate

### Tabla de Decision

| Decision | Criterio honesto |
|---|---|
| Pivotar | Si tras replay OOS rolling con al menos 12 meses, al menos 6 folds y al menos 150 trades simulados netos, la estrategia mantiene PF < 1.05, Sharpe OOS < 0.3, DSR/PSR < 60%, o la mayoria de folds tiene expectancy <= 0 |
| Avanzar a mainnet | PF OOS >= 1.20 neto de fees/slippage, Sharpe OOS >= 1.0 o Deflated Sharpe confidence > 95%, max DD dentro del presupuesto, al menos 100 trades post-fix o 60 dias testnet congelado, drift/slippage audit limpio y 0 divergencias criticas |
| Seguir testnet | Solo si hay señal incipiente: PF 1.05-1.20, Sharpe 0.3-1.0, muestra post-fix < 100 trades, y estrategia congelada |

### Interpretacion del Track Record Actual

Con WR 47.5%, P&L flat con drift negativo, 80 trades cerrados, 78% SL y replay A/B sin variante rentable, la estrategia actual no merece mainnet. No prueba que sea imposible encontrar edge, pero si prueba que la configuracion actual no tiene evidencia suficiente.

La decision correcta es:

- No activar partial exits como cambio principal.
- No activar Strategist Agent diario para ajustar parametros.
- No poner capital real.
- Pivotar entradas y evaluacion.

Para seguir recolectando datos sin decidir, hay que congelar configuracion. Si cada semana se cambia RSI, ADX, cooldown, SL/TP o perfiles, los nuevos trades no acumulan evidencia comparable. Cada cambio reinicia el experimento.

### Gates Numericos Recomendados

| Gate | Minimo |
|---|---:|
| Trades OOS simulados | >= 150 |
| Folds OOS | >= 6 |
| Periodo OOS | >= 6 meses, ideal 12 |
| Profit Factor neto | >= 1.20 |
| Sharpe OOS | >= 1.0 |
| Deflated Sharpe confidence | > 95% |
| Max drawdown OOS | <= presupuesto definido |
| Folds positivos | >= 70% |
| Slippage stress | Sigue rentable a 20 bps |
| Live/testnet frozen | >= 60 dias o >= 100 trades post-fix |

---

## Bloque 4 - Si tuviera que apostar US$5k propios

No pondria US$5k al bot tal como esta. Antes haria, en este orden: corregir CI sobre `main`; bloquear velas no cerradas; implementar trazabilidad `decision_trace_id`; correr walk-forward/PBO/DSR con dataset congelado; cambiar sizing a riesgo-at-stop; integrar derivatives como veto; ampliar solo a 5 simbolos liquidos con ranking cross-sectional; y operar 60 dias testnet con estrategia congelada. Recién si pasa el gate, arrancaria mainnet con capital muy chico, tipo US$100-US$250, no con US$5k de entrada.

---

## Plan Priorizado de Implementacion

### Sprint 1 - P0 Operacional (2-4 dias)

| Tarea | Archivos probables | Criterio de aceptacion |
|---|---|---|
| Arreglar CI `master` -> `main` | `.github/workflows/ci.yml` | Push a `main` corre frontend + backend tests |
| Hacer Docker build dependiente de CI | `.github/workflows/build-backend.yml` | No push GHCR si tests fallan |
| Filtrar velas cerradas | `kline_collector.py`, `technical_analysis.py`, `backtester.py`, migracion Supabase | Ningun indicador usa vela abierta |
| Agregar `decision_trace_id` | `signal_generator.py`, `executor.py`, migracion Supabase | Cada proposal/order/position comparte trace id |
| Replay smoke en CI | `backend/scripts/diagnostics` | CI falla si replay fixture cambia sin aprobacion |

### Sprint 2 - Research Harness (4-7 dias)

| Tarea | Archivos probables | Criterio de aceptacion |
|---|---|---|
| `research_runs` y `variant_results` | migracion Supabase | Cada backtest guarda dataset/config hash |
| Rolling OOS runner | nuevo `backend/scripts/research/walk_forward_report.py` | Genera `.md` y `.csv` por run |
| DSR/PBO basico | `backend/app/services/research_metrics.py` | Reporta DSR/PBO por estrategia |
| Sensibilidad costos | runner research | Reporta base, 10 bps, 20 bps slippage |
| Performance por regimen | runner research | Tabla PF/Sharpe por regimen |

### Sprint 3 - Alpha Pivot (1-2 semanas)

| Tarea | Archivos probables | Criterio de aceptacion |
|---|---|---|
| Ampliar universo a 5 simbolos | config + backfill | 365d 1h completos sin gaps graves |
| Cross-sectional scorer | nuevo `xs_momentum.py` | Ranking reproducible por vela |
| Router por regimen | `signal_generator.py` o nuevo `strategy_router.py` | Cada proposal tiene `strategy_family` |
| Mean-reversion ranging | nuevo modulo estrategia | Solo opera `ranging_low_vol` |
| ML meta-label target | `ml/trainer.py` | Target +1R before -1R y OOS report |

### Sprint 4 - Derivatives Veto (2-4 dias)

| Tarea | Archivos probables | Criterio de aceptacion |
|---|---|---|
| `derivatives_client.py` | nuevo service | Smoke real BTC/ETH OK |
| Persist snapshots | migracion + orchestrator | snapshots horarios guardados |
| Veto rules | `signal_generator.py` o router | Funding/OI crowding bloquea longs tardios |
| Tests con mocks | `backend/tests/test_derivatives_client.py` | Partial failure no rompe señales |

---

## Checklist para Validacion de Claude Code

Claude Code deberia validar este informe contra el repo con estas preguntas:

1. Confirmar que `.github/workflows/ci.yml` apunta a `master` y que el repo opera en `main`.
2. Confirmar que `build-backend.yml` puede construir/pushear imagen sin depender de pytest.
3. Confirmar si `technical_analysis._load_klines_df` puede devolver la ultima vela sin verificar que este cerrada.
4. Confirmar que no existe `backend/app/services/derivatives_client.py`.
5. Confirmar que el backtester actual no implementa PBO/DSR/CPCV ni registra todos los trials.
6. Confirmar que no hay `decision_trace_id` persistido de punta a punta.
7. Confirmar que el sizing runtime limita notional, pero no riesgo agregado al stop.
8. Confirmar que la estrategia actual mezcla perfiles por regimen en vez de un router de estrategias separado.
9. Validar que las recomendaciones P0 son implementables sin migrar de stack ni adoptar Freqtrade/Jesse/Nautilus.
10. Rechazar cualquier propuesta de mainnet hasta pasar el Decision Gate.

---

## Fuentes

- VectorBT documentation: https://vectorbt.dev/
- VectorBT features: https://vectorbt.dev/getting-started/features/
- NautilusTrader backtesting docs: https://nautilustrader.io/docs/latest/concepts/backtesting/
- NautilusTrader data catalog docs: https://nautilustrader.io/docs/latest/concepts/data/
- NautilusTrader architecture/fail-fast docs: https://nautilustrader.io/docs/latest/concepts/architecture/
- Hummingbot architecture and order tracking: https://hummingbot.org/blog/hummingbot-architecture---part-1/
- Freqtrade recursive analysis: https://docs.freqtrade.io/en/stable/recursive-analysis/
- Freqtrade strategy callbacks/custom stoploss: https://www.freqtrade.io/en/stable/strategy-callbacks/
- Binance Spot API market data endpoints: https://developers.binance.com/docs/binance-spot-api-docs/rest-api/market-data-endpoints
- Binance USD-M Futures funding history: https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Get-Funding-Rate-History
- Binance USD-M Futures open interest: https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Open-Interest
- Binance USD-M Futures top trader long/short ratio: https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Top-Trader-Long-Short-Ratio
- Bailey, D. H. and Lopez de Prado, M., The Deflated Sharpe Ratio: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551
- Backtest overfitting in the machine learning era, ScienceDirect 2024: https://www.sciencedirect.com/science/article/abs/pii/S0950705124011110
- Machine learning and the cross-section of cryptocurrency returns, IRFA 2024: https://www.sciencedirect.com/science/article/pii/S1057521924001765
- Cross-cryptocurrency return predictability, JEDC 2024: https://www.sciencedirect.com/science/article/pii/S0165188924000551
- Cross-sectional interactions in cryptocurrency returns, IRFA 2025: https://www.sciencedirect.com/science/article/abs/pii/S1057521924007415
- Cryptocurrency momentum has not its moments, 2025: https://link.springer.com/article/10.1007/s11408-025-00474-9
- The reversal in the cryptocurrency market before and during the Covid-19 pandemic, PLOS ONE 2024: https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0304377
- Exploring Risk and Return Profiles of Funding Rate Arbitrage on CEX and DEX, 2025: https://www.sciencedirect.com/science/article/pii/S2096720925000818
- Predictability of Funding Rates, SSRN 2025: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5576424
- Return and Volatility Forecasting Using On-Chain Flows in Cryptocurrency Markets, arXiv 2024: https://arxiv.org/abs/2411.06327
- Enhancing Price Prediction in Cryptocurrency Using Transformer Neural Network and Technical Indicators, arXiv 2024: https://arxiv.org/abs/2403.03606

