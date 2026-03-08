# Agentic Trading Bot

Bot de trading algorítmico con research pipeline basado en IA (Gemini), ejecutado sobre Binance Testnet.

## Arquitectura

```
┌─────────────────────┐        ┌──────────────────────┐
│  Next.js (Vercel)   │◄──────►│  Supabase (PostgreSQL)│
│  - Dashboard/UI     │        └──────────────────────┘
│  - API routes       │
│  - Vercel Cron      │        ┌──────────────────────┐
│    (trading loop)   │◄──────►│  Python Backend       │
└─────────────────────┘        │  (FastAPI, VPS)       │
         │                     │  - Motor cuantitativo │
         │                     │  - Loop 60s propio    │
         ▼                     └──────────┬───────────┘
┌─────────────────────┐                   │
│  Telegram Bot       │        ┌──────────▼───────────┐
│  (webhook + notify) │        │  Binance Testnet      │
└─────────────────────┘        │  (spot_testnet)       │
                                └──────────────────────┘
```

El frontend delega la ejecución al backend Python si `PYTHON_BACKEND_URL` está configurado.
Si no, Next.js corre su propio loop de trading vía Vercel Cron (cada 5 min).

## Requisitos

- Node >= 20.9.0
- pnpm 9.0.0
- Python 3.12

## Setup local

```bash
git clone <repo>
cd traiding-agentic

# Frontend
cp .env.example .env.local
pnpm install
pnpm dev

# Backend Python (separado)
cd backend
python -m venv venv
# Windows: venv\Scripts\activate | Linux/Mac: source venv/bin/activate
pip install -r requirements.txt
# Las variables de entorno se toman del .env.local del paso anterior
# o exportarlas en el shell: export SUPABASE_URL=... etc.
uvicorn app.main:app --reload --port 8000
```

## Variables de entorno

| Variable | Descripción | Requerida |
|---|---|---|
| `GOOGLE_AI_API_KEY` | API key de Gemini (research, chat, embeddings) | Sí |
| `NEXT_PUBLIC_SUPABASE_URL` | URL pública de Supabase | Sí |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Anon key de Supabase | Sí |
| `SUPABASE_SERVICE_ROLE_KEY` | Service role key (operaciones server-side) | Sí |
| `TELEGRAM_BOT_TOKEN` | Token del bot de Telegram | Sí |
| `TELEGRAM_CHAT_ID` | Chat ID destino de notificaciones | Sí |
| `BINANCE_TESTNET_API_KEY` | API key de Binance Testnet | Sí |
| `BINANCE_TESTNET_SECRET` | Secret de Binance Testnet | Sí |
| `OPERATOR_API_KEY` | Auth para rutas operativas (`X-Operator-Key`) | Sí |
| `BACKEND_SECRET` | Secreto compartido Next.js ↔ Python backend | Sí |
| `PYTHON_BACKEND_URL` | URL del backend Python (si está en VPS) | No |
| `TRADING_ENABLED` | Kill switch de trading (`false` por defecto) | No |

Ver `.env.example` para la lista completa.

## Deploy

**Frontend (Vercel):**
```bash
vercel deploy
# o push a master (CI automático vía GitHub Actions)
```

**Backend Python (Docker):**
```bash
cd backend
docker build -t trading-backend .
docker run -d -p 8000:8000 --env-file ../.env trading-backend
```
El backend está diseñado para correr en cualquier VPS con Docker (ej: Easypanel).

## Testing

```bash
# Frontend
pnpm lint
pnpm typecheck
pnpm build

# Backend Python
pytest backend/tests -q
# 56 unit tests
```

CI corre automáticamente en GitHub Actions (lint + typecheck + build + pytest + SSRF tests).

## Estructura

```
traiding-agentic/
├── app/                  # Next.js App Router (pages + API routes)
│   ├── api/              # API routes (health, trades, pipeline, chat, telegram, cron)
│   ├── chat/             # Chat con agente Gemini
│   ├── sources/          # Fuentes de investigación
│   ├── strategies/       # Estrategias detectadas
│   ├── trades/           # Propuestas y ejecución
│   ├── portfolio/        # Posiciones y P&L
│   ├── quant/            # Análisis cuantitativo
│   ├── logs/             # Logs del sistema
│   ├── history/          # Historial
│   ├── docs/             # Documentación generada por IA
│   └── guides/           # Guías generadas por IA
├── backend/              # FastAPI (motor cuantitativo, señales, riesgo)
│   ├── app/
│   │   └── main.py
│   ├── tests/            # 56 unit tests
│   └── Dockerfile
├── components/           # Componentes React compartidos
├── lib/                  # Utilidades y clientes (Supabase, Binance, Gemini)
└── .env.example
```
