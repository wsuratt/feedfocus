"""
Quick test script to verify automation is working
Run this before full population
"""

import asyncio
import sys
import os

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from automation.topic_handler import process_topic
from automation.semantic_db import get_stats


async def test_single_topic():
    """Test with a single topic"""
    
    test_topic = "value investing"
    
    print(f"\n{'='*80}")
    print(f"TESTING AUTOMATION WITH: {test_topic}")
    print(f"{'='*80}\n")
    
    # Get initial stats
    print("Initial DB stats:")
    stats = get_stats()
    print(f"  Total insights: {stats['total_insights']}")
    
    # Process topic
    print(f"\nProcessing topic...")
    result = await process_topic(test_topic)
    
    # Get final stats
    print(f"\nFinal DB stats:")
    stats = get_stats()
    print(f"  Total insights: {stats['total_insights']}")
    
    print(f"\n{'='*80}")
    print(f"TEST RESULT:")
    print(f"  Status: {result['status']}")
    print(f"  Topic: {result['topic']}")
    print(f"  Sources: {result.get('sources_count', 0)}")
    print(f"  Insights added: {result.get('insights_count', 0)}")
    print(f"{'='*80}\n")
    
    if result['status'] == 'success' and result.get('insights_count', 0) > 0:
        print("✅ Test passed! Automation is working.")
        return True
    else:
        print("❌ Test failed. Check errors above.")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_single_topic())
    sys.exit(0 if success else 1)
