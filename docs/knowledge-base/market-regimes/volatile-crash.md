---
regime: volatile
detection: ATR% > 5% en <4h, noticias/eventos macro
---

# Volatile / Crash

## Características
- Movements >5% en ventanas cortas
- Liquidaciones en cascada
- Spreads bid/ask amplios
- Volumen extremo (3-10× baseline)

## Performance histórica del bot
- Ningún trade identificado en este régimen en la data actual (testnet, movimientos simulados)
- En mainnet, este régimen es el que genera los **peores drawdowns** si no se pausa

## Estrategia activa
**NINGUNA — pausar todas las entradas**

Acción recomendada por el sistema:
1. `TRADING_ENABLED=false` automático si ATR% > 5% en 1h
2. Notificación Telegram inmediata
3. Cerrar posiciones abiertas con trailing agresivo

## Implementación faltante
- Circuit breaker automático (no existe actualmente)
- Detección de news/events (no existe)
- Auto-pause via cron o signal

## Riesgos
- Fills a precios muy malos (slippage brutal)
- SL saltado por gap
- Chain liquidations (long squeeze)
