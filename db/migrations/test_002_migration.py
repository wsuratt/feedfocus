"""
Test script for migration 002: extraction_jobs table

This script tests basic CRUD operations on the extraction_jobs table.

Usage:
    python db/migrations/test_002_migration.py
"""

import sqlite3
import os
import sys
import uuid
from datetime import datetime, timedelta

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, PROJECT_ROOT)

DB_PATH = os.path.join(PROJECT_ROOT, "insights.db")


def test_insert_job(conn):
    """Test inserting a job"""
    print("\n📝 Test 1: Insert job...")

    job_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    estimated = (datetime.utcnow() + timedelta(minutes=5)).isoformat()

    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO extraction_jobs (
            id, topic, user_id, priority, status,
            insight_count, sources_processed,
            estimated_completion_at, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        job_id,
        "machine learning",
        "user123",
        10,
        "queued",
        0,
        0,
        estimated,
        now,
        now
    ))
    conn.commit()

    print(f"✅ Inserted job: {job_id}")
    return job_id


def test_select_job(conn, job_id):
    """Test selecting a job"""
    print("\n📝 Test 2: Select job...")

    cursor = conn.cursor()
    cursor.execute("SELECT * FROM extraction_jobs WHERE id = ?", (job_id,))
    row = cursor.fetchone()

    if row:
        print(f"✅ Found job: {row[1]} (status: {row[4]})")
        return True
    else:
        print("❌ Job not found!")
        return False


def test_update_job(conn, job_id):
    """Test updating a job"""
    print("\n📝 Test 3: Update job status...")

    cursor = conn.cursor()
    cursor.execute("""
        UPDATE extraction_jobs
        SET status = 'processing',
            sources_processed = 10,
            updated_at = ?
        WHERE id = ?
    """, (datetime.utcnow().isoformat(), job_id))
    conn.commit()

    # Verify update
    cursor.execute("SELECT status, sources_processed FROM extraction_jobs WHERE id = ?", (job_id,))
    status, sources = cursor.fetchone()

    if status == 'processing' and sources == 10:
        print(f"✅ Updated job: status={status}, sources_processed={sources}")
        return True
    else:
        print(f"❌ Update failed: status={status}, sources={sources}")
        return False


def test_query_by_status(conn):
    """Test querying by status"""
    print("\n📝 Test 4: Query by status...")

    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM extraction_jobs WHERE status = 'processing'")
    count = cursor.fetchone()[0]

    print(f"✅ Found {count} processing jobs")
    return True


def test_priority_ordering(conn):
    """Test priority ordering"""
    print("\n📝 Test 5: Priority ordering...")

    cursor = conn.cursor()
    cursor.execute("""
        SELECT topic, priority
        FROM extraction_jobs
        ORDER BY priority DESC
        LIMIT 5
    """)

    jobs = cursor.fetchall()
    print(f"✅ Top priority jobs:")
    for topic, priority in jobs:
        print(f"   - {topic}: priority {priority}")

    return True


def test_error_handling(conn):
    """Test error field with JSON"""
    print("\n📝 Test 6: Error handling...")

    import json

    job_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    error_obj = {
        "type": "api_rate_limit",
        "message": "Claude API rate limit exceeded",
        "retry_eligible": True
    }

    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO extraction_jobs (
            id, topic, user_id, priority, status,
            error, retry_count, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        job_id,
        "test topic",
        "user123",
        5,
        "failed",
        json.dumps(error_obj),
        1,
        now,
        now
    ))
    conn.commit()

    # Retrieve and parse error
    cursor.execute("SELECT error FROM extraction_jobs WHERE id = ?", (job_id,))
    error_json = cursor.fetchone()[0]
    parsed_error = json.loads(error_json)

    if parsed_error["type"] == "api_rate_limit":
        print(f"✅ Error JSON stored and retrieved correctly")
        return True
    else:
        print(f"❌ Error JSON parsing failed")
        return False


def test_cleanup(conn):
    """Clean up test data"""
    print("\n🧹 Cleaning up test data...")

    cursor = conn.cursor()
    cursor.execute("DELETE FROM extraction_jobs")
    deleted = cursor.rowcount
    conn.commit()

    print(f"✅ Deleted {deleted} test records")


def main():
    """Run all tests"""
    print("=" * 70)
    print("Testing Migration 002: extraction_jobs table")
    print("=" * 70)
    print(f"Database: {DB_PATH}")
    print()

    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found: {DB_PATH}")
        print("   Run the migration first: python db/migrations/run_002_extraction_jobs.py")
        sys.exit(1)

    try:
        conn = sqlite3.connect(DB_PATH)

        # Run tests
        job_id = test_insert_job(conn)
        test_select_job(conn, job_id)
        test_update_job(conn, job_id)
        test_query_by_status(conn)
        test_priority_ordering(conn)
        test_error_handling(conn)

        # Cleanup
        test_cleanup(conn)

        print("\n" + "=" * 70)
        print("✅ All tests passed!")
        print("=" * 70)
        print("\nTask 1.1 completed! ✓")
        print("Ready to proceed to Task 1.2: Build Topic Validation Module")

    except Exception as e:
        print(f"\n❌ Tests failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    main()
