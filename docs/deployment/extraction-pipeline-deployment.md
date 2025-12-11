# Extraction Pipeline Deployment Guide

Complete guide for deploying the extraction pipeline feature to production.

## 📋 Pre-Deployment Checklist

### Local Testing
- [ ] All unit tests pass: `python -m pytest tests/unit/`
- [ ] All integration tests pass: `python tests/test_integration_*.py`
- [ ] End-to-end tests pass: `python tests/test_end_to_end.py`
- [ ] Daily refresh test passes: `python tests/test_daily_refresh.py`
- [ ] Mobile app builds without errors
- [ ] No console errors in mobile app during testing

### Code Review
- [ ] All new endpoints documented
- [ ] Error handling comprehensive
- [ ] Logging statements in place
- [ ] No hardcoded values
- [ ] Environment variables documented

### Dependencies
- [ ] `requirements-backend.txt` up to date
- [ ] Mobile dependencies in `package.json`
- [ ] No new system dependencies needed

---

## 🚀 Deployment Steps

### Step 1: Backend Deployment

#### 1.1 SSH into Production Server
```bash
ssh ubuntu@feed-focus.com
cd /home/ubuntu/feedfocus
```

#### 1.2 Pull Latest Code
```bash
git fetch origin
git checkout main
git pull origin main
```

#### 1.3 Run Database Migration
```bash
# Backup current database first
cp insights.db insights.db.backup-$(date +%Y%m%d-%H%M%S)

# Run the extraction_jobs table migration
sqlite3 insights.db < db/migrations/002_extraction_jobs.sql

# Verify the table was created
sqlite3 insights.db "SELECT name FROM sqlite_master WHERE type='table' AND name='extraction_jobs';"
# Expected output: extraction_jobs

# Check indexes were created
sqlite3 insights.db ".indexes extraction_jobs"
# Expected: 7 indexes listed

# Verify schema
sqlite3 insights.db ".schema extraction_jobs"
```

**Note:** The migration is idempotent (uses `CREATE TABLE IF NOT EXISTS`), so it's safe to run multiple times.

#### 1.4 Restart Backend Service
```bash
# The backend startup event will automatically:
# - Enable WAL mode
# - Initialize extraction queue (2 workers)
# - Recover any stale jobs

sudo systemctl restart feedfocus
```

#### 1.5 Verify Backend Started
```bash
# Check service status
sudo systemctl status feedfocus

# Check logs for startup messages
sudo journalctl -u feedfocus -n 50 --no-pager

# Look for these log lines:
# ✓ "Database journal mode: wal"
# ✓ "WAL mode enabled - multiple workers can write concurrently"
# ✓ "ExtractionQueue initialized with 2 workers"
# ✓ "Recovered X stale jobs"
```

#### 1.6 Test API Endpoints
```bash
# Test queue health endpoint
curl https://api.feed-focus.com/api/queue/health

# Expected response:
# {
#   "workers_active": 2,
#   "queue_size": 0,
#   "jobs_processing": 0,
#   "completed_today": 0,
#   "failed_today": 0,
#   "avg_completion_time_minutes": 0,
#   "recent_failures": []
# }
```

---

### Step 2: Daily Refresh Setup

#### 2.1 Choose Scheduler (Cron or Systemd)

**Option A: Using Cron (Recommended for simplicity)**

```bash
cd /home/ubuntu/feedfocus/automation

# Review the cron setup script
cat setup_cron.sh

# Run the setup script
bash setup_cron.sh

# Verify cron job was added
crontab -l | grep daily_refresh
```

**Option B: Using Systemd Timer (Recommended for production)**

```bash
cd /home/ubuntu/feedfocus/automation

# Copy service and timer files
sudo cp feedfocus-daily-refresh.service /etc/systemd/system/
sudo cp feedfocus-daily-refresh.timer /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable and start the timer
sudo systemctl enable feedfocus-daily-refresh.timer
sudo systemctl start feedfocus-daily-refresh.timer

# Verify timer is active
sudo systemctl status feedfocus-daily-refresh.timer
systemctl list-timers | grep feedfocus
```

#### 2.2 Test Daily Refresh Manually

```bash
cd /home/ubuntu/feedfocus

# Dry run to see what would be queued
/home/ubuntu/feedfocus/.venv/bin/python automation/daily_refresh_queue.py --dry-run

# Run actual refresh (optional, for testing)
/home/ubuntu/feedfocus/.venv/bin/python automation/daily_refresh_queue.py
```

#### 2.3 Verify Daily Refresh Logs

```bash
# For cron
tail -f /home/ubuntu/feedfocus/logs/daily_refresh.log

# For systemd
sudo journalctl -u feedfocus-daily-refresh.service -f
```

---

### Step 3: Mobile App Deployment

#### 3.1 Update Mobile Environment Variables

Ensure `.env` files have correct API URLs:

```bash
# feedfocus-mobile/.env
API_URL=https://api.feed-focus.com
SUPABASE_URL=your_supabase_url
SUPABASE_ANON_KEY=your_supabase_key
```

#### 3.2 Build and Deploy

**For iOS:**
```bash
cd feedfocus-mobile
npx expo build:ios
# Follow Expo instructions for TestFlight/App Store
```

**For Android:**
```bash
cd feedfocus-mobile
npx expo build:android
# Follow Expo instructions for Play Store
```

**For Development:**
```bash
# Test with Expo Go
cd feedfocus-mobile
npx expo start
```

---

## ✅ Verification Steps

### Backend Verification

#### 1. Check Service Health
```bash
# API health endpoint
curl https://api.feed-focus.com/api/queue/health

# Expected: 200 OK with queue metrics
```

#### 2. Test Topic Follow Flow
```bash
# Follow a new topic
curl -X POST https://api.feed-focus.com/api/topics/follow \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{"topic": "test deployment topic"}'

# Expected: Status "extracting" or "ready"
```

#### 3. Check Topic Status
```bash
curl https://api.feed-focus.com/api/topics/test%20deployment%20topic/status \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# Expected: Topic status with extraction_job details
```

#### 4. Monitor Database
```bash
# Connect to database
sqlite3 /home/ubuntu/feedfocus/insights.db

# Check extraction jobs
SELECT topic, status, priority, retry_count, created_at
FROM extraction_jobs
ORDER BY created_at DESC
LIMIT 10;

# Check for WAL mode
PRAGMA journal_mode;
# Expected: wal
```

### Mobile App Verification

#### 1. Search Flow
- Open app → Tap search icon
- Search for a topic
- Verify status displays correctly

#### 2. Extraction Progress
- Follow a new topic
- Verify navigation to progress screen
- Verify polling updates status
- Verify completion navigation

#### 3. Error Handling
- Search for invalid topic ("f", "test")
- Verify helpful error messages
- Verify no crash

---

## 📊 Monitoring

### Key Metrics to Monitor

#### 1. Queue Health
```bash
# Check every 5 minutes
curl https://api.feed-focus.com/api/queue/health
```

Monitor:
- `workers_active` = 2
- `queue_size` < 10 (under normal load)
- `jobs_processing` ≤ 2
- `avg_completion_time_minutes` < 15

#### 2. Daily Refresh Logs
```bash
# Cron logs
tail -f /home/ubuntu/feedfocus/logs/daily_refresh.log

# Systemd logs
sudo journalctl -u feedfocus-daily-refresh.service --since today
```

Look for:
- Successfully queued topics count
- Failed topic count
- Total time taken

#### 3. Backend Logs
```bash
sudo journalctl -u feedfocus -f
```

Watch for:
- `ExtractionWorker-X processing job` messages
- `Job completed: N insights from M sources` messages
- Any ERROR level messages

#### 4. Database Size
```bash
# Check database file sizes
ls -lh /home/ubuntu/feedfocus/insights.db*

# Expected files:
# insights.db       - Main database
# insights.db-wal   - Write-ahead log
# insights.db-shm   - Shared memory file
```

---

## 🚨 Troubleshooting

### Backend Won't Start

**Issue:** Service fails to start

**Solution:**
```bash
# Check logs
sudo journalctl -u feedfocus -n 100 --no-pager

# Common issues:
# 1. Database locked
sudo systemctl stop feedfocus
rm -f /home/ubuntu/feedfocus/insights.db-wal
rm -f /home/ubuntu/feedfocus/insights.db-shm
sudo systemctl start feedfocus

# 2. Port already in use
sudo lsof -i :8000
# Kill conflicting process

# 3. Environment variables missing
cat /home/ubuntu/feedfocus/.env
# Verify all required vars present
```

### Extraction Jobs Stuck

**Issue:** Jobs stay in "processing" or "queued" forever

**Solution:**
```bash
# Check queue health
curl https://api.feed-focus.com/api/queue/health

# If workers not active, restart backend
sudo systemctl restart feedfocus

# If jobs truly stuck (>20 minutes), they'll be recovered on restart
# Check for stale job recovery logs
sudo journalctl -u feedfocus | grep "Recovered.*stale jobs"
```

### Database Lock Errors

**Issue:** "database is locked" errors in logs

**Solution:**
```bash
# Verify WAL mode is enabled
sqlite3 /home/ubuntu/feedfocus/insights.db "PRAGMA journal_mode;"
# Should return: wal

# If not WAL, restart backend (it will set WAL mode)
sudo systemctl restart feedfocus

# Check if other processes are holding locks
fuser /home/ubuntu/feedfocus/insights.db
```

### Daily Refresh Not Running

**Issue:** Daily refresh didn't run at 2 AM

**Solution:**

**For Cron:**
```bash
# Check cron is running
sudo systemctl status cron

# Check cron logs
grep CRON /var/log/syslog | grep daily_refresh

# Verify cron entry exists
crontab -l | grep daily_refresh

# Test manually
/home/ubuntu/feedfocus/.venv/bin/python \
  /home/ubuntu/feedfocus/automation/daily_refresh_queue.py --dry-run
```

**For Systemd:**
```bash
# Check timer status
sudo systemctl status feedfocus-daily-refresh.timer

# Check when next run is scheduled
systemctl list-timers | grep feedfocus

# Check service logs
sudo journalctl -u feedfocus-daily-refresh.service --since "today"

# Manually trigger
sudo systemctl start feedfocus-daily-refresh.service
```

### Mobile App Issues

**Issue:** Progress screen not updating

**Solution:**
- Check API_URL in mobile .env
- Verify JWT token is valid
- Check backend logs for 401/403 errors
- Test API endpoints directly with curl

**Issue:** "Extraction queued" but nothing happens

**Solution:**
- Check queue health endpoint
- Verify backend extraction queue is running
- Check backend logs for worker activity

---

## 🔄 Rollback Procedure

If issues arise, rollback to previous version:

### 1. Rollback Backend Code
```bash
ssh ubuntu@feed-focus.com
cd /home/ubuntu/feedfocus

# Find previous working commit
git log --oneline -10

# Rollback to previous commit
git checkout <previous-commit-hash>

# Restart service
sudo systemctl restart feedfocus
```

### 2. Restore Database (if needed)
```bash
# List backups
ls -lh /home/ubuntu/feedfocus/insights.db.backup-*

# Stop backend
sudo systemctl stop feedfocus

# Restore backup
cp insights.db.backup-YYYYMMDD-HHMMSS insights.db

# Remove WAL files
rm -f insights.db-wal insights.db-shm

# Start backend
sudo systemctl start feedfocus
```

### 3. Disable Daily Refresh (if needed)
```bash
# For cron
crontab -e
# Comment out the daily_refresh line

# For systemd
sudo systemctl stop feedfocus-daily-refresh.timer
sudo systemctl disable feedfocus-daily-refresh.timer
```

---

## 📝 Post-Deployment Tasks

### Day 1 (Deployment Day)
- [ ] Monitor backend logs for first 2 hours
- [ ] Check queue health every 30 minutes
- [ ] Verify 2-3 user-triggered extractions complete successfully
- [ ] Test mobile app on real devices

### Day 2 (After Daily Refresh)
- [ ] Check daily refresh ran at 2 AM
- [ ] Review daily refresh logs
- [ ] Verify queued topics completed
- [ ] Check for any failed extractions

### Week 1
- [ ] Monitor average completion times
- [ ] Check for recurring errors
- [ ] Verify no database growth issues
- [ ] Review user feedback on extraction flow

### Week 2
- [ ] Optimize if needed (worker count, timeout values)
- [ ] Document any production-specific quirks
- [ ] Update runbooks if needed

---

## 🔐 Security Notes

### API Endpoints
- All extraction endpoints require JWT authentication
- Queue health endpoint can be public for monitoring
- Retry endpoint requires user owns the topic

### Database
- Ensure proper file permissions: `chmod 600 insights.db*`
- Regular backups scheduled
- Monitor database file size growth

### Daily Refresh
- Runs as system user (user_id='system')
- No sensitive data exposed in logs
- Rate limited to prevent abuse

---

## 📞 Support

### If Issues Persist

1. **Check documentation:**
   - `docs/features/extraction-pipeline-implementation.md`
   - `docs/architecture/database.md`
   - `docs/architecture/api-endpoints.md`

2. **Review test results:**
   - Run `python tests/test_end_to_end.py` locally
   - Compare with production behavior

3. **Gather diagnostics:**
   ```bash
   # Backend logs
   sudo journalctl -u feedfocus --since "1 hour ago" > backend-logs.txt

   # Queue health
   curl https://api.feed-focus.com/api/queue/health > queue-health.json

   # Database stats
   sqlite3 insights.db ".schema extraction_jobs" > db-schema.txt
   sqlite3 insights.db "SELECT COUNT(*), status FROM extraction_jobs GROUP BY status;" > job-counts.txt
   ```

---

## ✅ Success Criteria

Deployment is successful when:

- [x] Backend starts without errors
- [x] WAL mode enabled (log confirms)
- [x] 2 extraction workers active
- [x] Queue health endpoint returns valid metrics
- [x] New topic extraction completes successfully
- [x] Mobile app can search and follow topics
- [x] Progress screen updates in real-time
- [x] Daily refresh scheduled (cron/systemd)
- [x] No database lock errors in logs
- [x] Response times < 1 second

**Congratulations! The extraction pipeline is live! 🎉**
