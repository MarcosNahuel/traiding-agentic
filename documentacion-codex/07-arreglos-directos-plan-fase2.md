# 07 - Arreglos directos al plan de Fase 2

Base revisada:
- `docs/plans/2026-02-15-fase2-trading-bot-design.md`

## Cambios recomendados (listos para aplicar)

1. Seccion de Idempotencia
- Reemplazar "exchange ignora duplicados" por:
  - "orden con mismo `newClientOrderId` solo se acepta cuando la previa esta cerrada/filled"
  - "si hay timeout con estado desconocido, consultar por `clientOrderId` antes de retry"

2. Seccion de Reconciliacion
- Mantener polling cada 60s, pero agregar:
  - "user data stream como fuente primaria de estado"
  - "polling como fallback"

3. Seccion Market Data
- Agregar politicas WS:
  - reconexion y resuscripcion automatica
  - rotacion preventiva de conexion antes de 24h
  - control de ping/pong segun reglas del entorno spot/futures

4. Seccion Risk Manager (interfaces TS)
- Cambiar tipos literales a `number`.

Ejemplo:

```ts
interface RiskLimits {
  maxDailyLossPct: number;
  maxPositionSizeBTC: number;
  maxOpenPositions: number;
  stopLossPct: number;
  takeProfitPct: number;
  maxLeverage: number;
  cooldownAfterLossMinutes: number;
}
```

5. Seccion HITL
- Agregar `priceDriftGuardBps` al momento de aprobar.
- Si deriva demasiado del precio propuesto: revalidar o expirar propuesta.

6. Seccion Entornos
- Evaluar agregar `spot_demo` como etapa intermedia entre testnet y live.

7. Seccion Configuracion
- Consolidar `BINANCE_ENV` + `BROKER_ADAPTER` en una variable de enrutamiento unica.

8. Seccion Circuit Breakers
- En breaker de LLM, fallback recomendado:
  - `NO_TRADE` y alerta
  - evitar repetir ultima decision ciegamente

9. Seccion Definition of Done
- Agregar criterios:
  - `execution_unknown` resuelto automaticamente en > 99% de casos
  - `user stream uptime >= 99%`
  - `order_rejection_rate` desglosado en "esperado vs no esperado"

10. Seccion Security
- Agregar:
  - rotacion de API keys por entorno
  - bloqueo de logs con secretos
  - validacion estricta del payload de tool/LLM antes de ejecutar orden

