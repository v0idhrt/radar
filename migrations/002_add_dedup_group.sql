-- Migration 002: Add dedup_group column
-- Created: 2025-10-03
-- Description: Add dedup_group column to news table for duplicate clustering

-- Add dedup_group column to news table
ALTER TABLE news ADD COLUMN dedup_group TEXT;

-- Create index for dedup_group
CREATE INDEX IF NOT EXISTS idx_news_dedup_group ON news(dedup_group);