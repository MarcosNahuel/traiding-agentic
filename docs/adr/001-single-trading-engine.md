# ADR 001: Python FastAPI como único motor de ejecución de trades

**Fecha:** 2026-03-08
**Estado:** Aceptado
**Autores:** Equipo de desarrollo

---

## Contexto

El sistema tiene dos componentes que históricamente podían ejecutar trades de forma independiente:

1. **Next.js (Vercel):** loop de trading via Vercel Cron (`/api/cron/trading-loop`, cada 5 min). Evaluaba estrategias con `runTradingLoop()` y ejecutaba propuestas con `executeApprovedProposals()`.

2. **Python FastAPI (VPS):** loop propio iniciado automáticamente al arrancar (`backend/app/main.py`). Ciclo de 60s: señales cuantitativas → validación de riesgo → ejecución → actualización de portfolio → reconciliación.

Cuando `PYTHON_BACKEND_URL` estaba configurado, ambos loops corrían en paralelo sin coordinación. Esto producía:

- **Propuestas duplicadas:** el mismo signal podía generar dos propuestas, una por cada motor.
- **Ejecuciones repetidas:** ambos ejecutores podían actuar sobre la misma propuesta.
- **Reconciliaciones cruzadas:** el estado del portfolio divergía entre los dos planos de control.
- **Safety rules inconsistentes:** los límites de riesgo estaban definidos de forma diferente en TypeScript (`lib/trading/risk-manager.ts`) y Python (`backend/app/services/risk_manager.py`).
- **Contratos de entorno diferentes:** Next.js usaba `BINANCE_ENV=spot_testnet` como string; Python tenía `binance_env = "testnet"` como default.

---

## Decisión

**Python FastAPI es la única autoridad de ejecución de trades.**

Cuando `PYTHON_BACKEND_URL` está configurado, el loop de Next.js delega completamente al backend Python y no genera señales, propuestas ni ejecuciones propias.

---

## Implementación

### Next.js (`app/api/cron/trading-loop/route.ts`)

```typescript
import { isPythonBackendEnabled } from "@/lib/trading/python-backend";

if (isPythonBackendEnabled()) {
  return NextResponse.json({
    success: true,
    skipped: true,
    reason: "Python backend is active — trading loop delegated to FastAPI (avoids split-brain)",
    timestamp: new Date().toISOString(),
  });
}
```

El cron de Vercel sigue ejecutándose cada 5 minutos pero retorna inmediatamente sin operar si el backend Python está activo.

### Python FastAPI (`backend/app/main.py`)

El loop Python sigue siendo la única fuente de:
- Generación de señales cuantitativas (`signal_generator.py`)
- Validación de riesgo (`risk_manager.py`)
- Ejecución de órdenes en Binance (`executor.py`)
- Actualización de portfolio y reconciliación (`trading_loop.py`)

---

## Consecuencias

### Positivas

- **Estado consistente:** una sola fuente de verdad para propuestas, ejecuciones y portfolio.
- **Safety rules unificadas:** los límites de riesgo se definen y aplican en un único lugar.
- **Trazabilidad:** todo el flujo de una señal hasta una orden pasa por el mismo runtime.
- **Degradación controlada:** si el backend Python no está disponible (`PYTHON_BACKEND_URL` no configurado), Next.js activa su propio loop como fallback.

### Negativas / Trade-offs

- **Kill switch independiente:** `TRADING_ENABLED !== "true"` desactiva el loop de Next.js con precedencia sobre la delegación al backend Python. Ambos guards son independientes (`route.ts:27-47`).
- **Dependencia del VPS:** si el backend Python cae, no hay trading (hasta que se detecte y el operador intervenga o se limpie `PYTHON_BACKEND_URL`).
- **Latencia de cron:** el cron de Vercel corre cada 5 min pero el loop Python es autónomo (60s); el cron es efectivamente un health check cuando el backend está activo.
- **Mantenimiento dual:** el ejecutor de Next.js (`lib/trading/executor.ts`) sigue existiendo para el modo fallback, requiriendo mantenimiento paralelo.

---

## Alternativas consideradas

### Alternativa A: Next.js como único motor

Descartada. Next.js en Vercel tiene límites de duración de función (60s para cron), no puede mantener estado en memoria entre invocaciones, y el motor cuantitativo Python requiere librerías NumPy/SciPy que no son viables en edge/serverless.

### Alternativa B: Lock distribuido con ambos motores

Descartada por complejidad. Requeriría un sistema de leader election (Redis, Supabase advisory locks) con lógica de failover y TTL. El beneficio (redundancia activa) no justifica la complejidad en el estado actual del sistema.

### Alternativa C: Eliminar el loop de Next.js completamente

Viable a largo plazo, pero descartada por ahora para preservar el modo fallback (cuando no hay VPS disponible). El costo de mantener el código de fallback es bajo comparado con la flexibilidad operativa.

---

## Estado actual

- Python FastAPI es el motor activo en producción (VPS con `PYTHON_BACKEND_URL` configurado).
- El fallback de Next.js permanece funcional pero inactivo mientras el backend Python esté disponible.
- Variable de control: `PYTHON_BACKEND_URL` en el entorno de Vercel.

---

## Referencias

- `app/api/cron/trading-loop/route.ts` — implementación del skip
- `lib/trading/python-backend.ts` — `isPythonBackendEnabled()`
- `backend/app/main.py` — arranque del loop Python
- `backend/app/services/trading_loop.py` — ciclo de 60s
- Commit: `ec84dab` (implementación del skip en cron route)
