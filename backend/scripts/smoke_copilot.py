"""Smoke test del Claude veto co-pilot — UNA llamada real a Claude, sin trade real.

Verifica de punta a punta: token + claude CLI (Node) + KB + el loop del agente.

Uso (desde backend/):
    # backend/.env debe tener COPILOT_ENABLED=true y CLAUDE_CODE_OAUTH_TOKEN=...
    python scripts/smoke_copilot.py
"""
import asyncio
import os
import sys

# La consola de Windows (cp1252) no puede imprimir emojis — forzar UTF-8.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# Permitir `python scripts/smoke_copilot.py` desde backend/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings  # noqa: E402
from app.services.copilot.veto_agent import veto_gate  # noqa: E402


async def main() -> None:
    if not settings.copilot_enabled:
        print("⚠️  COPILOT_ENABLED no está en true en backend/.env — lo forzamos solo para este smoke.")
        settings.copilot_enabled = True
    if not settings.claude_code_oauth_token and not os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"):
        print("❌ Falta CLAUDE_CODE_OAUTH_TOKEN (en backend/.env o en el entorno). El veto haría fail-open.")

    print("Corriendo veto sobre un candidato BUY de prueba (ETHUSDT, régimen ranging)...\n")
    verdict = await veto_gate(
        symbol="ETHUSDT",
        trade_type="buy",
        price=3000.0,
        quantity=0.02,
        notional=60.0,
        reasoning=(
            "Entry[range-caution]: RSI=46, ADX=22, Entropy=0.71, "
            "Regime=ranging(72%), BreakoutHints=0(none), SMA20<SMA50(override)"
        ),
        proposal_id="smoke-test",
    )

    print("=== VEREDICTO ===")
    print(f"  veto            = {verdict.veto}  ({'BLOQUEA el trade' if verdict.veto else 'deja pasar'})")
    print(f"  confidence      = {verdict.confidence}")
    print(f"  reason          = {verdict.reason}")
    print(f"  failed_open     = {verdict.failed_open}  (true = el SDK falló → aprobó por default)")
    print(f"  latency_ms      = {verdict.latency_ms}")
    print(f"  tool_calls      = {verdict.tool_calls}")

    if verdict.failed_open:
        print(
            "\n⚠️  failed_open=true → el agente NO corrió bien. Revisá:\n"
            "    - `claude` CLI en PATH (npm install -g @anthropic-ai/claude-code)\n"
            "    - Node instalado\n"
            "    - CLAUDE_CODE_OAUTH_TOKEN válido (claude setup-token)\n"
        )
    else:
        print("\n✅ El agente corrió y emitió veredicto vía submit_verdict. Integración OK.")


if __name__ == "__main__":
    asyncio.run(main())
