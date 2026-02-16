# 🚀 Deploy en VPS Hostinger (Brasil) con EasyPanel

## ✅ ¡PERFECTO! Brasil NO está bloqueado por Binance

Tu VPS en Brasil debería funcionar perfectamente con Binance Testnet.

---

## 📋 GUÍA PASO A PASO

### **Paso 1: Preparar el Repositorio**

```bash
# 1. Commit los cambios (Dockerfile y next.config.ts)
git add Dockerfile next.config.ts
git commit -m "Add Docker support for VPS deployment"
git push origin master
```

---

### **Paso 2: Configurar en EasyPanel**

#### A. Crear Nueva Aplicación

1. Entrá a tu EasyPanel: `https://tu-vps-ip:3000`
2. Click en **"+ Create"** → **"App"**
3. Seleccioná **"Deploy from GitHub"**
4. Conectá tu repo: `github.com/MarcosNahuel/traiding-agentic`
5. Branch: `master`

#### B. Configuración de Build

```yaml
# En EasyPanel, configurá:
Build Method: Dockerfile
Dockerfile Path: ./Dockerfile
Port: 3000
```

#### C. Variables de Entorno

En la sección **Environment Variables**, agregá:

```env
# Core - AI
GOOGLE_AI_API_KEY=AIzaSyCXAoLtp-Wpy6rM1aGDsGwY6GHhmsxbS2k

# Supabase
NEXT_PUBLIC_SUPABASE_URL=https://zaqpiuwacinvebfttygm.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InphcXBpdXdhY2ludmViZnR0eWdtIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc0NjM5NzMwNiwiZXhwIjoyMDYxOTczMzA2fQ.NcmHTXSqJ_OXjTYSg0xGN7GYy3N9i_hGqhJP5bGqBY0

# Telegram
TELEGRAM_BOT_TOKEN=8540887019:AAGrshOGOVLsjgpsekKx7xV7eO5TzHsIVTg
TELEGRAM_CHAT_ID=

# App
NEXT_PUBLIC_APP_URL=https://tu-dominio.com

# Binance Testnet
BINANCE_TESTNET_API_KEY=xq4BTyC9s3j55PsIxSbx4bZ4sTNawrS5kLeCOeRQYUzop3IW7Nz0CB2aCo8h6KuG
BINANCE_TESTNET_SECRET=0JEekLagtstI3G24YUGtNCu1Jf2ytJfLTdRZPiPBg8iIp2BsqhwNxYVXBGNh2BMS
BINANCE_ENV=spot_testnet

# Node
NODE_ENV=production
```

#### D. Dominio

1. En EasyPanel, ve a **"Domains"**
2. Click **"Add Domain"**
3. Opciones:
   - **Subdominio de EasyPanel:** `trading.tu-vps.easypanel.host` (gratis)
   - **Dominio propio:** `trading.tudominio.com`

Para dominio propio:
```dns
# Agregar en tu DNS:
Type: A
Name: trading
Value: IP_DE_TU_VPS
TTL: 3600
```

4. EasyPanel auto-configura SSL con Let's Encrypt ✅

---

### **Paso 3: Deploy**

1. Click en **"Deploy"**
2. EasyPanel va a:
   - Clonar el repo
   - Build con Docker
   - Levantar el contenedor
   - Configurar HTTPS automáticamente

⏱️ **Tiempo estimado:** 3-5 minutos

---

### **Paso 4: Verificar**

```bash
# Test 1: Health check
curl https://trading.tudominio.com/api/health

# Test 2: Binance connection
curl https://trading.tudominio.com/api/binance/test

# Test 3: Portfolio
curl https://trading.tudominio.com/api/portfolio
```

✅ **Si funciona:** Binance NO está bloqueado en Brasil!

---

## 🔧 Troubleshooting

### Problema 1: Build falla

```bash
# Ver logs en EasyPanel:
# Dashboard → Tu App → Logs → Build Logs
```

**Solución:** Verificar que el Dockerfile esté en la raíz del repo.

### Problema 2: App no levanta

```bash
# Ver logs:
# Dashboard → Tu App → Logs → Application Logs
```

**Solución común:** Variables de entorno faltantes.

### Problema 3: Binance sigue bloqueado

```bash
# Verificar la IP del VPS
curl -s https://ipinfo.io/$(curl -s https://ifconfig.me) | jq .

# Debe mostrar:
# "country": "BR"  ✅
```

Si muestra otro país, contactá a Hostinger.

---

## 📊 Comparación: Vercel vs VPS

| Feature | Vercel | VPS (EasyPanel) |
|---------|--------|-----------------|
| **Binance API** | ❌ Bloqueado | ✅ Funciona |
| **Costo** | $20/mes | $5-15/mes |
| **Control** | Limitado | Total |
| **Auto-Deploy** | ✅ Si | ✅ Si (GitHub webhook) |
| **SSL/HTTPS** | ✅ Auto | ✅ Auto (Let's Encrypt) |
| **Rollback** | ✅ 1-click | Manual |
| **Logs** | ✅ Excelente | ✅ Bueno |
| **Latency** | Baja | Media |

---

## 🎯 Configuración Avanzada

### Auto-Deploy desde GitHub

En EasyPanel:
1. Settings → GitHub Webhook
2. Cada push a `master` → auto-deploy

### Cron Jobs

EasyPanel soporta cron jobs nativamente:

```yaml
# En EasyPanel → Cron Jobs
Schedule: */5 * * * *
Command: curl http://localhost:3000/api/cron/trading-loop
```

### Backups

```bash
# EasyPanel → Backups → Schedule
Frequency: Daily
Retention: 7 days
Includes: Database + App
```

---

## ⚡ Performance Tips

### 1. CDN (Opcional)

```bash
# Agregar Cloudflare delante:
# 1. Cambiar nameservers en tu dominio
# 2. Apuntar a tu VPS
# 3. Cloudflare cachea assets estáticos
```

### 2. Monitoring

```bash
# En EasyPanel → Monitoring
# Auto-restart si la app se cae
# Alertas por email/Discord/Telegram
```

### 3. Resources

```yaml
# En EasyPanel → Resources
CPU: 1 core (suficiente)
RAM: 1GB mínimo, 2GB recomendado
Disk: 10GB
```

---

## 🚀 Next Steps

Una vez deployado:

1. ✅ Verificar que Binance funcione
2. ✅ Crear tu primer trade de prueba
3. ✅ Configurar Telegram alerts
4. ✅ Activar cron job para trading automático
5. ✅ Monitorear logs

---

## ❓ FAQ

**P: ¿Puedo usar Vercel para el frontend y VPS solo para las APIs?**
R: Sí, pero más complejo. Mejor todo en VPS.

**P: ¿Cuánto RAM necesito?**
R: Mínimo 1GB, recomendado 2GB para Next.js + Node.

**P: ¿Qué pasa si mi VPS se cae?**
R: EasyPanel auto-reinicia. También podés configurar failover.

**P: ¿Puedo usar Docker Compose en lugar de EasyPanel?**
R: Sí, tengo un docker-compose.yml si preferís.

---

## 📝 Checklist Final

Antes de ir a producción:

- [ ] SSL/HTTPS configurado (Let's Encrypt)
- [ ] Variables de entorno configuradas
- [ ] Binance API funcionando
- [ ] Dominio apuntando correctamente
- [ ] Monitoring activado
- [ ] Backups configurados
- [ ] Logs funcionando
- [ ] Cron job testeado

---

**¿Listo para deployar?** 🚀

Seguí los pasos y en 10 minutos tenés todo funcionando en tu VPS!
