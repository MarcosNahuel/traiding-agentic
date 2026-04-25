# Variables de entorno

Listado de las env vars requeridas para que el sistema funcione. Agrupadas por **dónde** vivir (Vercel = frontend, Dokploy = backend Python).

## Frontend (Vercel)

| Variable | Requerida | Para qué |
|---|:-:|---|
| `NEXT_PUBLIC_SUPABASE_URL` | sí | Endpoint Supabase |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | sí | Auth cliente |
| `SUPABASE_SERVICE_ROLE_KEY` | sí | Server-side escritura |
| `GOOGLE_AI_API_KEY` | sí | Gemini (research + chat) |
| `OPERATOR_API_KEY` | sí | Auth operadores |
| `BACKEND_SECRET` | sí | Next.js ↔ Python backend |
| `STRATEGIST_APPROVAL_TOKEN` | **sí (Fase 0)** | Token para aprobar/rechazar configs LLM. Mismo valor en frontend y backend. Generar: `openssl rand -hex 32`. |
| `CRON_SECRET` | **sí (Fase 0)** | Auth de los cron jobs Vercel (ej. `expire-pending-configs`). Generar: `openssl rand -hex 32`. |
| `TELEGRAM_BOT_TOKEN` | opcional | Notifs |

## Backend Python (Dokploy)

| Variable | Default | Para qué |
|---|---|---|
| `BINANCE_TESTNET_API_KEY` | — | Llave del exchange testnet |
| `BINANCE_TESTNET_SECRET` | — | Secret del exchange testnet |
| `TRADING_ENABLED` | `false` | Kill switch — `false` por default, NO ejecuta órdenes |
| `STRATEGIST_APPROVAL_TOKEN` | — | **Mismo valor que en Vercel.** Backend lo usa para validar callbacks de aprobación. |
| `SUPABASE_URL` | — | DB |
| `SUPABASE_SERVICE_ROLE_KEY` | — | Acceso server-side a DB |
| `TELEGRAM_BOT_TOKEN` | — | Notifs y aprobaciones |

### Feature flags introducidos en Fase 0 (2026-04-25)

| Variable | Default | Para qué |
|---|---|---|
| `LANGGRAPH_DAILY_ENABLED` | `false` | Sigue corriendo el pipeline LangGraph diario (será reemplazado por Strategist Agent en Fase 1). Default false = pipeline apagado. |
| `PARTIAL_EXIT_ENABLED` | `false` | Activa partial exit 50% al 1R + Chandelier sobre runner. **Decisión 2026-04-25: dejar en `false`** hasta tener edge demostrado (ver `docs/knowledge-base/evaluations/2026-04-25-diagnostic-sprint.md`). |
| `PARTIAL_EXIT_FRACTION` | `0.5` | Fracción de la posición que se cierra al 1R. |
| `PARTIAL_EXIT_AT_R` | `1.0` | A cuántos R se toma el partial. |
| `CHANDELIER_K` | `3.0` | Multiplicador ATR del Chandelier exit. V1 (k=2) gana a V2 (k=3) en el A/B 2026-04-25, pero la diferencia no fue significativa. |

## Cómo aplicar los cambios de Fase 0

Antes de pushear `master` a remoto:

```bash
# 1. Generar dos secrets distintos
openssl rand -hex 32   # → STRATEGIST_APPROVAL_TOKEN
openssl rand -hex 32   # → CRON_SECRET

# 2. Setear en Vercel:
#    Dashboard → Project → Settings → Environment Variables
#    - STRATEGIST_APPROVAL_TOKEN = <primer secret>
#    - CRON_SECRET                = <segundo secret>

# 3. Setear en Dokploy:
#    Dashboard → App backend → Environment
#    - STRATEGIST_APPROVAL_TOKEN = <MISMO primer secret que en Vercel>
#    - LANGGRAPH_DAILY_ENABLED   = false
#    - PARTIAL_EXIT_ENABLED      = false
#    - CHANDELIER_K              = 3.0
#    - PARTIAL_EXIT_FRACTION     = 0.5
#    - PARTIAL_EXIT_AT_R         = 1.0

# 4. Redeploy backend (Dokploy) y frontend (Vercel).
```

Sin estas vars, los endpoints `/api/admin/approve-config`, `/api/admin/reject-config`, y `/api/cron/expire-pending-configs` van a fallar con 401/500.

## Validación

Tras el deploy, chequear:
- `curl -X POST $BACKEND_URL/healthz` responde 200.
- Vercel `Functions → Logs` no muestra errores de "missing env var".
- `/api/cron/expire-pending-configs` retorna 401 si se llama sin Bearer (no rompe en 500).
