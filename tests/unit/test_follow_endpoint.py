"""Test suite for POST /api/topics/follow endpoint."""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch
from backend.utils.database import get_db_connection


def test_follow_invalid_topic(test_db):
    """Test following an invalid topic."""
    from backend.main import app
    from fastapi.testclient import TestClient

    client = TestClient(app)

    response = client.post(
        "/api/topics/follow",
        json={"topic": "x"}  # Too short
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "invalid"
    assert "error" in data


def test_follow_similar_topic_reuse(test_db):
    """Test following a topic similar to existing one - should reuse."""
    from backend.main import app
    from fastapi.testclient import TestClient

    # Add existing insights for "machine learning"
    with get_db_connection() as conn:
        cursor = conn.cursor()
        for i in range(35):
            cursor.execute("""
                INSERT INTO insights
                (id, topic, category, text, source_url, domain, quality_score, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                f"insight-{i}",
                "machine learning",
                "strategic_insights",
                f"Test insight {i}",
                "https://test.com",
                "test.com",
                8.0,
                datetime.now().isoformat()
            ))
        conn.commit()

    client = TestClient(app)

    # Follow "ML" which is similar to "machine learning"
    response = client.post(
        "/api/topics/follow",
        json={"topic": "ML"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["topic"] == "machine learning"  # Should reuse existing topic
    assert data["original_topic"] == "ML"
    assert data["insight_count"] >= 30


def test_follow_new_topic_with_insights(test_db):
    """Test following a new topic that already has >= 30 insights."""
    from backend.main import app
    from fastapi.testclient import TestClient

    # Add insights for "remote work"
    with get_db_connection() as conn:
        cursor = conn.cursor()
        for i in range(35):
            cursor.execute("""
                INSERT INTO insights
                (id, topic, category, text, source_url, domain, quality_score, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                f"rw-insight-{i}",
                "remote work",
                "strategic_insights",
                f"Remote work insight {i}",
                "https://test.com",
                "test.com",
                8.0,
                datetime.now().isoformat()
            ))
        conn.commit()

    client = TestClient(app)

    response = client.post(
        "/api/topics/follow",
        json={"topic": "remote work"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["topic"] == "remote work"
    assert data["insight_count"] >= 30


def test_follow_new_topic_needs_extraction(test_db):
    """Test following a new topic with < 30 insights - should queue extraction."""
    from backend.main import app
    from fastapi.testclient import TestClient

    # Add only a few insights
    with get_db_connection() as conn:
        cursor = conn.cursor()
        for i in range(5):
            cursor.execute("""
                INSERT INTO insights
                (id, topic, category, text, source_url, domain, quality_score, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                f"ai-insight-{i}",
                "AI agents",
                "strategic_insights",
                f"AI agent insight {i}",
                "https://test.com",
                "test.com",
                8.0,
                datetime.now().isoformat()
            ))
        conn.commit()

    client = TestClient(app)

    response = client.post(
        "/api/topics/follow",
        json={"topic": "AI agents"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "extracting"
    assert data["topic"] == "AI agents"
    assert "message" in data
    assert data["existing_count"] < 30
    assert "job_id" in data


def test_follow_duplicate_extraction_job(test_db):
    """Test following a topic that's already being extracted."""
    from backend.main import app
    from fastapi.testclient import TestClient

    client = TestClient(app)

    # First request - should queue
    response1 = client.post(
        "/api/topics/follow",
        json={"topic": "quantum computing"}
    )

    assert response1.status_code == 200
    data1 = response1.json()
    assert data1["status"] == "extracting"

    # Second request - should detect duplicate
    response2 = client.post(
        "/api/topics/follow",
        json={"topic": "quantum computing"}
    )

    assert response2.status_code == 200
    data2 = response2.json()
    assert data2["status"] == "extracting"
    assert "already in progress" in data2["message"].lower()


def test_user_added_to_user_topics(test_db):
    """Test that user is added to user_topics table immediately."""
    from backend.main import app
    from fastapi.testclient import TestClient

    client = TestClient(app)

    response = client.post(
        "/api/topics/follow",
        json={"topic": "blockchain technology"}
    )

    assert response.status_code == 200

    # Verify user was added to user_topics
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT topic FROM user_topics WHERE user_id = ?
        """, ("default",))

        row = cursor.fetchone()
        assert row is not None
        assert row[0] == "blockchain technology"


def test_high_priority_for_user_triggered_jobs(test_db):
    """Test that user-triggered extractions get priority 10."""
    from backend.main import app
    from fastapi.testclient import TestClient

    client = TestClient(app)

    response = client.post(
        "/api/topics/follow",
        json={"topic": "sustainable energy"}
    )

    assert response.status_code == 200
    data = response.json()

    if data["status"] == "extracting":
        # Verify job has priority 10
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT priority FROM extraction_jobs WHERE topic = ?
            """, ("sustainable energy",))

            row = cursor.fetchone()
            assert row is not None
            assert row[0] == 10  # High priority


def test_follow_with_whitespace(test_db):
    """Test that topic whitespace is trimmed."""
    from backend.main import app
    from fastapi.testclient import TestClient

    client = TestClient(app)

    response = client.post(
        "/api/topics/follow",
        json={"topic": "  cloud computing  "}
    )

    assert response.status_code == 200
    data = response.json()

    # Topic should be trimmed
    assert data["topic"] == "cloud computing"
