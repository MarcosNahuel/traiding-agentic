"""API routes for complete quantitative analysis snapshots."""

from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone
from ..services.technical_analysis import compute_indicators
from ..services.entropy_filter import compute_entropy
from ..services.support_resistance import compute_sr_levels
from ..config import settings
import logging

router = APIRouter(prefix="/analysis", tags=["analysis"])
logger = logging.getLogger(__name__)


@router.get("/{symbol}")
async def get_full_analysis(symbol: str, interval: str = "1h"):
    """Get a complete quantitative analysis snapshot for a symbol.

    Includes: indicators, entropy, regime, S/R levels, position sizing.
    """
    symbol = symbol.upper()
    result: dict = {"symbol": symbol, "interval": interval, "timestamp": datetime.now(timezone.utc).isoformat()}

    # Indicators
    indicators = compute_indicators(symbol, interval)
    result["indicators"] = indicators.model_dump() if indicators else None

    # Entropy
    entropy = compute_entropy(symbol, interval)
    result["entropy"] = entropy.model_dump() if entropy else None

    # S/R Levels
    sr = compute_sr_levels(symbol, interval)
    result["sr_levels"] = sr.model_dump() if sr else None

    # Regime (depends on indicators)
    regime = None
    if indicators:
        try:
            from ..services.regime_detector import detect_regime
            regime = detect_regime(symbol, interval)
            result["regime"] = regime.model_dump() if regime else None
        except Exception as e:
            logger.warning(f"Regime detection failed: {e}")
            result["regime"] = None
    else:
        result["regime"] = None

    # Position sizing
    sizing = None
    try:
        from ..services.position_sizer import compute_position_size
        sizing = await compute_position_size(symbol)
        result["position_sizing"] = sizing.model_dump() if sizing else None
    except Exception as e:
        logger.warning(f"Position sizing failed: {e}")
        result["position_sizing"] = None

    # Tradability
    trade_blocks = []
    if entropy and not entropy.is_tradable:
        trade_blocks.append(f"entropy_high ({entropy.entropy_ratio:.3f} > {settings.entropy_threshold_ratio})")
    if regime and regime.regime == "volatile":
        trade_blocks.append(f"regime_volatile (confidence: {regime.confidence:.1f}%)")
    result["is_tradable"] = len(trade_blocks) == 0
    result["trade_blocks"] = trade_blocks

    return result


@router.get("/{symbol}/entropy")
async def get_entropy(symbol: str, interval: str = "1h"):
    """Get entropy reading for a symbol."""
    symbol = symbol.upper()
    entropy = compute_entropy(symbol, interval)
    if entropy is None:
        raise HTTPException(404, f"Not enough data for entropy: {symbol}")
    return {"symbol": symbol, "interval": interval, "entropy": entropy.model_dump()}
