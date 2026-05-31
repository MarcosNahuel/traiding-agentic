FROM python:3.11-slim

WORKDIR /app

# El Claude Agent SDK spawnea el CLI de Claude Code (Node) como subproceso en cada
# query del asesor — sin esto, cada Advisor.ask falla al no encontrar el CLI.
RUN apt-get update && apt-get install -y --no-install-recommends nodejs npm \
    && npm install -g @anthropic-ai/claude-code \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# F4 (jury): hatchling lee README.md (declarado como `readme` en pyproject.toml) durante
# la generación de metadata del build → hay que copiarlo ANTES de `pip install .`.
COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir .

# data/ (SQLite + brief) se monta como volumen en runtime.
VOLUME ["/app/data"]

CMD ["asesor-iol"]
