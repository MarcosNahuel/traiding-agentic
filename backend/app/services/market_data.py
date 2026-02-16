import asyncio
from typing import Dict, Optional
from dataclasses import dataclass
from ..config import AppSettings
from .logging_service import LoggingService


@dataclass
class MarketQuote:
    symbol: str
    bid: Optional[float]
    ask: Optional[float]
    last: Optional[float]
    venue: str
    timestamp_ms: int


class MarketDataHandler:
    def __init__(self, settings: AppSettings, logger: LoggingService) -> None:
        self.settings = settings
        self.logger = logger
        self._quotes: Dict[str, MarketQuote] = {}
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        self._running = True
        # In MVP, skip background polling. Placeholder for future poller
        # self._task = asyncio.create_task(self._poll_loop())

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None

    async def _poll_loop(self) -> None:
        try:
            while self._running:
                # TODO: implement polling to IOL REST and consuming ROFEX WS
                await asyncio.sleep(1.0)
        except asyncio.CancelledError:
            return

    def upsert_quote(self, quote: MarketQuote) -> None:
        self._quotes[quote.symbol] = quote

    def get_last_quote(self, symbol: str) -> Optional[MarketQuote]:
        return self._quotes.get(symbol)
