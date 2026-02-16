from fastapi import APIRouter, Request
from pydantic import BaseModel
from sqlmodel import Session, select
from ..utils.db import get_engine
from ..models.entities import Order

router = APIRouter()


class PlaceOrder(BaseModel):
    venue: str
    symbol: str
    side: str
    qty: float
    price: float | None = None


@router.post("/orders")
async def place_order(body: PlaceOrder, request: Request) -> dict:
    res = await request.app.state.execution.send_order(
        venue=body.venue,
        symbol=body.symbol,
        side=body.side,
        qty=body.qty,
        price=body.price,
    )
    return res


@router.get("/orders")
async def list_orders(limit: int = 50) -> dict:
    engine = get_engine()
    assert engine is not None, "Database engine is not initialized"
    with Session(engine) as session:
        stmt = select(Order).order_by(Order.ts.desc()).limit(limit)
        rows = session.exec(stmt).all()
        items = [
            {
                "id": o.id,
                "ts": o.ts.isoformat(),
                "venue": o.venue,
                "symbol": o.symbol,
                "side": o.side,
                "qty": o.qty,
                "price": o.price,
                "status": o.status,
                "external_id": o.external_id,
            }
            for o in rows
        ]
        return {"orders": items}
