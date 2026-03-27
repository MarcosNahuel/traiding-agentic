# 🚨 Quick Fix Guide - Production Error

## ⚡ TL;DR - La Solución en 2 Pasos

**Problema:** API endpoints retornan 500 porque el `SUPABASE_SERVICE_ROLE_KEY` en Vercel está corrupto.

**Solución:** Copiar el token correcto desde Supabase y actualizarlo en Vercel.

---

## 📋 Step-by-Step Fix (5 minutos)

### Paso 1: Obtener el Token Correcto de Supabase

1. Ir a: https://app.supabase.com/project/zaqpiuwacinvebfttygm/settings/api
2. Buscar la sección **"Project API keys"**
3. Copiar el **`service_role`** key (NO el anon key)
   - El token es MUY LARGO (más de 200 caracteres)
   - Empieza con `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.`
   - Tiene formato: `xxxxx.yyyyy.zzzzz` (3 partes separadas por puntos)

**⚠️ IMPORTANTE:** Asegúrate de copiar el token COMPLETO. Si está truncado, no funcionará.

### Paso 2: Actualizar en Vercel

1. Ir a: https://vercel.com/marcosnahuel/traiding-agentic/settings/environment-variables
2. Buscar `SUPABASE_SERVICE_ROLE_KEY`
3. Hacer click en **"Edit"**
4. Pegar el token completo que copiaste de Supabase
5. Guardar los cambios
6. **Redeploy:** Click en "Deployments" → Menú del último deployment → "Redeploy"

---

## ✅ Verificar que Funcionó

Después del redeploy, abrir estos URLs:

### 1. Test de Conexión Supabase
```
https://traiding-agentic.vercel.app/api/diagnostic/supabase
```

**✅ Debe mostrar:**
```json
{
  "status": "ok",
  "steps": [
    {"step": "check_env_vars", "status": "success"},
    {"step": "create_client", "status": "success"},
    {"step": "query_sources", "status": "success"},
    {"step": "query_strategies", "status": "success"}
  ]
}
```

### 2. Test de JWT Token
```
https://traiding-agentic.vercel.app/api/diagnostic/jwt
```

**✅ Debe mostrar:**
```json
{
  "status": "ok",
  "comparison": {
    "urlRef": "zaqpiuwacinvebfttygm",
    "jwtRef": "zaqpiuwacinvebfttygm",
    "match": true
  },
  "jwt": {
    "role": "service_role",
    "expired": false
  }
}
```

### 3. Test de API Sources
```
https://traiding-agentic.vercel.app/api/sources
```

**✅ Debe mostrar:**
```json
{
  "sources": [],
  "total": 0,
  "limit": 50,
  "offset": 0
}
```

---

## 🎯 ¿Cómo Saber si Está Todo OK?

Si los 3 endpoints de arriba responden correctamente, **la aplicación está lista para usarse**.

Podrás:
- ✅ Agregar papers (/api/sources POST)
- ✅ Procesar con los agentes AI
- ✅ Generar guías de trading
- ✅ Ver logs de actividad

---

## 🐛 Si Sigue Sin Funcionar

### Problema: JWT token sigue inválido

**Posibles causas:**
1. Token truncado al copiar (verifica que tenga 3 partes: `xxxx.yyyy.zzzz`)
2. Espacios extra al inicio o final
3. Token de otro proyecto de Supabase

**Solución:** Volver a copiar el token con mucho cuidado, verificando que esté completo.

### Problema: "Invalid API key" persiste

**Posibles causas:**
1. El proyecto de Supabase cambió su configuración
2. El service role key fue regenerado en Supabase
3. RLS (Row Level Security) está bloqueando el acceso

**Solución:**
1. Ir a Supabase Dashboard → Settings → API
2. Si el service_role key cambió, regenerarlo y copiarlo nuevamente
3. Verificar que las tablas tengan RLS configurado correctamente

---

## 📞 Debugging Avanzado

Si necesitas más detalles técnicos, consulta:
- **Reporte completo:** `docs/PRODUCTION-TEST-REPORT.md`
- **Logs en Vercel:** https://vercel.com/marcosnahuel/traiding-agentic/logs

---

## 🎉 Una Vez Arreglado

Después de confirmar que todo funciona:

1. ✅ Probar agregar un paper de prueba
2. ✅ Verificar que los agentes procesen correctamente
3. ✅ Revisar que las guías se generen

**Próximos pasos de desarrollo:**
- Crear las páginas frontend faltantes (/sources, /strategies, /guides, /chat, /logs)
- Agregar autenticación
- Implementar monitoreo de errores

---

**Tiempo estimado para el fix:** 5 minutos
**Complejidad:** Muy baja (solo actualizar 1 variable)
**Impacto:** Desbloquea toda la funcionalidad de la app
