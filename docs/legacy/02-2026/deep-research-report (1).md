# Investigación profunda para un sistema multiagente de trading en BTC con ejecución por API

## Resumen ejecutivo

Este informe define una recomendación técnica “Wall Street-grade” (control de riesgo, trazabilidad, telemetría y gobernanza) para que Nahuel construya un sistema multiagente que **investiga, sintetiza evidencia, propone trades y ejecuta por API** sobre BTC (spot y short vía derivados), pero **con aprobación humana obligatoria** (HITL) y “kill-switch” desde el primer MVP. La premisa central es separar estrictamente: **(i) una capa determinista de baja latencia** (market data, order management, risk checks, ejecución) y **(ii) una capa decisoria/LLM** (research, hipótesis, señales, propuesta de orden), donde la LLM **no puede ejecutar** sin pasar por el “Risk Governor” + aprobación humana. Esta arquitectura existe precisamente porque la integración de LLMs con herramientas externas es **intrínsecamente vulnerable** a prompt injection, salida insegura y supply-chain de herramientas, según guías y literatura de seguridad. citeturn5search11turn5search2turn0search0

Recomendación prioritaria de plataforma de orquestación multiagente: **LangGraph** como “workflow kernel” para flujos stateful, pausas y reanudación con persistencia, y HITL nativo (approve/edit/reject). Esto alinea con los requisitos explícitos de durable execution y “human-in-the-loop” documentados por el proyecto. citeturn0search8turn0search7turn0search9  
Alternativas serias: **entity["company","Microsoft","software company"] Agent Framework** si el objetivo es un stack enterprise con type safety, filters y telemetría integrada, pero asumiendo su condición de “public preview” y el costo de madurez/volatilidad típico de esa etapa. citeturn0search0turn0search21  
Como control-plane (UI de aprobación humana, dashboard, configuración), **entity["company","Vercel","cloud platform company"] AI SDK** es una opción fuerte en TypeScript por su foco en tool calling, structured outputs y la introducción explícita de “Agents” en versiones recientes, además de su posicionamiento como toolkit para apps y agentes. citeturn1search20turn1search4turn1search1

En trading stack, para “rápido” (segundos/minutos, no HFT) y continuidad research→paper→live sin reescrituras, dos candidatos dominan:
- **NautilusTrader**: se define como plataforma open-source “production-grade”, event-driven, con paridad backtest↔live (mismo código de estrategia). citeturn2search1turn2search4  
- **entity["company","QuantConnect","algo trading platform"] LEAN**: motor event-driven, modular, con soporte de live trading y algoritmos en Python/C#. citeturn2search0turn2search6  

Para ejecución real en BTC (spot + derivados), **entity["company","Binance","crypto exchange"] aporta un diferencial práctico: testnet spot y testnet futures (endpoints documentados), WebSocket y detalles operativos como pings, desconexiones por tiempo y rate limits, que son críticos si querés tomar decisiones en segundos/minutos sin “mentirte” con un sistema frágil. citeturn4search5turn4search0turn4search1turn4search7  

Advertencia no negociable (objetiva): con capital inicial de **USD 1.000**, short y derivados, la probabilidad de pérdidas rápidas por volatilidad y liquidaciones existe; incluso organismos públicos argentinos remarcan la volatilidad y la posibilidad de perder todo en criptoactivos. citeturn7search1turn7search7  

## Plataformas de orquestación multiagente

La elección de framework debe priorizar: **(a) durable execution**, **(b) HITL first-class**, **(c) trazabilidad/observabilidad**, **(d) herramientas “typed/structured”**, **(e) seguridad por diseño** (permisos y sandbox), porque el dominio (trading automático) es de alto riesgo operativo.

**Matriz de decisión (scoring relativo 1–5, orientado a producción)**  
*(Los puntajes reflejan adecuación al caso específico: multiagente + HITL + auditoría + VPS core + TS control-plane. Los trade-offs se justifican debajo con evidencia.)*

| Opción | Durable/stateful + retries | HITL nativo | Observabilidad/telemetría | Ergonomía para TS control-plane | Riesgo de “demo-ware” | Score global |
|---|---:|---:|---:|---:|---:|---:|
| LangGraph | 5 | 5 | 4 | 3 | 2 | 4.4 |
| Microsoft Agent Framework | 4 | 4 | 4 | 3 | 3 | 3.8 |
| CrewAI | 3 | 3 | 3 | 3 | 3 | 3.0 |
| LlamaIndex Agents/Workflows | 3 | 2 | 3 | 3 | 3 | 2.8 |
| Vercel AI SDK (control-plane) | 2 | 2 | 3 | 5 | 3 | 3.0 |

**Justificación crítica de los puntajes**

LangGraph está explícitamente diseñado alrededor de capacidades que en trading no se negocian: **durable execution** (persistencia de estado para reanudar sin reprocesar) y **human-in-the-loop** con semántica de “approve/edit/reject”, además de enfocarse en orquestación de agentes con streaming y ejecución stateful. citeturn0search7turn0search9turn0search8

El agente framework de Microsoft se posiciona como “sucesor directo” de AutoGen y Semantic Kernel, integrando abstractions de multi-agent con state management orientado a escenarios long-running y HITL. Pero su documentación lo marca como **public preview**, lo cual en un sistema que mueve dinero implica asumir churn de APIs y comportamiento; es una apuesta razonable si querés estándar enterprise y roadmap, no si querés máxima estabilidad desde el día 1. citeturn0search0turn0search21  
Además, en Semantic Kernel se recomienda para nuevos agentes usar function calling en lugar de planners “deprecated”, lo que confirma que piezas del stack han estado en transición y hay decisiones que deben anclarse a prácticas actuales (tools/structured outputs) para minimizar riesgo. citeturn0search1turn0search4

CrewAI enfatiza “guardrails, memory, knowledge y observability baked in” y ofrece un modelo conceptual simple de agentes con memoria y delegación, lo cual acelera prototipado; aun así, el desafío típico es demostrar “durable execution” y control de reanudación/compensación al nivel que trading exige (idempotencia y recuperación). citeturn0search2turn0search6turn0search19

LlamaIndex define agentes como sistemas con LLM + memoria + herramientas, y ofrece Workflows para mayor control; es excelente para “paper reading” y agentes sobre documentos, pero no es, por sí solo, un motor de ejecución durable orientado a workflows críticos: suele brillar como capa de knowledge/document orchestration. citeturn1search0turn1search3  

Finalmente, Vercel AI SDK es especialmente fuerte como toolkit TypeScript para apps y agentes, con tool calling y structured output, y en versiones recientes anunció explícitamente soporte de “Agents”, mejoras de tools y soporte alrededor de MCP. La lectura correcta es usarlo como **control-plane/UI**, no como el núcleo determinista de ejecución de trading. citeturn1search20turn1search4turn1search1  

image_group{"layout":"carousel","aspect_ratio":"16:9","query":["LangGraph durable execution state graph diagram","Microsoft Agent Framework agent workflow diagram","Vercel AI SDK agents architecture diagram","NautilusTrader event-driven architecture diagram"],"num_per_query":1}

## Contexto justo y memoria verificable

“Contexto justo” no es una estética; es un control de riesgo contra alucinación, latencia y leakage. Dos líneas de evidencia orientan el diseño:

- RAG formaliza combinar memoria paramétrica (modelo) con memoria no paramétrica (índice recuperable) para mejorar factualidad y actualizar conocimiento sin reentrenar; a nivel práctico, esto habilita **provenir** (provenance) y actualización de fuentes, que es crítico cuando el agente “lee papers” y repos. citeturn5search0turn5search3  
- ReAct muestra que intercalar razonamiento y acciones (consulta de fuentes/herramientas) reduce errores de alucinación y mejora interpretabilidad por trazas de decisión, lo cual es útil para un workflow que termina en una propuesta de trade que un humano aprueba. citeturn5search1turn5search4  

**Arquitectura de memoria recomendada (3 capas, con límites duros)**

1) **Short-term (ventana de conversación)**: lo mínimo para el paso actual.  
2) **Working Context Pack (máx. tokens fijo)**: una “carpeta” que condensa solo: hipótesis activa, supuestos, datos recientes, señales y riesgos. La regla operativa es: si no entra acá, no es necesario para decidir ahora. (Esto fuerza disciplina y evita prompt-bloat). La disciplina de “no evidencia = no acción” también se apoya en el hecho de que el modelo no distingue perfectamente dato vs instrucción, por lo que el pack debe estar altamente curado. citeturn5search2turn5search11  
3) **Long-term KB**: resúmenes de papers/repos con metadatos (fecha, fuente, hash de contenido, tags, evaluación) y embeddings para retrieval.

Implementación con **entity["company","Pinecone","vector database company"]**: el producto habilita almacenar metadata junto con vectores y filtrar por metadata en búsqueda; eso permite “contexto justo” por **filtros deterministas** (ej., solo fuentes de los últimos N meses, o solo “primary sources”), evitando que el modelo “mezcle” contenido irrelevante. citeturn1search2turn1search22turn1search14  
Para multitenancy y aislamiento por módulos (research vs ejecución), Pinecone destaca namespaces para particionar datos y opciones de diseño para multitenancy; esto es útil si luego querés separar “sandbox” de “producción” sin contaminación semántica. citeturn1search18turn1search14  

Implementación con **entity["company","Supabase","backend platform company"]**: su propuesta de audit logs (y logs a nivel de plataforma) soporta la exigencia de que cambios, accesos y eventos queden trazados; combinado con RLS, es una base razonable para construir un “audit trail” de decisiones del agente y de aprobaciones humanas. citeturn1search7turn1search9turn1search13  

## Stack de trading y ejecución en BTC

La literatura y los repos de “agentic trading” muestran un patrón repetido: separar “departamentos” (analistas, señales, risk) y no dejar que la LLM ejecute sin gates. En repos actuales, hay frameworks explícitos multiagente que intentan imitar una mesa real, con agentes especializados y un rol de risk. citeturn8search0turn8search4turn8search3  

**Ejecución por API y testnet**

El camino más limpio para un MVP con dinero real mínimo es: **testnet primero** (spot y/o futures) y luego “small live” con límites. Binance documenta endpoints de testnet para Spot (REST) y Futures (REST/WebSocket) y detalla consideraciones operativas como: sesiones WebSocket válidas por 24 horas, pings periódicos y desconexiones; si no modelás esto, tu “trading rápido” falla por ingeniería, no por estrategia. citeturn4search1turn4search0turn4search4turn4search17  
También expone rate limits (por peso y por órdenes), reglas para órdenes no llenadas y hasta endpoints batch de órdenes en futuros, lo que obliga a diseñar un “order governor” con control de ritmo y backoff. citeturn4search7turn4search11turn4search15  

**Librerías/engines: dónde conviene “pararse”**

- **NautilusTrader** se describe como plataforma open-source de alto rendimiento, con motor event-driven, que permite backtest con fidelidad y desplegar live sin cambios de código. En términos profesionales, esto reduce riesgo de que el backtest sea una maqueta que no se sostiene en producción. citeturn2search1turn2search4  
- LEAN es un motor event-driven modular, con soporte de investigación/backtesting/live, y algoritmos en Python/C#. Es robusto, pero su integración específica a cripto/derivados depende del broker/exchange adapter y del esfuerzo de configuración. citeturn2search6turn2search0turn2search12  
- Para backtesting rápido de ideas (no para ejecución), vectorbt se enfoca en performance y experimentación a gran escala (vectorización). Es útil para “Strategy Lab”, pero no reemplaza un motor event-driven realista para ejecución. citeturn2search14turn2search22  
- Zipline/derivados de Zipline siguen siendo útiles como referencia conceptual de sistema event-driven con modelos de slippage/costos y prevención de look-ahead bias, pero su ecosistema histórico tuvo discontinuidades y forks; esto suele ser una señal de riesgo si buscás “production” sin mantenimiento fuerte. citeturn3search1turn3search17turn3search20  

**Bots/frameworks open-source como “patrones reutilizables” (no como producto final)**

- Freqtrade es un bot open-source en Python con backtesting, tooling de gestión de dinero y optimización; es un excelente “anti/ejemplo” para ver arquitectura, configuración y operación. citeturn3search2turn3search14  
- Hummingbot es un framework open-source modular para correr estrategias automatizadas en múltiples venues (CEX/DEX) con enfoque fuerte en conectores; incluso su repositorio “awesome” remarca su orientación a bots de alta frecuencia/market making, lo cual es relevante si luego explorás estrategias de microestructura. citeturn3search3turn3search18turn3search11  

**Capa de conectores: CCXT y el problema de latencia**

CCXT es una librería unificada (multi-lenguaje) para conectarse a múltiples exchanges; sirve para acelerar prototipos y reducir fricción de integración. citeturn2search2turn2search11  
Pero, para “rápido” real, la lectura profesional es: **market data por WebSocket nativo del exchange**, y CCXT como capa de conveniencia para REST, porque la variante con WebSockets (CCXT Pro) se ofrece como add-on profesional/pago. Con presupuesto de USD 20/mes, este punto define si invertís en CCXT Pro o implementás WebSockets nativos con Binance directamente. citeturn4search2turn4search6  

## Gobernanza, riesgo y seguridad

La diferencia entre un demo y un sistema que puede sobrevivir en producción no es “mejor modelo”; es **gobernanza + risk controls + seguridad de herramientas**.

**HITL y “kill switch” como controles institucionales**

El concepto de kill switch aparece consistentemente como control de riesgo en mercados automatizados: la idea es cortar el sistema cuando excede límites predefinidos o cuando hay una falla tecnológica que puede escalar. Incluso en discusiones regulatorias históricas se plantea suspender/cancelar órdenes cuando se superan umbrales. citeturn6search2turn6search8turn6search23  
En guías de industria para automatización (derivados), se remarca que el kill switch es **uno de muchos controles** y que debe formar parte de un conjunto, no ser el único “paracaídas”. citeturn6search5  

Concretamente, para tu caso (BTC + derivados + USD 1.000), un set de **límites genéricos de arranque** (no “consejo de inversión”, sino plantilla de risk engineering) que un Risk Governor debería aplicar antes de pedir aprobación humana:
- Leverage máximo conservador; bloqueo automático si el exchange/estrategia intenta elevarlo.
- Máx. pérdida diaria (hard stop) y cooldown.
- Máx. órdenes por minuto (alineado a rate limits) y degradación a “no-trade” si hay errores.
- Validación de “account health” (margen, riesgo de liquidación) antes de cada orden propuesta.
Estos no son “tips”; son controles para que el sistema no se destruya por ingeniería o por sobreoperar. Su necesidad deriva de la realidad de rate limits/mercado y del diseño de kill switches como práctica de control. citeturn4search7turn4search11turn6search5  

**Threat model específico para agentes con tools**

Los riesgos principales están estandarizados por marcos como el Top 10 de **entity["organization","OWASP","security nonprofit"] para apps con LLM: prompt injection, insecure output handling, training data poisoning y supply chain. En un agente que navega la web y ejecuta tools (trading), estos riesgos no son teóricos: forman parte del diseño base. citeturn5search11  
La investigación académica muestra que prompt injection en apps integradas con LLM puede habilitar exfiltración o abuso de la app, y que es difícil “arreglarlo” como si fuera SQL injection; por eso, el control debe estar en permisos, sandbox y gates deterministas. citeturn5search2turn5news41  

**Auditoría y trazabilidad: event sourcing + telemetría**

Para auditoría, el patrón de event sourcing formaliza registrar cada cambio como evento append-only, reconstruible, y es ampliamente documentado como patrón de arquitectura. Esto encaja con tu requisito de “auditoría completa” porque cada trade/decisión puede registrarse como evento inmutable (propuesta → riesgo → aprobación → envío → fill → post-mortem). citeturn6search0  
Para telemetría, OpenTelemetry documenta el enfoque de correlacionar logs con resource context y señales (logs/métricas/trazas). En sistemas distribuidos (VPS core + control-plane), esto es lo que permite debug y post-mortems confiables. citeturn6search1turn6search7  

## Operativa desde Argentina

La operativa desde **entity["country","Argentina","south america"]** no es un detalle: condiciona fondeo, tiempos, costos, riesgo de contraparte y compliance. La normativa cambiaria vigente se compila en el Texto Ordenado de Exterior y Cambios y normas complementarias del **entity["organization","Banco Central de la República Argentina","central bank argentina"]**; cualquier ruta de fondeo al exterior o conversiones relevantes debe analizarse contra ese marco (y puede requerir asesoramiento profesional local porque cambia con frecuencia). citeturn7search3turn7search0  

Respecto a criptoactivos, tanto el BCRA como la **entity["organization","Comisión Nacional de Valores","securities regulator argentina"]** han emitido advertencias públicas enfatizando volatilidad, riesgos y posibilidad de pérdida total; esto es especialmente material si el sistema opera derivados y short. citeturn7search1turn7search7  

**Rutas operativas (mapa inicial, para investigación y decisión técnica)**

- Broker local: **entity["company","Bull Market Brokers","broker buenos aires, ar"] se identifica como ALyC registrado y miembro de **entity["organization","Bolsas y Mercados Argentinos","argentina exchange operator"], con acceso a mercados locales; su material de soporte describe una plataforma de trading (“Matriz”) con acceso a instrumentos locales. Esto es relevante si más adelante expandís a CEDEARs/acciones, pero para BTC/derivados la ruta típica es vía exchange cripto (no por ALyC). citeturn7search2turn7search8  
- On-ramps/apps: **DolarApp** se presenta como una vía para cuentas en “dólares digitales” desde Argentina; es un candidato a estudiar por “fricción y velocidad” de fondeo, pero requiere due diligence (costos efectivos, límites, KYC, tiempos, y cómo interactúa con el resto del flujo). citeturn7search15  
- Exchange cripto y testnet: para tu MVP técnico, la ventaja de Binance es la existencia clara de testnets y documentación de conectividad para spot y futuros, que habilita pruebas end-to-end sin riesgo de dinero real (o con riesgo mínimo al pasar a live). citeturn4search5turn4search0turn4search1  

Lo profesional, dado el objetivo “tipo entity["point_of_interest","Wall Street","new york, ny, us"]”, es que el sistema produzca un “Ops/Compliance pack” con: (i) ruta(s) de fondeo, (ii) riesgos, (iii) controles, (iv) qué puntos requieren revisión legal/contable local, porque advertencias públicas y normativa cambiaria existen y el costo del error puede ser operativo o regulatorio. citeturn7search3turn7search1turn7search7  

## Roadmap de implementación

Este roadmap prioriza lo que en entornos institucionales se exige: reproducibilidad, auditoría y control, antes que “autonomía total”. El objetivo es que el sistema pueda defender decisiones con evidencia y que falle en seguro.

**MVP (2–4 semanas): paper trading + loop de aprobación humana**

- Orquestación: LangGraph como workflow kernel con durable execution y HITL (approve/edit/reject). citeturn0search7turn0search9  
- Control plane: UI en Next/TS con Vercel AI SDK para tool calling, structured outputs y experiencia de aprobación. citeturn1search20turn1search4  
- Core VPS determinista: conectores WebSocket/REST a testnet (spot o futures), risk checks y “proposal builder”. La especificación de endpoints de testnet y comportamiento WebSocket debe implementarse con reconexión y manejo de pings. citeturn4search0turn4search1turn4search17  
- Memoria: Pinecone para KB (papers/repos/resúmenes) con metadata filtering; Supabase para auditoría y configuración, aprovechando audit logs y RLS. citeturn1search2turn1search9turn1search13  
- Observabilidad: instrumentación OpenTelemetry (trazas + logs correlacionables) desde el primer día, para que cada decisión sea auditable. citeturn6search1turn6search7  
- Seguridad: threat model basado en OWASP LLM Top 10; sandbox de herramientas; permisos mínimos; bloqueo explícito de ejecución si la evidencia no está citada o si el contexto pack no justifica. citeturn5search11turn5search2  

**Producción (8–12 semanas): small live con límites + hardening**

- Engine: decidir entre NautilusTrader o LEAN según la complejidad real que quieras soportar (paridad backtest↔live vs ecosistema adapters). citeturn2search1turn2search6  
- Risk suite: kill switch + controles múltiples (pérdida diaria, DD, tasa de errores, rate limits, health de margen). Alineación con guías de controles de riesgo y evidencia de kill switch como práctica. citeturn6search5turn6search2turn4search7  
- Auditoría: event sourcing (append-only) para todo el ciclo de vida de cada trade; esto habilita reproducibilidad y reconstrucción. citeturn6search0  
- Interoperabilidad: evaluar MCP/A2A solo cuando el threat model y el control de servers quede resuelto; MCP define integración estándar con tools y context, y Microsoft documenta A2A para agentes remotos y procesos long-running, pero ambos amplían superficie de ataque si se habilitan sin controles estrictos. citeturn8search1turn8search5turn8search2turn0search0  

En paralelo, el módulo “Repo Analyst” debe estudiar repos reales de agentic trading para extraer patrones (departamentalización, risk role, debate multiagente) y también anti-patrones (LLM ejecutando sin gates). Ejemplos públicos muestran explícitamente marcos multiagente para trading y bots que operan futuros en Binance; sirven para aprender arquitectura y riesgos, no para copiar ciegamente. citeturn8search0turn8search3turn8search4turn3search2