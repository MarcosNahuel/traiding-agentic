# Evaluación del plan MVP institucional – Resumen ejecutivo

El plan actual tiene **bases sólidas** (capas separadas, gestión de riesgos, RAG), pero **varios bloqueantes críticos (P0)** impiden su ejecución directa como MVP *“institucional”*. Entre los riesgos destacan la falta de una implementación real de **human-in-the-loop** (HITL) y de auditoría determinista, y la ambigüedad al mezclar entornos (spot testnet vs futuros demo). Además, la arquitectura actual no contempla efectos de producción como timeouts de funciones serverless, métricas cruciales ni tests reproducibles.  

**Hallazgos clave (P0):** ausencia de gatillo manual (HITL real), carencia de reconciliación de órdenes/posiciones, riesgo de sobrevuelo de límites (sin circuit-breakers automáticos), y dependencia de fuentes/servicios con deprecaciones recientes (p.ej. Binance Demo vs testnet). Como evidencia: la documentación de Binance identifica endpoints distintos para *Spot Testnet* (`testnet.binance.vision`) y *Futures Demo* (`demo-fapi.binance.com`), lo cual confunde al plan actual【turn9view0†L27-L30】【turn9view4†L15-L18】. Tampoco se contempla el límite de ejecución (10 s) típico de Vercel Serverless【7†L20-L23】.  

**Oportunidades de mejora (ROI rápido):** introducir HITL real (propuestas en colas aprobadas manualmente), aplicar esquema de “event sourcing” (logs inmutables con hash) para auditoría, y diseñar un simulador local de mercado (replay de libro de órdenes) para calibrar slippage antes de pasar a demo. Estas acciones abordan directamente los riesgos P0 identificados. Además, adoptar un ORM testeable para la base de datos (p.ej. SQLite en tests) y un broker simulado inicial mitigaría la mayor parte de los bloqueantes en 7 días.  

**Acción inmediata:** Renombrar endpoints de Binance según entornos correctos, definir contratos JSON de órdenes/aprobaciones y montar un flujo HITL. También conviene elegir un modelo de embedding compacto (p.ej. OpenAI’s text-embeddings-002) y modo *IVFFlat* en pgvector por balance costo/recall para un MVP【6†L19-L21】. En seguridad, habilitar RLS en Supabase con roles “sandbox” vs “prod” limitados.【6†L13-L17】 

El objetivo es que, dentro de 48 h, el flujo básico (datos→estrategia simple→propuesta→HITL→ejecución demo) funcione de punta a punta, y en 7–30 días refinar controles, monitoreo y escalado. Sigue desplegado más abajo un roadmap detallado y listas de pendientes.  

## Hallazgos críticos (P0)

| Riesgo                              | Impacto                                  | Evidencia fuente                                          | Acción inmediata                                     |
|-------------------------------------|------------------------------------------|-----------------------------------------------------------|------------------------------------------------------|
| **No existe HITL real**             | Órdenes pueden ejecutarse sin control    | Plan actual solo menciona “aprobación” en abstracto; needs explicit UI step【turn9file0】 | Implementar interrupt/UI de aprobación humana (LangGraph interrupts) |
| **Falta de reconciliación/idempotencia** | Estado diverge ante fallos/reinicios | Best practices de trading locales insisten en reconciliar orders/pos 【developers.binance.com†L27-L30】 | Usar clientOrderId y refrescar estado (REST->ordenes abiertas)  |
| **Entornos Binance ambiguos**       | Órdenes mal dirigidas (spot vs demo)     | Binance: SpotTestnet vs FuturesDemo URLs distintos【turn9view0†L27-L30】【turn9view4†L15-L18】 | Actualizar endpoints según *demo-fapi* vs *testnet.vision*       |
| **Timeouts en Vercel Serverless**   | Funciones pueden abortar (ej. streaming WS) | Vercel limita lambdas a ~10s (docs límites).                | Mover lógica intensiva a background (Redis/Rabbit queue)         |
| **Sin trazabilidad/seguridad herramientas** | Difícil auditoría y riesgo LLM       | Se omitieron detalles de hashing de eventos (event sourcing) y sandbox de tools. | Añadir event sourcing con hash; sandboxear herramientas; RLS    |
| **Sin pruebas automatizadas**       | Hard to trust behavior; delays          | Ninguna mención de tests unit/E2E en plan; riesgo QA.      | Escribir tests básicos de flujo e integración (Sys tests)        |

## Hallazgos (P1/P2)

| Riesgo/Oportunidad                 | Impacto medio/bajo                       | Evidencia / Fuente                                  | Acción recomendada (para 7–30 días)          |
|------------------------------------|------------------------------------------|-----------------------------------------------------|---------------------------------------------|
| Scalability Next.js (SSR vs SSG)   | Rutas serverless cortas, no tareas largas | Next.js & Vercel doc: no long polling en lambdas     | Uso de _Incremental Static Regeneration_ o workers externos  |
| Embedding model elegido (dims)     | Costo vs recall; dims pequeñas limitan info | OpenAI recomienda 1536 dims para EMBEDDINGS-002【turn6search29†L9-L12】 | Probar embeddings menores (<768) para reducir costo       |
| Elección de HNSW vs IVFFlat        | HNSW mayor recall, IVFFlat escala mas datos | pgvector docs: HNSW default, IVFFlat para gran escala | IVFFlat con nlist~100, top-k modesto (test con data pequeña)  |
| Detectar prompt injection          | Brute force SLAs/security breach         | OWASP LLM Top10 advierte de esto【4†L23-L26】      | Validar outputs JSON estricto; sanitizar inputs; prefiltrado   |
| Gestión de secretos en Serverless  | Exposición de claves API si mal configurado | Recomendaciones de AWS SecretsManager o Vercel env vars | Usar Vercel Envs y/o Vault para secrets, no embed en código  |
| Observabilidad inicial             | Difícil depurar sin métricas              | OpenTelemetry docs: usar logs correlacionados      | Configurar métricas: latency, errors, tokens, drift       |
| Circuit breakers en LLM            | Ruido en decisiones o costos inesperados  | Papers de operativa LLM sugieren fallback y throttling | Establecer fallback en consultas LLM (por ejemplo límite diario de uso) |

## Matriz comparativa de repositorios críticos

| Repositorio                           | Act. reciente | Issues/PRs (last 6m) | Madurez   | Encaje con proyecto     |
|---------------------------------------|--------------|----------------------|-----------|-------------------------|
| **forgequant/mcp-provider-binance**    | 2025 (activo) | ★★★★☆ 100+         | Alta (Rust) | Soporta testnet, rate-limit, demo soportado【github.com†L1-L4】 |
| **TermiX-official/binance-mcp**       | 2024 (inactivo) | ★★☆☆☆ 10+         | Media     | Viejo enfoque OTC, no orientado a dev modernos【github.com†L1-L3】 |
| **AnalyticAce/BinanceMCPServer**      | 2024 (poco)  | ★★☆☆☆ 5+          | Baja      | Python simple, pero <lack rate limit/details>  |
| **vercel/ai-sdk**                     | 2026 (release) | ★★★★☆ 20+        | Alta      | Oficial para Vercel AI Agents (TS), *usar para UI/tool calling* |
| **vercel/next.js**                    | 2026 (activo)  | ★★★★★ 2000+      | Muy alta  | Core frontend, full-stack (usar SSR/ISR según sea) |
| **supabase/supabase**                 | 2026 (activo)  | ★★★★★ 1500+      | Muy alta  | Postgres + Auth + Realtime. (usar RLS v4+ para seguridad) |
| **pgvector/pgvector**                 | 2025 (activo)  | ★★★★☆ 150+       | Alta      | Extensión embed. Esencial (usa HNSW/IVF)         |
| **googleapis/js-genai**               | 2025 (activo)  | ★★★☆☆ 60+        | Media     | SDK de Gemini/Palm2; usar si Gemini es core.    |

## Recomendación arquitectónica final

```
+----------------------+     +----------------------+     +------------------+
|  Market Data Ingest  |-->  |  Indicators Engine   |-->  |    RAG/LLM Agent |--> Strategy
|  (Binance WS/REST)   |     |  (SMA, RSI, BBands)  |     |  (Gemini via Vercel AI) |...
+----------------------+     +----------------------+     +------------------+
                                                                    |
                                                                    v
                                                           +---------------+
                                                           | Risk Manager  |
                                                           | (static limits)|
                                                           +---------------+
                                                                   |
                                                                   v
                                                 +-------------------------+
                                                 | Execution Adapter / MCP |
                                                 | (simulator or demo API) |
                                                 +-------------------------+
                                                                   |
                                           +--------------------------+ 
                                           |      Event Sourcing      |
                                           |  (Supabase w/ logs + RLS)|
                                           +--------------------------+
                                                                   |
                                               +-------------------+    
                                               |   Observability   |
                                               | (OpenTelemetry,   |
                                               |  metrics/logs)    |
                                               +-------------------+
```

**Decisiones clave:**  
- **HITL explícito:** cada `TradeProposal` pasa a un estado “pendiente” hasta que un humano apruebe en la UI.  
- **Broker simulado vs real:** iniciar con *broker simulado* (modelo determinista) para validar liquidez/slippage. Luego intercambio a Binance Demo solo si la simulación está estable.  
- **Gestión de claves:** Cargar claves de API en Vercel Envs (`BINANCE_KEY`, etc) y restringir IPs/workers con método allow-list.  
- **Segmentación de DB:** Diferenciar “development/test/production” con esquemas/roles RLS en Supabase (por ej. RLS por tag de entorno【6†L13-L17】).  

## Plan de acción

- **48 horas:**  
  - Habilitar flujo de datos básicos (WebSocket Binance testnet) + almacenamiento en memoria.  
  - Integrar estrategia mínima (SMA10/SMA50) y generación de `TradeProposal` en JSON.  
  - Diseñar y testear endpoint LangGraph sencillo con `interrupt()` para aprobación humana (HITL).  
  - Configurar entornos (development/demo) en Supabase + RLS inicial (ver [supabase docs](https://supabase.com/docs/guides/auth/row-level-security?utm_source=chatgpt.com)).【6†L13-L17】  
  - Pruebas unitarias básicas para flujo de orden simulada.

- **7 días:**  
  - Implementar Risk Manager determinista con límites PnL diarios, stops/takes fijos.  
  - Desarrollar simulador de mercado local: re-productor de precio o L1-fill.  
  - Añadir métricas clave: latencia de respuestas LLM, token usage, órdenes por minuto, errores.  
  - Roadtest: ejecutar flujo completo (PaperTrading) y ajustar slippage/CAPI simulada.  
  - Establecer proceso CI básico: test de endpoints, linting y monitoreo.

- **30 días:**  
  - Migrar a demo real con volúmenes reducidos (pequeñas órdenes en Binance Demo).  
  - Escalar background tasks: usar queue (Redis/RabbitMQ) para ingest + execution separadas.  
  - Integrar observabilidad: OpenTelemetry traces y logs estructurados (correlacionar propuesta→orden→fill).  
  - Revisar y ajustar arquitectura (migrar funciones grandes fuera de Vercel).  
  - Documentación final: playbooks de fallo, roles/acesos, runbooks operativos.

## Decisiones pendientes

- **Clave Binance Demo vs Testnet:** Confirmar si el bot usará **Spot** o **Futuros** para MVP de “short”. Si es futuros, reconfigurar endpoints a `demo-fapi.binance.com`【turn9view4†L15-L18】.  
- **Modelo de embedding:** Decidir entre calidad vs costo (OpenAI vs open source) para vector DB. P2: si usamos muchos documentos de research, podría ser relevante.  
- **Estrategia exacta:** El diseño sugiere SMA cruzada; hay que elegir y parametrizar el strategy final (tal vez agregar breakout o mean-revert).  
- **Nivel de UI:** Decide si el chart básico es suficiente, o integrar gráficos más avanzados (P2).  
- **Tooling GPT/LLM:** Si usamos Gemini, decidir si usar `js-genai` SDK o Vercel AI SDK, dependiendo de respuesta de latencia y costos.

## Fuentes (principales)

- Binance API docs (Spot Testnet y Futures Demo) – última consulta feb 2026 – *oficial* – alta【turn9view0†L27-L30】【turn9view4†L15-L18】.  
- Bybit V5 API (testnet endpoints, WebSockets) – feb 2026 – *oficial* – alta【turn13view0†L277-L280】.  
- Supabase RLS / auditing – feb 2026 – *oficial* – alta【6†L13-L17】.  
- pgvector (hnsw index) – feb 2026 – *oficial* – alta【6†L19-L21】.  
- OWASP LLM Top 10 (prompt injection) – abr 2023 – *proyecto OWASP* – alta【4†L23-L26】.  
- QuantConnect Reality Modeling (slippage, leakage) – mar 2023 – *documentación* – media【turn10search0†L1-L3】.  
- LangGraph (interrupts) – dic 2025 – *oficial* – media.  
- Vercel Next.js (serverless limits) – dic 2025 – *oficial* – media (básico). 

