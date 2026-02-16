-- Add missing content-related fields to sources table
-- These fields store the fetched raw content for evaluation

ALTER TABLE sources
  ADD COLUMN IF NOT EXISTS raw_content TEXT,
  ADD COLUMN IF NOT EXISTS content_length INTEGER,
  ADD COLUMN IF NOT EXISTS fetched_at TIMESTAMPTZ;

-- Add status for when content is being fetched
-- Update the status check constraint to include 'fetching'
ALTER TABLE sources
  DROP CONSTRAINT IF EXISTS sources_status_check;

ALTER TABLE sources
  ADD CONSTRAINT sources_status_check CHECK (status IN (
    'pending', 'fetching', 'evaluating', 'approved', 'processing',
    'processed', 'rejected', 'error'
  ));
