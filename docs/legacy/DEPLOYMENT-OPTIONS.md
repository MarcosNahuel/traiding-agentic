# 🚀 Opciones de Deployment

Tenés **2 opciones** para deployar tu trading app:

## 📊 Comparación Rápida

| Aspecto | **Opción A: VPS Full** | **Opción B: Vercel + Proxy** |
|---------|------------------------|------------------------------|
| **Binance API** | ✅ Acceso directo | ✅ Vía proxy |
| **Complejidad** | ⭐⭐ Media | ⭐⭐⭐ Alta |
| **Costo** | $5-15/mes VPS | $0-20/mes Vercel + $5/mes VPS |
| **Performance** | ⚡⚡⚡ Mejor | ⚡⚡ Buena |
| **Mantenimiento** | 🔧 Más control | 🔧 Menos control |
| **Auto-deploy** | ✅ Con EasyPanel | ✅ Nativo |
| **Latency Binance** | 🚀 Directa (50-100ms) | 🐌 Proxy (150-300ms) |

---

## ✅ **Opción A: VPS Full (RECOMENDADA)**

Deployá toda la app en tu VPS de Brasil. **Más simple y mejor performance.**

### Ventajas
- ✅ Acceso directo a Binance (sin proxy)
- ✅ Menor latencia en trades
- ✅ Un solo servidor
- ✅ Más fácil de debuggear
- ✅ EasyPanel maneja todo (SSL, logs, monitoring)

### Deployment

1. **Ya tenés los archivos necesarios:**
   - `Dockerfile` ✅
   - `docker-compose.yml` ✅
   - `next.config.ts` (con `output: "standalone"`) ✅

2. **Seguí la guía:** [DEPLOY-EASYPANEL-VPS.md](./DEPLOY-EASYPANEL-VPS.md)

3. **Variables de entorno en EasyPanel:**
```env
# Core
GOOGLE_AI_API_KEY=tu_key
NEXT_PUBLIC_SUPABASE_URL=tu_url
SUPABASE_SERVICE_ROLE_KEY=tu_key

# Telegram
TELEGRAM_BOT_TOKEN=tu_token
TELEGRAM_CHAT_ID=tu_id

# App
NEXT_PUBLIC_APP_URL=https://trading.tudominio.com

# Binance Testnet
BINANCE_TESTNET_API_KEY=tu_key
BINANCE_TESTNET_SECRET=tu_secret
BINANCE_ENV=spot_testnet

# Node
NODE_ENV=production

# ⚠️ NO necesitás BINANCE_PROXY_* (acceso directo)
```

4. **Deploy en EasyPanel:**
   - Source: GitHub `MarcosNahuel/traiding-agentic`
   - Build: Dockerfile
   - Port: 3000
   - Domain: `trading.tudominio.com`
   - Deploy! ⏱️ ~3-5 min

5. **Verificar:**
```bash
curl https://trading.tudominio.com/api/health
curl https://trading.tudominio.com/api/binance/test
```

✅ **Listo! Todo funciona desde Brasil.**

---

## 🔄 **Opción B: Vercel + Proxy**

Deployá el frontend en Vercel y usá un proxy en VPS para Binance API.

### Ventajas
- ✅ Frontend en edge network (rápido globalmente)
- ✅ Auto-deploy de Vercel (excelente DX)
- ✅ Rollbacks 1-click
- ✅ Analytics de Vercel

### Desventajas
- ❌ Mayor latencia en trades (proxy hop)
- ❌ Dos servicios que mantener
- ❌ Más complejo de debuggear
- ❌ Punto de falla adicional (proxy)

### Deployment

#### Paso 1: Deploy Proxy en VPS

1. **Crear repo en GitHub:**
   - Nombre: `binance-proxy`
   - Private ✅
   - NO inicializar con README

2. **Push el proxy:**
```bash
cd D:\OneDrive\GitHub\binance-proxy
git remote add origin https://github.com/MarcosNahuel/binance-proxy.git
git branch -M master
git push -u origin master
```

3. **Deploy en EasyPanel:**
   - Source: GitHub `MarcosNahuel/binance-proxy`
   - Build: Dockerfile
   - Port: 3001
   - Domain: `binance-proxy.tudominio.com`

4. **Variables de entorno del proxy:**
```env
# Binance Testnet
BINANCE_TESTNET_API_KEY=tu_key
BINANCE_TESTNET_SECRET=tu_secret
BINANCE_ENV=spot_testnet

# Auth
PROXY_AUTH_SECRET=tu_token_secreto_generado  # openssl rand -hex 32

# Optional
PORT=3001
```

5. **Verificar proxy:**
```bash
curl https://binance-proxy.tudominio.com/health

curl -H "Authorization: Bearer TU_TOKEN" \
  https://binance-proxy.tudominio.com/binance/api/v3/time
```

#### Paso 2: Deploy App en Vercel

1. **Conectá tu repo a Vercel:**
   - Import `MarcosNahuel/traiding-agentic`
   - Framework: Next.js
   - Root: ./

2. **Variables de entorno en Vercel:**
```env
# Core
GOOGLE_AI_API_KEY=tu_key
NEXT_PUBLIC_SUPABASE_URL=tu_url
SUPABASE_SERVICE_ROLE_KEY=tu_key

# Telegram
TELEGRAM_BOT_TOKEN=tu_token
TELEGRAM_CHAT_ID=tu_id

# App
NEXT_PUBLIC_APP_URL=https://trading-agentic.vercel.app

# Binance Testnet
BINANCE_TESTNET_API_KEY=tu_key
BINANCE_TESTNET_SECRET=tu_secret
BINANCE_ENV=spot_testnet

# ⚠️ PROXY CONFIG (lo nuevo!)
BINANCE_PROXY_URL=https://binance-proxy.tudominio.com
BINANCE_PROXY_AUTH_SECRET=mismo_token_que_en_proxy

# Node
NODE_ENV=production
```

3. **Deploy:**
   - Vercel auto-deploya en cada push a `master`
   - ⏱️ ~2-3 min

4. **Verificar:**
```bash
# Vercel debería mostrar logs:
# 🔄 Binance Proxy Mode: Enabled
# → Proxy URL: https://binance-proxy.tudominio.com

curl https://trading-agentic.vercel.app/api/health
curl https://trading-agentic.vercel.app/api/binance/test
```

---

## 🎯 ¿Cuál elegir?

### Elegí **Opción A (VPS Full)** si:
- ✅ Querés la **menor latencia** posible en trades
- ✅ Preferís **simplicidad** (un solo servidor)
- ✅ No te importa perder auto-deploy de Vercel
- ✅ Querés **máximo control** del entorno

### Elegí **Opción B (Vercel + Proxy)** si:
- ✅ Querés el **mejor DX** (auto-deploy, rollbacks, analytics)
- ✅ Necesitás **frontend ultra-rápido** globalmente
- ✅ No hacés trades de alta frecuencia (latencia aceptable)
- ✅ Preferís separar frontend de backend

---

## 💡 Mi Recomendación

**Para trading bot:** → **Opción A (VPS Full)**

**Razones:**
1. Latencia crítica en trading (cada ms cuenta)
2. Menos complejidad = menos puntos de falla
3. Más fácil debuggear (todo en un lugar)
4. EasyPanel ya da auto-deploy + SSL + monitoring
5. Costo similar o menor

**Bonus:** Si después querés frontend rápido globalmente, podés poner Cloudflare CDN delante del VPS.

---

## 📝 Checklist de Deployment

### Opción A (VPS Full)
- [ ] Dockerfile y docker-compose.yml en repo ✅
- [ ] Variables de entorno configuradas en EasyPanel
- [ ] Dominio apuntando a VPS
- [ ] SSL configurado (auto con EasyPanel)
- [ ] Health check passing
- [ ] Binance API funcionando (sin proxy)
- [ ] Logs monitoreados
- [ ] Backups configurados

### Opción B (Vercel + Proxy)
- [ ] Proxy deployado en VPS
- [ ] Proxy health check passing
- [ ] Token secreto generado y guardado
- [ ] App deployada en Vercel
- [ ] Variables proxy configuradas en Vercel
- [ ] Logs muestran "Proxy Mode: Enabled"
- [ ] Binance API funcionando vía proxy
- [ ] Latency aceptable (<500ms)

---

## 🐛 Troubleshooting

### Problema: Binance sigue bloqueado en Vercel
```bash
# Verificar que las variables estén configuradas:
vercel env ls

# Debe mostrar:
# BINANCE_PROXY_URL
# BINANCE_PROXY_AUTH_SECRET

# Verificar logs de deployment:
vercel logs
# Debe mostrar: "🔄 Binance Proxy Mode: Enabled"
```

### Problema: Proxy retorna 401 Unauthorized
```bash
# Verificar que el token sea el mismo en ambos lados:
# 1. En proxy VPS: PROXY_AUTH_SECRET=xxx
# 2. En Vercel: BINANCE_PROXY_AUTH_SECRET=xxx

# Debe ser EXACTAMENTE el mismo token
```

### Problema: Proxy timeout
```bash
# Verificar que el proxy esté corriendo:
curl https://binance-proxy.tudominio.com/health

# Si falla, revisar logs en EasyPanel:
# Dashboard → binance-proxy → Logs
```

### Problema: Alta latencia en trades
```bash
# Medir latencia:
time curl -H "Authorization: Bearer TOKEN" \
  https://binance-proxy.tudominio.com/binance/api/v3/time

# Si >500ms, considerá migrar a Opción A (VPS Full)
```

---

## 🚀 Próximos Pasos

1. **Elegí tu opción** (A o B)
2. **Seguí la guía** correspondiente
3. **Deploy** 🎉
4. **Verificá** que todo funcione
5. **Ejecutá tu primer trade** de prueba
6. **Monitoreá logs** por 24h
7. **A tradear!** 💰

---

¿Dudas? Check:
- [DEPLOY-EASYPANEL-VPS.md](./DEPLOY-EASYPANEL-VPS.md) - Guía detallada VPS
- [binance-proxy README](https://github.com/MarcosNahuel/binance-proxy) - Docs del proxy
- [Vercel Docs](https://vercel.com/docs) - Vercel deployment

**¿Listo para deployar?** 🚀
