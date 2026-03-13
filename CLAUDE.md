# Trading Agentic — Instrucciones para Claude Code

## Proyecto

Bot de trading agentic con pipeline de investigación AI + ejecución algorítmica en Binance Testnet.

- **Deploy Frontend:** Vercel
- **Deploy Backend:** Docker VPS (FastAPI)
- **Stack:** Next.js 16 + Python FastAPI (hybrid)

---

## Datos del Proyecto

| Campo | Valor |
|-------|-------|
| **Supabase Project Ref** | zaqpiuwacinvebfttygm |
| **Exchange** | Binance Testnet (spot_testnet) |
| **AI Model** | Google Gemini (via @ai-sdk/google) |
| **Package Manager** | pnpm |
| **Node** | >=20.9.0 |
| **Python** | 3.12 |

---

## Stack

### Frontend (Next.js)

- **Framework**: Next.js 16.1.6 (App Router)
- **UI**: React 19, Tailwind CSS 4, shadcn/ui, Lucide React
- **AI**: Vercel AI SDK 6 + @ai-sdk/google
- **State**: SWR, Zustand
- **Validation**: Zod 4
- **Auth**: Supabase Auth + middleware.ts

### Backend (Python)

- **Framework**: FastAPI + Uvicorn
- **Data**: Pandas, NumPy, SciPy, Scikit-learn
- **Trading**: Pandas-TA (indicadores técnicos)
- **DB**: Supabase Python client
- **Tests**: pytest + pytest-asyncio (56 tests)

---

## Comandos

```bash
# Frontend
pnpm dev          # Next.js dev (:3000)
pnpm build        # Build producción
pnpm lint         # ESLint (max-warnings 0)
pnpm typecheck    # TypeScript strict
pnpm format:check # Prettier

# Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
pytest tests/ -q --tb=short
```

---

## MCP Servers

Configurados en `.mcp.json`:

| MCP | Rol |
|-----|-----|
| `supabase` | Base de datos del proyecto |
| `next-devtools` | Dev server, errores, rutas |

---

## Arquitectura

```
Next.js (Vercel)      ←→  Supabase PostgreSQL
├─ Dashboard/UI
├─ API routes (50+)    ↓
└─ Vercel Cron    ←→  Python Backend (FastAPI, VPS)
    (5-min loop)      ├─ Motor cuantitativo
                      ├─ Loop 60s propio
                      └─ Binance Testnet (spot_testnet)

   Telegram Bot (webhook + notify)
```

### Agentes AI

1. **Source Agent** — Busca y valida fuentes de investigación
2. **Reader Agent** — Extrae información de papers/artículos
3. **Synthesis Agent** — Genera guías de trading accionables
4. **Chat Agent** — Interfaz conversacional con Gemini
5. **Trading Agent** — Backend Python: análisis cuantitativo + ejecución

---

## CI/CD (GitHub Actions)

**Frontend Job (`build`):**
1. Lint (ESLint max-warnings 0)
2. Type check (tsc --noEmit)
3. Build (Next.js)
4. SSRF security tests
5. Integration tests (auth guards)

**Backend Job (`backend-tests`):**
1. Python 3.12 setup
2. pytest (56 unit tests)

---

## Variables de Entorno Críticas

```
GOOGLE_AI_API_KEY              # Gemini API
NEXT_PUBLIC_SUPABASE_URL       # Supabase
NEXT_PUBLIC_SUPABASE_ANON_KEY  # Anon key
SUPABASE_SERVICE_ROLE_KEY      # Server-side
TELEGRAM_BOT_TOKEN             # Notificaciones
BINANCE_TESTNET_API_KEY        # Exchange
BINANCE_TESTNET_SECRET         # Exchange
OPERATOR_API_KEY               # Auth operadores
BACKEND_SECRET                 # Next.js ↔ Python
TRADING_ENABLED                # Kill switch (default: false)
```

---

## STACKOS Integration

### Quality Gates (para /loop y /deploy)

| Gate | Comando |
|------|---------|
| **Typecheck** | `pnpm typecheck` |
| **Lint** | `pnpm lint` |
| **Tests Frontend** | `npx playwright test` |
| **Tests Backend** | `cd backend && pytest tests/ -q` |
| **Build** | `pnpm build` |

### Skills Disponibles

| Skill | Propósito |
|-------|-----------|
| `/deploy` | Deploy adaptativo — analiza proyecto, pregunta si hay duda, verifica post-deploy |
| `/QA` | Testing: accesibilidad + responsive (4 viewports) + performance + SEO |
| `/wrap-up` | Cierra sesión → registra lecciones en CONOCIMIENTO-NAHUEL |
| `/loop` | Loop autónomo (Ralph method) — plan → implementar → quality gates → commit |

### Knowledge Hub

- **Repo**: `D:/OneDrive/GitHub/CONOCIMIENTO-NAHUEL`
- Al descubrir patterns reutilizables → persistir en knowledge hub
- Al terminar sesión → `/wrap-up` para registrar lecciones
- Evaluaciones Tech Radar → `content/evaluations/`
- Standards de código → `standards/`

### Codebase Patterns (para agentes)

- Hybrid stack: Frontend (Vercel) + Backend (Docker VPS)
- Trading delegado a Python si `PYTHON_BACKEND_URL` configurado
- Fallback a Vercel Cron (cada 5 min) si backend no disponible
- SSRF protection en API routes
- Auth middleware con Supabase
- Kill switch: `TRADING_ENABLED=false` por defecto
