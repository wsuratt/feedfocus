"""Backfill user_topic_affinities from existing user_topics and engagement data"""
import sqlite3
import os
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "insights.db")

def backfill_topic_affinities():
    """
    Seed user_topic_affinities table with initial values based on:
    - Topics user follows → 0.70 base affinity
    - Topics user liked insights from → 0.40 base affinity
    - Topics user saved insights from → 0.50 base affinity
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("Backfilling user topic affinities...")

    # Get all users
    cursor.execute("SELECT DISTINCT user_id FROM user_topics")
    users = [row[0] for row in cursor.fetchall()]

    print(f"Found {len(users)} users")

    for user_id in users:
        print(f"\nProcessing user: {user_id}")

        # 1. Topics user follows → 0.70 affinity
        cursor.execute("""
            SELECT topic FROM user_topics WHERE user_id = ?
        """, (user_id,))
        followed_topics = [row[0] for row in cursor.fetchall()]

        for topic in followed_topics:
            cursor.execute("""
                INSERT OR REPLACE INTO user_topic_affinities
                (user_id, topic, affinity_score, last_engagement_at, updated_at)
                VALUES (?, ?, 0.70, ?, ?)
            """, (user_id, topic, datetime.now().isoformat(), datetime.now().isoformat()))

        print(f"  Added {len(followed_topics)} followed topics with 0.70 affinity")

        # 2. Topics user liked insights from → 0.40 affinity (if not already following)
        cursor.execute("""
            SELECT DISTINCT i.topic
            FROM user_engagement ue
            JOIN insights i ON ue.insight_id = i.id
            WHERE ue.user_id = ? AND ue.action = 'like'
        """, (user_id,))
        liked_topics = [row[0] for row in cursor.fetchall()]

        new_liked = 0
        for topic in liked_topics:
            if topic not in followed_topics:
                cursor.execute("""
                    INSERT OR IGNORE INTO user_topic_affinities
                    (user_id, topic, affinity_score, last_engagement_at, updated_at)
                    VALUES (?, ?, 0.40, ?, ?)
                """, (user_id, topic, datetime.now().isoformat(), datetime.now().isoformat()))
                new_liked += 1

        print(f"  Added {new_liked} liked topics with 0.40 affinity")

        # 3. Topics user saved insights from → 0.50 affinity (if not already following or liked)
        cursor.execute("""
            SELECT DISTINCT i.topic
            FROM user_engagement ue
            JOIN insights i ON ue.insight_id = i.id
            WHERE ue.user_id = ? AND ue.action = 'save'
        """, (user_id,))
        saved_topics = [row[0] for row in cursor.fetchall()]

        new_saved = 0
        for topic in saved_topics:
            if topic not in followed_topics and topic not in liked_topics:
                cursor.execute("""
                    INSERT OR IGNORE INTO user_topic_affinities
                    (user_id, topic, affinity_score, last_engagement_at, updated_at)
                    VALUES (?, ?, 0.50, ?, ?)
                """, (user_id, topic, datetime.now().isoformat(), datetime.now().isoformat()))
                new_saved += 1

        print(f"  Added {new_saved} saved topics with 0.50 affinity")

        # 4. Create user profile if doesn't exist
        cursor.execute("""
            INSERT OR IGNORE INTO user_profiles (user_id)
            VALUES (?)
        """, (user_id,))

        # 5. Update total counts in user profile
        cursor.execute("""
            SELECT COUNT(*) FROM user_engagement WHERE user_id = ? AND action = 'view'
        """, (user_id,))
        total_views = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*) FROM user_engagement WHERE user_id = ? AND action = 'like'
        """, (user_id,))
        total_likes = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*) FROM user_engagement WHERE user_id = ? AND action = 'save'
        """, (user_id,))
        total_saves = cursor.fetchone()[0]

        cursor.execute("""
            UPDATE user_profiles
            SET total_views = ?,
                total_likes = ?,
                total_saves = ?,
                updated_at = ?
            WHERE user_id = ?
        """, (total_views, total_likes, total_saves, datetime.now().isoformat(), user_id))

        print(f"  Updated profile: {total_views} views, {total_likes} likes, {total_saves} saves")

    conn.commit()
    conn.close()

    print("\n✅ Backfill complete!")

    # Show summary
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM user_topic_affinities")
    total_affinities = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM user_profiles")
    total_profiles = cursor.fetchone()[0]

    print(f"\nSummary:")
    print(f"  Total user profiles: {total_profiles}")
    print(f"  Total topic affinities: {total_affinities}")

    conn.close()

if __name__ == "__main__":
    backfill_topic_affinities()
