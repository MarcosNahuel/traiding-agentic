# 03 - Incorporacion de MCP Binance

## Objetivo

Incorporar un MCP de Binance para comenzar testing simulado de forma inmediata, sin riesgo de operar en produccion por error.

## Estado real de entornos Binance (validado)

| Scope | REST base | WebSocket base | Fuente |
|---|---|---|---|
| Spot Testnet | `https://testnet.binance.vision` | `wss://stream.testnet.binance.vision/ws` | Binance Spot Testnet docs |
| Futures Demo (USDT-M) | `https://demo-fapi.binance.com` | `wss://stream.binancefuture.com/ws` (reportado por comunidad Binance) | Binance futures docs + Binance dev community |

Nota: el plan maestro actual usa `wss://testnet.binance.vision/ws/btcusdt@kline_1m` (`docs/02-2026/PLAN-TECNICO-MVP-COMPLETO.md:1090`), endpoint que no coincide con la base WS de Spot Testnet documentada.

## Recomendacion tecnica (para arrancar ya)

### Fase A - 48h (solo lectura)

- Integrar `forgequant/mcp-provider-binance` en modo local.
- Permitir solo herramientas read-only:
  - `get_server_time`
  - `get_ticker`
  - `get_order_book`
  - `get_open_orders`
  - `get_positions` (si aplica en tu variant)
- Bloquear toda tool de ejecucion (`place_order`, `cancel_order`) al inicio.

Resultado esperado:
- Validar conectividad, latencia, estabilidad MCP y formato de datos sin tocar ordenes.

### Fase B - 72h (ejecucion demo controlada)

- Mantener MCP para market data/contexto.
- Implementar `execution-adapter` determinista separado para entorno objetivo:
  - Spot testnet si vas por spot.
  - Demo Futures (`demo-fapi`) si vas por USDT-M perps.
- Habilitar ordenes solo bajo guardrails:
  - entorno DEMO obligatorio
  - notional minimo
  - max 1 posicion abierta
  - stop-loss obligatorio
  - kill-switch por error consecutivo

Resultado esperado:
- Pipeline end-to-end con control total del riesgo operativo.

## Guardrails obligatorios

1. Bloqueo por entorno:
- Si `BINANCE_ENV != DEMO`, rechazar `place_order`.

2. Allowlist de simbolos:
- Solo `BTCUSDT` inicialmente.

3. Limites de riesgo codigo:
- `maxPositionNotional`, `maxDailyLossPct`, `cooldownAfterLoss`.

4. Confirmacion de endpoint en runtime:
- Loguear base URL efectiva en cada orden.

5. Dry-run handshake antes de ejecutar:
- Verificar server time, cuenta demo y permisos de API key.

## Variables de entorno sugeridas

```env
# Entorno
BINANCE_ENV=demo_futures   # demo_futures | spot_testnet

# Spot testnet
BINANCE_SPOT_BASE_URL=https://testnet.binance.vision
BINANCE_SPOT_WS_URL=wss://stream.testnet.binance.vision/ws

# Futures demo
BINANCE_FUTURES_BASE_URL=https://demo-fapi.binance.com
BINANCE_FUTURES_WS_URL=wss://stream.binancefuture.com/ws

# Credenciales (nunca en frontend)
BINANCE_API_KEY=
BINANCE_API_SECRET=

# Kill switch
TRADING_ENABLED=false
```

## Decision para el plan maestro

- Si el objetivo inmediato es research + dashboard: integrar MCP ya (read-only).
- Si el objetivo inmediato es trading demo perps: MCP solo para data, y ejecucion via adapter propio a `demo-fapi`.
- No mezclar en una sola capa el control de riesgo con decisiones LLM.

## Cambio puntual recomendado en el plan

Agregar una seccion nueva en Fase 2:
- `Market Data Adapter` (MCP read-only)
- `Execution Adapter` (Demo endpoint + reglas duras)
- `Environment Router` (spot testnet vs futures demo)
