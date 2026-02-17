"""Position sizing using Kelly Criterion and ATR normalization.

Determines optimal trade size based on:
- Kelly Criterion (historical win rate and payoff ratio)
- ATR-based volatility normalization
- Hard cap at $500

Uses Half-Kelly (f*/2) for safety.
"""

import logging
from typing import Optional

from ..db import get_supabase
from ..config import settings
from ..models.quant_models import PositionSizing
from .technical_analysis import compute_indicators
from . import binance_client

logger = logging.getLogger(__name__)

# Hard cap on position size
MAX_POSITION_USD = 500.0


def _compute_kelly(win_rate: float, avg_win: float, avg_loss: float) -> Optional[float]:
    """Compute Kelly fraction: f* = (p*b - q) / b, then apply dampener."""
    if avg_loss == 0 or win_rate <= 0 or win_rate >= 1:
        return None
    p = win_rate
    q = 1 - p
    b = avg_win / avg_loss  # payoff ratio
    kelly = (p * b - q) / b
    # Apply dampener (Half-Kelly by default)
    kelly_dampened = kelly * settings.kelly_dampener
    return max(0.0, min(kelly_dampened, 0.25))  # Cap at 25%


def _get_trade_stats() -> Optional[dict]:
    """Get historical trade stats from closed positions."""
    supabase = get_supabase()
    try:
        resp = (
            supabase.table("positions")
            .select("realized_pnl,entry_notional")
            .eq("status", "closed")
            .execute()
        )
        if not resp.data or len(resp.data) < 10:
            return None

        wins = []
        losses = []
        for pos in resp.data:
            pnl = float(pos.get("realized_pnl", 0) or 0)
            notional = float(pos.get("entry_notional", 0) or 1)
            pct = pnl / notional if notional > 0 else 0
            if pnl > 0:
                wins.append(pct)
            elif pnl < 0:
                losses.append(abs(pct))

        total = len(wins) + len(losses)
        if total < 10 or not losses:
            return None

        return {
            "win_rate": len(wins) / total,
            "avg_win": sum(wins) / len(wins) if wins else 0,
            "avg_loss": sum(losses) / len(losses) if losses else 0,
            "total_trades": total,
        }
    except Exception as e:
        logger.warning(f"Could not get trade stats: {e}")
        return None


async def compute_position_size(symbol: str, interval: str = "1h") -> Optional[PositionSizing]:
    """Compute recommended position size for a symbol."""
    try:
        # Get account balance
        account = await binance_client.get_account()
        balances = {b["asset"]: float(b["free"]) for b in account.get("balances", [])}
        usdt_free = balances.get("USDT", 0.0)
    except Exception as e:
        logger.warning(f"Could not fetch balance for sizing: {e}")
        usdt_free = 10000.0  # Fallback

    risk_amount = usdt_free * settings.max_risk_per_trade_pct  # 2% of account

    # ATR-based sizing
    indicators = compute_indicators(symbol, interval)
    atr_size = None
    if indicators and indicators.atr_14 and indicators.atr_14 > 0:
        atr = indicators.atr_14
        atr_stop = settings.atr_multiplier * atr
        # risk_amount / atr_stop gives quantity, then multiply by price for USD
        # Actually: notional = risk_amount / (atr_stop / price) * price = risk_amount * price / atr_stop
        # Simplified: atr_size = risk_amount / (atr_stop / current_price) but as USD value
        try:
            price_data = await binance_client.get_price(symbol)
            current_price = float(price_data["price"])
            quantity = risk_amount / atr_stop
            atr_size = quantity * current_price
        except Exception:
            atr_size = risk_amount  # Fallback

    # Kelly-based sizing
    trade_stats = _get_trade_stats()
    kelly_fraction = None
    kelly_size = None
    method = "fixed_pct"
    details = {"risk_amount_usd": round(risk_amount, 2), "account_balance": round(usdt_free, 2)}

    if trade_stats:
        kelly_fraction = _compute_kelly(
            trade_stats["win_rate"],
            trade_stats["avg_win"],
            trade_stats["avg_loss"],
        )
        if kelly_fraction and kelly_fraction > 0:
            kelly_size = usdt_free * kelly_fraction
            details["kelly_raw"] = round(kelly_fraction / settings.kelly_dampener, 4)
            details["kelly_dampened"] = round(kelly_fraction, 4)
            details["trade_stats"] = trade_stats

    # Determine final size
    if kelly_size and atr_size:
        recommended = min(kelly_size, atr_size, MAX_POSITION_USD)
        method = "kelly_atr"
    elif atr_size:
        recommended = min(atr_size, MAX_POSITION_USD)
        method = "atr_only"
    else:
        recommended = min(risk_amount, MAX_POSITION_USD)
        method = "fixed_pct"

    if indicators and indicators.atr_14:
        details["atr_14"] = round(indicators.atr_14, 2)
        details["atr_multiplier"] = settings.atr_multiplier

    return PositionSizing(
        symbol=symbol,
        kelly_fraction=round(kelly_fraction, 4) if kelly_fraction else None,
        kelly_size_usd=round(kelly_size, 2) if kelly_size else None,
        atr_size_usd=round(atr_size, 2) if atr_size else None,
        recommended_size_usd=round(recommended, 2),
        method=method,
        details=details,
    )
