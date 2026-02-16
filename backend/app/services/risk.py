from typing import Optional
from ..config import AppSettings
from .logging_service import LoggingService


class RiskManager:
    def __init__(self, settings: AppSettings, logger: LoggingService) -> None:
        self.settings = settings
        self.logger = logger
        self.max_daily_loss_pct = 5.0
        self.max_drawdown_pct = 10.0
        self.position_pct = 5.0

    def get_limits(self) -> dict:
        return {
            "max_daily_loss_pct": self.max_daily_loss_pct,
            "max_drawdown_pct": self.max_drawdown_pct,
            "position_pct": self.position_pct,
        }

    def set_limits(self, max_daily_loss_pct: Optional[float] = None, max_drawdown_pct: Optional[float] = None, position_pct: Optional[float] = None) -> dict:
        if max_daily_loss_pct is not None:
            self.max_daily_loss_pct = max_daily_loss_pct
        if max_drawdown_pct is not None:
            self.max_drawdown_pct = max_drawdown_pct
        if position_pct is not None:
            self.position_pct = position_pct
        self.logger.info("risk.update", self.get_limits())
        return self.get_limits()
