#!/usr/bin/env python3
"""
Manual extraction tester - test extraction on specific URLs to debug issues
"""

import asyncio
import sys
import os

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from automation.extraction import extract_from_url
from automation.semantic_db import should_include_insight

async def test_extraction(url: str, topic: str = ""):
    """Test extraction on a single URL with detailed output"""
    
    print(f"\n{'='*80}")
    print(f"TESTING EXTRACTION")
    print(f"{'='*80}")
    print(f"URL: {url}")
    print(f"Topic: {topic or '(none)'}")
    print(f"{'='*80}\n")
    
    # Extract
    print("1️⃣  Extracting insights...")
    result = await extract_from_url(url)
    
    if not result or result.get('status') != 'success':
        print(f"❌ Extraction failed: {result.get('error', 'unknown error')}")
        return
    
    # Show raw results
    print(f"\n✅ Extraction succeeded!")
    print(f"   Source: {result.get('source_domain', 'unknown')}")
    print(f"   Quality score: {result.get('quality_score', 0)}")
    print(f"   Total insights: {result.get('insight_count', 0)}")
    
    insights_by_category = result.get('insights', {})
    
    print(f"\n{'='*80}")
    print(f"RAW EXTRACTED INSIGHTS")
    print(f"{'='*80}\n")
    
    total_raw = 0
    for category, items in insights_by_category.items():
        if not isinstance(items, list) or len(items) == 0:
            continue
        
        total_raw += len(items)
        print(f"\n📋 {category.upper().replace('_', ' ')} ({len(items)} insights)")
        print("-" * 80)
        
        for i, insight in enumerate(items, 1):
            print(f"\n{i}. {insight}")
    
    if total_raw == 0:
        print("\n⚠️  No insights extracted (LLM returned empty arrays)")
        print("\nPossible reasons:")
        print("  - Content is too promotional")
        print("  - Content is too generic/obvious")
        print("  - Extraction prompt is too strict")
        print("  - Content doesn't match topic well")
        return
    
    # Test filtering
    print(f"\n{'='*80}")
    print(f"FILTER TESTING (with topic: '{topic}')")
    print(f"{'='*80}\n")
    
    passed = []
    failed = []
    
    for category, items in insights_by_category.items():
        if not isinstance(items, list):
            continue
        
        for insight in items:
            if should_include_insight(insight, topic):
                passed.append((category, insight))
            else:
                failed.append((category, insight))
    
    print(f"\n✅ PASSED FILTERS ({len(passed)}/{total_raw}):")
    print("-" * 80)
    if passed:
        for i, (cat, insight) in enumerate(passed, 1):
            print(f"\n{i}. [{cat}]")
            print(f"   {insight}")
    else:
        print("\n(none)")
    
    print(f"\n\n❌ REJECTED BY FILTERS ({len(failed)}/{total_raw}):")
    print("-" * 80)
    if failed:
        for i, (cat, insight) in enumerate(failed, 1):
            print(f"\n{i}. [{cat}]")
            print(f"   {insight[:150]}...")
    else:
        print("\n(none)")
    
    # Summary
    print(f"\n{'='*80}")
    print(f"SUMMARY")
    print(f"{'='*80}")
    print(f"Raw extracted:     {total_raw}")
    print(f"Passed filters:    {len(passed)} ({len(passed)/total_raw*100:.0f}%)" if total_raw > 0 else "Passed filters: 0")
    print(f"Rejected:          {len(failed)} ({len(failed)/total_raw*100:.0f}%)" if total_raw > 0 else "Rejected: 0")
    print(f"{'='*80}\n")


async def main():
    """Run manual extraction test"""
    
    # Get URL from command line or use default
    if len(sys.argv) < 2:
        print("\nUsage: python test_manual_extraction.py <url> [topic]")
        print("\nExample:")
        print("  python test_manual_extraction.py https://example.com 'value investing'")
        print("\nOr edit the script to hardcode URLs for testing:\n")
        
        # EDIT THESE to test specific URLs
        test_urls = [
            ("https://substack.com/inbox/post/167069914", "value investing")
        ]
        
        if not test_urls:
            print("No URLs to test. Add URLs to the test_urls list or pass as argument.")
            return
        
        for url, topic in test_urls:
            await test_extraction(url, topic)
            if len(test_urls) > 1:
                print("\n" + "="*80 + "\n")
    else:
        url = sys.argv[1]
        topic = sys.argv[2] if len(sys.argv) > 2 else ""
        await test_extraction(url, topic)


if __name__ == "__main__":
    asyncio.run(main())
