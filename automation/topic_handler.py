"""
Handles topic processing with dynamic query generation
Workflow: generate queries → discover → extract → import
"""

import asyncio
import sys
import os
from datetime import datetime
from typing import Dict, List
from dotenv import load_dotenv
from anthropic import Anthropic

# Load environment variables
load_dotenv()

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automation.discover_sources import discover_sources_with_queries
from automation.extraction import extract_from_url
from automation.semantic_db import add_insights_batch
from automation.metrics import log_metric

# Initialize Anthropic client
client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))


def generate_search_queries(topic: str, count: int = 6) -> List[str]:
    """
    Generate optimized search queries for any topic
    
    Args:
        topic: User's interest (e.g., "longevity research", "remote work trends")
        count: Number of queries to generate
    
    Returns:
        List of search query strings
    """
    
    prompt = f"""Generate {count} search queries for finding the BEST insights on: "{topic}"

CRITICAL: Design queries to find:
✅ Case studies from specific companies/people
✅ Strategic frameworks and playbooks  
✅ Counterintuitive findings with data
✅ Primary sources (annual letters, interviews, research papers)

❌ AVOID queries that find:
- "Best of" listicles
- Generic tips and advice
- Stock picks / product recommendations
- Performance predictions

FORMULA: [Specific Company/Person] + [Topic] + [Strategy/Framework/Result]

Good examples:
- "Airbnb remote work policy employee retention"
- "Basecamp async communication case study"
- "Warren Buffett investment framework"
- "Shopify AI automation workflow results"
- "Berkshire Hathaway annual letter insights"
- "YC startup fundraising playbook"

Bad examples:
- "best remote work tips 2025"
- "top value stocks to buy"
- "AI trends report 2024"

Now generate {count} queries for "{topic}" following this pattern.

Return ONLY a JSON array of query strings, no explanation."""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Parse response
        import json
        queries_text = response.content[0].text.strip()
        
        # Handle markdown code blocks
        if queries_text.startswith("```"):
            queries_text = queries_text.split("```")[1]
            if queries_text.startswith("json"):
                queries_text = queries_text[4:]
            queries_text = queries_text.strip()
        
        queries = json.loads(queries_text)
        return queries
        
    except Exception as e:
        print(f"  ⚠️  Failed to generate queries with Claude: {e}")
        
        # Fallback: case study focused queries
        return [
            f"{topic} case study analysis",
            f"{topic} strategic framework",
            f"{topic} research findings",
            f"{topic} implementation guide",
            f"{topic} best practices results",
            f"{topic} expert insights"
        ]


async def process_topic(user_topic: str) -> dict:
    """
    Complete pipeline with dynamic query generation
    No mapping needed - works for ANY topic
    
    Args:
        user_topic: User's interest (any string)
    
    Returns:
        Dict with status and results
    """
    
    print(f"\n🎯 Processing topic: {user_topic}")
    start_time = datetime.now()
    
    try:
        # 1. Generate search queries for this topic
        phase_start = datetime.now()
        print(f"  1/4 Generating search queries...")
        queries = generate_search_queries(user_topic)
        phase_time = (datetime.now() - phase_start).total_seconds()
        print(f"  Generated {len(queries)} queries (took {phase_time:.1f}s):")
        for q in queries:
            print(f"    - {q}")
        
        # 2. Discover sources using ground truth discovery logic
        phase_start = datetime.now()
        print(f"  2/4 Discovering sources...")
        sources = await discover_sources_with_queries(queries, max_results=50)
        phase_time = (datetime.now() - phase_start).total_seconds()
        print(f"  Discovery phase completed in {phase_time:.1f}s")
        
        if not sources:
            print(f"  ⚠️  No sources found")
            return {
                "status": "no_sources",
                "topic": user_topic,
                "sources_count": 0,
                "insights_count": 0
            }
        
        # Take top 40 sources (was 15 - too aggressive, caused 93% extraction failure)
        # With 40 sources: 40 × 30% success rate = 12 successful extractions
        # 12 × 5 insights each = 60 insights → 20-30 after filtering ✅
        sources.sort(key=lambda x: x.get('quality_score', 0), reverse=True)
        top_sources = sources[:40]
        urls = [s['url'] for s in top_sources]
        
        avg_quality = sum(s['quality_score'] for s in top_sources) / len(top_sources) if top_sources else 0
        print(f"  Selected {len(urls)} sources (avg quality: {avg_quality:.1f})")
        print(f"    [DEBUG] Quality range: {top_sources[0]['quality_score']:.0f} (best) to {top_sources[-1]['quality_score']:.0f} (worst)")
        
        # 3. Extract insights
        phase_start = datetime.now()
        print(f"  3/4 Extracting insights from {len(urls)} sources...")
        
        extraction_results = []
        successful = 0
        failed = 0
        
        for idx, url in enumerate(urls, 1):
            try:
                # Progress update every 5 URLs
                if idx % 5 == 0:
                    elapsed = (datetime.now() - phase_start).total_seconds()
                    print(f"    Progress: {idx}/{len(urls)} URLs processed ({elapsed:.1f}s elapsed)...")
                
                result = await extract_from_url(url, topic=user_topic)  # Pass topic for training logging
                if result and result.get('status') == 'success':
                    extraction_results.append(result)
                    insight_count = result.get('insight_count', 0)
                    successful += 1
                    print(f"    ✓ {url[:60]}... ({insight_count} insights)")
                else:
                    failed += 1
                    print(f"    ✗ {url[:60]}... (extraction returned no insights)")
            except Exception as e:
                failed += 1
                print(f"    ✗ {url[:60]}... - {str(e)[:50]}")
        
        phase_time = (datetime.now() - phase_start).total_seconds()
        success_rate = (successful / len(urls) * 100) if urls else 0
        print(f"    [DEBUG] Extraction: {successful} succeeded, {failed} failed ({success_rate:.0f}% success rate, {phase_time:.1f}s total)")
        
        # 4. Import to vector DB
        print(f"  4/4 Importing to vector DB...")
        
        insights_to_add = []
        for result in extraction_results:
            for category, items in result['insights'].items():
                if not isinstance(items, list):
                    continue
                
                for item in items:
                    insights_to_add.append({
                        'text': item,
                        'category': category,
                        'topic': user_topic,  # Use exact user topic
                        'source_url': result['url'],
                        'source_domain': result['source_domain'],
                        'quality_score': result.get('quality_score', 0),
                        'extracted_at': result['extracted_at'],
                    })
        
        print(f"    [DEBUG] Total insights before filtering: {len(insights_to_add)}")
        if len(insights_to_add) == 0:
            print(f"    [WARNING] No insights extracted from {len(extraction_results)} sources!")
            print(f"    [DEBUG] Extraction results structure:")
            for result in extraction_results[:2]:  # Show first 2
                print(f"      URL: {result.get('url', 'unknown')[:60]}")
                print(f"      Insights keys: {list(result.get('insights', {}).keys())}")
                for cat, items in result.get('insights', {}).items():
                    print(f"        {cat}: {len(items) if isinstance(items, list) else 'not a list'} items")
        
        added_ids = add_insights_batch(insights_to_add, topic=user_topic)
        
        duration = (datetime.now() - start_time).total_seconds()
        
        print(f"  ✓ Completed {user_topic}")
        print(f"    Sources: {len(extraction_results)}")
        print(f"    Insights: {len(added_ids)}")
        print(f"    Duration: {duration:.1f}s")
        
        # Log metrics
        log_metric("topic_processed", {
            "topic": user_topic,
            "duration_sec": duration,
            "sources": len(extraction_results),
            "insights": len(added_ids),
            "avg_quality": avg_quality,
            "success": True
        })
        
        return {
            "status": "success",
            "topic": user_topic,
            "sources_count": len(extraction_results),
            "insights_count": len(added_ids)
        }
        
    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        
        print(f"  ✗ Error processing {user_topic}: {e}")
        
        log_metric("topic_failed", {
            "topic": user_topic,
            "duration_sec": duration,
            "error": str(e),
            "success": False
        })
        
        return {
            "status": "error",
            "topic": user_topic,
            "error": str(e)
        }


if __name__ == "__main__":
    # Test with any topic
    test_topic = sys.argv[1] if len(sys.argv) > 1 else "longevity research"
    
    print(f"Testing topic handler with: {test_topic}")
    result = asyncio.run(process_topic(test_topic))
    
    print(f"\n{'='*80}")
    print(f"Result: {result}")
    print(f"{'='*80}")