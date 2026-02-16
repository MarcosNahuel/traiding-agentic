from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from .config import AppSettings
from .services.market_data import MarketDataHandler
from .services.strategy import StrategyEngine
from .services.execution import OrderExecutionManager
from .services.risk import RiskManager
from .services.logging_service import LoggingService
from .services.agent_llm import GeminiAgent
from .utils.db import init_db
from .routers import health, status, prices, orders, positions, agent


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = AppSettings()  # Loads env configuration
    app.state.settings = settings

    # Initialize shared services and attach to app state
    app.state.logger = LoggingService()
    app.state.market_data = MarketDataHandler(settings=settings, logger=app.state.logger)
    app.state.risk = RiskManager(settings=settings, logger=app.state.logger)
    app.state.execution = OrderExecutionManager(settings=settings, logger=app.state.logger, risk_manager=app.state.risk)
    app.state.strategy = StrategyEngine(settings=settings,
                                        logger=app.state.logger,
                                        market_data=app.state.market_data,
                                        execution=app.state.execution,
                                        risk_manager=app.state.risk)
    # Initialize LLM agent (Gemini) if configured
    app.state.agent = None
    if settings.google_api_key:
        try:
            app.state.agent = GeminiAgent(api_key=settings.google_api_key,
                                          model_name=settings.gemini_model,
                                          risk_manager=app.state.risk,
                                          strategy_engine=app.state.strategy)
            app.state.logger.info("agent.init", {"provider": "gemini", "model": settings.gemini_model})
        except Exception as e:
            app.state.logger.error("agent.init.error", {"error": str(e)})

    # Initialize database
    init_db(settings)

    # Start background workers if needed (pollers, ws). MVP keeps manual triggers
    await app.state.market_data.start()
    yield
    await app.state.market_data.stop()


app = FastAPI(lifespan=lifespan, title="Agentic Trading Bot API", version="0.1.0")

# CORS configuration for local dev and web frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(health.router)
app.include_router(status.router, prefix="/api")
app.include_router(prices.router, prefix="/api")
app.include_router(orders.router, prefix="/api")
app.include_router(positions.router, prefix="/api")
app.include_router(agent.router, prefix="/api")
