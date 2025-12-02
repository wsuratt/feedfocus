"""
Migration script: Transform old agent-based insights to unified feed

This script:
1. Creates new unified feed tables
2. Migrates existing insights from insights_v2 to insights
3. Migrates user interests to user_topics
4. Preserves engagement data
5. Creates topic metadata
"""

import sqlite3
import json
import os
import sys
from datetime import datetime
import uuid

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, PROJECT_ROOT)

DB_PATH = os.path.join(PROJECT_ROOT, "insights.db")
MIGRATION_SQL = os.path.join(PROJECT_ROOT, "db", "migrations", "001_unified_feed.sql")


def run_migration_sql(conn):
    """Execute the migration SQL file"""
    print("📝 Running migration SQL...")
    
    with open(MIGRATION_SQL, 'r') as f:
        migration_sql = f.read()
    
    cursor = conn.cursor()
    cursor.executescript(migration_sql)
    conn.commit()
    
    print("✅ Migration SQL executed")


def migrate_insights(conn):
    """
    Migrate insights from insights_v2 + agents to new insights table
    """
    print("\n📦 Migrating insights...")
    
    cursor = conn.cursor()
    
    # Get all insights with their agent info
    cursor.execute("""
        SELECT 
            i.id,
            i.agent_id,
            a.topic,
            i.url,
            i.source_name,
            i.extracted_data,
            i.date_crawled
        FROM insights_v2 i
        LEFT JOIN agents a ON i.agent_id = a.id
        WHERE a.topic IS NOT NULL
    """)
    
    old_insights = cursor.fetchall()
    print(f"Found {len(old_insights)} insights to migrate")
    
    migrated = 0
    skipped = 0
    
    for row in old_insights:
        legacy_id = row[0]
        legacy_agent_id = row[1]
        topic = row[2]
        source_url = row[3]
        source_name = row[4]
        extracted_data_json = row[5]
        date_crawled = row[6]
        
        # Parse extracted data
        try:
            extracted_data = json.loads(extracted_data_json)
        except:
            print(f"⚠️  Skipping insight {legacy_id}: Invalid JSON")
            skipped += 1
            continue
        
        # Generate insight text from extracted data
        insight_text = generate_insight_text(extracted_data)
        if not insight_text or len(insight_text) < 20:
            print(f"⚠️  Skipping insight {legacy_id}: No valid text")
            skipped += 1
            continue
        
        # Categorize insight
        category = categorize_insight(extracted_data)
        
        # Extract domain from URL
        source_domain = extract_domain(source_url)
        
        # Generate quality score (placeholder - will be improved)
        quality_score = estimate_quality_score(insight_text, extracted_data)
        
        # Generate UUID for new insight
        insight_id = str(uuid.uuid4())
        
        # Insert into new insights table
        try:
            cursor.execute("""
                INSERT INTO insights (
                    id, topic, category, text, source_url, source_domain,
                    quality_score, engagement_score, created_at,
                    legacy_insight_id, legacy_agent_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                insight_id,
                topic,
                category,
                insight_text,
                source_url,
                source_domain,
                quality_score,
                0.0,  # Default engagement score
                date_crawled,
                legacy_id,
                legacy_agent_id
            ))
            migrated += 1
        except Exception as e:
            print(f"⚠️  Error migrating insight {legacy_id}: {e}")
            skipped += 1
            continue
    
    conn.commit()
    print(f"✅ Migrated {migrated} insights ({skipped} skipped)")


def migrate_user_interests(conn):
    """
    Migrate user_interests to user_topics
    Default user_id = 1 for MVP (single user)
    """
    print("\n👤 Migrating user interests...")
    
    cursor = conn.cursor()
    
    # Get unique topics from user_interests
    cursor.execute("""
        SELECT DISTINCT topic, MIN(created_at) as first_added
        FROM user_interests
        GROUP BY topic
    """)
    
    interests = cursor.fetchall()
    print(f"Found {len(interests)} user interests")
    
    # Insert into user_topics (use 'default' as user_id for MVP)
    for row in interests:
        topic = row[0]
        created_at = row[1]
        
        cursor.execute("""
            INSERT OR IGNORE INTO user_topics (user_id, topic, followed_at)
            VALUES (?, ?, ?)
        """, ('default', topic, created_at))
    
    conn.commit()
    print(f"✅ Migrated {len(interests)} user interests")


def migrate_engagement(conn):
    """
    Migrate insight_engagement to user_engagement
    """
    print("\n💚 Migrating engagement data...")
    
    cursor = conn.cursor()
    
    # Get old engagement records
    # Check if table exists first
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='insight_engagement'
    """)
    
    if not cursor.fetchone():
        print("⚠️  No insight_engagement table found, skipping...")
        return
    
    # Check what columns exist in the old table
    cursor.execute("PRAGMA table_info(insight_engagement)")
    columns = [row[1] for row in cursor.fetchall()]
    has_created_at = 'created_at' in columns
    
    # Build query based on available columns
    if has_created_at:
        cursor.execute("""
            SELECT 
                id,
                user_id,
                insight_id,
                action,
                created_at
            FROM insight_engagement
        """)
    else:
        # Use CURRENT_TIMESTAMP if created_at doesn't exist
        cursor.execute("""
            SELECT 
                id,
                user_id,
                insight_id,
                action,
                CURRENT_TIMESTAMP as created_at
            FROM insight_engagement
        """)
    
    old_engagements = cursor.fetchall()
    print(f"Found {len(old_engagements)} engagement records")
    
    migrated = 0
    
    for row in old_engagements:
        legacy_id = row[0]
        user_id = row[1]
        legacy_insight_id = row[2]
        action = row[3]
        engaged_at = row[4]
        
        # Find new insight ID
        cursor.execute("""
            SELECT id FROM insights WHERE legacy_insight_id = ?
        """, (legacy_insight_id,))
        
        result = cursor.fetchone()
        if not result:
            continue  # Insight wasn't migrated
        
        new_insight_id = result[0]
        
        # Map action names if needed
        if action == 'skip':
            action = 'dismiss'
        
        # Convert action to 'view' if it was shown in feed
        # (We'll assume engagement means they viewed it)
        if action in ['like', 'bookmark', 'dismiss']:
            # Insert view action first
            cursor.execute("""
                INSERT OR IGNORE INTO user_engagement (id, user_id, insight_id, action, created_at)
                VALUES (?, ?, ?, 'view', ?)
            """, (str(uuid.uuid4()), f"user_{user_id}", new_insight_id, engaged_at))
        
        # Insert the actual engagement
        cursor.execute("""
            INSERT OR IGNORE INTO user_engagement (id, user_id, insight_id, action, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (str(uuid.uuid4()), f"user_{user_id}", new_insight_id, action, engaged_at))
        
        migrated += 1
    
    conn.commit()
    print(f"✅ Migrated {migrated} engagement records")


def create_topic_metadata(conn):
    """
    Create topics metadata table with counts
    """
    print("\n📚 Creating topic metadata...")
    
    cursor = conn.cursor()
    
    # Get unique topics with counts
    cursor.execute("""
        SELECT 
            topic,
            COUNT(*) as insight_count
        FROM insights
        WHERE is_archived = 0
        GROUP BY topic
    """)
    
    topics = cursor.fetchall()
    
    for row in topics:
        topic = row[0]
        insight_count = row[1]
        
        # Count followers
        cursor.execute("""
            SELECT COUNT(*) FROM user_topics WHERE topic = ?
        """, (topic,))
        follower_count = cursor.fetchone()[0]
        
        # Insert or update topic
        cursor.execute("""
            INSERT OR REPLACE INTO topics (topic, insight_count, follower_count)
            VALUES (?, ?, ?)
        """, (topic, insight_count, follower_count))
    
    conn.commit()
    print(f"✅ Created metadata for {len(topics)} topics")


def calculate_engagement_scores(conn):
    """
    Calculate engagement scores for insights based on user interactions
    """
    print("\n📊 Calculating engagement scores...")
    
    cursor = conn.cursor()
    
    # Get insights with engagement data
    cursor.execute("""
        SELECT 
            i.id,
            COUNT(DISTINCT CASE WHEN e.action = 'view' THEN e.user_id END) as views,
            COUNT(DISTINCT CASE WHEN e.action = 'like' THEN e.user_id END) as likes,
            COUNT(DISTINCT CASE WHEN e.action = 'save' THEN e.user_id END) as saves
        FROM insights i
        LEFT JOIN user_engagement e ON i.id = e.insight_id
        GROUP BY i.id
        HAVING views > 0
    """)
    
    insights = cursor.fetchall()
    
    for row in insights:
        insight_id = row[0]
        views = row[1]
        likes = row[2]
        saves = row[3]
        
        # Calculate engagement score: (likes + saves) / views
        if views > 0:
            engagement_score = min((likes + saves) / views, 1.0)
        else:
            engagement_score = 0.0
        
        # Update insight
        cursor.execute("""
            UPDATE insights 
            SET engagement_score = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (engagement_score, insight_id))
    
    conn.commit()
    print(f"✅ Calculated engagement scores for {len(insights)} insights")


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def generate_insight_text(extracted_data: dict) -> str:
    """Generate full insight text from extracted data"""
    # Try to find the main text field
    for field_name, values in extracted_data.items():
        if isinstance(values, list) and len(values) > 0:
            if isinstance(values[0], str) and len(values[0]) > 20:
                return values[0]
    
    # Fallback: concatenate all text
    all_text = []
    for field_name, values in extracted_data.items():
        if isinstance(values, list):
            for value in values:
                if isinstance(value, str) and len(value) > 10:
                    all_text.append(value)
    
    return "\n\n".join(all_text) if all_text else ""


def categorize_insight(extracted_data: dict) -> str:
    """Categorize insight based on content"""
    data_str = json.dumps(extracted_data).lower()
    
    if any(word in data_str for word in ['case study', 'example', 'company', 'startup']):
        return 'CASE STUDY'
    elif any(word in data_str for word in ['how to', 'playbook', 'framework', 'strategy']):
        return 'PLAYBOOK'
    elif any(word in data_str for word in ['metric', 'benchmark', 'data', 'number', 'stat']):
        return 'TREND'
    elif any(word in data_str for word in ['surprising', 'unexpected', 'counterintuitive', 'paradox']):
        return 'COUNTERINTUITIVE'
    elif any(word in data_str for word in ['opportunity', 'gap', 'untapped', 'potential']):
        return 'OPPORTUNITY'
    else:
        return 'INSIGHT'


def extract_domain(url: str) -> str:
    """Extract domain from URL"""
    if not url:
        return ""
    
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc
        # Remove www.
        if domain.startswith('www.'):
            domain = domain[4:]
        return domain
    except:
        return ""


def estimate_quality_score(text: str, extracted_data: dict) -> float:
    """Estimate quality score (0-10) based on simple heuristics"""
    score = 5.0  # Start at middle
    
    # Length bonus (not too short, not too long)
    text_len = len(text)
    if 100 < text_len < 1000:
        score += 1.0
    elif text_len < 50:
        score -= 2.0
    
    # Specificity bonus (numbers, names, examples)
    if any(char.isdigit() for char in text):
        score += 1.0
    
    if text.count('.') >= 2:  # Multiple sentences
        score += 0.5
    
    # Extracted data richness
    field_count = len(extracted_data)
    if field_count >= 3:
        score += 1.0
    elif field_count == 1:
        score -= 0.5
    
    return max(0, min(10, score))


def print_migration_summary(conn):
    """Print summary of migration"""
    cursor = conn.cursor()
    
    print("\n" + "="*60)
    print("MIGRATION SUMMARY")
    print("="*60)
    
    # Count insights
    cursor.execute("SELECT COUNT(*) FROM insights")
    insight_count = cursor.fetchone()[0]
    print(f"📦 Insights migrated: {insight_count}")
    
    # Count topics
    cursor.execute("SELECT COUNT(*) FROM topics")
    topic_count = cursor.fetchone()[0]
    print(f"📚 Topics: {topic_count}")
    
    # Count user topics
    cursor.execute("SELECT COUNT(*) FROM user_topics")
    user_topic_count = cursor.fetchone()[0]
    print(f"👤 User topic follows: {user_topic_count}")
    
    # Count engagement
    cursor.execute("SELECT COUNT(*) FROM user_engagement")
    engagement_count = cursor.fetchone()[0]
    print(f"💚 Engagement records: {engagement_count}")
    
    # Show topic breakdown
    cursor.execute("""
        SELECT topic, insight_count, follower_count
        FROM topics
        ORDER BY insight_count DESC
        LIMIT 10
    """)
    
    print("\n📊 Top Topics:")
    for row in cursor.fetchall():
        print(f"  • {row[0]}: {row[1]} insights, {row[2]} followers")
    
    print("\n✅ Migration complete!")
    print("="*60)


def main():
    """Run the complete migration"""
    print("🚀 Starting unified feed migration...")
    print(f"📁 Database: {DB_PATH}")
    
    if not os.path.exists(DB_PATH):
        print("❌ Database not found! Run init_db.py first.")
        return
    
    conn = sqlite3.connect(DB_PATH)
    
    try:
        # Step 1: Run migration SQL
        run_migration_sql(conn)
        
        # Step 2: Migrate insights
        migrate_insights(conn)
        
        # Step 3: Migrate user interests
        migrate_user_interests(conn)
        
        # Step 4: Migrate engagement data
        migrate_engagement(conn)
        
        # Step 5: Create topic metadata
        create_topic_metadata(conn)
        
        # Step 6: Calculate engagement scores
        calculate_engagement_scores(conn)
        
        # Print summary
        print_migration_summary(conn)
        
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
