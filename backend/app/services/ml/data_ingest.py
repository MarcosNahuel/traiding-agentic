"""Historical data backfill from Binance.

Dos métodos de descarga:
1. data.binance.vision — archivos ZIP mensuales (preferido para bulk)
2. REST API /api/v3/klines — para incrementos recientes

Usage:
    import asyncio
    from app.services.ml.data_ingest import backfill_all_symbols_archive
    asyncio.run(backfill_all_symbols_archive())
"""

import asyncio
import csv
import io
import logging
import zipfile
from datetime import datetime, timezone, timedelta
from typing import Any

import httpx

from ...db import get_supabase

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

BINANCE_PRODUCTION_BASE = "https://api.binance.com"
KLINES_ENDPOINT = "/api/v3/klines"

# Símbolos objetivo para ML training
ML_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"]

INTERVAL = "1h"
INTERVAL_MS = 3_600_000  # 1 hora en milisegundos
MAX_CANDLES_PER_REQUEST = 1000
BACKFILL_DAYS = 365  # 1 año
SUPABASE_BATCH_SIZE = 500

# Rate limiting: Binance permite 1200 req/min para endpoints públicos,
# pero usamos un intervalo conservador para evitar problemas.
REQUEST_DELAY_SECONDS = 0.5

# Binance kline array indices (12 campos)
_OT = 0   # Open time (ms)
_O = 1    # Open price
_H = 2    # High price
_L = 3    # Low price
_C = 4    # Close price
_V = 5    # Volume
_CT = 6   # Close time (ms)
_QV = 7   # Quote asset volume
_T = 8    # Number of trades
_TBV = 9  # Taker buy base asset volume
_TQV = 10  # Taker buy quote asset volume
_IGNORE = 11  # Ignore field


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _parse_kline(symbol: str, interval: str, raw: list) -> dict[str, Any]:
    """Convierte un array de kline de Binance en un dict compatible con klines_ohlcv.

    Args:
        symbol: Par de trading (ej: BTCUSDT).
        interval: Intervalo temporal (ej: 1h).
        raw: Array de 12 elementos de la API de Binance.

    Returns:
        Dict con las columnas de la tabla klines_ohlcv.
    """
    return {
        "symbol": symbol,
        "interval": interval,
        "open_time": datetime.fromtimestamp(
            raw[_OT] / 1000, tz=timezone.utc
        ).isoformat(),
        "close_time": datetime.fromtimestamp(
            raw[_CT] / 1000, tz=timezone.utc
        ).isoformat(),
        "open": float(raw[_O]),
        "high": float(raw[_H]),
        "low": float(raw[_L]),
        "close": float(raw[_C]),
        "volume": float(raw[_V]),
        "quote_volume": float(raw[_QV]),
        "trades_count": int(raw[_T]),
        "taker_buy_base_volume": float(raw[_TBV]),
        "taker_buy_quote_volume": float(raw[_TQV]),
    }


# ---------------------------------------------------------------------------
# Fetch desde Binance Production
# ---------------------------------------------------------------------------

async def _fetch_klines_page(
    client: httpx.AsyncClient,
    symbol: str,
    interval: str,
    start_time: int,
    end_time: int,
    limit: int = MAX_CANDLES_PER_REQUEST,
) -> list[list]:
    """Fetches una página de klines desde la API pública de Binance Production.

    Args:
        client: httpx.AsyncClient reutilizable.
        symbol: Par de trading.
        interval: Intervalo temporal.
        start_time: Timestamp de inicio en milisegundos.
        end_time: Timestamp de fin en milisegundos.
        limit: Máximo de candles por request (max 1000).

    Returns:
        Lista de arrays crudos de Binance (cada uno con 12 elementos).

    Raises:
        httpx.HTTPStatusError: Si la API responde con error.
    """
    params = {
        "symbol": symbol,
        "interval": interval,
        "startTime": start_time,
        "endTime": end_time,
        "limit": limit,
    }
    resp = await client.get(
        f"{BINANCE_PRODUCTION_BASE}{KLINES_ENDPOINT}",
        params=params,
    )
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Upsert a Supabase
# ---------------------------------------------------------------------------

def _batch_upsert(klines: list[dict[str, Any]]) -> int:
    """Upsert en batches a la tabla klines_ohlcv de Supabase.

    Args:
        klines: Lista de dicts parseados listos para insertar.

    Returns:
        Cantidad de filas insertadas/actualizadas.
    """
    if not klines:
        return 0

    supabase = get_supabase()
    total = 0

    for i in range(0, len(klines), SUPABASE_BATCH_SIZE):
        batch = klines[i : i + SUPABASE_BATCH_SIZE]
        try:
            resp = (
                supabase.table("klines_ohlcv")
                .upsert(batch, on_conflict="symbol,interval,open_time")
                .execute()
            )
            total += len(resp.data) if resp.data else 0
        except Exception as e:
            logger.error(
                "Error upserting batch %d-%d: %s",
                i,
                i + len(batch),
                e,
            )

    return total


# ---------------------------------------------------------------------------
# Verificación de integridad
# ---------------------------------------------------------------------------

def check_gaps(
    klines: list[dict[str, Any]],
    interval_ms: int = INTERVAL_MS,
) -> list[dict[str, Any]]:
    """Verifica que no haya gaps en los timestamps de las klines.

    Compara cada open_time consecutivo; la diferencia esperada es
    exactamente interval_ms.

    Args:
        klines: Lista de klines ordenadas por open_time ascendente.
        interval_ms: Duración esperada del intervalo en milisegundos.

    Returns:
        Lista de dicts describiendo cada gap encontrado. Lista vacía = sin gaps.
    """
    if len(klines) < 2:
        return []

    gaps = []
    for i in range(1, len(klines)):
        prev_ts = int(
            datetime.fromisoformat(klines[i - 1]["open_time"]).timestamp() * 1000
        )
        curr_ts = int(
            datetime.fromisoformat(klines[i]["open_time"]).timestamp() * 1000
        )
        diff = curr_ts - prev_ts

        if diff != interval_ms:
            missing_count = (diff // interval_ms) - 1
            gaps.append({
                "after": klines[i - 1]["open_time"],
                "before": klines[i]["open_time"],
                "expected_ms": interval_ms,
                "actual_ms": diff,
                "missing_candles": max(0, missing_count),
            })

    return gaps


# ---------------------------------------------------------------------------
# Backfill de un símbolo
# ---------------------------------------------------------------------------

async def backfill_symbol(
    symbol: str,
    interval: str = INTERVAL,
    days: int = BACKFILL_DAYS,
) -> dict[str, Any]:
    """Backfill completo de datos históricos para un símbolo.

    Descarga klines de 1 año desde Binance Production API (paginando
    en bloques de 1000 candles) y los upserta en Supabase.

    Args:
        symbol: Par de trading (ej: BTCUSDT).
        interval: Intervalo de las velas (default: 1h).
        days: Cantidad de días hacia atrás a descargar (default: 365).

    Returns:
        Dict con estadísticas del backfill: total_fetched, total_stored,
        gaps encontrados, y duración.
    """
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    start_ms = now_ms - (days * 86_400_000)
    end_ms = now_ms

    all_klines: list[dict[str, Any]] = []
    current_start = start_ms
    page = 0
    start_time = datetime.now(timezone.utc)

    logger.info(
        "Iniciando backfill %s %s: %d dias (%s -> %s)",
        symbol,
        interval,
        days,
        datetime.fromtimestamp(start_ms / 1000, tz=timezone.utc).isoformat(),
        datetime.fromtimestamp(end_ms / 1000, tz=timezone.utc).isoformat(),
    )

    async with httpx.AsyncClient(timeout=30, verify=False) as client:
        while current_start < end_ms:
            page += 1
            try:
                raw_klines = await _fetch_klines_page(
                    client=client,
                    symbol=symbol,
                    interval=interval,
                    start_time=current_start,
                    end_time=end_ms,
                    limit=MAX_CANDLES_PER_REQUEST,
                )
            except httpx.HTTPStatusError as e:
                logger.error(
                    "Binance API error (HTTP %d) para %s pagina %d: %s",
                    e.response.status_code,
                    symbol,
                    page,
                    e.response.text[:300],
                )
                break
            except httpx.RequestError as e:
                logger.error(
                    "Request error para %s pagina %d: %s",
                    symbol,
                    page,
                    e,
                )
                break

            if not raw_klines:
                logger.info(
                    "No hay mas datos para %s a partir de pagina %d",
                    symbol,
                    page,
                )
                break

            parsed = [_parse_kline(symbol, interval, k) for k in raw_klines]
            all_klines.extend(parsed)

            # Avanzar el cursor después de la última vela recibida
            last_open_ms = int(raw_klines[-1][_OT])
            current_start = last_open_ms + INTERVAL_MS

            logger.info(
                "Backfill %s: pagina %d, %d candles (total acumulado: %d)",
                symbol,
                page,
                len(parsed),
                len(all_klines),
            )

            # Rate limiting entre requests
            await asyncio.sleep(REQUEST_DELAY_SECONDS)

    # Verificar integridad antes de guardar
    gaps = check_gaps(all_klines, INTERVAL_MS)
    if gaps:
        logger.warning(
            "Backfill %s: encontrados %d gaps en timestamps. "
            "Primer gap: despues de %s, %d candles faltantes",
            symbol,
            len(gaps),
            gaps[0]["after"],
            gaps[0]["missing_candles"],
        )
    else:
        logger.info("Backfill %s: sin gaps en timestamps", symbol)

    # Upsert a Supabase
    total_stored = _batch_upsert(all_klines)

    elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
    result = {
        "symbol": symbol,
        "interval": interval,
        "days": days,
        "total_fetched": len(all_klines),
        "total_stored": total_stored,
        "gaps_found": len(gaps),
        "gaps_detail": gaps[:10] if gaps else [],  # Limitar detalle a 10
        "elapsed_seconds": round(elapsed, 1),
    }

    logger.info(
        "Backfill %s completo: %d fetched, %d stored, %d gaps, %.1fs",
        symbol,
        result["total_fetched"],
        result["total_stored"],
        result["gaps_found"],
        elapsed,
    )

    return result


# ---------------------------------------------------------------------------
# Backfill de todos los símbolos
# ---------------------------------------------------------------------------

async def backfill_all_symbols(
    symbols: list[str] | None = None,
    interval: str = INTERVAL,
    days: int = BACKFILL_DAYS,
) -> list[dict[str, Any]]:
    """Ejecuta el backfill secuencial para todos los símbolos ML.

    Procesa los símbolos de forma secuencial (no paralela) para respetar
    los rate limits de Binance y evitar sobrecarga en Supabase.

    Args:
        symbols: Lista de pares a descargar. Default: ML_SYMBOLS.
        interval: Intervalo de las velas (default: 1h).
        days: Días hacia atrás (default: 365).

    Returns:
        Lista de resultados, uno por símbolo.
    """
    target_symbols = symbols or ML_SYMBOLS
    results: list[dict[str, Any]] = []

    logger.info(
        "Iniciando backfill para %d simbolos: %s",
        len(target_symbols),
        ", ".join(target_symbols),
    )

    for i, symbol in enumerate(target_symbols, 1):
        logger.info(
            "Procesando simbolo %d/%d: %s",
            i,
            len(target_symbols),
            symbol,
        )
        try:
            result = await backfill_symbol(
                symbol=symbol,
                interval=interval,
                days=days,
            )
            results.append(result)
        except Exception as e:
            logger.error("Error fatal en backfill de %s: %s", symbol, e)
            results.append({
                "symbol": symbol,
                "interval": interval,
                "days": days,
                "total_fetched": 0,
                "total_stored": 0,
                "gaps_found": 0,
                "gaps_detail": [],
                "elapsed_seconds": 0,
                "error": str(e),
            })

        # Pausa entre símbolos para no saturar rate limits
        if i < len(target_symbols):
            await asyncio.sleep(2.0)

    total_fetched = sum(r["total_fetched"] for r in results)
    total_stored = sum(r["total_stored"] for r in results)
    total_gaps = sum(r["gaps_found"] for r in results)
    errors = sum(1 for r in results if "error" in r)

    logger.info(
        "Backfill completo: %d simbolos, %d candles fetched, "
        "%d stored, %d gaps, %d errores",
        len(results),
        total_fetched,
        total_stored,
        total_gaps,
        errors,
    )

    return results


# ---------------------------------------------------------------------------
# Método alternativo: data.binance.vision (archivos ZIP mensuales)
# ---------------------------------------------------------------------------

ARCHIVE_BASE = "https://data.binance.vision/data/spot/monthly/klines"


def _ts_to_iso(raw_ts: int) -> str:
    """Convierte timestamp de Binance a ISO. Auto-detecta ms vs us."""
    # Binance cambió de ms (13 dígitos) a us (16 dígitos) en archivos recientes
    if raw_ts > 1e15:  # microsegundos
        return datetime.fromtimestamp(raw_ts / 1_000_000, tz=timezone.utc).isoformat()
    return datetime.fromtimestamp(raw_ts / 1000, tz=timezone.utc).isoformat()


def _parse_archive_row(symbol: str, interval: str, row: list) -> dict[str, Any] | None:
    """Parsea una fila CSV del archivo de data.binance.vision."""
    if len(row) < 11:
        return None
    try:
        return {
            "symbol": symbol,
            "interval": interval,
            "open_time": _ts_to_iso(int(row[0])),
            "close_time": _ts_to_iso(int(row[6])),
            "open": float(row[1]),
            "high": float(row[2]),
            "low": float(row[3]),
            "close": float(row[4]),
            "volume": float(row[5]),
            "quote_volume": float(row[7]),
            "trades_count": int(row[8]),
            "taker_buy_base_volume": float(row[9]),
            "taker_buy_quote_volume": float(row[10]),
        }
    except (ValueError, IndexError):
        return None


async def backfill_symbol_archive(
    symbol: str,
    interval: str = INTERVAL,
    months_back: int = 12,
) -> dict[str, Any]:
    """Backfill descargando archivos ZIP mensuales de data.binance.vision.

    Más confiable que la REST API (no tiene rate limits ni WAF blocks).
    """
    now = datetime.now(timezone.utc)
    all_klines: list[dict[str, Any]] = []
    start_time = datetime.now(timezone.utc)
    failed_months = 0

    logger.info("Backfill ARCHIVE %s %s: %d meses", symbol, interval, months_back)

    async with httpx.AsyncClient(timeout=60, verify=False) as client:
        for m in range(months_back, 0, -1):
            # Calcular año-mes target
            target = now - timedelta(days=m * 30)
            year = target.year
            month = target.month

            url = (
                f"{ARCHIVE_BASE}/{symbol}/{interval}/"
                f"{symbol}-{interval}-{year}-{month:02d}.zip"
            )

            try:
                resp = await client.get(url)
                if resp.status_code == 404:
                    logger.debug("Archivo no encontrado (404): %s", url)
                    failed_months += 1
                    continue
                resp.raise_for_status()

                # Descomprimir ZIP en memoria
                zip_data = io.BytesIO(resp.content)
                with zipfile.ZipFile(zip_data) as zf:
                    for name in zf.namelist():
                        if not name.endswith(".csv"):
                            continue
                        with zf.open(name) as f:
                            reader = csv.reader(io.TextIOWrapper(f, "utf-8"))
                            for row in reader:
                                parsed = _parse_archive_row(symbol, interval, row)
                                if parsed:
                                    all_klines.append(parsed)

                logger.info(
                    "ARCHIVE %s %d-%02d: %d candles acumuladas",
                    symbol, year, month, len(all_klines),
                )
                await asyncio.sleep(0.3)

            except Exception as e:
                logger.error("Error descargando %s: %s", url, e)
                failed_months += 1
                continue

    # Upsert
    total_stored = _batch_upsert(all_klines)

    # Verificar gaps
    all_klines.sort(key=lambda k: k["open_time"])
    gaps = check_gaps(all_klines, INTERVAL_MS)

    elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
    result = {
        "symbol": symbol,
        "interval": interval,
        "months": months_back,
        "total_fetched": len(all_klines),
        "total_stored": total_stored,
        "gaps_found": len(gaps),
        "failed_months": failed_months,
        "elapsed_seconds": round(elapsed, 1),
    }

    logger.info(
        "ARCHIVE backfill %s completo: %d fetched, %d stored, %d gaps, %.1fs",
        symbol, len(all_klines), total_stored, len(gaps), elapsed,
    )
    return result


async def backfill_all_symbols_archive(
    symbols: list[str] | None = None,
    interval: str = INTERVAL,
    months_back: int = 12,
) -> list[dict[str, Any]]:
    """Backfill de todos los símbolos usando data.binance.vision."""
    target_symbols = symbols or ML_SYMBOLS
    results: list[dict[str, Any]] = []

    logger.info(
        "Backfill ARCHIVE para %d simbolos: %s",
        len(target_symbols), ", ".join(target_symbols),
    )

    for i, symbol in enumerate(target_symbols, 1):
        logger.info("ARCHIVE %d/%d: %s", i, len(target_symbols), symbol)
        try:
            result = await backfill_symbol_archive(
                symbol=symbol, interval=interval, months_back=months_back,
            )
            results.append(result)
        except Exception as e:
            logger.error("Error fatal ARCHIVE %s: %s", symbol, e)
            results.append({
                "symbol": symbol, "error": str(e),
                "total_fetched": 0, "total_stored": 0,
            })

        if i < len(target_symbols):
            await asyncio.sleep(1.0)

    total = sum(r.get("total_fetched", 0) for r in results)
    stored = sum(r.get("total_stored", 0) for r in results)
    logger.info("ARCHIVE completo: %d candles fetched, %d stored", total, stored)
    return results
