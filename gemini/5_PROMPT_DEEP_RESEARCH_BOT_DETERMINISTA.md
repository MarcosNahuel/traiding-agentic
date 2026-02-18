# Deep Research: Fortalecimiento Determinista del Bot Trading-Agentic

Este documento contiene el análisis de debilidades actuales y el prompt diseñado para realizar una investigación profunda sobre cómo blindar el bot con lógica matemática y de riesgo en Python.

## 1. Resumen del Diagnóstico Arquitectónico
Actualmente, el bot delega demasiada "interpretación" al LLM (Gemini). 
- **Debilidad:** El agente recibe precios crudos pero no indicadores (RSI, EMAs, Volatilidad). Está "operando a ciegas" matemáticamente.
- **Riesgo:** "Alucinación de mercado". El LLM puede sugerir trades basados en patrones inexistentes sin validación estadística.
- **Oportunidad:** Usar el backend de Python (FastAPI + Pandas) como un **Alpha Engine** y **Risk Guardrail**.

---

## 2. Prompt Maestro para Deep Research (Copiar y Pegar)

> **Contexto:** Estoy desarrollando un bot de trading híbrido (Agéntico/Determinista). El sistema usa Next.js para la ingesta de noticias y orquestación de LLMs (Gemini 2.0), y un backend en Python (FastAPI) para la ejecución en Binance. 
>
> **Objetivo:** Necesito diseñar la integración de un "Alpha Engine" y un "Risk Manager" determinista en Python que sirva como fuente de verdad para el agente.
>
> **Tareas de Investigación:**
> 1. **Cálculo de Features (Alpha Engine):** ¿Cómo implementar un pipeline eficiente en Python (usando `pandas-ta` o `TA-Lib`) que consuma WebSockets de Binance y entregue al agente un JSON con: RSI, Bandas de Bollinger, ADX, y niveles de Soporte/Resistencia calculados matemáticamente?
> 2. **Capa de Riesgo (Risk Guardrail):** Diseñar un middleware en Python que valide las señales del LLM. Debe incluir reglas duras: 
>    - Max Drawdown diario (ej. detener todo si se pierde el 2% del equity).
>    - Position Sizing basado en volatilidad (ATR).
>    - Bloqueo de trades si el spread de Binance supera un umbral.
> 3. **Estrategia de Memoria y Contexto:** Cómo estructurar la base de datos (Supabase) para que el bot en Python mantenga el estado de las estrategias sintetizadas y pueda compararlas con el "Market Snapshot" actual de forma síncrona.
> 4. **Backtesting Agéntico:** Investigar frameworks (como `VectorBT` o `Backtrader`) que permitan simular cómo hubiera actuado el Agente de LLM en el pasado usando logs de market data histórica.
> 5. **Foco Regional (Argentina):** Identificar APIs de data local o patrones de arbitraje específicos (ej. brecha entre USDT/ARS en exchanges locales vs Binance P2P) que puedan integrarse como 'features' adicionales al bot.
>
> **Formato de Respuesta:** Provee una arquitectura técnica detallada, snippets de código en Python 3.11+ y recomendaciones de librerías específicas para cada módulo.

---

## 3. Preguntas Clave para el Equipo (Roadmap)
Para implementar los resultados de esta investigación, debemos decidir:
1. **¿Priorizamos Arbitraje o Trend Following?** (En Argentina el arbitraje suele ser más seguro).
2. **¿Frecuencia de Operación?** (¿Scalping de minutos o Swing Trading de horas? Esto cambia la carga del Alpha Engine).
3. **¿Autonomía Total o Aprobación Humana?** (¿El Risk Manager puede auto-aprobar órdenes si el Risk Score es bajo?).

---
*Documento generado para la fase de fortalecimiento técnico del Bot Agentic.*
