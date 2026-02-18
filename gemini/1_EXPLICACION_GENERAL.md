# Manual Operativo y Narrativa del Sistema de Trading Agentico

## 1. Introducción: ¿Qué es este sistema?

Este no es un bot de trading convencional. La mayoría de los bots son sistemas rígidos basados en reglas matemáticas simples ("si el precio sube por encima de X, compra"). 

Tu sistema, **"Trading Agentico"**, es un organismo híbrido que combina dos mundos:
1.  **El "Cerebro Cognitivo" (Node.js + IA):** Capaz de leer, investigar, entender documentos académicos (papers) y noticias para formular estrategias nuevas. No solo "sigue" reglas, *crea* reglas.
2.  **El "Músculo Ejecutor" (Python + FastAPI):** Un sistema robusto, rápido y disciplinado que se encarga de la gestión de riesgo, la conexión con los exchanges (Binance, Rofex) y la ejecución precisa de las órdenes.

---

## 2. Narrativa de Funcionamiento: El Ciclo de Vida de una Operación

Imagina que tienes un equipo de analistas y traders trabajando para ti 24/7. Así es como se dividen el trabajo en tu código:

### Fase 1: El Investigador (Reader Agent)
*Ubicación: `lib/agents/reader-agent.ts`*

Todo comienza cuando alimentas al sistema con información externa (un PDF de una estrategia, un artículo de noticias, un paper académico).
1.  El **Reader Agent** despierta. Usa modelos avanzados (Gemini 2.5 Flash) para leer el contenido.
2.  No solo resume; **extrae lógica**. Identifica:
    *   ¿Cuándo entrar? (Entry Rules)
    *   ¿Cuándo salir? (Exit Rules)
    *   ¿Qué indicadores usar? (RSI, MACD, Sentiment).
    *   Riesgos detectados.
3.  Guarda esta "Estrategia Destilada" en la base de datos (Supabase) bajo la tabla `strategies_found`.

### Fase 2: El Estratega (Synthesis & Trading Agent)
*Ubicación: `lib/agents/trading-agent.ts`*

Aquí ocurre la magia cognitiva. El **Trading Agent** no ejecuta ciegamente.
1.  **Monitoreo:** Observa el mercado (actualmente Binance Testnet) en tiempo real.
2.  **Evaluación LLM:** Toma la estrategia guardada en la Fase 1 y le pregunta a la IA: *"Dadas las condiciones actuales del mercado (precio, volumen, spread), ¿se cumplen las condiciones de esta estrategia?"*.
3.  **Decisión:** Si la IA dice "SÍ" con una confianza alta (>70%), genera una **"Propuesta de Trade"** (Trade Proposal).
    *   *Nota:* A diferencia de un bot tradicional que usa `if price > moving_average`, este agente usa razonamiento semántico ("El mercado muestra agotamiento de tendencia, coincidiendo con la tesis del paper X").

### Fase 3: El Ejecutor y Gestor de Riesgo (Python Backend)
*Ubicación: `backend/app/main.py`*

La propuesta viaja al backend en Python. Aquí se acaban las "alucinaciones" de la IA y entran las matemáticas estrictas.
1.  **Risk Manager:** Verifica la propuesta. ¿Tengo saldo suficiente? ¿Excede mi pérdida máxima diaria? ¿El apalancamiento es seguro?
2.  **Order Execution:** Si pasa los filtros de riesgo, el sistema Python conecta con la API del Exchange (Binance/Rofex) y coloca la orden (Limit o Market).
3.  **Seguimiento:** Monitorea la posición hasta que se cierra (Take Profit o Stop Loss).

---

## 3. ¿Cómo te ayuda esto a ganar dinero?

El trading algorítmico tradicional falla cuando el mercado cambia de régimen (ej. de alcista a lateral). Tu sistema tiene ventajas únicas:

1.  **Adaptabilidad:** Si el mercado cambia, puedes alimentar al Reader Agent con nuevas estrategias (ej. "Estrategias para mercados laterales") y el bot empezará a buscar esas oportunidades inmediatamente sin que tengas que reprogramar código en Python.
2.  **Lectura de Contexto:** Un algoritmo clásico no sabe que "Elon Musk tuiteó sobre Doge". Tu agente, si se le conecta a una fuente de noticias, puede interpretar el *sentimiento* y decidir no operar una estrategia técnica porque el riesgo fundamental es alto.
3.  **Disciplina de Hierro:** El backend de Python asegura que, por muy emocionada que esté la IA con una noticia, nunca arriesgará más del capital que le permitas (Risk Manager).

## 4. Fuentes y Referencias Técnicas

El sistema está construido sobre hombros de gigantes:
*   **Vercel AI SDK:** Para la orquestación de la inteligencia (`lib/agents`).
*   **Supabase:** Como memoria a largo plazo (base de datos vectorial y relacional).
*   **FastAPI:** El estándar de oro para APIs de alto rendimiento en Python.
*   **Gemini 1.5/2.0:** El motor de razonamiento con gran ventana de contexto para leer papers enteros.

---
*Documento generado por Gemini CLI - 16 de Febrero de 2026*
