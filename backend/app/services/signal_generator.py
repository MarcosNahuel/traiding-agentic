"""Signal generator: reads quant outputs and creates trade proposals.

Called every tick from trading_loop.py after quant analysis runs.

Anti-churn protections (research: QuantScience, López de Prado Triple Barrier):
  1. MIN_HOLD_MINUTES: no signal exits before position matures (SL/TP exempt)
  2. BREAKEVEN_THRESHOLD_PCT: no signal exit unless profit covers fees+slippage
  3. Entry/exit threshold sync: same regime confidence for both directions

Entry logic (BUY):
  - Regime != trending_down (confidence > threshold)
  - RSI < buy_rsi_max (LLM configurable)
  - ADX > buy_adx_min (LLM configurable)
  - Entropy ratio < buy_entropy_max (LLM configurable)
  - SMA20 > SMA50 (or override with ADX>30 + Hurst>0.55)
  - No existing position in symbol
  - Max open positions (LLM configurable)
  - Cooldown per symbol

Exit logic (SELL — only after MIN_HOLD_MINUTES):
  - RSI overbought + MACD fading
  - Regime flip to trending_down (confidence > threshold, synced with entry)
  - Hurst mean-reversion detection
  - ALL signal exits require breakeven gate (except SL/TP in fast_loop)
"""

import logging
from datetime import datetime, timezone, timedelta

from ..config import settings
from ..db import get_supabase
from . import binance_client
from .entropy_filter import compute_entropy
from .regime_detector import detect_regime
from .technical_analysis import compute_indicators
from ..utils.binance_utils import round_quantity as _round_quantity

logger = logging.getLogger(__name__)

# Static thresholds — testnet: relajados para generar trades
# Mainnet: restaurar a -10.0 y 5.0
BUY_MACD_HIST_MIN = -200.0
SELL_MACD_HIST_MAX = 50.0

# ── Anti-churn protections (research: QuantScience + Freqtrade + Triple Barrier) ──
# 1. Minimum hold: no signal-based exits before this time (SL/TP in fast_loop exempt)
MIN_HOLD_MINUTES = 180  # 3 horas — 3 barras de 1h, cubre desarrollo de tendencia
# 2. Breakeven gate: exit only if profit covers round-trip costs (2x fee + slippage)
#    Binance spot: 2 * (0.1% maker + ~0.05% slippage) = 0.30%
BREAKEVEN_THRESHOLD_PCT = 0.003  # 0.30%
# 3. Regime exit confidence synced with entry (no asymmetry)
REGIME_EXIT_CONFIDENCE_MIN = 80.0  # Mismo nivel que entry gate


def _get_thresholds() -> dict:
    """Return trading thresholds: LLM override from Supabase if active, else defaults.

    Called every tick (60s). Config bridge caches for 60s internally.
    """
    try:
        from .daily_analyst.config_bridge import load_active_config
        override = load_active_config()
        if override:
            return {
                "buy_rsi_max": override.buy_rsi_max,
                "buy_adx_min": override.buy_adx_min,
                "buy_entropy_max": override.buy_entropy_max,
                "sell_rsi_min": override.sell_rsi_min,
                "signal_cooldown_minutes": override.signal_cooldown_minutes,
                "max_open_positions": override.max_open_positions,
            }
    except Exception:
        pass  # No LLM analyst configured — use defaults

    return {
        "buy_rsi_max": 50.0,
        "buy_adx_min": settings.buy_adx_min,
        "buy_entropy_max": settings.buy_entropy_max,
        "sell_rsi_min": 65.0,
        "signal_cooldown_minutes": 180,
        "max_open_positions": settings.risk_max_open_positions,
    }


# Legacy module-level constants (kept for backward compat with tests)
BUY_RSI_MAX = 50.0
BUY_ADX_MIN = settings.buy_adx_min
BUY_ENTROPY_MAX = settings.buy_entropy_max
SELL_RSI_MIN = 65.0
MAX_OPEN_POSITIONS = settings.risk_max_open_positions
SIGNAL_COOLDOWN_MINUTES = 180

def _cooled_down(symbol: str, signal_type: str, supabase=None) -> bool:
    """Verifica cooldown consultando DB (sobrevive reinicios del proceso)."""
    if supabase is None:
        return True
    try:
        from datetime import timedelta
        cooldown = _get_thresholds()["signal_cooldown_minutes"]
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=cooldown)).isoformat()
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
    thresholds = _get_thresholds()
    # Use LLM-configured symbols if available, else settings default
    try:
        from .daily_analyst.config_bridge import load_active_config
        override = load_active_config()
        symbols_str = override.quant_symbols if override else settings.quant_symbols
    except Exception:
        symbols_str = settings.quant_symbols
    symbols = symbols_str.split(",")

    # ── ML signals (adicionales a las reglas técnicas) ──
    await _generate_ml_signals(supabase)

    for raw_symbol in symbols:
        symbol = raw_symbol.strip().upper()
        if not symbol:
            continue

        # Refresh each symbol to keep position limits strict after auto-execution.
        resp = supabase.table("positions").select("id, symbol").eq("status", "open").execute()
        open_positions = resp.data or []
        open_symbols = {p["symbol"] for p in open_positions}
        open_count = len(open_positions)  # Total positions, NOT unique symbols

        try:
            await _evaluate_symbol(supabase, symbol, open_symbols, open_count)
        except Exception as exc:
            logger.error("Signal generation error [%s]: %s", symbol, exc)


async def _evaluate_symbol(supabase, symbol: str, open_symbols: set[str], open_count: int) -> None:
    interval = settings.quant_primary_interval
    t = _get_thresholds()  # Dynamic: LLM override or defaults

    indicators = compute_indicators(symbol, interval)
    if not indicators:
        return

    rsi = indicators.rsi_14
    macd_hist = indicators.macd_histogram
    adx = indicators.adx_14
    ppo = indicators.ppo                        # QS: PPO normalizado
    autocorr = indicators.autocorr_1            # QS: autocorrelación
    volume_ratio = indicators.volume_ratio      # QS: volumen relativo
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

    # Exit logic (close existing position) — with anti-churn protections
    if symbol in open_symbols:
        sell_rsi = t["sell_rsi_min"]

        # ── Protection 1: Minimum hold time ──
        # Signal-based exits suppressed until position matures (SL/TP in fast_loop exempt)
        try:
            pos_resp = (
                supabase.table("positions")
                .select("opened_at, entry_price")
                .eq("symbol", symbol)
                .eq("status", "open")
                .order("opened_at", desc=True)
                .limit(1)
                .execute()
            )
            if pos_resp.data:
                opened_at = datetime.fromisoformat(pos_resp.data[0]["opened_at"].replace("Z", "+00:00"))
                entry_price = float(pos_resp.data[0]["entry_price"])
                hold_minutes = (datetime.now(timezone.utc) - opened_at).total_seconds() / 60
                if hold_minutes < MIN_HOLD_MINUTES:
                    logger.debug("SELL suppressed [%s]: hold %.0fmin < %dmin minimum",
                                 symbol, hold_minutes, MIN_HOLD_MINUTES)
                    return
            else:
                entry_price = current_price
                hold_minutes = 0
        except Exception as e:
            logger.warning("Min hold check failed [%s]: %s — allowing exit", symbol, e)
            entry_price = current_price
            hold_minutes = 999  # Allow exit on error

        # ── Protection 2: Breakeven gate ──
        # Signal exits only if profit covers round-trip costs (fees + slippage)
        pnl_pct = (current_price - entry_price) / entry_price if entry_price else 0
        if pnl_pct < BREAKEVEN_THRESHOLD_PCT:
            # Allow exit only if there's a STRONG regime reason (emergency protection)
            try:
                regime = detect_regime(symbol, interval)
            except Exception:
                regime = None
            strong_regime_exit = (regime and regime.regime == "trending_down"
                                 and regime.confidence > 90.0)
            if not strong_regime_exit:
                logger.debug("SELL suppressed [%s]: PnL %.2f%% < breakeven %.2f%% (hold %.0fmin)",
                             symbol, pnl_pct * 100, BREAKEVEN_THRESHOLD_PCT * 100, hold_minutes)
                return
        else:
            try:
                regime = detect_regime(symbol, interval)
            except Exception:
                regime = None

        # ── Signal-based exit triggers (only reached after min hold + breakeven) ──

        # Exit trigger 1: RSI overbought + MACD fading
        rsi_exit = rsi > sell_rsi and macd_hist < SELL_MACD_HIST_MAX

        # Exit trigger 2: Regime flip (Protection 3: synced confidence with entry)
        regime_exit = (regime and regime.regime == "trending_down"
                       and regime.confidence > REGIME_EXIT_CONFIDENCE_MIN)

        # Exit trigger 3: Hurst < 0.40 = mercado mean-reverting
        hurst_raw = getattr(regime, 'hurst_exponent', None) if regime else None
        hurst = float(hurst_raw) if isinstance(hurst_raw, (int, float)) else None
        hurst_exit = hurst is not None and hurst < 0.40 and rsi > 55

        if (rsi_exit or regime_exit or hurst_exit) and _cooled_down(symbol, "sell", supabase):
            trigger = "RSI-overbought" if rsi_exit else ("regime-flip" if regime_exit else "hurst-mean-revert")
            regime_str = f"{regime.regime}({regime.confidence:.0f}%)" if regime else "?"
            hurst_str = f", Hurst={hurst:.2f}" if hurst else ""
            reasoning = (
                f"Exit({trigger}): RSI={rsi:.1f}, MACD hist={macd_hist:.2f}, "
                f"ADX={adx:.1f}, Regime={regime_str}{hurst_str}, "
                f"PnL={pnl_pct*100:+.2f}%, Hold={hold_minutes:.0f}min"
            )
            logger.info("SELL signal [%s] %s", symbol, reasoning)
            await _submit_proposal(supabase, "sell", symbol, current_price, reasoning)
            _mark_signal(symbol, "sell")
        return

    # Entry logic (open new position) — uses dynamic max_open_positions
    if open_count >= t["max_open_positions"]:
        return

    # Regime filter: DESACTIVADO para testing agresivo en testnet
    # En producción, descomentar para bloquear BUY en downtrend fuerte
    regime = detect_regime(symbol, interval)
    if regime and regime.regime == "trending_down" and regime.confidence > settings.buy_regime_confidence_min:
        logger.info("BUY blocked [%s]: downtrend (confidence=%.1f%% > %.0f%%)", symbol, regime.confidence, settings.buy_regime_confidence_min)
        return

    # SMA cross: confirmar dirección alcista
    sma_20 = indicators.sma_20
    sma_50 = indicators.sma_50

    # SMA cross: factor de confianza, NO gate duro.
    # Research (quantscience-io): en crypto, SMA cross llega tarde y bloquea
    # entradas post-dip válidas. Usar como bonus, no como bloqueo.
    sma_aligned = sma_20 is not None and sma_50 is not None and sma_20 > sma_50
    sma_info = "SMA20>SMA50" if sma_aligned else "SMA20<SMA50(override)"

    # Si SMA no alineado, exigir ADX fuerte + Hurst trending como compensación
    if not sma_aligned:
        hurst_raw = getattr(regime, 'hurst_exponent', None) if regime else None
        hurst = float(hurst_raw) if isinstance(hurst_raw, (int, float)) else None
        # Permitir entrada contra SMA solo si: ADX muy fuerte (>30) Y Hurst trending (>0.55)
        # Sin Hurst disponible, no se permite override (requiere evidencia de trending)
        if hurst is None or adx <= 30 or hurst < 0.55:
            logger.info("BUY blocked [%s]: SMA bearish + insufficient override (ADX=%.1f, H=%s)", symbol, adx, hurst)
            return
        sma_info = f"SMA-override(ADX={adx:.0f},H={hurst:.2f})"

    # QS: Volumen — en testnet desactivado (volumen artificial)
    # Mainnet: restaurar a volume_ratio >= 1.2
    vol_ok = True
    vol_info = f"Vol={volume_ratio:.2f}x" if volume_ratio else "Vol=N/A"

    # QS: PPO para reasoning (normaliza MACD por precio)
    ppo_info = f"PPO={ppo:.2f}%" if ppo else "PPO=N/A"

    # QS: Autocorrelación como confirmación (>0 = trending, favorece momentum)
    autocorr_info = f"AC1={autocorr:.3f}" if autocorr else "AC1=N/A"

    if (
        rsi < t["buy_rsi_max"]
        and macd_hist > BUY_MACD_HIST_MIN
        and adx > t["buy_adx_min"]
        and entropy_ratio < t["buy_entropy_max"]
        and vol_ok
        and _cooled_down(symbol, "buy", supabase)
    ):
        regime_str = f"{regime.regime}({regime.confidence:.0f}%)" if regime else "unknown"
        reasoning = (
            f"Entry: RSI={rsi:.1f} (<{t['buy_rsi_max']}), "
            f"{ppo_info}, ADX={adx:.1f} (>{t['buy_adx_min']}), "
            f"Entropy={entropy_ratio:.3f}, {vol_info}, "
            f"{autocorr_info}, {sma_info}, Regime={regime_str}"
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

    # Verificar estado de posiciones — total positions, NOT unique symbols
    resp = supabase.table("positions").select("id, symbol").eq("status", "open").execute()
    open_positions = resp.data or []
    open_symbols = {p["symbol"] for p in open_positions}
    open_count = len(open_positions)

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


