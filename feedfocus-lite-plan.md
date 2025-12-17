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

## Phase 3: Lite Frontend App (30 min)

### 3.1 Create Separate Vite App

**Structure:**
```
feedfocus/
├── frontend/          # Main app (keep for later)
└── frontend-lite/     # NEW - Lite landing page
    ├── src/
    │   ├── App.tsx
    │   ├── main.tsx
    │   └── index.css
    ├── index.html
    ├── package.json
    ├── vite.config.ts
    ├── tailwind.config.js
    ├── tsconfig.json
    └── .env
```

**Tech Stack:** React 18 + TypeScript + Vite + Tailwind (same as main app)

**Features:**
- Single page, no routing
- Topic input with autocomplete
- Email validation
- Loading states
- Success/queued messages
- Mobile responsive
- Fast load (<1s)

### 3.2 Setup Frontend-Lite

**Create package.json:**
```json
{
  "name": "feedfocus-lite",
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "lucide-react": "^0.263.1",
    "react": "^18.2.0",
    "react-dom": "^18.2.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.15",
    "@types/react-dom": "^18.2.7",
    "@vitejs/plugin-react": "^4.0.3",
    "autoprefixer": "^10.4.22",
    "postcss": "^8.5.6",
    "tailwindcss": "^3.4.18",
    "typescript": "^5.0.2",
    "vite": "^4.4.5"
  }
}
```

**Create App.tsx:**
```typescript
import { useState } from 'react';
import { Mail, Sparkles, CheckCircle, Clock } from 'lucide-react';

export default function App() {
  const [formData, setFormData] = useState({ email: '', topic: '' });
  const [status, setStatus] = useState<'idle' | 'loading' | 'immediate' | 'queued'>('idle');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setStatus('loading');

    try {
      const response = await fetch('/api/lite/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData)
      });

      const data = await response.json();
      setStatus(data.status);
    } catch (error) {
      console.error('Submission failed:', error);
      setStatus('idle');
    }
  };

  if (status === 'immediate' || status === 'queued') {
    return <SuccessScreen status={status} email={formData.email} />;
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-white rounded-2xl shadow-xl p-8">
        <div className="text-center mb-8">
          <Sparkles className="w-12 h-12 text-indigo-600 mx-auto mb-4" />
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            Get Curated Insights
          </h1>
          <p className="text-gray-600">
            Enter any topic, get the best insights in your inbox
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Topic
            </label>
            <input
              type="text"
              value={formData.topic}
              onChange={(e) => setFormData({...formData, topic: e.target.value})}
              placeholder="e.g. AI agents, productivity, startups"
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Email
            </label>
            <input
              type="email"
              value={formData.email}
              onChange={(e) => setFormData({...formData, email: e.target.value})}
              placeholder="you@example.com"
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              required
            />
          </div>

          <button
            type="submit"
            disabled={status === 'loading'}
            className="w-full bg-indigo-600 text-white py-3 rounded-lg hover:bg-indigo-700 disabled:opacity-50 font-medium"
          >
            {status === 'loading' ? 'Submitting...' : 'Get Insights'}
          </button>
        </form>
      </div>
    </div>
  );
}

function SuccessScreen({ status, email }: { status: 'immediate' | 'queued', email: string }) {
  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-white rounded-2xl shadow-xl p-8 text-center">
        {status === 'immediate' ? (
          <>
            <CheckCircle className="w-16 h-16 text-green-500 mx-auto mb-4" />
            <h2 className="text-2xl font-bold text-gray-900 mb-2">Check Your Email!</h2>
            <p className="text-gray-600 mb-4">
              We just sent your insights to <strong>{email}</strong>
            </p>
          </>
        ) : (
          <>
            <Clock className="w-16 h-16 text-indigo-500 mx-auto mb-4" />
            <h2 className="text-2xl font-bold text-gray-900 mb-2">We're On It!</h2>
            <p className="text-gray-600 mb-4">
              You'll get insights within 2 hours at <strong>{email}</strong>
            </p>
          </>
        )}
        <p className="text-sm text-gray-500">
          Want weekly updates? Just reply to the email.
        </p>
      </div>
    </div>
  );
}
```

### 3.3 Configuration Files

**vite.config.ts:**
```typescript
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000'
    }
  }
});
```

**tailwind.config.js, tsconfig.json, etc.** - Copy from main frontend

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

### 6.1 Modify Docker Compose

**Update `docker-compose.yml` to build frontend-lite instead:**

```yaml
# Comment out main frontend (for later)
# frontend:
#   build:
#     context: ./frontend
#   volumes:
#     - ./frontend/dist:/app/dist

# Add frontend-lite
frontend-lite:
  build:
    context: ./frontend-lite
    dockerfile: ../frontend/Dockerfile  # Reuse same Dockerfile
  volumes:
    - ./frontend-lite/dist:/app/dist
  environment:
    - VITE_API_URL=https://api.feed-focus.com
```

**Or simpler - just change the context in existing service:**
```yaml
frontend:
  build:
    context: ./frontend-lite  # Changed from ./frontend
  volumes:
    - ./frontend-lite/dist:/app/dist
  environment:
    - VITE_API_URL=https://api.feed-focus.com
```

### 6.2 Update GitHub Actions

**Modify `.github/workflows/deploy-aws-ec2.yml`:**

```yaml
# Change frontend build section
- name: Build frontend on host
  script: |
    # ... existing setup ...

    # Build frontend-lite instead
    cd frontend-lite  # Changed from frontend

    # Create .env for build
    echo "VITE_API_URL=https://api.feed-focus.com" > .env

    # Remove old dist
    sudo rm -rf dist

    # Build
    npm ci
    npm run build

    # Fix ownership
    sudo chown -R ubuntu:ubuntu dist
    cd ..

    # Restart containers
    sudo docker-compose restart
```

### 6.3 Deployment Steps

**On Local:**
```bash
cd feedfocus

# Create frontend-lite
mkdir frontend-lite
cd frontend-lite

# Copy config from main frontend
cp ../frontend/package.json .
cp ../frontend/vite.config.ts .
cp ../frontend/tailwind.config.js .
cp ../frontend/tsconfig.json .
cp ../frontend/postcss.config.js .

# Modify package.json name
# Add src/App.tsx, src/main.tsx, etc.

# Commit and push
git add frontend-lite
git commit -m "feat: add feedfocus lite landing page"
git push origin main
```

**GitHub Actions will automatically:**
1. Pull latest code
2. Build frontend-lite
3. Restart containers

**Then SSH to EC2:**
```bash
ssh your-ec2-instance
cd feedfocus

# Run migration
python3 db/apply_migration.py 005_lite_leads.sql

# Configure AWS SES in .env
nano .env
# Add:
# AWS_REGION=us-east-1
# AWS_ACCESS_KEY_ID=your_key
# AWS_SECRET_ACCESS_KEY=your_secret
# FROM_EMAIL=insights@feedfocus.app

# Restart backend to pick up new env vars
sudo docker-compose restart backend
```

### 6.4 DNS Configuration

**Frontend serves from root:**
- `feedfocus.com` → frontend-lite (landing page)
- `feedfocus.com/api/*` → backend API

**No additional nginx config needed** - existing setup works

### 6.5 Rollback to Main Frontend Later

**When ready to deploy full app:**
```yaml
# In docker-compose.yml
frontend:
  build:
    context: ./frontend  # Change back
  volumes:
    - ./frontend/dist:/app/dist
```

Push and GitHub Actions will rebuild with main frontend.

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
├── frontend/                      # Main app (commented out in docker-compose for now)
│   └── ...
├── frontend-lite/                 # NEW - Lite landing page
│   ├── src/
│   │   ├── App.tsx               # Main component
│   │   ├── main.tsx              # Entry point
│   │   └── index.css             # Global styles
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   └── tsconfig.json
├── .env                           # Add AWS_* environment variables
├── docker-compose.yml             # Modified to build frontend-lite
└── .github/workflows/
    └── deploy-aws-ec2.yml         # Modified to build frontend-lite

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
