"""
One-time script to populate vector DB with popular topics
Run this once before deployment
"""

import asyncio
import sys
import os
import json
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automation.popular_topics import POPULAR_TOPICS, get_core_topics
from automation.topic_handler import process_topic

CHECKPOINT_FILE = "population_checkpoint.json"


def save_checkpoint(results: dict):
    """Save progress after each batch"""
    with open(CHECKPOINT_FILE, 'w') as f:
        json.dump(results, f, indent=2)


def load_checkpoint() -> dict:
    """Load previous progress"""
    try:
        with open(CHECKPOINT_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return None


async def populate_popular_topics(batch_size: int = 10, topics_limit: int = None, resume: bool = True):
    """
    Populate topics in parallel batches with checkpoint recovery
    
    Args:
        batch_size: Process N topics in parallel (default 10)
        topics_limit: Limit for testing (e.g., 30 topics)
        resume: Resume from checkpoint if available
    """
    
    # Load checkpoint
    checkpoint = load_checkpoint() if resume else None
    
    if checkpoint:
        completed_topics = {r['topic'] for r in checkpoint['successful']}
        
        # Apply topics_limit when resuming
        if topics_limit and topics_limit <= 30:
            all_topics = get_core_topics(topics_limit)
        else:
            all_topics = POPULAR_TOPICS[:topics_limit] if topics_limit else POPULAR_TOPICS
        
        topics_to_process = [t for t in all_topics if t not in completed_topics]
        
        print(f"📁 Resuming from checkpoint")
        print(f"   Completed: {len(completed_topics)}")
        print(f"   Total limit: {len(all_topics)}")
        print(f"   Remaining: {len(topics_to_process)}")
        
        results = checkpoint
    else:
        # Use core topics if limit is specified, otherwise all
        if topics_limit and topics_limit <= 30:
            topics_to_process = get_core_topics(topics_limit)
        else:
            topics_to_process = POPULAR_TOPICS[:topics_limit] if topics_limit else POPULAR_TOPICS
        
        results = {
            "successful": [],
            "failed": [],
            "start_time": datetime.now().isoformat(),
        }
    
    print(f"\n{'='*80}")
    print(f"INITIAL POPULATION - {datetime.now().isoformat()}")
    print(f"Processing {len(topics_to_process)} topics in batches of {batch_size}")
    print(f"{'='*80}\n")
    
    # Process in batches
    for i in range(0, len(topics_to_process), batch_size):
        batch = topics_to_process[i:i+batch_size]
        batch_num = i // batch_size + 1
        total_batches = (len(topics_to_process) + batch_size - 1) // batch_size
        
        print(f"\n{'='*80}")
        print(f"Batch {batch_num}/{total_batches}: {len(batch)} topics")
        print(f"{'='*80}\n")
        
        # Process batch in parallel
        tasks = [process_topic(topic) for topic in batch]
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Collect results
        for topic, result in zip(batch, batch_results):
            if isinstance(result, Exception):
                print(f"  ✗ {topic}: {result}")
                results["failed"].append({"topic": topic, "error": str(result)})
            else:
                print(f"  ✓ {topic}: {result.get('insights_count', 0)} insights")
                results["successful"].append(result)
        
        # Save checkpoint after each batch
        save_checkpoint(results)
        
        # Rate limit between batches
        if i + batch_size < len(topics_to_process):
            print(f"\n⏸️  Pausing 120s between batches...")
            await asyncio.sleep(120)
    
    results["end_time"] = datetime.now().isoformat()
    results["success_rate"] = f"{len(results['successful'])}/{len(POPULAR_TOPICS)}"
    
    # Save final results
    with open(f"population_results_{datetime.now().strftime('%Y%m%d_%H%M')}.json", 'w') as f:
        json.dump(results, f, indent=2)
    
    # Calculate duration
    start = datetime.fromisoformat(results['start_time'])
    end = datetime.fromisoformat(results['end_time'])
    duration_minutes = (end - start).total_seconds() / 60
    
    print(f"\n{'='*80}")
    print(f"POPULATION COMPLETE")
    print(f"Success: {len(results['successful'])}/{len(topics_to_process)}")
    print(f"Failed: {len(results['failed'])}")
    print(f"Duration: {duration_minutes:.1f} minutes")
    print(f"{'='*80}\n")
    
    return results


if __name__ == "__main__":
    # Allow limiting topics for testing
    # Usage: python automation/initial_population.py 30
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    
    asyncio.run(populate_popular_topics(
        batch_size=2,  # Reduced to 2 for t3.small stability
        topics_limit=limit,
        resume=True
    ))
