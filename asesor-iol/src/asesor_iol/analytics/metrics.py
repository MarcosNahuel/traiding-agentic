"""Métricas de cartera. Funciones puras -> fáciles de testear. Solo hechos."""
from __future__ import annotations

from dataclasses import dataclass

from ..iol.models import AccountState, Portfolio


@dataclass
class PortfolioMetrics:
    total_valorizado: float
    cash_total: float
    cash_pct: float
    allocation_pct: dict[str, float]      # símbolo -> % del total invertido
    top_concentration_pct: float           # mayor posición como % del invertido
    top_symbol: str | None


def compute_metrics(portfolio: Portfolio, accounts: list[AccountState]) -> PortfolioMetrics:
    invested = portfolio.total_valorizado
    cash = sum(a.disponible for a in accounts)
    base = invested + cash

    allocation = {
        h.simbolo: round(100 * h.valorizado / invested, 2)
        for h in portfolio.holdings
        if invested > 0
    }
    top_symbol = max(allocation, key=allocation.get) if allocation else None  # type: ignore[arg-type]
    top_pct = allocation.get(top_symbol, 0.0) if top_symbol else 0.0

    return PortfolioMetrics(
        total_valorizado=round(base, 2),
        cash_total=round(cash, 2),
        cash_pct=round(100 * cash / base, 2) if base > 0 else 0.0,
        allocation_pct=allocation,
        top_concentration_pct=top_pct,
        top_symbol=top_symbol,
    )
