"""Runner para Strategy Replay — ejecutar desde terminal.

Uso:
    cd backend
    python run_replay.py                           # BTC 90 días, rules only
    python run_replay.py --symbol ETHUSDT --days 180  # ETH 180 días
    python run_replay.py --all --days 365 --ml     # Todos los symbols, 365 días, con ML
    python run_replay.py --symbol BTCUSDT --days 365 --ml  # BTC con ML
"""

import argparse
import asyncio
import logging
import sys
import os

# Agregar el directorio backend al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Cargar .env desde la raíz del proyecto
from dotenv import load_dotenv
root_env = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")
load_dotenv(root_env)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
# Silenciar logs verbosos
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("hpack").setLevel(logging.WARNING)


async def main():
    parser = argparse.ArgumentParser(description="Strategy Replay Simulator")
    parser.add_argument("--symbol", type=str, default="BTCUSDT", help="Par de trading")
    parser.add_argument("--days", type=int, default=90, help="Días de historia")
    parser.add_argument("--ml", action="store_true", help="Incluir ML (LightGBM)")
    parser.add_argument("--all", action="store_true", help="Todos los symbols")
    args = parser.parse_args()

    from app.services.strategy_replay import run_comparison, run_full_comparison

    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║          STRATEGY REPLAY SIMULATOR                      ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()

    if args.all:
        results = await run_full_comparison(days=args.days)
        print("\n\n" + "═" * 60)
        print("  RESUMEN GLOBAL")
        print("═" * 60)
        for sym, res in results.items():
            if "error" in res:
                print(f"  {sym}: ERROR — {res['error']}")
            else:
                r = res["rules"]
                print(f"  {sym}: {r.total_trades} trades | WR {r.win_rate}% | PnL ${r.total_pnl:+.2f} | Sharpe {r.sharpe_ratio:.2f}")
    else:
        result = await run_comparison(
            symbol=args.symbol.upper(),
            days=args.days,
            train_ml=args.ml,
        )

        print("\n" + result["comparison_table"])

        # Desglose de trades
        rules = result["rules"]
        if rules.trades:
            print(f"\n{'─' * 60}")
            print(f"  Detalle trades ({rules.mode}): {len(rules.trades)} operaciones")
            print(f"{'─' * 60}")
            for t in rules.trades[-20:]:  # Últimos 20
                emoji = "✅" if t.pnl > 0 else "❌"
                print(
                    f"  {emoji} ${t.entry_price:>10,.2f} → ${t.exit_price:>10,.2f} | "
                    f"PnL: ${t.pnl:>+7.2f} ({t.pnl_pct:>+6.2f}%) | "
                    f"{t.hold_bars:>3}h | {t.exit_reason}"
                )

    print()


if __name__ == "__main__":
    asyncio.run(main())
