#!/usr/bin/env python3
"""
View and analyze training data collected for SLM fine-tuning
"""

import json
import sys
import os
from collections import Counter, defaultdict
from datetime import datetime

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from automation.training_logger import get_training_stats, EXTRACTION_LOG, FEEDBACK_LOG, QUERY_LOG


def view_extraction_samples(limit=5):
    """View recent extraction samples"""
    print("\n" + "="*80)
    print("EXTRACTION SAMPLES")
    print("="*80)
    
    if not EXTRACTION_LOG.exists():
        print("No extraction logs yet")
        return
    
    with open(EXTRACTION_LOG) as f:
        lines = f.readlines()
    
    print(f"\nTotal samples: {len(lines)}")
    print(f"\nShowing last {limit} samples:\n")
    
    for i, line in enumerate(lines[-limit:], 1):
        data = json.loads(line)
        print(f"{i}. {data['topic']} | {data['source_url'][:60]}...")
        print(f"   Quality: {data['quality_score']:.1f} | Passed: {data['passed_filters']}")
        print(f"   Insights: {data['insight_count']}")
        print(f"   Content length: {len(data['source_content'])} chars")
        print()


def view_feedback_samples(limit=10):
    """View recent feedback"""
    print("\n" + "="*80)
    print("FEEDBACK SAMPLES")
    print("="*80)
    
    if not FEEDBACK_LOG.exists():
        print("No feedback logs yet")
        return
    
    with open(FEEDBACK_LOG) as f:
        lines = f.readlines()
    
    print(f"\nTotal events: {len(lines)}")
    
    # Count by action
    actions = Counter()
    for line in lines:
        data = json.loads(line)
        actions[data['action']] += 1
    
    print(f"\nAction breakdown:")
    for action, count in actions.most_common():
        print(f"  {action}: {count}")
    
    print(f"\nShowing last {limit} events:\n")
    for i, line in enumerate(lines[-limit:], 1):
        data = json.loads(line)
        print(f"{i}. {data['action']} | Insight: {data['insight_id']}")


def analyze_quality_distribution():
    """Analyze quality score distribution"""
    print("\n" + "="*80)
    print("QUALITY ANALYSIS")
    print("="*80)
    
    if not EXTRACTION_LOG.exists():
        print("No extraction logs yet")
        return
    
    scores = []
    passed_count = 0
    topics = Counter()
    
    with open(EXTRACTION_LOG) as f:
        for line in f:
            data = json.loads(line)
            scores.append(data['quality_score'])
            if data['passed_filters']:
                passed_count += 1
            topics[data['topic']] += 1
    
    print(f"\nQuality score distribution:")
    print(f"  Min: {min(scores):.1f}")
    print(f"  Max: {max(scores):.1f}")
    print(f"  Avg: {sum(scores)/len(scores):.1f}")
    print(f"  Median: {sorted(scores)[len(scores)//2]:.1f}")
    
    print(f"\nFilter pass rate: {passed_count}/{len(scores)} ({passed_count/len(scores)*100:.1f}%)")
    
    print(f"\nTop topics:")
    for topic, count in topics.most_common(10):
        print(f"  {topic}: {count} samples")


def export_for_finetuning(output_file="training_data/finetuning_data.jsonl"):
    """Export high-quality samples for fine-tuning"""
    print("\n" + "="*80)
    print("EXPORT FOR FINE-TUNING")
    print("="*80)
    
    if not EXTRACTION_LOG.exists():
        print("No extraction logs yet")
        return
    
    # Filter for high quality samples
    exported = 0
    
    with open(EXTRACTION_LOG) as f_in:
        with open(output_file, 'w') as f_out:
            for line in f_in:
                data = json.loads(line)
                
                # Only export if:
                # 1. Passed filters
                # 2. Quality score >= 70
                # 3. Has at least 2 insights
                if (data['passed_filters'] and 
                    data['quality_score'] >= 70 and 
                    data['insight_count'] >= 2):
                    
                    # Format for fine-tuning
                    training_sample = {
                        "messages": [
                            {
                                "role": "system",
                                "content": "You are an expert at extracting actionable insights from content."
                            },
                            {
                                "role": "user",
                                "content": f"Topic: {data['topic']}\n\nContent:\n{data['source_content']}"
                            },
                            {
                                "role": "assistant",
                                "content": json.dumps({"insights": data['extracted_insights']})
                            }
                        ]
                    }
                    
                    f_out.write(json.dumps(training_sample) + '\n')
                    exported += 1
    
    print(f"\nExported {exported} high-quality samples to: {output_file}")
    print(f"Ready for fine-tuning with OpenAI, Anthropic, or Llama!")


if __name__ == "__main__":
    print("\n" + "="*80)
    print("TRAINING DATA VIEWER")
    print("="*80)
    
    stats = get_training_stats()
    print(f"\nOverall stats:")
    print(f"  Extraction samples: {stats['extraction_samples']}")
    print(f"  Feedback events: {stats['feedback_events']}")
    print(f"  Query samples: {stats['query_samples']}")
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "extraction":
            view_extraction_samples(limit=10)
        elif cmd == "feedback":
            view_feedback_samples(limit=20)
        elif cmd == "analyze":
            analyze_quality_distribution()
        elif cmd == "export":
            export_for_finetuning()
        else:
            print(f"\nUnknown command: {cmd}")
            print("Usage: python view_training_data.py [extraction|feedback|analyze|export]")
    else:
        # Show all
        view_extraction_samples()
        view_feedback_samples()
        analyze_quality_distribution()
        
        if stats['extraction_samples'] >= 100:
            print("\n" + "="*80)
            print("💡 TIP: You have enough samples to export for fine-tuning!")
            print("    Run: python view_training_data.py export")
            print("="*80)
