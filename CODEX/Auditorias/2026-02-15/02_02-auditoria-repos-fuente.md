# 02 - Auditoria de repositorios fuente

Fecha del snapshot: 2026-02-15
Metodo: GitHub API + revision de README/codigo fuente.

## Repos core (tecnologia base)

| Repo | Stars | Ultimo push UTC | Lenguaje | Lectura tecnica |
|---|---:|---|---|---|
| `vercel/next.js` | 137682 | 2026-02-15T17:51:01Z | JavaScript | Framework principal activo y mantenido. |
| `vercel/ai` | 21772 | 2026-02-14T20:45:09Z | TypeScript | SDK vigente para agentes/chat/structured output. |
| `supabase/supabase` | 97641 | 2026-02-15T00:36:12Z | TypeScript | Plataforma DB/auth/vector madura para MVP. |
| `pgvector/pgvector` | 19819 | 2026-01-22T00:41:05Z | C | Base robusta para vector search en Postgres. |
| `googleapis/js-genai` | 1470 | 2026-02-14T12:57:28Z | TypeScript | SDK JS recomendado por Google para Gemini. |

## Repos MCP Binance (candidatos)

| Repo | Stars | Forks | Issues | Ultimo push UTC | Lenguaje | Releases |
|---|---:|---:|---:|---|---|---|
| `forgequant/mcp-provider-binance` | 1 | 1 | 0 | 2025-10-21T15:52:55Z | Rust | none |
| `TermiX-official/binance-mcp` | 73 | 32 | 5 | 2025-04-16T06:57:55Z | TypeScript | none |
| `AnalyticAce/BinanceMCPServer` | 41 | 18 | 11 | 2026-01-22T10:05:45Z | Python | none |

## Hallazgos por candidato MCP

### `forgequant/mcp-provider-binance`

Hallazgos positivos:
- README declara `TESTNET Ready` y `Rate Limiting` con `exponential backoff`.
- Buen enfoque de seguridad: credenciales por env vars y mascarado de secretos.
- Herramientas de ordenes incluidas (`place_order`, `cancel_order`, `get_open_orders`).

Limitaciones detectadas:
- En codigo, el modelo de entorno es `testnet`/`mainnet` basado en `testnet.binance.vision` y `api.binance.com`.
- No aparece soporte explicito a `demo-fapi.binance.com` (Futures Demo).
- Baja adopcion publica actual (muy nuevo).

Lectura:
- Excelente para Spot testnet y para iniciar rapido con seguridad razonable.
- No alcanza por si solo si el objetivo operativo es USDT-M Perps en Demo Futures.

### `TermiX-official/binance-mcp`

Hallazgos:
- Incluye capacidades de trading y ordenes.
- README pide tambien una private key de wallet BSC para parte del setup.

Lectura:
- Para tu caso (MVP research/trading en Binance), agrega superficie de riesgo y complejidad no esencial.
- No es el mejor primer candidato para empezar "ya" en demo controlado.

### `AnalyticAce/BinanceMCPServer`

Hallazgos:
- README expone tools amplios y toggle `BINANCE_TESTNET=true`.
- Incluye funciones asociadas a trading/futures en documentacion.
- Actividad reciente buena, licencia MIT.

Lectura:
- Candidato util para iterar rapido en Python.
- Menos evidencia documentada de hardening operativo (rate policy, circuit breakers, etc.) comparado con `forgequant`.

## Conclusiones de auditoria repos

1. Para calidad tecnica de base del proyecto, los repos core elegidos son correctos.
2. Para MCP Binance, la mejor base pragmatica inicial sigue siendo `forgequant` si arrancas por Spot testnet.
3. Si objetivo inmediato es Perps/Futures demo, hace falta extender MCP o usar adapter de ejecucion propio a `demo-fapi`.
4. Ningun candidato trae una ruta "plug and play" claramente validada para Futures Demo + guardrails institucionales.
