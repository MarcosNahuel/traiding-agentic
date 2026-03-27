"""MCP Tools for the Daily LLM Analyst.

7 @tool functions that wrap existing Python code for LangGraph agent access.
These are NOT remote MCP servers — they're native LangChain tools for efficiency.
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from pathlib import Path

import httpx
from langchain_core.tools import tool

logger = logging.getLogger(__name__)


@tool
async def get_quant_snapshot(symbol: str) -> str:
    """Get complete quant analysis for a symbol: technical indicators (RSI, MACD,
    ADX, ATR, Bollinger Bands, PPO), entropy reading, market regime detection,
    support/resistance levels, and position sizing recommendation."""
    try:
        from ..quant_orchestrator import get_quant_snapshot as _get
        snapshot = await _get(symbol)
        if not snapshot:
            return json.dumps({"error": f"No quant data for {symbol}"})
        return snapshot.model_dump_json()
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
async def get_recent_trades(symbol: str, days: int = 7) -> str:
    """Get recent closed trades for a symbol including entry/exit prices, PnL,
    realized PnL percent, holding time, and SL/TP levels. Used to assess
    strategy effectiveness and identify patterns."""
    try:
        from ...db import get_supabase
        supabase = get_supabase()
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        resp = (
            supabase.table("positions")
            .select("symbol,side,entry_price,exit_price,realized_pnl,realized_pnl_percent,"
                    "stop_loss_price,take_profit_price,opened_at,closed_at,status")
            .eq("symbol", symbol)
            .eq("status", "closed")
            .gte("closed_at", cutoff)
            .order("closed_at", desc=True)
            .limit(20)
            .execute()
        )
        trades = resp.data or []
        if not trades:
            return json.dumps({"symbol": symbol, "trades": [], "message": "No recent trades"})

        wins = sum(1 for t in trades if float(t.get("realized_pnl") or 0) > 0)
        total_pnl = sum(float(t.get("realized_pnl") or 0) for t in trades)
        return json.dumps({
            "symbol": symbol,
            "period_days": days,
            "total_trades": len(trades),
            "wins": wins,
            "losses": len(trades) - wins,
            "win_rate": round(wins / len(trades) * 100, 1) if trades else 0,
            "total_pnl": round(total_pnl, 4),
            "trades": trades,
        }, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
async def get_portfolio_state() -> str:
    """Get current portfolio state: USDT balance, open positions with unrealized PnL,
    daily P&L, win rate, total trades, and current drawdown."""
    try:
        from ..portfolio import get_portfolio_state as _get
        state = await _get()
        return json.dumps(state, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def get_research_context(topic: str) -> str:
    """Search the trading research knowledge base for strategy recommendations.
    Topics: 'trend momentum', 'mean reversion', 'breakout volatilidad',
    'entropy', 'ml sentiment', 'riesgo ejecucion', 'arbitraje'."""
    try:
        docs_dir = Path(__file__).parent.parent.parent.parent / "docs" / "estrategias"
        if not docs_dir.exists():
            # Try alternative path for Docker
            docs_dir = Path("/app/docs/estrategias")

        results = []
        topic_lower = topic.lower()

        for md_file in sorted(docs_dir.glob("*.md")):
            try:
                content = md_file.read_text(encoding="utf-8", errors="ignore")
                if topic_lower in content.lower():
                    # Extract first 500 chars of matching file
                    results.append({
                        "file": md_file.name,
                        "excerpt": content[:500].strip(),
                    })
            except Exception:
                continue

        if not results:
            return json.dumps({"topic": topic, "results": [], "message": "No matching research found"})

        return json.dumps({"topic": topic, "results_count": len(results), "results": results[:3]})
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
async def search_market_news(query: str) -> str:
    """Search for recent crypto market news and sentiment from major sources.
    Returns headlines and summaries. Use queries like 'bitcoin outlook',
    'ethereum update', 'crypto regulation', 'market crash'."""
    try:
        import feedparser

        feeds = [
            "https://cointelegraph.com/rss",
            "https://www.coindesk.com/arc/outboundfeeds/rss/",
        ]

        articles = []
        query_lower = query.lower()

        async with httpx.AsyncClient(timeout=10.0) as client:
            for feed_url in feeds:
                try:
                    resp = await client.get(feed_url)
                    feed = feedparser.parse(resp.text)
                    for entry in feed.entries[:10]:
                        title = entry.get("title", "")
                        summary = entry.get("summary", "")[:200]
                        if query_lower in title.lower() or query_lower in summary.lower():
                            articles.append({
                                "title": title,
                                "summary": summary,
                                "published": entry.get("published", ""),
                                "source": feed_url.split("/")[2],
                            })
                except Exception:
                    continue

        if not articles:
            return json.dumps({"query": query, "articles": [],
                             "message": "No matching news found. Market may be quiet."})

        return json.dumps({"query": query, "count": len(articles), "articles": articles[:5]})
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
async def get_fear_greed_index() -> str:
    """Get the current Crypto Fear & Greed Index (0-100).
    0-24: Extreme Fear, 25-49: Fear, 50: Neutral, 51-74: Greed, 75-100: Extreme Greed.
    This is a key sentiment indicator for daily market assessment."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get("https://api.alternative.me/fng/?limit=1")
            data = resp.json()
            if data.get("data"):
                entry = data["data"][0]
                return json.dumps({
                    "value": int(entry["value"]),
                    "classification": entry["value_classification"],
                    "timestamp": entry.get("timestamp", ""),
                })
        return json.dumps({"error": "No data from Fear & Greed API"})
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
async def get_performance_metrics() -> str:
    """Get rolling performance metrics: Sharpe ratio, Sortino ratio, win rate,
    profit factor, max drawdown, Kelly fraction, expectancy.
    Available for 7-day, 30-day, and all-time periods."""
    try:
        from ...db import get_supabase
        supabase = get_supabase()
        resp = (
            supabase.table("performance_metrics")
            .select("*")
            .order("calculated_at", desc=True)
            .limit(5)
            .execute()
        )
        metrics = resp.data or []
        if not metrics:
            return json.dumps({"message": "No performance metrics available yet"})
        return json.dumps(metrics, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


# Export all tools for LangGraph
ALL_TOOLS = [
    get_quant_snapshot,
    get_recent_trades,
    get_portfolio_state,
    get_research_context,
    search_market_news,
    get_fear_greed_index,
    get_performance_metrics,
]
