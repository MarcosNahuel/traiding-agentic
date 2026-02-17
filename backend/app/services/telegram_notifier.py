"""Telegram notification service for quant risk events.

Uses the Telegram Bot API via httpx (already in dependencies).
Notifications are fire-and-forget — failures are logged but never raised.

Configuration (via .env):
    TELEGRAM_BOT_TOKEN=123456:ABC-...
    TELEGRAM_CHAT_ID=-1001234567890  (group) or 123456789 (user)
"""

import logging
import httpx

from ..config import settings

logger = logging.getLogger(__name__)

_TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


def is_telegram_configured() -> bool:
    return bool(settings.telegram_bot_token and settings.telegram_chat_id)


async def send_telegram(message: str) -> None:
    """Send a Telegram message asynchronously. Silently ignores errors."""
    if not is_telegram_configured():
        return
    url = _TELEGRAM_API.format(token=settings.telegram_bot_token)
    payload = {
        "chat_id": settings.telegram_chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(url, json=payload)
            if not resp.is_success:
                logger.warning(f"Telegram API error {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        logger.warning(f"Telegram notification failed: {e}")


async def notify_entropy_blocked(symbol: str, entropy_ratio: float) -> None:
    """Alert when entropy gate blocks a trade."""
    msg = (
        f"<b>ENTROPY GATE</b> - Trade blocked\n"
        f"Symbol: <code>{symbol}</code>\n"
        f"Entropy ratio: <b>{entropy_ratio:.3f}</b> (threshold {settings.entropy_threshold_ratio})\n"
        f"Market is too noisy for trading."
    )
    await send_telegram(msg)


async def notify_regime_blocked(symbol: str, regime: str, confidence: float, reason: str) -> None:
    """Alert when regime check blocks a trade."""
    regime_emoji = {
        "volatile": "🔴",
        "trending_up": "📈",
        "trending_down": "📉",
        "ranging": "↔️",
        "low_liquidity": "🔵",
    }.get(regime, "⚠️")

    msg = (
        f"{regime_emoji} <b>REGIME BLOCK</b> - Trade blocked\n"
        f"Symbol: <code>{symbol}</code>\n"
        f"Regime: <b>{regime}</b> ({confidence:.1f}% confidence)\n"
        f"Reason: {reason}"
    )
    await send_telegram(msg)
