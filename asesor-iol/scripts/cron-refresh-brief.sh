#!/usr/bin/env bash
# Regenera el brief de contexto de mercado del asesor IOL.
# Pensado para cron en el VPS (Linux). Ejemplo de crontab (cada 6 h):
#
#   0 */6 * * * /ruta/al/repo/asesor-iol/scripts/cron-refresh-brief.sh >> /var/log/asesor-brief.log 2>&1
#
# Con secretos en Infisical, envolver con `infisical run --`:
#   0 */6 * * * cd /ruta/asesor-iol && infisical run -- ./scripts/cron-refresh-brief.sh
set -euo pipefail

cd "$(dirname "$0")/.."

# Usa el venv del proyecto si existe; si no, el python del PATH.
PYTHON="./.venv/bin/python"
[ -x "$PYTHON" ] || PYTHON="python3"

export PYTHONIOENCODING=utf-8
PYTHONPATH=src "$PYTHON" -m asesor_iol.context.refresh_market
