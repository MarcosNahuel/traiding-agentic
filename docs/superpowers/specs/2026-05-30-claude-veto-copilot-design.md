# Claude Veto Co-Pilot — Design Spec

**Fecha:** 2026-05-30
**Branch:** `feat/claude-veto-copilot`
**Estado:** Aprobado, listo para plan de implementación

---

## 1. Contexto y objetivo

El bot de `traiding-agentic` corre un motor cuant determinista (RSI/MACD/ADX/Entropy + régimen + ML) que genera proposals de trade ejecutadas en Binance **Testnet**. Diagnóstico vigente (memoria `project_rr_fix_reverted_2026-05-30`): **el bleeding de mayo es de RÉGIMEN (chop/lateral), no de código** — el bot entra cuando no debería.

**Objetivo:** incorporar un agente Claude Agent SDK como **co-piloto de veto en el hot path**: un segundo gate, después del risk gate determinista y antes de ejecutar, que aprueba o veta **solo entradas BUY** usando RAG sobre el Knowledge Base + historial de trades. Ataca directo el problema de "no entrar en chop" sin tocar la protección de capital.

El patrón SDK replica `traid-brain` (proyecto hermano): `create_sdk_mcp_server` + `@tool` + `ClaudeAgentOptions`, auth por `CLAUDE_CODE_OAUTH_TOKEN` (plan Claude Max, no API key).

## 2. Decisiones (cerradas con el usuario)

| Decisión | Elección | Implicancia |
|---|---|---|
| Rol del agente | **Co-piloto en hot path** | LLM en el loop, pero solo como filtro |
| Autoridad | **Veto / gate** (approve/reject) | Nunca genera señales ni ajusta sizing |
| Deploy | **In-process** en el backend de trading | Tools acceden directo a `compute_indicators`/`detect_regime`/Supabase |
| Rollout | **Enforce desde día 1** | El veto bloquea trades reales (testnet) |
| Fallback | **Fail-open** | Si Claude falla/timeout → ejecuta como hoy |
| Scope | **Solo entradas BUY** | Exits/SL/TP/time-stop quedan 100% deterministas |

## 3. Arquitectura

### Punto de inserción

El veto entra en `signal_generator._submit_proposal()`, **después** de que `validate_proposal_enhanced()` (el gate determinista de 8 checks — la "constitution") setea el status, y **antes** de `execute_proposal()`:

```
generate_signals() →60s
  └─ _evaluate_symbol() → candidato BUY
       └─ _submit_proposal()
            ├─ insert proposal (status: "draft")
            ├─ validate_proposal_enhanced()  →  approved/rejected/validated   [GATE 1: determinista]
            ├─ if new_status == "approved" and trading_enabled:
            │     ├─ if COPILOT_ENABLED and trade_type == "buy":
            │     │     └─ veto_gate(...)  →  approve | veto                    [GATE 2: Claude]
            │     │            └─ veto  →  status="vetoed", log, NO ejecuta
            │     └─ execute_proposal()                                         [ejecución]
```

### Invariantes de seguridad (innegociables)

1. **El gate determinista corre primero.** Claude solo puede hacer la decisión más conservadora (vetar). Nunca puede saltearse `LLM_SAFE_BOUNDS` ni aprobar lo que el gate 1 rechazó.
2. **Solo gatea entradas BUY.** Los SL/TP/time-stop del `_fast_loop` (`_execute_sl_tp`) y los signal-exits (`_submit_proposal(... "sell" ...)`) **no pasan por el veto** — siguen deterministas. Un LLM jamás vetea un stop-loss.
3. **Fail-open.** Cualquier error/timeout del veto → el proposal `approved` ejecuta como hoy. Garantía "nunca peor que hoy".
4. **Doble kill-switch.** `COPILOT_ENABLED=false` (default) hace que el bot opere idéntico a hoy. Independiente de `TRADING_ENABLED`.
5. **Stateless.** Cada veto es un juicio independiente — sin sesión ni `resume`. No hay tabla de sesiones.

## 4. Componentes nuevos

```
backend/app/services/copilot/
├─ __init__.py
├─ veto_agent.py      # orquestación: build prompt, llamar SDK (query one-shot), timeout, parse verdict, fail-open
├─ veto_tools.py      # @tool: search_kb, read_kb, get_recent_trades, submit_verdict + create_copilot_server()
└─ prompts/
   └─ veto.md         # system prompt del gate
```

### `veto_agent.py` — interfaz pública

```python
async def veto_gate(
    *, symbol: str, trade_type: str, price: float, quantity: float,
    notional: float, reasoning: str, proposal_id: str,
    indicators_snapshot: dict, regime_snapshot: dict,
) -> VetoVerdict: ...
```

- `VetoVerdict` (pydantic): `veto: bool`, `confidence: float`, `reason: str`, `tool_calls: list`, `failed_open: bool`, `latency_ms: int`.
- Usa el API one-shot `query(prompt, options)` del SDK (más simple que `ClaudeSDKClient`; no necesitamos streaming ni sesión).
- `ClaudeAgentOptions(system_prompt=<veto.md>, mcp_servers={"copilot": server}, allowed_tools=[...], permission_mode="bypassPermissions", max_turns=COPILOT_MAX_TURNS)`.
- Envuelto en `asyncio.wait_for(..., timeout=COPILOT_TIMEOUT_S)`. `TimeoutError` o cualquier `Exception` → `VetoVerdict(veto=False, failed_open=True, reason="<error>")`.
- El régimen + indicadores van **inyectados en el prompt** (ya disponibles en `_evaluate_symbol`), para que Claude arranque con contexto sin gastar turns.
- El veredicto se fuerza vía el tool `submit_verdict` (no se parsea texto libre). Si el agente termina sin llamarlo → fail-open con `reason="no verdict emitted"`.

### `veto_tools.py` — el RAG + veredicto

| Tool | Firma | Qué hace |
|---|---|---|
| `search_kb` | `(query: str)` | grep agéntico sobre `docs/knowledge-base/**/*.md`, devuelve paths + snippets |
| `read_kb` | `(path: str)` | lee un doc del KB (path validado dentro de `docs/knowledge-base/`, anti path-traversal) |
| `get_recent_trades` | `(symbol: str, n: int)` | últimos N cierres del símbolo desde Supabase `positions` (PnL, win/loss, closed_at) |
| `submit_verdict` | `(approve: bool, confidence: float, reason: str)` | veredicto estructurado final |

`create_copilot_server()` → `create_sdk_mcp_server(name="copilot", tools=[...])`. `ALLOWED_TOOL_NAMES = ["mcp__copilot__search_kb", ...]`.

**RAG v1 = lectura agéntica filesystem.** El KB son ~25 markdowns. Cero vector DB. pgvector/Pinecone queda como camino de escala cuando el corpus crezca (trades + papers externos).

### `prompts/veto.md` — política

System prompt clave: *"Sos un risk gate de un bot de trading. Tu único trabajo es decidir si una entrada BUY ya aprobada por el motor cuant debe ejecutarse o vetarse. **Default a aprobar.** Vetá SOLO si hay señal clara de que es una trampa: régimen chop/lateral sin breakout confirmado, racha de pérdidas reciente en el símbolo, o contradicción explícita con las reglas del KB para el régimen actual. Consultá el KB y los trades recientes antes de decidir. Siempre terminá llamando a submit_verdict."* Sesgo a `approve` para no convertir el gate en un freno que mata todo el flujo.

## 5. El hook (cambio en `signal_generator._submit_proposal`)

Justo antes del bloque final de ejecución existente:

```python
    if new_status == "approved" and settings.trading_enabled:
        # ── GATE 2: Claude veto co-pilot (solo entradas BUY) ──
        if settings.copilot_enabled and trade_type == "buy":
            from .copilot.veto_agent import veto_gate
            verdict = await veto_gate(
                symbol=symbol, trade_type=trade_type, price=price,
                quantity=quantity, notional=notional_val, reasoning=reasoning,
                proposal_id=proposal_id, indicators_snapshot=..., regime_snapshot=...,
            )
            if verdict.veto:
                _record_veto(supabase, proposal_id, symbol, price, quantity,
                             reasoning, verdict)   # status="vetoed" + risk_events + Telegram
                return
            # approve o fail-open → cae al execute de abajo

        from .executor import execute_proposal
        result = await execute_proposal(proposal_id)
        logger.info("Auto-execute result: %s", result)
```

`_record_veto` (helper nuevo en signal_generator o copilot):
- `trade_proposals.update(status="vetoed", reasoning += "\n[COPILOT VETO] ...")`.
- `risk_events.insert(event_type="copilot_veto", severity="info", message=..., details=<candidato completo + verdict>)`.
- Telegram notify.

`"vetoed"` se agrega como valor permitido — verificar el check constraint de `trade_proposals.status` en Supabase (precedente: el commit `32c1e7f` ya tocó un check constraint de `risk_events`). Si el constraint lo rechaza, fallback a `status="rejected"` con el reason del veto.

## 6. Modelo de datos / logging / replay contrafáctico

No se crean tablas nuevas. Se usa lo existente:
- `trade_proposals.status` += `"vetoed"`; `reasoning` con el motivo del veto.
- `risk_events(event_type="copilot_veto")` con `details` = **contexto completo del candidato** (symbol, price, quantity, intended SL/TP, indicators snapshot, regime, verdict, latency).

**Replay contrafáctico (clave para enforce-mode):** como los trades vetados no ejecutan, su `details` ricos en `risk_events` permiten que `strategy_replay.py` reconstruya después el PnL hipotético contra las klines reales. Así medimos si el veto agregó o restó edge, sin shadow-mode. (Backlog: helper `replay_vetoed_candidates(since)` — fuera de v1.)

## 7. Deploy

El SDK de Python spawnea el CLI de Claude Code (Node) como subproceso. El container del backend necesita:
- `claude-agent-sdk>=0.2` en `requirements.txt`.
- Node + `@anthropic-ai/claude-code` CLI en el `Dockerfile` (replicar el patrón del Dockerfile de traid-brain).
- Env vars: `CLAUDE_CODE_OAUTH_TOKEN` (generar con `claude setup-token`, vida 1 año), `COPILOT_ENABLED`, `COPILOT_TIMEOUT_S`, `COPILOT_MAX_TURNS`.

## 8. Config / flags (en `app/config.py` `Settings`)

```python
copilot_enabled: bool = False          # Kill switch — default off
copilot_timeout_s: float = 20.0        # Hard timeout → fail-open
copilot_max_turns: int = 8             # Bound del tool loop
copilot_model: str = ""                # "" = default del SDK (Sonnet); override opcional
claude_code_oauth_token: str = ""      # Auth plan Max
```

## 9. Tests (pytest, espejo de `backend/tests/`)

`backend/tests/test_copilot_veto.py`:
1. **veto-path** — SDK mockeado devuelve `submit_verdict(approve=False)` → `_submit_proposal` setea `vetoed`, NO llama `execute_proposal`.
2. **approve-path** — `submit_verdict(approve=True)` → ejecuta normal.
3. **timeout → fail-open** — SDK cuelga > timeout → `failed_open=True`, ejecuta normal.
4. **error → fail-open** — SDK tira excepción → ejecuta normal.
5. **disabled passthrough** — `COPILOT_ENABLED=false` → ni se invoca el SDK, comportamiento idéntico a hoy.
6. **sólo BUY** — un `_submit_proposal("sell", ...)` nunca invoca el veto.
7. **invariante de orden** — el veto solo se evalúa si gate 1 dejó `new_status=="approved"`.

El SDK se mockea (no se llama a Claude real en CI). Los tools (`search_kb`, `get_recent_trades`) se testean unitariamente con fixtures.

## 10. Fuera de scope (YAGNI) + backlog

**No** en v1: sizing modulation, generación de señales, veto de exits/SL/TP, vector RAG, microservicio separado, shadow-mode infra.

**Backlog (de QuantMuse / análisis):**
- `replay_vetoed_candidates()` para medir edge del veto.
- Tool de **sentiment de news** (única pieza de alpha nueva real de QuantMuse) como input adicional del veto.
- VaR/CVaR y param-optimization de QuantMuse → solo si un sprint diagnóstico futuro los justifica.

## 11. Criterios de aceptación

- [ ] Con `COPILOT_ENABLED=false`, el bot opera byte-idéntico a hoy (tests 5).
- [ ] Con `COPILOT_ENABLED=true`, un BUY approved se evalúa por Claude; veto → no ejecuta + log; approve → ejecuta.
- [ ] Timeout/error del SDK nunca bloquea un trade (fail-open, tests 3-4).
- [ ] Exits/SL/TP nunca pasan por el veto (test 6).
- [ ] Todo veto deja en `risk_events` el contexto completo para replay.
- [ ] `pytest backend/tests/ -q` verde. `ruff` limpio.
