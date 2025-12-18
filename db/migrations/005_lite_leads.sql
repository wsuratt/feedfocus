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
