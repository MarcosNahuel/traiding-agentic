"""Smoke test de IOL: autentica y lee el estado de cuenta.

Verifica que (1) la API esté activada, (2) las credenciales del .env sean correctas
y (3) el token/refresh funcionen. NO opera nada — solo lectura.

Uso (con .env completo en asesor-iol/):
    python scripts/smoke_iol.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from asesor_iol.config import load_settings  # noqa: E402
from asesor_iol.iol.client import IOLClient, IOLError  # noqa: E402


async def main() -> int:
    s = load_settings()
    print(f"→ Autenticando contra {s.iol_api_base} como {s.iol_username} ...")
    try:
        async with IOLClient(s.iol_username, s.iol_password, s.iol_api_base) as c:
            cuentas = await c.get_account_state()
            print("✅ Auth OK. Estado de cuenta:")
            for cta in cuentas:
                print(f"   - {cta.moneda}: disponible {cta.disponible}, total {cta.total}")
            print("→ Probando cartera ...")
            p = await c.get_portfolio()
            print(f"✅ Cartera OK: {len(p.holdings)} tenencias, total {p.total_valorizado}")
    except IOLError as e:
        print(f"❌ Falló: {e}")
        print("   Causas típicas: API no activada todavía, usuario/clave incorrectos,")
        print("   o estás apuntando a producción sin acceso. Revisá el .env.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
