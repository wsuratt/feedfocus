# Extraction Pipeline Deployment Checklist

Quick reference for deploying to production. For detailed instructions, see `extraction-pipeline-deployment.md`.

## Pre-Deployment (Local)

```bash
# Run all tests
cd /Users/williamsuratt/Documents/feedfocus-dev/feedfocus

□ python -m pytest tests/unit/ -v
□ python tests/test_integration_new_topic.py
□ python tests/test_integration_similar_topic.py
□ python tests/test_integration_retry.py
□ python tests/test_concurrent_extraction.py
□ python tests/test_error_handling.py
□ python tests/test_daily_refresh.py
□ python tests/test_end_to_end.py

# Push to main
□ git add .
□ git commit -m "Add extraction pipeline feature"
□ git push origin main
```

---

## Backend Deployment

```bash
# 1. SSH to server
ssh ubuntu@feed-focus.com
cd /home/ubuntu/feedfocus

# 2. Backup database
□ cp insights.db insights.db.backup-$(date +%Y%m%d-%H%M%S)

# 3. Pull latest code
□ git pull origin main

# 4. Run migration
□ sqlite3 insights.db < db/migrations/002_extraction_jobs.sql
□ sqlite3 insights.db "SELECT name FROM sqlite_master WHERE type='table' AND name='extraction_jobs';"
   # Should output: extraction_jobs

# 5. Restart backend
□ sudo systemctl restart feedfocus

# 6. Verify startup (wait 10 seconds)
□ sudo systemctl status feedfocus
□ sudo journalctl -u feedfocus -n 50 | grep "WAL mode enabled"
□ sudo journalctl -u feedfocus -n 50 | grep "ExtractionQueue initialized"

# 7. Test queue health
□ curl https://api.feed-focus.com/api/queue/health
   # Should return: workers_active: 2, queue_size: 0
```

---

## Daily Refresh Setup

Choose ONE option:

### Option A: Cron (Simple)
```bash
cd /home/ubuntu/feedfocus/automation
□ bash setup_cron.sh
□ crontab -l | grep daily_refresh  # Verify installed
```

### Option B: Systemd (Production)
```bash
cd /home/ubuntu/feedfocus/automation
□ sudo cp feedfocus-daily-refresh.service /etc/systemd/system/
□ sudo cp feedfocus-daily-refresh.timer /etc/systemd/system/
□ sudo systemctl daemon-reload
□ sudo systemctl enable feedfocus-daily-refresh.timer
□ sudo systemctl start feedfocus-daily-refresh.timer
□ systemctl list-timers | grep feedfocus  # Verify scheduled
```

### Test Daily Refresh
```bash
□ /home/ubuntu/feedfocus/.venv/bin/python automation/daily_refresh_queue.py --dry-run
□ # Review output, ensure no errors
```

---

## Mobile App Update

```bash
# Local machine
cd feedfocus-mobile

# Verify .env has production URLs
□ cat .env | grep API_URL
   # Should be: https://api.feed-focus.com

# Test locally
□ npx expo start
□ # Test search → follow topic → progress screen

# Build for production
□ npx expo build:ios   # For iOS
□ npx expo build:android  # For Android
```

---

## Verification Tests

### 1. API Endpoints
```bash
# Get JWT token from app or Supabase
export TOKEN="your_jwt_token_here"

# Test follow topic
□ curl -X POST https://api.feed-focus.com/api/topics/follow \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"topic": "deployment test topic"}'

# Test status endpoint
□ curl "https://api.feed-focus.com/api/topics/deployment%20test%20topic/status" \
  -H "Authorization: Bearer $TOKEN"

# Test queue health
□ curl https://api.feed-focus.com/api/queue/health
```

### 2. Database Check
```bash
ssh ubuntu@feed-focus.com

# Check WAL mode
□ sqlite3 /home/ubuntu/feedfocus/insights.db "PRAGMA journal_mode;"
   # Should return: wal

# Check recent jobs
□ sqlite3 /home/ubuntu/feedfocus/insights.db \
  "SELECT topic, status, priority, created_at FROM extraction_jobs ORDER BY created_at DESC LIMIT 5;"
```

### 3. Mobile App
```bash
□ Open FeedFocus app
□ Tap search icon (left of profile)
□ Search for "artificial intelligence"
□ Tap "Follow" button
□ Verify navigation to progress screen
□ Verify status updates (polling works)
□ Verify completion message
```

---

## Monitoring (First 24 Hours)

### Hour 1
```bash
□ Watch backend logs: sudo journalctl -u feedfocus -f
□ Check queue health every 15 min
□ Test 2-3 topic follows via mobile app
```

### Hour 6
```bash
□ Review backend logs for errors
□ Check extraction job completion rate
□ Verify no database locks
```

### After First Daily Refresh (2 AM Next Day)
```bash
# Check daily refresh ran
□ tail -100 /home/ubuntu/feedfocus/logs/daily_refresh.log
   # OR
□ sudo journalctl -u feedfocus-daily-refresh.service --since "02:00"

# Verify topics were queued
□ sqlite3 /home/ubuntu/feedfocus/insights.db \
  "SELECT COUNT(*) FROM extraction_jobs WHERE user_id='system' AND created_at > datetime('now', '-2 hours');"
```

---

## Rollback (If Needed)

```bash
ssh ubuntu@feed-focus.com
cd /home/ubuntu/feedfocus

# 1. Stop service
□ sudo systemctl stop feedfocus

# 2. Rollback code
□ git log --oneline -5  # Find previous commit
□ git checkout <previous-commit-hash>

# 3. Restore database (if needed)
□ ls insights.db.backup-*
□ cp insights.db.backup-YYYYMMDD-HHMMSS insights.db
□ rm -f insights.db-wal insights.db-shm

# 4. Restart
□ sudo systemctl start feedfocus

# 5. Disable daily refresh
□ crontab -e  # Comment out line
   # OR
□ sudo systemctl stop feedfocus-daily-refresh.timer
```

---

## Success Criteria ✅

Deployment successful when:

□ Backend starts without errors
□ `sudo journalctl -u feedfocus | grep "WAL mode enabled"`
□ `sudo journalctl -u feedfocus | grep "ExtractionQueue initialized with 2 workers"`
□ `curl https://api.feed-focus.com/api/queue/health` returns `workers_active: 2`
□ Mobile app search works
□ Following new topic shows progress screen
□ Progress screen polls and updates
□ Extraction completes successfully
□ Daily refresh scheduled (timer shows in `systemctl list-timers`)
□ No errors in logs for 1 hour

---

## Emergency Contacts

**If issues persist:**
1. Check detailed troubleshooting: `docs/deployment/extraction-pipeline-deployment.md`
2. Review implementation docs: `docs/features/extraction-pipeline-implementation.md`
3. Run diagnostics:
   ```bash
   sudo journalctl -u feedfocus --since "1 hour ago" > backend-logs.txt
   curl https://api.feed-focus.com/api/queue/health > queue-health.json
   ```

---

## Notes

- **Database grows**: ~10-50 MB per day with normal usage
- **WAL files**: Normal to see `.db-wal` and `.db-shm` files
- **Worker count**: 2 workers is optimal for current server specs
- **Daily refresh**: Runs at 2:00 AM, takes 5-15 minutes
- **Priority**: Daily refresh (10) > User requests (1)

---

**Total Deployment Time:** ~30-45 minutes
**Monitoring Required:** First 24 hours
**Expected Downtime:** ~30 seconds (backend restart)
