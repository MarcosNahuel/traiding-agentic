# 14 - Fuentes oficiales actualizadas (2026-02-15)

Objetivo: dejar referencias primarias y vigentes para implementar sin ambiguedad.
Fecha de consulta: 2026-02-15.

## A. Stack base (framework y runtime)

1. Next.js 16 release
   - https://nextjs.org/blog/next-16
   - Uso: confirmar version objetivo del framework.
2. Next.js 16 upgrade guide
   - https://nextjs.org/docs/app/guides/upgrading/version-16
   - Uso: validar requisitos minimos (`Node.js >= 20.9.0`, React 19).

## B. AI SDK + Gemini

1. AI SDK Google provider (embeddings)
   - https://ai-sdk.dev/providers/ai-sdk-providers/google-generative-ai
   - Uso: firma oficial para embeddings con `providerOptions`.
2. AI SDK 6 migration guide
   - https://ai-sdk.dev/docs/migration-guides/migration-guide-6-0
   - Uso: validar cambios de API entre versiones.
3. Gemini API deprecations
   - https://ai.google.dev/gemini-api/docs/deprecations
   - Uso: evitar modelos/librerias en retiro.
4. Gemini API pricing
   - https://ai.google.dev/gemini-api/docs/pricing
   - Uso: costeo real de LLM y embeddings.
5. Gemini API migrate from deprecated SDK
   - https://ai.google.dev/gemini-api/docs/migrate
   - Uso: reemplazo de SDKs legacy.
6. Gemini model catalog
   - https://ai.google.dev/gemini-api/docs/models
   - Uso: confirmar modelos vigentes para texto/embeddings.

## C. Binance (spot, futures demo, WS, ordenes)

1. Spot Testnet general info
   - https://developers.binance.com/docs/binance-spot-api-docs/testnet/websocket-api/general-api-information
   - Uso: base URLs de testnet, limites y aclaraciones de ambiente.
2. Spot Testnet websocket streams
   - https://developers.binance.com/docs/binance-spot-api-docs/testnet/web-socket-streams
   - Uso: URL WS correcta para market data en spot testnet.
3. Spot WebSocket API rates and limits
   - https://developers.binance.com/docs/binance-spot-api-docs/websocket-api/rate-limits
   - Uso: limites de conexion/peso y politicas de rate limit.
4. Spot WebSocket API user data stream
   - https://developers.binance.com/docs/binance-spot-api-docs/websocket-api/user-data-stream-requests
   - Uso: suscripcion de eventos de cuenta/orden para reconciliacion.
5. Spot trading endpoints
   - https://developers.binance.com/docs/binance-spot-api-docs/rest-api/trading-endpoints
   - Uso: `newClientOrderId`, `recvWindow`, comportamiento de ordenes.
6. Spot filters (exchangeInfo)
   - https://developers.binance.com/docs/binance-spot-api-docs/filters
   - Uso: validar `PRICE_FILTER`, `LOT_SIZE`, `MIN_NOTIONAL` antes de enviar orden.
7. USDT-M futures general info (demo trading note)
   - https://developers.binance.com/docs/derivatives/usds-margined-futures/general-info
   - Uso: confirmar endpoints para futures demo (`demo-fapi`).

## D. Supabase + pgvector

1. Supabase Row Level Security
   - https://supabase.com/docs/guides/database/postgres/row-level-security
   - Uso: politicas RLS desde MVP.
2. pgvector docs (HNSW / indexing)
   - https://github.com/pgvector/pgvector
   - Uso: estrategia de indexacion vectorial y tuning basico.

## E. Seguridad (SSRF)

1. OWASP SSRF Prevention Cheat Sheet
   - https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html
   - Uso: controles minimos para fetcher de URLs externas.

## Regla de calidad de fuentes para siguientes iteraciones

1. Priorizar siempre documentacion oficial del proveedor o repositorio oficial.
2. Si hay conflicto entre blog/terceros y docs oficiales, gana la documentacion oficial.
3. Registrar fecha de consulta porque endpoints/modelos pueden cambiar.

