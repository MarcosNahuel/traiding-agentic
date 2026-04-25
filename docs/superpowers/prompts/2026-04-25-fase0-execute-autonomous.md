# Prompt: Ejecución autónoma de Fase 0 — Foundation

> **Cómo usar este prompt:** copialo a una sesión nueva de Claude Code (Opus 4.7
> recomendado). El agente va a implementar Fase 0 completa sin pedirte input,
> commiteando cada tarea por separado, con tests pasando.
>
> **Comando rápido en Claude Code:**
> ```
> /loop Lee docs/superpowers/prompts/2026-04-25-fase0-execute-autonomous.md y ejecutalo de punta a punta.
> ```

---

# Brief

Sos un ingeniero senior. Tu trabajo: implementar **Fase 0 del spec** del Daily
Strategist Agent en este repo, de forma autónoma, sin pedirme aprobación entre
tareas. El spec autoritativo está en:

```
docs/superpowers/specs/2026-04-24-daily-strategist-agent-design.md
```

**Leelo entero ANTES de empezar a tocar código.** Es la fuente de verdad. Si
algo de este prompt contradice al spec, gana el spec.

# Repo y stack

- **Working directory:** `C:\Users\nahue\Documents\PROYECTOS\traiding-agentic`
- **OS:** Windows 11 (bash y PowerShell disponibles).
- **Frontend:** Next.js 16 (App Router) en `app/`, TypeScript estricto.
  - Comando dev: `pnpm dev`
  - Build: `pnpm build`
  - Lint: `pnpm lint`
  - Typecheck: `pnpm typecheck`
- **Backend:** Python 3.12 / FastAPI en `backend/`.
  - Tests: `cd backend && pytest tests/ -q --tb=short`
  - Lint: ninguno crítico (sigue PEP-8 razonable).
- **DB:** Supabase. Project ref `zaqpiuwacinvebfttygm`. MCP `supabase`
  configurado en `.mcp.json` con permisos read/write.
- **Trading:** Binance Spot Testnet. Bot está en producción (Dokploy). **NO
  toques `TRADING_ENABLED`.**

# Hard rules (no negociables)

1. **NO `git push`.** Solo commits locales. El usuario revisa antes de pushear.
2. **NO toques `llm_trading_configs` con `status='active'`.** Solo
   `pending_approval`.
3. **NO desactives ni toques `daily_analyst/`** todavía. Fase 0.6 solo agrega
   un feature flag `LANGGRAPH_DAILY_ENABLED`. La pausa real es manual del
   usuario.
4. **NO modifiques `.env`, `.env.local`, `.env.production`.** Si necesitás env
   vars nuevas, documentalas en `docs/knowledge-base/research/gaps.md` o en
   un nuevo `docs/setup/env-vars.md`.
5. **NO instales paquetes globales.** `pip install` solo dentro de venv.
   `pnpm add` SÍ está OK (lockfile lo controla).
6. **TDD obligatorio:** test primero, falla, implementación mínima, pasa.
7. **Commits frecuentes:** uno por tarea completa (test+implementación+pasa).
   Mensajes con formato `feat(scope): ...`, `fix(scope): ...`, `test(scope): ...`,
   `docs(scope): ...`, `chore(scope): ...`.
8. **Si una tarea falla en CI/tests y no podés arreglarla en 2 intentos:**
   parala, dejá el repo limpio (descartá cambios no commiteados de esa tarea),
   reportá al final con detalle del bloqueante. NO inventes workarounds.
9. **Reportá progreso** después de cada tarea con un mensaje corto: "✅ Task X.Y
   done — N files, M tests, commit `<hash>`". Si una tarea queda BLOCKED,
   marcá "⚠️ Task X.Y BLOCKED: <reason>".

# Quality gates obligatorios después de cada tarea

```bash
# Backend
cd backend && pytest tests/ -q --tb=short
# Solo si tocaste código backend nuevo o existente

# Frontend (solo si tocaste TS/TSX)
pnpm typecheck
pnpm lint

# Final check antes de commit
git status   # debe estar limpio salvo lo que vas a commitear
git diff --stat    # revisión rápida de magnitud de cambios
```

Si pytest o typecheck fallan: NO COMMITEÁS. Arreglás. Si no podés en 2 intentos,
descartás los cambios de esa tarea, marcás BLOCKED, seguís con la siguiente
tarea independiente.

# Orden de ejecución

Las tareas tienen dependencias. Respetalas. Tareas marcadas **(paralelo)**
pueden ir en cualquier orden entre sí.

```
Task 1 → Task 2 → Task 3 → Task 4         (Bounds: secuencial)
Task 5 → Task 6                             (Migración Supabase + verificación)
Task 7 → Task 8 → Task 9                    (Endpoints Next.js + cron cleanup)
Task 10 → Task 11 → Task 12 → Task 13       (Derivatives client)
Task 14 → Task 15 → Task 16 → Task 17 → Task 18  (Partial exit con feature flag)
Task 19                                     (Proxy drift helper script)
Task 20 → Task 21                           (Decommission prep + KB doc)
```

Tasks 1-4 desbloquean todo. Empezá ahí. Tasks 7-9 dependen de Tasks 5-6
(migración aplicada). Tasks 14-18 son las más complejas — dejalas para el
final.

---

# Tareas

## Task 1 — Crear `backend/app/services/llm_bounds.py`

**Files:** Create `backend/app/services/llm_bounds.py`

**Steps:**

1. Crear el archivo con este contenido EXACTO:

```python
"""Single source of truth for LLM-overridable trading parameter bounds.

Used by:
- backend/app/services/signal_generator.py (runtime clamp)
- agents/daily_strategist/schemas.py (Pydantic Field constraints — Phase 1)

DO NOT redefine these bounds anywhere else. Import from here.

Post-mortem context: in 2026-03 the LLM analyst (Gemini Flash via LangGraph)
generated a config with cooldown=30min, RSI_max=60, ADX_min=12, entropy=0.93.
That config bypassed naive validation and produced -$18.74 in 49 trades by
trading in noisy non-trending markets. These bounds are the constitution.
"""

from typing import Final


LLM_SAFE_BOUNDS: Final[dict[str, tuple[float, float]]] = {
    "buy_rsi_max":             (30.0, 55.0),
    "buy_adx_min":             (18.0, 35.0),
    "buy_entropy_max":         (0.60, 0.80),
    "sell_rsi_min":            (60.0, 75.0),
    "signal_cooldown_minutes": (120.0, 360.0),
    "sl_atr_multiplier":       (0.5, 3.0),
    "tp_atr_multiplier":       (1.0, 4.0),
    "risk_multiplier":         (0.25, 2.0),
    "max_open_positions":      (1.0, 3.0),
}


def clamp(key: str, value: float) -> float:
    """Clamp a value to its safe bound. Raises KeyError if key unknown."""
    lo, hi = LLM_SAFE_BOUNDS[key]
    return max(lo, min(hi, value))


def is_within_bounds(key: str, value: float) -> bool:
    """Check if a value is within bounds without clamping."""
    if key not in LLM_SAFE_BOUNDS:
        return False
    lo, hi = LLM_SAFE_BOUNDS[key]
    return lo <= value <= hi
```

2. Verificar que el archivo importa OK:
   ```bash
   cd backend && python -c "from app.services.llm_bounds import LLM_SAFE_BOUNDS, clamp, is_within_bounds; print(len(LLM_SAFE_BOUNDS), 'bounds')"
   ```
   Expected output: `9 bounds`

3. Commit:
   ```bash
   git add backend/app/services/llm_bounds.py
   git commit -m "feat(bounds): single source of truth for LLM safe bounds"
   ```

---

## Task 2 — Test `llm_bounds`

**Files:** Create `backend/tests/test_llm_bounds.py`

**Steps:**

1. Escribir test fallando primero:

```python
"""Tests for backend.app.services.llm_bounds."""

import pytest
from app.services.llm_bounds import LLM_SAFE_BOUNDS, clamp, is_within_bounds


def test_bounds_dict_has_all_required_keys():
    required = {
        "buy_rsi_max", "buy_adx_min", "buy_entropy_max",
        "sell_rsi_min", "signal_cooldown_minutes",
        "sl_atr_multiplier", "tp_atr_multiplier",
        "risk_multiplier", "max_open_positions",
    }
    assert required.issubset(LLM_SAFE_BOUNDS.keys())


def test_bounds_are_tuples_of_two_floats():
    for key, val in LLM_SAFE_BOUNDS.items():
        assert isinstance(val, tuple), f"{key} not a tuple"
        assert len(val) == 2, f"{key} not length 2"
        lo, hi = val
        assert isinstance(lo, (int, float))
        assert isinstance(hi, (int, float))
        assert lo < hi, f"{key}: lo={lo} not < hi={hi}"


def test_clamp_within_bounds_returns_value():
    assert clamp("buy_rsi_max", 50.0) == 50.0


def test_clamp_below_min_returns_min():
    assert clamp("buy_rsi_max", 20.0) == 30.0


def test_clamp_above_max_returns_max():
    assert clamp("buy_rsi_max", 99.0) == 55.0


def test_clamp_unknown_key_raises():
    with pytest.raises(KeyError):
        clamp("nonexistent", 1.0)


def test_is_within_bounds_inside():
    assert is_within_bounds("buy_adx_min", 25.0) is True


def test_is_within_bounds_outside():
    assert is_within_bounds("buy_adx_min", 5.0) is False
    assert is_within_bounds("buy_adx_min", 99.0) is False


def test_is_within_bounds_unknown_key_returns_false():
    assert is_within_bounds("nonexistent", 1.0) is False


def test_clamp_at_boundaries():
    # Exact min and max should pass through unchanged
    lo, hi = LLM_SAFE_BOUNDS["buy_rsi_max"]
    assert clamp("buy_rsi_max", lo) == lo
    assert clamp("buy_rsi_max", hi) == hi
```

2. Correr test:
   ```bash
   cd backend && pytest tests/test_llm_bounds.py -v
   ```
   Expected: all green.

3. Commit:
   ```bash
   git add backend/tests/test_llm_bounds.py
   git commit -m "test(bounds): unit tests for llm_bounds module"
   ```

---

## Task 3 — Migrar `signal_generator.py` a usar `llm_bounds`

**Files:** Modify `backend/app/services/signal_generator.py`

**Steps:**

1. Leer las líneas 76-101 del archivo actual (donde está `LLM_SAFE_BOUNDS` local
   y `_clamp_llm_value`).

2. Reemplazar ese bloque (líneas 76-101) por:

```python
# ── Safe bounds para LLM overrides ──
# Importadas de single source of truth: backend/app/services/llm_bounds.py
# Post-mortem 2026-03: ver llm_bounds.py para contexto histórico.
from .llm_bounds import LLM_SAFE_BOUNDS, clamp as _clamp_bound


def _clamp_llm_value(key: str, value: float) -> float:
    """Clampea un valor LLM dentro de los safe bounds importados de llm_bounds."""
    if key not in LLM_SAFE_BOUNDS:
        return value
    clamped = _clamp_bound(key, value)
    if clamped != value:
        lo, hi = LLM_SAFE_BOUNDS[key]
        logger.warning(
            "LLM override CLAMPED: %s=%.2f -> %.2f (bounds: %.2f-%.2f)",
            key, value, clamped, lo, hi
        )
    return clamped
```

3. Verificar que ningún test existente se rompe:
   ```bash
   cd backend && pytest tests/ -q --tb=short
   ```
   Expected: todos los tests siguen verdes (pueden saltarse los que requieran
   Supabase si no tenés env). Si pytest reporta failures relacionados a
   `LLM_SAFE_BOUNDS` que NO existían antes, REVERTIR y reportar BLOCKED.

4. Commit:
   ```bash
   git add backend/app/services/signal_generator.py
   git commit -m "refactor(signal-generator): import LLM_SAFE_BOUNDS from llm_bounds module"
   ```

---

## Task 4 — Migrar `daily_analyst/models.py::PARAM_BOUNDS` y test alignment

**Files:**
- Modify `backend/app/services/daily_analyst/models.py`
- Create `backend/tests/test_bounds_alignment.py`

**Steps:**

1. En `daily_analyst/models.py`, reemplazar líneas 42-69 (`PARAM_BOUNDS` y
   `validate_bounds`) por:

```python
# Hard bounds — imported from single source of truth.
# Phase 0.2: aligned with signal_generator's LLM_SAFE_BOUNDS to prevent
# the analyst from generating values that get silently clamped at runtime.
from ..llm_bounds import LLM_SAFE_BOUNDS

PARAM_BOUNDS = LLM_SAFE_BOUNDS


def validate_bounds(config: dict) -> tuple[dict, list[str]]:
    """Clamp config values to hard bounds. Returns (clamped_config, warnings)."""
    clamped = dict(config)
    warnings = []
    for key, (lo, hi) in PARAM_BOUNDS.items():
        if key in clamped and clamped[key] is not None:
            val = float(clamped[key])
            if val < lo:
                warnings.append(f"{key}: {val} clamped to min {lo}")
                clamped[key] = lo
            elif val > hi:
                warnings.append(f"{key}: {val} clamped to max {hi}")
                clamped[key] = hi
    return clamped, warnings
```

2. Las Pydantic `Field(ge=, le=)` constraints en `TradingConfigOverride` (líneas
   18-37) están más laxas que `LLM_SAFE_BOUNDS`. Ajustarlas para que matcheen.
   Reemplazar las líneas 18-37 por:

```python
    buy_adx_min: float = Field(default=20.0, ge=18.0, le=35.0,
        description="Minimum ADX for BUY signals (higher = stronger trend required)")
    buy_entropy_max: float = Field(default=0.75, ge=0.60, le=0.80,
        description="Maximum entropy ratio for BUY (lower = less noise tolerance)")
    buy_rsi_max: float = Field(default=50.0, ge=30.0, le=55.0,
        description="Maximum RSI for BUY entry (lower = more oversold required)")
    sell_rsi_min: float = Field(default=65.0, ge=60.0, le=75.0,
        description="Minimum RSI for SELL exit (higher = more overbought required)")
    signal_cooldown_minutes: int = Field(default=180, ge=120, le=360,
        description="Minutes between signals for same symbol")
    sl_atr_multiplier: float = Field(default=1.0, ge=0.5, le=3.0,
        description="Stop-loss = entry - (multiplier x ATR)")
    tp_atr_multiplier: float = Field(default=2.0, ge=1.0, le=4.0,
        description="Take-profit = entry + (multiplier x ATR)")
    risk_multiplier: float = Field(default=1.0, ge=0.25, le=2.0,
        description="Position size multiplier")
    max_open_positions: int = Field(default=3, ge=1, le=3,
        description="Maximum simultaneous open positions")
    quant_symbols: str = Field(default="BTCUSDT,ETHUSDT",
        description="Comma-separated symbols to trade")
    reasoning: str = Field(default="",
        description="LLM explanation for the adjustments")
```

3. Crear `backend/tests/test_bounds_alignment.py`:

```python
"""Verify that signal_generator and daily_analyst share the same bounds."""

from app.services.llm_bounds import LLM_SAFE_BOUNDS
from app.services.daily_analyst.models import PARAM_BOUNDS, TradingConfigOverride


def test_signal_generator_bounds_match_single_source():
    # signal_generator imports from llm_bounds, so test that the import
    # is referentially the same object (not a copy that could drift).
    from app.services.signal_generator import LLM_SAFE_BOUNDS as SG_BOUNDS
    assert SG_BOUNDS is LLM_SAFE_BOUNDS, (
        "signal_generator.LLM_SAFE_BOUNDS should be the imported singleton, "
        "not a copy. If you see this fail, check the import statement in "
        "signal_generator.py — it should be `from .llm_bounds import LLM_SAFE_BOUNDS`."
    )


def test_param_bounds_is_llm_safe_bounds():
    assert PARAM_BOUNDS is LLM_SAFE_BOUNDS, (
        "daily_analyst PARAM_BOUNDS must be the same object as LLM_SAFE_BOUNDS."
    )


def test_pydantic_field_constraints_match_bounds():
    """Each Pydantic Field's ge/le should match LLM_SAFE_BOUNDS."""
    schema = TradingConfigOverride.model_json_schema()
    properties = schema.get("properties", {})

    field_to_bound = {
        "buy_rsi_max": "buy_rsi_max",
        "buy_adx_min": "buy_adx_min",
        "buy_entropy_max": "buy_entropy_max",
        "sell_rsi_min": "sell_rsi_min",
        "signal_cooldown_minutes": "signal_cooldown_minutes",
        "sl_atr_multiplier": "sl_atr_multiplier",
        "tp_atr_multiplier": "tp_atr_multiplier",
        "risk_multiplier": "risk_multiplier",
        "max_open_positions": "max_open_positions",
    }

    for field, bound_key in field_to_bound.items():
        lo, hi = LLM_SAFE_BOUNDS[bound_key]
        prop = properties.get(field, {})
        assert prop.get("minimum") == lo, (
            f"{field} minimum={prop.get('minimum')} != LLM_SAFE_BOUNDS lo={lo}"
        )
        assert prop.get("maximum") == hi, (
            f"{field} maximum={prop.get('maximum')} != LLM_SAFE_BOUNDS hi={hi}"
        )
```

4. Correr tests:
   ```bash
   cd backend && pytest tests/test_bounds_alignment.py tests/test_llm_bounds.py tests/test_daily_analyst.py -v
   ```
   Expected: green. Si `test_daily_analyst.py` falla por valores defaults
   (ej: el default era `buy_entropy_max=0.85` y ahora es `0.75`), actualizar
   los expected values en ese test pero NO cambiar las defaults nuevas (las
   defaults nuevas son intencionales).

5. Commit:
   ```bash
   git add backend/app/services/daily_analyst/models.py backend/tests/test_bounds_alignment.py
   git commit -m "refactor(daily-analyst): align PARAM_BOUNDS with LLM_SAFE_BOUNDS single source"
   ```

---

## Task 5 — Migración Supabase: `pending_approval` status

**Files:** Create `supabase/migrations/2026-04-25_pending_approval_status.sql`
(create dir if missing)

**Steps:**

1. Crear el archivo:

```sql
-- Migration: 2026-04-25 — Daily Strategist Agent foundation
-- Adds pending_approval workflow to llm_trading_configs.
-- Phase 0.5 of docs/superpowers/specs/2026-04-24-daily-strategist-agent-design.md

BEGIN;

-- Drop existing status check constraint if any
ALTER TABLE llm_trading_configs
    DROP CONSTRAINT IF EXISTS llm_trading_configs_status_check;

-- Recreate with new allowed values
ALTER TABLE llm_trading_configs
    ADD CONSTRAINT llm_trading_configs_status_check
    CHECK (status IN ('active', 'superseded', 'pending_approval', 'rejected', 'expired'));

-- Workflow columns
ALTER TABLE llm_trading_configs
    ADD COLUMN IF NOT EXISTS proposed_by text DEFAULT 'unknown';

ALTER TABLE llm_trading_configs
    ADD COLUMN IF NOT EXISTS approval_token text NULL;

ALTER TABLE llm_trading_configs
    ADD COLUMN IF NOT EXISTS approved_at timestamptz NULL;

ALTER TABLE llm_trading_configs
    ADD COLUMN IF NOT EXISTS approved_by text NULL;

ALTER TABLE llm_trading_configs
    ADD COLUMN IF NOT EXISTS rejection_reason text NULL;

-- Index for fast lookup of pending and recent rows
CREATE INDEX IF NOT EXISTS idx_llm_configs_status_created
    ON llm_trading_configs(status, created_at DESC);

COMMIT;
```

2. Aplicar la migración usando el MCP supabase. Usá la tool `apply_migration`:
   - name: `2026_04_25_pending_approval_status`
   - query: el contenido del archivo SQL arriba.

3. Verificar que el constraint se aplicó:
   - Usar tool `execute_sql` con:
     ```sql
     SELECT conname, pg_get_constraintdef(oid)
     FROM pg_constraint
     WHERE conname = 'llm_trading_configs_status_check';
     ```
   - Expected: muestra el CHECK con los 5 valores.

4. Commit:
   ```bash
   git add supabase/migrations/2026-04-25_pending_approval_status.sql
   git commit -m "feat(db): add pending_approval workflow to llm_trading_configs"
   ```

---

## Task 6 — Verificar migración aplicada (smoke test)

**Files:** none (solo verificación)

**Steps:**

1. Vía MCP supabase tool `execute_sql`:
   ```sql
   INSERT INTO llm_trading_configs (
       buy_adx_min, buy_entropy_max, buy_rsi_max, sell_rsi_min,
       signal_cooldown_minutes, sl_atr_multiplier, tp_atr_multiplier,
       risk_multiplier, max_open_positions, quant_symbols, reasoning,
       status, proposed_by
   ) VALUES (
       22.0, 0.75, 50.0, 65.0,
       180, 1.0, 2.0,
       1.0, 3, 'BTCUSDT,ETHUSDT', 'fase0 smoke test',
       'pending_approval', 'fase0_smoke'
   ) RETURNING id, status, proposed_by;
   ```
   Expected: row creada con status=pending_approval.

2. Cleanup:
   ```sql
   DELETE FROM llm_trading_configs WHERE proposed_by = 'fase0_smoke';
   ```

3. **No hay commit** para esta tarea (solo verificación).

---

## Task 7 — Endpoint Next.js `/api/admin/approve-config`

**Files:**
- Create `app/api/admin/approve-config/route.ts`
- Create `app/api/admin/_lib/token-validator.ts`

**Steps:**

1. Crear `app/api/admin/_lib/token-validator.ts`:

```typescript
import { timingSafeEqual } from "node:crypto";

/**
 * Timing-safe comparison of approval token from query string vs env var.
 * Returns false on any error (missing env, length mismatch, etc).
 */
export function validateApprovalToken(provided: string | null): boolean {
  if (!provided) return false;
  const expected = process.env.STRATEGIST_APPROVAL_TOKEN;
  if (!expected) {
    console.error("STRATEGIST_APPROVAL_TOKEN not set");
    return false;
  }
  if (provided.length !== expected.length) return false;
  try {
    return timingSafeEqual(
      Buffer.from(provided, "utf8"),
      Buffer.from(expected, "utf8"),
    );
  } catch {
    return false;
  }
}
```

2. Crear `app/api/admin/approve-config/route.ts`:

```typescript
import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@supabase/supabase-js";
import { validateApprovalToken } from "../_lib/token-validator";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  const url = new URL(req.url);
  const token = url.searchParams.get("token");
  const id = url.searchParams.get("id");

  if (!validateApprovalToken(token)) {
    return NextResponse.json({ error: "invalid_token" }, { status: 401 });
  }
  if (!id) {
    return NextResponse.json({ error: "missing_id" }, { status: 400 });
  }

  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const supabaseKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!supabaseUrl || !supabaseKey) {
    return NextResponse.json({ error: "server_misconfigured" }, { status: 500 });
  }
  const supabase = createClient(supabaseUrl, supabaseKey);

  // Fetch the pending config
  const { data: pending, error: fetchErr } = await supabase
    .from("llm_trading_configs")
    .select("id, status")
    .eq("id", id)
    .single();

  if (fetchErr || !pending) {
    return NextResponse.json({ error: "not_found" }, { status: 404 });
  }

  if (pending.status === "active") {
    return NextResponse.json({ ok: true, message: "already_active" });
  }
  if (pending.status === "rejected" || pending.status === "expired") {
    return NextResponse.json(
      { error: "already_processed", current_status: pending.status },
      { status: 409 },
    );
  }
  if (pending.status !== "pending_approval") {
    return NextResponse.json(
      { error: "invalid_state", current_status: pending.status },
      { status: 409 },
    );
  }

  const now = new Date().toISOString();

  // Supersede any other active configs first
  await supabase
    .from("llm_trading_configs")
    .update({ status: "superseded", superseded_at: now })
    .eq("status", "active");

  // Promote to active
  const { error: updateErr } = await supabase
    .from("llm_trading_configs")
    .update({
      status: "active",
      approved_at: now,
      approved_by: "telegram_inline_button",
    })
    .eq("id", id);

  if (updateErr) {
    return NextResponse.json({ error: "update_failed", detail: updateErr.message }, { status: 500 });
  }

  return NextResponse.json({ ok: true, message: "approved", id });
}
```

3. Typecheck + lint:
   ```bash
   pnpm typecheck
   pnpm lint
   ```
   Expected: clean.

4. Commit:
   ```bash
   git add app/api/admin/approve-config/route.ts app/api/admin/_lib/token-validator.ts
   git commit -m "feat(api): /api/admin/approve-config endpoint with token validation"
   ```

---

## Task 8 — Endpoint Next.js `/api/admin/reject-config`

**Files:** Create `app/api/admin/reject-config/route.ts`

**Steps:**

1. Crear el archivo:

```typescript
import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@supabase/supabase-js";
import { validateApprovalToken } from "../_lib/token-validator";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  const url = new URL(req.url);
  const token = url.searchParams.get("token");
  const id = url.searchParams.get("id");
  const reason = url.searchParams.get("reason") || "manual_reject";

  if (!validateApprovalToken(token)) {
    return NextResponse.json({ error: "invalid_token" }, { status: 401 });
  }
  if (!id) {
    return NextResponse.json({ error: "missing_id" }, { status: 400 });
  }

  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const supabaseKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!supabaseUrl || !supabaseKey) {
    return NextResponse.json({ error: "server_misconfigured" }, { status: 500 });
  }
  const supabase = createClient(supabaseUrl, supabaseKey);

  const { data: pending } = await supabase
    .from("llm_trading_configs")
    .select("id, status")
    .eq("id", id)
    .single();

  if (!pending) {
    return NextResponse.json({ error: "not_found" }, { status: 404 });
  }
  if (pending.status === "rejected") {
    return NextResponse.json({ ok: true, message: "already_rejected" });
  }
  if (pending.status !== "pending_approval") {
    return NextResponse.json(
      { error: "invalid_state", current_status: pending.status },
      { status: 409 },
    );
  }

  const { error } = await supabase
    .from("llm_trading_configs")
    .update({
      status: "rejected",
      rejection_reason: reason.slice(0, 500),
    })
    .eq("id", id);

  if (error) {
    return NextResponse.json({ error: "update_failed" }, { status: 500 });
  }
  return NextResponse.json({ ok: true, message: "rejected", id });
}
```

2. Typecheck:
   ```bash
   pnpm typecheck
   ```

3. Commit:
   ```bash
   git add app/api/admin/reject-config/route.ts
   git commit -m "feat(api): /api/admin/reject-config endpoint"
   ```

---

## Task 9 — Vercel Cron cleanup de pending expirados

**Files:**
- Create `app/api/cron/expire-pending-configs/route.ts`
- Modify `vercel.json` (agregar cron entry)

**Steps:**

1. Crear `app/api/cron/expire-pending-configs/route.ts`:

```typescript
import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@supabase/supabase-js";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  // Vercel Cron sends Authorization: Bearer <CRON_SECRET>
  const auth = req.headers.get("authorization");
  if (auth !== `Bearer ${process.env.CRON_SECRET}`) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!;
  const supabaseKey = process.env.SUPABASE_SERVICE_ROLE_KEY!;
  const supabase = createClient(supabaseUrl, supabaseKey);

  const cutoff = new Date(Date.now() - 24 * 3600 * 1000).toISOString();

  const { data, error } = await supabase
    .from("llm_trading_configs")
    .update({ status: "expired" })
    .eq("status", "pending_approval")
    .lt("created_at", cutoff)
    .select("id");

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json({
    ok: true,
    expired_count: data?.length ?? 0,
    cutoff,
  });
}
```

2. Leer `vercel.json` actual (si existe). Si NO existe, crearlo. Si existe,
   agregar entry al array `crons`:

```json
{
  "crons": [
    {
      "path": "/api/cron/expire-pending-configs",
      "schedule": "0 * * * *"
    }
  ]
}
```

   *(Si ya hay otros crons, mergear sin pisar.)*

3. Typecheck:
   ```bash
   pnpm typecheck
   ```

4. Commit:
   ```bash
   git add app/api/cron/expire-pending-configs/route.ts vercel.json
   git commit -m "feat(cron): expire pending_approval configs after 24h"
   ```

---

## Task 10 — `derivatives_client.py` con cache 5min

**Files:** Create `backend/app/services/derivatives_client.py`

**Steps:**

1. Crear archivo:

```python
"""Read-only Binance Futures derivatives data client.

Provides funding rates, open interest, and long/short ratios for spot decision
support. ALWAYS read-only — no orders are ever placed via this module.

All endpoints are public (no auth required). Rate limit: 2400/min, well above
our daily query budget. We cache responses for 5 minutes to avoid spam.
"""

import asyncio
import logging
import time
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

FAPI_BASE = "https://fapi.binance.com"
CACHE_TTL_SECONDS = 300  # 5 minutes

_cache: dict[str, tuple[float, dict]] = {}
_cache_lock = asyncio.Lock()


async def _cached_get(url: str, params: dict) -> Optional[list | dict]:
    """GET with simple TTL cache keyed by url+params."""
    cache_key = f"{url}?{sorted(params.items())}"
    async with _cache_lock:
        if cache_key in _cache:
            ts, payload = _cache[cache_key]
            if time.time() - ts < CACHE_TTL_SECONDS:
                return payload

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.warning("derivatives_client GET failed: %s — %s", url, e)
        return None

    async with _cache_lock:
        _cache[cache_key] = (time.time(), data)
    return data


async def get_funding_rate_history(symbol: str, limit: int = 50) -> Optional[list]:
    """Recent funding rate history. Returns list of {symbol, fundingTime, fundingRate}."""
    url = f"{FAPI_BASE}/fapi/v1/fundingRate"
    return await _cached_get(url, {"symbol": symbol, "limit": limit})


async def get_open_interest(symbol: str) -> Optional[dict]:
    """Current open interest. Returns {symbol, openInterest, time}."""
    url = f"{FAPI_BASE}/fapi/v1/openInterest"
    return await _cached_get(url, {"symbol": symbol})


async def get_open_interest_hist(symbol: str, period: str = "1h", limit: int = 24) -> Optional[list]:
    """Historical open interest. period: 5m, 15m, 30m, 1h, 2h, 4h, 6h, 12h, 1d."""
    url = f"{FAPI_BASE}/futures/data/openInterestHist"
    return await _cached_get(url, {"symbol": symbol, "period": period, "limit": limit})


async def get_top_long_short_account_ratio(symbol: str, period: str = "1h", limit: int = 24) -> Optional[list]:
    """Top trader accounts long/short ratio."""
    url = f"{FAPI_BASE}/futures/data/topLongShortAccountRatio"
    return await _cached_get(url, {"symbol": symbol, "period": period, "limit": limit})


async def get_top_long_short_position_ratio(symbol: str, period: str = "1h", limit: int = 24) -> Optional[list]:
    """Top trader positions long/short ratio."""
    url = f"{FAPI_BASE}/futures/data/topLongShortPositionRatio"
    return await _cached_get(url, {"symbol": symbol, "period": period, "limit": limit})


async def get_derivatives_snapshot(symbol: str) -> dict:
    """Aggregated derivatives view for a symbol — used by quant_orchestrator.

    Returns normalized dict; missing fields are None on partial failures.
    """
    funding, oi_now, oi_hist, ls_acct = await asyncio.gather(
        get_funding_rate_history(symbol, limit=10),
        get_open_interest(symbol),
        get_open_interest_hist(symbol, period="1h", limit=24),
        get_top_long_short_account_ratio(symbol, period="1h", limit=24),
        return_exceptions=False,
    )

    out = {
        "symbol": symbol,
        "funding_rate_current": None,
        "funding_rate_8h_avg": None,
        "funding_rate_trend": None,
        "oi_current_usd": None,
        "oi_change_24h_pct": None,
        "long_short_ratio_24h_avg": None,
        "long_short_ratio_inverting": None,
    }

    if funding and isinstance(funding, list) and len(funding) > 0:
        rates = [float(r["fundingRate"]) for r in funding if "fundingRate" in r]
        if rates:
            out["funding_rate_current"] = rates[0]
            if len(rates) >= 3:
                out["funding_rate_8h_avg"] = sum(rates[:3]) / 3
            if len(rates) >= 5:
                recent3 = sum(rates[:3]) / 3
                older3 = sum(rates[2:5]) / 3
                if recent3 > older3 * 1.1:
                    out["funding_rate_trend"] = "rising"
                elif recent3 < older3 * 0.9:
                    out["funding_rate_trend"] = "falling"
                else:
                    out["funding_rate_trend"] = "neutral"

    if oi_now and "openInterest" in oi_now:
        try:
            out["oi_current_usd"] = float(oi_now["openInterest"])
        except (TypeError, ValueError):
            pass

    if oi_hist and isinstance(oi_hist, list) and len(oi_hist) >= 2:
        try:
            latest = float(oi_hist[-1]["sumOpenInterest"])
            oldest = float(oi_hist[0]["sumOpenInterest"])
            if oldest > 0:
                out["oi_change_24h_pct"] = (latest - oldest) / oldest * 100.0
        except (TypeError, ValueError, KeyError):
            pass

    if ls_acct and isinstance(ls_acct, list) and len(ls_acct) >= 5:
        try:
            ratios = [float(r["longShortRatio"]) for r in ls_acct]
            out["long_short_ratio_24h_avg"] = sum(ratios) / len(ratios)
            recent = sum(ratios[-3:]) / 3
            older = sum(ratios[:3]) / 3
            out["long_short_ratio_inverting"] = (
                (recent < 1.0 and older > 1.0) or (recent > 1.0 and older < 1.0)
            )
        except (TypeError, ValueError, KeyError):
            pass

    return out
```

2. Verificar que importa OK:
   ```bash
   cd backend && python -c "from app.services.derivatives_client import get_derivatives_snapshot; print('ok')"
   ```

3. Commit:
   ```bash
   git add backend/app/services/derivatives_client.py
   git commit -m "feat(derivatives): Binance Futures read-only client with 5min cache"
   ```

---

## Task 11 — Tests para `derivatives_client`

**Files:** Create `backend/tests/test_derivatives_client.py`

**Steps:**

1. Crear:

```python
"""Tests for derivatives_client. Uses respx for HTTP mocking."""

import pytest
from unittest.mock import patch, AsyncMock


@pytest.mark.asyncio
async def test_get_derivatives_snapshot_normalized():
    """Snapshot returns expected shape with mocked Binance responses."""
    fake_funding = [
        {"symbol": "BTCUSDT", "fundingTime": 1, "fundingRate": "0.0001"},
        {"symbol": "BTCUSDT", "fundingTime": 2, "fundingRate": "0.0001"},
        {"symbol": "BTCUSDT", "fundingTime": 3, "fundingRate": "0.0001"},
        {"symbol": "BTCUSDT", "fundingTime": 4, "fundingRate": "0.00008"},
        {"symbol": "BTCUSDT", "fundingTime": 5, "fundingRate": "0.00008"},
    ]
    fake_oi_now = {"symbol": "BTCUSDT", "openInterest": "1000000.0", "time": 1}
    fake_oi_hist = [
        {"symbol": "BTCUSDT", "sumOpenInterest": "950000", "timestamp": 1},
        {"symbol": "BTCUSDT", "sumOpenInterest": "1000000", "timestamp": 24},
    ]
    fake_ls = [
        {"symbol": "BTCUSDT", "longShortRatio": "1.2", "timestamp": 1},
        {"symbol": "BTCUSDT", "longShortRatio": "1.3", "timestamp": 2},
        {"symbol": "BTCUSDT", "longShortRatio": "1.4", "timestamp": 3},
        {"symbol": "BTCUSDT", "longShortRatio": "1.5", "timestamp": 4},
        {"symbol": "BTCUSDT", "longShortRatio": "1.6", "timestamp": 5},
    ]

    from app.services import derivatives_client as mod
    # Reset cache between tests
    mod._cache.clear()

    async def fake_get(url, params):
        if "fundingRate" in url:
            return fake_funding
        if url.endswith("/openInterest"):
            return fake_oi_now
        if "openInterestHist" in url:
            return fake_oi_hist
        if "topLongShortAccountRatio" in url:
            return fake_ls
        return None

    with patch.object(mod, "_cached_get", side_effect=fake_get):
        snap = await mod.get_derivatives_snapshot("BTCUSDT")

    assert snap["symbol"] == "BTCUSDT"
    assert snap["funding_rate_current"] == pytest.approx(0.0001)
    assert snap["funding_rate_8h_avg"] == pytest.approx(0.0001)
    # 5.26% change from 950k -> 1M
    assert snap["oi_change_24h_pct"] == pytest.approx(5.263, abs=0.01)
    assert snap["oi_current_usd"] == 1_000_000.0
    assert snap["long_short_ratio_24h_avg"] == pytest.approx(1.4)


@pytest.mark.asyncio
async def test_get_derivatives_snapshot_partial_failure():
    """If funding fails, other fields still populate."""
    from app.services import derivatives_client as mod
    mod._cache.clear()

    async def fake_get(url, params):
        if "fundingRate" in url:
            return None  # fail
        if url.endswith("/openInterest"):
            return {"symbol": "ETHUSDT", "openInterest": "500000.0", "time": 1}
        return None

    with patch.object(mod, "_cached_get", side_effect=fake_get):
        snap = await mod.get_derivatives_snapshot("ETHUSDT")

    assert snap["funding_rate_current"] is None
    assert snap["oi_current_usd"] == 500_000.0
```

2. Run:
   ```bash
   cd backend && pytest tests/test_derivatives_client.py -v
   ```
   Expected: green.

3. Commit:
   ```bash
   git add backend/tests/test_derivatives_client.py
   git commit -m "test(derivatives): unit tests for derivatives_client snapshot"
   ```

---

## Task 12 — Integrar derivatives en `quant_orchestrator.get_quant_snapshot`

**Files:** Modify `backend/app/services/quant_orchestrator.py`

**Steps:**

1. Leer `backend/app/services/quant_orchestrator.py` para entender el shape
   actual de `get_quant_snapshot()`. Identificar el dict/Pydantic model retornado.

2. Agregar al dict/model output un campo `derivatives` poblado con
   `await get_derivatives_snapshot(symbol)`. La integración es:
   - Import al top: `from .derivatives_client import get_derivatives_snapshot`
   - Antes del return final del snapshot, agregar:
     ```python
     try:
         derivatives = await get_derivatives_snapshot(symbol)
     except Exception as e:
         logger.warning("derivatives snapshot failed for %s: %s", symbol, e)
         derivatives = None
     ```
   - Sumar `derivatives` al dict/model retornado.

3. Si `get_quant_snapshot` retorna un Pydantic model: agregar campo opcional al
   model:
   ```python
   derivatives: Optional[dict] = None
   ```

4. Verificar que tests existentes pasan:
   ```bash
   cd backend && pytest tests/ -q --tb=short
   ```

5. Commit:
   ```bash
   git add backend/app/services/quant_orchestrator.py
   git commit -m "feat(quant): include derivatives data in quant snapshot"
   ```

---

## Task 13 — Smoke test contra Binance Futures real

**Files:** Create `backend/scripts/smoke_derivatives.py`

**Steps:**

1. Crear:

```python
"""Smoke test: hit Binance Futures public endpoints, print derivatives snapshot.

Run from backend dir: python scripts/smoke_derivatives.py BTCUSDT
"""
import asyncio
import json
import sys

from app.services.derivatives_client import get_derivatives_snapshot


async def main():
    symbol = sys.argv[1] if len(sys.argv) > 1 else "BTCUSDT"
    snap = await get_derivatives_snapshot(symbol)
    print(json.dumps(snap, indent=2, default=str))

    # Sanity assertions
    assert snap["symbol"] == symbol
    assert snap["funding_rate_current"] is not None, "Funding data missing"
    assert snap["oi_current_usd"] is not None, "OI data missing"
    print("\nAll checks PASSED.")


if __name__ == "__main__":
    asyncio.run(main())
```

2. Correr:
   ```bash
   cd backend && python scripts/smoke_derivatives.py BTCUSDT
   ```
   Expected: JSON con valores numéricos, "All checks PASSED" al final.
   Si falla por network: NO ES bloqueante. Marcar como NETWORK_BLOCKED en
   el reporte.

3. Commit:
   ```bash
   git add backend/scripts/smoke_derivatives.py
   git commit -m "chore(derivatives): smoke test script for live binance futures"
   ```

---

## Task 14 — Migración DB para partial exit

**Files:** Create `supabase/migrations/2026-04-25_partial_exit_columns.sql`

**Steps:**

1. Crear:

```sql
-- Migration: 2026-04-25 — Partial exit tracking columns on positions.
-- Phase 0.3 of docs/superpowers/specs/2026-04-24-daily-strategist-agent-design.md

BEGIN;

ALTER TABLE positions
    ADD COLUMN IF NOT EXISTS partial_exit_taken boolean DEFAULT false NOT NULL;

ALTER TABLE positions
    ADD COLUMN IF NOT EXISTS partial_exit_price numeric(18, 8) NULL;

ALTER TABLE positions
    ADD COLUMN IF NOT EXISTS partial_exit_qty numeric(18, 8) NULL;

ALTER TABLE positions
    ADD COLUMN IF NOT EXISTS partial_exit_at timestamptz NULL;

CREATE INDEX IF NOT EXISTS idx_positions_partial_exit
    ON positions(partial_exit_taken)
    WHERE status = 'open';

COMMIT;
```

2. Aplicar via MCP supabase `apply_migration`:
   - name: `2026_04_25_partial_exit_columns`
   - query: contenido del archivo.

3. Verificar:
   ```sql
   SELECT column_name, data_type, is_nullable, column_default
   FROM information_schema.columns
   WHERE table_name = 'positions'
     AND column_name LIKE 'partial_exit%';
   ```
   Expected: 4 rows.

4. Commit:
   ```bash
   git add supabase/migrations/2026-04-25_partial_exit_columns.sql
   git commit -m "feat(db): partial exit tracking columns on positions"
   ```

---

## Task 15 — Feature flags en `Settings`

**Files:** Modify `backend/app/config.py`

**Steps:**

1. En la clase `Settings` de `backend/app/config.py`, agregar:

```python
    # ── Phase 0.3: Partial exit + Chandelier experiments ──
    partial_exit_enabled: bool = False  # Off by default until A/B validates
    partial_exit_fraction: float = 0.5  # 50% taken at 1R
    partial_exit_at_r: float = 1.0      # trigger at +1R
    chandelier_k: float = 2.0           # 2.0 current; research suggests 3.0 classic
```

2. Verificar:
   ```bash
   cd backend && python -c "from app.config import settings; print(settings.partial_exit_enabled, settings.chandelier_k)"
   ```
   Expected: `False 2.0`

3. Commit:
   ```bash
   git add backend/app/config.py
   git commit -m "feat(config): partial_exit and chandelier_k feature flags"
   ```

---

## Task 16 — Tests para partial exit logic

**Files:** Create `backend/tests/test_partial_exit.py`

**Steps:**

1. Crear el test ANTES de la implementación:

```python
"""Tests for partial exit logic in trading_loop._maybe_take_partial_exit.

Behavior under test:
- When PARTIAL_EXIT_ENABLED=false: nothing happens, returns False.
- When current_price < entry + 1R: returns False, no DB write.
- When current_price >= entry + 1R AND partial_exit_taken=False:
    - Marks partial_exit_taken=True, partial_exit_price, partial_exit_qty=50% of current_quantity.
    - Moves SL to breakeven (entry_price).
    - Returns True.
- When partial_exit_taken=True already: returns False (idempotent).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture
def base_position():
    return {
        "id": "pos-uuid",
        "symbol": "BTCUSDT",
        "entry_price": 100.0,
        "stop_loss_price": 95.0,
        "take_profit_price": 110.0,
        "current_quantity": 1.0,
        "partial_exit_taken": False,
    }


@pytest.mark.asyncio
async def test_partial_exit_disabled_returns_false(base_position):
    from app.services.trading_loop import _maybe_take_partial_exit
    with patch("app.services.trading_loop.settings") as s:
        s.partial_exit_enabled = False
        s.partial_exit_fraction = 0.5
        s.partial_exit_at_r = 1.0
        result = await _maybe_take_partial_exit(MagicMock(), base_position, current_price=110.0)
    assert result is False


@pytest.mark.asyncio
async def test_partial_exit_below_1R_returns_false(base_position):
    from app.services.trading_loop import _maybe_take_partial_exit
    # entry=100, sl=95 → R=5. 1R = 105. current=104 → no trigger.
    with patch("app.services.trading_loop.settings") as s:
        s.partial_exit_enabled = True
        s.partial_exit_fraction = 0.5
        s.partial_exit_at_r = 1.0
        result = await _maybe_take_partial_exit(MagicMock(), base_position, current_price=104.0)
    assert result is False


@pytest.mark.asyncio
async def test_partial_exit_at_or_above_1R_triggers(base_position):
    from app.services.trading_loop import _maybe_take_partial_exit
    supabase = MagicMock()
    # Simulate update + insert succeeding.
    supabase.table().update().eq().execute.return_value = MagicMock(data=[base_position])
    supabase.table().insert().execute.return_value = MagicMock(data=[{"id": "prop-1"}])

    with patch("app.services.trading_loop.settings") as s, \
         patch("app.services.trading_loop._execute_sl_tp", new=AsyncMock()):
        s.partial_exit_enabled = True
        s.partial_exit_fraction = 0.5
        s.partial_exit_at_r = 1.0
        # entry=100, sl=95 → R=5. 1R = 105. current=105 → trigger.
        result = await _maybe_take_partial_exit(supabase, base_position, current_price=105.0)

    assert result is True


@pytest.mark.asyncio
async def test_partial_exit_idempotent_when_already_taken(base_position):
    base_position["partial_exit_taken"] = True
    from app.services.trading_loop import _maybe_take_partial_exit
    with patch("app.services.trading_loop.settings") as s:
        s.partial_exit_enabled = True
        s.partial_exit_fraction = 0.5
        s.partial_exit_at_r = 1.0
        result = await _maybe_take_partial_exit(MagicMock(), base_position, current_price=999.0)
    assert result is False
```

2. Correr — debe FALLAR (función no existe todavía):
   ```bash
   cd backend && pytest tests/test_partial_exit.py -v
   ```
   Expected: ImportError o "function not defined".

3. Commit:
   ```bash
   git add backend/tests/test_partial_exit.py
   git commit -m "test(partial-exit): failing tests for partial exit at 1R"
   ```

---

## Task 17 — Implementar `_maybe_take_partial_exit` en `trading_loop.py`

**Files:** Modify `backend/app/services/trading_loop.py`

**Steps:**

1. Agregar una nueva función async cerca de `_execute_sl_tp` y `_update_trailing_stop`:

```python
async def _maybe_take_partial_exit(
    supabase, position: dict, current_price: float
) -> bool:
    """If current_price >= entry + 1R, sell partial_exit_fraction and move SL to breakeven.

    Returns True if a partial exit was triggered, False otherwise.
    Feature-flagged by settings.partial_exit_enabled.
    Idempotent: if position.partial_exit_taken is already True, no-op.
    """
    from ..config import settings

    if not settings.partial_exit_enabled:
        return False
    if position.get("partial_exit_taken"):
        return False

    entry = float(position.get("entry_price") or 0)
    sl = float(position.get("stop_loss_price") or 0)
    if entry <= 0 or sl <= 0 or sl >= entry:
        return False

    r = entry - sl
    threshold = entry + settings.partial_exit_at_r * r
    if current_price < threshold:
        return False

    qty_total = float(position.get("current_quantity") or 0)
    if qty_total <= 0:
        return False

    partial_qty = round_quantity(position["symbol"], qty_total * settings.partial_exit_fraction)
    if partial_qty <= 0:
        return False

    logger.warning(
        "PARTIAL_EXIT [%s] price=%.4f >= 1R threshold=%.4f — selling %s of %s, moving SL to breakeven",
        position["symbol"], current_price, threshold, partial_qty, qty_total,
    )

    now = datetime.now(timezone.utc).isoformat()

    # Mark position as partial-exit-taken AND move SL to breakeven on the runner.
    supabase.table("positions").update({
        "partial_exit_taken": True,
        "partial_exit_price": current_price,
        "partial_exit_qty": partial_qty,
        "partial_exit_at": now,
        "stop_loss_price": entry,  # breakeven on remainder
    }).eq("id", position["id"]).execute()

    # Create a sell proposal for the partial qty.
    insert = {
        "type": "sell",
        "symbol": position["symbol"],
        "quantity": partial_qty,
        "price": current_price,
        "order_type": "MARKET",
        "notional": partial_qty * current_price,
        "status": "approved",
        "reasoning": f"[PARTIAL_EXIT_1R] Auto @ ${current_price:,.2f}",
        "risk_score": 0,
        "risk_checks": [],
        "auto_approved": True,
        "retry_count": 0,
        "created_at": now,
        "updated_at": now,
        "approved_at": now,
    }
    resp = supabase.table("trade_proposals").insert(insert).execute()
    if not resp.data:
        logger.error("Failed to create partial-exit proposal for %s", position["symbol"])
        return False

    proposal_id = resp.data[0]["id"]

    try:
        from .telegram_notifier import send_telegram
        pnl = (current_price - entry) * partial_qty
        await send_telegram(
            f"💰 <b>PARTIAL EXIT 1R: {position['symbol']}</b>\n"
            f"Entry: ${entry:,.4f} → Partial: ${current_price:,.4f}\n"
            f"Qty: {partial_qty} ({int(settings.partial_exit_fraction*100)}%)\n"
            f"PnL parcial: ${pnl:+.2f}\n"
            f"SL movido a breakeven en runner restante."
        )
    except Exception:
        pass

    from .executor import execute_proposal
    await execute_proposal(proposal_id)
    return True
```

2. Llamar `_maybe_take_partial_exit` desde el loop principal de SL/TP en
   `_check_stop_losses` (cerca de línea 188 en el archivo actual). Antes del
   bloque `if triggered:` agregar:

```python
            # Phase 0.3: Partial exit at 1R (feature-flagged)
            partial_taken = await _maybe_take_partial_exit(supabase, pos, current_price)
            if partial_taken:
                # Re-fetch position for updated SL+qty before continuing checks
                refreshed = supabase.table("positions").select("*").eq("id", pos["id"]).single().execute()
                if refreshed.data:
                    pos = refreshed.data
                    sl = float(pos["stop_loss_price"]) if pos.get("stop_loss_price") else None
```

3. Hacer Chandelier `k` configurable. Buscar la línea con `compute_chandelier_sl(current_price, ind.atr_14, 2.0)` (cerca línea 330) y reemplazar por:

```python
            chandelier_sl = compute_chandelier_sl(current_price, ind.atr_14, settings.chandelier_k)
```

4. Run tests:
   ```bash
   cd backend && pytest tests/test_partial_exit.py tests/test_executor_sltp.py tests/ -q --tb=short
   ```
   Expected: green.

5. Commit:
   ```bash
   git add backend/app/services/trading_loop.py
   git commit -m "feat(trading): partial exit 50% at 1R + configurable chandelier k (off by default)"
   ```

---

## Task 18 — Documento de A/B test plan

**Files:** Create `docs/knowledge-base/research/2026-04-25-partial-exit-ab-plan.md`

**Steps:**

1. Crear:

```markdown
---
date: 2026-04-25
type: experiment-plan
status: ready
related_spec: docs/superpowers/specs/2026-04-24-daily-strategist-agent-design.md
---

# Partial Exit 50% @ 1R — A/B Test Plan

## Hypothesis

Partial exit 50% del position size cuando current_price >= entry + 1R, con
SL del runner movido a breakeven, captura ganancia mientras el trailing
chandelier se encarga del resto.

Síntoma a atacar: 78% STOP_LOSS / 3% TAKE_PROFIT histórico (200 últimas
proposals). Si la hipótesis funciona, ratio mejora.

## Pre-requisito

Phase 0.1 cumplida: drift del proxy < 1% en >90% de los últimos 10-20 trades
post-redeploy de `f6ba148`.

## Plan

### Baseline (Variant A) — `PARTIAL_EXIT_ENABLED=false`
- Acumular 30 trades cerrados con flag OFF.
- Métricas a guardar (script ad-hoc o consulta SQL):
  - P&L medio por trade
  - Win rate
  - Profit factor
  - SL hit %, TP hit %, signal exit %
  - Drawdown máximo

### Variant B — `PARTIAL_EXIT_ENABLED=true`
- Setear flag en `.env` del backend (Dokploy) y redeploy.
- Acumular 30 trades cerrados.
- Mismas métricas.

### Decisión

Mantener `PARTIAL_EXIT_ENABLED=true` si y solo si:
- P&L medio mejora >=10% vs baseline.
- Drawdown no aumenta >20%.
- Variant B no introduce nuevos bugs (errores en logs).

Si no se cumple, revertir a OFF y documentar resultado.

## Chandelier 3ATR experiment (post-A/B)

Después del A/B partial exit, considerar segundo experimento:
`CHANDELIER_K=3.0` (clásico 22-period × 3ATR) vs `2.0` actual.

Mismo formato: 30 trades pre vs 30 trades post.

## Notes

- No correr ambos experimentos en paralelo.
- No tocar otros parámetros durante un experimento.
- Documentar resultado en `evaluations/YYYY-MM-DD-partial-exit-ab.md`.
```

2. Commit:
   ```bash
   git add docs/knowledge-base/research/2026-04-25-partial-exit-ab-plan.md
   git commit -m "docs(research): A/B test plan for partial exit 1R"
   ```

---

## Task 19 — Helper script `scripts/check-proxy-drift.py`

**Files:** Create `backend/scripts/check_proxy_drift.py`

**Steps:**

1. Crear:

```python
"""Phase 0.1 — Proxy drift check.

Reads recent SL/TP-triggered trades from Supabase, compares trigger_price vs
executed price, reports drift.

Pass criteria: >90% of last N trades have abs(drift) < 1%.

Usage: python scripts/check_proxy_drift.py [--limit 20]
"""

import argparse
import asyncio
import json

from app.db import get_supabase


async def main(limit: int = 20):
    supabase = get_supabase()

    # Fetch last N closed positions with stop_loss_price set
    resp = (
        supabase.table("positions")
        .select("id,symbol,entry_price,stop_loss_price,exit_price,realized_pnl_percent,closed_at,close_reason")
        .eq("status", "closed")
        .not_.is_("stop_loss_price", "null")
        .not_.is_("exit_price", "null")
        .order("closed_at", desc=True)
        .limit(limit)
        .execute()
    )
    rows = resp.data or []
    if not rows:
        print(json.dumps({"error": "no closed trades"}))
        return 1

    drifts = []
    for r in rows:
        sl = float(r.get("stop_loss_price") or 0)
        ex = float(r.get("exit_price") or 0)
        if sl <= 0 or ex <= 0:
            continue
        pct = abs(sl - ex) / ex * 100.0
        drifts.append({
            "symbol": r["symbol"],
            "sl": sl,
            "exit": ex,
            "drift_pct": round(pct, 3),
            "close_reason": r.get("close_reason"),
            "closed_at": r.get("closed_at"),
        })

    over_1pct = [d for d in drifts if d["drift_pct"] > 1.0]
    pct_over = len(over_1pct) / max(1, len(drifts)) * 100.0
    passed = pct_over <= 10.0  # <=10% over 1% drift = >=90% under 1%

    out = {
        "n_trades": len(drifts),
        "n_over_1pct": len(over_1pct),
        "pct_over_1pct": round(pct_over, 1),
        "passed": passed,
        "trades": drifts,
    }
    print(json.dumps(out, indent=2, default=str))
    return 0 if passed else 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.limit)))
```

2. Smoke run:
   ```bash
   cd backend && python scripts/check_proxy_drift.py --limit 20
   ```
   Expected: JSON con `passed`, `pct_over_1pct`, lista de trades. Si Supabase
   no es accesible localmente, marcar NETWORK_BLOCKED y continuar.

3. Commit:
   ```bash
   git add backend/scripts/check_proxy_drift.py
   git commit -m "feat(checks): proxy drift gate script for phase 0.1"
   ```

---

## Task 20 — Feature flag `LANGGRAPH_DAILY_ENABLED` (decommission prep)

**Files:**
- Modify `backend/app/config.py`
- Modify `backend/app/main.py` (donde llama el scheduler del LangGraph)

**Steps:**

1. En `backend/app/config.py` `Settings`, agregar:

```python
    # ── Phase 0.6: LangGraph daily_analyst decommission flag ──
    # Default true while we observe Strategist Agent in dry-run.
    # Set to false in env once Strategist has 7 OK days.
    langgraph_daily_enabled: bool = True
```

2. Buscar en `backend/app/main.py` (o donde corra el scheduler del LangGraph)
   las llamadas a `should_run_pre_market` / `run_pre_market_analysis` y
   `should_run_post_market` / `run_post_market_audit`. Envolverlas:

```python
    if settings.langgraph_daily_enabled:
        if should_run_pre_market(now):
            await run_pre_market_analysis()
        if should_run_post_market(now):
            await run_post_market_audit()
```

3. Tests existentes pasan:
   ```bash
   cd backend && pytest tests/ -q --tb=short
   ```

4. Commit:
   ```bash
   git add backend/app/config.py backend/app/main.py
   git commit -m "feat(config): LANGGRAPH_DAILY_ENABLED flag for phase 0.6 decommission prep"
   ```

---

## Task 21 — Documento de decommission timeline

**Files:** Create `docs/knowledge-base/research/2026-04-25-langgraph-decommission-plan.md`

**Steps:**

1. Crear:

```markdown
---
date: 2026-04-25
type: decommission-plan
status: ready
related_spec: docs/superpowers/specs/2026-04-24-daily-strategist-agent-design.md
phase: 0.6
---

# LangGraph daily_analyst — Decommission Plan

## Status

LangGraph daily_analyst (`backend/app/services/daily_analyst/`) sigue activo.
Plan de pausa graceful durante el rollout del Claude Strategist Agent.

## Timeline

| Día | Acción | Quién |
|---|---|---|
| Día -7 a Día 0 | Strategist en dry-run en local. LangGraph sigue. | Auto + manual |
| Día 0 (= Strategist 7 días OK) | Set `LANGGRAPH_DAILY_ENABLED=false` en Dokploy env. Redeploy. | Manual usuario |
| Día +1 a +14 | Verificar que `llm_trading_configs` recibe rows solo de `proposed_by='strategist'`. | Manual |
| Día +14 | Si Strategist sigue OK, eliminar `backend/app/services/daily_analyst/` entero. Limpieza imports. | Manual |
| Día +14 | Tabla `llm_audit_reports` queda como histórico read-only. NO se borra. | — |

## Rollback

Si Strategist falla en cualquier momento entre Día 0 y Día +14:
1. Set `LANGGRAPH_DAILY_ENABLED=true` en Dokploy env.
2. Redeploy backend.
3. LangGraph retoma operación normal.

## Riesgo de no-fallback post Día +14

Después de eliminar el código del LangGraph no hay rollback automático.
Si Strategist falla, backend cae a defaults de `config.py` (comportamiento
existente cuando `llm_trading_configs` no tiene `status=active`).

Watchdog Vercel Cron alertará vía Telegram si Strategist >36h sin run.

## Métricas de éxito Strategist (gate para Día 0)

- 7 días seguidos generando eval markdown sin fallar.
- Cada run produce: eval + pending_approval row + Telegram + heartbeat.
- Costo medio <$1.50/día.
- Cero modificaciones a `status=active` por el agente.
- Aprobaciones manuales registradas con razón.
```

2. Commit:
   ```bash
   git add docs/knowledge-base/research/2026-04-25-langgraph-decommission-plan.md
   git commit -m "docs(research): LangGraph decommission timeline and rollback plan"
   ```

---

# Reporte final

Cuando termines (o quedes BLOCKED en algo crítico), reportá con esta estructura
en un único mensaje al usuario:

```
# Fase 0 — Reporte de ejecución

## Status global
- Tareas completadas: X/21
- Tareas BLOCKED: N (listadas abajo)
- Tiempo total: HH:MM

## Commits creados
<lista de hashes y mensajes, en orden>

## Tareas BLOCKED
### Task X.Y — <nombre>
**Razón**: <explicación corta>
**Estado del repo**: <qué quedó hecho/no hecho>
**Próximo paso recomendado**: <qué debería hacer el humano>

## Quality gates finales
- backend pytest: <PASS/FAIL — N tests>
- pnpm typecheck: <PASS/FAIL>
- pnpm lint: <PASS/FAIL>
- git status: <clean / archivos pendientes>

## Recomendaciones para Fase 1
<2-3 puntos cortos basados en lo que encontraste implementando Fase 0>
```

# Reglas de oro para el agente

1. **No improvises arquitectura**. El spec manda. Si algo no está claro, leé
   más código antes de decidir, no preguntes al usuario.
2. **Tests primero, siempre**.
3. **Commits chicos**. Una tarea = un commit. Mensajes claros.
4. **No tocar lo no listado**. Si ves un bug en otro lado, anotá en
   `docs/knowledge-base/research/gaps.md` pero NO arregles fuera de scope.
5. **Read antes de Write**. Cuando el spec dice "modify X:Y-Z", leé esas
   líneas primero. El código pudo cambiar.
6. **Si pytest tiene `Supabase env not set` errors**: probablemente faltan
   env vars en local. NO seteás creds en commit. Marcá esos tests como
   skipped local y seguí. La verificación final se hace cuando corre el CI.
