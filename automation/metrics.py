"""
Simple metrics logging for monitoring population and discovery
"""

import json
from datetime import datetime
from pathlib import Path

METRICS_FILE = "logs/metrics.json"

def log_metric(event: str, data: dict):
    """
    Log a metric event
    
    Args:
        event: Event name (e.g., 'topic_processed', 'topic_failed')
        data: Event data dictionary
    """
    
    Path("logs").mkdir(exist_ok=True)
    
    metric = {
        "timestamp": datetime.now().isoformat(),
        "event": event,
        **data
    }
    
    # Append to file
    with open(METRICS_FILE, 'a') as f:
        f.write(json.dumps(metric) + '\n')
    
    print(f"📊 {event}: {data}")


def get_metrics_summary():
    """Get summary of all metrics"""
    
    if not Path(METRICS_FILE).exists():
        return {"total_events": 0}
    
    metrics = []
    with open(METRICS_FILE, 'r') as f:
        for line in f:
            metrics.append(json.loads(line))
    
    # Aggregate
    summary = {
        "total_events": len(metrics),
        "topics_processed": sum(1 for m in metrics if m['event'] == 'topic_processed'),
        "topics_failed": sum(1 for m in metrics if m['event'] == 'topic_failed'),
        "total_insights": sum(m.get('insights', 0) for m in metrics if m['event'] == 'topic_processed'),
        "avg_duration_sec": sum(m.get('duration_sec', 0) for m in metrics if m['event'] == 'topic_processed') / max(1, sum(1 for m in metrics if m['event'] == 'topic_processed')),
    }
    
    return summary


if __name__ == "__main__":
    # Print summary
    summary = get_metrics_summary()
    print("\n📊 Metrics Summary")
    print("=" * 50)
    for key, value in summary.items():
        print(f"{key}: {value}")
