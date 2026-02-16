# Prompt de Investigacion Ultra Estricta (Sin Referencias a Documentos)

Actua como auditor tecnico senior de trading algoritmico, ingenieria de plataformas y sistemas multiagente.

Objetivo:
Realizar una investigacion profunda en la web para validar, corregir y ampliar una documentacion tecnica de un bot de trading de BTC/USDT en paper trading, con enfoque en Binance API, seguridad operativa, robustez de ejecucion e infraestructura de produccion.

Contexto completo del sistema (base a auditar):
1. Arquitectura general:
- Stack: Next.js, API backend en TypeScript, Supabase/PostgreSQL, vector search, LLM (Gemini), observabilidad operativa.
- Dos fases:
  - Fase de investigacion: agentes que curan fuentes, extraen estrategias y generan una guia maestra.
  - Fase de trading: bot que usa esa guia para proponer operaciones.

2. Flujo de trading:
- Ingesta de mercado por WebSocket de Binance (klines 1m).
- Calculo de indicadores: SMA10, SMA50, RSI14, Bollinger Bands, volumen promedio/ratio, ATR14.
- Cada 5 minutos el LLM propone una accion, pero nunca envia orden directa.
- La salida del LLM es un TradeProposal que pasa por un Risk Manager determinista.
- HITL hibrido:
  - Ordenes con notional < 100 USDT: auto-aprobacion.
  - Ordenes con notional >= 100 USDT: aprobacion manual.
  - SLA de aprobacion: 5 minutos (si no, expira).
- Estados esperados del proposal: draft, validated, auto_approved, pending_approval, approved, rejected, expired, risk_rejected, executed, failed, cancelled.

3. Ejecucion:
- Adaptadores de broker:
  - Simulador local con slippage/latencia/replay.
  - Binance Spot Testnet.
  - Binance Futures Demo.
- Idempotencia por client_order_id.
- Reconciliacion periodica (cada 60s).
- Dead-letter para fallos repetidos.

4. Riesgo y seguridad:
- Limites base: perdida diaria max 2%, tamano de posicion reducido, una posicion abierta, SL/TP, sin apalancamiento en MVP.
- Circuit breakers en 3 categorias: trading, infraestructura y LLM.
- Logs inmutables con correlation_id para trazabilidad end-to-end.
- Metricas operativas: fill rate, rejection rate, slippage, divergencias de reconciliacion, costos LLM, Sharpe rolling, win rate, tiempos de aprobacion/ejecucion.

Hipotesis y puntos criticos que DEBES validar:
1. Comportamiento real de idempotencia con newClientOrderId en Binance.
2. Manejo correcto de "execution unknown" por timeout.
3. Necesidad y diseno de user data streams vs polling.
4. Keepalive y expiracion de streams.
5. Limites y reglas de WebSocket (ping/pong, duracion de conexion, limites de mensajes).
6. Validacion previa de filtros de simbolo (PRICE_FILTER, LOT_SIZE, MIN_NOTIONAL/NOTIONAL, etc.).
7. Sincronizacion de reloj y recvWindow.
8. Rate limits y estrategia de throttling/backoff.
9. Riesgo de "fallback a ultima decision LLM" vs fallback seguro "NO_TRADE".
10. Diseno de reconciliacion hibrida (event-driven + polling).
11. Seguridad de claves, secretos, logging y hardening operativo.
12. Patrones de arquitectura de bots open-source reutilizables sin copiar ciegamente.

Alcance de investigacion en web:
1. Prioriza fuentes primarias:
- Documentacion oficial de Binance (Spot, Futures, Testnet, Demo, WS, user streams, filtros, firmas, errores).
- Repos oficiales de conectores Binance.
- Repos open-source consolidados de trading bots/frameworks.
2. Fuentes secundarias (blogs/videos) solo como complemento y etiquetadas como "secundarias".
3. Cada afirmacion debe tener evidencia y fecha de consulta.
4. Si hay incertidumbre, declarala explicitamente.

Entregables obligatorios (formato exacto):
A) Resumen ejecutivo (maximo 15 lineas).
B) Hallazgos criticos ordenados por severidad (P0, P1, P2).
C) Matriz de validacion de afirmaciones:
- Afirmacion
- Estado (VALIDA / PARCIAL / DESACTUALIZADA / INCORRECTA / NO VERIFICABLE)
- Evidencia
- Impacto
- Correccion recomendada
D) Arquitectura objetivo mejorada:
- Componentes
- Flujos
- Estados
- Puntos de control de riesgo
E) Mejoras concretas de implementacion:
- Cambios tecnicos recomendados
- Snippets de codigo listos (TypeScript/Python cuando aplique)
- Reglas operativas y runbooks minimos
F) Checklist de produccion endurecido.
G) Plan de pruebas:
- Unit
- Integracion
- E2E
- Chaos/fallos de red/timeouts/reintentos
H) Roadmap 30/60/90 dias con prioridades.
I) Riesgos residuales no resueltos.
J) Bibliografia final con URL y fecha de consulta.

Criterios de calidad:
1. Precision tecnica por encima de volumen.
2. Recomendaciones accionables, no genericas.
3. Distingue claramente hechos verificados vs inferencias.
4. Redacta todo en espanol tecnico claro.
5. Entrega el resultado listo para convertirse en documentacion operativa y plan de implementacion.

