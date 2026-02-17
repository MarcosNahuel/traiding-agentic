# 05 - Fuentes verificadas

Fecha de consulta: 2026-02-15

## Documento auditado

1. `docs/02-2026/PLAN-TECNICO-MVP-COMPLETO.md`
   - Plan maestro analizado completo (lineas 1-1359).

## Fuentes oficiales del stack

1. Next.js 16 release
- https://nextjs.org/blog/next-16
- Validacion de version base usada en el plan.

2. Next.js Route Handlers (App Router)
- https://nextjs.org/docs/app/getting-started/route-handlers
- Validacion de modelo de backend en `app/api/.../route.ts`.

3. Next.js route segment config (`maxDuration`)
- https://nextjs.org/docs/app/api-reference/file-conventions/route-segment-config
- Validacion de limites para handlers serverless.

4. create-next-app docs (Node requirement)
- https://nextjs.org/docs/app/api-reference/cli/create-next-app
- Referencia de runtime Node requerido.

5. Vercel AI SDK Google provider
- https://ai-sdk.dev/providers/ai-sdk-providers/google-generative-ai
- Validacion de APIs actuales de provider y embedding.

6. Vercel AI SDK `useChat`
- https://ai-sdk.dev/docs/reference/ai-sdk-ui/use-chat
- Validacion del contrato actual de chat UI.

7. Gemini API JS libraries
- https://ai.google.dev/gemini-api/docs/libraries
- Evidencia de deprecacion de `@google/generative-ai`.

8. Gemini API deprecations
- https://ai.google.dev/gemini-api/docs/deprecations
- Estado temporal de `gemini-2.0-flash` y reemplazos recomendados.

9. Gemini API pricing
- https://ai.google.dev/gemini-api/docs/pricing
- Recalculo de costos de embeddings/modelos.

10. Supabase RLS docs
- https://supabase.com/docs/guides/database/postgres/row-level-security
- Validacion de recomendacion de seguridad en DB.

11. pgvector README
- https://github.com/pgvector/pgvector
- Recomendaciones HNSW/IVFFlat y tuning.

## Fuentes oficiales Binance

1. Spot Testnet WS
- https://raw.githubusercontent.com/binance/binance-spot-api-docs/master/testnet/web-socket-streams.md
- Endpoint WS base de spot testnet.

2. Spot Testnet REST
- https://raw.githubusercontent.com/binance/binance-spot-api-docs/master/testnet/rest-api.md
- Endpoint REST base de spot testnet.

3. USDS-M Futures general info (Demo endpoint)
- https://raw.githubusercontent.com/binance/binance-docs/master/docs/derivatives/usds-margined-futures/general-info.md
- Endpoint `https://demo-fapi.binance.com`.

4. Binance Developer Community (contexto de migracion a demo trading)
- https://dev.binance.vision/t/no-authorization-with-futures-api-on-testnet/36541
- Confirmacion operativa de cambios testnet/demo en futuros.

5. Binance FAQ demo trading
- https://www.binance.com/en/support/faq/how-to-use-binance-futures-s-testnet-website-35131f3e8ce14f5da40f6f4e1f90d161
- Referencia oficial de disponibilidad de APIs en modo demo.

## Repos MCP Binance auditados

1. forgequant
- https://github.com/forgequant/mcp-provider-binance

2. TermiX-official
- https://github.com/TermiX-official/binance-mcp

3. AnalyticAce
- https://github.com/AnalyticAce/BinanceMCPServer

## Repos core auditados

1. https://github.com/vercel/next.js
2. https://github.com/vercel/ai
3. https://github.com/supabase/supabase
4. https://github.com/pgvector/pgvector
5. https://github.com/googleapis/js-genai

## Metadata adicional usada

- GitHub REST API (`/repos/{owner}/{repo}` y `/releases/latest`) para snapshot de actividad y salud de repos.
