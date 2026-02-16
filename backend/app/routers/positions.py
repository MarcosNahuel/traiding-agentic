from fastapi import APIRouter
from sqlmodel import Session, select
from ..utils.db import get_engine
from ..models.entities import Position

router = APIRouter()


@router.get("/positions")
async def list_positions() -> dict:
    engine = get_engine()
    assert engine is not None, "Database engine is not initialized"
    with Session(engine) as session:
        rows = session.exec(select(Position)).all()
        items = [
            {
                "id": p.id,
                "symbol": p.symbol,
                "qty": p.qty,
                "avg_price": p.avg_price,
                "updated_at": p.updated_at.isoformat(),
            }
            for p in rows
        ]
        return {"positions": items}
