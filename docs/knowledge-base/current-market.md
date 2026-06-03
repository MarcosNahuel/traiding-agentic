---
generated_at: 2026-06-03 01:58 UTC
stale_after: 1 hour
---

# Current Market Snapshot

> Este archivo se genera con `python scripts/refresh-market-context.py`.
> Si el timestamp tiene >1 hora, regenerar antes de reevaluar la estrategia.

## Estado de posiciones

- **Abiertas:** 0
- **Cerradas histórico:** 169
- **P&L total histórico:** $-28.12

## Últimos 7 días

- **Trades cerrados:** 18
- **P&L:** $+0.55
- **Win rate:** 44.4% (8W / 10L)
- **Profit factor:** 1.17

### Por símbolo (7d)

| Symbol | P&L | Trades | Win Rate |
|---|---|---|---|
| BTCUSDT | $+0.39 | 9 | 33% |
| ETHUSDT | $+0.16 | 9 | 56% |

### Motivos de cierre (últimas 200 proposals)

| Tag | Count | % |
|---|---|---|
| [STOP_LOSS] | 87 | 85% |
| [TAKE_PROFIT] | 9 | 9% |
| [TIME_STOP] | 5 | 5% |
| [AUTO] | 1 | 1% |

## Red Flags (auto-check)

- 🚨 Drawdown total $-28.12 < -$20

## Checklist de reevaluación

- [ ] Leer `decision-matrix.md`
- [ ] Verificar régimen actual del símbolo (si hay posición abierta)
- [ ] Revisar last evaluation en `evaluations/`
- [ ] Si hay red flags → acción inmediata
- [ ] Guardar nueva evaluation en `evaluations/YYYY-MM-DD-HHMM.md`
