---
generated_at: 2026-04-11 18:22 UTC
stale_after: 1 hour
---

# Current Market Snapshot

> Este archivo se genera con `python scripts/refresh-market-context.py`.
> Si el timestamp tiene >1 hora, regenerar antes de reevaluar la estrategia.

## Estado de posiciones

- **Abiertas:** 0
- **Cerradas histórico:** 62
- **P&L total histórico:** $-2.80

## Últimos 7 días

- **Trades cerrados:** 16
- **P&L:** $+15.82
- **Win rate:** 68.8% (11W / 5L)
- **Profit factor:** 13.26

### Por símbolo (7d)

| Symbol | P&L | Trades | Win Rate |
|---|---|---|---|
| ETHUSDT | $+14.21 | 9 | 78% |
| BTCUSDT | $+1.60 | 7 | 57% |

### Motivos de cierre (últimas 200 proposals)

| Tag | Count | % |
|---|---|---|
| [STOP_LOSS] | 82 | 78% |
| [AUTO] | 18 | 17% |
| [TAKE_PROFIT] | 3 | 3% |
| [TIME_STOP] | 2 | 2% |

## Red Flags (auto-check)

✓ Ninguna red flag detectada

## Checklist de reevaluación

- [ ] Leer `decision-matrix.md`
- [ ] Verificar régimen actual del símbolo (si hay posición abierta)
- [ ] Revisar last evaluation en `evaluations/`
- [ ] Si hay red flags → acción inmediata
- [ ] Guardar nueva evaluation en `evaluations/YYYY-MM-DD-HHMM.md`
