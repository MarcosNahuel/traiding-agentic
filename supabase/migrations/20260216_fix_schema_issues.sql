-- ============================================================================
-- Fix Schema Issues (P1 from Audit)
-- ============================================================================
-- This migration fixes schema inconsistencies identified in the audit:
-- 1. Expands risk_events.event_type to include all types used in code
-- 2. Creates missing synthesis_results table
-- 3. Adds validation_status to strategies_found table
-- ============================================================================

-- ============================================================================
-- 1. Fix risk_events.event_type constraint
-- ============================================================================

-- Drop existing constraint
ALTER TABLE risk_events DROP CONSTRAINT IF EXISTS risk_events_event_type_check;

-- Add new constraint with all event types used in code
ALTER TABLE risk_events ADD CONSTRAINT risk_events_event_type_check CHECK (
  event_type IN (
    -- Original types
    'limit_hit',
    'drawdown_alert',
    'daily_loss_limit',
    'position_size_limit',
    'margin_call',
    'max_positions',
    'price_spike',
    'connection_loss',
    'order_rejected',
    -- New types used in code
    'execution_blocked',
    'execution_error',
    'order_executed',
    'proposal_approved',
    'proposal_rejected',
    'proposal_cancelled',
    'position_closed',
    'position_opened',
    'risk_warning'
  )
);

-- ============================================================================
-- 2. Create synthesis_results table
-- ============================================================================

CREATE TABLE IF NOT EXISTS synthesis_results (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Version tracking
  version INTEGER NOT NULL DEFAULT 1,

  -- Source metadata
  based_on_sources INTEGER NOT NULL DEFAULT 0,
  based_on_strategies INTEGER NOT NULL DEFAULT 0,
  source_ids UUID[] DEFAULT ARRAY[]::UUID[],

  -- Quality metrics
  confidence_score DECIMAL(5, 2), -- 0-100
  completeness_score DECIMAL(5, 2), -- 0-100

  -- Content
  executive_summary TEXT,
  full_guide_markdown TEXT NOT NULL,
  structured_data JSONB, -- Additional structured insights

  -- Status
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'superseded', 'archived')),

  -- Timestamps
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  superseded_at TIMESTAMPTZ
);

-- Indexes
CREATE INDEX idx_synthesis_results_version ON synthesis_results(version DESC);
CREATE INDEX idx_synthesis_results_status ON synthesis_results(status);
CREATE INDEX idx_synthesis_results_created_at ON synthesis_results(created_at DESC);

COMMENT ON TABLE synthesis_results IS 'Stores synthesized trading guides generated from multiple sources';
COMMENT ON COLUMN synthesis_results.version IS 'Incremental version number for tracking guide evolution';
COMMENT ON COLUMN synthesis_results.status IS 'Only one synthesis can be active at a time';

-- ============================================================================
-- 3. Add validation_status to strategies_found table
-- ============================================================================

-- Check if column exists, if not add it
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'strategies_found'
    AND column_name = 'validation_status'
  ) THEN
    ALTER TABLE strategies_found
    ADD COLUMN validation_status TEXT DEFAULT 'pending'
    CHECK (validation_status IN ('pending', 'validated', 'rejected', 'needs_review'));

    CREATE INDEX idx_strategies_validation_status ON strategies_found(validation_status);

    COMMENT ON COLUMN strategies_found.validation_status IS 'Validation status for strategy quality and applicability';
  END IF;
END $$;

-- ============================================================================
-- Migration Complete
-- ============================================================================
