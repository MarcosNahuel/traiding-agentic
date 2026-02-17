# 09 - Fuentes de reauditoria (2026-02-15)

## Plan interno auditado
- `docs/02-2026/PLAN-TECNICO-MVP-COMPLETO.md`

## Fuentes oficiales usadas en esta reauditoria

1. AI SDK Google provider (metodo `.embedding()` y opciones `outputDimensionality`)
- https://ai-sdk.dev/providers/ai-sdk-providers/google-generative-ai

2. AI SDK embeddings overview (tabla de modelos/dimensiones)
- https://ai-sdk.dev/docs/ai-sdk-core/embeddings

3. Gemini API changelog (anuncio de shutdown de `text-embedding-004`)
- https://ai.google.dev/gemini-api/docs/changelog

4. Gemini API deprecations (ciclo de vida de modelos Gemini 2.0/2.5)
- https://ai.google.dev/gemini-api/docs/deprecations

5. Gemini embeddings docs (`gemini-embedding-001`, dimensionalidad flexible)
- https://ai.google.dev/gemini-api/docs/embeddings

6. Binance Spot Testnet WS docs
- https://developers.binance.com/docs/binance-spot-api-docs/testnet/web-socket-streams

7. Binance USDS-M Futures general info (demo endpoints)
- https://developers.binance.com/docs/derivatives/usds-margined-futures/general-info

## Nota

Las evidencias de esta pasada priorizan vigencia temporal (model lifecycle + endpoints). Si el proveedor actualiza fechas/model IDs, se debe revalidar antes de implementar.
