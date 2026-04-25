-- Migration: 2026-04-25 — Partial exit tracking columns on positions.
-- Phase 0.3 of docs/superpowers/specs/2026-04-24-daily-strategist-agent-design.md

BEGIN;

ALTER TABLE positions
    ADD COLUMN IF NOT EXISTS partial_exit_taken boolean DEFAULT false NOT NULL;

ALTER TABLE positions
    ADD COLUMN IF NOT EXISTS partial_exit_price numeric(18, 8) NULL;

ALTER TABLE positions
    ADD COLUMN IF NOT EXISTS partial_exit_qty numeric(18, 8) NULL;

ALTER TABLE positions
    ADD COLUMN IF NOT EXISTS partial_exit_at timestamptz NULL;

CREATE INDEX IF NOT EXISTS idx_positions_partial_exit
    ON positions(partial_exit_taken)
    WHERE status = 'open';

COMMIT;
