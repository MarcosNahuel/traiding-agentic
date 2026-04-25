# Supabase trades export

Para regenerar `data/diagnostics/trades.csv`, correr la siguiente query vía MCP `supabase.execute_sql` y persistir el resultado en CSV:

```sql
SELECT
  id,
  symbol,
  side,
  opened_at,
  closed_at,
  entry_price,
  exit_price,
  stop_loss_price,
  take_profit_price,
  realized_pnl,
  realized_pnl_percent,
  partial_exit_taken,
  partial_exit_price,
  partial_exit_at,
  status
FROM positions
WHERE status = 'closed'
  AND symbol IN ('ETHUSDT','BTCUSDT','BNBUSDT')
ORDER BY opened_at ASC;
```

Última corrida: 2026-04-25 — 75 filas (ETH=32, BTC=22, BNB=21 de los closed).

El archivo CSV está gitignored (`data/diagnostics/`). Solo está committeado este `.md` con la query y schema.

## Schema esperado por los scripts

- `id` — uuid (clave primaria)
- `symbol` — text (ETHUSDT, BTCUSDT, BNBUSDT)
- `side` — text ('long' / 'short' — al 2026-04-25 todos son long)
- `opened_at`, `closed_at`, `partial_exit_at` — timestamptz
- `entry_price`, `exit_price`, `stop_loss_price`, `take_profit_price`,
  `realized_pnl`, `realized_pnl_percent`, `partial_exit_price` — numeric
- `partial_exit_taken` — boolean
- `status` — text (filtramos por 'closed')

## Notas

- `stop_loss_price` y `take_profit_price` pueden ser NULL en trades muy viejos
  (los primeros 2 trades 2026-02-16/17 son así). El drift audit los excluye.
- El campo "exit_reason" no existe en la tabla. Se deriva en `02_drift_audit.py`
  comparando `exit_price` con `stop_loss_price` y `take_profit_price` con
  tolerancia de 0.5% (configurable).
