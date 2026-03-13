# Auditoria Backend Trading

Fecha: 2026-03-13

Objetivo: dejar un informe operativo para que otro agente valide cada hallazgo y aplique fixes si corresponde.

Alcance revisado:

- `backend/app/config.py`
- `backend/app/services/signal_generator.py`
- `backend/app/services/quant_risk.py`
- `backend/app/services/executor.py`
- `backend/app/services/trading_loop.py`
- `backend/app/services/risk_manager.py`
- `backend/app/services/reconciliation.py`
- `backend/app/services/portfolio.py`
- `backend/app/services/entropy_filter.py`
- `backend/app/services/regime_detector.py`
- `backend/app/services/position_sizer.py`
- `backend/app/services/technical_analysis.py`
- `backend/app/routers/proposals.py`
- `backend/app/models/quant_models.py`
- `backend/tests/`

Estado de tests al momento de la auditoria:

- `pytest backend/tests -q`
- Resultado: `69 passed`
- Nota: la suite esta verde, pero no cubre varios paths de mayor riesgo operativo detallados abajo.

## CRITICO

### 1. Ejecucion duplicada del mismo proposal por falta de lock/claim atomico

- Archivo y linea:
  - `backend/app/services/executor.py:21`
  - `backend/app/services/executor.py:66`
  - `backend/app/services/trading_loop.py:26`
  - `backend/app/services/trading_loop.py:137`
  - `backend/app/services/signal_generator.py:269`
  - `backend/app/routers/proposals.py:112`
  - `backend/app/routers/execute.py:19`
- Problema:
  - `execute_proposal()` hace `read -> place_order -> update` sin lock ni compare-and-swap.
  - El mismo proposal `approved` puede ser tomado por multiples callers: main loop, SL/TP loop, endpoint manual, auto-exec de señales y retry de dead-letter.
- Impacto concreto:
  - Puede mandar dos ordenes reales a Binance para el mismo proposal.
  - Puede abrir dos posiciones o cerrar dos veces la misma.
  - Si Binance ejecuta la orden y luego falla la escritura de DB, queda una orden real sin reflejo consistente en estado interno.
- Fix sugerido:

```python
# Pseudocodigo
claimed = update trade_proposals
set status = "executing", claimed_at = now(), executor_id = <uuid>
where id = :proposal_id and status = "approved"
returning *

if not claimed:
    return {"success": False, "error": "already claimed"}

try:
    order = await place_order(...)
    # persist proposal + position + risk_event via RPC/transaccion idempotente
except Exception:
    update trade_proposals set status = "error", ...
```

### 2. Partial fills rompen el modelo de posiciones y dejan inventario huerfano

- Archivo y linea:
  - `backend/app/services/executor.py:59`
  - `backend/app/services/executor.py:67`
  - `backend/app/services/executor.py:213`
  - `backend/app/services/executor.py:231`
  - `backend/app/services/trading_loop.py:102`
  - `backend/app/services/signal_generator.py:77`
  - `backend/app/services/signal_generator.py:171`
  - `backend/app/services/risk_manager.py:41`
  - `backend/app/services/reconciliation.py:100`
- Problema:
  - El executor marca cualquier respuesta como `executed` sin validar `order.status`.
  - Si Binance devuelve fill parcial, `_close_position()` pasa a `partially_closed`.
  - El resto del sistema solo consulta `status = "open"` para SL/TP, exits, límites por símbolo y reconciliación.
- Impacto concreto:
  - Queda posición residual sin SL/TP.
  - `_close_position()` ya no encuentra esa posición para cerrarla después.
  - El bot puede abrir un BUY nuevo sobre el mismo símbolo porque ya no ve la posición como abierta.
  - La reconciliación deja de contar esa exposición.
- Fix sugerido:

```python
status = order.get("status")
executed_qty = float(order.get("executedQty", 0))

if status == "FILLED":
    proposal_status = "executed"
elif status == "PARTIALLY_FILLED":
    proposal_status = "partially_filled"
else:
    proposal_status = "submitted"

# Mantener la posicion como open con current_quantity residual
# o soportar partially_closed en todos los readers del sistema
```

### 3. `is_exit=True` no evita que los checks base bloqueen exits legitimos

- Archivo y linea:
  - `backend/app/routers/proposals.py:56`
  - `backend/app/services/signal_generator.py:211`
  - `backend/app/services/quant_risk.py:37`
  - `backend/app/services/quant_risk.py:87`
  - `backend/app/services/risk_manager.py:41`
  - `backend/app/services/risk_manager.py:72`
  - `backend/app/services/risk_manager.py:107`
- Problema:
  - `is_exit=True` solo desactiva el bloqueo por régimen en `quant_risk`.
  - Los checks base siguen exigiendo balance USDT, max open positions y daily loss aun para una venta de salida.
- Impacto concreto:
  - Un exit manual o automático puede ser rechazado cuando el sistema mas necesita cerrar riesgo.
  - En una cuenta con USDT bajo o daily loss excedido, el bot puede quedar atrapado en una posición abierta.
- Fix sugerido:

```python
async def validate_proposal(..., is_exit: bool = False):
    if not is_exit:
        run_open_position_checks()
    else:
        run_exit_checks_only()  # quantity disponible, simbolo existente, etc.
```

### 4. Path de LIMIT/NEW/PARTIALLY_FILLED queda marcado como `executed`

- Archivo y linea:
  - `backend/app/routers/proposals.py:34`
  - `backend/app/services/executor.py:46`
  - `backend/app/services/executor.py:49`
  - `backend/app/services/executor.py:59`
- Problema:
  - El API acepta `LIMIT`, pero el executor no modela estados intermedios.
  - Usa el primer fill como precio final y no distingue `NEW`, `PARTIALLY_FILLED` y `FILLED`.
- Impacto concreto:
  - Proposal `executed` con `executedQty = 0` o parcial.
  - Posiciones fantasma o incompletas en DB.
  - Divergencia entre DB y exchange.
- Fix sugerido:

```python
fills = order.get("fills", [])
executed_qty = float(order.get("executedQty", 0))
order_status = order.get("status")

avg_price = (
    float(order["cummulativeQuoteQty"]) / executed_qty
    if executed_qty > 0 and order.get("cummulativeQuoteQty")
    else None
)

if order_status != "FILLED":
    store_as_submitted_or_partial(...)
    return
```

## IMPORTANTE

### 5. ATR aberrante puede generar SL/TP invalidos o inutiles

- Archivo y linea:
  - `backend/app/services/executor.py:149`
  - `backend/app/services/executor.py:151`
  - `backend/app/services/trading_loop.py:200`
- Problema:
  - ATR negativo cae al fallback, pero ATR positivo absurdamente grande no.
  - Eso puede generar `stop_loss_price <= 0` o un TP irreal.
- Impacto concreto:
  - Posición abierta con protección inválida o inútil.
  - El repair replica el mismo error porque llama a la misma función.
- Fix sugerido:

```python
MAX_ATR_RATIO = 0.25  # ejemplo

if atr is None or atr <= 0 or price <= 0 or (atr / price) > MAX_ATR_RATIO:
    return fallback_sl_tp(price)

sl = price - settings.sl_atr_multiplier * atr
tp = price + settings.tp_atr_multiplier * atr

if not (0 < sl < price < tp):
    return fallback_sl_tp(price)
```

### 6. Comisiones mal contabilizadas cuando Binance cobra en BNB u otro asset

- Archivo y linea:
  - `backend/app/services/executor.py:60`
  - `backend/app/services/executor.py:61`
  - `backend/app/services/executor.py:179`
  - `backend/app/services/executor.py:227`
  - `backend/app/services/portfolio.py:35`
  - `backend/app/services/portfolio.py:37`
- Problema:
  - La comisión se suma como número bruto sin convertir al asset quote.
  - Si el fee viene en `BNB`, el sistema lo trata como si fueran USD/USDT.
- Impacto concreto:
  - PnL realizado y no realizado incorrecto.
  - Daily PnL, win rate y sizing histórico sesgados.
- Fix sugerido:

```python
def fee_to_quote(commission, commission_asset, fill_price, market_prices):
    if commission_asset in ("USDT", "FDUSD", "USDC"):
        return commission
    return commission * market_prices[commission_asset + "USDT"]
```

### 7. Proteccion ante flash crash es solo por polling cada 5 segundos

- Archivo y linea:
  - `backend/app/services/trading_loop.py:16`
  - `backend/app/services/trading_loop.py:37`
  - `backend/app/services/trading_loop.py:113`
  - `backend/app/services/trading_loop.py:120`
- Problema:
  - El SL/TP depende de polling y luego manda `MARKET SELL`.
  - No hay orden stop real alojada en exchange.
- Impacto concreto:
  - En un movimiento violento, el fill puede quedar muy por debajo del SL configurado.
- Fix sugerido:
  - Colocar protección nativa en exchange al abrir posición: OCO, STOP_LOSS_LIMIT o equivalente permitido por testnet/spot.
  - Como mínimo, usar stream/websocket y no solo polling.

### 8. Cooldown de 4 horas se resetea al reiniciar el proceso

- Archivo y linea:
  - `backend/app/services/signal_generator.py:47`
  - `backend/app/services/signal_generator.py:60`
- Problema:
  - `_last_signal_time` vive solo en memoria del proceso.
- Impacto concreto:
  - Reinicio o scaling horizontal elimina el cooldown.
  - Puede reentrar inmediatamente sobre el mismo símbolo.
- Fix sugerido:
  - Persistir `last_signal_at` o `last_entry_at` por `symbol + side` en DB.
  - Consultar DB antes de generar señales.

### 9. Thresholds inconsistentes entre signal generator y quant risk

- Archivo y linea:
  - `backend/app/config.py:36`
  - `backend/app/config.py:48`
  - `backend/app/config.py:64`
  - `backend/app/services/signal_generator.py:38`
  - `backend/app/services/signal_generator.py:44`
  - `backend/app/services/signal_generator.py:128`
  - `backend/app/services/quant_risk.py:55`
  - `backend/app/services/quant_risk.py:91`
- Problema:
  - `MAX_OPEN_POSITIONS = 2` en signals, pero config dice `risk_max_open_positions = 3`.
  - Entropy de BUY en signals usa `0.70`, mientras quant risk usa `entropy_threshold_ratio = 0.75`.
  - Downtrend block en signals usa `confidence > 60`; quant risk lo bloquea recién con `> 70`.
- Impacto concreto:
  - El path automático y el manual no aplican la misma política.
  - Puede aprobarse manualmente algo que el generador nunca produciría, o viceversa.
- Fix sugerido:
  - Centralizar una sola policy de entrada/salida.
  - Evitar constantes de módulo capturadas al importar.

### 10. Existen proposals `approved` sin ejecucion ni expiracion

- Archivo y linea:
  - `backend/app/routers/proposals.py:112`
  - `backend/app/routers/proposals.py:186`
  - `backend/app/services/executor.py:15`
  - `backend/app/services/reconciliation.py:45`
  - `backend/app/services/reconciliation.py:77`
- Problema:
  - Hay paths donde un proposal queda `approved` pero nunca se ejecuta.
  - La reconciliación solo revisa proposals con `binance_order_id`.
- Impacto concreto:
  - Proposal vieja puede ejecutarse mucho después, por ejemplo cuando vuelve `trading_enabled = True`.
  - Queda estado huerfano sin alerta.
- Fix sugerido:
  - Agregar `expires_at` y barrido de `approved` viejos sin `binance_order_id`.
  - Considerar estado `approved_pending_execution` o `executing`.

### 11. `round_quantity()` puede redondear hacia arriba y vender mas de lo disponible

- Archivo y linea:
  - `backend/app/utils/binance_utils.py:21`
  - `backend/app/services/trading_loop.py:140`
  - `backend/app/services/signal_generator.py:177`
- Problema:
  - Se hace `max(round(qty, decimals), min_qty)`.
  - Eso puede subir una cantidad residual por encima de la tenencia real.
- Impacto concreto:
  - Error 400 en Binance.
  - Exits fallidos y mas ruido sobre posiciones residuales o dust.
- Fix sugerido:

```python
from math import floor

def round_quantity(symbol, qty):
    decimals, step = _SYMBOL_PRECISION.get(symbol, _DEFAULT_PRECISION)
    rounded = floor(qty / step) * step
    return round(rounded, decimals)
```

### 12. La reconciliacion no cubre balances ni posiciones huerfanas reales

- Archivo y linea:
  - `backend/app/services/reconciliation.py:39`
  - `backend/app/services/reconciliation.py:43`
  - `backend/app/services/reconciliation.py:99`
- Problema:
  - Solo compara open orders y cuenta posiciones `open`.
  - No cruza balances spot por asset contra `positions.current_quantity`.
  - No detecta `positions open` sin proposal asociada ni proposals `executed` sin posición.
- Impacto concreto:
  - Exposición real en Binance puede no verse en DB.
  - El sistema puede operar creyendo que está flat cuando no lo está.
- Fix sugerido:
  - Cruce de inventario por asset.
  - Verificación de integridad proposal <-> position.
  - Alertas para `entry_proposal_id` faltante o proposal ejecutado sin posición.

## MEJORA

### 13. Dedupe preventivo por simbolo/direccion/ventana temporal

- Archivo y linea:
  - `backend/app/services/trading_loop.py:143`
  - `backend/app/services/signal_generator.py:182`
  - `backend/app/routers/proposals.py:29`
- Oportunidad concreta:
  - Agregar idempotency key por `symbol + side + strategy + bucket_temporal`.
- Impacto medible:
  - Reduce trades duplicados antes de tocar Binance.
- Fix sugerido:

```python
idempotency_key = f"{symbol}:{trade_type}:{strategy_id}:{now:%Y%m%d%H}"
# unique partial index sobre proposals activas
```

### 14. Persistir y versionar reglas de riesgo operativas

- Archivo y linea:
  - `backend/app/config.py:31`
  - `backend/app/services/signal_generator.py:35`
  - `backend/app/services/quant_risk.py:23`
- Oportunidad concreta:
  - Versionar policy de riesgo usada en cada proposal.
- Impacto medible:
  - Permite auditar por qué una decisión se aprobó o bloqueó bajo ciertos thresholds.
- Fix sugerido:
  - Guardar `risk_policy_version` y snapshot de thresholds en el proposal.

### 15. Fail-fast de env vars criticas en startup

- Archivo y linea:
  - `backend/app/config.py:7`
  - `backend/app/config.py:13`
  - `backend/app/config.py:25`
  - `backend/app/main.py:48`
- Oportunidad concreta:
  - El proceso arranca aunque falten variables críticas.
- Impacto medible:
  - Evita fallos diferidos en plena operación.
- Fix sugerido:

```python
if settings.trading_enabled:
    required = [
        settings.supabase_url,
        settings.supabase_service_role_key,
        settings.binance_testnet_api_key,
        settings.binance_testnet_secret,
        settings.backend_secret,
    ]
    if not all(required):
        raise RuntimeError("Missing critical env vars for trading mode")
```

## TESTS FALTANTES

### 16. Falta testear `_repair_missing_sl_tp()` y dedupe de SL/TP

- Archivo y linea:
  - `backend/app/services/trading_loop.py:99`
  - `backend/app/services/trading_loop.py:195`
- Gap:
  - No existe `backend/tests/test_trading_loop.py`.
  - No se cubre reparación de SL/TP, reintentos múltiples sobre la misma posición ni la carrera entre repair y close.
- Casos a agregar:
  - Posición `open` sin SL/TP se repara una sola vez.
  - Posición ya cerrándose no vuelve a repararse.
  - `_compute_sl_tp()` devuelve valores invalidos y cae al fallback.

### 17. Falta un test end-to-end del path `proposals.py` con `is_exit`

- Archivo y linea:
  - `backend/app/routers/proposals.py:56`
  - `backend/app/services/risk_manager.py:72`
  - `backend/app/services/risk_manager.py:107`
- Gap:
  - Hay tests de `quant_risk` con `is_exit=True`, pero parchean `_base_validate`.
  - No detectan que los checks base siguen bloqueando exits.
- Casos a agregar:
  - SELL con posición abierta y `USDT free = 0` debe seguir pudiendo validarse como exit.
  - SELL con daily loss excedido debe poder cerrar riesgo.

### 18. Falta cobertura de partial fills y estados intermedios de Binance

- Archivo y linea:
  - `backend/app/services/executor.py:46`
  - `backend/app/services/executor.py:59`
  - `backend/app/services/executor.py:213`
- Gap:
  - No hay tests para `NEW`, `PARTIALLY_FILLED`, fills múltiples, precio promedio ni fee asset distinto.
- Casos a agregar:
  - `LIMIT` creada y no ejecutada.
  - `PARTIALLY_FILLED` con remanente.
  - `fills` múltiples con promedio ponderado.
  - Comisión en `BNB`.

### 19. Falta cobertura de reconciliacion real

- Archivo y linea:
  - `backend/app/services/reconciliation.py:43`
  - `backend/app/services/reconciliation.py:77`
  - `backend/app/services/reconciliation.py:100`
- Gap:
  - No hay tests del reconciler.
- Casos a agregar:
  - `approved` sin `binance_order_id`.
  - `executed` sin posición.
  - Posición `open` sin proposal asociada.
  - Balance spot residual no reflejado en `positions`.
  - `partially_closed`.

### 20. Falta testear cooldown persistente y proposals duplicadas

- Archivo y linea:
  - `backend/app/services/signal_generator.py:47`
  - `backend/app/services/signal_generator.py:77`
  - `backend/app/services/signal_generator.py:171`
- Gap:
  - No se cubre reinicio de proceso ni dedupe por proposal activa.
- Casos a agregar:
  - Reinicio de proceso no debe perder cooldown si se persiste en DB.
  - No crear BUY si ya hay `draft`, `validated`, `approved` o `executing` del mismo símbolo.

### 21. Los mocks actuales ocultan bugs operativos reales

- Archivo y linea:
  - `backend/tests/conftest.py:55`
  - `backend/tests/test_quant_risk.py:56`
  - `backend/tests/test_signal_generator.py:50`
  - `backend/tests/test_executor_sltp.py:13`
- Gap:
  - `mock_supabase` devuelve cadenas felices y no simula errores de consistencia.
  - `test_quant_risk` parchea `_base_validate`, por eso no ve el bug de exits.
  - `test_signal_generator` parchea `settings`, pero el módulo usa constantes capturadas al importar.
  - `test_executor_sltp` no prueba ATR aberrante.
- Casos a agregar:
  - Tests sin parchear `_base_validate`.
  - Tests reimportando módulo o evitando constantes congeladas.
  - Tests con respuestas de Supabase/Binance no felices.

## Recomendacion de validacion para el siguiente agente

Orden sugerido:

1. Corregir modelo de ejecución atómica e idempotencia.
2. Corregir partial fills y soportar exposición residual en todo el sistema.
3. Separar explícitamente validaciones de entrada vs exit.
4. Unificar thresholds y mover hardcodes a config/policy única.
5. Reforzar reconciliación con inventario por asset.
6. Agregar tests de regresión para cada hallazgo crítico antes de desplegar.

## Nota final

Este informe no propone cambios cosméticos, de estilo ni de documentación. Todos los puntos listados arriba tienen impacto funcional, financiero o de consistencia de estado.
