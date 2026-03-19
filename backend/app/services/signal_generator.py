"""Signal generator: reads quant outputs and creates trade proposals.

Called every tick from trading_loop.py after quant analysis runs.

AGGRESSIVE TESTING MODE — optimizado para generar 5-10+ trades/día.

Entry logic (BUY):
  - Regime != trending_down (confidence > 80%)
  - RSI < 50
  - MACD histogram > -10
  - ADX > 15
  - Entropy ratio < 0.85
  - No existing position in symbol
  - Max 5 open positions across all symbols
  - 1-hour cooldown per symbol

Exit logic (SELL):
  - RSI > 65
  - MACD histogram < 5
  - Existing open position in symbol
"""

import logging
from datetime import datetime, timezone

from ..config import settings
from ..db import get_supabase
from . import binance_client
from .entropy_filter import compute_entropy
from .regime_detector import detect_regime
from .technical_analysis import compute_indicators
from ..utils.binance_utils import round_quantity as _round_quantity

logger = logging.getLogger(__name__)

# Thresholds — AGGRESSIVE TESTING MODE
BUY_RSI_MAX = 50.0                          # ERA 38 — compra más temprano en reversión
BUY_MACD_HIST_MIN = -10.0                   # ERA -5 — acepta momentum más negativo
BUY_ADX_MIN = settings.buy_adx_min          # 15 (era 25) — no requiere trend fuerte
BUY_ENTROPY_MAX = settings.buy_entropy_max  # 0.85 (era 0.70) — acepta más ruido

SELL_RSI_MIN = 65.0                          # ERA 68 — toma profit antes
SELL_MACD_HIST_MAX = 5.0

# Desde settings para ser consistente con risk_manager
MAX_OPEN_POSITIONS = settings.risk_max_open_positions  # 5 (era 3)
SIGNAL_COOLDOWN_MINUTES = 60                 # ERA 240 (4h) — ahora 1h de cooldown

def _cooled_down(symbol: str, signal_type: str, supabase=None) -> bool:
    """Verifica cooldown consultando DB (sobrevive reinicios del proceso)."""
    if supabase is None:
        return True
    try:
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=SIGNAL_COOLDOWN_MINUTES)).isoformat()
        resp = (
            supabase.table("trade_proposals")
            .select("id")
            .eq("symbol", symbol)
            .eq("type", signal_type)
            .gte("created_at", cutoff)
            .execute()
        )
        return len(resp.data or []) == 0
    except Exception as e:
        logger.warning("Cooldown DB check failed [%s %s]: %s — permitiendo señal", symbol, signal_type, e)
        return True


def _mark_signal(symbol: str, signal_type: str) -> None:
    pass  # El cooldown se lee desde DB; insertar el proposal ya actúa como marca


async def generate_signals() -> None:
    """Evaluate monitored symbols and create proposals where conditions are met.

    Dos fuentes de señales:
    1. Reglas técnicas (RSI, MACD, ADX, Entropy) — señales inmediatas
    2. ML predictions (LightGBM) — señales basadas en 30 features
    """
    if not settings.quant_enabled:
        return

    supabase = get_supabase()
    symbols = settings.quant_symbols.split(",")

    # ── ML signals (adicionales a las reglas técnicas) ──
    await _generate_ml_signals(supabase)

    for raw_symbol in symbols:
        symbol = raw_symbol.strip().upper()
        if not symbol:
            continue

        # Refresh each symbol to keep position limits strict after auto-execution.
        resp = supabase.table("positions").select("symbol").eq("status", "open").execute()
        open_symbols = {p["symbol"] for p in (resp.data or [])}
        open_count = len(open_symbols)

        try:
            await _evaluate_symbol(supabase, symbol, open_symbols, open_count)
        except Exception as exc:
            logger.error("Signal generation error [%s]: %s", symbol, exc)


async def _evaluate_symbol(supabase, symbol: str, open_symbols: set[str], open_count: int) -> None:
    interval = settings.quant_primary_interval

    indicators = compute_indicators(symbol, interval)
    if not indicators:
        return

    rsi = indicators.rsi_14
    macd_hist = indicators.macd_histogram
    adx = indicators.adx_14
    if rsi is None or macd_hist is None or adx is None:
        return

    entropy_obj = compute_entropy(symbol, interval)
    entropy_ratio = entropy_obj.entropy_ratio if entropy_obj else 0.7

    try:
        ticker = await binance_client.get_price(symbol)
        current_price = float(ticker["price"])
    except Exception as exc:
        logger.warning("Price fetch failed [%s]: %s", symbol, exc)
        return

    # Exit logic (close existing position)
    if symbol in open_symbols:
        if rsi > SELL_RSI_MIN and macd_hist < SELL_MACD_HIST_MAX and _cooled_down(symbol, "sell", supabase):
            reasoning = (
                f"Exit: RSI={rsi:.1f} (overbought >{SELL_RSI_MIN}), "
                f"MACD hist={macd_hist:.2f} (fading), ADX={adx:.1f}"
            )
            logger.info("SELL signal [%s] %s", symbol, reasoning)
            await _submit_proposal(supabase, "sell", symbol, current_price, reasoning)
            _mark_signal(symbol, "sell")
        return

    # Entry logic (open new position)
    if open_count >= MAX_OPEN_POSITIONS:
        return

    # Regime filter: DESACTIVADO para testing agresivo en testnet
    # En producción, descomentar para bloquear BUY en downtrend fuerte
    regime = detect_regime(symbol, interval)
    if regime and regime.regime == "trending_down" and regime.confidence > 95.0:
        # Solo bloquear en downtrend EXTREMO (>95%) — testnet mode
        logger.info("BUY blocked [%s]: extreme downtrend (confidence=%.1f%%)", symbol, regime.confidence)
        return

    # SMA cross: confirmar dirección alcista
    sma_20 = indicators.sma_20
    sma_50 = indicators.sma_50

    # SMA cross ya no es gate obligatorio — se usa como bonus info
    sma_aligned = sma_20 is not None and sma_50 is not None and sma_20 > sma_50
    sma_info = "SMA20>SMA50" if sma_aligned else "SMA20<SMA50(ok)"

    if (
        rsi < BUY_RSI_MAX
        and macd_hist > BUY_MACD_HIST_MIN
        and adx > BUY_ADX_MIN
        and entropy_ratio < BUY_ENTROPY_MAX
        and _cooled_down(symbol, "buy", supabase)
    ):
        regime_str = f"{regime.regime}({regime.confidence:.0f}%)" if regime else "unknown"
        reasoning = (
            f"Entry: RSI={rsi:.1f} (oversold <{BUY_RSI_MAX}), "
            f"MACD hist={macd_hist:.2f} (momentum ok), "
            f"ADX={adx:.1f} (trend >{BUY_ADX_MIN}), "
            f"Entropy={entropy_ratio:.3f} (<{BUY_ENTROPY_MAX}), "
            f"{sma_info}, Regime={regime_str}"
        )
        logger.info("BUY signal [%s] %s", symbol, reasoning)
        await _submit_proposal(supabase, "buy", symbol, current_price, reasoning)
        _mark_signal(symbol, "buy")


async def _submit_proposal(
    supabase, trade_type: str, symbol: str, price: float, reasoning: str
) -> None:
    """Create, validate, and optionally execute a proposal."""
    from .quant_risk import validate_proposal_enhanced

    if trade_type == "buy":
        notional = max(float(settings.quant_buy_notional_usd), 10.0)
        quantity = _round_quantity(symbol, notional / price)
    else:
        resp = (
            supabase.table("positions")
            .select("current_quantity")
            .eq("symbol", symbol)
            .eq("status", "open")
            .order("opened_at")
            .execute()
        )
        if not resp.data:
            return
        quantity = _round_quantity(symbol, float(resp.data[0]["current_quantity"]))

    notional_val = quantity * price
    now = datetime.now(timezone.utc).isoformat()

    insert = {
        "type": trade_type,
        "symbol": symbol,
        "quantity": quantity,
        "price": price,
        "order_type": "MARKET",
        "notional": notional_val,
        "status": "draft",
        "reasoning": f"[AUTO] {reasoning}",
        "risk_score": 0,
        "risk_checks": [],
        "auto_approved": False,
        "retry_count": 0,
        "created_at": now,
        "updated_at": now,
    }
    resp = supabase.table("trade_proposals").insert(insert).execute()
    if not resp.data:
        logger.error("Failed to insert %s proposal for %s", trade_type, symbol)
        return

    proposal_id = resp.data[0]["id"]

    validation = await validate_proposal_enhanced(
        trade_type=trade_type,
        symbol=symbol,
        quantity=quantity,
        notional=notional_val,
        current_price=price,
        is_exit=(trade_type == "sell"),
    )

    if not validation.approved:
        new_status = "rejected"
    elif validation.auto_approved:
        new_status = "approved"
    else:
        new_status = "validated"

    supabase.table("trade_proposals").update(
        {
            "status": new_status,
            "risk_score": validation.risk_score,
            "risk_checks": [c.model_dump() for c in validation.checks],
            "auto_approved": validation.auto_approved,
            "validated_at": now,
            "updated_at": now,
            **({"approved_at": now} if new_status == "approved" else {}),
            **({"rejected_at": now} if new_status == "rejected" else {}),
        }
    ).eq("id", proposal_id).execute()

    logger.info(
        "Auto-proposal [%s %s] qty=%s @ $%0.2f -> %s (risk=%0.1f)",
        trade_type.upper(),
        symbol,
        quantity,
        price,
        new_status,
        validation.risk_score,
    )

    try:
        from .telegram_notifier import escape_html, send_telegram

        status_icon = {
            "approved": "[OK]",
            "validated": "[REVIEW]",
            "rejected": "[BLOCK]",
        }.get(new_status, "[INFO]")
        sent = await send_telegram(
            f"{status_icon} <b>AUTO-SIGNAL: {escape_html(trade_type.upper())} {escape_html(symbol)}</b>\n"
            f"Price: ${price:,.2f}\n"
            f"Quantity: {quantity} | Notional: ${notional_val:.2f}\n"
            f"Status: <b>{escape_html(new_status)}</b> | Risk: {validation.risk_score:.1f}\n"
            f"Reason: {escape_html(reasoning)}"
        )
        if not sent:
            logger.warning(
                "Failed to send Telegram AUTO-SIGNAL for %s %s (proposal %s)",
                trade_type,
                symbol,
                proposal_id,
            )
    except Exception:
        logger.exception("Unexpected error sending Telegram AUTO-SIGNAL")

    if new_status == "approved" and settings.trading_enabled:
        from .executor import execute_proposal

        result = await execute_proposal(proposal_id)
        logger.info("Auto-execute result: %s", result)


async def _generate_ml_signals(supabase) -> None:
    """Genera señales adicionales usando el modelo ML (LightGBM).

    Las señales ML complementan las reglas técnicas. Se aplican los mismos
    controles de posiciones abiertas y cooldown.
    """
    try:
        from .ml.signal_policy import get_ml_signals
    except ImportError:
        return  # ML no disponible

    try:
        ml_signals = await get_ml_signals()
    except Exception as e:
        logger.debug("ML signals no disponibles: %s", e)
        return

    if not ml_signals:
        return

    # Verificar estado de posiciones
    resp = supabase.table("positions").select("symbol").eq("status", "open").execute()
    open_symbols = {p["symbol"] for p in (resp.data or [])}
    open_count = len(open_symbols)

    for sig in ml_signals:
        symbol = sig["symbol"]
        signal_type = sig["signal"].lower()  # "buy" o "sell"
        confidence = sig.get("confidence", 0)
        pred_return = sig.get("predicted_return", 0)

        # Mismo control que reglas técnicas
        if signal_type == "buy":
            if symbol in open_symbols:
                continue
            if open_count >= MAX_OPEN_POSITIONS:
                continue
            if not _cooled_down(symbol, "buy", supabase):
                continue
        elif signal_type == "sell":
            if symbol not in open_symbols:
                continue
            if not _cooled_down(symbol, "sell", supabase):
                continue
        else:
            continue

        try:
            ticker = await binance_client.get_price(symbol)
            current_price = float(ticker["price"])
        except Exception:
            continue

        reasoning = (
            f"ML Signal: pred_return={pred_return:+.4f}, "
            f"confidence={confidence:.2f}, model=lgb_logret"
        )
        logger.info("ML %s signal [%s] %s", signal_type.upper(), symbol, reasoning)

        await _submit_proposal(supabase, signal_type, symbol, current_price, reasoning)

        if signal_type == "buy":
            open_count += 1
            open_symbols.add(symbol)


