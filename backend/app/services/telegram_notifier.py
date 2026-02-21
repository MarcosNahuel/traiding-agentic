"""Telegram notification service.

Improvements for reliability:
- Escapes dynamic HTML content to avoid Telegram parse errors.
- Retries transient failures with exponential backoff.
- Falls back to plain text when Telegram rejects HTML formatting.
"""

import asyncio
import logging
import re
from html import escape
from typing import Any

import httpx

from ..config import settings

logger = logging.getLogger(__name__)

_TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"
_MAX_RETRIES = 3
_REQUEST_TIMEOUT_SECONDS = 8.0
_MAX_ERROR_BODY_CHARS = 300
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_missing_config_warned = False


def is_telegram_configured() -> bool:
    return bool(settings.telegram_bot_token and settings.telegram_chat_id)


def escape_html(value: Any) -> str:
    """Escape user/dynamic content embedded in Telegram HTML payloads."""
    return escape(str(value), quote=False)


def _strip_html_markup(text: str) -> str:
    return _HTML_TAG_RE.sub("", text)


async def _post_telegram(
    client: httpx.AsyncClient,
    url: str,
    payload: dict,
    attempt: int,
) -> tuple[bool, bool]:
    """Return (sent_ok, html_parse_failed)."""
    try:
        resp = await client.post(url, json=payload)
        if resp.is_success:
            return True, False

        body = (resp.text or "")[:_MAX_ERROR_BODY_CHARS]
        logger.warning(
            "Telegram API error status=%s attempt=%s body=%s",
            resp.status_code,
            attempt,
            body,
        )

        parse_mode = payload.get("parse_mode")
        parse_failed = (
            parse_mode == "HTML"
            and resp.status_code == 400
            and ("parse entities" in resp.text.lower() or "can't parse" in resp.text.lower())
        )
        return False, parse_failed
    except Exception as exc:
        logger.warning("Telegram request failed attempt=%s error=%s", attempt, exc)
        return False, False


async def send_telegram(message: str, parse_mode: str | None = "HTML") -> bool:
    """Send a Telegram message with retries and optional HTML parsing."""
    global _missing_config_warned

    if not is_telegram_configured():
        if not _missing_config_warned:
            logger.warning("Telegram is not configured (missing bot token or chat id).")
            _missing_config_warned = True
        return False

    url = _TELEGRAM_API.format(token=settings.telegram_bot_token)
    payload = {
        "chat_id": settings.telegram_chat_id,
        "text": message,
        "disable_web_page_preview": True,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode

    async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT_SECONDS) as client:
        backoff_seconds = 0.6
        for attempt in range(1, _MAX_RETRIES + 1):
            sent_ok, parse_failed = await _post_telegram(client, url, payload, attempt)
            if sent_ok:
                return True

            if parse_failed and parse_mode == "HTML":
                logger.warning("Telegram rejected HTML message. Retrying as plain text.")
                plain_payload = {
                    "chat_id": settings.telegram_chat_id,
                    "text": _strip_html_markup(message),
                    "disable_web_page_preview": True,
                }
                sent_ok, _ = await _post_telegram(
                    client, url, plain_payload, attempt=attempt
                )
                return sent_ok

            if attempt < _MAX_RETRIES:
                await asyncio.sleep(backoff_seconds)
                backoff_seconds = min(backoff_seconds * 2, 3.0)

    return False


async def notify_entropy_blocked(symbol: str, entropy_ratio: float) -> None:
    """Alert when entropy gate blocks a trade."""
    msg = (
        "<b>ENTROPY GATE</b> - Trade blocked\n"
        f"Symbol: <code>{escape_html(symbol)}</code>\n"
        f"Entropy ratio: <b>{entropy_ratio:.3f}</b> "
        f"(threshold {settings.entropy_threshold_ratio})\n"
        "Market is too noisy for trading."
    )
    await send_telegram(msg)


async def notify_regime_blocked(
    symbol: str, regime: str, confidence: float, reason: str
) -> None:
    """Alert when regime check blocks a trade."""
    msg = (
        "<b>REGIME BLOCK</b> - Trade blocked\n"
        f"Symbol: <code>{escape_html(symbol)}</code>\n"
        f"Regime: <b>{escape_html(regime)}</b> ({confidence:.1f}% confidence)\n"
        f"Reason: {escape_html(reason)}"
    )
    await send_telegram(msg)
