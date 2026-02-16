# 05 - Repositorios de bots y piezas reutilizables

## Objetivo

No copiar bots completos, sino extraer componentes probados:

- Motor de estrategia
- Conectividad exchange
- Risk controls
- Backtesting/replay
- Observabilidad operativa

## Repositorios recomendados

## 1) Freqtrade

- Repo: `https://github.com/freqtrade/freqtrade`
- Stack: Python
- Foco: estrategia cuantitativa, backtesting, hyperopt, bot de produccion crypto.

Que extraer:
- Estructura de estrategia separada de ejecucion
- Control de riesgo por configuracion
- Pipeline de backtesting reproducible

## 2) Hummingbot

- Repo: `https://github.com/hummingbot/hummingbot`
- Stack: Python/Cython
- Foco: conectores de exchange y estrategias market making/arbitraje.

Que extraer:
- Patron de conectores robustos a exchanges
- Estado de ordenes en tiempo real
- Manejo de reconexiones y sincronizacion

## 3) Jesse

- Repo: `https://github.com/jesse-ai/jesse`
- Stack: Python
- Foco: trading framework con enfasis en backtesting y ejecucion real.

Que extraer:
- Organizacion de estrategia y rutas
- Patron de tests de estrategia
- Flujo de simulacion -> live

## 4) CCXT

- Repo: `https://github.com/ccxt/ccxt`
- Stack: JS/TS/Python/PHP
- Foco: capa unificada para exchanges.

Que extraer:
- Abstracciones cross-exchange
- Manejo de precision/market metadata

Advertencia:
- Si el objetivo es exprimir capacidades Binance (user streams, detalles finos), mantener tambien adapter nativo Binance.

## 5) NautilusTrader

- Repo: `https://github.com/nautechsystems/nautilus_trader`
- Stack: Python + Rust
- Foco: infraestructura de trading de baja latencia, fuerte en paridad backtest/live.

Que extraer:
- Modelo de eventos y ciclo de orden profesional
- Arquitectura modular de componentes de ejecucion

## 6) Binance Connector (oficial)

- Repo principal: `https://github.com/binance/binance-connector-python`
- Nota: conectores legacy de futures/spot tienen avisos de deprecacion en favor del conector modular.

Que extraer:
- Firma y flujo de request oficial
- Mapeo de endpoints y parametros actualizados

## Matriz rapida: que usar en este repo

Para `traiding-agentic` (Next.js + TS + Supabase):

1. Tomar de Freqtrade:
- metodologia de validacion y backtesting.

2. Tomar de Hummingbot:
- patrones de conectividad/reconexion de exchange.

3. Tomar de CCXT:
- normalizacion cuando agregues mas exchanges.

4. Tomar de Binance Connector:
- referencia oficial de auth/params cuando no alcance CCXT.

## Plan de adopcion de codigo externo

1. Implementar POC del componente en `lib/trading/experimental/`.
2. Agregar tests unitarios y de integracion.
3. Medir impacto en latencia, error rate y complejidad.
4. Solo luego promover a `lib/trading/`.

