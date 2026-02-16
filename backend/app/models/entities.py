from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field


class Order(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    ts: datetime = Field(default_factory=datetime.utcnow, index=True)
    venue: str
    symbol: str
    side: str
    qty: float
    price: float | None = None
    status: str = Field(default="NEW")
    external_id: str | None = None


class Fill(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    ts: datetime = Field(default_factory=datetime.utcnow, index=True)
    order_id: int = Field(foreign_key="order.id")
    qty: float
    price: float
    fee: float = 0.0


class Position(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    symbol: str = Field(index=True)
    qty: float = 0.0
    avg_price: float = 0.0
    updated_at: datetime = Field(default_factory=datetime.utcnow)
