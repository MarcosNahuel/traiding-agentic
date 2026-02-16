# 🔧 Solución: Binance Proxy para Vercel

## Problema
Binance bloquea requests desde servidores de Vercel por restricciones geográficas.

## Solución: VPS Proxy

### Opción A: Proxy Simple con Node.js

**1. Crear VPS en ubicación permitida**
Proveedores recomendados:
- **DigitalOcean** (Droplet $6/mes) - Singapore, Frankfurt
- **Vultr** ($5/mes) - Tokyo, Amsterdam
- **Hetzner** (€4/mes) - Europa
- **Railway** (free tier o $5/mes)

**2. Código del Proxy**

```typescript
// proxy-server/index.ts
import express from 'express';
import axios from 'axios';
import crypto from 'crypto';

const app = express();
app.use(express.json());

const BINANCE_BASE = 'https://testnet.binance.vision';

// Middleware de autenticación
const AUTH_SECRET = process.env.PROXY_AUTH_SECRET;

function verifyAuth(req: any, res: any, next: any) {
  const token = req.headers.authorization?.replace('Bearer ', '');
  if (token !== AUTH_SECRET) {
    return res.status(401).json({ error: 'Unauthorized' });
  }
  next();
}

// Proxy endpoint
app.all('/binance/*', verifyAuth, async (req, res) => {
  try {
    const path = req.path.replace('/binance', '');
    const url = `${BINANCE_BASE}${path}`;

    // Forward headers y query params
    const response = await axios({
      method: req.method,
      url,
      data: req.body,
      params: req.query,
      headers: {
        'X-MBX-APIKEY': process.env.BINANCE_TESTNET_API_KEY,
      },
    });

    res.json(response.data);
  } catch (error: any) {
    console.error('Proxy error:', error.response?.data || error.message);
    res.status(error.response?.status || 500).json({
      error: error.response?.data || error.message
    });
  }
});

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

const PORT = process.env.PORT || 3001;
app.listen(PORT, () => {
  console.log(`Proxy running on port ${PORT}`);
});
```

**3. Deploy del Proxy**

```bash
# En el VPS
git clone https://github.com/tu-usuario/binance-proxy.git
cd binance-proxy
npm install
npm install -g pm2

# Variables de entorno
cat > .env <<EOF
BINANCE_TESTNET_API_KEY=tu_api_key
BINANCE_TESTNET_SECRET=tu_secret
PROXY_AUTH_SECRET=un_token_secreto_random
PORT=3001
EOF

# Iniciar con PM2 (auto-restart)
pm2 start index.ts --name binance-proxy
pm2 save
pm2 startup
```

**4. Actualizar el código de Next.js**

```typescript
// lib/exchanges/binance-testnet.ts
const USE_PROXY = process.env.NODE_ENV === 'production';
const PROXY_URL = process.env.BINANCE_PROXY_URL; // https://tu-vps.com
const PROXY_AUTH = process.env.BINANCE_PROXY_AUTH_SECRET;

export async function getBinanceAPI(endpoint: string) {
  const url = USE_PROXY
    ? `${PROXY_URL}/binance${endpoint}`
    : `https://testnet.binance.vision${endpoint}`;

  const headers: any = {};

  if (USE_PROXY) {
    headers.Authorization = `Bearer ${PROXY_AUTH}`;
  } else {
    headers['X-MBX-APIKEY'] = process.env.BINANCE_TESTNET_API_KEY;
  }

  const response = await fetch(url, { headers });
  return response.json();
}
```

**5. Variables en Vercel**

```bash
vercel env add BINANCE_PROXY_URL production
# Valor: https://tu-vps-ip:3001

vercel env add BINANCE_PROXY_AUTH_SECRET production
# Valor: el mismo token que pusiste en el VPS

# Redeploy
vercel --prod
```

---

### Opción B: Railway (Más fácil, menos control)

**Railway** es un PaaS que permite desplegar en ubicaciones específicas:

```bash
# 1. Instalar Railway CLI
npm install -g @railway/cli

# 2. Login
railway login

# 3. Crear proyecto del proxy
railway init

# 4. Desplegar
railway up

# 5. Configurar variables
railway variables set BINANCE_TESTNET_API_KEY=xxx
railway variables set PROXY_AUTH_SECRET=xxx

# Railway te da una URL automáticamente
# Ejemplo: https://binance-proxy-production.up.railway.app
```

---

## Opción C: Cloudflare Workers (Avanzado)

Usar Cloudflare Workers como proxy:

```typescript
// cloudflare-worker.ts
export default {
  async fetch(request: Request, env: any): Promise<Response> {
    const url = new URL(request.url);
    const binanceUrl = `https://testnet.binance.vision${url.pathname}${url.search}`;

    // Verificar auth
    const authHeader = request.headers.get('Authorization');
    if (authHeader !== `Bearer ${env.PROXY_SECRET}`) {
      return new Response('Unauthorized', { status: 401 });
    }

    // Proxy request
    const response = await fetch(binanceUrl, {
      method: request.method,
      headers: {
        'X-MBX-APIKEY': env.BINANCE_API_KEY,
      },
    });

    return response;
  }
};
```

Deploy:
```bash
npm install -g wrangler
wrangler init
wrangler publish
```

---

## 📊 Comparación de Soluciones

| Solución | Costo/mes | Complejidad | Latencia | Control |
|----------|-----------|-------------|----------|---------|
| **VPS + Proxy** | $5-10 | Media | Baja | Alto ✅ |
| **Railway** | $5 | Baja | Media | Medio |
| **Cloudflare Workers** | $0-5 | Alta | Muy Baja | Bajo |
| **DigitalOcean Functions** | $0-10 | Media | Baja | Medio |

---

## 🎯 Recomendación Final

**Para tu caso específico:**

1. **Opción más rápida (ahora):** Railway
   - Deploy en 5 minutos
   - Free tier suficiente para testing
   - Cuando escale, $5/mes

2. **Opción más profesional (producción):** VPS
   - DigitalOcean Droplet $6/mes en Singapore
   - Control total
   - Mejor para trading en serio

---

## 🚀 Quick Start (Railway - 5 minutos)

```bash
# 1. Clonar template
git clone https://github.com/MarcosNahuel/binance-proxy.git
cd binance-proxy

# 2. Deploy a Railway
railway init
railway up

# 3. Configurar variables
railway variables set BINANCE_TESTNET_API_KEY=tu_key
railway variables set BINANCE_TESTNET_SECRET=tu_secret
railway variables set PROXY_AUTH_SECRET=$(openssl rand -hex 32)

# 4. Obtener URL
railway domain
# Te da: https://binance-proxy-production.up.railway.app

# 5. Actualizar Vercel
vercel env add BINANCE_PROXY_URL production
# Pegar la URL de Railway

vercel env add BINANCE_PROXY_AUTH_SECRET production
# Pegar el mismo token

# 6. Redeploy
vercel --prod
```

---

## ✅ Testing

```bash
# Probar el proxy
curl https://tu-proxy.railway.app/health

# Probar Binance a través del proxy
curl -H "Authorization: Bearer tu_token" \
  https://tu-proxy.railway.app/binance/api/v3/time
```

---

## 📝 Notas de Seguridad

⚠️ **IMPORTANTE:**
- Nunca expongas las API keys de Binance directamente
- El proxy debe tener autenticación (PROXY_AUTH_SECRET)
- Usa HTTPS siempre
- Rotá el PROXY_AUTH_SECRET regularmente
- Monitorea los logs del proxy

---

**Última actualización:** 16 Feb 2026
**Status:** Listo para implementar
