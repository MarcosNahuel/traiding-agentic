# Proyecto Trading Agentico: Guia para Maximiliano

**Fecha:** Febrero 2026
**De:** Equipo de Desarrollo
**Para:** Maximiliano (Estrategia de Trading y Validacion)

---

## Que estamos construyendo (en simple)

Imaginate un equipo de analistas que trabajan 24/7 leyendo papers academicos de trading, extrayendo las mejores estrategias, y armando un manual de operaciones. Despues, ese manual se lo damos a un bot que opera en el mercado de Bitcoin siguiendo esas instrucciones.

Eso es exactamente lo que estamos construyendo, pero con inteligencia artificial.

**El sistema tiene dos grandes partes:**

1. **El Investigador** (Fase 1 - lo que hacemos ahora): Una IA que lee papers de trading, entiende las estrategias, y genera una guia maestra.
2. **El Trader** (Fase 2 - despues): Un bot que usa esa guia para operar BTC en modo simulado (paper trading, sin plata real).

---

## Por que empezamos por la investigacion y no por el trading

Muchos bots de trading fracasan porque alguien programa una estrategia que "le parece buena" sin evidencia solida. Nosotros hacemos lo contrario:

1. Primero investigamos que funciona (con datos reales de papers academicos)
2. Despues sintetizamos todo en una estrategia probada
3. Recien ahi le damos esa estrategia al bot

Es como en medicina: primero estudias la evidencia, despues tratas al paciente. No al reves.

---

## El Sistema de Investigacion (Fase 1)

### Los 3 Agentes de IA

Tenemos 3 "empleados virtuales" que trabajan en cadena:

### Agente 1: El Curador de Fuentes

**Que hace:** Evalua si un paper o articulo vale la pena leerlo.

**Como funciona:**
- Le damos una URL (un paper de arXiv, un articulo de QuantConnect, un repo de GitHub)
- El agente lee el resumen y evalua en 4 dimensiones:
  - **Relevancia** (0-10): Habla de trading de BTC? O es trading de acciones de 1990?
  - **Credibilidad** (0-10): Esta publicado en un journal serio? Tiene citas?
  - **Aplicabilidad** (0-10): Se puede implementar con nuestro capital (~$10K)?
  - **Actualidad**: Los datos son recientes?
- Si el score promedio es 6 o mas, lo aprueba. Si no, lo descarta y explica por que.

**Tu rol aqui, Maxi:** Vos nos podes pasar URLs de papers y articulos que conozcas. El agente los evalua automaticamente, pero tu criterio como trader es clave para alimentar buenas fuentes.

---

### Agente 2: El Lector de Papers

**Que hace:** Lee cada paper aprobado y extrae informacion estructurada.

**Que busca en cada paper:**

1. **Estrategias de trading:** Con todos los detalles:
   - Nombre de la estrategia
   - Tipo (momentum, mean-reversion, breakout, etc.)
   - Indicadores que usa (RSI, medias moviles, Bollinger, etc.)
   - Reglas exactas de entrada (cuando comprar)
   - Reglas exactas de salida (cuando vender, stop-loss, take-profit)
   - Resultados de backtest (Sharpe ratio, drawdown, win rate)
   - En que condiciones de mercado funciona y en cuales no

2. **Insights importantes:** Ideas que no son estrategias pero informan decisiones.
   Ejemplo: "La volatilidad de BTC aumenta 40% los fines de semana"

3. **Advertencias de riesgo:** Que puede salir mal.

4. **Contradicciones:** Si un paper dice lo contrario de otro, lo marca.

**Tu rol aqui, Maxi:** Cuando el agente extrae una estrategia, necesitamos tu ojo critico:
- "Esta estrategia tiene sentido desde tu experiencia?"
- "Los resultados de backtest son realistas?"
- "Falta considerar algo?"

---

### Agente 3: El Sintetizador (el mas importante)

**Que hace:** Toma TODO lo que extrajeron los papers y genera una "Guia Maestra de Trading".

**El proceso:**

1. **Encuentra patrones:** "5 de 8 papers dicen que RSI adaptativo funciona mejor que RSI fijo para BTC"
2. **Resuelve contradicciones:** Si Paper A dice una cosa y Paper B dice otra, evalua cual tiene mejor evidencia (mejor backtest, datos mas recientes, journal mas prestigioso)
3. **Rankea estrategias:** Ordena por cuanta evidencia las respalda
4. **Genera la guia:** Un documento que dice exactamente que hacer en cada situacion

**Ejemplo de output:**

> **Estrategia Principal: Momentum Adaptativo**
> - Respaldada por 6 de 12 papers analizados
> - Sharpe ratio promedio: 1.6
> - Usar cuando: BTC tiene tendencia clara (SMA 10 por encima de SMA 50 por mas de 4 horas)
> - Comprar cuando: RSI cruza 30 de abajo hacia arriba + SMA alcista + Volumen 20% arriba del promedio
> - Vender cuando: RSI supera 70, o Stop-loss de -2%, o Take-profit de +4%
>
> **Estrategia Secundaria: Mean-Reversion en Rango**
> - Usar cuando: Mercado lateral (SMA 10 y SMA 50 estan cerca por mas de 12 horas)
> - Comprar cuando: Precio toca Bollinger inferior + RSI por debajo de 25
> - Vender cuando: Precio llega a SMA 20, o Stop-loss de -1.5%

**Tu rol aqui, Maxi:** La guia es clave. Necesitamos que la revises:
- "Las reglas de entrada/salida son correctas?"
- "Los parametros de los indicadores tienen sentido?"
- "El mapa de condiciones de mercado es realista?"

---

## Estrategia de Trading Completa

### Contexto General

Operamos **BTCUSDT** en **Binance Testnet** (entorno simulado, sin dinero real).

- **Capital:** 10,000 USDT simulados
- **Tamanio por operacion:** 0.001 BTC (~$100 USD)
- **Timeframe:** Velas de 1 minuto, decisiones cada 5 minutos
- **Estilo:** Intraday a swing (no somos HFT, no tenemos la infra)
- **Leverage:** Ninguno para el MVP (1x)

### Indicadores Tecnicos que Usa el Sistema

Para que entiendas que mira el bot (esto ya lo sabes, pero lo dejo documentado):

| Indicador | Config | Para que lo usamos |
|-----------|--------|--------------------|
| **SMA 10** | Media movil simple 10 periodos | Tendencia de corto plazo |
| **SMA 50** | Media movil simple 50 periodos | Tendencia de mediano plazo |
| **RSI 14** | Relative Strength Index 14 periodos | Sobrecompra (>70) / Sobreventa (<30) |
| **Bollinger Bands** | SMA 20 +/- 2 desviaciones estandar | Volatilidad y extremos de precio |
| **Volumen promedio 20** | Media de volumen 20 periodos | Confirmar que hay interes del mercado |
| **ATR 14** | Average True Range 14 periodos | Medir volatilidad para sizing de stop-loss |

### Estrategias Disponibles

El bot tiene 4 "modos" que la IA elige segun las condiciones:

#### 1. Momentum Long (compra por tendencia)
**Cuando se activa:** Mercado en tendencia alcista clara
**Condiciones de entrada:**
- SMA 10 cruza por encima de SMA 50 (cruce dorado)
- RSI entre 40 y 65 (hay momentum pero no sobrecompra)
- Volumen actual > 120% del promedio de 20 periodos
- ATR > promedio (volatilidad saludable, no mercado muerto)

**Condiciones de salida:**
- Take-profit: +3% desde precio de entrada
- Stop-loss: -1.5% desde precio de entrada
- RSI supera 75 (sobrecompra, tomar ganancia antes del reverso)
- SMA 10 cruza por debajo de SMA 50 (tendencia se revierte)

**Basado en:** Estrategias de momentum documentadas en papers como "Momentum Strategies in Cryptocurrency Markets" y similares.

#### 2. Mean Reversion (compra en sobreventa)
**Cuando se activa:** Mercado lateral o despues de una caida brusca
**Condiciones de entrada:**
- Precio toca o cruza Bollinger Band inferior
- RSI < 25 (sobreventa extrema)
- El precio no esta en caida libre (SMA 50 relativamente plana)
- Volumen decreciente (el sell-off esta perdiendo fuerza)

**Condiciones de salida:**
- Take-profit: precio llega a Bollinger medio (SMA 20)
- Stop-loss: -1.5% desde precio de entrada
- RSI supera 50 (ya salio de sobreventa)
- Timeout: si en 2 horas no se movio, cerrar

**Basado en:** Mean-reversion en crypto tiene evidencia mixta; funciona mejor en timeframes cortos y rangos establecidos.

#### 3. Hold (no hacer nada)
**Cuando se activa:** Condiciones ambiguas
- RSI entre 40-60 (zona neutral)
- SMA 10 y SMA 50 muy cerca (sin tendencia clara)
- Volumen por debajo del promedio (poco interes)

**Accion:** Esperar. No forzar trades. Es la decision mas frecuente y la mas inteligente en mercados indecisos.

#### 4. Exit Position (cerrar posicion)
**Cuando se activa:** Hay una posicion abierta que debe cerrarse
- Se alcanzo stop-loss o take-profit
- Cambio de condiciones de mercado (la razon original ya no aplica)
- Riesgo elevado (volatilidad extrema sin direccion)

### Risk Management (Gestion de Riesgo)

**Esto es AUTOMATICO y no lo controla la IA.** Son reglas de codigo fijo:

| Regla | Limite | Razon |
|-------|--------|-------|
| Perdida diaria maxima | -2% del capital ($200) | Proteger capital. Si perdemos 2% en un dia, paramos hasta maniana |
| Tamanio de posicion | 0.001 BTC (~$100) | Nunca arriesgar mas del 1% del capital en una operacion |
| Posiciones abiertas | 1 a la vez | Mantener simple, no sobreexponerse |
| Stop-loss automatico | -1.5% desde entrada | Se ejecuta sin preguntar. No negociable |
| Take-profit automatico | +3% desde entrada | Tomar ganancia, no ser codicioso |
| Cooldown post-perdida | 30 minutos | Despues de una perdida, esperar antes de operar de nuevo |
| Leverage maximo | 1x (sin apalancamiento) | Para el MVP, solo capital propio |

**Importante:** Estas reglas las podemos ajustar, pero la IA NUNCA puede cambiarlas. Estan grabadas en codigo. Incluso si la IA dice "compra", si se excedio el limite diario, no se ejecuta.

---

## Como funciona el ciclo completo

```
1. Cargamos papers de trading (URLs)
         |
2. El Curador evalua cada uno (aprueba o rechaza)
         |
3. El Lector extrae estrategias e insights
         |
4. El Sintetizador genera la Guia Maestra
         |
5. La Guia alimenta al Trading Bot (Fase 2)
         |
6. El Bot opera en Binance Testnet (simulado)
         |
7. Analizamos resultados
         |
8. Agregamos mas papers, regeneramos la guia
         |
9. El Bot se actualiza automaticamente
         |
(ciclo continuo de mejora)
```

---

## Testing y Validacion

### Fase 1: Validacion de la Investigacion

Antes de que el bot opere, validamos que el sistema de investigacion funcione bien:

1. **Test con papers conocidos:** Le damos papers clasicos de trading (como los de Gatev sobre pairs trading, o estudios de momentum en crypto) y verificamos que extraiga las estrategias correctamente.

2. **Test de contradicciones:** Le damos papers que se contradicen y verificamos que el sintetizador resuelva el conflicto correctamente.

3. **Test de calidad de guia:** Generamos una guia y vos, Maxi, la revisas como trader. Los entry/exit rules tienen sentido? Los indicadores estan bien configurados?

### Fase 2: Validacion del Trading (Paper Trading)

Una vez que tengamos el bot operando en testnet:

1. **Paper Trading (simulado):** El bot opera con dinero ficticio en Binance Testnet. Los precios son similares a los reales pero no hay riesgo.

2. **Metricas que vamos a medir:**
   - **Win Rate:** % de operaciones ganadoras (target: > 55%)
   - **Profit Factor:** Ganancia total / Perdida total (target: > 1.5)
   - **Sharpe Ratio:** Retorno ajustado por riesgo (target: > 1.0)
   - **Max Drawdown:** Peor caida del capital (target: < 10%)
   - **Operaciones por dia:** Cuantos trades hace (target: 3-8)

3. **Periodo de prueba:** Minimo 2 semanas de paper trading antes de considerar dinero real.

4. **Go/No-Go:** Criterios para pasar a dinero real (si algun dia queremos):
   - Win rate > 55% sostenido por 2 semanas
   - Max drawdown < 10%
   - Profit factor > 1.5
   - Sin errores de sistema en 48 horas
   - Revision tuya aprobada

### Que puede salir mal (y como lo mitigamos)

| Riesgo | Mitigacion |
|--------|-----------|
| La IA toma malas decisiones de trading | Risk manager determinista la frena. Perdida maxima -2% diario |
| Los papers tienen data vieja que no aplica | El Curador filtra por actualidad. Podemos re-generar la guia |
| Binance cambia su API | Estamos en testnet, si rompe no perdemos nada |
| Prompt injection (alguien intenta manipular la IA) | La IA nunca ejecuta codigo directo. Output estructurado con validacion |
| El mercado se comporta diferente a los papers | Por eso hacemos paper trading. La evidencia academica es un input, no verdad absoluta |

---

## Tu Rol en el Proyecto, Maxi

### Fase 1 (ahora):
1. **Fuentes:** Pasanos URLs de papers y articulos de trading que consideres valiosos
2. **Revision de estrategias:** Cuando el agente extraiga estrategias, validar que tengan sentido
3. **Revision de la guia:** La guia maestra necesita tu ojo critico antes de alimentar al bot
4. **Feedback continuo:** "Este indicador esta mal configurado", "en mi experiencia esto no funciona asi"

### Fase 2 (despues):
1. **Parametros de riesgo:** Ayudarnos a calibrar stop-loss, take-profit, position sizing
2. **Analisis de operaciones:** Revisar las trades del bot y diagnosticar que esta haciendo bien/mal
3. **Ajustes de estrategia:** Proponer cambios basados en los resultados
4. **Go/No-Go:** Tu aprobacion es necesaria antes de cualquier paso a real

---

## Cronograma

| Semana | Que hacemos | Tu participacion |
|--------|-------------|-----------------|
| 1 | Setup tecnico (base de datos, infraestructura) | Nada, puro codigo |
| 2 | Source Agent + Reader Agent funcionando | Pasanos 5-10 URLs de papers |
| 3 | Synthesis Agent + Dashboard + Chat | Revision de la guia maestra |
| 4 | Pulir + preparar Fase 2 | Feedback final sobre estrategia |
| 5-6 | Trading Bot en testnet | Monitorear operaciones, analizar performance |
| 7-8 | Ajustes basados en resultados | Calibrar parametros con nosotros |

---

## Preguntas que Necesitamos que Respondas

1. **Fuentes iniciales:** Tenes papers o articulos de trading de BTC que consideres buenos? Pasanos las URLs.

2. **Indicadores favoritos:** Ademas de SMA, RSI, Bollinger, y ATR, hay algun otro indicador que uses mucho y quieras que el sistema considere?

3. **Timeframe preferido:** Nos enfocamos en velas de 1 minuto con decisiones cada 5 minutos. Te parece bien o preferis otro timeframe (5m, 15m, 1h)?

4. **Risk tolerance:** Los limites de riesgo (2% diario, 1.5% stop-loss) te parecen razonables para $10K de capital?

5. **Que estrategias conoces que funcionen?** Aunque el sistema va a investigar por su cuenta, tu experiencia es valiosa como punto de partida.

---

*Este documento fue generado el 15 de febrero de 2026. Se actualizara a medida que el proyecto avance.*
