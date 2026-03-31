# Diseno: Analisis Estrategico Diario con Claude Code

Fecha: 2026-03-30
Status: Aprobado
Reemplaza: docs/plans/2026-03-30-claude-trading-brain.md (rechazado, ver audit)

## Contexto

El sistema de trading tiene dos necesidades distintas:

1. **Evaluacion constante** (cada 60s) — ya resuelta por Gemini via Daily Analyst
2. **Analisis estrategico profundo** (1x/dia) — no existia, ahora resuelto por Claude Code

La decision clave: NO construir un agente nuevo. Usar Claude Code (el CLI que ya esta instalado y autenticado en la PC del operador) como el agente estrategico.

## Arquitectura

```
GEMINI (Backend VPS, constante)              CLAUDE CODE (PC local, 1x/dia)
├── Pre-market analysis                      ├── Lee trades de Supabase (MCP)
├── Post-market audit                        ├── Consulta 8+ APIs de mercado
├── Config bridge cada ciclo                 ├── WebSearch noticias y papers
├── Loop 60s evaluacion                      ├── Analiza rendimiento vs config
│                                            ├── Decide: ajustar, fixear, o nada
│   source: 'gemini_premarket'               ├── Escribe config via Supabase MCP
│   source: 'gemini_postmarket'              │   source: 'claude_strategic'
│                                            ├── Crea branch si hay bug
└──────── llm_trading_configs ───────────────┘── Notifica por Telegram
                    │
          config_bridge (cada 60s)
                    │
            signal_generator
```

### Por que esta arquitectura

| Decisión | Razon |
|----------|-------|
| Claude Code CLI, no Agent SDK | Ya es un agente terminado con todas las tools. No hay que construir nada. |
| Auth Max, no API key | $0/mes. 1 llamada/dia no justifica API billing. |
| Supabase como punto de encuentro | Backend y Claude Code ya lo usan. No hay que exponer el VPS. |
| Branch para fixes, no push a main | El operador revisa antes de mergear. Human-in-the-loop para codigo. |
| Autonomia para config, review para code | Config es reversible (supersede). Codigo no. |

## Componentes

### 1. Prompt: `prompts/daily-strategic-analysis.md`

5 fases secuenciales:

| Fase | Que hace | Herramienta |
|------|----------|-------------|
| 1. Leer estado | Queries a trade_proposals, positions, llm_trading_configs, risk_events | Supabase MCP |
| 2. Investigar | Fear&Greed, funding rates, L/S ratio, OI, on-chain, noticias, papers | curl + WebSearch |
| 3. Analizar | Performance vs config, contexto de mercado, deteccion de anomalias | Razonamiento |
| 4. Decidir | Ajustar config via SQL, crear branch para fix, o solo reportar | Supabase MCP + Git |
| 5. Notificar | Resumen por Telegram via curl al bot | Bash |

### 2. Launcher: `scripts/run-daily-analysis.bat`

- Verifica que Claude Code esta instalado
- Ejecuta `claude -p` con el prompt
- Loguea en `logs/claude-daily-YYYY-MM-DD.log`
- Maneja errores

### 3. Schedule: Windows Task Scheduler

- Ejecuta el .bat cada dia a las 7:00 AM
- Timeout 30 minutos
- 2 reintentos si falla
- Instrucciones en `scripts/SETUP-TASK-SCHEDULER.md`

## Fuentes de datos

### Tier 1 — Obligatorias cada dia (gratis, sin API key)

| Fuente | Dato | URL |
|--------|------|-----|
| Alternative.me | Fear & Greed Index | api.alternative.me/fng/ |
| Binance Futures API | Funding rates, L/S ratio, Open Interest | fapi.binance.com |
| Blockchain.info | On-chain BTC stats | api.blockchain.info/stats |
| Mempool.space | BTC fees, congestion | mempool.space/api |
| DeFiLlama | DeFi TVL global | api.llama.fi |
| CryptoPanic | Noticias con sentiment | cryptopanic.com/api |
| CoinDesk/CoinTelegraph RSS | Noticias tier-1 | RSS feeds |

### Tier 2 — Con API key gratuita

| Fuente | Dato | Requisito |
|--------|------|-----------|
| Finnhub | Calendario macro (FOMC, CPI) | FINNHUB_API_KEY |
| FRED | Datos de la Fed | FRED_API_KEY |
| Whale Alert | Whale movements | WHALE_ALERT_KEY |
| Glassnode | On-chain pro (SOPR, MVRV) | GLASSNODE_KEY |

### Tier 3 — Research semanal (solo lunes o anomalias)

| Fuente | Contenido |
|--------|-----------|
| arXiv q-fin.TR | Papers de trading |
| Binance Research | Reportes mensuales |
| Quantocracy | Curacion de papers quant |
| Quantpedia | Estrategias derivadas de papers |
| Alpha Architect | Curacion academica |

## Contrato de escritura

Claude Code escribe al mismo contrato que Gemini: `llm_trading_configs`.

Campo `source` distingue el origen:

| Source | Quien | Cuando |
|--------|-------|--------|
| `gemini_premarket` | Gemini Daily Analyst | Scheduled (03:00 UTC) |
| `gemini_postmarket` | Gemini Daily Analyst | Scheduled (23:00 UTC) |
| `claude_strategic` | Claude Code CLI | Diario 7:00 AM local |
| `claude_reactive` | Claude Code CLI | Manual (alarma) |

El `config_bridge` ya lee la config mas reciente con `status='active'`. No necesita cambios.

## Seguridad

| Riesgo | Mitigacion |
|--------|------------|
| Claude modifica codigo critico | Solo en branch, nunca main |
| Claude borra datos | Regla explicita: NUNCA DELETE/TRUNCATE |
| Claude envia ordenes | No tiene acceso a Binance API keys |
| Config degrada performance | Bounds de TradingConfigOverride (Pydantic) + validate_bounds() |
| PC apagada | Gemini sigue operando con la ultima config valida |
| Claude falla silenciosamente | Log local + Telegram como canales independientes |

## Costos

| Componente | Costo/mes |
|------------|-----------|
| Claude Code (Max subscription) | $0 adicional (ya pagado) |
| APIs Tier 1 | $0 (gratuitas) |
| APIs Tier 2 | $0 (planes free) |
| Supabase | $0 adicional (ya pagado) |
| **Total** | **$0** |

## Implementacion completada

- [x] Migration para tablas faltantes (`20260330_normalize_missing_tables.sql`)
- [x] Fix partial fills (`executor.py:126`)
- [x] Fix defaults inconsistentes (`models.py:30` tp_atr alineado a 2.5)
- [x] Fix Edge runtime warning (`lib/auth/constants.ts`)
- [x] Update README (164+ tests)
- [x] Prompt completo (`prompts/daily-strategic-analysis.md`)
- [x] Launcher script (`scripts/run-daily-analysis.bat`)
- [x] Instrucciones Task Scheduler (`scripts/SETUP-TASK-SCHEDULER.md`)

## Pendiente (operador)

- [ ] Aplicar migracion en Supabase (`supabase db push` o ejecutar SQL manualmente)
- [ ] Configurar Windows Task Scheduler (seguir `scripts/SETUP-TASK-SCHEDULER.md`)
- [ ] Probar corrida manual: `scripts/run-daily-analysis.bat`
- [ ] Verificar que Telegram recibe el mensaje
- [ ] Opcionalmente agregar API keys Tier 2 al .env
