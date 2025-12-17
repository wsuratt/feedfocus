-- Migration 004: User Profiles and Topic Affinities
-- Creates tables for personalized feed algorithm v2

-- User profile table
CREATE TABLE IF NOT EXISTS user_profiles (
    user_id TEXT PRIMARY KEY,
    quality_preference REAL DEFAULT 0.7,      -- 0-1, preferred quality level
    freshness_preference REAL DEFAULT 0.5,    -- 0-1, how much they prefer new content
    avg_session_length INTEGER DEFAULT 15,    -- Typical insights per session
    total_views INTEGER DEFAULT 0,
    total_likes INTEGER DEFAULT 0,
    total_saves INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Topic affinity scores (replaces simple follow/unfollow)
CREATE TABLE IF NOT EXISTS user_topic_affinities (
    user_id TEXT NOT NULL,
    topic TEXT NOT NULL,
    affinity_score REAL DEFAULT 0.5,  -- 0-1, how interested user is
    last_engagement_at TIMESTAMP,     -- For time decay calculation
    view_count INTEGER DEFAULT 0,
    like_count INTEGER DEFAULT 0,
    save_count INTEGER DEFAULT 0,
    dismiss_count INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, topic)
);

CREATE INDEX IF NOT EXISTS idx_user_topic_affinity ON user_topic_affinities(user_id, affinity_score DESC);
CREATE INDEX IF NOT EXISTS idx_topic_affinity ON user_topic_affinities(topic, affinity_score DESC);

-- Topic similarities (pre-computed using embeddings)
CREATE TABLE IF NOT EXISTS topic_similarities (
    topic_a TEXT NOT NULL,
    topic_b TEXT NOT NULL,
    similarity_score REAL NOT NULL,  -- Cosine similarity 0-1
    PRIMARY KEY (topic_a, topic_b)
);

CREATE INDEX IF NOT EXISTS idx_topic_sim_a ON topic_similarities(topic_a, similarity_score DESC);
CREATE INDEX IF NOT EXISTS idx_topic_sim_b ON topic_similarities(topic_b, similarity_score DESC);
