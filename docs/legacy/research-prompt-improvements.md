# Deep Research Prompt - Trading Agentic Improvements

## Prompt para copiar y usar en Gemini Deep Research / ChatGPT Deep Research / Claude

---

Soy desarrollador de un sistema de trading automatizado de criptomonedas (BTC, ETH, SOL, BNB, XRP) que opera en Binance Spot. El sistema tiene:

- **Frontend:** Next.js 16 + React 19 + TypeScript
- **Backend cuantitativo:** Python 3.11 + FastAPI + pandas + pandas-ta + scikit-learn + NumPy
- **Base de datos:** Supabase (PostgreSQL con pgvector)
- **IA:** Google Gemini (via Vercel AI SDK) para evaluación de señales
- **Indicadores actuales:** RSI(14), MACD(12,26,9), ADX(14), Bollinger Bands(20,2), ATR(14), SMA(20,50,200), EMA(12,26,50), OBV, VWAP, Stochastic(14,3,3)
- **Componentes actuales:** Detección de régimen de mercado (trending/ranging/volatile), filtro de entropía de Shannon, soporte/resistencia por K-Means, position sizing con Kelly Criterion + ATR, backtesting básico con 3 estrategias

Necesito investigar a fondo e implementar **7 mejoras críticas**. Para cada mejora necesito:

1. **Papers académicos y fuentes de referencia** (con URLs o DOIs cuando sea posible)
2. **Código de referencia o librerías** existentes en Python que pueda usar o adaptar
3. **Implementación concreta** con pseudocódigo o código Python funcional
4. **Cómo integrarlo** en mi arquitectura existente (FastAPI + pandas + PostgreSQL)
5. **Parámetros recomendados** para crypto spot (BTC, ETH, etc.)
6. **Métricas para validar** que la mejora funciona correctamente
7. **Errores comunes** a evitar en la implementación

---

## MEJORA 1: Análisis Multi-Timeframe (MTF)

Actualmente mi sistema evalúa señales en un solo intervalo temporal. Necesito implementar análisis multi-timeframe que combine señales de múltiples intervalos (por ejemplo: 15m, 1h, 4h, 1d) para filtrar señales falsas y operar solo cuando hay confluencia temporal.

Investiga:
- ¿Cuál es el enfoque académico más robusto para combinar señales de múltiples timeframes?
- ¿Cómo ponderar la importancia de cada timeframe (el diario debería pesar más que el de 15min)?
- ¿Qué técnica usar: votación por mayoría, scoring ponderado, confirmación jerárquica (top-down)?
- ¿Cómo evitar el sesgo de look-ahead al combinar timeframes con distinto delay?
- Dame código Python que tome DataFrames de OHLCV en múltiples timeframes, calcule indicadores en cada uno, y produzca una señal unificada con score de confluencia (0-100).
- ¿Qué combinaciones de timeframes son óptimas para crypto (que opera 24/7)?
- Papers sobre "multiple timeframe analysis", "temporal aggregation in trading systems", "hierarchical signal confirmation"

---

## MEJORA 2: Trailing Stops Dinámicos

Mi sistema actualmente usa stop-loss fijo basado en ATR pero no tiene trailing stops. Necesito implementar trailing stops que sigan el precio cuando va a favor, protegiendo ganancias sin cortar prematuramente posiciones ganadoras.

Investiga:
- **ATR Trailing Stop:** Cálculo de trailing stop basado en N × ATR que se mueve solo a favor del trade
- **Chandelier Exit:** Método de Chuck LeBeau - trailing stop desde el máximo más alto menos N × ATR
- **Parabolic SAR:** Como alternativa o complemento para trailing stops
- **Adaptive trailing stops:** Stops que se ajustan según la volatilidad actual (más apretados en baja vol, más amplios en alta vol)
- ¿Cuándo es mejor usar trailing stop vs. take-profit fijo vs. combinación?
- Dame código Python completo para una clase `TrailingStopManager` que:
  - Soporte múltiples métodos: ATR-based, Chandelier, percentage-based, Parabolic SAR
  - Actualice el stop en cada nueva vela
  - Determine cuándo cerrar la posición
  - Se integre con un DataFrame de OHLCV y un registro de posición abierta
- ¿Cuál es el multiplicador ATR óptimo para crypto? (¿2×? ¿3×? ¿depende del régimen?)
- Papers sobre "adaptive trailing stops", "exit strategies in quantitative trading", "optimal stop placement"

---

## MEJORA 3: Control de Riesgo por Correlación entre Activos

Mi sistema permite hasta 3 posiciones abiertas simultáneas, pero no verifica si los activos están altamente correlacionados. En crypto, BTC, ETH, SOL, BNB frecuentemente se mueven juntos (correlación > 0.85), por lo que tener 3 posiciones en cripto podría ser equivalente a 3× el riesgo en un solo activo.

Investiga:
- ¿Cómo calcular correlación rolling (ventana móvil) entre pares de activos crypto?
- ¿Pearson vs. Spearman vs. Kendall para retornos de crypto?
- ¿Qué umbral de correlación usar para considerar dos posiciones como "la misma apuesta"?
- **Ajuste de posición por correlación:** Si ya tengo una posición en BTC y quiero abrir en ETH con correlación 0.9, ¿cómo debería reducir el tamaño de la segunda posición?
- **Cluster de correlación:** ¿Cómo agrupar activos por correlación y limitar exposición por cluster?
- Dame código Python que:
  - Calcule una matriz de correlación rolling (ventana de 30 días) entre todos los pares de activos
  - Implemente un `CorrelationRiskCheck` que reciba las posiciones abiertas y la nueva propuesta, y valide que la exposición correlacionada no exceda un límite
  - Ajuste dinámicamente el tamaño de posición según la correlación con posiciones existentes
- Papers sobre "portfolio correlation risk in crypto markets", "diversification in cryptocurrency portfolios", "correlation-adjusted position sizing"

---

## MEJORA 4: Modelado de Slippage y Comisiones en Backtesting

Mi backtester actual no modela slippage ni comisiones, lo que sobreestima significativamente los resultados. Necesito agregar modelos realistas.

Investiga:
- **Comisiones Binance Spot:** Estructura actual de fees (maker/taker, con/sin BNB discount)
- **Modelo de slippage para crypto:** ¿Cómo estimar el slippage basado en el volumen de la orden vs. la liquidez del order book?
- **Slippage fijo vs. dinámico:** ¿Es mejor un slippage fijo (ej: 0.05%) o uno que varíe con la volatilidad y el volumen?
- **Impact model:** Para órdenes más grandes, ¿cómo modelar el market impact?
- Dame código Python que:
  - Implemente una clase `SlippageModel` con métodos: `fixed_slippage`, `volume_based_slippage`, `volatility_adjusted_slippage`
  - Implemente una clase `CommissionModel` con la estructura de fees de Binance
  - Se integre con mi backtester existente, aplicando slippage y comisiones a cada trade simulado
  - Muestre el impacto de costos en las métricas (Sharpe antes/después de costos)
- ¿Cuáles son valores realistas de slippage para BTCUSDT, ETHUSDT, SOLUSDT en distintos volúmenes?
- Papers sobre "transaction cost analysis in cryptocurrency", "slippage modeling", "realistic backtesting frameworks"

---

## MEJORA 5: Walk-Forward Optimization (WFO)

Mi backtesting actual prueba estrategias en todo el periodo histórico disponible, lo que puede resultar en overfitting. Necesito implementar walk-forward optimization para validar que las estrategias generalizan a datos fuera de muestra.

Investiga:
- **¿Qué es Walk-Forward Optimization?** Explicar el concepto de ventanas in-sample (entrenamiento) y out-of-sample (test) que se mueven en el tiempo
- **Anchored vs. Rolling WFO:** ¿Cuándo usar cada uno?
- **¿Cuánto in-sample vs. out-of-sample?** ¿Ratio 80/20? ¿70/30? ¿Depende del timeframe?
- **Walk-Forward Efficiency (WFE):** Métrica para evaluar si una estrategia generaliza
- **Combinatorial Purged Cross-Validation (CPCV)** de Marcos López de Prado como alternativa más robusta
- Dame código Python que:
  - Implemente `WalkForwardOptimizer` que divida datos OHLCV en ventanas móviles
  - Para cada ventana: optimice parámetros in-sample, evalúe out-of-sample
  - Calcule Walk-Forward Efficiency y métricas agregadas
  - Soporte mis 3 estrategias existentes (SMA crossover, RSI reversal, Bollinger squeeze)
  - Genere un reporte de robustez con equity curve de solo las ventanas out-of-sample
- **Libro:** "Advances in Financial Machine Learning" de Marcos López de Prado - capítulos relevantes
- Papers sobre "walk-forward analysis", "out-of-sample validation trading strategies", "avoiding overfitting in backtesting"

---

## MEJORA 6: Detección de Degradación del Modelo (Model Monitoring)

Mi sistema usa Gemini AI para evaluar señales de trading, pero no tengo forma de detectar si la calidad de las señales se degrada con el tiempo. Necesito un sistema de monitoreo que detecte automáticamente cuando el modelo está dando señales consistentemente malas y pause el trading.

Investiga:
- **Métricas de calidad de señales en tiempo real:**
  - Win rate rolling (últimas N operaciones)
  - Sharpe ratio rolling
  - Expectancy rolling
  - Distribución de P&L reciente vs. histórica
- **Detección de cambio de distribución (concept drift):**
  - CUSUM (Cumulative Sum Control Chart)
  - Page-Hinkley test
  - ADWIN (Adaptive Windowing)
  - ¿Cuál es más apropiado para detectar degradación en trading?
- **Reglas de auto-pausa:** ¿Qué criterios usar para pausar automáticamente?
  - ¿N trades perdedores consecutivos?
  - ¿Win rate por debajo de X% en las últimas Y operaciones?
  - ¿Drawdown excediendo un umbral?
- Dame código Python que:
  - Implemente una clase `ModelHealthMonitor` que reciba el flujo de trades completados
  - Calcule métricas rolling y detecte degradación usando CUSUM o similar
  - Emita alertas con niveles: `healthy`, `warning`, `degraded`, `critical`
  - Tenga un método `should_pause_trading()` que devuelva True si el modelo está en `degraded` o `critical`
  - Se integre con mi tabla de `trade_proposals` y `positions` en Supabase
- Papers sobre "concept drift detection in financial time series", "adaptive trading system monitoring", "regime-aware model validation"

---

## MEJORA 7: Equity Curve Visualization y Analytics

Mi dashboard no tiene una visualización gráfica de la curva de equity (evolución del capital en el tiempo). Esta es la herramienta más importante para evaluar la salud de un sistema de trading de un vistazo.

Investiga:
- **¿Qué debe mostrar un buen equity curve dashboard?**
  - Curva de equity acumulada
  - Underwater curve (drawdown en cada punto)
  - Benchmark comparativo (buy & hold BTC)
  - Bandas de volatilidad del equity
  - Marcadores de trades individuales sobre la curva
- **Librerías de visualización:**
  - ¿Lightweight Charts (TradingView) para el frontend React?
  - ¿Plotly.js para gráficos interactivos?
  - ¿Recharts para React?
  - ¿Cuál es mejor para este caso de uso?
- **Métricas derivadas de la equity curve:**
  - Recovery time (tiempo para recuperar un drawdown)
  - Equity curve smoothness (varianza de retornos)
  - Risk of Ruin calculation
- Dame código:
  - **Python (backend):** Endpoint FastAPI que calcule la equity curve desde los datos de posiciones cerradas y snapshots de cuenta
  - **React (frontend):** Componente que renderice la equity curve con Recharts o Lightweight Charts, incluyendo drawdown overlay y marcadores de trades
  - SQL query para Supabase que reconstruya la equity curve desde `positions` y `account_snapshots`
- ¿Cómo calcular Risk of Ruin dado un win rate y un risk-per-trade?
- Papers sobre "equity curve analysis", "risk of ruin in trading", "performance visualization in quantitative trading"

---

## FORMATO DE RESPUESTA ESPERADO

Para CADA mejora, estructura tu respuesta así:

### Mejora N: [Nombre]

**1. Fundamento teórico:** Explicación concisa de por qué es necesario
**2. Papers y referencias:** Lista con títulos, autores, año, DOI/URL
**3. Librerías recomendadas:** Nombre, versión, URL, para qué usarla
**4. Implementación en Python:** Código funcional y completo, bien comentado
**5. Integración con FastAPI:** Cómo exponerlo como endpoint
**6. Integración con la base de datos:** Tablas necesarias, queries
**7. Parámetros recomendados para crypto:** Valores específicos para BTC/ETH/SOL
**8. Métricas de validación:** Cómo saber que funciona correctamente
**9. Errores comunes:** Qué NO hacer
**10. Prioridad de implementación:** Alta/Media/Baja y por qué

---

## CONTEXTO ADICIONAL

- El sistema opera en Binance Spot (no futuros, no margin, no short selling)
- Account size objetivo: $10,000 USD
- Timeframe principal: intraday a swing (5min a 4h)
- Los datos OHLCV ya están recolectados en PostgreSQL para intervalos: 1m, 5m, 15m, 1h, 4h, 1d
- La máxima posición es $500 USD
- El máximo drawdown permitido es $1,000
- El sistema ya tiene un Risk Manager determinista con 7 checks que NO debe ser reemplazado, sino extendido
- Prefiero código que use pandas, NumPy, y scikit-learn (ya son dependencias del proyecto)
- Para el frontend, ya uso React 19 + Tailwind CSS + SWR para data fetching

Prioriza profundidad y precisión sobre brevedad. Quiero implementación completa, no fragmentos sueltos.
