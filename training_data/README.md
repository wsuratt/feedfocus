# Training Data Collection

This directory contains training data logs for fine-tuning a smaller, cheaper LLM to replace Claude for insight extraction.

## Files

- `extraction_logs.jsonl` - Extraction inputs/outputs with quality scores
- `feedback_logs.jsonl` - User engagement data (likes, dismissals, saves, etc.)
- `query_logs.jsonl` - Query generation with source quality feedback

## Format

### extraction_logs.jsonl
```jsonl
{"timestamp": "2024-11-20T10:30:00Z", "stage": "extraction", "topic": "value investing", "source_url": "https://...", "source_content": "...", "extracted_insights": [...], "quality_score": 8.5, "passed_filters": true}
```

### feedback_logs.jsonl
```jsonl
{"timestamp": "2024-11-20T12:00:00Z", "insight_id": "abc123", "action": "like", "topic": "value investing", "shown_count": 50}
```

### query_logs.jsonl
```jsonl
{"timestamp": "2024-11-20T09:00:00Z", "topic": "value investing", "queries": ["13F filings hedge fund value", ...], "sources_found": 15, "avg_quality": 7.2}
```

## Training Pipeline

1. **Collect 500-1000 extraction examples** (2-3 months of usage)
2. **Filter by quality:**
   - Quality score ≥ 7
   - User engagement (likes - dismissals) > 0
   - Shown to ≥ 10 users
3. **Fine-tune GPT-4o-mini or Llama 3.1 8B**
4. **A/B test:** Claude vs fine-tuned model
5. **Switch if quality ≥ 90% of Claude**

## Cost Savings

**Current:** Claude = $0.003/source × 40 sources = $0.12/topic

**After fine-tuning:** GPT-4o-mini = $0.0001/source × 40 sources = $0.004/topic

**Savings:** 97% cost reduction (30x cheaper)
