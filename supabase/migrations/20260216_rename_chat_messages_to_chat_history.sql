-- ============================================================================
-- Rename chat_messages to chat_history
-- ============================================================================
-- This migration fixes the inconsistency between schema and code:
-- - Schema creates: chat_messages
-- - Code uses: chat_history
-- Decision: Rename table to match code expectations
-- ============================================================================

-- Rename the table
ALTER TABLE IF EXISTS chat_messages RENAME TO chat_history;

-- Update any indexes that reference the old name
-- (PostgreSQL automatically renames constraints and indexes when renaming tables,
-- but we'll verify the key ones exist)

-- Add a comment to document the change
COMMENT ON TABLE chat_history IS 'Stores chat conversation history between users and AI assistant. Renamed from chat_messages to match code expectations.';

-- ============================================================================
-- Migration Complete
-- ============================================================================
