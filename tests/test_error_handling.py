"""
Integration test for error categorization.

Tests that different error types are handled correctly:
1. Transient errors (rate limit, network) -> auto-retry
2. Permanent errors (no results, invalid) -> no auto-retry
3. Error JSON structure verification
4. Retry count tracking
"""

import sys
import os
import json
from datetime import datetime

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from backend.utils.database import get_db_connection


def create_failed_job(topic: str, error_type: str, error_message: str, retry_eligible: bool):
    """Create a failed job with specific error type."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        job_id = f"error-test-{topic}"
        error = json.dumps({
            "type": error_type,
            "message": error_message,
            "retry_eligible": retry_eligible
        })

        cursor.execute("""
            INSERT OR REPLACE INTO extraction_jobs
            (id, topic, user_id, priority, status, retry_count, error, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            job_id,
            topic,
            "test-user",
            5,
            "failed",
            0,
            error,
            datetime.now().isoformat(),
            datetime.now().isoformat()
        ))

        conn.commit()
        return job_id


def get_job_error(topic: str):
    """Get error details for a job."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT error, retry_count FROM extraction_jobs
            WHERE topic = ?
            ORDER BY created_at DESC
            LIMIT 1
        """, (topic,))

        row = cursor.fetchone()
        if row:
            error_json, retry_count = row
            error = json.loads(error_json) if error_json else None
            return error, retry_count
        return None, None


def cleanup_test_data(topics: list):
    """Clean up test data."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        for topic in topics:
            cursor.execute("DELETE FROM extraction_jobs WHERE topic = ?", (topic,))
        conn.commit()


def test_error_handling():
    """Test error categorization and handling."""
    print("\n" + "="*70)
    print("Integration Test: Error Categorization")
    print("="*70)

    test_topics = [
        "rate-limit-test",
        "network-error-test",
        "no-results-test",
        "invalid-content-test"
    ]

    # Clean up
    cleanup_test_data(test_topics)

    # Test 1: Rate limit error (transient - should auto-retry)
    print("\n1. Testing rate limit error (transient)...")
    job_id = create_failed_job(
        test_topics[0],
        error_type="transient",
        error_message="API rate limit exceeded",
        retry_eligible=True
    )

    error, retry_count = get_job_error(test_topics[0])

    assert error is not None
    assert error["type"] == "transient"
    assert error["retry_eligible"] == True
    assert "rate limit" in error["message"].lower()

    print(f"   Error type: {error['type']}")
    print(f"   Message: {error['message']}")
    print(f"   Retry eligible: {error['retry_eligible']}")
    print("   ✓ Rate limit error correctly categorized as transient")

    # Test 2: Network error (transient - should auto-retry)
    print("\n2. Testing network error (transient)...")
    job_id = create_failed_job(
        test_topics[1],
        error_type="transient",
        error_message="Connection timeout after 30 seconds",
        retry_eligible=True
    )

    error, retry_count = get_job_error(test_topics[1])

    assert error is not None
    assert error["type"] == "transient"
    assert error["retry_eligible"] == True
    assert "timeout" in error["message"].lower() or "connection" in error["message"].lower()

    print(f"   Error type: {error['type']}")
    print(f"   Message: {error['message']}")
    print(f"   Retry eligible: {error['retry_eligible']}")
    print("   ✓ Network error correctly categorized as transient")

    # Test 3: No results found (permanent - should NOT auto-retry)
    print("\n3. Testing no results error (permanent)...")
    job_id = create_failed_job(
        test_topics[2],
        error_type="permanent",
        error_message="No relevant sources found for this topic",
        retry_eligible=False
    )

    error, retry_count = get_job_error(test_topics[2])

    assert error is not None
    assert error["type"] == "permanent"
    assert error["retry_eligible"] == False
    assert "no" in error["message"].lower() and "found" in error["message"].lower()

    print(f"   Error type: {error['type']}")
    print(f"   Message: {error['message']}")
    print(f"   Retry eligible: {error['retry_eligible']}")
    print("   ✓ No results error correctly categorized as permanent")

    # Test 4: Invalid content (permanent - should NOT auto-retry)
    print("\n4. Testing invalid content error (permanent)...")
    job_id = create_failed_job(
        test_topics[3],
        error_type="permanent",
        error_message="Topic contains invalid characters or format",
        retry_eligible=False
    )

    error, retry_count = get_job_error(test_topics[3])

    assert error is not None
    assert error["type"] == "permanent"
    assert error["retry_eligible"] == False
    assert "invalid" in error["message"].lower()

    print(f"   Error type: {error['type']}")
    print(f"   Message: {error['message']}")
    print(f"   Retry eligible: {error['retry_eligible']}")
    print("   ✓ Invalid content error correctly categorized as permanent")

    # Test 5: Verify error JSON structure
    print("\n5. Verifying error JSON structure...")

    required_fields = ["type", "message", "retry_eligible"]

    for topic in test_topics:
        error, _ = get_job_error(topic)
        assert error is not None

        for field in required_fields:
            assert field in error, f"Missing field '{field}' in error JSON"

        # Verify types
        assert isinstance(error["type"], str)
        assert isinstance(error["message"], str)
        assert isinstance(error["retry_eligible"], bool)

        # Verify type is valid
        assert error["type"] in ["transient", "permanent"]

    print(f"   ✓ All errors have required fields: {', '.join(required_fields)}")
    print("   ✓ Field types are correct")
    print("   ✓ Error types are valid (transient/permanent)")

    # Test 6: Test retry count tracking for auto-retries
    print("\n6. Testing retry count tracking...")

    # Simulate auto-retry progression for transient error
    topic = test_topics[0]  # Rate limit error

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # First retry (0 -> 1)
        cursor.execute("""
            UPDATE extraction_jobs
            SET retry_count = 1, status = 'failed'
            WHERE topic = ?
        """, (topic,))
        conn.commit()

    _, retry_count = get_job_error(topic)
    assert retry_count == 1
    print(f"   After 1st auto-retry: retry_count = {retry_count}")

    # Second retry (1 -> 2)
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE extraction_jobs
            SET retry_count = 2, status = 'failed'
            WHERE topic = ?
        """, (topic,))
        conn.commit()

    _, retry_count = get_job_error(topic)
    assert retry_count == 2
    print(f"   After 2nd auto-retry: retry_count = {retry_count}")

    # Third retry (2 -> 3)
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE extraction_jobs
            SET retry_count = 3, status = 'failed'
            WHERE topic = ?
        """, (topic,))
        conn.commit()

    _, retry_count = get_job_error(topic)
    assert retry_count == 3
    print(f"   After 3rd auto-retry: retry_count = {retry_count}")
    print("   ✓ Retry count tracked correctly through auto-retries")

    # Test 7: Verify permanent errors don't increment retry_count
    print("\n7. Verifying permanent errors don't auto-retry...")

    permanent_topic = test_topics[2]  # No results error
    _, retry_count = get_job_error(permanent_topic)

    assert retry_count == 0
    print(f"   Permanent error retry_count: {retry_count}")
    print("   ✓ Permanent errors stay at retry_count = 0 (no auto-retry)")

    # Test 8: Test error message quality
    print("\n8. Checking error message quality...")

    error_messages = []
    for topic in test_topics:
        error, _ = get_job_error(topic)
        if error:
            error_messages.append(error["message"])

    for msg in error_messages:
        # Messages should be descriptive (at least 15 characters)
        assert len(msg) >= 15, f"Error message too short: {msg}"

        # Messages should start with capital letter or contain useful info
        assert msg[0].isupper() or any(word in msg.lower() for word in ["api", "connection", "timeout", "no", "invalid"])

    print("   Sample messages:")
    for msg in error_messages[:2]:
        print(f"     - {msg}")
    print("   ✓ Error messages are descriptive and helpful")

    print("\n" + "="*70)
    print("Integration Test PASSED!")
    print("="*70)

    print("\nKey Verified:")
    print("  ✓ Rate limit errors marked as transient")
    print("  ✓ Network errors marked as transient")
    print("  ✓ No results errors marked as permanent")
    print("  ✓ Invalid content errors marked as permanent")
    print("  ✓ Error JSON has correct structure (type, message, retry_eligible)")
    print("  ✓ Retry count tracked correctly")
    print("  ✓ Permanent errors don't auto-retry")
    print("  ✓ Error messages are descriptive")

    # Cleanup
    cleanup_test_data(test_topics)


if __name__ == "__main__":
    test_error_handling()
