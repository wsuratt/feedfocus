# FeedFocus Lite - Implementation Plan

## Product Overview

**FeedFocus Lite** is a wedge product for topic validation and lead generation.

### User Flow
1. Visit landing page
2. Enter topic + email
3. Submit
4. Receive insights via email within 2 hours
5. CTA: "Want weekly updates? Reply or click here"

### Value Proposition
- Validate if topics are valuable to users
- Build email list of engaged users
- Low-friction entry point (no signup required)
- Immediate value delivery

---

## Architecture Decision

### ✅ Same Backend + New Frontend
**Rationale:**
- Reuse existing infrastructure (EC2, DB, extraction queue)
- Leverage topic validation + extraction logic
- No additional deployment complexity
- Share insight quality scoring
- Single codebase maintenance

**What Changes:**
- **Frontend**: New lightweight static page (HTML/CSS/JS, no React)
- **Backend**: Add lite-specific endpoints + email service
- **Database**: Add lead tracking table

---

## Phase 1: Database & Email Setup (30 min)

### 1.1 Create Lead Tracking Table

**File:** `db/migrations/005_lite_leads.sql`

```sql
CREATE TABLE lite_leads (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL,
    topic TEXT NOT NULL,
    status TEXT NOT NULL, -- 'pending', 'sent', 'failed'
    submitted_at TEXT NOT NULL,
    sent_at TEXT,
    insights_sent INTEGER DEFAULT 0,
    conversion_source TEXT -- 'immediate', 'queued'
);

CREATE INDEX idx_lite_leads_email ON lite_leads(email);
CREATE INDEX idx_lite_leads_status ON lite_leads(submitted_at);
```

### 1.2 Email Service Integration

**Recommendation:** Use AWS SES
- Already on EC2
- Free tier: 62,000 emails/month
- Reliable delivery
- Built-in analytics

**Environment Variables** (`.env`):
```env
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
FROM_EMAIL=insights@feedfocus.app
```

**Dependencies** (`requirements-backend.txt`):
```
boto3>=1.28.0  # AWS SDK for SES
```

---

## Phase 2: Backend Endpoints (45 min)

### 2.1 Submission Endpoint

**Endpoint:** `POST /api/lite/submit`

**Request:**
```json
{
  "email": "user@example.com",
  "topic": "AI agents"
}
```

**Response:**
```json
{
  "status": "immediate" | "queued",
  "message": "Check your email!" | "You'll get insights within 2 hours",
  "topic": "AI agents"
}
```

**Logic Flow:**
1. Validate email format
2. Validate topic (use existing validator)
3. Check if topic has ≥5 quality insights (quality_score ≥ 7)
4. **If YES**: Send email immediately, return "immediate"
5. **If NO**: Queue extraction, return "queued"
6. Record submission in `lite_leads` table

### 2.2 Email Sending Service

**File:** `backend/services/email_service.py`

**Features:**
- Format insights as clean HTML email
- Send via AWS SES
- Track delivery status
- Handle errors gracefully

**Email Template Structure:**
- **Subject:** "Your {topic} insights are ready"
- **Content:**
  - 5-10 best insights (quality_score DESC)
  - Each insight: text + source link
  - Clean, readable formatting
- **CTA:** "Want weekly updates? Reply YES or [click here]"

---

## Phase 3: Lightweight Frontend (30 min)

### 3.1 Static HTML Page

**File:** `feedfocus/frontend/lite.html` (standalone, no React)

**Features:**
- Clean, modern design (Tailwind CDN for styling)
- Topic input with autocomplete (popular topics)
- Email validation (client-side)
- Loading state during submission
- Success/queued message display
- No navigation, no auth, single purpose
- Mobile responsive
- Fast load time (<1s)

**Served from Backend:**
```python
# backend/main.py
@app.get("/lite")
async def serve_lite_page():
    return FileResponse("frontend/lite.html")
```

### 3.2 Form Submission

**Implementation:** Vanilla JavaScript (no framework)

```javascript
// Example structure
async function handleSubmit(email, topic) {
  const response = await fetch('/api/lite/submit', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, topic })
  });

  const data = await response.json();
  // Show success message based on data.status
}
```

---

## Phase 4: Extraction Queue Enhancement (20 min)

### 4.1 Add Email Callback

**Modify:** `backend/extraction_queue.py`

**Changes:**
- Add optional callback parameter to `queue_extraction()`
- Call callback when extraction completes
- Pass topic and insights to callback

```python
def queue_extraction(topic, on_complete=None):
    # Existing extraction logic
    # When done:
    if on_complete:
        on_complete(topic, insights)
```

### 4.2 Lite Extraction Handler

**Function:** `handle_lite_extraction_complete(topic)`

**Logic:**
1. Query `lite_leads` for pending leads with this topic
2. Get best insights for topic
3. Send email to all waiting leads
4. Update `lite_leads` status to 'sent'
5. Record insights_sent count

---

## Phase 5: Analytics & Monitoring (15 min)

### 5.1 Track Conversions

**Add Column:**
```sql
ALTER TABLE lite_leads ADD COLUMN
    conversion_clicked BOOLEAN DEFAULT FALSE;
```

**Metrics to Track:**
- Total submissions
- Immediate vs queued send ratio
- Email open rate (via SES)
- Click-through to main app
- Email replies (manual check)
- Popular topics requested
- Average response time for queued requests

### 5.2 Admin Dashboard (Optional)

**Endpoint:** `GET /api/admin/lite-stats`

**Response:**
```json
{
  "total_submissions": 150,
  "immediate_sends": 100,
  "queued_sends": 50,
  "pending_extractions": 5,
  "avg_response_time": "45 minutes",
  "popular_topics": [
    {"topic": "AI agents", "count": 25},
    {"topic": "productivity", "count": 18}
  ]
}
```

---

## Phase 6: Deployment (20 min)

### 6.1 Same EC2 Instance

**Steps:**
1. Deploy `lite.html` to frontend folder
2. Backend updates via `git pull`
3. Run migration: `python db/apply_migration.py 005_lite_leads.sql`
4. Configure AWS SES credentials in `.env`
5. Install `boto3`: `pip install boto3`
6. Restart backend: `sudo systemctl restart feedfocus`

### 6.2 Nginx Configuration

**Add route for `/lite`:**
```nginx
location /lite {
    proxy_pass http://127.0.0.1:8000/lite;
}
```

### 6.3 DNS Options

**Option 1:** Subdomain
- `try.feedfocus.com` → `/lite`
- Clean, memorable URL

**Option 2:** Path
- `feedfocus.com/lite`
- Simpler setup

---

## File Structure

```
feedfocus/
├── backend/
│   ├── main.py                    # Add /api/lite/submit endpoint
│   ├── services/
│   │   └── email_service.py       # NEW - AWS SES integration
│   └── extraction_queue.py        # Add email callback support
├── db/
│   └── migrations/
│       └── 005_lite_leads.sql     # NEW - Lead tracking table
├── frontend/
│   └── lite.html                  # NEW - Standalone landing page
├── .env                           # Add AWS_* environment variables
└── requirements-backend.txt       # Add boto3
```

---

## Implementation Timeline

| Phase | Task | Time | Status |
|-------|------|------|--------|
| 1 | Database + Email Setup | 30 min | Pending |
| 2 | Backend Endpoints | 45 min | Pending |
| 3 | Lightweight Frontend | 30 min | Pending |
| 4 | Queue Enhancement | 20 min | Pending |
| 5 | Analytics | 15 min | Pending |
| 6 | Deployment | 20 min | Pending |
| **Total** | | **~2.5 hours** | |

---

## Success Metrics

### Week 1 Targets
- 50+ email submissions
- 80%+ immediate send rate (validates topic coverage)
- 10% reply/click rate

### Week 4 Targets
- Identify high-demand topics
- Measure conversion to main app
- Analyze email engagement patterns
- Build email list of 200+ engaged users

---

## Future Enhancements

### v1.1 Features
1. **Weekly Digest Option**
   - Store email subscriptions
   - Cron job for weekly sends
   - Unsubscribe link

2. **Social Proof**
   - "Join 500+ people getting AI insights"
   - Display submission count

3. **Topic Suggestions**
   - "People also liked: X, Y, Z"
   - Based on similar topic searches

4. **Referral Tracking**
   - UTM parameters
   - Track acquisition channels

5. **A/B Testing**
   - Different CTAs
   - Email format variations
   - Subject line testing

### v2.0 Features
- Personalized insight selection based on industry
- Multi-topic subscriptions
- Insight voting/feedback
- Integration with main app (automatic account creation)

---

## Risk Mitigation

### Email Deliverability
- Use AWS SES (high reputation)
- Implement SPF, DKIM, DMARC
- Start with warm-up period (slow ramp)
- Monitor bounce/complaint rates

### Spam Concerns
- Require double opt-in (optional)
- Clear unsubscribe link
- Only send requested content
- Rate limiting on submissions

### Extraction Overload
- Queue depth monitoring
- Prioritize popular topics
- Batch similar topic requests
- Set max pending extractions

### Database Growth
- Archive old leads after 90 days
- Index optimization
- Regular cleanup of failed/bounced

---

## Cost Analysis

### AWS SES
- **Free Tier:** 62,000 emails/month
- **Paid:** $0.10 per 1,000 emails
- **Estimated Month 1:** Free tier sufficient

### EC2
- **No additional cost** (same instance)
- Current instance handles load

### Storage
- **Lead table:** ~1KB per lead
- **10,000 leads:** ~10MB
- Negligible impact

**Total Additional Cost:** $0-5/month

---

## Next Steps

1. **Validate AWS SES Setup**
   - Verify domain ownership
   - Move out of sandbox (production)
   - Test email sending

2. **Start Implementation**
   - Phase 1: Database + Email (30 min)
   - Test email delivery
   - Continue to Phase 2

3. **Deploy to Staging**
   - Test full flow
   - Verify extraction queue integration
   - Load testing

4. **Launch**
   - Deploy to production
   - Monitor metrics
   - Iterate based on feedback
