# Backend Dockerfile

# ── Node + Claude Code CLI (para el Agent SDK: chat de Telegram y co-pilot) ──────
# El chat conversacional (CHAT_ENABLED=true) y el veto co-pilot (COPILOT_ENABLED=true)
# usan el Claude Agent SDK, que spawnea el CLI de Claude Code (Node) como subproceso.
# Traemos Node desde la imagen oficial (multi-stage, confiable — sin apt flaky).
# Si el SDK no está disponible en runtime, ambos features hacen fail-safe (el bot
# opera como hoy) — no rompe nada. Auth por CLAUDE_CODE_OAUTH_TOKEN (env).
FROM node:20-slim AS node

FROM python:3.11-slim
# git: el CLI de Claude Code (agente de código) lo necesita para arrancar la sesión;
# sin git el SDK falla con ProcessError. ca-certificates para TLS salientes.
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates \
    && apt-get clean && rm -rf /var/lib/apt/lists/*
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -sf /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && npm install -g @anthropic-ai/claude-code \
    && npm cache clean --force
# ───────────────────────────────────────────────────────────────────────────────

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY app /app/app
# Copiar modelos ML entrenados (si existen)
COPY models /app/models

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
