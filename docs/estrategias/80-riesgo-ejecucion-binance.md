# Riesgo y Ejecucion en Binance (Spot + Futures)

Este archivo consolida reglas tecnicas obligatorias para evitar fallas de implementacion.

## Validaciones oficiales clave

## Spot Testnet

- WebSocket API testnet base endpoint: `wss://ws-api.testnet.binance.vision/ws-api/v3`.
- WebSocket Streams testnet base endpoint: `wss://stream.testnet.binance.vision/ws`.
- Limites WS Streams: max `5` mensajes entrantes/segundo y hasta `1024` streams por conexion.

## Spot Trading Endpoints

- `newClientOrderId` debe ser unico entre ordenes abiertas.
- `recvWindow` no puede ser mayor a `60000` ms.
- Validar filtros de `exchangeInfo` antes de enviar orden:
  - `PRICE_FILTER`
  - `LOT_SIZE`
  - `MIN_NOTIONAL`

## Futures (USDT-M)

- REST base endpoint productivo: `https://fapi.binance.com`.
- Demo/Futures test environment: `https://demo-fapi.binance.com`.
- WS testnet futures: `wss://fstream.binancefuture.com`.
- Endpoint funding history: `GET /fapi/v1/fundingRate`, weight compartido `500/5min/IP` con funding info.

## Implicancias para el agente de codificacion

1. Nunca hardcodear step size/tick size.
2. Nunca enviar orden sin normalizar precision contra filtros.
3. Usar `newClientOrderId` deterministico para idempotencia.
4. Sincronizar reloj y usar `recvWindow` razonable.
5. Preparar backoff para `429` y manejo de `418`.

## Snippet Python (validacion de filtros)

```python
from decimal import Decimal, ROUND_DOWN

def quantize(value: float, step: str) -> float:
    d = Decimal(str(value))
    s = Decimal(step)
    return float((d / s).to_integral_value(rounding=ROUND_DOWN) * s)

def validate_order(price, qty, filters):
    pf = filters["PRICE_FILTER"]
    lf = filters["LOT_SIZE"]
    mn = filters["MIN_NOTIONAL"]

    price_q = quantize(price, pf["tickSize"])
    qty_q = quantize(qty, lf["stepSize"])
    notional = price_q * qty_q

    if price_q < float(pf["minPrice"]) or price_q > float(pf["maxPrice"]):
        raise ValueError("PRICE_FILTER fail")
    if qty_q < float(lf["minQty"]) or qty_q > float(lf["maxQty"]):
        raise ValueError("LOT_SIZE fail")
    if notional < float(mn["minNotional"]):
        raise ValueError("MIN_NOTIONAL fail")

    return price_q, qty_q
```

## Estado real del repo

- Cliente de Binance orientado a Spot via proxy:
  - `backend/app/services/binance_client.py`
- Backtester implementado:
  - `backend/app/services/backtester.py`
- Engine live actual placeholder:
  - `backend/app/services/strategy.py`

## Checklist minimo antes de pasar a live/demo serio

1. Validacion local de filtros por simbolo en cada orden.
2. Reconciliacion por stream de usuario y no solo polling.
3. Manejo formal de errores HTTP/WS (reintentos y circuit breaker).
4. Pruebas de idempotencia de ordenes.
5. Simulacion de slippage realista en backtests.
