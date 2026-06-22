---
date: 2026-04-11
last_updated: 2026-04-12
type: tech-debt
status: open
---

# Open Gaps — Tech Debt

Issues abiertos conocidos, priorizados por severidad.

## 🔬 BACKTEST-LAB (descubierto 2026-06-21, auditoría adversarial Codex+agy+Claude)

### Look-ahead intrabar en el motor horario del lab
- **Archivo:** `scripts/backtest-lab/lab.py:331-336` (función `simulate`)
- **Problema:** en la misma iteración chequea `nxt["low"]/nxt["high"]` (vela i+1) para SL/TP
  y, si no saltan, decide el exit por señal evaluada en `row` (vela i) ejecutando a `row["close"]`.
  El orden de eventos está mezclado (prioriza el SL/TP de i+1 sobre la señal de close de i).
- **Impacto:** contamina TODOS los backtests horarios del donchian-bull y legacy (el PF 1.30 del
  donchian ya era dudoso por DSR 0.06; esto agrega otra razón para no confiar en ese número).
  NO afecta el veredicto cross-sectional (ese usa `xsectional.py`, verificado sin look-ahead).
- **Fix:** separar el orden de eventos — evaluar señal de exit en close de i y ejecutar en
  open de i+1 ANTES de aplicar SL/TP de i+1. Luego re-correr lab.py y ver si el donchian
  sobrevive. Sprint aparte (cambia la réplica, requiere re-validación).
- **Ref:** `docs/knowledge-base/evaluations/2026-06-21-cross-sectional-no-edge.md`

## 🚨 CRÍTICOS NUEVOS (descubiertos 2026-04-12 durante auditoría)

### 0. Proxy `binance.italicia.com` sirve tickers STALE → falsos SL (⚠️ REGRESIÓN 2026-04-21)
- **Archivo:** `backend/app/services/binance_client.py` (get_price_safe)
- **Status actual:** El fix de 2026-04-12 (commit f6ba148) añadió `get_price_safe`
  con fallback proxy. **Los datos del 2026-04-21 prueban que el fix NO está efectivo
  en producción** — 11 de los últimos 20 SL triggers siguen con drift 3-14%. Hipótesis:
  `get_price_direct` falla desde el VPS Dokploy (geo-block Binance) y cae al proxy stale.
- **Evidencia nueva (2026-04-21):** trigger vs exit_price real en `trade_proposals`:
  ```
  2026-04-19 ETHUSDT trigger=$1,968 exec=$2,298 delta=14.36%
  2026-04-19 BTCUSDT trigger=$68,114 exec=$75,270 delta=9.51%
  2026-04-20 ETHUSDT trigger=$2,103 exec=$2,315 delta=9.14%
  2026-04-12 ETHUSDT trigger=$2,049 exec=$2,245 delta=8.72%
  2026-04-15 ETHUSDT trigger=$2,174 exec=$2,335 delta=6.90%
  2026-04-10 BTCUSDT trigger=$67,966 exec=$71,929 delta=5.51%
  2026-04-09 BTCUSDT trigger=$67,966 exec=$71,132 delta=5.65%  <- trigger REPETIDO 24h
  ```
- **Impacto:** TP hit % cayó 12% → 2%. Los winners reales se están cerrando por SL
  falsos antes de llegar al TP. P&L semanal +$1.42 cuando el edge real debería ser
  +$8-12 si los trades llegaran a TP.
- **Fix aplicado 2026-04-21:**
  - Nueva función `get_price_verified(symbol, reference_price, max_drift_pct=0.10)`
    que usa SOLO direct testnet (sin fallback) y lanza `StalePriceError` si el
    precio difiere >10% del `reference_price` (entry).
  - `_check_stop_losses` y `_emergency_sl_check` usan ahora `get_price_verified`.
    Si direct falla o drift es detectado, SE SALTA el tick (fail-closed) en lugar
    de triggerar SL con data stale.
- **Pendiente (infra):** confirmar en logs Dokploy si direct-fetch está siendo
  bloqueado. Si sí, deployar un proxy alternativo confiable (Cloudflare Worker a
  testnet.binance.vision) o reemplazar `binance.italicia.com`.
- **Descubierto:** 2026-04-12 (session Opus 4.6), re-auditoría 2026-04-21 (session
  Opus 4.7) reveló regresión.

### 0b. `reconciliation_runs` table usa 210 MB (44% del free tier Supabase)
- **Archivo:** `backend/app/services/reconciliation.py`
- **Issue:** Cada row de `reconciliation_runs` pesa ~21 KB (payload JSON completo del
  state del portfolio). Con retention 7d = ~10,000 rows = 210 MB.
- **Impacto:** Bot consume 44% del free tier Supabase por sí solo (500 MB). Supabase
  compartido con otros proyectos → riesgo de hit del límite.
- **Fix propuesto 1 (quick):** Retention 7d → 2d en `data_retention.py`
- **Fix propuesto 2 (mejor):** Slim el payload — guardar solo summary, no state completo.
- **Descubierto:** 2026-04-12 (backup ML dump reveló tamaños reales).

## CRÍTICOS (afectan trading real)

### 1. Partial fills no modelados en SL/TP trailing
- **Archivo:** `backend/app/services/executor.py`
- **Issue:** Si Binance ejecuta parcialmente una orden, el SL/TP se calcula sobre qty inicial. El trailing no ajusta.
- **Workaround actual:** `exitQty` clampea a `entryQty` (línea 344-346)
- **Impacto:** En spot real, si la orden no llena, el position tracking divirge.
- **Fix:** Actualizar `entry_quantity` a `executed_quantity` real de Binance response.

### 2. Exits potencialmente bloqueados por base risk checks
- **Source:** `docs/AUDITORIA_BACKEND_TRADING_2026-03-13.md`
- **Issue:** Los checks de risk_manager.py se aplican también a proposals de SELL. Si el balance USDT está bajo, el SELL puede fallar.
- **Impacto:** Imposibilidad de cerrar posiciones en crisis
- **Fix:** Distinguir BUY vs SELL en `risk_manager.validate()`

## IMPORTANTES

### 3. No exchange-native stop orders
- **Archivos:** `executor.py`, `trading_loop.py`
- **Issue:** SL/TP son "internal" (polling cada 2s). No hay OCO orders en Binance.
- **Riesgo:** Latency entre price move y execution. Flash crash = slippage grande.
- **Fix:** Al abrir posición, mandar `client.create_oco_order()` con (SL, TP). Polling queda como backup.

### 4. Commission conversion BNB → USDT
- **Archivo:** `executor.py`
- **Issue:** Si Binance cobra fee en BNB, el código tiene fallback raw (sin conversión).
- **Impacto:** P&L underestimated si usuario tiene BNB para fees.
- **Fix:** Usar ticker BNBUSDT para convertir commission a USDT.

### 5. `round_quantity` puede redondear arriba
- **Archivo:** `backend/app/utils/binance_utils.py`
- **Issue:** Si la precisión del exchange es más estricta, redondear arriba puede causar "insufficient balance"
- **Fix:** Siempre redondear hacia abajo (floor) usando `stepSize` exchange info.

### 6. Reconciliation no cross-checks balances
- **Archivo:** `backend/app/services/reconciliation.py`
- **Issue:** La reconciliación compara DB vs Binance positions, pero no valida que los balances USDT matchen.
- **Impacto:** Drift silencioso entre DB y exchange.
- **Fix:** Agregar check de USDT balance + alerting si divergence >1%.

## MENORES

### 7. Volume filter desactivado en testnet
- **Archivo:** `signal_generator.py:361`
- **Issue:** Código comentado. Testnet tiene volumen artificial, filtro no sirve.
- **Action:** Re-habilitar al mover a mainnet.

### 8. Hardcoded values (inflexibilidad)
- `POST_CLOSE_COOLDOWN_MINUTES = 180`
- `MIN_HOLD_MINUTES = 180`
- `BREAKEVEN_CEILING_PCT = 0.008`
- `chandelier_multiplier = 2.0`

Mover a config (con safe bounds) cuando el bot pase a mainnet y se quiera experimentar.

## Implementados 2026-04-11

- ✓ SL/TP ATR multipliers por símbolo
- ✓ Breakeven gate adaptativo por ATR%
- ✓ Position size por símbolo
- ✓ Trailing activation 40% → 30%

## Limpiezas 2026-04-12

- ✓ Eliminados 72 dead_letters de símbolos deshabilitados (BNB/SOL/XRP, todos del 22 mar)
- ✓ Backup completo de datos para ML local en `data/ml_backup/2026-04-12/` (222 MB)
- ✓ PYTHON_BACKEND_URL actualizado a Dokploy (`http://trading-backend.161.35.54.238.sslip.io`)

## Cómo priorizar

Cuando se abra tiempo de desarrollo:
1. **Primero críticos** (1, 2) — pueden romper trades reales
2. **Después importantes** (3, 4, 5, 6) — cada uno gana 1-3% de performance
3. **Menores al final** (7, 8) — polishing
