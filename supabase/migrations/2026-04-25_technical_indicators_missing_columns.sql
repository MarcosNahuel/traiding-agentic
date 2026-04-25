-- Fix silent INSERT failures in technical_indicators since 2026-03-27.
-- The Python writer (technical_analysis.py:139-151) persists ppo,
-- autocorr_1 and volume_ratio, but those columns never existed in the
-- table — every INSERT raised, was caught one frame up and logged as
-- a warning, and the table stopped receiving rows.
--
-- Adding the columns rather than dropping the writes preserves the
-- indicators (used by signal_generator and quant_orchestrator).

ALTER TABLE technical_indicators
  ADD COLUMN IF NOT EXISTS ppo          DECIMAL(20, 8),
  ADD COLUMN IF NOT EXISTS autocorr_1   DECIMAL(10, 6),
  ADD COLUMN IF NOT EXISTS volume_ratio DECIMAL(10, 4);

COMMENT ON COLUMN technical_indicators.ppo IS
  'Percentage Price Oscillator — MACD-style normalized to %';
COMMENT ON COLUMN technical_indicators.autocorr_1 IS
  'Lag-1 autocorrelation of returns (QuantScience filter)';
COMMENT ON COLUMN technical_indicators.volume_ratio IS
  'Current volume / 20-period average';
