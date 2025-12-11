"""Semantic similarity search for topics using embeddings."""

import os
import sys
from typing import Dict, List, Tuple, Optional

from backend.utils.database import get_db_connection
from backend.utils.logger import setup_logger

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

logger = setup_logger(__name__)

# Lazy load embedding model (avoid import errors during startup)
_model = None

def _get_model():
    """Lazy load the embedding model"""
    global _model
    if _model is None:
        try:
            from automation.semantic_db import model as semantic_model
            _model = semantic_model
        except Exception as e:
            logger.warning(f"Failed to load embedding model: {e}")
            logger.warning("Similarity search will not work without the model")
            _model = None
    return _model


def get_all_topics() -> List[str]:
    """Get all unique topics that have insights."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT topic
                FROM insights
                WHERE topic IS NOT NULL AND topic != ''
                ORDER BY topic
            """)
            return [row[0] for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Failed to fetch topics: {e}")
        return []


def calculate_similarity(text1: str, text2: str) -> float:
    """
    Calculate cosine similarity between two text strings.

    Args:
        text1: First text
        text2: Second text

    Returns:
        Similarity score between 0 and 1
    """
    try:
        model = _get_model()
        if model is None:
            logger.debug("Embedding model not available, returning 0.0 similarity")
            return 0.0

        emb1 = model.encode(text1)
        emb2 = model.encode(text2)

        dot_product = sum(a * b for a, b in zip(emb1, emb2))
        magnitude1 = sum(a * a for a in emb1) ** 0.5
        magnitude2 = sum(b * b for b in emb2) ** 0.5

        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0

        similarity = dot_product / (magnitude1 * magnitude2)
        return max(0.0, min(1.0, similarity))

    except Exception as e:
        logger.error(f"Error calculating similarity: {e}")
        return 0.0


def find_similar_topics(
    new_topic: str,
    very_similar_threshold: float = 0.85,
    related_threshold: float = 0.65,
    top_k: int = 5
) -> Dict:
    """
    Find topics similar to a new topic.

    Returns tiered response based on similarity:
    - >0.85: Very similar (reuse existing topic)
    - >0.65: Related (show existing, also queue new)
    - <0.65: New topic (queue extraction)

    Args:
        new_topic: Topic name to check
        very_similar_threshold: Threshold for "reuse" action (default 0.85)
        related_threshold: Threshold for "related" action (default 0.65)
        top_k: Number of similar topics to return (default 5)

    Returns:
        {
            "action": "reuse" | "related" | "new",
            "existing_topic": str or None,
            "similarity_score": float,
            "similar_topics": [
                {"topic": str, "score": float},
                ...
            ],
            "message": str
        }
    """
    # Get all existing topics
    existing_topics = get_all_topics()

    if not existing_topics:
        # No existing topics - this is definitely new
        return {
            "action": "new",
            "existing_topic": None,
            "similarity_score": 0.0,
            "similar_topics": [],
            "message": "No existing topics found. This will be the first topic."
        }

    # Calculate similarity to all existing topics
    similarities = []
    for topic in existing_topics:
        score = calculate_similarity(new_topic.lower(), topic.lower())
        similarities.append((topic, score))

    # Sort by similarity (highest first)
    similarities.sort(key=lambda x: x[1], reverse=True)

    # Get top K similar topics
    top_similar = [
        {"topic": topic, "score": round(score, 3)}
        for topic, score in similarities[:top_k]
    ]

    # Get the most similar topic
    most_similar_topic, max_similarity = similarities[0]

    # Determine action based on similarity
    if max_similarity >= very_similar_threshold:
        # Very similar - reuse existing topic
        return {
            "action": "reuse",
            "existing_topic": most_similar_topic,
            "similarity_score": round(max_similarity, 3),
            "similar_topics": top_similar,
            "message": f"Very similar to existing topic '{most_similar_topic}'. Using existing topic."
        }

    elif max_similarity >= related_threshold:
        # Related - show existing but also queue new
        return {
            "action": "related",
            "existing_topic": most_similar_topic,
            "similarity_score": round(max_similarity, 3),
            "similar_topics": top_similar,
            "message": f"Related to '{most_similar_topic}'. Showing existing insights and queueing extraction for new topic."
        }

    else:
        # New topic - queue extraction
        return {
            "action": "new",
            "existing_topic": None,
            "similarity_score": round(max_similarity, 3),
            "similar_topics": top_similar,
            "message": "New topic. Queueing extraction."
        }


def get_topic_insight_count(topic: str) -> int:
    """Get the number of insights for a given topic."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM insights WHERE topic = ?", (topic,))
            return cursor.fetchone()[0]
    except Exception as e:
        logger.error(f"Failed to get insight count: {e}")
        return 0


def find_similar_topic(
    topic: str,
    threshold: float = 0.85
) -> Optional[Tuple[str, float]]:
    """
    Simplified version: Find the single most similar topic above threshold.

    Args:
        topic: Topic name to check
        threshold: Minimum similarity threshold (default 0.85)

    Returns:
        (existing_topic, similarity_score) if found, None otherwise
    """
    result = find_similar_topics(
        topic,
        very_similar_threshold=threshold,
        related_threshold=threshold - 0.1
    )

    if result["action"] == "reuse" or result["action"] == "related":
        return (result["existing_topic"], result["similarity_score"])

    return None


# Testing and debugging functions
def test_similarity_search():
    """Test the similarity search with known topics."""
    logger.info("Testing Semantic Topic Similarity")

    topics = get_all_topics()
    logger.info(f"Found {len(topics)} existing topics in database")

    for topic in topics[:10]:
        count = get_topic_insight_count(topic)
        logger.info(f"  {topic} ({count} insights)")

    if len(topics) > 10:
        logger.info(f"  ... and {len(topics) - 10} more")

    test_cases = [
        "AI agents",
        "artificial intelligence agents",
        "machine learning",
        "startup fundraising",
        "venture capital",
    ]

    logger.info("Testing Similarity Detection")

    for test_topic in test_cases:
        logger.info(f"Test: '{test_topic}'")
        result = find_similar_topics(test_topic)

        logger.info(f"  Action: {result['action']}")
        if result['existing_topic']:
            logger.info(f"  Most Similar: '{result['existing_topic']}' (score: {result['similarity_score']})")
        logger.info(f"  Message: {result['message']}")

        if result['similar_topics']:
            for sim in result['similar_topics'][:3]:
                logger.info(f"    {sim['topic']}: {sim['score']}")


if __name__ == "__main__":
    test_similarity_search()
