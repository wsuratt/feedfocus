-- Migration 002: Extraction Queue System
-- Creates extraction_jobs table for background topic extraction with queue management

-- ============================================================================
-- EXTRACTION JOBS TABLE (Queue management for topic extractions)
-- ============================================================================
CREATE TABLE IF NOT EXISTS extraction_jobs (
    id TEXT PRIMARY KEY,  -- UUID
    topic TEXT NOT NULL,
    user_id TEXT NOT NULL,  -- User who requested, or 'system' for daily refresh
    priority INTEGER DEFAULT 5,  -- 1-10, higher = processed first (10=user, 1=daily refresh)
    status TEXT NOT NULL CHECK(status IN ('queued', 'processing', 'complete', 'failed')),
    insight_count INTEGER DEFAULT 0,  -- Number of insights extracted
    error TEXT,  -- JSON string with error details: {"type": "...", "message": "...", "retry_eligible": bool}
    retry_count INTEGER DEFAULT 0,  -- Number of retry attempts
    last_retry_at TEXT,  -- ISO timestamp of last retry
    estimated_completion_at TEXT,  -- ISO timestamp of expected completion
    sources_processed INTEGER DEFAULT 0,  -- Progress tracking (0-40)
    extraction_duration_seconds REAL,  -- Actual time taken to complete
    created_at TEXT NOT NULL,  -- ISO timestamp
    updated_at TEXT NOT NULL  -- ISO timestamp
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_extraction_jobs_topic ON extraction_jobs(topic);
CREATE INDEX IF NOT EXISTS idx_extraction_jobs_status ON extraction_jobs(status);
CREATE INDEX IF NOT EXISTS idx_extraction_jobs_user_id ON extraction_jobs(user_id);
CREATE INDEX IF NOT EXISTS idx_extraction_jobs_priority ON extraction_jobs(priority DESC);
CREATE INDEX IF NOT EXISTS idx_extraction_jobs_created_at ON extraction_jobs(created_at);
CREATE INDEX IF NOT EXISTS idx_extraction_jobs_status_priority ON extraction_jobs(status, priority DESC);

-- Composite index for finding active jobs
CREATE INDEX IF NOT EXISTS idx_extraction_jobs_active ON extraction_jobs(status, topic)
    WHERE status IN ('queued', 'processing');
