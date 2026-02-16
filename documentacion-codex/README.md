# Documentacion Codex - Trading Agentic

Este folder consolida el conocimiento tecnico necesario para aplicar Fase 2 del bot de trading con Binance, alineado a:

- `docs/plans/2026-02-15-mvp-research-trading-agent-design.md`
- `docs/plans/2026-02-15-fase2-trading-bot-design.md`
- `docs/02-2026/PLAN-TECNICO-MVP-COMPLETO.md`
- `docs/02-2026/Sistema Trading Multiagente Institucional.md`

Tambien incorpora validacion con fuentes externas oficiales y repositorios abiertos.

## Como usar esta documentacion

1. Leer `01-contexto-interno-y-criterios.md` para entender el marco del proyecto.
2. Leer `02-binance-api-testnet-demo.md` para reglas reales de Binance (spot/futures, testnet/demo).
3. Implementar con `03-arquitectura-bot-y-flujos.md` y `04-snippets-typescript.md`.
4. Revisar `05-repositorios-bots-referencia.md` para extraer patrones de otros bots.
5. Ejecutar `06-checklist-implementacion.md` antes de activar trading.
6. Validar trazabilidad en `FUENTES.md`.

## Objetivo practico

Reducir riesgo de implementacion y eliminar huecos comunes:

- Duplicados de orden por timeouts
- Rechazos por filtros de simbolo
- Desincronizacion por no usar user streams
- Drift entre simulador y exchange
- Falta de runbooks operativos

