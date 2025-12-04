#!/usr/bin/env python3
"""
Import insights from backup JSON into fresh ChromaDB
"""
import json
import os
import sys

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from automation.semantic_db import add_insight

def import_insights(backup_file):
    """Import insights from JSON backup"""
    
    if not os.path.exists(backup_file):
        print(f"❌ Backup file not found: {backup_file}")
        return
    
    print(f"Loading insights from: {backup_file}")
    
    with open(backup_file, "r") as f:
        insights = json.load(f)
    
    print(f"Found {len(insights)} insights to import")
    
    imported = 0
    skipped = 0
    
    for i, insight in enumerate(insights, 1):
        if i % 100 == 0:
            print(f"  Progress: {i}/{len(insights)} ({imported} imported, {skipped} skipped)")
        
        try:
            # Skip insights without required fields
            if not insight.get("text") or not insight.get("topic"):
                skipped += 1
                continue
            
            add_insight(insight)
            imported += 1
            
        except Exception as e:
            print(f"  ⚠️  Error importing insight {i}: {e}")
            skipped += 1
    
    print(f"\n✅ Import complete!")
    print(f"   Imported: {imported}")
    print(f"   Skipped: {skipped}")
    print(f"   Total: {len(insights)}")

if __name__ == "__main__":
    backup_file = os.path.join(PROJECT_ROOT, "insights_backup.json")
    
    if len(sys.argv) > 1:
        backup_file = sys.argv[1]
    
    import_insights(backup_file)
