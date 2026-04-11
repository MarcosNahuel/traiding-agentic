# Knowledge Base — Trading Strategy Brain

Esta es la **base de conocimiento** del bot de trading. Sirve como "cerebro" para que cualquier sesión de Claude (u otro analista) pueda:

1. **Entender qué estrategias están disponibles** y cómo se usan
2. **Ver el estado actual del mercado** y qué estrategia fit mejor
3. **Reevaluar la estrategia activa** con contexto histórico completo
4. **Registrar nuevas investigaciones** y sus fuentes

## Cómo usar este KB (para Claude / analista)

Cuando el usuario pida **"reevalúa la estrategia"** o similar, seguir esta checklist:

1. Leer `current-market.md` (estado actual del mercado y la performance)
2. Leer `decision-matrix.md` (qué estrategia para qué régimen)
3. Revisar `strategies/` para los detalles de la(s) candidata(s)
4. Consultar `evaluations/` para ver decisiones anteriores (no repetir errores)
5. Regenerar `current-market.md` con `python scripts/refresh-market-context.py` si está stale (>1h)
6. Documentar la nueva decisión en `evaluations/YYYY-MM-DD-HHMM.md`

## Estructura

```
docs/knowledge-base/
├── README.md                    # Este archivo
├── current-market.md            # ESTADO ACTUAL (auto-generado, stale después de 1h)
├── decision-matrix.md           # Qué estrategia usar en qué régimen
├── strategies/                  # Catálogo de estrategias disponibles
│   ├── 01-trend-momentum.md     # ACTIVA — default desde post-mortem 5 abr
│   ├── 02-reversal-oversold.md  # IDEA — no implementada (RSI<20 bypass)
│   └── _template.md             # Template para nuevas estrategias
├── market-regimes/              # Taxonomía de regímenes
│   ├── README.md                # Vista general
│   ├── trending-up.md
│   ├── trending-down.md
│   ├── ranging-low-vol.md
│   ├── ranging-high-vol.md
│   └── volatile-crash.md
├── research/                    # Fuentes, documentos, investigaciones
│   ├── sources.md               # Índice maestro
│   └── YYYY-MM-DD-*.md          # Cada análisis con fecha
└── evaluations/                 # Historial de decisiones tomadas
    └── YYYY-MM-DD-HHMM.md
```

## Principios

- **Data-driven:** cada recomendación debe apoyarse en datos reales (trades cerrados, P&L, Sharpe, etc.)
- **Versionado en git:** cada cambio al KB es un commit
- **Fechas absolutas:** nunca "ayer" o "la semana pasada" — usar YYYY-MM-DD
- **Enlaces vivos:** citar `file:line` para código, URLs para papers externos
- **No overfitting:** una muestra < 30 trades es hipótesis, no conclusión
