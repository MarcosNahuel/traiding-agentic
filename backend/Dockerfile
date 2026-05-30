# Backend Dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# ── Claude Veto Co-Pilot (OPT-IN) ──────────────────────────────────────────────
# El co-piloto (COPILOT_ENABLED=true) usa el Claude Agent SDK, que spawnea el CLI
# de Claude Code (Node) como subproceso. Descomentá este bloque para que la imagen
# soporte habilitarlo. Si NO está y alguien pone COPILOT_ENABLED=true, el gate hace
# fail-open (el bot opera como hoy, sin vetar) — no rompe nada.
# RUN apt-get update && apt-get install -y --no-install-recommends nodejs npm \
#     && npm install -g @anthropic-ai/claude-code \
#     && apt-get clean && rm -rf /var/lib/apt/lists/*
# Además: pasar CLAUDE_CODE_OAUTH_TOKEN por env, y montar el KB:
#   volumes: ["./docs/knowledge-base:/app/knowledge-base:ro"]  + COPILOT_KB_DIR=/app/knowledge-base
# ───────────────────────────────────────────────────────────────────────────────

COPY app /app/app
# Copiar modelos ML entrenados (si existen)
COPY models /app/models

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
