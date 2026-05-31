# Revisión — Agentes Claude Agent SDK (`8269512..HEAD`)

## Summary

Los tres sistemas implementan sus garantías de seguridad de forma sólida en la lógica (no solo en comentarios): el veto es genuinamente fail-open y BUY-only, el strategist nunca toca `status='active'` ni hace `update`/supersede, y el asesor-iol bloquea toda orden sin confirmación humana + límites duros con subagentes de mínimo privilegio. El uso del SDK es razonable y los patrones de aislamiento SDK-free/lazy-import están bien pensados. Hay un bypass real de bounds en el strategist (claves arbitrarias no se clampean), una race condition en el tope diario del asesor, y el `record_veto` puede dejar una proposición ejecutándose pese al veto si el `update` de status falla. Confidence: **high**.

## Critical findings (severity: blocker)

**`backend/app/services/strategist/outputs.py:45` + `daily_analyst/models.py:58-69` — clamping NO cubre claves fuera de `PARAM_BOUNDS`; bounds bypass.**
`validate_bounds` hace `clamped = dict(config)` y solo recorta las claves presentes en `PARAM_BOUNDS`. Cualquier clave que el agente proponga y que NO esté en `PARAM_BOUNDS` (ej. `risk_max_daily_loss`, `quant_buy_notional_usd`, `trading_enabled`, o un typo) pasa **sin clampear ni filtrar** al payload del `insert`. La garantía de "parámetros dentro de bounds duros" se rompe para todo el espacio de columnas escribibles de `llm_trading_configs`. Aunque es `pending_approval`, un humano aprobando a ojo puede promover un valor jamás validado.
Fix: usar allowlist estricta — descartar (o rechazar el insert de) cualquier clave de `proposed_config` que no esté en `PARAM_BOUNDS`, y validar tipos. Ej.: `clamped = {k: v for k, v in config.items() if k in PARAM_BOUNDS}` antes de clampear. Agregar test con `proposed_config={"trading_enabled": True}` que verifique que NO aparece en el payload.

**`backend/app/services/copilot/veto_agent.py:138-148` — un veto puede ejecutarse igual si el `update` de status falla en ambos intentos.**
El flujo en `signal_generator.py` decide vetar (`return` antes de `execute_proposal`) en base a `verdict.veto`, lo cual es correcto y **no** depende de `record_veto`. PERO el invariante real de negocio es "proposición vetada queda marcada vetada/rejected". Si `update` falla con `'vetoed'` y también con `'rejected'` (línea 148 solo loguea `error`, no re-lanza ni reintenta), la proposición queda en `status='approved'` en la DB mientras el trade no se ejecutó. Cualquier otro path que reconcilie "approved sin posición" (executor retry, cron de reconciliación) podría re-ejecutar la entrada que fue vetada, anulando el veto. El hot-path está OK; el riesgo es de consistencia de estado.
Fix: si ambos updates fallan, escalar (alerta/severity error en `risk_events`) y/o garantizar que ningún reconciliador trate `approved` como "pendiente de ejecutar". Documentar/forzar que el único path de ejecución es este `_submit_proposal`.

**`asesor-iol/src/asesor_iol/security/gate.py:130` + `state/store.py:65-72` — race condition en el tope diario (`max_daily_amount`) bajo confirmaciones concurrentes.**
`_check_hard_limits` lee `executed_amount_today()` (suma de órdenes con `status='executed'`) ANTES de pedir confirmación. Una orden solo se cuenta como `executed` tras la aprobación humana (`resolve_pending(order_id, "executed")`, línea 114). Entre el check y la resolución hay una ventana de minutos (timeout de confirmación). Si el agente propone dos órdenes en paralelo (o el usuario tiene dos pendientes), ambas pasan el check con el mismo "ejecutado hoy", y la suma de las dos puede superar `max_daily_amount`. El tope diario es un límite duro de dinero real (cuenta IOL real, no testnet) — superarlo es exactamente lo que el control debe impedir.
Fix: contar también el monto **comprometido** por órdenes `pending` (no resueltas) dentro del check, o reservar el monto al crear la pending y liberarlo en cancel/expire. Con SQLite y un solo proceso async basta sumar `pending`+`executed` del día en `_check_hard_limits`.

## Important findings (severity: major)

**`asesor-iol/src/asesor_iol/security/gate.py:26-30` vs `agents/orchestrator.py:27-38` — `cancel_order` está en `ORDER_TOOLS` (gateado) pero NO existe como tool ni está en `ALLOWED_TOOLS`; y la lista de tools de orden gateadas debe derivarse de una sola fuente.**
`ORDER_TOOLS` incluye `mcp__iol__cancel_order`, pero `build_iol_server` (tools.py) no define `cancel_order` y `ALLOWED_TOOLS` no lo lista. No es un agujero de seguridad (gatear algo inexistente es inocuo), pero revela drift entre la allowlist del orquestador y el set gateado. El riesgo inverso es el peligroso: si mañana se agrega una tool de escritura a `build_iol_server` y a `ALLOWED_TOOLS` pero alguien olvida agregarla a `ORDER_TOOLS`, esa orden **se ejecuta sin gate**. El default del gate (gate.py:84-85) es "no-orden → permitida", o sea fail-open para escrituras desconocidas.
Fix: derivar la allowlist de órdenes desde una única constante, o invertir el default a deny-by-default para cualquier tool `place_*`/`*_order` (matchear por prefijo/sufijo además del set explícito).

**`asesor-iol/src/asesor_iol/security/gate.py:138-143` — `_extract_amount` devuelve 0.0 cuando faltan `cantidad`/`precio`, evadiendo silenciosamente los límites de monto.**
Si el LLM emite `place_buy` sin `precio` (o con `precio=0`, orden a mercado), `amount=0.0` → pasa `max_order_amount` y `max_daily_amount` sin tope efectivo. La orden igual requiere confirmación humana (mitiga), pero el límite duro de monto queda anulado y el resumen de Telegram muestra "Monto aprox: 0.00", ocultando el tamaño real al humano que confirma. Para un broker real esto es relevante.
Fix: si no se puede calcular un monto confiable (`cantidad`/`precio` ausentes o ≤0), tratarlo como límite excedido (deny) o exigir precio explícito para órdenes gateadas.

**`asesor-iol` — cobertura de tests del invariante de seguridad incompleta en el path del SDK.**
`test_gate.py` cubre bien el `ConfirmationGate` aislado (límites, timeout, símbolo). Pero NO hay test de `make_can_use_tool`/`make_audit_hook` (hooks.py) ni de que `orchestrator.ALLOWED_TOOLS` ⊇ tools de escritura ⊆ `ORDER_TOOLS`. El invariante "ninguna orden sin confirmación" se prueba a nivel `gate.evaluate`, no a nivel del callback que el SDK realmente invoca, ni del wiring de `ClaudeAgentOptions`. Un cambio en la forma del retorno de `can_use_tool` (los propios comentarios admiten que "puede variar según la versión") rompería la seguridad sin que ningún test falle.
Fix: test de `make_can_use_tool` que verifique `_deny` cuando el gate niega, y un test de invariante sobre las constantes (todo tool de escritura del server está en `ORDER_TOOLS`).

**`asesor-iol/src/asesor_iol/iol/client.py:8-9, 176-195` — escrituras reales con endpoints "no verificados" y sin idempotencia; riesgo de doble orden.**
Los comentarios admiten que los paths `/api/v2/operar/...` deben verificarse contra el Swagger vivo y que las escrituras están en BETA. `_post` correctamente no reintenta (bien), pero `place_order` interpreta `data.get("ok", True)` con **default `True`**: si la respuesta de IOL no trae `ok`, se asume éxito. Combinado con endpoints no confirmados, una respuesta inesperada (HTML de error 200, body vacío) se reportaría como orden enviada. Para dinero real, el default debe ser "no asumir éxito".
Fix: `ok` debe defaultear a `False` salvo confirmación explícita (presencia de `numeroOperacion` o flag positivo conocido). Mantener `IOLError` como única vía de "no pasó nada" — alinear con el principio rector declarado en gate.py:9.

## Suggestions (severity: minor)

**`asesor-iol/src/asesor_iol/agents/orchestrator.py:33-38` — `ALLOWED_TOOLS` del orquestador incluye `place_buy`/`place_sell` (correcto, el gate los intercepta) pero también `Read`/`WebFetch`/`WebSearch` a nivel main agent.** El subagente `conocimiento` ya tiene WebSearch/WebFetch; dar `Read` al orquestador con `setting_sources=[]` es de bajo riesgo, pero conviene documentar por qué el main agent necesita `Read` (¿market-context.md?) o quitarlo (mínimo privilegio también para el orquestador).

**`backend/app/services/strategist/agent.py:24` — `_DEFAULT_DATA_MODEL = "claude-opus-4-8"` hardcodeado** mientras el copilot/asesor usan aliases (`opus`). Inconsistencia de naming de modelos entre los tres sistemas; si el alias del CLI cambia o el ID exacto se retira, falla en runtime (mitigado por fail-open/degraded, pero ruidoso). Centralizar.

**`backend/app/services/copilot/veto_agent.py:265` y `strategist/tools.py:98` — `submit_verdict`/`submit_decision` devuelven texto fijo; el valor real se captura del `ToolUseBlock.input` en el loop.** Funciona, pero acopla la correctitud a que el último `submit_*` gane (veto_agent.py:264 sobrescribe `verdict` en cada bloque). Si el agente llamara `submit_verdict` dos veces, gana el último — comportamiento aceptable pero no documentado. Un `break` tras el primer verdict válido sería más predecible.

**`asesor-iol/src/asesor_iol/state/store.py:83-85` — `_start_of_day` usa hora local del proceso (`time.localtime`/`mktime`).** El tope "diario" depende del TZ del contenedor; en UTC vs America/Argentina el corte se mueve 3h. Para un límite de dinero conviene fijar el TZ explícitamente.

**`asesor-iol/src/asesor_iol/security/gate.py:97` — `order_id = uuid.uuid4().hex[:12]` (48 bits).** Suficiente para volumen humano, pero como entra en `callback_data` de Telegram y es la clave del broker, documentar que el espacio es chico está bien; colisión es despreciable.

## Positive observations

- **Veto fail-open es real, no decorativo.** `veto_gate` (veto_agent.py:58-94) hace passthrough con `skipped=True` si `copilot_enabled=false` ANTES de tocar el SDK; BUY-only en línea 60-61; `asyncio.wait_for` con timeout → `failed_open`; `except Exception` amplio → `failed_open`; y "no verdict emitted" → `failed_open`. El hook en `signal_generator.py` está dentro del bloque `new_status == "approved" and trading_enabled`, gateado por `copilot_enabled and trade_type == "buy"`, y la notificación de Telegram está en su propio `try/except`. Exits/SL/TP no pasan por acá. `test_copilot_hook.py` prueba los tres invariantes (veto bloquea, approve ejecuta, disabled = no-op). Diseño correcto.
- **Strategist dry-run es genuino.** `insert_pending_config` (outputs.py) hace `return None` para todo lo que no sea `TWEAK_PARAMS`, hardcodea `status="pending_approval"`, nunca llama `update` ni supersede, y `test_insert_pending_never_active_never_supersedes` afirma `update.assert_not_called()`. `runner.py` jamás toca config activa. Bien aislado.
- **Aislamiento SDK-free + lazy import** (veto_agent, agent.py, kb_tools): permite testear toda la lógica de seguridad sin la CLI de Claude. Patrón replicado consistentemente. El bridge del token (`os.environ` solo si falta) es correcto.
- **Path traversal** en `read_kb_impl` (kb_tools.py:21-38) resuelto correctamente con `resolve()` + `relative_to(root)`, con manejo de `ValueError`.
- **Mínimo privilegio de subagentes** en asesor-iol/definitions.py: `datos` solo lecturas IOL (sin order tools), `conocimiento` solo Web (sin IOL). Coincide con el requisito.
- **`_post` sin reintento** en iol/client.py (comentario explícito sobre doble-ejecución) es la decisión correcta para escrituras.
- **Telegram allowlist** de un solo `chat_id` aplicada tanto en mensajes como en botones (bot.py:38-39, 61-63).

## Out of scope but worth noting

- `escape_html` se aplica al `reason` del veto/strategist en Telegram (bueno), pero `signal_generator` arma el mensaje con f-strings y emojis — verificar que `send_telegram` use `parse_mode=HTML` consistentemente, o el `<b>` se mostrará literal.
- `claude_code_oauth_token`/`anthropic_api_key` viven en `Settings` y se puentean a `os.environ`; los `.env.example` no incluyen secretos (correcto). Confirmar que `.gitignore` del asesor cubre `data/asesor.db` (audit log con tool inputs de cuenta real) — está en el árbol nuevo, vale revisar.
- El smoke `backend/scripts/smoke_copilot.py` y `run_strategist.py` no fueron auditados en profundidad; son scripts operativos, no path de producción.
- La dependencia de que `claude-agent-sdk` mantenga la forma de `PermissionResultAllow/Deny` y de `can_use_tool` es un riesgo de versión reconocido en los propios comentarios — pinnear la versión del SDK en `pyproject.toml`/`requirements.txt` reduce el blast radius.
