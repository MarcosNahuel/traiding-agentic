from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter()


class UpsertQuote(BaseModel):
    symbol: str
    bid: float | None = None
    ask: float | None = None
    last: float | None = None
    venue: str = "IOL"
    timestamp_ms: int


@router.get("/prices/{symbol}")
async def get_price(symbol: str, request: Request) -> dict:
    quote = request.app.state.market_data.get_last_quote(symbol)
    if not quote:
        return {"symbol": symbol, "quote": None}
    return {"symbol": symbol, "quote": quote.__dict__}


@router.post("/prices")
async def upsert_price(body: UpsertQuote, request: Request) -> dict:
    from ..services.market_data import MarketQuote

    q = MarketQuote(
        symbol=body.symbol,
        bid=body.bid,
        ask=body.ask,
        last=body.last,
        venue=body.venue,
        timestamp_ms=body.timestamp_ms,
    )
    request.app.state.market_data.upsert_quote(q)
    return {"ok": True}
