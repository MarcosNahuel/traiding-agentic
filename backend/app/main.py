import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import health, proposals, execute, portfolio
from .routers import klines, indicators, analysis, backtest, quant_status
from .services.trading_loop import run_loop
from .config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

_loop_task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _loop_task
    logger.info(f"Trading backend starting (env={settings.binance_env}, proxy={settings.binance_proxy_url})")
    _loop_task = asyncio.create_task(run_loop(interval_seconds=60))
    yield
    if _loop_task:
        _loop_task.cancel()
        try:
            await _loop_task
        except asyncio.CancelledError:
            pass
    logger.info("Trading backend stopped")


app = FastAPI(title="Trading Backend", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(proposals.router)
app.include_router(execute.router)
app.include_router(portfolio.router)
app.include_router(klines.router)
app.include_router(indicators.router)
app.include_router(analysis.router)
app.include_router(backtest.router)
app.include_router(quant_status.router)
