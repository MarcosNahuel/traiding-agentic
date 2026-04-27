"""Signal generator: reads quant outputs and creates trade proposals.

Called every tick from trading_loop.py after quant analysis runs.

Anti-churn protections (research: QuantScience, López de Prado Triple Barrier):
  1. MIN_HOLD_MINUTES: no signal exits before position matures (SL/TP exempt)
  2. BREAKEVEN_THRESHOLD_PCT: no signal exit unless profit covers fees+slippage
  3. Entry/exit threshold sync: same regime confidence for both directions

Entry logic (BUY):
  - Regime profile must allow the entry
  - RSI < buy_rsi_max (LLM configurable)
  - ADX > buy_adx_min (LLM configurable)
  - Entropy ratio < buy_entropy_max (LLM configurable)
  - SMA20 > SMA50 (or override with ADX>30 + Hurst>0.55)
  - In ranging markets, require breakout confirmation (PPO/autocorr/volume)
  - Pause symbol temporarily after 3 consecutive losing trades
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
BUY_MACD_HIST_MIN = -50.0   # era -200 (no filtraba nada); ahora bloquea entradas con MACD muy negativo
SELL_MACD_HIST_MAX = 50.0

# ── Anti-churn protections (research: QuantScience + Freqtrade + Triple Barrier) ──
# 1. Minimum hold: no signal-based exits before this time (SL/TP in fast_loop exempt)
MIN_HOLD_MINUTES = 180  # 3 horas — 3 barras de 1h, cubre desarrollo de tendencia
# 2. Breakeven gate: exit only if profit covers round-trip costs (2x fee + slippage)
#    Binance spot: 2 * (0.1% maker + ~0.05% slippage) = 0.30%
BREAKEVEN_THRESHOLD_PCT = 0.010  # 1.0% floor (era 0.3%; signal exits solo si ganamos al menos 1%)
# Adaptive breakeven: in low-vol symbols (BTC) el 0.3% es demasiado alto y bloquea
# signal exits en winners pequeños. Escalamos por ATR% del precio.
# Empírico 2026-04-11: 3 BTC trades cerraron +0.15%/+0.23% bajo el floor sin poder salir.
BREAKEVEN_ATR_SCALE = 0.3  # breakeven efectivo = max(floor, ATR% * 0.3)
BREAKEVEN_CEILING_PCT = 0.025  # nunca > 2.5% (era 0.8%; subimos ceiling para que el floor 1% funcione en high-vol)


def compute_breakeven_threshold(atr_pct: float | None) -> float:
    """Breakeven threshold adaptativo por volatilidad (ATR%).

    BTC (ATR ~0.5%) → floor 0.30%
    ETH (ATR ~1.5%) → 0.45%
    High-vol (ATR 3%+) → capped 0.80%
    """
    if atr_pct is None or atr_pct <= 0:
        return BREAKEVEN_THRESHOLD_PCT
    scaled = atr_pct * BREAKEVEN_ATR_SCALE
    return max(BREAKEVEN_THRESHOLD_PCT, min(scaled, BREAKEVEN_CEILING_PCT))
# 3. Regime exit confidence synced with entry (no asymmetry)
REGIME_EXIT_CONFIDENCE_MIN = 80.0  # Mismo nivel que entry gate
# 4. Post-close re-entry guard: no BUY after ANY close (SL/TP/signal) for N minutes.
#    Hardcoded — no overrideable por LLM — para evitar churn cuando signal_cooldown es corto.
POST_CLOSE_COOLDOWN_MINUTES = 180
RANGING_CAUTIOUS_RSI_MAX = 47.0
RANGING_CAUTIOUS_ADX_MIN = 21.0
RANGING_CAUTIOUS_BREAKOUT_HINTS = 1
RANGING_LOW_VOL_RSI_MAX = 45.0
RANGING_LOW_VOL_ADX_MIN = 22.0
RANGING_LOW_VOL_BREAKOUT_HINTS = 2
BREAKOUT_HINT_PPO_MIN = 0.0
BREAKOUT_HINT_AUTOCORR_MIN = 0.02
BREAKOUT_HINT_VOLUME_RATIO_MIN = 1.05
LOSS_STREAK_TRIGGER = 3
LOSS_STREAK_LOOKBACK_DAYS = 7
LOSS_STREAK_PAUSE_HOURS = 24


# ── Safe bounds para LLM overrides ──
# Post-mortem: LLM config puso buy_rsi_max=60, adx_min=12, entropy=0.93, cooldown=30min
# Resultado: churn masivo, trades en mercados ruidosos sin tendencia. -$18.74 en 49 trades.
# Estos bounds son la "constitution" que el LLM no puede violar.
LLM_SAFE_BOUNDS = {
    "buy_rsi_max":              (30.0, 55.0),   # Nunca comprar arriba de RSI 55
    "buy_adx_min":              (18.0, 35.0),   # Siempre requerir tendencia mínima
    "buy_entropy_max":          (0.60, 0.80),   # Siempre filtrar ruido
    "sell_rsi_min":             (65.0, 78.0),   # No vender demasiado pronto ni tarde
    "signal_cooldown_minutes":  (120, 360),     # Mínimo 2h cooldown
    "max_open_positions":       (1, 3),         # Máximo 3 posiciones
}


def _clamp_llm_value(key: str, value: float) -> float:
    """Clampea un valor LLM dentro de los safe bounds."""
    bounds = LLM_SAFE_BOUNDS.get(key)
    if not bounds:
        return value
    lo, hi = bounds
    clamped = max(lo, min(hi, value))
    if clamped != value:
        logger.warning("LLM override CLAMPED: %s=%.2f → %.2f (bounds: %.2f-%.2f)",
                       key, value, clamped, lo, hi)
    return clamped


def _get_thresholds() -> dict:
    """Return trading thresholds: LLM override from Supabase (clamped to safe bounds), else defaults.

    Called every tick (60s). Config bridge caches for 60s internally.
    LLM overrides pasan por _clamp_llm_value — nunca pueden destruir la estrategia.
    """
    try:
        from .daily_analyst.config_bridge import load_active_config
        override = load_active_config()
        if override:
            return {
                "buy_rsi_max": _clamp_llm_value("buy_rsi_max", override.buy_rsi_max),
                "buy_adx_min": _clamp_llm_value("buy_adx_min", override.buy_adx_min),
                "buy_entropy_max": _clamp_llm_value("buy_entropy_max", override.buy_entropy_max),
                "sell_rsi_min": _clamp_llm_value("sell_rsi_min", override.sell_rsi_min),
                "signal_cooldown_minutes": int(_clamp_llm_value("signal_cooldown_minutes", override.signal_cooldown_minutes)),
                "max_open_positions": int(_clamp_llm_value("max_open_positions", override.max_open_positions)),
            }
    except Exception:
        pass  # No LLM analyst configured — use defaults

    return {
        "buy_rsi_max": 50.0,
        "buy_adx_min": settings.buy_adx_min,
        "buy_entropy_max": settings.buy_entropy_max,
        "sell_rsi_min": 70.0,  # era 65; subimos para dejar correr winners hacia TP
        "signal_cooldown_minutes": 180,
        "max_open_positions": settings.risk_max_open_positions,
    }


# Legacy module-level constants (kept for backward compat with tests)
BUY_RSI_MAX = 50.0
BUY_ADX_MIN = settings.buy_adx_min
BUY_ENTROPY_MAX = settings.buy_entropy_max
SELL_RSI_MIN = 70.0
MAX_OPEN_POSITIONS = settings.risk_max_open_positions
SIGNAL_COOLDOWN_MINUTES = 180

def _cooled_down(symbol: str, signal_type: str, supabase=None) -> bool:
    """Verifica cooldown consultando DB (sobrevive reinicios del proceso).

    Para señales BUY aplica dos checks:
    1. Propuestas de compra recientes (configurable por LLM).
    2. Posiciones cerradas recientemente (POST_CLOSE_COOLDOWN_MINUTES, no overrideable).
       Esto previene re-entrada inmediata tras SL/TP cuando la posición lleva horas abierta
       y el cooldown de propuestas ya venció.
    """
    if supabase is None:
        return True
    try:
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
        if len(resp.data or []) > 0:
            return False

        # Post-close re-entry guard (solo para BUY)
        if signal_type == "buy":
            close_cutoff = (
                datetime.now(timezone.utc) - timedelta(minutes=POST_CLOSE_COOLDOWN_MINUTES)
            ).isoformat()
            closed_resp = (
                supabase.table("positions")
                .select("id")
                .eq("symbol", symbol)
                .eq("status", "closed")
                .gte("closed_at", close_cutoff)
                .execute()
            )
            if len(closed_resp.data or []) > 0:
                logger.debug(
                    "BUY blocked [%s]: position closed within last %dmin (post-close guard)",
                    symbol, POST_CLOSE_COOLDOWN_MINUTES,
                )
                return False

        return True
    except Exception as e:
        logger.warning("Cooldown DB check failed [%s %s]: %s — permitiendo señal", symbol, signal_type, e)
        return True


def _mark_signal(symbol: str, signal_type: str) -> None:
    pass  # El cooldown se lee desde DB; insertar el proposal ya actúa como marca


def _build_entry_profile(regime_name: str | None, thresholds: dict) -> dict:
    """Build regime-aware entry requirements on top of the base thresholds."""
    profile = {
        "name": "default",
        "buy_rsi_max": thresholds["buy_rsi_max"],
        "buy_adx_min": thresholds["buy_adx_min"],
        "min_breakout_hints": 0,
        "blocked_reason": None,
    }

    if regime_name == "ranging":
        profile.update({
            "name": "range-caution",
            "buy_rsi_max": min(profile["buy_rsi_max"], RANGING_CAUTIOUS_RSI_MAX),
            "buy_adx_min": max(profile["buy_adx_min"], RANGING_CAUTIOUS_ADX_MIN),
            "min_breakout_hints": RANGING_CAUTIOUS_BREAKOUT_HINTS,
        })
    elif regime_name == "ranging_low_vol":
        profile.update({
            "name": "range-breakout",
            "buy_rsi_max": min(profile["buy_rsi_max"], RANGING_LOW_VOL_RSI_MAX),
            "buy_adx_min": max(profile["buy_adx_min"], RANGING_LOW_VOL_ADX_MIN),
            "min_breakout_hints": RANGING_LOW_VOL_BREAKOUT_HINTS,
        })
    elif regime_name == "ranging_high_vol":
        profile.update({
            "name": "range-high-vol",
            "blocked_reason": "ranging_high_vol without dedicated reversal strategy",
        })
    elif regime_name == "volatile":
        profile.update({
            "name": "volatile-pause",
            "blocked_reason": "volatile regime",
        })
    elif regime_name == "low_liquidity":
        profile.update({
            "name": "illiquid-pause",
            "blocked_reason": "low liquidity regime",
        })

    return profile


def _breakout_hints(
    ppo: float | None,
    autocorr: float | None,
    volume_ratio: float | None,
) -> tuple[int, str]:
    """Return the number of breakout hints and a compact explanation string."""
    hints: list[str] = []
    if ppo is not None and ppo > BREAKOUT_HINT_PPO_MIN:
        hints.append(f"PPO={ppo:.2f}%")
    if autocorr is not None and autocorr > BREAKOUT_HINT_AUTOCORR_MIN:
        hints.append(f"AC1={autocorr:.3f}")
    if volume_ratio is not None and volume_ratio >= BREAKOUT_HINT_VOLUME_RATIO_MIN:
        hints.append(f"Vol={volume_ratio:.2f}x")
    return len(hints), ", ".join(hints) if hints else "none"


def _loss_streak_pause_active(supabase, symbol: str) -> tuple[bool, str | None]:
    """Pause fresh entries after a recent loss streak in the same symbol."""
    if supabase is None:
        return False, None

    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=LOSS_STREAK_LOOKBACK_DAYS)).isoformat()
        resp = (
            supabase.table("positions")
            .select("realized_pnl,closed_at")
            .eq("symbol", symbol)
            .eq("status", "closed")
            .gte("closed_at", cutoff)
            .order("closed_at", desc=True)
            .limit(LOSS_STREAK_TRIGGER)
            .execute()
        )
        recent = resp.data or []
        if len(recent) < LOSS_STREAK_TRIGGER:
            return False, None

        losses = 0
        latest_closed_at = None
        for trade in recent:
            closed_at_raw = trade.get("closed_at")
            if latest_closed_at is None and closed_at_raw:
                latest_closed_at = datetime.fromisoformat(closed_at_raw.replace("Z", "+00:00"))

            pnl = float(trade.get("realized_pnl", 0) or 0)
            if pnl < 0:
                losses += 1
            else:
                break

        if losses < LOSS_STREAK_TRIGGER or latest_closed_at is None:
            return False, None

        pause_until = latest_closed_at + timedelta(hours=LOSS_STREAK_PAUSE_HOURS)
        if datetime.now(timezone.utc) >= pause_until:
            return False, None

        reason = (
            f"{losses} consecutive losers in <{LOSS_STREAK_PAUSE_HOURS}h "
            f"(pause until {pause_until.isoformat()})"
        )
        return True, reason
    except Exception as e:
        logger.warning("Loss-streak guard failed [%s]: %s", symbol, e)
        return False, None


# Rejection telemetry — counts silent rejection paths each tick.
# Reset at start of every generate_signals() call, written to risk_events
# at the end. Surfaces what's bouncing (filters, cooldowns, regime) so we
# don't have to guess from absence of logs.
_rejection_counters: dict[str, int] = {}


def _bump(reason: str) -> None:
    _rejection_counters[reason] = _rejection_counters.get(reason, 0) + 1


async def generate_signals() -> None:
    """Evaluate monitored symbols and create proposals where conditions are met.

    Dos fuentes de señales:
    1. Reglas técnicas (RSI, MACD, ADX, Entropy) — señales inmediatas
    2. ML predictions (LightGBM) — señales basadas en 30 features
    """
    if not settings.quant_enabled:
        return

    _rejection_counters.clear()
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
    # Wrapped in try/except so a ML failure can't bypass the rejection
    # telemetry block at the bottom of this function.
    try:
        await _generate_ml_signals(supabase)
    except Exception as exc:
        logger.error("ML signal generation error: %s", exc)

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

    # Rejection telemetry — surfaces silent rejections to risk_events
    if _rejection_counters:
        summary = ", ".join(f"{k}={v}" for k, v in sorted(_rejection_counters.items()))
        logger.info("Signals tick rejections: %s", summary)
        try:
            supabase.table("risk_events").insert({
                "event_type": "signal_rejections_tick",
                "severity": "info",
                "message": summary,
                "details": dict(_rejection_counters),
            }).execute()
        except Exception as exc:
            logger.error("Rejection telemetry insert failed: %s", exc)


async def _evaluate_symbol(supabase, symbol: str, open_symbols: set[str], open_count: int) -> None:
    interval = settings.quant_primary_interval
    t = _get_thresholds()  # Dynamic: LLM override or defaults

    indicators = compute_indicators(symbol, interval)
    if not indicators:
        _bump("no_indicators")
        return

    rsi = indicators.rsi_14
    macd_hist = indicators.macd_histogram
    adx = indicators.adx_14
    ppo = indicators.ppo                        # QS: PPO normalizado
    autocorr = indicators.autocorr_1            # QS: autocorrelación
    volume_ratio = indicators.volume_ratio      # QS: volumen relativo
    if rsi is None or macd_hist is None or adx is None:
        _bump("indicator_nan")
        return

    entropy_obj = compute_entropy(symbol, interval)
    entropy_ratio = entropy_obj.entropy_ratio if entropy_obj else 0.7

    try:
        ticker = await binance_client.get_price(symbol)
        current_price = float(ticker["price"])
    except Exception as exc:
        logger.warning("Price fetch failed [%s]: %s", symbol, exc)
        _bump("price_fetch_failed")
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
            logger.warning("Min hold check failed [%s]: %s — BLOCKING exit (safe default)", symbol, e)
            return  # Error = no data = no exit. SL/TP en fast_loop protegen igualmente.

        # ── Protection 2: Breakeven gate (adaptive per symbol volatility) ──
        # Signal exits only if profit covers round-trip costs (fees + slippage)
        atr_pct = None
        try:
            if indicators and indicators.atr_14:
                atr_pct = float(indicators.atr_14) / current_price
        except Exception:
            atr_pct = None
        breakeven_gate = compute_breakeven_threshold(atr_pct)
        pnl_pct = (current_price - entry_price) / entry_price if entry_price else 0
        if pnl_pct < breakeven_gate:
            # Allow exit only if there's a STRONG regime reason (emergency protection)
            try:
                regime = detect_regime(symbol, interval)
            except Exception:
                regime = None
            strong_regime_exit = (regime and regime.regime == "trending_down"
                                 and regime.confidence > 90.0)
            if not strong_regime_exit:
                logger.debug("SELL suppressed [%s]: PnL %.2f%% < breakeven %.2f%% (hold %.0fmin)",
                             symbol, pnl_pct * 100, breakeven_gate * 100, hold_minutes)
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
        _bump("max_open_positions")
        return

    # Regime filter: DESACTIVADO para testing agresivo en testnet
    # En producción, descomentar para bloquear BUY en downtrend fuerte
    regime = detect_regime(symbol, interval)
    if regime and regime.regime == "trending_down" and regime.confidence > settings.buy_regime_confidence_min:
        logger.info("BUY blocked [%s]: downtrend (confidence=%.1f%% > %.0f%%)", symbol, regime.confidence, settings.buy_regime_confidence_min)
        _bump("regime_downtrend")
        return

    loss_pause_active, loss_pause_reason = _loss_streak_pause_active(supabase, symbol)
    if loss_pause_active:
        logger.warning("BUY blocked [%s]: %s", symbol, loss_pause_reason)
        _bump("loss_streak_pause")
        return

    entry_profile = _build_entry_profile(regime.regime if regime else None, t)
    if entry_profile["blocked_reason"]:
        logger.info("BUY blocked [%s]: %s", symbol, entry_profile["blocked_reason"])
        _bump(f"profile_blocked_{regime.regime if regime else 'unknown'}")
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
            _bump("sma_bearish_no_override")
            return
        sma_info = f"SMA-override(ADX={adx:.0f},H={hurst:.2f})"

    # QS: Volumen — en testnet desactivado (volumen artificial)
    # Mainnet: restaurar a volume_ratio >= 1.2
    breakout_hint_count, breakout_hint_info = _breakout_hints(ppo, autocorr, volume_ratio)
    if breakout_hint_count < entry_profile["min_breakout_hints"]:
        logger.info(
            "BUY blocked [%s]: %s requires %d breakout hints, got %d (%s)",
            symbol,
            entry_profile["name"],
            entry_profile["min_breakout_hints"],
            breakout_hint_count,
            breakout_hint_info,
        )
        _bump("breakout_hints_insufficient")
        return

    vol_info = f"Vol={volume_ratio:.2f}x" if volume_ratio is not None else "Vol=N/A"

    # QS: PPO para reasoning (normaliza MACD por precio)
    ppo_info = f"PPO={ppo:.2f}%" if ppo is not None else "PPO=N/A"

    # QS: Autocorrelación como confirmación (>0 = trending, favorece momentum)
    autocorr_info = f"AC1={autocorr:.3f}" if autocorr is not None else "AC1=N/A"

    # Granular rejection telemetry — first failing filter wins.
    if rsi >= entry_profile["buy_rsi_max"]:
        _bump("buy_rsi_high")
        return
    if macd_hist <= BUY_MACD_HIST_MIN:
        _bump("buy_macd_weak")
        return
    if adx <= entry_profile["buy_adx_min"]:
        _bump("buy_adx_low")
        return
    if entropy_ratio >= t["buy_entropy_max"]:
        _bump("buy_entropy_high")
        return
    if not _cooled_down(symbol, "buy", supabase):
        _bump("buy_cooldown")
        return

    regime_str = f"{regime.regime}({regime.confidence:.0f}%)" if regime else "unknown"
    reasoning = (
        f"Entry[{entry_profile['name']}]: RSI={rsi:.1f} (<{entry_profile['buy_rsi_max']}), "
        f"{ppo_info}, ADX={adx:.1f} (>{entry_profile['buy_adx_min']}), "
        f"Entropy={entropy_ratio:.3f}, {vol_info}, "
        f"{autocorr_info}, BreakoutHints={breakout_hint_count}({breakout_hint_info}), "
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
        from ..config import get_symbol_notional
        symbol_notional = get_symbol_notional(symbol, float(settings.quant_buy_notional_usd))
        notional = max(symbol_notional, 10.0)
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


