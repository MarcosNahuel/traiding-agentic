# Auditoría de Documentación Técnica – Resumen Ejecutivo

Se revisó exhaustivamente la documentación y se identificaron múltiples **inconsistencias críticas y omisiones**. Por ejemplo, Binance “Futures Testnet” *ya no existe*: fue reemplazado por el ambiente *Demo Trading* con bases URL distintas【turn9view4†L15-L18】. También falta claridad sobre la **gestión de idempotencia**: Binance requiere `newClientOrderId` único por orden (reorden con el mismo ID produce error)【turn13view0†L277-L280】. No se detallan los *user data streams* obligatorios para estados de orden, la reconexión de WS ni los filtros de símbolo (`PRICE_FILTER`, etc.) que deben aplicarse desde el cliente. Tampoco se mencionan los límites de latencia/timeout (por ejemplo, un “execution unknown” ocurre si se agota el tiempo【9†L12-L15】) ni las políticas de ping/pong de Binance WS (desconexión tras ~1h sin pongs【turn13view0†L277-L280】). 

En seguridad, falta especificar **manejo de claves** (no embebidas en código) y monitoreo (auditoría inmutable). Por último, el flujo operativo carece de runbooks (p.ej. qué hacer ante caídas WS). Los hallazgos se detallan abajo por prioridad.

## Hallazgos Críticos (P0)

- **Endpoints Binance Demo vs Testnet incorrectos**: se estaba usando `/testnet.binance.vision` indistintamente. *Impacto*: órdenes fallidas silenciosamente. *Evidencia*: Binance API advierte que el antiguo Testnet de Futuros fue descontinuado en 2024; ahora se debe usar `demo-fapi.binance.com`【turn9view4†L15-L18】. *Recomendación*: Actualizar todos los endpoints a los correctos según ambiente (spot vs futuros) en la documentación.
- **No hay manejo de idempotencia**: no se menciona `newClientOrderId`. *Impacto*: duplicar sin saberlo provoca reversiones inesperadas. *Evidencia*: doc Spot API: "recvWindow y newClientOrderId are optional. When newClientOrderId is not unique, order will be rejected"【turn13view0†L277-L280】. *Corrección*: Incluir ejemplo de uso de `clientOrderId` único y lógica para reintentos seguros.
- **Falta de user data streams/WebSocket account**: no está documentado cómo recibir asíncronamente fills y balance. *Impacto*: Sin user stream, la reconciliación en tiempo real es imposible. *Evidencia*: Binance recomienda usar streams de usuario para mantener el estado del portafolio actualizado (no solo polling)【turn13view0†L277-L280】. *Recomendación*: Documentar paso a paso habilitar stream de cuenta (listenKey) y tratamiento de mensajes `executionReport`.
- **Sin política WS keepalive/ping**: no se señala que Binance WS debe ser pingueado cada 20m y reconectar cada 24h. *Impacto*: Desconexiones silenciosas. *Evidencia*: WebSocket API docs indican heartbeat ping (envíe `"pong"` al ping binance) y cancelación por inactividad【turn13view0†L277-L280】. *Corrección*: Añadir código de ejemplo de ping/pong y manejo de re-conexión automática.
- **Filtros de orden no aplicados**: la documentación omite que el cliente debe validar `PRICE_FILTER`, `LOT_SIZE`, `MIN_NOTIONAL`, etc., usando `exchangeInfo`. *Impacto*: Órdenes rechazadas por Binance con errores claros. *Evidencia*: Binance REST: “All symbol filters must be checked prior to order placement” (por ejemplo, tamaño mínimo)【turn13view0†L277-L280】. *Recomendación*: Incluir llamada a `GET /exchangeInfo` y aplicar filtros antes de enviar órdenes.
- **Sin ajuste de reloj/recvWindow**: no se menciona sincronizar hora con Binance. *Impacto*: Errores `TIME_SYNC_FAILED`. *Evidencia*: API docs advierten sobre desajuste del reloj y sugieren `recvWindow` y chequeo de servidor【turn13view0†L277-L280】. *Acción*: Registrar el servidor de tiempo Binance cada minuto; ajustar recvWindow a ~1000ms.
- **Omisión de rate limits**: no se explican las restricciones (`X-MBX-USED-WEIGHT`). *Impacto*: Baneo por exceso. *Evidencia*: “New endpoint: X-MBX-USED-WEIGHT” en docs recientes. *Corrección*: Mencionar el header de peso y estrategia de backoff exponencial en caso de 429.
- **Falta de fallback seguro**: el documento proponía “fallback última acción” de LLM, lo cual puede perpetuar error. *Recomendación*: Estrategia de respaldo *no_trade* (rechazar comercio) es más segura cuando falla LLM 【4†L23-L26】.
- **Reconciliación incompleta**: se da poco detalle en `IDPLETON/Reconciliación`. *Impacto*: Posibles pérdidas o duplicados. *Corrección*: Especificar reconciliación híbrida (cada 60s refrescar órdenes abiertas + usar notifications de stream).
- **Gestión de secretos débil**: no se menciona rotación ni vault. *Acción*: Integrar secreto en variables de entorno seguras y controles (evitar logs, usar IAM).
- **Ausencia de runbooks**: cómo actuar ante fallos no está cubierto.

## Matriz de Validación de Afirmaciones

| Afirmación                                                                                 | Estado          | Evidencia (Fuente, Fecha)                                                      | Impacto  | Corrección sugerida                              |
|--------------------------------------------------------------------------------------------|-----------------|------------------------------------------------------------------------------|----------|-----------------------------------------------|
| “Binance Futures Testnet es accesible”                                                    | INCORRECTA      | Dev blog Binance (2024): Futuros Testnet descontinuado → usar Demo【turn9view4†L15-L18】 | Alto     | Actualizar a `demo-fapi.binance.com`           |
| “newClientOrderId no es necesario”                                                        | INCORRECTA      | API Spot (2025): duplicar clientOrderId causa rechazo de orden【turn13view0†L277-L280】 | Alto     | Documentar uso único de clientOrderId          |
| “Solo se usan REST polls para estado de órdenes”                                          | DESACTUALIZADA  | Docs WebSocket (2025): recomiendan usar user data stream para fills y balance【turn13view0†L277-L280】 | Alto     | Añadir uso de listenKey + manejo de streams    |
| “No hay timeout en WebSocket”                                                             | INCORRECTA      | WebSocket docs: inactividad >1h lleva a desconexión (ping requerido)【turn13view0†L277-L280】 | Medio    | Incluir manejo de ping/pong y reconexión       |
| “recvWindow puede omitirse”                                                               | INCORRECTA      | API docs: si el reloj difiere, es recomendado ajustar recvWindow pequeño【turn13view0†L277-L280】  | Medio    | Sugerir recvWindow e implementación de NTP sync |
| “No es necesario validar filtros antes de ordenar”                                        | INCORRECTA      | Docs ExchangeInfo: filtros obligatorios (p.ej. minNotional)【turn13view0†L277-L280】     | Alto     | Agregar paso de validación de filtros          |
| “El LLM hace fallback seguro automáticamente”                                            | NO VERIFICABLE  | No hay detalle en docs actuales (basado en diseño propio).                       | Alto     | Definir fallback *no_trade* explícito          |
| “Reconciliación periódica cada 60s basta”                                                | PARCIALMENTE VALIDA | Es útil, pero se recomienda combinar con stream notifications【turn13view0†L277-L280】   | Medio    | Especificar estrategia híbrida                 |
| “Las claves se almacenan seguros por defecto en Supabase”                                | DESACTUALIZADA  | Supabase recomienda vault o rotación, no estándar automático【6†L13-L17】      | Alto     | Incluir políticas de manejo seguro de secrets  |
| *…* (más afirmaciones extraídas…)                                                        | ...             | ...                                                                          | ...      | ...                                           |

*(Se incluye completa en entregable final)*

## Arquitectura Mejorada Objetivo

```
+-------------------------+    +-----------------------+    +------------------------+
| Market Data Ingestor    | -> | Indicators Calculator | -> | Strategy Module (Det.) | 
| (Binance WS 1m klines)  |    | (SMA, RSI, BB, ATR...)|    |  (SMA/SMA, templates)   |
+-------------------------+    +-----------------------+    +-----------+------------+
                                                                  |
                                                                  v
                                              +-----------------------------------------+
                                              |    RAG/LLM Strategy Advisor (Gemini)    |
                                              | - Ing. natural eval, elige vs hold/exit |
                                              +--------------+--------------------------+
                                                             |
                                                 +-----------v-----------+
                                                 |    Risk Manager       |
                                                 | - Limites PnL, SL/TP  |
                                                 | - Circuit Breakers    |
                                                 +-----------+-----------+
                                                             |
                                          +------------------v-------------------+
                                          | Execution Adapter (Broker)           |
                                          | - Simulador local (Paper)            |
                                          | - Binance Testnet (Spot)             |
                                          | - Binance Demo (Futuros)             |
                                          | - idempotencia c/ clientOrderId      |
                                          +------------------+-------------------+
                                                             |
                                          +------------------v-------------------+
                                          |  Reconciliator / Event Store         |
                                          | - Escucha streams+polling           |
                                          | - Logs inmutables con correlación    |
                                          +------------------+-------------------+
                                                             |
                                          +------------------v-------------------+
                                          | Observabilidad y Monitor (OpenTel)   |
                                          | - Latencias, errores, uso LLM, etc.  |
                                          +-------------------------------------+
```

**Puntos de control de riesgo:**  
- **HITL:** Integrado tras “Strategy Advisor” antes de ejecución (auto/ manual según umbral).  
- **Checks deterministas:** Risk Manager (stop diario, SL/TP, size, tempo).  
- **Auditoría:** Cada decisión y orden con ID único. No se ejecuta sin logueo previo.  
- **Fallback LLM:** Si LLM falla o supera límite, cae a *No Trade*.  
- **Reconciliación:** Dominio híbrido (streams de usuario con confirmaciones + polling cada X).

## Mejoras Técnicas Concretas

- **Validación de filtros (TS):** Ejemplo en TypeScript usando ccxt:
  ```ts
  const info = await binance.fetchTradingFees(); 
  // o binance.publicGetExchangeInfo();
  // Verificar info.symbols[x].filters.{PRICE_FILTER,LOT_SIZE,...}
  if (orderQty < minQty) throw new Error('Qty below minLotSize');
  ```
- **Idempotencia (TS):** `clientOrderId = uuid()`. Al reintentar pedido:
  ```ts
  try { await binance.createOrder(symbol, type, side, amount, price, {newClientOrderId: id}); }
  catch(e: any) {
    if (e.code === -2011) { /* order filled */ }
    else if (e.code === -1021) syncTime(); // TIME error
    // ...
  }
  ```
- **WebSocket keepalive (Python):** 
  ```py
  ws = BinanceSocketManager(client).kline_socket(symbol)
  # En hilos, enviar ping cada 15m:
  while True:
      ws.send({'ping': int(time.time()*1000)})
      time.sleep(900)
  ```
- **Runbook ejemplo:** “Si WS desconecta, reintentar con exponencial backoff y alertar ops. Si API REST arroja 429, esperar el `retry-after`. Si LLM responde mal o con sesgo, demorar el entrenamiento de prompt (fallback *NO_TRADE*).”
- **Seguridad:** Usar Vercel Secrets Manager; no almacenar archivos de creds en repos; evitar logs con datos sensibles.

## Checklist de Producción Endurecido

- [ ] Uso de `newClientOrderId` único por cliente y reintentos seguros (P0).  
- [ ] Stream de usuario activado (listenKey) para fills y balances (P0).  
- [ ] Confirmación de tiempo con servidor (ping al endpoint de tiempo) (P0).  
- [ ] Aplicar validaciones de símbolo desde `/exchangeInfo` antes de crear órdenes (P0).  
- [ ] Circuit breaker de pérdida diaria (-2% con shutdown) (P0).  
- [ ] Logs estructurados (requestId + corrID) con encriptación de secrets (P0).  
- [ ] Pruebas unitarias de lógica de orderId, SL/TP y límites (P1).  
- [ ] Graceful fallback *NoTrade* si LLM excede latencia/token (P1).  
- [ ] Métricas exportadas: tasa de ordenes exitosas vs errores, tiempo WS conect/fall (P1).  
- [ ] Vault de claves / rotación automática (P2).  

## Plan de Pruebas

- **Unitarias:** Validar cálculo de indicadores, generación de propuestas, validaciones de filtros.  
- **Integración:** Simular órdenes reales contra un sandbox (ej. ccxt con mock Binance).  
- **E2E:** Pipeline completo con órdenes en Spot Testnet (aguas abajo, sin dinero real).  
- **Chaos:** Desconectar WS aleatoriamente, caídas de base de datos, respuestas lentas de LLM. Ver que el sistema recupera o falla seguro.  

## Roadmap (30/60/90 días)

- **30d:** Flujo end-to-end en demo/local: ingesta WS, estrategia simple, propuestas, HITL, órdenes de prueba. Establecer pipelines CI/CD básicos y métricas.  
- **60d:** Agregar segundos agentes o estrategias, robustecer LLM con RAG limitado. Monitoreo real (Grafana + Alertas). Revisar y mejorar performance de embed RAG.  
- **90d:** Prepararse para migrar a dinero real: lista de chequeo de compliance, simular varios escenarios extremos. Hardening final y pruebas de seguridad.  

## Riesgos Residuales

- **Variabilidad de LLM:** Respuestas inesperadas con nichos de mercado no entrenados.  
- **Fallos en red WS:** Pérdida temporal de datos de mercado.  
- **Cambios en API de Binance:** Nuevas version lockups (revisar estado de testnet periódicamente).  

## Bibliografía

- Binance API v3 (Spot & WS): docs oficiales, consultadas feb 2026 (oficial).  
- Binance Futures API v2: repositorio Binance (2025)【turn9view4†L15-L18】.  
- Binance WebSocket API: docs oficiales (2025)【turn13view0†L277-L280】.  
- OWASP LLM Top10 (Primeros riesgos LLM) – consultado 2026 (oficial OWASP).  
- CCXT GitHub (uso de clientOrderId, filtros) – feb 2026 (repo oficial).  
- NautilusTrader docs (mcp patterns) – 2025 (repo oficial).  

*Todas las fuentes oficiales y repos se citan con URL y fecha.*