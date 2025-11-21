"""
Test script to verify quality improvements
Run after implementing quality fixes
"""

import asyncio
import sys
import os

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from automation.semantic_db import reset_database, get_stats
from automation.topic_handler import process_topic


async def test_quality():
    """Test quality improvements on a single topic"""
    
    print("\n" + "="*80)
    print("QUALITY TEST - Testing improved extraction and filtering")
    print("="*80 + "\n")
    
    # 1. Reset database
    print("Step 1: Resetting database...")
    confirm = input("This will delete all insights. Continue? (yes/no): ")
    if confirm.lower() != 'yes':
        print("Aborted.")
        return
    
    reset_database()
    print("✅ Database reset\n")
    
    # 2. Process one topic with quality fixes
    test_topic = "ai agents"
    
    print(f"Step 2: Processing '{test_topic}' with quality fixes...")
    print("Watch for:")
    print("  - ⏭️  Removed X duplicate insights")
    print("  - 🗑️  Filtered X low-quality insights")
    print("  - ✅ Adding Y/Z insights to DB (fewer = better quality)\n")
    
    result = await process_topic(test_topic)
    
    # 3. Show results
    print("\n" + "="*80)
    print("RESULTS:")
    print("="*80)
    print(f"Status: {result['status']}")
    print(f"Sources: {result.get('sources_count', 0)}")
    print(f"Insights added: {result.get('insights_count', 0)}")
    print(f"Duration: {result.get('duration_sec', 0):.1f}s")
    
    # 4. Check stats
    stats = get_stats()
    print(f"\nTotal in DB: {stats['total_insights']}")
    
    print("\n" + "="*80)
    print("NEXT STEPS:")
    print("="*80)
    print("1. Restart backend: cd backend && python main.py")
    print("2. Refresh frontend and check feed quality")
    print("3. Look for:")
    print("   ✅ No duplicates")
    print("   ✅ All insights have numbers")
    print("   ✅ No promotional content")
    print("   ✅ No website metadata")
    print("   ✅ More Tier 1 sources (gov, research, consulting)")
    print("\n4. Rate quality 1-10:")
    print("   - Target: 7-8/10 before scaling")
    print("   - If < 7: Review QUALITY_FIXES.md and tune thresholds")
    print("   - If >= 7: Test 4 more topics, then scale to 100")
    print("="*80 + "\n")


if __name__ == "__main__":
    asyncio.run(test_quality())
