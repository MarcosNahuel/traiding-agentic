from typing import Optional
from ..config import AppSettings
from .logging_service import LoggingService
from .market_data import MarketDataHandler, MarketQuote
from .execution import OrderExecutionManager
from .risk import RiskManager


class StrategyEngine:
    def __init__(
        self,
        settings: AppSettings,
        logger: LoggingService,
        market_data: MarketDataHandler,
        execution: OrderExecutionManager,
        risk_manager: RiskManager,
    ) -> None:
        self.settings = settings
        self.logger = logger
        self.market_data = market_data
        self.execution = execution
        self.risk = risk_manager

    def explain_last_decision(self) -> str:
        return "Aún no hay decisiones registradas en el MVP."

    def get_signal_snapshot(self) -> dict:
        return {"status": "idle", "details": None}

    def evaluate_and_maybe_trade(self, symbol: str) -> Optional[dict]:
        quote: Optional[MarketQuote] = self.market_data.get_last_quote(symbol)
        if not quote or quote.last is None:
            return None
        # Placeholder: no-op strategy. Extend with parity/z-score checks.
        return None
