"""Daily Strategist Agent (MVP, dry-run).

Runs once daily off the hot path: audits yesterday's trades, investigates macro
context (Fear&Greed, news, web), and proposes strategy/config adjustments. Output:
an evaluation markdown + a pending_approval config row (NEVER touches status=active).

Reuses the proven Claude Agent SDK pattern (see services/copilot/) and the existing
TradingConfigOverride bounds (services/daily_analyst/models.py).
See docs/superpowers/specs/2026-04-24-daily-strategist-agent-design.md
"""
