# Implementación Pendiente - Motor Cuantitativo Wall Street
> Fecha de auditoría: 2026-02-17
> Para implementar por: Claude Opus 4.6
> Repo: `D:\OneDrive\GitHub\traiding-agentic`

---

## Estado Actual - Resumen del Audit

### ✅ COMPLETAMENTE IMPLEMENTADO

**Backend Python (18 archivos nuevos)**
- `backend/app/services/quant_cache.py` - LRU cache con TTL
- `backend/app/services/kline_collector.py` - Fetch + store OHLCV
- `backend/app/services/technical_analysis.py` - Indicadores con pandas-ta-classic
- `backend/app/services/entropy_filter.py` - Shannon entropy filter
- `backend/app/services/support_resistance.py` - K-Means S/R levels
- `backend/app/services/regime_detector.py` - Detector de régimen (ADX + Hurst)
- `backend/app/services/position_sizer.py` - Kelly + ATR sizing
- `backend/app/services/quant_risk.py` - 8 risk checks (5 base + 3 quant)
- `backend/app/services/quant_orchestrator.py` - Coordinador central con ticks
- `backend/app/services/backtester.py` - Backtester manual (sin VectorBT)
- `backend/app/routers/klines.py` - GET/{symbol}, POST/backfill, GET/status/all
- `backend/app/routers/indicators.py` - GET/{symbol}
- `backend/app/routers/analysis.py` - GET/{symbol} (completo con régimen + sizing), GET/{symbol}/entropy
- `backend/app/routers/backtest.py` - POST/run, GET/results
- `backend/app/routers/quant_status.py` - GET/status, GET/performance, GET/health, GET/snapshot/{symbol}
- `backend/app/models/quant_models.py` - Pydantic models completos
- `backend/app/models/__init__.py` - Re-exports

**Backend Python (7 archivos modificados)**
- `backend/requirements.txt` - pandas-ta-classic, numpy>=2.0.0, scipy, scikit-learn
- `backend/app/config.py` - Todos los settings quant
- `backend/app/services/binance_client.py` - `get_klines()` en línea 95
- `backend/app/services/trading_loop.py` - Llama `run_quant_tick()` en cada ciclo
- `backend/app/main.py` - Registra los 5 routers nuevos
- `backend/app/routers/proposals.py` - Usa `validate_proposal_enhanced`

**Frontend TypeScript**
- `lib/trading/python-backend.ts` - 10+ funciones proxy (getQuantAnalysis, getIndicators, etc.)
- `lib/agents/trading-agent.ts` - Inyecta QUANT_ANALYSIS completo en prompt LLM
- `lib/agents/prompts.ts` - TRADING_AGENT_PROMPT con instrucciones quant (entropy gate, regime, S/R)

**Infraestructura**
- `supabase/migrations/20260217_quant_engine_tables.sql` - 7 tablas + risk_events update
- `vercel.json` - Cron cada 5 minutos + maxDuration configurado
- `.env.example` - PYTHON_BACKEND_URL documentado
- VPS: Engine corriendo, 30 días de klines backfilled, verificado E2E

---

## ❌ PENDIENTE - Checklist para Opus 4.6

---

## FASE A: Tests y Validación (ALTA PRIORIDAD)

El plan dice explícitamente: *"Unit test: Cada módulo Python tiene tests con datos mock"*. No existe ningún archivo de test Python.

### A.1 - Crear estructura de tests Python

**Crear directorio**: `backend/tests/`

**Archivos a crear**:
```
backend/tests/
├── __init__.py
├── conftest.py                          # Fixtures compartidos (mock supabase, mock binance)
├── test_quant_cache.py                  # TTLCache: set, get, expiry, LRU eviction
├── test_kline_collector.py              # parse_kline, backfill con mock HTTP
├── test_technical_analysis.py           # compute_indicators con DataFrame mock
├── test_entropy_filter.py               # compute_entropy con returns mock
├── test_support_resistance.py           # compute_sr_levels con precios mock
├── test_regime_detector.py              # detect_regime con indicadores mock
├── test_position_sizer.py               # compute_position_size con trades mock
├── test_quant_risk.py                   # validate_proposal_enhanced: todos los 8 checks
└── test_orchestrator.py                 # run_quant_tick con mocks
```

**`backend/tests/conftest.py`** debe incluir:
```python
# Fixtures:
# - mock_supabase: MagicMock que devuelve datos de prueba
# - sample_klines_df: DataFrame con 200 candles de BTCUSDT (precios sintéticos)
# - sample_indicators: TechnicalIndicators con valores conocidos
# - mock_binance_response: dict con precio mock
```

**`backend/tests/test_entropy_filter.py`** ejemplo mínimo:
```python
def test_compute_entropy_noisy_market(sample_klines_df, mock_supabase):
    """Mercado ruidoso → is_tradable=False"""
    # Generar returns completamente aleatorios (entropia maxima)
    # entropy_ratio debe ser > 0.85
    ...

def test_compute_entropy_trending_market(sample_klines_df, mock_supabase):
    """Mercado en tendencia → is_tradable=True"""
    # Returns con tendencia clara (entropia baja)
    ...
```

**`backend/tests/test_quant_risk.py`** debe verificar los 8 checks:
1. `max_position_size` (base) - rechaza si notional > límite
2. `daily_loss_limit` (base) - rechaza si pérdida diaria excedida
3. `max_open_positions` (base) - rechaza si demasiadas posiciones
4. `drawdown_limit` (base) - rechaza si drawdown excesivo
5. `min_notional` (base) - rechaza si notional < mínimo
6. `entropy_gate` (quant) - rechaza si mercado ruidoso
7. `regime_check` (quant) - rechaza trade contra-tendencia en trend fuerte / bloquea en volatile
8. `kelly_size_validation` (quant) - rechaza si notional > 1.5x recomendado

**Instrucciones de ejecución**:
```bash
cd backend
pip install pytest pytest-asyncio
pytest tests/ -v
```

---

## FASE B: Performance Metrics Completos (ALTA PRIORIDAD)

### B.1 - Agregar métricas rolling 30d y 7d

**Archivo a modificar**: `backend/app/services/quant_orchestrator.py`

La función `_update_performance_metrics()` actualmente solo calcula `metric_type = "all_time"`. Debe también calcular `rolling_30d` y `rolling_7d`.

**Cambio requerido** en `_update_performance_metrics()`:
```python
async def _update_performance_metrics() -> None:
    from datetime import timedelta
    supabase = get_supabase()
    now_dt = datetime.now(timezone.utc)

    # Calcular para 3 ventanas temporales
    windows = {
        "all_time": None,
        "rolling_30d": now_dt - timedelta(days=30),
        "rolling_7d": now_dt - timedelta(days=7),
    }

    for metric_type, since in windows.items():
        query = supabase.table("positions").select(
            "realized_pnl,entry_notional,opened_at,closed_at"
        ).eq("status", "closed")

        if since:
            query = query.gte("closed_at", since.isoformat())

        resp = query.execute()
        # ... resto del cálculo igual que ahora
        # Guardar con el metric_type correspondiente
```

### B.2 - Agregar Calmar Ratio al orquestador

**El problema**: La tabla `performance_metrics` tiene columna `calmar_ratio` pero el código en `_update_performance_metrics()` no la calcula.

**Fórmula**: Calmar = Annualized Return / |Max Drawdown|

**Agregar en `_update_performance_metrics()`** después del cálculo de Sortino:
```python
# Calmar ratio
calmar = None
if max_dd < 0:  # max_dd es negativo (pérdida)
    total_return = sum(pnls)
    annualized = total_return * 252 / max(total, 1)  # Aproximación
    calmar = round(annualized / abs(max_dd), 4) if abs(max_dd) > 0 else None
```

**Agregar al dict `metrics`**:
```python
"calmar_ratio": calmar,
```

---

## FASE C: Frontend Quant Dashboard (MEDIA PRIORIDAD)

El plan incluyó integración frontend (Fase 6) pero **no existe ninguna página UI** para visualizar los datos cuantitativos. El LLM los recibe en el prompt pero el usuario no puede verlos.

### C.1 - Next.js API proxy routes para quant

Sin rutas proxy en Next.js, el frontend llama directamente al VPS (CORS issues en producción). Crear:

**`app/api/quant/status/route.ts`**:
```typescript
import { NextResponse } from "next/server";
import { getQuantStatus } from "@/lib/trading/python-backend";
import { isPythonBackendEnabled } from "@/lib/trading/python-backend";

export async function GET() {
  if (!isPythonBackendEnabled()) {
    return NextResponse.json({ error: "Python backend not configured" }, { status: 503 });
  }
  try {
    const status = await getQuantStatus();
    return NextResponse.json(status);
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 500 });
  }
}
```

**`app/api/quant/analysis/[symbol]/route.ts`**:
```typescript
import { NextResponse } from "next/server";
import { getQuantAnalysis, isPythonBackendEnabled } from "@/lib/trading/python-backend";

export async function GET(
  _req: Request,
  { params }: { params: { symbol: string } }
) {
  if (!isPythonBackendEnabled()) {
    return NextResponse.json({ error: "Python backend not configured" }, { status: 503 });
  }
  try {
    const analysis = await getQuantAnalysis(params.symbol.toUpperCase());
    return NextResponse.json(analysis);
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 500 });
  }
}
```

**`app/api/quant/performance/route.ts`**:
```typescript
import { NextResponse } from "next/server";
import { getPerformanceMetrics, isPythonBackendEnabled } from "@/lib/trading/python-backend";

export async function GET() {
  if (!isPythonBackendEnabled()) {
    return NextResponse.json({ error: "Python backend not configured" }, { status: 503 });
  }
  try {
    const metrics = await getPerformanceMetrics();
    return NextResponse.json(metrics);
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 500 });
  }
}
```

**`app/api/quant/backtest/route.ts`**:
```typescript
import { NextResponse } from "next/server";
import { runBacktest, getBacktestResults, isPythonBackendEnabled } from "@/lib/trading/python-backend";

export async function GET(req: Request) {
  if (!isPythonBackendEnabled()) return NextResponse.json({ error: "Python backend not configured" }, { status: 503 });
  const { searchParams } = new URL(req.url);
  const strategyId = searchParams.get("strategy_id") || undefined;
  const results = await getBacktestResults(strategyId);
  return NextResponse.json(results);
}

export async function POST(req: Request) {
  if (!isPythonBackendEnabled()) return NextResponse.json({ error: "Python backend not configured" }, { status: 503 });
  const body = await req.json();
  const result = await runBacktest(body);
  return NextResponse.json(result);
}
```

### C.2 - Página de Quant Dashboard

**Crear**: `app/quant/page.tsx`

La página debe mostrar 4 secciones:

**Sección 1: Quant Engine Status**
- Tick count actual
- Módulos activos (kline_collector, technical_analysis, entropy_filter, etc.)
- Errores recientes
- Última actualización

**Sección 2: Market Analysis (tabs por símbolo)**
- Selector de símbolo (BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT, XRPUSDT)
- Semáforo de tradabilidad (verde/rojo) con motivos de bloqueo
- Régimen actual con color (trending_up=verde, trending_down=rojo, ranging=amarillo, volatile=naranja)
- Entropy ratio con barra de progreso (rojo si > 0.85)
- Indicadores clave: RSI(14), ADX(14), MACD histogram, precio vs SMA200
- Niveles S/R más cercanos (2 support, 2 resistance)
- Sizing recomendado (Kelly + ATR)

**Sección 3: Performance Metrics**
- Tabla con métricas all_time / rolling_30d / rolling_7d:
  - Sharpe ratio
  - Sortino ratio
  - Calmar ratio
  - Win rate
  - Profit factor
  - Kelly fraction
  - Total trades

**Sección 4: Backtesting**
- Formulario para ejecutar backtest:
  - Symbol selector
  - Strategy (sma_cross, rsi_reversal, bbands_squeeze)
  - Interval selector
  - Parámetros opcionales (fast/slow periods, etc.)
- Tabla de resultados anteriores (últimos 10)
- Para cada resultado: strategy, symbol, return%, Sharpe, max_drawdown, win_rate

**Usar**: SWR para fetching con refresh, Tailwind para estilos, mismo AppShell y StatusBadge que el resto del app.

### C.3 - Agregar Quant Engine al home page

**Archivo a modificar**: `app/page.tsx`

En la sección "Trading System" (actualmente 2 cards: Portfolio Command + Trade Proposals), agregar:

```tsx
<NavCard
  href="/quant"
  title="Quant Engine"
  description="Motor cuantitativo: indicadores, régimen de mercado, entropy filter y backtesting."
  icon={<Activity className="h-6 w-6 text-white" />}
  gradient="from-violet-500/20 to-purple-500/5"
/>
```

### C.4 - Agregar Quant Engine al AppShell navigation

**Archivo a encontrar y modificar**: `components/ui/AppShell.tsx` (o donde esté la nav)

Agregar link `/quant` con ícono Activity o BarChart2.

---

## FASE D: Mejoras de Calidad (BAJA PRIORIDAD)

### D.1 - Notificaciones Telegram para eventos quant

**Archivo a modificar**: `backend/app/services/quant_risk.py`

Cuando se dispara un bloqueo cuantitativo (entropy_gate o regime), enviar notificación a Telegram.

**Agregar en `validate_proposal_enhanced()`** cuando se rechaza por entropy:
```python
# En el bloque de entropy check
if entropy and not entropy.is_tradable:
    # Log risk event to DB
    supabase.table("risk_events").insert({
        "event_type": "entropy_gate_blocked",
        "severity": "warning",
        "message": f"Trade blocked: entropy too high for {symbol} ({entropy.entropy_ratio:.3f})",
        ...
    }).execute()
    # Telegram notification (if configured)
    from ...config import settings
    # import telegram if TELEGRAM_BOT_TOKEN available
```

### D.2 - Verificar `store_entropy`, `store_regime`, `store_sr_levels` existen

El orquestador llama:
- `store_entropy(entropy)` de `entropy_filter.py`
- `store_regime(regime)` de `regime_detector.py`
- `store_sr_levels(sr)` de `support_resistance.py`

Verificar que estas funciones existen y hacen upsert correcto a sus respectivas tablas con `ON CONFLICT DO UPDATE`.

**Acción**: Leer los 3 archivos completos y agregar las funciones `store_*` si faltan.

### D.3 - Endpoint de backtest en vercel.json

Si el endpoint de backtest tarda más de 60s, agregar configuración:

**En `vercel.json`**:
```json
"app/api/quant/backtest/route.ts": {
  "maxDuration": 120
}
```

---

## Orden de Implementación Recomendado

```
1. FASE B (30 min) → Métricas rolling + Calmar ratio (código Python simple)
2. FASE D.2 (30 min) → Verificar store_* functions (crítico para que el orquestador guarde datos)
3. FASE A (2-3 horas) → Unit tests Python (alta confianza, no afecta producción)
4. FASE C.1 (45 min) → API proxy routes en Next.js (necesario para FASE C.2)
5. FASE C.2 (3-4 horas) → Frontend Quant Dashboard page
6. FASE C.3 y C.4 (30 min) → Agregar a home page y nav
7. FASE D.1 y D.3 (30 min) → Telegram + vercel.json
```

---

## Archivos a Crear (resumen)

| # | Archivo | Prioridad |
|---|---------|-----------|
| 1 | `backend/tests/__init__.py` | Alta |
| 2 | `backend/tests/conftest.py` | Alta |
| 3 | `backend/tests/test_quant_cache.py` | Alta |
| 4 | `backend/tests/test_kline_collector.py` | Alta |
| 5 | `backend/tests/test_technical_analysis.py` | Alta |
| 6 | `backend/tests/test_entropy_filter.py` | Alta |
| 7 | `backend/tests/test_support_resistance.py` | Alta |
| 8 | `backend/tests/test_regime_detector.py` | Alta |
| 9 | `backend/tests/test_position_sizer.py` | Alta |
| 10 | `backend/tests/test_quant_risk.py` | Alta |
| 11 | `backend/tests/test_orchestrator.py` | Alta |
| 12 | `app/api/quant/status/route.ts` | Media |
| 13 | `app/api/quant/analysis/[symbol]/route.ts` | Media |
| 14 | `app/api/quant/performance/route.ts` | Media |
| 15 | `app/api/quant/backtest/route.ts` | Media |
| 16 | `app/quant/page.tsx` | Media |

## Archivos a Modificar (resumen)

| # | Archivo | Cambio |
|---|---------|--------|
| 1 | `backend/app/services/quant_orchestrator.py` | Rolling 30d/7d + Calmar ratio |
| 2 | `backend/app/services/entropy_filter.py` | Verificar/agregar `store_entropy()` |
| 3 | `backend/app/services/regime_detector.py` | Verificar/agregar `store_regime()` |
| 4 | `backend/app/services/support_resistance.py` | Verificar/agregar `store_sr_levels()` |
| 5 | `app/page.tsx` | Agregar NavCard para /quant |
| 6 | `components/ui/AppShell.tsx` | Agregar link /quant en nav |
| 7 | `vercel.json` | maxDuration para quant/backtest |

---

## Notas Importantes para Opus 4.6

1. **No romper lo que funciona**: El sistema está en producción con 2 posiciones abiertas y corriendo 24/7. Solo agregar, nunca modificar lógica existente sin verificar.

2. **Binance Testnet**: Las API keys son de testnet (datos reales pero dinero virtual). Los tests Python deben usar mocks, no llamar a Binance real.

3. **Supabase**: La DB ya tiene las 7 tablas del quant engine migradas. Los tests deben usar MagicMock para supabase, no la DB real.

4. **VPS deployment**: Después de modificar archivos Python en `backend/`, hay que hacer commit+push. El VPS (EasyPanel) hace auto-deploy desde el repo. El webhook de deploy es `http://145.223.95.154:3000/api/deploy/fadc50e5e2486bccb28ffcf7e8f5b9fa6abc704a3eeee904`.

5. **PYTHON_BACKEND_URL**: Ya configurado en Vercel para todos los ambientes. Las rutas proxy Next.js en `app/api/quant/` deben usar `isPythonBackendEnabled()` como guard.

6. **Performance**: La página `/quant` puede ser pesada (5 símbolos × múltiples endpoints). Usar `Promise.all()` para llamadas paralelas y SWR con `dedupingInterval` adecuado.

7. **Estilo consistente**: El app usa Tailwind con dark theme (slate-900/950 backgrounds, white/emerald accents). Seguir el mismo patrón que `portfolio/page.tsx`.

---

## Verificación Post-Implementación

Para verificar cada fase:

```bash
# FASE A: Tests Python
cd backend && pytest tests/ -v --tb=short

# FASE B: Métricas rolling (necesita al menos 2 trades cerrados en DB)
curl https://italicia-traiding-backend.un5bby.easypanel.host/quant/performance

# FASE C.1: Proxy routes
curl https://traiding-agentic.vercel.app/api/quant/status
curl https://traiding-agentic.vercel.app/api/quant/analysis/BTCUSDT

# FASE C.2: Frontend UI
# Abrir https://traiding-agentic.vercel.app/quant en browser
# Verificar que carga datos de todos los módulos

# FASE D.2: Store functions
# Después de 5 ticks del orchestrador, verificar en Supabase:
# SELECT * FROM entropy_readings ORDER BY measured_at DESC LIMIT 5;
# SELECT * FROM market_regimes ORDER BY detected_at DESC LIMIT 5;
# SELECT * FROM support_resistance_levels ORDER BY calculated_at DESC LIMIT 10;
```
