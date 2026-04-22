---
generated_at: 2026-04-21 20:54 UTC
stale_after: 1 hour
---

# Current Market Snapshot

> Este archivo se genera con `python scripts/refresh-market-context.py`.
> Si el timestamp tiene >1 hora, regenerar antes de reevaluar la estrategia.

## Estado de posiciones

- **Abiertas:** 0
- **Cerradas histórico:** 78
- **P&L total histórico:** $-1.63

## Últimos 7 días

- **Trades cerrados:** 15
- **P&L:** $+1.42
- **Win rate:** 66.7% (10W / 5L)
- **Profit factor:** 1.27

### Por símbolo (7d)

| Symbol | P&L | Trades | Win Rate |
|---|---|---|---|
| ETHUSDT | $+1.23 | 9 | 78% |
| BTCUSDT | $+0.19 | 6 | 50% |

### Motivos de cierre (últimas 200 proposals)

| Tag | Count | % |
|---|---|---|
| [STOP_LOSS] | 97 | 80% |
| [AUTO] | 18 | 15% |
| [TIME_STOP] | 3 | 2% |
| [TAKE_PROFIT] | 3 | 2% |

## Red Flags (auto-check)

✓ Ninguna red flag detectada

## Checklist de reevaluación

- [ ] Leer `decision-matrix.md`
- [ ] Verificar régimen actual del símbolo (si hay posición abierta)
- [ ] Revisar last evaluation en `evaluations/`
- [ ] Si hay red flags → acción inmediata
- [ ] Guardar nueva evaluation en `evaluations/YYYY-MM-DD-HHMM.md`
