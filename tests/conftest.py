"""Pytest configuration and shared fixtures."""

import os
import sys
import sqlite3
import pytest
from typing import Generator

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, PROJECT_ROOT)


@pytest.fixture
def test_db() -> Generator[sqlite3.Connection, None, None]:
    """Create in-memory test database with schema."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE insights (
            id TEXT PRIMARY KEY,
            topic TEXT NOT NULL,
            category TEXT NOT NULL,
            text TEXT NOT NULL,
            source_url TEXT NOT NULL,
            source_domain TEXT NOT NULL,
            quality_score REAL DEFAULT 0.5,
            engagement_score REAL DEFAULT 0,
            created_at TEXT NOT NULL
        );

        CREATE INDEX idx_insights_topic ON insights(topic);
        CREATE INDEX idx_insights_created_at ON insights(created_at);

        CREATE TABLE user_topics (
            user_id TEXT NOT NULL,
            topic TEXT NOT NULL,
            followed_at TEXT NOT NULL,
            PRIMARY KEY (user_id, topic)
        );

        CREATE INDEX idx_user_topics_user ON user_topics(user_id);

        CREATE TABLE user_engagement (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            insight_id TEXT NOT NULL,
            action TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE INDEX idx_engagement_user ON user_engagement(user_id);
        CREATE INDEX idx_engagement_insight ON user_engagement(insight_id);
    """)

    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def sample_insights(test_db: sqlite3.Connection) -> list:
    """Insert sample insights for testing."""
    insights = [
        ("1", "AI agents", "Technology", "AI agents are becoming more capable",
         "https://example.com/ai1", "example.com", "2024-01-01T00:00:00"),
        ("2", "AI agents", "Technology", "New AI agent framework released",
         "https://example.com/ai2", "example.com", "2024-01-02T00:00:00"),
        ("3", "Gen Z Consumer", "Business", "Gen Z shopping habits changing",
         "https://example.com/genz1", "example.com", "2024-01-03T00:00:00"),
        ("4", "Value Investing", "Finance", "Value investing strategies",
         "https://example.com/invest1", "example.com", "2024-01-04T00:00:00"),
    ]

    cursor = test_db.cursor()
    for insight in insights:
        cursor.execute("""
            INSERT INTO insights
            (id, topic, category, text, source_url, source_domain, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, insight)

    test_db.commit()
    return insights


@pytest.fixture
def test_user_id() -> str:
    """Test user ID."""
    return "test-user-123"


@pytest.fixture
def sample_topics() -> list:
    """Sample topics for testing."""
    return [
        "AI agents",
        "machine learning",
        "startup fundraising",
        "Web3",
        "DeFi"
    ]
