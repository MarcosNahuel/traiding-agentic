Sos parte de una COMISIÓN REVISORA de código (revisión independiente, multi-modelo). Revisá el desarrollo de 3 sistemas de agentes basados en el **Claude Agent SDK** en el repo `traiding-agentic`, comparando `HEAD` contra el commit base `8269512` (estado previo a este desarrollo). Diff: 63 archivos, ~3676 líneas nuevas.

## Los 3 sistemas a revisar

1. **`backend/app/services/copilot/`** — "veto co-pilot": un gate en el HOT-PATH de trading que usa Claude para aprobar/vetar entradas BUY, insertado en `backend/app/services/signal_generator.py` (función `_submit_proposal`). REQUISITO DE SEGURIDAD: debe ser **fail-open** — cualquier error/timeout NO debe bloquear un trade ni cambiar el comportamiento; con `COPILOT_ENABLED=false` (default) el bot DEBE operar idéntico a antes. Solo gatea BUY; los exits/SL/TP nunca deben pasar por el gate.

2. **`backend/app/services/strategist/`** — "daily strategist": un fleet multi-modelo (subagentes `data-analyst` + `knowledge` → agente decisor) que corre 1×/día y propone ajustes de configuración. REQUISITO DE SEGURIDAD: **DRY-RUN** — NUNCA debe escribir `status='active'` ni hacer supersede en la tabla `llm_trading_configs`; solo inserta `status='pending_approval'`. Un humano aprueba. Los parámetros propuestos deben quedar dentro de bounds duros (clamping).

3. **`asesor-iol/`** — asesor de inversión tradicional (broker InvertirOnline) con bot de Telegram + human-in-the-loop. REQUISITO DE SEGURIDAD: NINGUNA orden debe ejecutarse sin confirmación humana explícita por Telegram + límites duros (monto máx por orden, tope diario, símbolos permitidos). Los subagentes (datos, conocimiento) NO deben tener permiso de operar (mínimo privilegio).

## Foco prioritario (revisá esto con rigor especial)

- **¿Las 3 garantías de seguridad se cumplen DE VERDAD en el código?** No en los comentarios — en la lógica. (veto fail-open real; strategist nunca toca `active`; asesor-iol no opera sin confirmación + límites efectivos).
- **¿El uso del Claude Agent SDK es correcto?** `ClaudeAgentOptions`, `AgentDefinition`/subagentes, servidores MCP in-process, parsing de tool-use blocks, manejo de errores/timeouts, bridge del token.
- **Bugs de correctitud**, race conditions, manejo de errores, validación de inputs, path traversal, manejo de secretos/credenciales.
- **El hook en `signal_generator.py`** (hot-path de dinero): ¿puede romper, lanzar excepción, o cambiar el comportamiento cuando el gate está deshabilitado o cuando Claude falla?
- **Cobertura de tests** de los paths críticos (¿los tests realmente prueban el invariante de seguridad, o solo el happy path?).

## Contrato de salida (OBLIGATORIO — markdown, en este orden exacto)

```
## Summary
2-3 oraciones. Confidence: high/medium/low.

## Critical findings (severity: blocker)
Por cada uno: archivo:línea — qué está mal, por qué importa, fix sugerido.

## Important findings (severity: major)
Mismo formato.

## Suggestions (severity: minor)
Mismo formato.

## Positive observations
Qué está bien hecho (calibra confianza).

## Out of scope but worth noting
```

## Rúbrica de severidad

- **blocker** — bug, vulnerabilidad, riesgo de pérdida de datos/dinero, contrato roto, regresión, garantía de seguridad que NO se cumple.
- **major** — falla de diseño, performance, mantenibilidad, falta de tests en path crítico.
- **minor** — estilo, idiom, naming, code smell, gap de doc.

## Anti-adulación

NO rellenes con consejos genéricos. Si no encontrás un problema real en un nivel de severidad, dejá esa sección VACÍA. Citá `archivo:línea` siempre que puedas. Preferimos señal sobre volumen.
