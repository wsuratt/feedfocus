-- Migration 003: Performance Indexes for Feed Queries
-- Adds composite indexes to optimize feed generation

-- Composite index for Following feed (filter by archived + topic, sort by score)
CREATE INDEX IF NOT EXISTS idx_insights_archived_topic_created ON insights(is_archived, topic, created_at DESC);

-- Composite index for For You feed (filter by archived, sort by scores)
CREATE INDEX IF NOT EXISTS idx_insights_archived_quality_created ON insights(is_archived, quality_score DESC, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_insights_archived_engagement_created ON insights(is_archived, engagement_score DESC, created_at DESC);

-- Composite index for seen insights check
CREATE INDEX IF NOT EXISTS idx_user_engagement_user_insight_action ON user_engagement(user_id, insight_id, action);

-- Index for recent engagement queries
CREATE INDEX IF NOT EXISTS idx_user_engagement_insight_action_created ON user_engagement(insight_id, action, created_at DESC);
