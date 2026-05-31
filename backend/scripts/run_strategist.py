"""Run / smoke-test the Daily Strategist fleet — one real run, dry-run (no active config touched).

Usage (from backend/):
    # backend/.env con CLAUDE_CODE_OAUTH_TOKEN (+ SUPABASE_* para datos reales)
    python scripts/run_strategist.py
"""
import asyncio
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings  # noqa: E402
from app.services.strategist.runner import run_daily_strategist  # noqa: E402


async def main() -> None:
    if not settings.claude_code_oauth_token and not os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"):
        print("❌ Falta CLAUDE_CODE_OAUTH_TOKEN — el run degradaría.")
    print("Corriendo el fleet del strategist (data-analyst + knowledge -> decision)...")
    print("Puede tardar 1-3 min (subagentes + tools + web).\n")

    result = await run_daily_strategist()

    print("=== RESULTADO ===")
    for k, v in result.items():
        print(f"  {k:24} = {v}")
    if result.get("degraded"):
        print("\n⚠️  Run DEGRADADO (el agente no decidió bien). Revisá token / CLI / datos.")
    else:
        print("\n✅ Fleet corrió y decidió. Eval escrita; propuesta (si TWEAK) quedó pending_approval.")
        print(f"   Abrí: {result.get('eval_path')}")


if __name__ == "__main__":
    asyncio.run(main())
