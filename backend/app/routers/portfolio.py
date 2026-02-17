from fastapi import APIRouter
from ..services.portfolio import get_portfolio_state

router = APIRouter(prefix="/portfolio")


@router.get("")
async def portfolio():
    return await get_portfolio_state()
