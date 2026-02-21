"""Signal Generator - reads Quant Engine output and creates trade proposals.

Called every tick from trading_loop.py after the quant analysis runs.

Entry logic (BUY):
  - RSI < 38  (oversold territory)
  - MACD histogram > -5 (not deeply negative, looking for upturn)
  - ADX > 20  (trend is present)
  - Entropy ratio > 0.55 (market not pure noise)
  - No existing position in that symbol
  - Max 3 open positions across all symbols
  - 4-hour cooldown per symbol (prevent signal spam)

Exit logic (SELL):
  - RSI > 68  (overbought territory)
  - MACD histogram < 5 (momentum fading)
  - Existing open position in that symbol

Stop Loss / Take Profit are handled separately in trading_loop.py.
"""

import logging
from datetime import datetime, timezone

from ..config import settings
from ..db import get_supabase
from . import binance_client
from .technical_analysis import compute_indicators
from .entropy_filter import compute_entropy

logger = logging.getLogger(__name__)

APP_URL = "https://traiding-agentic.vercel.app"

# Thresholds
BUY_RSI_MAX = 38.0
BUY_MACD_HIST_MIN = -5.0
BUY_ADX_MIN = 20.0
BUY_ENTROPY_MIN = 0.55
BUY_NOTIONAL_USD = 100.0

SELL_RSI_MIN = 68.0
SELL_MACD_HIST_MAX = 5.0

MAX_OPEN_POSITIONS = 3
SIGNAL_COOLDOWN_MINUTES = 240  # 4 hours between signals per symbol

# State
_last_signal_time: dict[str, datetime] = {}


def _cooled_down(symbol: str, signal_type: str) -> bool:
    key = f"{symbol}:{signal_type}"
    last = _last_signal_time.get(key)
    if last is None:
        return True
    elapsed_min = (datetime.now(timezone.utc) - last).total_seconds() / 60
    return elapsed_min >= SIGNAL_COOLDOWN_MINUTES


def _mark_signal(symbol: str, signal_type: str) -> None:
    _last_signal_time[f"{symbol}:{signal_type}"] = datetime.now(timezone.utc)


async def generate_signals() -> None:
    """Evaluate all monitored symbols and create proposals where conditions are met."""
    if not settings.quant_enabled:
        return

    supabase = get_supabase()
    symbols = settings.quant_symbols.split(",")

    resp = supabase.table("positions").select("symbol").eq("status", "open").execute()
    open_symbols = {p["symbol"] for p in (resp.data or [])}
    open_count = len(open_symbols)

    for symbol in symbols:
        try:
            await _evaluate_symbol(supabase, symbol, open_symbols, open_count)
        except Exception as e:
            logger.error(f"Signal gen error [{symbol}]: {e}")


async def _evaluate_symbol(supabase, symbol: str, open_symbols: set, open_count: int) -> None:
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
    except Exception as e:
        logger.warning(f"Price fetch failed [{symbol}]: {e}")
        return

    # EXIT: close existing position
    if symbol in open_symbols:
        if (rsi > SELL_RSI_MIN
                and macd_hist < SELL_MACD_HIST_MAX
                and _cooled_down(symbol, "sell")):
            reasoning = (
                f"Exit: RSI={rsi:.1f} (overbought >{SELL_RSI_MIN}), "
                f"MACD hist={macd_hist:.2f} (fading), ADX={adx:.1f}"
            )
            logger.info(f"SELL signal [{symbol}] {reasoning}")
            await _submit_proposal(
                supabase, "sell", symbol, current_price, reasoning,
                rsi, macd_hist, adx, entropy_ratio,
            )
            _mark_signal(symbol, "sell")
        return

    # ENTRY: open new position
    if open_count >= MAX_OPEN_POSITIONS:
        return

    if (rsi < BUY_RSI_MAX
            and macd_hist > BUY_MACD_HIST_MIN
            and adx > BUY_ADX_MIN
            and entropy_ratio > BUY_ENTROPY_MIN
            and _cooled_down(symbol, "buy")):
        reasoning = (
            f"Entry: RSI={rsi:.1f} (oversold bajo {BUY_RSI_MAX}), "
            f"MACD hist={macd_hist:.2f} (momentum ok), "
            f"ADX={adx:.1f} (trend mayor {BUY_ADX_MIN}), "
            f"Entropy={entropy_ratio:.3f}"
        )
        logger.info(f"BUY signal [{symbol}] {reasoning}")
        await _submit_proposal(
            supabase, "buy", symbol, current_price, reasoning,
            rsi, macd_hist, adx, entropy_ratio,
        )
        _mark_signal(symbol, "buy")


async def _submit_proposal(
    supabase, trade_type: str, symbol: str, price: float, reasoning: str,
    rsi: float, macd_hist: float, adx: float, entropy_ratio: float,
) -> None:
    """Create, validate and optionally execute a proposal."""
    from .quant_risk import validate_proposal_enhanced

    if trade_type == "buy":
        notional = BUY_NOTIONAL_USD
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
        quantity = float(resp.data[0]["current_quantity"])

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
        logger.error(f"Failed to insert {trade_type} proposal for {symbol}")
        return

    proposal_id = resp.data[0]["id"]

    validation = await validate_proposal_enhanced(
        trade_type=trade_type,
        symbol=symbol,
        quantity=quantity,
        notional=notional_val,
        current_price=price,
    )

    if not validation.approved:
        new_status = "rejected"
    elif validation.auto_approved:
        new_status = "approved"
    else:
        new_status = "validated"

    supabase.table("trade_proposals").update({
        "status": new_status,
        "risk_score": validation.risk_score,
        "risk_checks": [c.model_dump() for c in validation.checks],
        "auto_approved": validation.auto_approved,
        "validated_at": now,
        "updated_at": now,
        **( {"approved_at": now} if new_status == "approved" else {}),
        **( {"rejected_at": now} if new_status == "rejected" else {}),
    }).eq("id", proposal_id).execute()

    logger.info(
        f"Auto-proposal [{trade_type.upper()} {symbol}] "
        f"qty={quantity} @ ${price:,.2f} -> {new_status} (risk={validation.risk_score:.1f})"
    )

    # Telegram notification
    try:
        from .telegram_notifier import send_telegram
        direction = "COMPRA" if trade_type == "buy" else "VENTA"
        status_emoji = {
            "approved": "&#128994;",
            "validated": "&#128269;",
            "rejected": "&#128308;",
        }.get(new_status, "&#128202;")
        dir_emoji = "&#11014;" if trade_type == "buy" else "&#11015;"
        lines = [
            status_emoji + " " + dir_emoji + " <b>SENAL AUTO: " + direction + " " + symbol + "</b>",
            "Precio: <b>$" + f"{price:,.2f}" + "</b>",
            "Cantidad: " + str(quantity) + " | Notional: $" + f"{notional_val:.2f}",
            "RSI: " + f"{rsi:.1f}" + " | MACD hist: " + f"{macd_hist:.2f}" + " | ADX: " + f"{adx:.1f}" + " | Entropy: " + f"{entropy_ratio:.3f}",
            "Estado: <b>" + new_status.upper() + "</b> | Risk score: " + f"{validation.risk_score:.1f}",
            "Razon: " + reasoning,
            "",
            "Ver propuestas: " + APP_URL + "/trades",
            "Ver portfolio: " + APP_URL + "/portfolio",
        ]
        await send_telegram("\n".join(lines))
    except Exception:
        pass

    # Auto-execute if approved
    if new_status == "approved" and settings.trading_enabled:
        from .executor import execute_proposal
        result = await execute_proposal(proposal_id)
        logger.info(f"Auto-execute result: {result}")

        try:
            from .telegram_notifier import send_telegram
            direction = "COMPRA" if trade_type == "buy" else "VENTA"
            exec_emoji = "&#9989;" if result.get("success") else "&#10060;"
            order_id = result.get("order_id", "N/A")
            exec_lines = [
                exec_emoji + " <b>EJECUTADO: " + direction + " " + symbol + "</b>",
                "Orden ID: <code>" + str(order_id) + "</code>",
                "Precio: $" + f"{price:,.2f}" + " | Qty: " + str(quantity),
                "Ver trades: " + APP_URL + "/trades",
            ]
            await send_telegram("\n".join(exec_lines))
        except Exception:
            pass


def _round_quantity(symbol: str, qty: float) -> float:
    """Round quantity to exchange-appropriate precision."""
    if symbol == "BTCUSDT":
        return max(round(qty, 5), 0.00001)
    elif symbol in ("ETHUSDT", "SOLUSDT"):
        return max(round(qty, 4), 0.0001)
    elif symbol in ("BNBUSDT",):
        return max(round(qty, 3), 0.001)
    else:
        return max(round(qty, 2), 0.01)
