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
