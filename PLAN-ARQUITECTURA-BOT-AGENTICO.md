## Plan técnico y repositorios base: Bot de trading con capa agéntica, RAG y dashboard web

### Objetivos
- Construir un sistema end-to-end que incluya:
  - Núcleo de trading eficiente (backtesting y ejecución en vivo).
  - Capa agéntica para parametrizar riesgo, operar bajo políticas y explicar decisiones.
  - RAG (Retrieval-Augmented Generation) para que el agente consulte papers y documentación y guíe al usuario.
  - Frontend web con dashboard de posiciones, PnL, órdenes y un chat con el agente.
- Facilitar despliegue reproducible (Docker) y observabilidad (logs, métricas, alertas).

### Alcance (MVP)
- Estrategia base: arbitraje estadístico/paridad (ej. CEDEAR ↔ subyacente, o futuro ↔ spot) con órdenes límite + cancel/replace.
- Brokers locales soportados: IOL (REST) y Matba Rofex (pyRofex). Opcional: IBKR (paper) para ADRs.
- Parametrización de riesgo: tamaño por % del capital, límites diarios, circuit breaker por drawdown.
- Dashboard web (Next.js) y chat con agente (MCP + LangChain/LlamaIndex).

---

### Arquitectura general
```mermaid
flowchart LR
  subgraph Frontend (Next.js)
    UI[Dashboard + Chat]
  end

  subgraph Backend API (FastAPI)
    MDH[MarketData Handler]
    STRAT[Strategy Engine]
    EXEC[Order Execution]
    RISK[Risk & Portfolio]
    LOGS[Logging/Metrics]
    AGENT[Agent Tools API]
  end

  subgraph RAG
    IDX[Vector DB (Chroma/Qdrant)]
    DOCS[Corpus: papers/docs/logs]
  end

  subgraph Brokers/Markets
    IOL[(IOL REST)]
    ROFEX[(pyRofex WS/REST)]
    IBKR[(IBKR (ib_insync))]
  end

  UI <-- WebSockets/HTTP --> Backend API
  AGENT <-.-> IDX
  AGENT <-.-> DOCS
  MDH --> STRAT --> EXEC --> Brokers/Markets
  EXEC --> RISK
  MDH --> LOGS
  STRAT --> LOGS
  EXEC --> LOGS
  RISK --> LOGS

  classDef node fill:#0b7285,stroke:#0b7285,color:#fff
  classDef ext fill:#495057,stroke:#495057,color:#fff
  class UI,MDH,STRAT,EXEC,RISK,LOGS,AGENT,IDX,DOCS node
  class IOL,ROFEX,IBKR ext
```

---

### Repositorios recomendados (curado por componente)
- Núcleo de trading
  - [Backtrader](https://www.backtrader.com): framework de backtesting y ejecución; ideal para MVP y prototipos rápidos.
  - [NautilusTrader](https://github.com/nautechsystems/nautilus_trader): plataforma de alto rendimiento (núcleo en Rust) con paridad research/live.
  - [vectorbt](https://github.com/polakowo/vectorbt): análisis vectorizado con pandas/NumPy para research rápido.

- Conectores de broker/market
  - [pyRofex (Matba Rofex)](https://github.com/matbarofex/pyRofex): REST + WebSocket, órdenes y market data (REMARKET y LIVE).
  - [ib_insync (IBKR)](https://github.com/erdewit/ib_insync): API sync/async para TWS/Gateway.
  - [CCXT](https://github.com/ccxt/ccxt): exchanges cripto (opcional si se extiende a cripto).
  - [IOL Python wrapper (aairabella)](https://github.com/aairabella/iol-python-api): punto de partida para autenticación y endpoints IOL.
  - [MCP-IOL (mcpiol)](https://github.com/fernandezpablo85/mcpiol): servidor MCP sobre API pública de IOL (útil para capa agéntica).

- Datos de mercado y utilidades
  - [bymadata-api-wrapper](https://github.com/matiasgleser/bymadata-api-wrapper): wrapper no oficial de BYMA Data (quotes/series) para validaciones y backtesting.
  - [yfinance](https://github.com/ranaroussi/yfinance): histórico rápido (ADR/US) para investigación.
  - [DolarAPI](https://dolarapi.com): tipos de cambio (CCL, MEP, etc.) para paridades.
  - [pandas-ta](https://github.com/twopirllc/pandas-ta) / [ta](https://github.com/bukosabino/ta): indicadores técnicos si hicieran falta.

- Capa agéntica
  - [Model Context Protocol (MCP)](https://modelcontextprotocol.io): estándar para exponer herramientas seguras al LLM.
  - [LangChain](https://github.com/langchain-ai/langchain): orquestación de tools/agents y chains.
  - [LlamaIndex](https://github.com/run-llama/llama_index): capa RAG e indexación de documentos.
  - Ejemplo de integración: [freqtrade-mcp](https://github.com/kukapay/freqtrade-mcp) (blueprint de tools y control conversacional).

- RAG (almacenamiento vectorial)
  - [Chroma](https://github.com/chroma-core/chroma): DB vectorial embedded-friendly.
  - [Qdrant](https://github.com/qdrant/qdrant): DB vectorial con búsqueda semántica y filtros.
  - [FAISS](https://github.com/facebookresearch/faiss): motor vectorial (lib) para escenarios locales.

- Backend web/API
  - [FastAPI](https://fastapi.tiangolo.com): API Python tipada, WebSockets, muy rápida de implementar.
  - [SQLModel](https://sqlmodel.tiangolo.com) / [SQLAlchemy](https://www.sqlalchemy.org): ORM para persistencia.

- Frontend y visualización
  - [Next.js](https://nextjs.org) + [shadcn/ui](https://ui.shadcn.com) + [Tailwind CSS](https://tailwindcss.com): UI moderna y DX excelente.
  - Charts: [TradingView Lightweight Charts](https://github.com/tradingview/lightweight-charts) o [Plotly.js](https://plotly.com/javascript/).

- Observabilidad y DevOps
  - [Prometheus](https://prometheus.io) + [Grafana](https://grafana.com): métricas y dashboards de sistema.
  - [OpenTelemetry](https://opentelemetry.io) / [Sentry](https://sentry.io): trazas/errores.
  - [Docker Compose](https://docs.docker.com/compose/) para empaquetado; [Kubernetes](https://kubernetes.io) opcional.

---

### Stack recomendado (MVP)
- Backend: Python 3.11, FastAPI, Pydantic, SQLModel/SQLite (MVP), Celery+Redis (jobs opcionales).
- Trading: Backtrader (MVP), pyRofex, cliente IOL propio, ib_insync (paper).
- Agent/RAG: LangChain + LlamaIndex + MCP server; Chroma local; embeddings OpenAI o `sentence-transformers`.
- Frontend: Next.js (App Router), shadcn/ui, Tailwind; sockets via Socket.IO o WS nativo.
- Observabilidad: logging estructurado (JSONL), Prometheus client, Grafana.
- Infra: Docker Compose, `.env` + secretos en variables de entorno.

---

### Diseño de módulos e interfaces
- MarketData Handler
  - IOL: polling REST con rate-limit y caché; normalización de símbolos.
  - ROFEX: WebSocket (pyRofex) con handlers de market data y order reports.
  - IBKR: suscripción con `ib_insync` para ADRs (paper/live opcional).

- Strategy Engine
  - Señales por paridad/cointegración y z-score; parámetros: ventana, umbrales, slippage estimado.
  - Política de entrada/salida y timeouts por orden (cancel/replace N barras/segundos).

- Order Execution
  - Adaptadores: `IOLExecutor`, `RofexExecutor`, `IBKRExecutor` con interfaz común.
  - Cancel/Replace atómico; protección contra órdenes duplicadas por instrumento.

- Risk & Portfolio
  - Sizing por % del portfolio; límites diarios; circuit breaker por drawdown.
  - Reconciliación de posiciones vs broker; cálculo de PnL realizado/latente.

- Agent Tools (MCP)
  - Tools de solo lectura: precios, posiciones, PnL, explicación última operación, estado de riesgo.
  - Tools de acción con confirmación: cerrar posición, pausar trading, ajustar umbrales.

- RAG
  - Ingesta: PDF/HTML (papers y docs), resúmenes + embeddings; indexado en Chroma/Qdrant.
  - Consultas: recuperación semántica + citación de fuentes en respuestas del agente.

- Frontend
  - Páginas: Dashboard (KPIs, PnL, exposición), Órdenes/Trades, Estrategia (parámetros), Riesgo, Chat del agente.
  - Tiempos reales via WebSockets; dark mode; autenticación local (MVP).

---

### Esquema de datos (MVP)
- Tablas principales (SQLModel/SQLite):
  - `instruments(id, symbol, venue, metadata)`
  - `ticks(id, ts, symbol, bid, ask, last, venue)`
  - `signals(id, ts, kind, symbol_a, symbol_b, payload)`
  - `orders(id, ts, venue, symbol, side, qty, price, status, external_id)`
  - `fills(id, ts, order_id, qty, price, fee)`
  - `positions(id, symbol, qty, avg_price, unrealized, realized)`
  - `risk_limits(id, key, value)`
  - `logs(id, ts, level, source, message, payload)`

---

### Seguridad y cumplimiento
- Gestión de secretos con variables de entorno; nunca versionar credenciales.
- Separar sandbox/live; flags de modo y bloqueos de herramientas críticas del agente.
- Controles: límites de frecuencia de órdenes y tamaño; confirmaciones para acciones peligrosas.
- Disclaimer: el sistema es herramienta de investigación; no es asesoramiento financiero.

---

### Roadmap de implementación (6–7 semanas)
- Semana 1: Conectividad (IOL sandbox, pyRofex REMARKET, IBKR paper). Esqueleto FastAPI y Next.js. Docker Compose básico.
- Semana 2: MarketData + Strategy (paridad/z-score). Logs estructurados. Backtesting con Backtrader.
- Semana 3: Order Execution (limit + cancel/replace), Risk Manager (sizing, límites, drawdown). WebSockets hacia Front.
- Semana 4: Dashboard (KPIs, posiciones, órdenes, trades). Métricas Prometheus + Grafana.
- Semana 5: Capa agéntica (MCP + LangChain). Tools de lectura. RAG mínimo (Chroma + 5–10 papers/docs).
- Semana 6: Tools de acción con confirmación. Hardening (rate limits, reconexión, tests). IBKR opcional.
- Semana 7: Pulido, documentación, scripts de despliegue y runbook.

---

### Corpus inicial sugerido para RAG
- Fundamentos de pairs trading y cointegración
  - Gatev, Goetzmann, Rouwenhorst (2006), "Pairs Trading" — [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=141868)
  - Engle & Granger (1987), "Co-integration and Error Correction" — [JSTOR/SSRN](https://www.jstor.org/stable/1913236)
  - Statsmodels: `tsa.stattools.coint` — [Docs](https://www.statsmodels.org/stable/generated/statsmodels.tsa.stattools.coint.html)
- Backtesting y fricciones
  - Backtrader — [Sitio oficial](https://www.backtrader.com)
  - Slippage/commission modeling — [Backtrader Docs](https://www.backtrader.com/docu/)
- Mercado local (operativa)
  - pyRofex — [GitHub](https://github.com/matbarofex/pyRofex)
  - IOL API (documentación pública) — [invertironline](https://www.invertironline.com/documentacion-api)
  - BYMA Data — [Productos de datos](https://www.byma.com.ar/en/byma-apis)

---

### Entregables del MVP
- Contenedor Docker del backend (FastAPI) y del frontend (Next.js).
- Servicio de market data + estrategia corriendo y generando señales.
- Ejecución de órdenes en REMARKET (fill confirmado) y sandbox IOL.
- Dashboard con PnL en tiempo real, posiciones y log de operaciones.
- Chat con agente que responda preguntas con RAG y cite fuentes.

### Próximos pasos
1) Confirmar brokers/mercados a soportar en la primera versión (IOL + ROFEX vs. solo uno).
2) Definir universo de instrumentos para el MVP (2–3 pares) y límites de riesgo iniciales.
3) Proveer credenciales de sandbox y un correo para alertas.
4) Aprobado este plan, inicio scaffolding del repo y primeras implementaciones.
