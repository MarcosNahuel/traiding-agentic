"""LangGraph state graphs for pre-market analysis and post-market audit.

Two independent graphs:
1. pre_market_graph: Analyzes market → generates TradingConfigOverride
2. post_market_graph: Audits performance → generates AuditReport
"""

import json
import logging
from datetime import datetime, timezone
from typing import TypedDict, Annotated, Optional

from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import HumanMessage, SystemMessage, BaseMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from .models import TradingConfigOverride, DailyBrief, AuditReport, validate_bounds
from .prompts import PRE_MARKET_SYSTEM, POST_MARKET_SYSTEM
from .tools import ALL_TOOLS

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════════
# State definitions
# ════════════════════════════════════════════════════════════════════

class PreMarketState(TypedDict):
    messages: list[BaseMessage]
    market_data: str
    proposed_config: Optional[dict]
    validated_config: Optional[dict]
    warnings: list[str]
    brief: Optional[dict]
    error: Optional[str]


class PostMarketState(TypedDict):
    messages: list[BaseMessage]
    performance_data: str
    audit: Optional[dict]
    error: Optional[str]


# ════════════════════════════════════════════════════════════════════
# Pre-Market Graph
# ════════════════════════════════════════════════════════════════════

def _get_llm(model_name: str = "gemini-2.0-flash", api_key: str = ""):
    """Create Gemini LLM instance."""
    return ChatGoogleGenerativeAI(
        model=model_name,
        google_api_key=api_key,
        temperature=0.3,
        max_output_tokens=4096,
    )


async def gather_market_data(state: PreMarketState) -> dict:
    """Node 1: Gather all market data using tools."""
    from ...config import settings
    symbols = settings.quant_symbols.split(",")

    llm = _get_llm(settings.analyst_model_name, settings.google_api_key)
    llm_with_tools = llm.bind_tools(ALL_TOOLS)

    # Ask LLM to gather data using ALL 9 tools
    gather_prompt = (
        f"Gather market data for today's analysis. Use ALL these tools:\n"
        f"1. get_quant_snapshot for each symbol: {', '.join(symbols)}\n"
        f"2. get_portfolio_state for current positions and balance\n"
        f"3. get_fear_greed_index for market sentiment\n"
        f"4. get_performance_metrics for rolling Sharpe, win rate, etc.\n"
        f"5. search_market_news with 'crypto market' for latest events\n"
        f"6. get_research_context with 'trend momentum' for strategy guidance\n"
        f"7. get_ml_review for ML model performance and recommendation\n"
        f"8. get_daily_research for latest research and news digest\n"
        f"9. get_recent_trades for each symbol to see recent performance\n\n"
        f"Call ALL tools now. The ML review and research are critical for config decisions."
    )

    messages = [
        SystemMessage(content=PRE_MARKET_SYSTEM),
        HumanMessage(content=gather_prompt),
    ]

    # Let the LLM call tools iteratively
    for _ in range(5):  # max 5 tool-calling rounds
        response = await llm_with_tools.ainvoke(messages)
        messages.append(response)

        if not response.tool_calls:
            break

        # Execute tools
        tool_node = ToolNode(ALL_TOOLS)
        tool_results = await tool_node.ainvoke({"messages": messages})
        messages.extend(tool_results.get("messages", []))

    return {"messages": messages, "market_data": "gathered"}


async def generate_config(state: PreMarketState) -> dict:
    """Node 2: LLM generates TradingConfigOverride from gathered data."""
    from ...config import settings

    llm = _get_llm(settings.analyst_model_name, settings.google_api_key)

    messages = list(state.get("messages", []))
    messages.append(HumanMessage(content=(
        "Based on all the data you gathered, generate the trading configuration "
        "for the next 24 hours. Output ONLY a JSON object with these fields:\n"
        "buy_adx_min, buy_entropy_max, buy_rsi_max, sell_rsi_min, "
        "signal_cooldown_minutes, sl_atr_multiplier, tp_atr_multiplier, "
        "risk_multiplier, max_open_positions, quant_symbols, reasoning.\n\n"
        "Be specific in your reasoning. Reference the data you analyzed."
    )))

    response = await llm.ainvoke(messages)

    # Parse JSON from response
    try:
        text = response.content
        # Extract JSON from markdown code blocks if present
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]

        config_dict = json.loads(text.strip())
        return {"proposed_config": config_dict, "messages": messages + [response]}
    except (json.JSONDecodeError, IndexError) as e:
        logger.error("Failed to parse LLM config output: %s", e)
        return {"proposed_config": None, "error": f"JSON parse error: {e}"}


async def validate_config(state: PreMarketState) -> dict:
    """Node 3: Validate and clamp config to hard bounds."""
    proposed = state.get("proposed_config")
    if not proposed:
        return {"validated_config": None, "error": "No config to validate"}

    clamped, warnings = validate_bounds(proposed)

    try:
        config = TradingConfigOverride(**clamped)
        return {
            "validated_config": config.model_dump(),
            "warnings": warnings,
        }
    except Exception as e:
        logger.error("Config validation failed: %s", e)
        return {"validated_config": None, "error": str(e)}


async def persist_config(state: PreMarketState) -> dict:
    """Node 4: Write validated config to Supabase."""
    config = state.get("validated_config")
    if not config:
        return {"error": "No validated config to persist"}

    try:
        from ...db import get_supabase
        supabase = get_supabase()
        now = datetime.now(timezone.utc)

        # Deactivate previous active configs
        supabase.table("llm_trading_configs").update({
            "status": "superseded",
            "superseded_at": now.isoformat(),
        }).eq("status", "active").execute()

        # Insert new active config
        row = {
            **config,
            "status": "active",
            "source": "llm_premarket",
            "confidence_score": 0.7,
            "values_clamped": state.get("warnings", []),
            "created_at": now.isoformat(),
            "expires_at": (now.replace(hour=23, minute=0, second=0) +
                          __import__("datetime").timedelta(days=1)).isoformat(),
        }
        supabase.table("llm_trading_configs").insert(row).execute()

        # Invalidate config bridge cache
        from .config_bridge import invalidate_cache
        invalidate_cache()

        logger.info("Pre-market config persisted: %s", config.get("reasoning", "")[:100])
        return {"brief": {"config": config, "persisted": True}}

    except Exception as e:
        logger.error("Failed to persist config: %s", e)
        return {"error": f"Persist failed: {e}"}


async def notify_telegram(state: PreMarketState) -> dict:
    """Node 5: Send Telegram notification with daily brief."""
    config = state.get("validated_config", {})
    warnings = state.get("warnings", [])

    try:
        from ..telegram_notifier import send_telegram, escape_html

        symbols = config.get("quant_symbols", "N/A")
        reasoning = config.get("reasoning", "No reasoning provided")[:300]
        warn_text = "\n".join(f"  - {w}" for w in warnings) if warnings else "None"

        msg = (
            f"<b>DAILY BRIEF — PRE-MARKET</b>\n\n"
            f"<b>Config:</b>\n"
            f"  ADX min: {config.get('buy_adx_min', '?')}\n"
            f"  Entropy max: {config.get('buy_entropy_max', '?')}\n"
            f"  RSI max: {config.get('buy_rsi_max', '?')}\n"
            f"  Cooldown: {config.get('signal_cooldown_minutes', '?')}m\n"
            f"  SL: {config.get('sl_atr_multiplier', '?')}x ATR\n"
            f"  TP: {config.get('tp_atr_multiplier', '?')}x ATR\n"
            f"  Risk: {config.get('risk_multiplier', '?')}x\n"
            f"  Symbols: {escape_html(symbols)}\n\n"
            f"<b>Clamped:</b> {warn_text}\n\n"
            f"<b>Reasoning:</b>\n{escape_html(reasoning)}"
        )
        await send_telegram(msg)
    except Exception as e:
        logger.warning("Telegram notify failed: %s", e)

    return {}


def build_pre_market_graph() -> StateGraph:
    """Build the pre-market analysis LangGraph."""
    graph = StateGraph(PreMarketState)

    graph.add_node("gather", gather_market_data)
    graph.add_node("generate", generate_config)
    graph.add_node("validate", validate_config)
    graph.add_node("persist", persist_config)
    graph.add_node("notify", notify_telegram)

    graph.set_entry_point("gather")
    graph.add_edge("gather", "generate")
    graph.add_edge("generate", "validate")

    # Conditional: only persist if validation succeeded
    def should_persist(state):
        return "persist" if state.get("validated_config") else END

    graph.add_conditional_edges("validate", should_persist, {"persist": "persist", END: END})
    graph.add_edge("persist", "notify")
    graph.add_edge("notify", END)

    return graph.compile()


# ════════════════════════════════════════════════════════════════════
# Post-Market Graph
# ════════════════════════════════════════════════════════════════════

async def gather_performance(state: PostMarketState) -> dict:
    """Node 1: Gather today's performance data using tools."""
    from ...config import settings

    llm = _get_llm(settings.analyst_model_name, settings.google_api_key)
    llm_with_tools = llm.bind_tools(ALL_TOOLS)

    symbols = settings.quant_symbols.split(",")
    gather_prompt = (
        f"Gather today's trading performance data for audit. Use these tools:\n"
        f"1. get_recent_trades for each: {', '.join(s.strip() for s in symbols)} (days=1)\n"
        f"2. get_portfolio_state for current balance and positions\n"
        f"3. get_performance_metrics for rolling metrics\n"
        f"4. get_fear_greed_index for today's sentiment\n"
        f"5. search_market_news with 'crypto today' for events\n"
        f"6. get_ml_review for ML model hit rate and recommendation\n"
        f"7. get_daily_research for latest news and research context\n\n"
        f"Call ALL tools now. ML review is critical for the audit."
    )

    messages = [
        SystemMessage(content=POST_MARKET_SYSTEM),
        HumanMessage(content=gather_prompt),
    ]

    for _ in range(5):
        response = await llm_with_tools.ainvoke(messages)
        messages.append(response)
        if not response.tool_calls:
            break
        tool_node = ToolNode(ALL_TOOLS)
        tool_results = await tool_node.ainvoke({"messages": messages})
        messages.extend(tool_results.get("messages", []))

    return {"messages": messages, "performance_data": "gathered"}


async def generate_audit(state: PostMarketState) -> dict:
    """Node 2: LLM generates audit report."""
    from ...config import settings

    llm = _get_llm(settings.analyst_model_name, settings.google_api_key)

    messages = list(state.get("messages", []))
    messages.append(HumanMessage(content=(
        "Based on all the data, generate a trading audit report as JSON with:\n"
        "performance_summary: {daily_pnl, trades_closed, wins, losses, win_rate}\n"
        "trade_reviews: [{symbol, pnl, analysis, was_correct_call}] for each trade\n"
        "error_analysis: string describing any errors\n"
        "market_events: string describing relevant market events\n"
        "recommendations: [list of specific improvements]\n"
        "overall_grade: A to F\n"
        "Be quantitative and honest."
    )))

    response = await llm.ainvoke(messages)

    try:
        text = response.content
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        audit_dict = json.loads(text.strip())
        return {"audit": audit_dict}
    except (json.JSONDecodeError, IndexError) as e:
        logger.error("Failed to parse audit output: %s", e)
        return {"audit": {"overall_grade": "N/A", "error": str(e)}}


async def persist_audit(state: PostMarketState) -> dict:
    """Node 3: Persist audit to Supabase."""
    audit = state.get("audit")
    if not audit:
        return {}

    try:
        from ...db import get_supabase
        supabase = get_supabase()
        now = datetime.now(timezone.utc)

        row = {
            "audit_date": now.strftime("%Y-%m-%d"),
            "performance_summary": audit.get("performance_summary", {}),
            "trade_reviews": audit.get("trade_reviews", []),
            "error_analysis": audit.get("error_analysis", ""),
            "market_events": audit.get("market_events", ""),
            "recommendations": audit.get("recommendations", []),
            "overall_grade": audit.get("overall_grade", "N/A"),
            "model_used": "gemini-2.0-flash",
            "created_at": now.isoformat(),
        }
        supabase.table("llm_audit_reports").upsert(
            row, on_conflict="audit_date"
        ).execute()

        logger.info("Audit persisted: grade=%s", audit.get("overall_grade"))
    except Exception as e:
        logger.error("Failed to persist audit: %s", e)

    return {}


async def send_audit_telegram(state: PostMarketState) -> dict:
    """Node 4: Send audit report via Telegram."""
    audit = state.get("audit", {})

    try:
        from ..telegram_notifier import send_telegram, escape_html

        perf = audit.get("performance_summary", {})
        grade = audit.get("overall_grade", "?")
        recs = audit.get("recommendations", [])
        recs_text = "\n".join(f"  {i+1}. {r}" for i, r in enumerate(recs[:5]))

        msg = (
            f"<b>DAILY AUDIT</b> — Grade: <b>{escape_html(grade)}</b>\n\n"
            f"<b>Performance:</b>\n"
            f"  PnL: ${perf.get('daily_pnl', '?')}\n"
            f"  Trades: {perf.get('trades_closed', '?')} "
            f"(W:{perf.get('wins', '?')} L:{perf.get('losses', '?')})\n"
            f"  Win rate: {perf.get('win_rate', '?')}%\n\n"
            f"<b>Recommendations:</b>\n{recs_text}"
        )
        await send_telegram(msg)
    except Exception as e:
        logger.warning("Audit Telegram failed: %s", e)

    return {}


def build_post_market_graph() -> StateGraph:
    """Build the post-market audit LangGraph."""
    graph = StateGraph(PostMarketState)

    graph.add_node("gather", gather_performance)
    graph.add_node("audit", generate_audit)
    graph.add_node("persist", persist_audit)
    graph.add_node("notify", send_audit_telegram)

    graph.set_entry_point("gather")
    graph.add_edge("gather", "audit")
    graph.add_edge("audit", "persist")
    graph.add_edge("persist", "notify")
    graph.add_edge("notify", END)

    return graph.compile()
