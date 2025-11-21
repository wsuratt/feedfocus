# Database Setup & Content Population Guide

Complete guide for initializing databases and populating with content.

## Overview

Your app uses two databases:
1. **SQLite** (`insights.db`) - Stores insights, topics, engagement
2. **ChromaDB** (`chroma_db/`) - Vector database for semantic search

## Step 1: Initialize SQLite Database

Creates all tables (user_interests, insights, feed_queue, etc.)

```bash
python db/init_db.py
```

**Output:**
```
Initializing database at: /path/to/insights.db
✅ Database initialized successfully
✅ user_interests table created
📋 Tables created: user_interests, insights, feed_queue, insight_engagement
```

**Verify:**
```bash
ls -la insights.db
# Should show file with size > 0
```

---

## Step 2: Populate with Content

### Quick Test (10 topics, ~10 minutes)

```bash
python automation/initial_population.py 10
```

**This will:**
1. Process 10 popular topics (AI, Machine Learning, etc.)
2. For each topic:
   - Discover 5-10 sources using web search
   - Evaluate source quality
   - Extract 5-10 insights per source
   - Store in both SQLite and ChromaDB
3. Save checkpoint after each batch

**Example output:**
```
================================================================================
INITIAL POPULATION - 2025-11-21T17:00:00
Processing 10 topics in batches of 10
================================================================================

Batch 1/1: 10 topics
================================================================================

  ✓ artificial intelligence: 47 insights
  ✓ machine learning: 52 insights
  ✓ software engineering: 38 insights
  ...

================================================================================
POPULATION COMPLETE
Success: 10/10
Failed: 0
Duration: 12.4 minutes
================================================================================
```

### Full Population (200+ topics, 4-6 hours)

```bash
# Run in background
nohup python automation/initial_population.py > population.log 2>&1 &

# Monitor progress
tail -f population.log

# Check checkpoint file
cat population_checkpoint.json
```

**Topics included:**
- Technology (AI, ML, Cloud, DevOps, etc.)
- Business (Startups, Marketing, Finance)
- Science (Physics, Biology, Climate)
- And 200+ more categories

---

## Step 3: Resume if Interrupted

The script saves checkpoints automatically:

```bash
# If script stops/crashes, just re-run
python automation/initial_population.py

# Output:
# 📁 Resuming from checkpoint
#    Completed: 47
#    Remaining: 153
```

**Checkpoint file:** `population_checkpoint.json`

---

## Step 4: Verify Population

```bash
# Check SQLite
sqlite3 insights.db "SELECT COUNT(*) FROM insights;"
# Should show: 5000+ insights

# Check ChromaDB
ls -la chroma_db/
# Should show directories with data

# Check via API
curl http://localhost:8000/api/feed?limit=10
# Should return insights
```

---

## Automation Scripts

### Initial Population
```bash
# Test with 10 topics
python automation/initial_population.py 10

# Full population
python automation/initial_population.py
```

### Daily Refresh
```bash
# Run daily to refresh content for existing topics
python automation/daily_refresh.py
```

**Setup cron job:**
```bash
crontab -e

# Add this line to run daily at 2 AM
0 2 * * * cd /path/to/feedfocus && python automation/daily_refresh.py
```

---

## On AWS EC2 (After Deployment)

### Initialize Database

```bash
ssh -i your-key.pem ubuntu@YOUR_EC2_IP

cd ~/feedfocus

# Initialize DB
python db/init_db.py

# Or via Docker
docker-compose exec backend python db/init_db.py
```

### Populate Content (Background)

```bash
# Start population in background
nohup python automation/initial_population.py > population.log 2>&1 &

# Disconnect from SSH (it keeps running)
exit

# Later, check progress
ssh -i your-key.pem ubuntu@YOUR_EC2_IP
tail ~/feedfocus/population.log
```

### Setup Daily Refresh

```bash
# On EC2
crontab -e

# Add:
0 2 * * * cd /home/ubuntu/feedfocus && /usr/bin/python3 automation/daily_refresh.py >> /home/ubuntu/feedfocus/cron.log 2>&1
```

---

## Troubleshooting

### Database locked error
```bash
# Stop Docker services
docker-compose down

# Run initialization
python db/init_db.py

# Restart
docker-compose up -d
```

### API keys not found
```bash
# Check .env file
cat .env

# Should contain:
# ANTHROPIC_API_KEY=sk-ant-...
# GROQ_API_KEY=gsk_...
```

### ChromaDB errors
```bash
# Remove and recreate
rm -rf chroma_db/
python automation/initial_population.py 10
```

### Out of memory
```bash
# Reduce batch size in initial_population.py
# Edit line 135:
batch_size=5  # Instead of 10
```

---

## Cost Estimates

### API Costs (Anthropic + Groq)

**For 10 topics:**
- ~$0.50 - $1.00

**For full population (200 topics):**
- ~$10 - $20

**Daily refresh:**
- ~$0.50 - $1.00 per day

### Time Estimates

| Operation | Time | Insights |
|-----------|------|----------|
| 10 topics | 10-15 min | ~400-500 |
| 30 topics | 30-45 min | ~1,200-1,500 |
| 100 topics | 2-3 hours | ~4,000-5,000 |
| 200 topics | 4-6 hours | ~8,000-10,000 |

---

## Recommended Approach

### For Development:
```bash
# Start small
python automation/initial_population.py 10

# Test the app
python start.sh
# Visit http://localhost:3000

# Add more topics as needed
python automation/initial_population.py 30
```

### For Production:
```bash
# 1. Deploy to AWS
# 2. Initialize DB
docker-compose exec backend python db/init_db.py

# 3. Populate with 30-50 core topics first
python automation/initial_population.py 50

# 4. Test the app works
curl http://YOUR_EC2_IP

# 5. Run full population overnight
nohup python automation/initial_population.py > population.log 2>&1 &

# 6. Setup daily refresh
crontab -e  # Add daily refresh job
```

---

## Quick Reference

```bash
# Initialize database
python db/init_db.py

# Populate 10 topics (testing)
python automation/initial_population.py 10

# Populate all topics
python automation/initial_population.py

# Resume from checkpoint
python automation/initial_population.py

# Daily refresh
python automation/daily_refresh.py

# Check database
sqlite3 insights.db "SELECT COUNT(*) FROM insights;"
```

**You're ready to populate your database!** 🚀
