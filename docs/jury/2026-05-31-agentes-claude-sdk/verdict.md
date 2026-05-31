# Jury verdict — desarrollo de agentes Claude SDK (`8269512..HEAD`)

**Fecha:** 2026-05-31
**Panel:** codex (GPT-5.5, high effort) · Claude (sub-agente Opus) · ~~agy~~ (salida vacía, excluido) — + verificación directa del autor contra el código
**Modo:** round 1

## Executive summary

El desarrollo es **fundamentalmente sólido**: ambos modelos confirman que las 3 garantías de seguridad se cumplen en la lógica real, no solo en comentarios (veto fail-open + BUY-only; strategist dry-run que nunca toca `status='active'`/supersede; asesor-iol con confirmación humana obligatoria + mínimo privilegio de subagentes). Pero hay **defectos reales de defensa-en-profundidad y un par de bugs** que conviene corregir antes de habilitar nada. Los dos modelos encontraron problemas **casi disjuntos** (solo coinciden en el área del tope diario del asesor) — exactamente el valor de revisar con familias distintas. Verifiqué los blockers contra el código: son reales. Confidence: **high**.

## Consensus findings (★★) — ambos modelos coinciden

### F1: Contabilidad del tope diario del asesor está mal (race + fantasmas)
- **Severidad:** blocker — dinero real (cuenta IOL)
- **Dónde:** `asesor-iol/src/asesor_iol/security/gate.py:114,130` + `state/store.py`
- **Por qué:** Claude lo ve como **race** (el check suma solo `executed`; dos órdenes pending concurrentes pasan el límite). Codex lo ve como **fantasma** (se marca `executed` en la confirmación, ANTES de que IOL acepte; si IOL rechaza, el límite queda consumido por trades que no pasaron). Las dos caras del mismo problema: el accounting no modela el estado pending→executed correctamente.
- **Fix:** máquina de estados real — contar monto comprometido por `pending` en el check, y marcar `executed` solo tras respuesta exitosa de IOL (y liberar en cancel/expire/reject).
- **Citado por:** codex + claude (+ verificado)

## Majority/Unique findings — cada modelo cazó lo que el otro no vio

### F2: Bounds bypass en el strategist (claves arbitrarias no se filtran) — **claude + verificado**
- **Severidad:** blocker
- **Dónde:** `backend/app/services/strategist/outputs.py:45` + `daily_analyst/models.py:56-69`
- **Por qué:** `validate_bounds` hace `dict(config)` y solo clampea claves de `PARAM_BOUNDS`. Una clave arbitraria que proponga el agente (`trading_enabled`, `risk_max_daily_loss`, typo) pasa **sin filtrar** al `insert`. La garantía de "bounds duros" se rompe para todo el espacio de columnas. Verificado: real.
- **Fix:** allowlist estricta — `clamped = {k:v for k,v in config.items() if k in PARAM_BOUNDS}` antes de clampear. + test con `{"trading_enabled": True}`.

### F3: El veto puede filtrarse si falla el update de status — **claude + verificado (escalé severidad)**
- **Severidad:** blocker (subí de "consistencia" a blocker)
- **Dónde:** `backend/app/services/copilot/veto_agent.py:record_veto` + `trading_loop._main_loop`
- **Por qué:** si `record_veto` no logra cambiar el status a `vetoed`/`rejected` (ambos updates fallan), la propuesta queda `approved`. Y `_main_loop` llama `execute_all_approved(supabase)` **cada tick** → ejecutaría la entrada vetada. El hot-path inmediato está OK, pero un fallo de DB anula el veto en el tick siguiente.
- **Fix:** no dejar una propuesta vetada en `approved`. Verificar que el flip de status haya ocurrido; si no, usar un status no-ejecutable o alertar con severity error.

### F4: Dockerfile del asesor — build roto (README) + falta el CLI — **codex (P1)**
- **Severidad:** blocker (build) + major (runtime)
- **Dónde:** `asesor-iol/Dockerfile:5-8`
- **Por qué:** `pyproject.toml` declara `readme = "README.md"` pero el Dockerfile no copia el README antes de `pip install .` → hatchling falla, la imagen no buildea. Y aunque buildeara, no instala Node + Claude Code CLI → cada `Advisor.ask` fallaría al spawnear el CLI.
- **Fix:** `COPY README.md` antes del install; agregar Node + `@anthropic-ai/claude-code` a la imagen.

### F5: `insert_pending_config` reporta éxito aunque el insert falle — **codex + verificado**
- **Severidad:** major
- **Dónde:** `backend/app/services/strategist/outputs.py:68-71`
- **Por qué:** el `except` loguea pero igual `return row` → `run_daily_strategist` reporta `proposed_pending_config=True` y manda Telegram de una propuesta que no existe en DB.
- **Fix:** `return None` en el path de excepción.

### F6: El veto recibe snapshots vacíos → rompe el replay contrafáctico — **codex + verificado**
- **Severidad:** major
- **Dónde:** `backend/app/services/signal_generator.py` (`_submit_proposal` no pasa `indicators_snapshot`/`regime_snapshot`)
- **Por qué:** el veto y `record_veto` reciben `{}`; debilita la decisión y rompe el dato de replay que el spec prometía para medir edge en enforce-mode.
- **Fix:** threadear los indicadores/régimen desde `_evaluate_symbol`.

### F7: `_extract_amount` devuelve 0.0 → evade el límite de monto — **claude + verificado**
- **Severidad:** major
- **Dónde:** `asesor-iol/src/asesor_iol/security/gate.py:138-143`
- **Por qué:** orden sin `precio` → `amount=0` → pasa `max_order_amount`/`max_daily_amount` y muestra "Monto aprox: 0.00" al humano que confirma.
- **Fix:** si no se puede calcular monto confiable, tratar como límite excedido (deny).

### F8: Gate fail-open para tools de escritura desconocidas — **claude**
- **Severidad:** major
- **Dónde:** `asesor-iol/security/gate.py:84` (default permite no-ORDER_TOOLS) + drift con `ALLOWED_TOOLS`
- **Fix:** deny-by-default para tools `place_*`/`*_order` por prefijo, no solo set explícito.

### Otros (major/minor, 1 modelo)
- **claude:** falta test del callback `can_use_tool`/hooks (el invariante se prueba en `gate.evaluate`, no en el wiring del SDK); `place_order` defaultea `ok=True` con endpoints IOL no verificados.
- **codex/claude (minor):** TZ del "día" usa hora local; naming de modelos inconsistente (alias vs id full); `submit_*` gana el último.

## Positivos (ambos confirman)

Veto fail-open genuino (passthrough antes de tocar el SDK, BUY-only, timeout/except → failed_open, Telegram en su try/except, `test_copilot_hook` prueba los 3 invariantes). Strategist dry-run real (`insert_pending_config` return None salvo TWEAK, status hardcodeado pending_approval, test que afirma `update.assert_not_called()`). Aislamiento SDK-free + lazy import bien replicado. Path traversal correcto en `read_kb_impl`. Mínimo privilegio de subagentes. `_post` sin reintento. Telegram allowlist en mensajes y botones.

## Severity distribution

| Severidad | Consenso | 1-modelo (verificado) |
|---|---|---|
| Blocker | 1 (F1) | 2 (F2, F3, F4-build) |
| Major | 0 | ~7 |
| Minor | 0 | ~5 |

## Recommended action plan

1. **[BLOCKER] F2** — allowlist estricta de claves en `validate_bounds`/`outputs` (5 líneas + test).
2. **[BLOCKER] F3** — el veto no debe dejar la propuesta en `approved` si falla el flip de status.
3. **[BLOCKER] F1** — accounting pending+executed en el tope diario del asesor.
4. **[BLOCKER/build] F4** — COPY README + Node/CLI en el Dockerfile del asesor (necesario para que corra en VPS).
5. **[MAJOR] F5, F6, F7, F8** — return None en insert fallido; threadear snapshots al veto; deny en monto 0; deny-by-default para escrituras.
6. **[MAJOR] tests** — `can_use_tool`/hooks + invariante "todo write tool ∈ ORDER_TOOLS".

## Confidence assessment

- **Overall:** high. Los blockers están verificados contra el código por el autor (Claude). El core de seguridad es sólido; lo que falta es defensa-en-profundidad y 2-3 bugs concretos.
- **Limitación:** agy no produjo salida (bug de entorno), así que la diversidad fue 2 modelos, no 3. codex necesitó `sandbox_mode=danger-full-access` por el bug 1312 de Windows.

## Reviewer outputs

- [codex-review.md](./codex-review.md) — review completa (P1/P2 + diff)
- [claude-review.md](./claude-review.md) — review completa (contrato Summary/Critical/...)
- agy-review.md — vacío (excluido)
