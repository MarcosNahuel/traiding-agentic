# 06 - Anexo de evidencias puntuales

## Evidencias internas del plan

1. Uso de modelo potencialmente deprecable
- `docs/02-2026/PLAN-TECNICO-MVP-COMPLETO.md:510`
- `docs/02-2026/PLAN-TECNICO-MVP-COMPLETO.md:680`
- `docs/02-2026/PLAN-TECNICO-MVP-COMPLETO.md:802`
- `docs/02-2026/PLAN-TECNICO-MVP-COMPLETO.md:956`
- `docs/02-2026/PLAN-TECNICO-MVP-COMPLETO.md:1002`

2. API de embeddings usada en snippets
- `docs/02-2026/PLAN-TECNICO-MVP-COMPLETO.md:664`
- `docs/02-2026/PLAN-TECNICO-MVP-COMPLETO.md:972`

3. Endpoint WS Binance usado en Fase 2
- `docs/02-2026/PLAN-TECNICO-MVP-COMPLETO.md:1090`

4. Bug en snippet de guardado de estrategias
- `docs/02-2026/PLAN-TECNICO-MVP-COMPLETO.md:700`

## Evidencias en repos MCP (forgequant)

1. Default base URL en cliente
- `src/binance/client.rs` del repo `forgequant/mcp-provider-binance` muestra default `https://api.binance.com`.

2. Modelo de entorno soportado en tipos
- `src/types.rs` del repo `forgequant/mcp-provider-binance` enumera `Testnet` y `Mainnet` con base URLs spot.

3. README declara testnet y rate limiting
- README del repo `forgequant/mcp-provider-binance` incluye `TESTNET Ready` y `Rate Limiting`.

## Evidencias Binance

1. Spot testnet websocket base
- `binance-spot-api-docs/testnet/web-socket-streams.md` indica `wss://stream.testnet.binance.vision`.

2. Futures demo REST base
- `binance-docs/.../usds-margined-futures/general-info.md` incluye `https://demo-fapi.binance.com`.

3. Cambio de futures testnet a demo trading
- Binance dev community confirma migracion operativa y uso de endpoints demo.
