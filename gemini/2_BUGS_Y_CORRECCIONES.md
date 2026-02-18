# Reporte de Auditoría: Bugs y Correcciones Críticas

Este documento detalla errores técnicos encontrados en el código actual que deben ser corregidos para garantizar la estabilidad y rentabilidad del sistema.

## 🔴 Prioridad Alta (Critical)

### 1. Inconsistencia en Dependencias de Python (`backend/requirements.txt`)
**Problema:** El código del backend (`market_data.py`, `strategy.py`) probablemente necesite manipular datos numéricos complejos. Sin embargo, `pandas` y `numpy` no están en `requirements.txt`. Además, si se planea usar análisis técnico clásico, faltan librerías como `pandas-ta` o `talib`.
**Riesgo:** El contenedor de Docker del backend fallará al arrancar o al intentar procesar datos de mercado.
**Solución:**
```text
# Agregar a backend/requirements.txt
pandas>=2.2.0
numpy>=1.26.0
pandas-ta>=0.3.14  # Si se usa análisis técnico
```

### 2. Fragilidad en el Parsing de JSON del Agente (`trading-agent.ts`)
**Problema:**
En `lib/agents/trading-agent.ts`, se usa `generateText` y luego una expresión regular (`text.match(/\{[\s\S]*\}/)`) para extraer el JSON.
```typescript
// CÓDIGO ACTUAL (INSEGURO)
const { text } = await generateText({...});
const jsonMatch = text.match(/\{[\s\S]*\}/);
const result = JSON.parse(jsonMatch[0]);
```
**Riesgo:** Los LLMs a menudo incluyen texto antes o después del JSON, o cometen errores de sintaxis menores que `JSON.parse` no tolera. Esto causará que el bot pierda oportunidades de trade por errores de parsing.
**Solución:** Usar `generateObject` de Vercel AI SDK, que fuerza al modelo a devolver una estructura tipada y valida automáticamente con Zod (como ya se hace en `reader-agent.ts`).

### 3. Hardcoding de Binance Testnet
**Problema:** En `lib/agents/trading-agent.ts` se importan funciones desde `@/lib/exchanges/binance-testnet`.
**Riesgo:** No hay una forma fácil de cambiar a "Producción" (Mainnet) sin reescribir las importaciones. Si depositas dinero real, el bot seguirá mirando precios de prueba o intentando operar en la testnet.
**Solución:** Crear un adaptador `binance-client.ts` que exporte las funciones y decida internamente si usar Testnet o Mainnet basado en una variable de entorno `NEXT_PUBLIC_TRADING_MODE=LIVE`.

## 🟡 Prioridad Media (Warning)

### 4. Desconexión entre Agente y Ejecución
**Problema:** El `trading-agent.ts` envía propuestas a `/api/trades/proposals`. Sin embargo, no hemos verificado que exista un "Cron Job" o un "Listener" en el backend de Python que lea esas propuestas y las ejecute automáticamente.
**Riesgo:** El agente puede generar 100 señales ganadoras, pero si el backend no las "recoge" (polling o webhook), se quedarán en la base de datos como simples registros.
**Acción:** Verificar el servicio `services/strategy.py` en Python para asegurar que consulta la tabla de `proposals` o implementar un endpoint en FastAPI que Next.js llame para forzar la ejecución inmediata.

### 5. Manejo de Errores en LLM
**Problema:** Si la API de Google/Gemini falla (rate limit, downtime), el `trading-agent.ts` simplemente captura el error y retorna `null`.
**Riesgo:** En momentos de alta volatilidad (cuando más se necesita operar), las APIs suelen saturarse. El bot podría quedarse "ciego".
**Solución:** Implementar un mecanismo de "Exponential Backoff" (reintentos con espera progresiva) para las llamadas a la API de IA.

---
*Instrucciones para el Agente de Código: Por favor procesar estas correcciones comenzando por las de Prioridad Alta.*
