-- Fix score columns to accept decimal values (not just integers)
-- This allows for more accurate weighted averages in source evaluation

ALTER TABLE sources
  ALTER COLUMN relevance_score TYPE NUMERIC(3,1),
  ALTER COLUMN credibility_score TYPE NUMERIC(3,1),
  ALTER COLUMN applicability_score TYPE NUMERIC(3,1),
  ALTER COLUMN overall_score TYPE NUMERIC(3,1);

-- Update constraints to work with NUMERIC
ALTER TABLE sources
  DROP CONSTRAINT IF EXISTS sources_relevance_score_check,
  ADD CONSTRAINT sources_relevance_score_check CHECK (relevance_score BETWEEN 1.0 AND 10.0);

ALTER TABLE sources
  DROP CONSTRAINT IF EXISTS sources_credibility_score_check,
  ADD CONSTRAINT sources_credibility_score_check CHECK (credibility_score BETWEEN 1.0 AND 10.0);

ALTER TABLE sources
  DROP CONSTRAINT IF EXISTS sources_applicability_score_check,
  ADD CONSTRAINT sources_applicability_score_check CHECK (applicability_score BETWEEN 1.0 AND 10.0);

ALTER TABLE sources
  DROP CONSTRAINT IF EXISTS sources_overall_score_check,
  ADD CONSTRAINT sources_overall_score_check CHECK (overall_score BETWEEN 1.0 AND 10.0);

-- Also fix paper_extractions confidence_score
ALTER TABLE paper_extractions
  ALTER COLUMN confidence_score TYPE NUMERIC(3,1);

ALTER TABLE paper_extractions
  DROP CONSTRAINT IF EXISTS paper_extractions_confidence_score_check,
  ADD CONSTRAINT paper_extractions_confidence_score_check CHECK (confidence_score BETWEEN 1.0 AND 10.0);
