-- Migration 001: Unified Feed Architecture
-- Creates new tables for unified feed system while keeping old tables for backwards compatibility

-- ============================================================================
-- 1. GLOBAL INSIGHTS TABLE (Unified pool of all insights)
-- ============================================================================
CREATE TABLE IF NOT EXISTS insights (
    id TEXT PRIMARY KEY,  -- UUID
    topic TEXT NOT NULL,
    category TEXT,  -- CASE STUDY, PLAYBOOK, COUNTERINTUITIVE, etc.
    text TEXT NOT NULL,
    source_url TEXT,
    source_domain TEXT,
    quality_score REAL DEFAULT 0,  -- 0-10 from extraction
    engagement_score REAL DEFAULT 0,  -- 0-1 based on user engagement
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_archived INTEGER DEFAULT 0,  -- SQLite uses INTEGER for boolean
    
    -- Legacy reference (for migration)
    legacy_insight_id INTEGER,  -- Reference to insights_v2.id
    legacy_agent_id INTEGER     -- Reference to agents.id
);

CREATE INDEX IF NOT EXISTS idx_insights_topic ON insights(topic);
CREATE INDEX IF NOT EXISTS idx_insights_created_at ON insights(created_at);
CREATE INDEX IF NOT EXISTS idx_insights_quality_score ON insights(quality_score);
CREATE INDEX IF NOT EXISTS idx_insights_engagement_score ON insights(engagement_score);
CREATE INDEX IF NOT EXISTS idx_insights_archived ON insights(is_archived);
CREATE INDEX IF NOT EXISTS idx_insights_legacy ON insights(legacy_insight_id);

-- ============================================================================
-- 2. USER TOPICS (What topics users follow)
-- ============================================================================
CREATE TABLE IF NOT EXISTS user_topics (
    user_id TEXT NOT NULL,
    topic TEXT NOT NULL,
    followed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, topic)
);

CREATE INDEX IF NOT EXISTS idx_user_topics_user ON user_topics(user_id);
CREATE INDEX IF NOT EXISTS idx_user_topics_topic ON user_topics(topic);

-- ============================================================================
-- 3. USER ENGAGEMENT TRACKING (Views, likes, saves, dismisses)
-- ============================================================================
CREATE TABLE IF NOT EXISTS user_engagement (
    id TEXT PRIMARY KEY,  -- UUID
    user_id TEXT NOT NULL,
    insight_id TEXT NOT NULL,
    action TEXT NOT NULL,  -- 'view', 'like', 'save', 'dismiss'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (insight_id) REFERENCES insights(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_user_engagement_user ON user_engagement(user_id);
CREATE INDEX IF NOT EXISTS idx_user_engagement_insight ON user_engagement(insight_id);
CREATE INDEX IF NOT EXISTS idx_user_engagement_action ON user_engagement(action);
CREATE INDEX IF NOT EXISTS idx_user_engagement_created_at ON user_engagement(created_at);

-- ============================================================================
-- 4. USER PREFERENCES (Derived from engagement)
-- ============================================================================
CREATE TABLE IF NOT EXISTS user_preferences (
    user_id TEXT PRIMARY KEY,
    liked_categories TEXT,  -- JSON: {"CASE STUDY": 15, "PLAYBOOK": 8, ...}
    saved_sources TEXT,  -- JSON: {"anthropic.com": 5, "a16z.com": 3, ...}
    topic_affinity TEXT,  -- JSON: {"AI agents": 0.95, "Value Investing": 0.78, ...}
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- 5. FEED CACHE (Pre-computed feed results for performance)
-- ============================================================================
CREATE TABLE IF NOT EXISTS feed_cache (
    id TEXT PRIMARY KEY,  -- UUID
    user_id TEXT NOT NULL,
    feed_type TEXT NOT NULL,  -- 'following' or 'for_you'
    insight_ids TEXT NOT NULL,  -- JSON array of insight IDs
    computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    
    UNIQUE(user_id, feed_type)
);

CREATE INDEX IF NOT EXISTS idx_feed_cache_user ON feed_cache(user_id);
CREATE INDEX IF NOT EXISTS idx_feed_cache_expires ON feed_cache(expires_at);

-- ============================================================================
-- 6. TOPICS METADATA (Info about each topic for discovery)
-- ============================================================================
CREATE TABLE IF NOT EXISTS topics (
    topic TEXT PRIMARY KEY,
    description TEXT,
    follower_count INTEGER DEFAULT 0,
    insight_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active INTEGER DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_topics_follower_count ON topics(follower_count);
CREATE INDEX IF NOT EXISTS idx_topics_insight_count ON topics(insight_count);
CREATE INDEX IF NOT EXISTS idx_topics_active ON topics(is_active);

-- ============================================================================
-- 7. TOPIC SIMILARITY (For "For You" recommendations)
-- ============================================================================
CREATE TABLE IF NOT EXISTS topic_similarity (
    topic_a TEXT NOT NULL,
    topic_b TEXT NOT NULL,
    similarity_score REAL NOT NULL,  -- 0-1
    PRIMARY KEY (topic_a, topic_b)
);

CREATE INDEX IF NOT EXISTS idx_topic_similarity_score ON topic_similarity(similarity_score);

-- ============================================================================
-- DATA MIGRATION VIEWS (Helper views for migration)
-- ============================================================================

-- View to see old insights with their agent topics
CREATE VIEW IF NOT EXISTS v_legacy_insights AS
SELECT 
    i.id as legacy_id,
    i.agent_id as legacy_agent_id,
    a.topic,
    i.extracted_data,
    i.url as source_url,
    i.source_name,
    i.date_crawled
FROM insights_v2 i
LEFT JOIN agents a ON i.agent_id = a.id;

-- View to see current unified feed stats
CREATE VIEW IF NOT EXISTS v_feed_stats AS
SELECT 
    topic,
    COUNT(*) as insight_count,
    AVG(quality_score) as avg_quality,
    AVG(engagement_score) as avg_engagement,
    COUNT(CASE WHEN is_archived = 0 THEN 1 END) as active_count
FROM insights
GROUP BY topic;
