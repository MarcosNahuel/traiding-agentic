# 02 - Binance API, testnet y demo: guia operativa

## 1) Entornos y endpoints recomendados

## Spot Testnet

- REST base: `https://testnet.binance.vision`
- REST API path: `/api` (solo `/api`, sin `/sapi`)
- WS streams base: `wss://stream.testnet.binance.vision/ws`

Notas:
- Binance indica reset de Spot Testnet aproximadamente mensual (sin aviso).
- Las API keys de testnet se preservan, pero balances/ordenes pueden resetearse.

## Spot Demo Trading

- Endpoint: `https://api-demo.binance.com`
- Objetivo: usar mismas reglas/limites del Spot live en modo de practica.
- Segun FAQ oficial, usa mismas API keys y restricciones (incluyendo IP whitelist) que Spot live.

Uso sugerido:
- `spot_testnet`: integracion inicial y pruebas rapidas.
- `spot_demo`: hardening previo al paso live por mayor paridad operativa.

## USDT-M Futures

- Mainnet REST: `https://fapi.binance.com`
- Testnet REST: `https://testnet.binancefuture.com`
- Demo REST: `https://demo-fapi.binance.com`
- WS testnet/demo (market streams): `wss://fstream.binancefuture.com`

## 2) Autenticacion y firma

- Endpoints `SIGNED` requieren `timestamp` y `signature`.
- Binance valida ventana temporal con `recvWindow`.
- Recomendacion: sincronizar clock local contra `serverTime` y monitorear drift.

## 3) Limites y rate limiting

Puntos clave:

- Hay limites por `REQUEST_WEIGHT` y por ordenes.
- Binance expone uso en headers (`X-MBX-USED-WEIGHT-*`, `X-MBX-ORDER-COUNT-*`).
- Exceder limites puede terminar en `429`, escalando a bloqueo temporal de IP.

Accion tecnica:

1. Rate limiter por tipo de request (market data, account, orders).
2. Backoff exponencial con jitter.
3. Presupuesto de peso por minuto y alertas al 80%.

## 4) Filtros de simbolo (validacion previa obligatoria)

Tomar `exchangeInfo` y validar antes de enviar orden:

- `PRICE_FILTER`
- `LOT_SIZE`
- `MIN_NOTIONAL` o `NOTIONAL`
- `PERCENT_PRICE` / `PERCENT_PRICE_BY_SIDE`

Esto evita rechazos evitables y protege la metrica de error rate.

## 5) Idempotencia real y manejo de "estado desconocido"

Hechos oficiales:

- En Spot, `newClientOrderId` repetido solo se acepta cuando la orden previa con ese ID ya esta llena.
- Binance puede devolver timeout con estado de ejecucion desconocido.

Patron recomendado:

1. Generar `clientOrderId` determinista por propuesta.
2. En timeout/error ambiguo: consultar estado por `clientOrderId`.
3. Si existe orden abierta/ejecutada, no reenviar.
4. Solo si no existe y el intento es confirmadamente fallido, evaluar retry.

## 6) User data streams (estado de cuenta/orden)

## Spot

- En WebSocket API testnet, se puede usar:
  - `userDataStream.subscribe` (requiere `session.logon` con Ed25519)
  - `userDataStream.subscribe.signature` (firmado por request; util con HMAC/RSA/Ed25519)

## Futures

- User stream tiene expiracion si no se hace keepalive.
- Regla practica: enviar keepalive aproximadamente cada 60 minutos.
- Binance recomienda usar user streams para evitar latencia de consultas REST para estado de orden.

## 7) Reglas de WebSocket a respetar

## Spot testnet streams

- Conexion dura maximo 24h.
- Ping del servidor aprox cada 20s; responder pong rapido.
- Limite de mensajes entrantes por segundo (controlar suscripciones/pings).

## Futures streams

- Conexion dura maximo 24h.
- Ping aprox cada 3 minutos, con timeout de pong definido por Binance.
- Limite de mensajes entrantes por segundo por conexion.

Accion tecnica:

- Implementar gestor de reconexion con backoff + resuscripcion automatica.
- Evitar crear conexiones masivas por simbolo si se puede multiplexar.

## 8) Mapa de variables de entorno sugerido

```env
# Enrutamiento unico
TRADING_ENV=simulated  # simulated | spot_testnet | spot_demo | futures_demo

# Spot
BINANCE_SPOT_TESTNET_REST=https://testnet.binance.vision
BINANCE_SPOT_TESTNET_WS=wss://stream.testnet.binance.vision/ws
BINANCE_SPOT_DEMO_REST=https://api-demo.binance.com

# Futures
BINANCE_FUTURES_DEMO_REST=https://demo-fapi.binance.com
BINANCE_FUTURES_DEMO_WS=wss://fstream.binancefuture.com

# Seguridad
BINANCE_API_KEY=
BINANCE_API_SECRET=
BINANCE_RECV_WINDOW_MS=5000
```

## 9) Recomendacion de adopcion por etapas

1. `simulated` con replay historico y validacion completa.
2. `spot_testnet` para validar conectividad + firma + flujos de orden.
3. `spot_demo` para acercarse a restricciones de live.
4. `futures_demo` solo cuando riesgo y reconciliacion esten probados.

