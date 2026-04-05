-- Data retention function and initial cleanup
-- Solves: reconciliation_runs 267 MB (48k filas), klines 136 MB (373k filas)
--
-- Políticas:
--   reconciliation_runs : 7 días
--   klines_ohlcv (1m)   : 7 días
--   klines_ohlcv (5m)   : 14 días
--   klines_ohlcv (15m)  : 30 días
--   klines_ohlcv (1h)   : 90 días
--   klines_ohlcv (4h/1d): 180 días
--   klines inactivos     : borrar todo (SOL, XRP, BNB ya no monitoreados)
--   technical_indicators : 30 días
--   risk_events          : 90 días (solo resolved)
--   trade_proposals      : 30 días (solo rejected/dead_letter/draft/cancelled)

CREATE OR REPLACE FUNCTION run_data_retention()
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  del_recon        int := 0;
  del_klines       int := 0;
  del_indicators   int := 0;
  del_risk         int := 0;
  del_proposals    int := 0;
  tmp              int;
BEGIN
  -- 1. reconciliation_runs: guardar solo 7 días
  DELETE FROM reconciliation_runs
  WHERE created_at < NOW() - INTERVAL '7 days';
  GET DIAGNOSTICS del_recon = ROW_COUNT;

  -- 2. klines inactivos: SOLUSDT, XRPUSDT, BNBUSDT ya no se monitorean
  DELETE FROM klines_ohlcv
  WHERE symbol IN ('SOLUSDT', 'XRPUSDT', 'BNBUSDT');
  GET DIAGNOSTICS tmp = ROW_COUNT;
  del_klines := del_klines + tmp;

  -- 3. klines por intervalo (solo activos: BTC, ETH)
  DELETE FROM klines_ohlcv
  WHERE interval = '1m' AND open_time < NOW() - INTERVAL '7 days';
  GET DIAGNOSTICS tmp = ROW_COUNT;
  del_klines := del_klines + tmp;

  DELETE FROM klines_ohlcv
  WHERE interval = '5m' AND open_time < NOW() - INTERVAL '14 days';
  GET DIAGNOSTICS tmp = ROW_COUNT;
  del_klines := del_klines + tmp;

  DELETE FROM klines_ohlcv
  WHERE interval = '15m' AND open_time < NOW() - INTERVAL '30 days';
  GET DIAGNOSTICS tmp = ROW_COUNT;
  del_klines := del_klines + tmp;

  DELETE FROM klines_ohlcv
  WHERE interval = '1h' AND open_time < NOW() - INTERVAL '90 days';
  GET DIAGNOSTICS tmp = ROW_COUNT;
  del_klines := del_klines + tmp;

  DELETE FROM klines_ohlcv
  WHERE interval IN ('4h', '1d') AND open_time < NOW() - INTERVAL '180 days';
  GET DIAGNOSTICS tmp = ROW_COUNT;
  del_klines := del_klines + tmp;

  -- 4. technical_indicators: guardar 30 días
  DELETE FROM technical_indicators
  WHERE candle_time < NOW() - INTERVAL '30 days';
  GET DIAGNOSTICS del_indicators = ROW_COUNT;

  -- 5. risk_events: guardar 90 días (solo los ya resueltos se pueden borrar)
  DELETE FROM risk_events
  WHERE created_at < NOW() - INTERVAL '90 days'
    AND resolved = true;
  GET DIAGNOSTICS del_risk = ROW_COUNT;

  -- 6. trade_proposals: borrar rechazadas/viejas (nunca borrar executed/closed)
  DELETE FROM trade_proposals
  WHERE status IN ('rejected', 'dead_letter', 'draft', 'cancelled')
    AND created_at < NOW() - INTERVAL '30 days';
  GET DIAGNOSTICS del_proposals = ROW_COUNT;

  RETURN jsonb_build_object(
    'reconciliation_runs', del_recon,
    'klines_ohlcv',        del_klines,
    'technical_indicators', del_indicators,
    'risk_events',         del_risk,
    'trade_proposals',     del_proposals,
    'ran_at',              NOW()
  );
END;
$$;

-- Ejecutar limpieza inicial inmediata
SELECT run_data_retention();
