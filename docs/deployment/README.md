# Deployment Documentation

## Quick Start

**First time deploying?** Start here: [`DEPLOYMENT-CHECKLIST.md`](./DEPLOYMENT-CHECKLIST.md)

**Need detailed instructions?** See: [`extraction-pipeline-deployment.md`](./extraction-pipeline-deployment.md)

---

## What's in This Folder

### 📋 [DEPLOYMENT-CHECKLIST.md](./DEPLOYMENT-CHECKLIST.md)
**Quick reference checklist** - Print this out and check boxes as you go
- Pre-deployment tests
- Backend deployment steps
- Daily refresh setup
- Verification commands
- Rollback procedure

**Use this when:** You're actively deploying and need a quick reference

---

### 📖 [extraction-pipeline-deployment.md](./extraction-pipeline-deployment.md)
**Comprehensive deployment guide** - All the details you need
- Pre-deployment checklist with explanations
- Step-by-step deployment instructions
- Monitoring and metrics guidance
- Troubleshooting common issues
- Post-deployment tasks

**Use this when:**
- First time deploying extraction pipeline
- Troubleshooting deployment issues
- Understanding monitoring requirements
- Need rollback procedures

---

## Deployment Overview

The extraction pipeline adds:
- **Backend:** Queue-based extraction with 2 worker threads
- **Database:** New `extraction_jobs` table with WAL mode
- **Daily Refresh:** Scheduled job to refresh popular topics
- **Mobile:** Search screen and progress tracking
- **APIs:** 4 new endpoints for queue management

**Deployment time:** ~30-45 minutes
**Downtime:** ~30 seconds (backend restart)
**Monitoring required:** First 24 hours

---

## Quick Deploy (Experienced Deployers)

```bash
# 1. Local tests
python tests/test_end_to_end.py

# 2. Deploy backend
ssh ubuntu@feed-focus.com "cd /home/ubuntu/feedfocus && \
  git pull origin main && \
  sudo systemctl restart feedfocus"

# 3. Setup daily refresh
ssh ubuntu@feed-focus.com "cd /home/ubuntu/feedfocus/automation && \
  bash setup_systemd.sh"

# 4. Verify
curl https://api.feed-focus.com/api/queue/health

# 5. Update mobile app
cd feedfocus-mobile && npx expo build:ios
```

---

## Prerequisites

Before deploying:
- [x] All extraction pipeline code merged to `main`
- [x] Backend has Python 3.8+ with required dependencies
- [x] SQLite database at `/home/ubuntu/feedfocus/insights.db`
- [x] Backend service named `feedfocus` in systemd
- [x] Mobile app has production API URLs in `.env`

---

## Need Help?

1. **Deployment issues?** → Check [Troubleshooting section](./extraction-pipeline-deployment.md#-troubleshooting)
2. **Architecture questions?** → See `docs/features/extraction-pipeline-implementation.md`
3. **API documentation?** → See `docs/architecture/api-endpoints.md`
4. **Database schema?** → See `docs/architecture/database.md`

---

## Post-Deployment

After successful deployment:
- Monitor backend logs for 2 hours
- Wait for first daily refresh (2 AM next day)
- Test mobile app on real devices
- Document any production-specific issues

---

**Last Updated:** December 2024
**Version:** 1.0 (Initial extraction pipeline release)
