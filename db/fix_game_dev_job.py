"""Fix the game development extraction job that succeeded but timed out"""
import sqlite3
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "insights.db")

def fix_game_dev_job():
    """Mark the game development job as complete with correct stats"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Update the job to complete status
    cursor.execute("""
        UPDATE extraction_jobs
        SET
            status = 'complete',
            insight_count = 129,
            sources_processed = 40,
            extraction_duration_seconds = 1633.6,
            updated_at = datetime('now')
        WHERE topic = 'game development'
        AND status IN ('processing', 'failed')
    """)

    rows_updated = cursor.rowcount
    conn.commit()

    if rows_updated > 0:
        print(f"✅ Fixed {rows_updated} job(s) for 'game development'")

        # Verify
        cursor.execute("""
            SELECT id, status, insight_count, sources_processed
            FROM extraction_jobs
            WHERE topic = 'game development'
            ORDER BY created_at DESC
            LIMIT 1
        """)
        job = cursor.fetchone()
        if job:
            print(f"   Job ID: {job[0]}")
            print(f"   Status: {job[1]}")
            print(f"   Insights: {job[2]}")
            print(f"   Sources: {job[3]}")
    else:
        print("⚠️  No jobs found to fix")

    conn.close()

if __name__ == "__main__":
    fix_game_dev_job()
