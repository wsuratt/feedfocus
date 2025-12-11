"""
Migration script: Add extraction_jobs table for background queue system

This script:
1. Creates extraction_jobs table
2. Adds all necessary indexes
3. Is idempotent (can be run multiple times safely)

Usage:
    python db/migrations/run_002_extraction_jobs.py
"""

import sqlite3
import os
import sys
from datetime import datetime

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, PROJECT_ROOT)

DB_PATH = os.path.join(PROJECT_ROOT, "insights.db")
MIGRATION_SQL = os.path.join(os.path.dirname(__file__), "002_extraction_jobs.sql")


def check_table_exists(conn, table_name):
    """Check if a table exists in the database"""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,)
    )
    return cursor.fetchone() is not None


def run_migration(conn):
    """Execute the migration SQL file"""
    print("📝 Running migration 002: extraction_jobs table...")

    # Check if table already exists
    if check_table_exists(conn, "extraction_jobs"):
        print("⚠️  extraction_jobs table already exists")
        response = input("Do you want to recreate it? This will DELETE all data. (yes/no): ")
        if response.lower() != 'yes':
            print("❌ Migration cancelled")
            return False

        # Drop existing table
        print("🗑️  Dropping existing extraction_jobs table...")
        cursor = conn.cursor()
        cursor.execute("DROP TABLE IF EXISTS extraction_jobs")
        conn.commit()

    # Read and execute migration SQL
    with open(MIGRATION_SQL, 'r') as f:
        migration_sql = f.read()

    cursor = conn.cursor()
    cursor.executescript(migration_sql)
    conn.commit()

    print("✅ Migration SQL executed successfully")
    return True


def verify_migration(conn):
    """Verify that the migration was successful"""
    print("\n🔍 Verifying migration...")

    cursor = conn.cursor()

    # Check table exists
    if not check_table_exists(conn, "extraction_jobs"):
        print("❌ extraction_jobs table not found!")
        return False

    print("✅ extraction_jobs table exists")

    # Check columns
    cursor.execute("PRAGMA table_info(extraction_jobs)")
    columns = {row[1] for row in cursor.fetchall()}

    expected_columns = {
        'id', 'topic', 'user_id', 'priority', 'status',
        'insight_count', 'error', 'retry_count', 'last_retry_at',
        'estimated_completion_at', 'sources_processed',
        'extraction_duration_seconds', 'created_at', 'updated_at'
    }

    if columns != expected_columns:
        print(f"❌ Column mismatch!")
        print(f"   Expected: {expected_columns}")
        print(f"   Found: {columns}")
        return False

    print(f"✅ All {len(columns)} columns present")

    # Check indexes
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='extraction_jobs'")
    indexes = [row[0] for row in cursor.fetchall()]

    expected_indexes = [
        'idx_extraction_jobs_topic',
        'idx_extraction_jobs_status',
        'idx_extraction_jobs_user_id',
        'idx_extraction_jobs_priority',
        'idx_extraction_jobs_created_at',
        'idx_extraction_jobs_status_priority',
        'idx_extraction_jobs_active'
    ]

    for expected_index in expected_indexes:
        if expected_index in indexes:
            print(f"✅ Index {expected_index} exists")
        else:
            print(f"⚠️  Index {expected_index} not found")

    return True


def main():
    """Main migration function"""
    print("=" * 70)
    print("FeedFocus Migration 002: Extraction Jobs Table")
    print("=" * 70)
    print(f"Database: {DB_PATH}")
    print(f"Migration SQL: {MIGRATION_SQL}")
    print()

    # Check files exist
    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found: {DB_PATH}")
        sys.exit(1)

    if not os.path.exists(MIGRATION_SQL):
        print(f"❌ Migration SQL not found: {MIGRATION_SQL}")
        sys.exit(1)

    # Connect to database
    try:
        conn = sqlite3.connect(DB_PATH)
        print(f"✅ Connected to database")

        # Run migration
        if not run_migration(conn):
            sys.exit(1)

        # Verify migration
        if not verify_migration(conn):
            print("\n❌ Migration verification failed!")
            sys.exit(1)

        print("\n" + "=" * 70)
        print("✅ Migration 002 completed successfully!")
        print("=" * 70)
        print("\nNext steps:")
        print("1. Test the table with a simple INSERT/SELECT")
        print("2. Proceed to Task 1.2: Build Topic Validation Module")

    except Exception as e:
        print(f"\n❌ Migration failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    main()
