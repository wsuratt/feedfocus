"""Sync insights from ChromaDB to SQLite insights table"""
import sqlite3
import os
import sys
import uuid
from datetime import datetime

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
DB_PATH = os.path.join(PROJECT_ROOT, "insights.db")

from automation.semantic_db import collection

def sync_chromadb_to_sqlite():
    """Export all insights from ChromaDB and import to SQLite"""
    print("🔄 Syncing ChromaDB → SQLite...\n")

    # Get all insights from ChromaDB
    print("1. Fetching insights from ChromaDB...")
    try:
        results = collection.get()
        ids = results.get("ids", [])
        metadatas = results.get("metadatas", [])

        print(f"   Found {len(ids)} insights in ChromaDB\n")

        if not ids:
            print("⚠️  No insights found in ChromaDB")
            return

    except Exception as e:
        print(f"❌ Error reading from ChromaDB: {e}")
        return

    # Connect to SQLite
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Import to SQLite
    print("2. Importing to SQLite...")
    imported = 0
    skipped = 0
    errors = 0

    for i, (chroma_id, metadata) in enumerate(zip(ids, metadatas), 1):
        try:
            # Check if already exists in SQLite
            cursor.execute("SELECT id FROM insights WHERE chroma_id = ?", (chroma_id,))
            if cursor.fetchone():
                skipped += 1
                continue

            # Insert into SQLite
            insight_id = str(uuid.uuid4())
            topic = metadata.get("topic", "")
            category = metadata.get("category", "")
            text = metadata.get("text", "")
            source_url = metadata.get("source_url", "")
            source_domain = metadata.get("source_domain", "")
            quality_score = float(metadata.get("quality_score", 0))
            extracted_at = metadata.get("extracted_at", datetime.now().isoformat())

            cursor.execute("""
                INSERT INTO insights (
                    id, topic, category, text, source_url, source_domain,
                    quality_score, engagement_score, created_at, updated_at,
                    is_archived, chroma_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                insight_id,
                topic,
                category,
                text,
                source_url,
                source_domain,
                quality_score,
                0.0,  # engagement_score starts at 0
                extracted_at,
                datetime.now().isoformat(),
                0,  # not archived
                chroma_id
            ))

            imported += 1

            if i % 100 == 0:
                print(f"   Progress: {i}/{len(ids)} ({imported} imported, {skipped} skipped)")
                conn.commit()

        except Exception as e:
            errors += 1
            print(f"   ⚠️  Error importing insight {i}: {e}")

    conn.commit()
    conn.close()

    print(f"\n✅ Sync complete!")
    print(f"   Imported: {imported}")
    print(f"   Skipped (already exist): {skipped}")
    print(f"   Errors: {errors}")
    print(f"   Total in ChromaDB: {len(ids)}")

    # Show topics
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

    print("\n📊 Top topics in SQLite after sync:")
    for topic, count in cursor.fetchall():
        print(f"   {topic}: {count} insights")

    conn.close()

if __name__ == "__main__":
    sync_chromadb_to_sqlite()
