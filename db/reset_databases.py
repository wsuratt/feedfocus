"""Reset both SQLite insights and ChromaDB to start fresh"""
import sqlite3
import os
import chromadb
from chromadb.config import Settings

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "insights.db")
CHROMA_PATH = os.path.join(PROJECT_ROOT, "chroma_db")


def reset_databases():
    """
    Clear both SQLite insights and ChromaDB collection.
    Preserves user data (profiles, affinities, engagement).
    """
    print("Resetting databases...\n")

    # 1. Clear SQLite insights table
    print("1. Clearing SQLite insights table...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get count before deletion
    cursor.execute("SELECT COUNT(*) FROM insights")
    before_count = cursor.fetchone()[0]

    # Delete all insights
    cursor.execute("DELETE FROM insights")
    conn.commit()

    # Reset autoincrement
    cursor.execute("DELETE FROM sqlite_sequence WHERE name='insights'")
    conn.commit()
    conn.close()

    print(f"   Deleted {before_count} insights from SQLite")

    # 2. Clear ChromaDB collection
    print("\n2. Clearing ChromaDB collection...")
    try:
        client = chromadb.PersistentClient(
            path=CHROMA_PATH,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True,
            ),
        )

        # Get count before deletion
        try:
            collection = client.get_collection('insights')
            before_chroma = collection.count()

            # Delete collection
            client.delete_collection('insights')
            print(f"   Deleted {before_chroma} embeddings from ChromaDB")

        except Exception:
            print("   ChromaDB collection doesn't exist or is already empty")

        # Recreate empty collection
        collection = client.create_collection(
            name="insights",
            metadata={"description": "Insight vectors for personalized feed"},
        )
        print(f"   Created fresh ChromaDB collection")

    except Exception as e:
        print(f"   Error resetting ChromaDB: {e}")

    print("\n✅ Database reset complete!")
    print("\nPreserved:")
    print("  - User profiles")
    print("  - Topic affinities")
    print("  - User engagement history")
    print("  - Topic similarities table")
    print("\nCleared:")
    print("  - All insights (SQLite)")
    print("  - All embeddings (ChromaDB)")
    print("\nNext steps:")
    print("  Run extraction to add new insights: python automation/extraction.py")


def show_status():
    """Show current database status"""
    print("\n=== Current Database Status ===\n")

    # SQLite
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM insights")
    insights_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM user_profiles")
    profiles_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM user_topic_affinities")
    affinities_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM user_engagement")
    engagement_count = cursor.fetchone()[0]

    conn.close()

    print(f"SQLite:")
    print(f"  Insights: {insights_count}")
    print(f"  User profiles: {profiles_count}")
    print(f"  Topic affinities: {affinities_count}")
    print(f"  Engagement records: {engagement_count}")

    # ChromaDB
    try:
        client = chromadb.PersistentClient(path=CHROMA_PATH)
        try:
            collection = client.get_collection('insights')
            chroma_count = collection.count()
            print(f"\nChromaDB:")
            print(f"  Embeddings: {chroma_count}")
        except Exception:
            print(f"\nChromaDB:")
            print(f"  Collection doesn't exist")
    except Exception as e:
        print(f"\nChromaDB: Error - {e}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "status":
        show_status()
    else:
        # Show current status
        show_status()

        # Confirm before resetting
        print("\n⚠️  This will DELETE all insights and embeddings!")
        response = input("Are you sure? (yes/no): ")

        if response.lower() == 'yes':
            reset_databases()
            show_status()
        else:
            print("Reset cancelled.")
