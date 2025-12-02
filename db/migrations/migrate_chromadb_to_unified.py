#!/usr/bin/env python3
"""
Migrate insights from ChromaDB to unified feed SQLite schema

Strategy:
- Export all 1830 insights from ChromaDB
- Import into SQLite unified feed structure
- Keep ChromaDB for deduplication only
- Use SQLite for feed queries
"""
import sqlite3
import chromadb
import uuid
import os
import sys
import json
from datetime import datetime
from typing import Dict, List

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# Paths
DB_PATH = os.path.join(PROJECT_ROOT, "insights.db")
CHROMA_PATH = os.path.join(PROJECT_ROOT, "chroma_db")

print("🚀 Starting ChromaDB → SQLite migration...")
print(f"📁 ChromaDB: {CHROMA_PATH}")
print(f"📁 SQLite: {DB_PATH}")
print()

def estimate_quality_score(text: str, metadata: Dict) -> float:
    """Estimate quality score from insight characteristics"""
    score = 0.5  # Base score
    
    # Length factor (sweet spot 100-300 chars)
    text_len = len(text)
    if 100 <= text_len <= 300:
        score += 0.2
    elif 50 <= text_len < 100:
        score += 0.1
    
    # Has numbers/data
    if any(char.isdigit() for char in text):
        score += 0.1
    
    # Has source
    if metadata.get('source_url'):
        score += 0.1
    
    # Category quality
    category = metadata.get('category', '')
    if category.lower() in ['case_study', 'playbook', 'counterintuitive']:
        score += 0.1
    
    return min(score, 1.0)

def normalize_category(category: str) -> str:
    """Normalize category names"""
    mapping = {
        'key_insights': 'INSIGHT',
        'case_study': 'CASE STUDY',
        'playbook': 'PLAYBOOK',
        'trends': 'TREND',
        'counterintuitive': 'COUNTERINTUITIVE',
        'opportunity': 'OPPORTUNITY',
    }
    return mapping.get(category.lower(), category.upper())

def migrate_chromadb_insights():
    """Export insights from ChromaDB and import to SQLite"""
    
    # Connect to ChromaDB
    print("🔗 Connecting to ChromaDB...")
    chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = chroma_client.get_collection("insights")
    total_count = collection.count()
    print(f"✅ Found {total_count} insights in ChromaDB")
    print()
    
    # Get all insights (ChromaDB limits to 10k per query, batch if needed)
    print("📥 Fetching insights from ChromaDB...")
    results = collection.get(
        include=['metadatas', 'documents']
    )
    
    chroma_ids = results['ids']
    metadatas = results['metadatas']
    documents = results['documents']
    
    print(f"✅ Fetched {len(chroma_ids)} insights")
    print()
    
    # Connect to SQLite
    print("🔗 Connecting to SQLite...")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Stats
    inserted = 0
    skipped = 0
    topics_found = set()
    
    print("📦 Migrating insights...")
    for i, chroma_id in enumerate(chroma_ids):
        if i % 100 == 0 and i > 0:
            print(f"  Progress: {i}/{len(chroma_ids)} ({(i/len(chroma_ids)*100):.1f}%)")
        
        metadata = metadatas[i]
        text = metadata.get('text', documents[i] if documents else '')
        
        # Skip if no text
        if not text or len(text) < 20:
            skipped += 1
            continue
        
        # Extract fields
        topic = metadata.get('topic', 'General')
        category = normalize_category(metadata.get('category', 'INSIGHT'))
        source_url = metadata.get('source_url', '')
        source_domain = metadata.get('source_domain', '')
        
        # Track topics
        topics_found.add(topic)
        
        # Generate scores
        quality_score = metadata.get('quality_score', estimate_quality_score(text, metadata))
        engagement_score = 0.0  # Will be calculated from actual engagement
        
        # Timestamps
        created_at = metadata.get('extracted_at', datetime.now().isoformat())
        
        # Generate new UUID for unified feed
        insight_id = str(uuid.uuid4())
        
        # Insert into SQLite
        try:
            cursor.execute("""
                INSERT INTO insights (
                    id, topic, category, text, source_url, source_domain,
                    quality_score, engagement_score, created_at,
                    chroma_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                insight_id,
                topic,
                category,
                text,
                source_url,
                source_domain,
                quality_score,
                engagement_score,
                created_at,
                chroma_id  # Store ChromaDB ID for reference
            ))
            inserted += 1
        except sqlite3.IntegrityError:
            skipped += 1
            continue
    
    # Commit insights
    conn.commit()
    print(f"✅ Migrated {inserted} insights ({skipped} skipped)")
    print()
    
    # Create topics metadata
    print("📚 Creating topic metadata...")
    for topic in topics_found:
        # Count insights per topic
        cursor.execute("""
            SELECT COUNT(*) as count, AVG(quality_score) as avg_quality
            FROM insights
            WHERE topic = ? AND is_archived = 0
        """, (topic,))
        row = cursor.fetchone()
        
        topic_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT OR IGNORE INTO topics (
                id, name, insight_count, avg_quality_score, updated_at
            ) VALUES (?, ?, ?, ?, ?)
        """, (
            topic_id,
            topic,
            row[0],  # count
            row[1] or 0.5,  # avg_quality_score
            datetime.now().isoformat()
        ))
    
    conn.commit()
    print(f"✅ Created metadata for {len(topics_found)} topics")
    print()
    
    # Migrate user topics (from old user_interests)
    print("👤 Migrating user topics...")
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='user_interests'
    """)
    if cursor.fetchone():
        cursor.execute("SELECT * FROM user_interests")
        old_interests = cursor.fetchall()
        
        for interest in old_interests:
            user_id = 'default'  # Single user for now
            topic = interest['topic']
            
            cursor.execute("""
                INSERT OR IGNORE INTO user_topics (
                    user_id, topic, followed_at
                ) VALUES (?, ?, ?)
            """, (user_id, topic, interest.get('created_at', datetime.now().isoformat())))
        
        conn.commit()
        print(f"✅ Migrated {len(old_interests)} user topic follows")
    else:
        print("⚠️  No user_interests table found")
    print()
    
    # Summary
    conn.close()
    
    print("=" * 60)
    print("MIGRATION SUMMARY")
    print("=" * 60)
    print(f"📦 Insights migrated: {inserted}")
    print(f"⏭️  Insights skipped: {skipped}")
    print(f"📚 Topics found: {len(topics_found)}")
    print()
    print("Top topics:")
    
    # Reconnect to show stats
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT topic, COUNT(*) as count
        FROM insights
        WHERE is_archived = 0
        GROUP BY topic
        ORDER BY count DESC
        LIMIT 10
    """)
    for row in cursor.fetchall():
        print(f"  • {row[0]}: {row[1]} insights")
    
    conn.close()
    
    print()
    print("✅ Migration complete!")
    print()
    print("📝 Next steps:")
    print("1. ChromaDB is still intact - used for dedup only")
    print("2. New insights will be added to both ChromaDB (dedup) and SQLite (feed)")
    print("3. Feed queries now use SQLite for better filtering/ranking")
    print("4. Update extraction pipeline to write to both databases")

if __name__ == "__main__":
    try:
        migrate_chromadb_insights()
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
