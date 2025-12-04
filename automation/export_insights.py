#!/usr/bin/env python3
"""
Export all insights from ChromaDB before migration
"""
import json
import chromadb
from chromadb.config import Settings
import os

# Path to existing ChromaDB
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROMA_PATH = os.path.join(PROJECT_ROOT, "chroma_db")

print(f"Connecting to ChromaDB at: {CHROMA_PATH}")

try:
    # Connect to existing database
    client = chromadb.PersistentClient(
        path=CHROMA_PATH,
        settings=Settings(
            anonymized_telemetry=False,
            allow_reset=True,
        ),
    )
    
    # Get the insights collection
    collection = client.get_collection("insights")
    
    # Get all items (ChromaDB limits to 100 by default, so we paginate)
    all_insights = []
    offset = 0
    batch_size = 1000
    
    print("Exporting insights...")
    
    while True:
        # Get a batch
        results = collection.get(
            limit=batch_size,
            offset=offset,
            include=["metadatas", "documents"]
        )
        
        if not results["ids"]:
            break
        
        # Add to our export
        for i, insight_id in enumerate(results["ids"]):
            metadata = results["metadatas"][i] if results["metadatas"] else {}
            document = results["documents"][i] if results["documents"] else ""
            
            all_insights.append({
                "id": insight_id,
                "text": metadata.get("text", document),
                "category": metadata.get("category", ""),
                "topic": metadata.get("topic", ""),
                "source_url": metadata.get("source_url", ""),
                "source_domain": metadata.get("source_domain", ""),
                "quality_score": metadata.get("quality_score", 0.0),
                "extracted_at": metadata.get("extracted_at", ""),
                "detected_year": metadata.get("detected_year"),
            })
        
        print(f"  Exported {len(all_insights)} insights...")
        offset += batch_size
    
    # Save to JSON
    export_file = os.path.join(PROJECT_ROOT, "insights_backup.json")
    with open(export_file, "w") as f:
        json.dump(all_insights, f, indent=2)
    
    print(f"\n✅ Exported {len(all_insights)} insights to: {export_file}")
    print(f"\nNext steps:")
    print(f"1. Copy this file to your server")
    print(f"2. Delete chroma_db/ folder")
    print(f"3. Restart backend (new schema will be created)")
    print(f"4. Run import_insights.py to restore data")

except Exception as e:
    print(f"❌ Error: {e}")
    print("\nIf you get 'no such column: collections.topic', the DB is already corrupted.")
    print("You may need to manually extract from the SQLite file.")
