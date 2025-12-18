-- FeedFocus Lite: Lead tracking table
-- Stores email submissions and tracks status

CREATE TABLE IF NOT EXISTS lite_leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL,
    topic TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    insights_sent INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    email_sent_at TEXT,
    conversion_source TEXT DEFAULT 'lite_landing',
    subscription_token TEXT,
    subscribed BOOLEAN DEFAULT 0,
    unsubscribed_at TEXT,
    UNIQUE(email, topic)
);

CREATE INDEX IF NOT EXISTS idx_lite_leads_email ON lite_leads(email);
CREATE INDEX IF NOT EXISTS idx_lite_leads_status ON lite_leads(status);
CREATE INDEX IF NOT EXISTS idx_lite_leads_created_at ON lite_leads(created_at);

-- Track which insights were sent to each email/topic to prevent repeats
CREATE TABLE IF NOT EXISTS lite_sent_insights (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL,
    topic TEXT NOT NULL,
    insight_id INTEGER NOT NULL,
    sent_at TEXT NOT NULL,
    UNIQUE(email, topic, insight_id)
);

CREATE INDEX IF NOT EXISTS idx_lite_sent_email_topic ON lite_sent_insights(email, topic);
CREATE INDEX IF NOT EXISTS idx_lite_sent_insight_id ON lite_sent_insights(insight_id);
