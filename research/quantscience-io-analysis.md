# QuantScience.io — Investigacion Completa para Trading Bot

**Fecha:** 2026-03-26
**Objetivo:** Extraer insights accionables para mejorar nuestro bot de crypto trading

---

## 1. Resumen de QuantScience.io

**Fundadores:**
- **Jason Strimpel** — 20+ anos como Quant (JP Morgan, BP Trading, Rio Tinto, AWS)
- **Matt Dancho** — Data Scientist, fundador de Business Science

**Propuesta:** Curso cohort-based "Start Algo Trading with Python in 60 Days". Enfoque en estrategias institucionales simplificadas para traders individuales.

**Stack de Software Propietario:**
| Componente | Funcion |
|------------|---------|
| **QSConnect** | Data management: 90,000+ equities/ETFs, FMP API + DuckDB cache |
| **QSResearch** | Feature engineering + backtesting con MLflow integration |
| **QSAutomate** | Orquestacion end-to-end (Prefect workflows) |
| **Omega** | Ejecucion de trades via Interactive Brokers |

---

## 2. Estrategias Core Ensenadas

### 2.1 Momentum Factor
- Compra activos trending up, asume "winners keep winning" a corto plazo
- Escanea stocks por market cap y volumen
- Calcula momentum factor y ejecuta trades
- Rebalanceo mensual: divest holdings actuales, seleccionar nuevos

### 2.2 Risk Parity
- Balancea *riesgo* (no capital) entre asset classes
- Pesos inversamente proporcionales a volatilidad
- Rebalanceo regular para mantener allocation de riesgo

### 2.3 Crack Spread (Commodities Arbitrage)
- Arbitraje clasico entre crude oil y refined products
- Demonstra logica de relative value trading institucional

### 2.4 Mean Reversion (Newsletter QS045)
- Z-score de returns de 21 dias: `(return_actual - mean) / std`
- Long bottom 5, Short top 5 por z-score
- Filtro VWAP > $15
- Rebalanceo mensual con Zipline

### 2.5 3-Day Pullback (QS043)
- Estrategia de pullback de corto plazo

---

## 3. Frameworks de Backtesting

### 3.1 Event-Based: Zipline
- Desarrollado originalmente por Quantopian
- Usado para momentum y risk parity
- **Ventaja clave:** Reduce lookahead bias inherentemente
- Maneja slippage, transaction costs, portfolio rebalancing

### 3.2 Vector-Based: VectorBT
- Mas rapido y flexible para custom metrics
- Excelente para optimizacion de parametros
- Usado para exit optimization con grid search

**Insight critico:** Profesionales usan AMBOS frameworks. Event-based para validacion rigurosa, vector-based para exploracion rapida.

---

## 4. Indicadores Tecnicos Cubiertos

| Indicador | Newsletter | Insights Clave |
|-----------|-----------|----------------|
| **MACD** | QS013 | 12/26/9 params. PPO (normalizado) sugerido como mejora. Analiza forward returns a 1D, 5D, 10D, 21D |
| **RSI** | QS010 | Standard 70/30. Enfasis en usar con otros indicadores, no standalone |
| **ATR** | QS009 | Volatility filter: stops dinamicos en alta vol, position sizing ajustado |
| **Hurst Exponent** | QS041 | H>0.5 trending, H<0.5 mean-reverting, H=0.5 random walk |
| **Autocorrelation** | QS035 | Positiva = momentum, Negativa = mean reversion |
| **FFT** | QS008 | Descomposicion de frecuencias para cycle detection y noise filtering |

---

## 5. Risk Management

### 5.1 Metricas Cubiertas
| Metrica | Newsletter | Aplicacion |
|---------|-----------|------------|
| **Downside Deviation** | QS024 | 33% menor que StdDev para AAPL; mide solo riesgo bajista |
| **CVaR** | QS040 | Mean de losses por debajo de VaR al 95%, lookback 500 dias |
| **Kelly Criterion** | QS031 | Optimizacion continua de leverage [0, 2], rolling 25Y window |
| **Sharpe/Sortino** | QS017 | QuantStats tearsheets para evaluacion |
| **Max Drawdown** | QS017 | Largest peak-to-trough decline |
| **Information Ratio** | QS032 | Excess returns vs benchmark |
| **Omega Ratio** | QS030 | Probability-weighted gains vs losses |
| **Tail Ratio** | QS044 | Ratio of right tail to left tail returns |
| **Skew/Kurtosis** | QS047 | Distribucion de returns (fat tails) |

### 5.2 Position Sizing con ATR
- Alta volatilidad (ATR alto) → posiciones mas chicas
- Baja volatilidad (ATR bajo) → posiciones mas grandes
- Stops dinamicos basados en ATR multiples (no porcentaje fijo)

### 5.3 Optimizacion de Exits (QS034)
- **Grid search** sobre 100 niveles de stop (1%-100%) con VectorBT
- Tres tipos: Stop-Loss (SL), Trailing Stop (TS), Take-Profit (TP)
- **400 rolling windows** para robustez estadistica
- Time-based exit forzado al final de cada window
- **Key finding:** TS generalmente outperforma SL fijo

---

## 6. Machine Learning para Trading

### 6.1 ML Prediction Strategy (QS007)
- **Random Forest** para predecir SPY sobre 20-day SMA a 5 dias
- Features: Distance from N-Day MA, Distance from N-Day High/Low, Price Distance
- Target: regions donde precio estara sobre SMA(20) proximos 5D

### 6.2 Autoencoders para Trading (QS025)
- Arquitectura: Input → 64 → 32 → 10 (bottleneck) → 32 → 64 → Output
- ReLU activations, batches de 32
- Features: log returns, SMA, volatility
- Uso: dimensionality reduction, clustering de stocks similares, anomaly detection

### 6.3 K-Means para Portfolio (QS023)
- Features: mean returns anualizados + volatility anualizada
- Elbow method para optimal K (~5-6 clusters)
- Clustering por risk-return profile para diversificacion

### 6.4 Markov Models para Regimenes (QS026)
- **Hidden Markov Model (HMM)** con 3 estados
- Features observables: log returns + price range (high-low)
- Estados descubiertos: bullish (green), sideways (orange), bearish (red)
- Transition probabilities para forecasting de persistencia de regimen

### 6.5 Level 2: XGBoost Production
- Hybrid factor: momentum + value + fundamental strength
- Feature engineering: technical indicators + FMP fundamentals
- Multi-period lookforward windows
- Screening: liquidity, volatility, quality filters
- MLflow para experiment tracking

---

## 7. Portfolio Construction

### 7.1 Hierarchical Risk Parity (QS022)
- Clustering-based allocation que no requiere inversion de matriz de covarianza
- Mas estable que Markowitz clasico

### 7.2 Correlacion para Diversificacion (QS019)
- Assets no correlacionados suavizan returns
- yfinance + pandas para correlation matrices
- Objetivo: volatility dampening + Sharpe improvement

### 7.3 Factor Analysis con Alphalens (QS015)
- Evaluar predictive power de alpha factors
- Separar beta (mercado) de alpha (skill)

### 7.4 Dollar-Neutral (QS048)
- Estrategia market-neutral con exposicion neta zero

---

## 8. Herramientas y Librerias Recomendadas

| Libreria | Proposito | Newsletter |
|----------|-----------|-----------|
| **VectorBT** | Backtesting rapido, exit optimization | QS034 |
| **Zipline** | Event-based backtesting riguroso | QS045 |
| **QuantStats** | Performance tearsheets | QS017 |
| **Riskfolio-Lib** | Portfolio optimization (MV, CVaR, HRP) | QS014 |
| **Skfolio** | Risk parity (scikit-learn compatible) | QS011 |
| **Alphalens** | Factor analysis | QS015 |
| **Pyfolio** | Portfolio analytics | Level 2 |
| **ffn** | Financial functions (Sharpe, drawdown) | QS020 |
| **hmmlearn** | Hidden Markov Models | QS026 |
| **Pytimetk** | Time series con Polars (20x faster) | QS012 |
| **mplfinance** | Candlestick charts | QS021 |
| **MLflow** | Experiment tracking | Level 2 |
| **Prefect** | Workflow orchestration | Level 2 |
| **DuckDB** | Fast local analytics DB | Level 2 |
| **yfinance** | Market data download | Multiple |
| **OpenBB** | Financial data + screening | QS001, QS003 |

---

## 9. INSIGHTS ACCIONABLES para Nuestro Bot

### 9.1 PRIORIDAD ALTA — Implementar

#### A. Hurst Exponent para Regime Detection
**Estado actual:** Usamos entropy-based regime detection.
**Mejora:** Agregar Hurst exponent como feature complementaria.
```python
def get_hurst_exponent(ts, max_lag=20):
    lags = range(2, max_lag)
    tau = [np.std(np.subtract(ts[lag:], ts[:-lag])) for lag in lags]
    return np.polyfit(np.log(lags), np.log(tau), 1)[0]
```
- H > 0.5 → trending → activar estrategia momentum (MACD signals)
- H < 0.5 → mean-reverting → activar mean-reversion (RSI extremes)
- H ≈ 0.5 → random walk → reducir position size o no operar
- **Multi-lag analysis** (20, 100, 250) para diferentes timeframes

#### B. Hidden Markov Model para Regimenes (Complementar Entropy)
**Estado actual:** Entropy filter binario.
**Mejora:** HMM con 3 estados descubiertos automaticamente.
- Features: log returns + range (high-low) — ya tenemos estos datos
- 3 estados: bull/sideways/bear con transition probabilities
- Mas robusto que threshold fijo de entropy
- **hmmlearn** es ligero y facil de integrar

#### C. Optimizacion de Exits con Grid Search
**Estado actual:** ATR-based SL/TP con trailing stops fijos.
**Mejora:** Grid search sistematico sobre parametros de exit.
- Testear 100 niveles de SL (1%-100% de ATR) x TS x TP
- Rolling windows para robustez (no solo un periodo)
- VectorBT-style pero adaptado a crypto con nuestro backtester
- **Key insight de QS:** Trailing stops generalmente outperforman SL fijo

#### D. Kelly Criterion para Position Sizing
**Estado actual:** Position sizing basado en risk percentage fijo.
**Mejora:** Kelly criterion continuo con rolling window.
- Optimizacion via `scipy.optimize.minimize_scalar`
- Rolling window (ej: 90 dias para crypto, mas corto que 25Y de acciones)
- Fractional Kelly (0.25-0.5 del Kelly optimo) para reducir varianza
- Bounds [0, max_leverage] segun nuestro risk management

### 9.2 PRIORIDAD MEDIA — Evaluar

#### E. PPO en vez de MACD
**Insight de QS:** MACD tiene problema de varianza no constante en el tiempo.
- PPO normaliza el MACD como porcentaje del precio
- Mas consistente para backtesting historico largo
- Formula: `PPO = (EMA12 - EMA26) / EMA26 * 100`
- Podria mejorar señales en crypto donde precios varian 10x-100x

#### F. CVaR como Risk Metric
**Estado actual:** Usamos max drawdown y risk percentage.
**Mejora:** CVaR al 95% como constraint adicional.
- Mide "average loss en los peores 5% de dias"
- Mejor que VaR para tail risk (crypto tiene fat tails)
- Implementacion simple: percentile + mean of worse returns

#### G. Autocorrelation Check Pre-Trade
- Antes de cada trade, verificar autocorrelacion de returns recientes
- Positiva → confirma momentum signal
- Negativa → confirma mean-reversion signal
- Cerca de 0 → señal debil, reducir confidence

#### H. Downside Deviation / Sortino para Evaluacion
**Estado actual:** Usamos Sharpe-like metrics.
**Mejora:** Sortino y downside deviation para evaluar estrategia.
- Penaliza solo volatilidad bajista, no la subida
- Mas relevante para crypto donde queremos upside vol

#### I. FFT para Cycle Detection
- Identificar ciclos dominantes en precios de crypto
- Filtrar ruido de alta frecuencia
- Detectar cuando precio se desvia del trend reconstruido
- Podria mejorar timing de entries

### 9.3 PRIORIDAD BAJA — Research

#### J. Autoencoders para Anomaly Detection
- Comprimir features de mercado a embeddings de dimension baja
- Detectar condiciones anomalas (flash crashes, pump-and-dumps)
- Requiere mas datos historicos que lo que tenemos ahora

#### K. K-Means para Regimen Clustering
- Complementar HMM con clustering no supervisado
- Agrupar periodos por risk-return profile
- Adaptar estrategia por cluster

#### L. Factor Analysis con Alphalens
- Evaluar predictive power de cada indicador (RSI, MACD, ADX, etc.)
- Descartar factores que no contribuyen alpha
- Optimizar weights en ensemble model

---

## 10. Mejoras Arquitectonicas Sugeridas (Inspiradas en QS)

### 10.1 Experiment Tracking
- Agregar MLflow o equivalente ligero para trackear backtests
- Log: parametros, metricas, plots por cada variante de estrategia
- Comparar historicamente que funciona mejor

### 10.2 Multi-Strategy Framework
- QS opera multiples estrategias en paralelo
- Nuestro bot podria tener:
  - **Momentum mode** (cuando Hurst > 0.5): MACD + ADX signals
  - **Mean-reversion mode** (cuando Hurst < 0.5): RSI extreme reversals
  - **Neutral mode** (cuando Hurst ≈ 0.5): reducir exposicion o no operar

### 10.3 Event-Based Backtesting
- Nuestro backtester actual es vector-based
- Para validacion final, considerar Zipline-style event-based
- Reduce lookahead bias, maneja slippage/fees mas realista

### 10.4 Rolling Window Validation
- No validar solo en un periodo
- Grid search sobre multiples ventanas rolling (como QS034: 400 windows)
- Resultados mas robustos y menos overfitting

---

## 11. Resumen de Librerias Python para Integrar

| Prioridad | Libreria | Para Que | Esfuerzo |
|-----------|----------|----------|----------|
| ALTA | scipy (minimize_scalar) | Kelly Criterion | Bajo |
| ALTA | hmmlearn | HMM regime detection | Medio |
| ALTA | statsmodels (acf) | Autocorrelation | Bajo |
| MEDIA | numpy (polyfit) | Hurst exponent | Bajo |
| MEDIA | quantstats | Performance tearsheets | Bajo |
| MEDIA | vectorbt | Exit optimization | Medio |
| BAJA | sklearn (KMeans) | Regime clustering | Bajo |
| BAJA | pytorch | Autoencoders | Alto |

---

## 12. Codigo Open-Source Disponible

**GitHub:** https://github.com/quant-science
- `sunday-quant-scientist` (1,719 stars) — 48+ notebooks con tutoriales
- `vectorbt_backtesting` — MA crossover con VectorBT
- `zipline_backtesting` — Event-based con Zipline

**Newsletter gratuito:** https://quantscience.io/newsletter
- 20+ articulos con codigo en Python
- Suscripcion da acceso a carpetas QS001-QS048 con codigo completo

---

## 13. Key Takeaways

1. **Regime detection es fundamental** — QS usa HMM con 3 estados, nosotros usamos entropy. Combinar ambos seria mas robusto.

2. **Exits importan mas que entries** — QS dedica un newsletter completo a optimizar exits con 100 niveles x 400 windows. Nuestros exits son basicos comparativamente.

3. **Kelly Criterion > fixed position sizing** — Adapta tamaño de posicion a la edge real de la estrategia, no a un % arbitrario.

4. **Hurst exponent es clave para saber QUE estrategia usar** — Momentum vs mean-reversion no es eleccion fija, depende del regimen actual.

5. **PPO > MACD para crypto** — La normalizacion resuelve el problema de precios que cambian ordenes de magnitud.

6. **Backtesting riguroso = rolling windows** — No un solo periodo. QS usa 400 windows para exit optimization.

7. **Autocorrelation como confirmacion** — Simple de calcular, potente para confirmar si momentum o mean-reversion es apropiado.

8. **CVaR para tail risk** — Crypto tiene fat tails extremas. CVaR captura esto mejor que VaR o StdDev.
