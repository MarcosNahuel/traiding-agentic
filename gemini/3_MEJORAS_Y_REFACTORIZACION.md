# Plan de Mejoras, Refactorización y Stack Tecnológico

## 1. Análisis del Stack Tecnológico

### Frontend & API (Next.js)
*   **Estado:** ✅ **Excelente**. Estás usando Next.js 16 (la última versión posible a la fecha, muy avanzado), React 19 y Tailwind 4. Esto es "Bleeding Edge".
*   **Observación:** Al estar en versiones tan nuevas, podrías encontrar incompatibilidades menores con librerías antiguas, pero el rendimiento será superior.
*   **Mejora:** Asegurar que se está usando el **App Router** completamente y `Server Actions` para las mutaciones de base de datos en lugar de crear demasiadas rutas de API REST (`app/api/...`), lo cual simplificaría el código.

### Backend (Python)
*   **Estado:** ⚠️ **Básico**. FastAPI es la elección correcta, pero la falta de librerías de ciencia de datos (`pandas`, `numpy`) limita su potencial.
*   **Mejora:** Implementar `Celery` o `Redis Queue` para manejar las tareas pesadas. Actualmente, si el backend tarda mucho procesando una orden, podría bloquear otras peticiones si no es perfectamente asíncrono.

### Base de Datos (Supabase)
*   **Estado:** ✅ **Sólido**. Postgres es ideal.
*   **Mejora:** Habilitar **Row Level Security (RLS)** si la aplicación va a tener múltiples usuarios o si va a estar expuesta a internet, para asegurar que nadie pueda leer las API Keys o estrategias de otros (aunque parece ser de uso personal por ahora).

---

## 2. Sugerencias de Refactorización

### A. Centralización de "Market Data"
Actualmente, tanto Node.js (Agente) como Python (Backend) parecen tener capacidad de consultar precios.
*   **Problema:** Doble gasto de API calls a Binance (pueden banearte por exceso de requests) y posible discrepancia de datos.
*   **Propuesta:** El Backend de Python debe ser la **Única Fuente de Verdad**.
    *   Node.js le pregunta a Python: `GET /api/price?symbol=BTCUSDT`.
    *   Python maneja el cache y el rate limiting con Binance.

### B. Estandarización de Prompts
Los prompts están hardcodeados dentro de las funciones en `trading-agent.ts`.
*   **Mejora:** Mover todos los prompts a `lib/agents/prompts.ts` o incluso a la base de datos. Esto permite "ajustar" la personalidad del trader sin redesplegar el código.

### C. Sistema de "Backtesting Rápido" en el Agente
Antes de proponer un trade real, el agente debería poder ejecutar una simulación rápida.
*   **Refactor:** Agregar una herramienta al agente llamada `simulate_strategy(strategy_id, days=7)` que corra la lógica contra datos históricos de la última semana antes de arriesgar dinero hoy.

---

## 3. Nuevas Features Recomendadas

1.  **Modo "Paper Trading" Transparente:**
    *   Un switch en la UI que cambie todo el sistema a modo simulación, usando dinero ficticio pero datos reales, guardando el PnL (Ganancia/Pérdida) en una tabla separada.

2.  **Notificaciones en Tiempo Real (Telegram/Discord):**
    *   El bot debería enviarte un mensaje a Telegram cuando el "Reader Agent" encuentra una estrategia prometedora o cuando se ejecuta una orden.
    *   *Herramienta:* Crear un bot de Telegram simple e integrarlo en el backend de Python.

3.  **Dashboard de "Salud Mental" del Agente:**
    *   Ver en la UI qué está "pensando" el agente. Mostrar los logs de razonamiento (`reasoning`) del LLM en tiempo real. "¿Por qué no compré BTC hace 10 minutos? -> Porque la volatilidad era muy alta y el paper indica esperar".
