FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src

RUN pip install --no-cache-dir .

# data/ (SQLite + brief) se monta como volumen en runtime.
VOLUME ["/app/data"]

CMD ["asesor-iol"]
