import asyncio
import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from .routers import health, proposals, execute, portfolio
from .routers import klines, indicators, analysis, backtest, quant_status
from .routers import dead_letter, reconciliation, graduation
# Note: agent, status, orders, positions, prices are legacy routers
# that depend on sqlmodel/app.state which are no longer used
from .services.trading_loop import run_loop
from .config import settings


class AuthMiddleware(BaseHTTPMiddleware):
    """Validate Bearer token on all endpoints except /health and /docs."""

    OPEN_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}

    async def dispatch(self, request: Request, call_next):
        if not settings.backend_secret:
            return await call_next(request)  # No secret configured, skip auth

        if request.url.path in self.OPEN_PATHS:
            return await call_next(request)

        auth = request.headers.get("authorization", "")
        if not auth.startswith("Bearer ") or auth[7:] != settings.backend_secret:
            raise HTTPException(status_code=401, detail="Unauthorized")

        return await call_next(request)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

_loop_task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _loop_task
    if not settings.backend_secret:
        logger.warning("BACKEND_SECRET is not set — all API endpoints are publicly accessible. Set BACKEND_SECRET in production.")
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

_allowed_origins = [
    o.strip()
    for o in os.environ.get(
        "ALLOWED_ORIGINS",
        "http://localhost:3000,https://traiding-agentic.vercel.app"
    ).split(",")
    if o.strip()
]

app.add_middleware(AuthMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
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
app.include_router(dead_letter.router)
app.include_router(reconciliation.router)
app.include_router(graduation.router)
