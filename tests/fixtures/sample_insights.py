"""Sample insights for testing."""

from datetime import datetime

SAMPLE_INSIGHTS = [
    {
        "id": "insight-1",
        "topic": "AI agents",
        "category": "Technology",
        "text": "New AI agent framework enables autonomous task completion with minimal human intervention.",
        "source_url": "https://example.com/ai-agents-1",
        "source_domain": "example.com",
        "quality_score": 0.85,
        "engagement_score": 0.0,
        "created_at": "2024-01-01T10:00:00"
    },
    {
        "id": "insight-2",
        "topic": "AI agents",
        "category": "Technology",
        "text": "Research shows AI agents can now collaborate effectively on complex projects.",
        "source_url": "https://example.com/ai-agents-2",
        "source_domain": "example.com",
        "quality_score": 0.80,
        "engagement_score": 0.0,
        "created_at": "2024-01-02T10:00:00"
    },
    {
        "id": "insight-3",
        "topic": "startup fundraising",
        "category": "Business",
        "text": "Q1 2024 saw record seed funding rounds for AI startups.",
        "source_url": "https://example.com/fundraising-1",
        "source_domain": "example.com",
        "quality_score": 0.75,
        "engagement_score": 0.0,
        "created_at": "2024-01-03T10:00:00"
    },
    {
        "id": "insight-4",
        "topic": "machine learning",
        "category": "Technology",
        "text": "New transformer architecture achieves state-of-the-art results on benchmark tasks.",
        "source_url": "https://example.com/ml-1",
        "source_domain": "example.com",
        "quality_score": 0.90,
        "engagement_score": 0.0,
        "created_at": "2024-01-04T10:00:00"
    },
    {
        "id": "insight-5",
        "topic": "Web3",
        "category": "Technology",
        "text": "Ethereum layer 2 solutions see significant adoption growth.",
        "source_url": "https://example.com/web3-1",
        "source_domain": "example.com",
        "quality_score": 0.70,
        "engagement_score": 0.0,
        "created_at": "2024-01-05T10:00:00"
    }
]

def create_insight(topic: str, text: str, **kwargs) -> dict:
    """Helper to create a test insight."""
    return {
        "id": kwargs.get("id", f"test-{topic.replace(' ', '-')}"),
        "topic": topic,
        "category": kwargs.get("category", "Technology"),
        "text": text,
        "source_url": kwargs.get("source_url", "https://example.com/test"),
        "source_domain": kwargs.get("source_domain", "example.com"),
        "quality_score": kwargs.get("quality_score", 0.75),
        "engagement_score": kwargs.get("engagement_score", 0.0),
        "created_at": kwargs.get("created_at", datetime.now().isoformat())
    }
