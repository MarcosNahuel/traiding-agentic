# Agentic Trading Bot (MVP)

Arranque rápido con Docker:

```bash
docker compose up --build
```

- Backend API: http://localhost:8000/health
- Frontend: http://localhost:3000/

Configura tus variables en `.env` (basado en `.env.example`).

Base de datos (Supabase / Postgres):
- Define `DATABASE_URL` apuntando a tu instancia de Supabase/Postgres (ejemplo):
  `postgresql+psycopg2://USER:PASSWORD@HOST:5432/DBNAME?sslmode=require`
- `docker-compose.yml` ahora lee variables desde `.env` para el backend.

Estructura:
- `backend/` (FastAPI + core trading)
- `frontend/` (Next.js + dashboard + chat)
- `data/` (sqlite, logs, vector store)

Siguientes pasos:
- Implementar conectores IOL/pyRofex en `app/services/execution.py` y market data en `app/services/market_data.py`.
- Añadir lógica de estrategia (paridad/z-score) en `app/services/strategy.py`.
- Integrar MCP + LangChain + LlamaIndex en `app/routers/agent.py`.

Agente (Gemini de Google):
- Variables de entorno: `GOOGLE_API_KEY` (obligatoria) y `GEMINI_MODEL` (por defecto `gemini-1.5-pro`).
- Endpoint: `POST /api/agent/query` con `{ "query": "<tu pregunta>" }`.
- Si no hay `GOOGLE_API_KEY`, el endpoint hace fallback a respuestas simples (límites/estado).
