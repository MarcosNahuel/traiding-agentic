from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime
from enum import Enum


class ProposalStatus(str, Enum):
    draft = "draft"
    validated = "validated"
    rejected = "rejected"
    approved = "approved"
    executed = "executed"
    error = "error"


class RiskCheck(BaseModel):
    name: str
    passed: bool
    message: str
    value: Optional[float] = None
    limit: Optional[float] = None


class ValidationResult(BaseModel):
    approved: bool
    auto_approved: bool
    risk_score: float
    checks: List[RiskCheck]
    rejection_reason: Optional[str] = None


class CreateProposalRequest(BaseModel):
    type: str  # "buy" | "sell"
    symbol: str
    quantity: float
    price: Optional[float] = None
    order_type: str = "MARKET"
    strategy_id: Optional[str] = None
    reasoning: Optional[str] = None


class ApproveProposalRequest(BaseModel):
    action: str  # "approve" | "reject"
    notes: Optional[str] = None


class ExecuteRequest(BaseModel):
    proposal_id: Optional[str] = None
    execute_all: bool = False


class PortfolioResponse(BaseModel):
    usdt_balance: float
    total_portfolio_value: float
    in_positions: float
    open_positions: int
    daily_pnl: float
    all_time_pnl: float
    win_rate: float
    total_trades: int
    unrealized_pnl: float
    positions: List[dict]
    performance: dict
