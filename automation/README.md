# Automation Setup

Production-ready automation for populating and maintaining the insight feed.

## Files Created

### Core Modules
- **`popular_topics.py`** - Curated list of 100 popular topics
- **`topic_handler.py`** - Processes single topics (discover → extract → import)
- **`metrics.py`** - Logs metrics for monitoring
- **`extraction.py`** - Production extraction module

### Scripts
- **`initial_population.py`** - One-time population with checkpointing
- **`daily_refresh.py`** - Daily cron job for refreshing topics
- **`test_automation.py`** (in root) - Quick test script

## Quick Start

### 1. Test Setup (5 minutes)
```bash
# Test with a single topic
python test_automation.py

# Or test topic handler directly
python automation/topic_handler.py "remote work trends"
```

### 2. Initial Population - Small Test (30 minutes)
```bash
# Test with 5 topics
python automation/initial_population.py 5

# Check results
python semantic_db.py test
python automation/metrics.py
```

### 3. Core Topics for Deployment (2-3 hours)
```bash
# Populate 30 most important topics
python automation/initial_population.py 30
```

### 4. Full Population (Optional, 3-4 hours)
```bash
# All 100 topics
python automation/initial_population.py
```

## Features

### ✅ Parallel Batching
- Processes 10 topics in parallel
- 2-minute pause between batches
- Reduces total time by ~70%

### ✅ Checkpoint Recovery
- Saves progress after each batch
- Auto-resumes if interrupted
- No lost work on crashes

### ✅ Metrics Logging
- Logs every topic attempt
- Tracks duration, sources, insights
- View summary: `python automation/metrics.py`

### ✅ Production Extraction
- Uses `extraction.py` (not test files)
- Hallucination removal
- Quality scoring
- Retry logic

## Deployment

### Option 1: Railway Cron (Recommended)
```bash
# 1. Deploy app
railway up

# 2. Run initial population on server
railway run python automation/initial_population.py 30

# 3. Set up cron in Railway dashboard
# Command: python automation/daily_refresh.py
# Schedule: 0 2 * * 0  (Weekly on Sunday at 2 AM)
```

### Option 2: Local Then Deploy
```bash
# 1. Populate locally
python automation/initial_population.py 30

# 2. Deploy with populated DB
railway up
```

## Monitoring

### Check Logs
```bash
# View metrics
python automation/metrics.py

# Check latest refresh log
cat logs/daily_refresh_$(date +%Y%m%d).json

# Check checkpoint
cat population_checkpoint.json
```

### Health Check
```bash
# Test a single topic
python automation/topic_handler.py "AI agents development"

# Check DB stats
python semantic_db.py test
```

## Troubleshooting

### "No sources found"
- Check if topic is in `SEARCH_QUERIES` in `discover_sources.py`
- Add custom queries for new topics

### "Extraction failed"
- Check Groq API key: `echo $GROQ_API_KEY`
- Check rate limits (30 requests/min)

### "Import failed"
- Check ChromaDB is accessible
- Verify semantic_db.py can write

### Resume from checkpoint
```bash
# Auto-resumes by default
python automation/initial_population.py

# Or force fresh start
rm population_checkpoint.json
python automation/initial_population.py
```

## Cost Estimates

**Groq API (Free Tier):**
- Per topic: ~15 sources × $0.001 = ~$0.015
- 30 topics: ~$0.45
- 100 topics: ~$1.50
- Daily refresh: ~$1.50/day

**Note:** Groq has generous free tier limits, should be free for testing.

## Next Steps

1. ✅ Test with 5 topics
2. ✅ Verify feed displays correctly
3. ✅ Deploy with 30 core topics
4. ✅ Set up Railway Cron (weekly initially)
5. ✅ Monitor for 1 week
6. ✅ Increase to daily refresh
7. ✅ Expand to 100+ topics
