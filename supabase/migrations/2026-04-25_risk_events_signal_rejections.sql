-- Allow signal_generator's per-tick rejection telemetry to land in risk_events.
-- The CHECK constraint whitelisted 24 specific event_types; without
-- 'signal_rejections_tick' every insert from generate_signals() failed and
-- was caught silently by the best-effort try/except. Result: 0 telemetry
-- rows in production despite the in-memory counters working correctly.

ALTER TABLE risk_events DROP CONSTRAINT risk_events_event_type_check;

ALTER TABLE risk_events ADD CONSTRAINT risk_events_event_type_check
  CHECK (event_type = ANY (ARRAY[
    'limit_hit', 'drawdown_alert', 'daily_loss_limit', 'position_size_limit',
    'margin_call', 'max_positions', 'price_spike', 'connection_loss',
    'order_rejected', 'proposal_approved', 'proposal_rejected', 'proposal_cancelled',
    'execution_blocked', 'execution_error', 'order_executed',
    'position_opened', 'position_closed', 'risk_warning', 'dead_letter',
    'entropy_gate_blocked', 'regime_warning', 'volatility_spike',
    'kelly_size_override', 'backtest_validation_fail',
    -- Added 2026-04-25: per-tick signal rejection counters from signal_generator.
    'signal_rejections_tick'
  ]::text[]));

COMMENT ON CONSTRAINT risk_events_event_type_check ON risk_events IS
  'Whitelist of event_type values. Update when signal_generator or risk paths add new event types.';
