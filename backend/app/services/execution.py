from typing import Optional
from sqlmodel import Session, select
from ..config import AppSettings
from ..models.entities import Order, Fill, Position
from ..utils.db import get_engine
from .logging_service import LoggingService
from .risk import RiskManager


class OrderExecutionManager:
    def __init__(self, settings: AppSettings, logger: LoggingService, risk_manager: RiskManager) -> None:
        self.settings = settings
        self.logger = logger
        self.risk = risk_manager

    async def send_order(self, venue: str, symbol: str, side: str, qty: float, price: Optional[float] = None) -> dict:
        # Persist order in DB
        engine = get_engine()
        assert engine is not None, "Database engine is not initialized"
        with Session(engine) as session:
            db_order = Order(
                venue=venue,
                symbol=symbol,
                side=side,
                qty=qty,
                price=price,
                status="ACCEPTED",
                external_id=None,
            )
            session.add(db_order)
            session.commit()
            session.refresh(db_order)

            # In DEMO mode, assume immediate fill at provided price (or 0 if None)
            if venue.upper() == "DEMO":
                fill_price = price or 0.0
                fill = Fill(order_id=db_order.id, qty=qty, price=fill_price, fee=0.0)
                session.add(fill)
                # Update position
                self._apply_fill_to_position(session, symbol=symbol, side=side, qty=qty, price=fill_price)
                session.commit()

            result = {
                "id": db_order.id,
                "venue": db_order.venue,
                "symbol": db_order.symbol,
                "side": db_order.side,
                "qty": db_order.qty,
                "price": db_order.price,
                "status": db_order.status,
                "external_id": db_order.external_id,
            }
        self.logger.info("order.send", result)
        return result

    async def cancel_order(self, venue: str, external_id: str) -> dict:
        result = {"venue": venue, "external_id": external_id, "status": "CANCELED"}
        self.logger.info("order.cancel", result)
        return result

    def _apply_fill_to_position(self, session: Session, *, symbol: str, side: str, qty: float, price: float) -> None:
        # Fetch existing position
        pos = session.exec(select(Position).where(Position.symbol == symbol)).first()
        signed_qty = qty if side.upper() == "BUY" else -qty
        if pos is None:
            pos = Position(symbol=symbol, qty=signed_qty, avg_price=price)
            session.add(pos)
            return
        # Update weighted average price if increasing exposure in same direction
        new_qty = pos.qty + signed_qty
        if new_qty == 0:
            pos.avg_price = 0.0
            pos.qty = 0.0
        elif (pos.qty >= 0 and signed_qty >= 0) or (pos.qty <= 0 and signed_qty <= 0):
            # Same direction: recalc average
            total_cost = pos.avg_price * abs(pos.qty) + price * abs(signed_qty)
            pos.avg_price = total_cost / abs(new_qty)
            pos.qty = new_qty
        else:
            # Reducing or flipping: adjust qty; avg_price remains if not fully closed; if flipped, set to price
            if (pos.qty > 0 and new_qty > 0) or (pos.qty < 0 and new_qty < 0):
                pos.qty = new_qty
            elif new_qty == 0:
                pos.qty = 0.0
                pos.avg_price = 0.0
            else:
                # flipped
                pos.qty = new_qty
                pos.avg_price = price
