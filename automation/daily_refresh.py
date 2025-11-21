"""
Runs daily via Railway Cron
Refreshes all popular topics to keep insights current
"""

import asyncio
import sys
import os
import json
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automation.popular_topics import POPULAR_TOPICS
from automation.topic_handler import process_topic


async def daily_refresh():
    """
    Daily refresh of popular topics
    Lighter than initial population - processes all topics
    """
    
    print(f"\n{'='*80}")
    print(f"DAILY REFRESH - {datetime.now().isoformat()}")
    print(f"{'='*80}\n")
    
    results = {
        "successful": [],
        "failed": [],
        "start_time": datetime.now().isoformat(),
    }
    
    # Process topics in batches to manage load
    batch_size = 10
    
    for i, topic in enumerate(POPULAR_TOPICS, 1):
        print(f"\n[{i}/{len(POPULAR_TOPICS)}] Refreshing: {topic}")
        
        try:
            result = await process_topic(topic)
            results["successful"].append(result)
            print(f"  ✓ Added {result.get('insights_count', 0)} insights")
            
        except Exception as e:
            print(f"  ✗ Failed: {e}")
            results["failed"].append({"topic": topic, "error": str(e)})
        
        # Rate limiting - pause every 10 topics
        if i % batch_size == 0 and i < len(POPULAR_TOPICS):
            print(f"\n⏸️  Pausing 60s...")
            await asyncio.sleep(60)
    
    results["end_time"] = datetime.now().isoformat()
    
    # Save log
    os.makedirs("logs", exist_ok=True)
    log_file = f"logs/daily_refresh_{datetime.now().strftime('%Y%m%d')}.json"
    with open(log_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    # Calculate duration
    start = datetime.fromisoformat(results['start_time'])
    end = datetime.fromisoformat(results['end_time'])
    duration_hours = (end - start).total_seconds() / 3600
    
    # Calculate statistics
    total_insights = sum(r.get('insights_count', 0) for r in results['successful'])
    
    print(f"\n{'='*80}")
    print(f"REFRESH COMPLETE")
    print(f"Success: {len(results['successful'])}/{len(POPULAR_TOPICS)}")
    print(f"Failed: {len(results['failed'])}")
    print(f"Total insights added: {total_insights}")
    print(f"Duration: {duration_hours:.1f} hours")
    print(f"Log saved to: {log_file}")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    asyncio.run(daily_refresh())
