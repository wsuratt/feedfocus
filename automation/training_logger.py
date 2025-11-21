"""
Training data logger for fine-tuning SLM to replace Claude
Logs extraction inputs/outputs and user feedback to JSONL files
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional
import asyncio
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
TRAINING_DATA_DIR = PROJECT_ROOT / "training_data"

# Ensure directory exists
TRAINING_DATA_DIR.mkdir(exist_ok=True)

EXTRACTION_LOG = TRAINING_DATA_DIR / "extraction_logs.jsonl"
FEEDBACK_LOG = TRAINING_DATA_DIR / "feedback_logs.jsonl"
QUERY_LOG = TRAINING_DATA_DIR / "query_logs.jsonl"


def log_extraction(
    topic: str,
    source_url: str,
    source_content: str,
    extracted_insights: List[Dict],
    quality_score: Optional[float] = None,
    passed_filters: bool = True,
    extraction_time_sec: Optional[float] = None
):
    """
    Log extraction attempt for training data
    
    Args:
        topic: Topic being processed
        source_url: URL of source
        source_content: First 8000 chars of content
        extracted_insights: List of insights extracted by Claude
        quality_score: SLM quality score (if evaluated)
        passed_filters: Whether insights passed quality filters
        extraction_time_sec: Time taken to extract (optional)
    """
    try:
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "stage": "extraction",
            "topic": topic,
            "source_url": source_url,
            "source_content": source_content[:8000],  # First 8K chars
            "extracted_insights": extracted_insights,
            "quality_score": quality_score,
            "passed_filters": passed_filters,
            "extraction_time_sec": extraction_time_sec,
            "insight_count": len(extracted_insights)
        }
        
        # Append to JSONL file
        with open(EXTRACTION_LOG, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
            
    except Exception as e:
        # Don't fail extraction if logging fails
        print(f"⚠️  Training logger error: {e}")


def log_feedback(
    insight_id: str,
    action: str,
    topic: Optional[str] = None,
    metadata: Optional[Dict] = None
):
    """
    Log user feedback for training data
    
    Args:
        insight_id: ID of insight
        action: 'like', 'x' (dismiss), 'bookmark', 'share'
        topic: Topic insight belongs to
        metadata: Additional metadata (shown_count, etc.)
    """
    try:
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "insight_id": insight_id,
            "action": action,
            "topic": topic,
            **(metadata or {})
        }
        
        with open(FEEDBACK_LOG, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
            
    except Exception as e:
        print(f"⚠️  Feedback logger error: {e}")


def log_query_generation(
    topic: str,
    queries: List[str],
    sources_found: int,
    avg_quality: Optional[float] = None,
    top_domains: Optional[List[str]] = None
):
    """
    Log query generation for training data
    
    Args:
        topic: Topic being processed
        queries: Generated search queries
        sources_found: Number of sources discovered
        avg_quality: Average quality score of sources
        top_domains: List of top-quality domains found
    """
    try:
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "stage": "query_generation",
            "topic": topic,
            "queries": queries,
            "sources_found": sources_found,
            "avg_quality": avg_quality,
            "top_domains": top_domains or []
        }
        
        with open(QUERY_LOG, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
            
    except Exception as e:
        print(f"⚠️  Query logger error: {e}")


def get_training_stats() -> Dict:
    """Get statistics about collected training data"""
    stats = {
        "extraction_samples": 0,
        "feedback_events": 0,
        "query_samples": 0
    }
    
    try:
        if EXTRACTION_LOG.exists():
            with open(EXTRACTION_LOG) as f:
                stats["extraction_samples"] = sum(1 for _ in f)
        
        if FEEDBACK_LOG.exists():
            with open(FEEDBACK_LOG) as f:
                stats["feedback_events"] = sum(1 for _ in f)
        
        if QUERY_LOG.exists():
            with open(QUERY_LOG) as f:
                stats["query_samples"] = sum(1 for _ in f)
    
    except Exception as e:
        print(f"⚠️  Stats error: {e}")
    
    return stats


if __name__ == "__main__":
    # Test logging
    print("Testing training logger...")
    
    log_extraction(
        topic="test topic",
        source_url="https://example.com",
        source_content="Test content...",
        extracted_insights=[{"text": "Test insight", "category": "test"}],
        quality_score=8.0,
        passed_filters=True
    )
    
    log_feedback(
        insight_id="test123",
        action="like",
        topic="test topic"
    )
    
    log_query_generation(
        topic="test topic",
        queries=["test query 1", "test query 2"],
        sources_found=10,
        avg_quality=7.5
    )
    
    stats = get_training_stats()
    print(f"✅ Training data stats: {stats}")
