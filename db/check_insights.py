"""Check what insights exist in the database"""
import sqlite3
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "insights.db")

def check_insights():
    """Check insights for game development topic"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("🔍 Checking insights in database...\n")

    # Check all topics
    cursor.execute("""
        SELECT topic, COUNT(*) as count
        FROM insights
        WHERE is_archived = 0
        GROUP BY topic
        ORDER BY count DESC
    """)

    all_topics = cursor.fetchall()
    print("📊 All topics with insights:")
    for topic, count in all_topics:
        print(f"   {topic}: {count} insights")

    print("\n🎮 Game development specific check:")

    # Check exact match
    cursor.execute("""
        SELECT COUNT(*) FROM insights
        WHERE topic = 'game development' AND is_archived = 0
    """)
    exact_count = cursor.fetchone()[0]
    print(f"   Exact match 'game development': {exact_count}")

    # Check case-insensitive
    cursor.execute("""
        SELECT COUNT(*) FROM insights
        WHERE LOWER(topic) = 'game development' AND is_archived = 0
    """)
    lower_count = cursor.fetchone()[0]
    print(f"   Case-insensitive match: {lower_count}")

    # Show sample insights if any exist
    cursor.execute("""
        SELECT topic, text, created_at
        FROM insights
        WHERE LOWER(topic) LIKE '%game%' AND is_archived = 0
        LIMIT 3
    """)

    samples = cursor.fetchall()
    if samples:
        print("\n📝 Sample insights:")
        for topic, text, created in samples:
            print(f"   Topic: '{topic}'")
            print(f"   Text: {text[:80]}...")
            print(f"   Created: {created}")
            print()

    # Check if user is following the topic
    cursor.execute("""
        SELECT user_id, topic FROM user_topics
        WHERE LOWER(topic) LIKE '%game%'
    """)

    follows = cursor.fetchall()
    if follows:
        print("👤 Users following game-related topics:")
        for user_id, topic in follows:
            print(f"   {user_id}: {topic}")
    else:
        print("⚠️  No users following game-related topics")

    conn.close()

if __name__ == "__main__":
    check_insights()
