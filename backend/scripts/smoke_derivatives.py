"""Smoke test: hit Binance Futures public endpoints, print derivatives snapshot.

Run from backend dir: python scripts/smoke_derivatives.py BTCUSDT
"""
import asyncio
import json
import sys

from app.services.derivatives_client import get_derivatives_snapshot


async def main():
    symbol = sys.argv[1] if len(sys.argv) > 1 else "BTCUSDT"
    snap = await get_derivatives_snapshot(symbol)
    print(json.dumps(snap, indent=2, default=str))

    # Sanity assertions
    assert snap["symbol"] == symbol
    assert snap["funding_rate_current"] is not None, "Funding data missing"
    assert snap["oi_current_usd"] is not None, "OI data missing"
    print("\nAll checks PASSED.")


if __name__ == "__main__":
    asyncio.run(main())
