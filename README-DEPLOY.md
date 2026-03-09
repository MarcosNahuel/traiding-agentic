# Deploy Guide

## Frontend — Vercel

El frontend se despliega automáticamente en Vercel al hacer push a `master`.

### Variables de entorno requeridas en Vercel

Configurar en el dashboard de Vercel (Settings → Environment Variables):

| Variable | Descripción |
|---|---|
| `GOOGLE_AI_API_KEY` | API key de Gemini |
| `NEXT_PUBLIC_SUPABASE_URL` | URL pública de Supabase |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Anon key de Supabase |
| `SUPABASE_SERVICE_ROLE_KEY` | Service role key |
| `TELEGRAM_BOT_TOKEN` | Token del bot de Telegram |
| `TELEGRAM_CHAT_ID` | Chat ID destino |
| `BINANCE_TESTNET_API_KEY` | API key de Binance Testnet |
| `BINANCE_TESTNET_SECRET` | Secret de Binance Testnet |
| `OPERATOR_API_KEY` | Auth para rutas operativas |
| `BACKEND_SECRET` | Secreto compartido con el backend Python |
| `PYTHON_BACKEND_URL` | URL del backend Python en VPS |
| `TRADING_ENABLED` | `true` para activar trading (kill switch) |
| `NEXT_PUBLIC_APP_URL` | URL pública de Vercel (ej: `https://traiding-agentic.vercel.app`) |

### Deploy manual

```bash
vercel deploy --prod
```

## Backend Python — VPS con Docker

### Requisitos
- Docker y Docker Compose instalados
- Puerto 8000 abierto

### Deploy

```bash
# Clonar repo en el VPS
git clone https://github.com/MarcosNahuel/traiding-agentic.git
cd traiding-agentic

# Crear archivo .env con las variables del backend
cp .env.example .env
# Editar .env con los valores reales

# Build y arranque
cd backend
docker build -t trading-backend .
docker run -d \
  --name trading-backend \
  --restart unless-stopped \
  -p 8000:8000 \
  --env-file ../.env \
  trading-backend
```

### Verificar que está corriendo

```bash
curl http://localhost:8000/health
```

### Variables mínimas para el backend Python

```env
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
BINANCE_TESTNET_API_KEY=
BINANCE_TESTNET_SECRET=
BINANCE_ENV=spot_testnet
BACKEND_SECRET=           # mismo valor que en Vercel
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
TRADING_ENABLED=false     # cambiar a true cuando esté listo
```

## Telegram Webhook

Registrar el webhook de Telegram apuntando al frontend de Vercel:

```bash
curl "https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://traiding-agentic.vercel.app/api/telegram/webhook&secret_token=<TELEGRAM_WEBHOOK_SECRET>"
```

## Verificación post-deploy

```bash
# Salud del sistema
curl https://traiding-agentic.vercel.app/api/health

# Salud del backend (requiere OPERATOR_API_KEY)
curl -H "X-Operator-Key: <OPERATOR_API_KEY>" https://traiding-agentic.vercel.app/api/pipeline/status
```
