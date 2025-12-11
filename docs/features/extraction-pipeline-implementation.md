# Implementation Plan: Search, Extract, and Refresh Pipeline

**Project:** FeedFocus Background Extraction System
**Created:** December 9, 2024
**Status:** Ready to Start

---

## 📊 Overview

Implement a complete background extraction system that allows users to add topics, queue extraction jobs, and automatically refresh content daily.

**Timeline:** 3 days
**Total Tasks:** 27 tasks
**Complexity:** Medium-High

---

## 🎯 Success Criteria

- ✅ Users can add topics and see "extracting" status immediately
- ✅ Extractions run in background without blocking user
- ✅ Failed extractions auto-retry (up to 3 times)
- ✅ Users can manually retry failed extractions
- ✅ Daily refresh updates top 20 active topics
- ✅ 2 extractions can run in parallel
- ✅ No duplicate extractions for same topic
- ✅ Progress tracking visible to users

---

## 📅 Day 1: Backend Core (8 tasks)

### Task 1.1: Create Database Migration
**Component:** Database Schema
**Estimated Time:** 1 hour
**Priority:** Critical

**Description:**
Create migration script to add `extraction_jobs` table.

**Implementation:**
1. Create `db/migrations/002_extraction_jobs.sql`
2. Add table creation SQL:
```sql
CREATE TABLE IF NOT EXISTS extraction_jobs (
    id TEXT PRIMARY KEY,
    topic TEXT NOT NULL,
    user_id TEXT NOT NULL,
    priority INTEGER DEFAULT 5,
    status TEXT NOT NULL CHECK(status IN ('queued', 'processing', 'complete', 'failed')),
    insight_count INTEGER DEFAULT 0,
    error TEXT,
    retry_count INTEGER DEFAULT 0,
    last_retry_at TEXT,
    estimated_completion_at TEXT,
    sources_processed INTEGER DEFAULT 0,
    extraction_duration_seconds REAL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX idx_extraction_jobs_topic ON extraction_jobs(topic);
CREATE INDEX idx_extraction_jobs_status ON extraction_jobs(status);
CREATE INDEX idx_extraction_jobs_user_id ON extraction_jobs(user_id);
CREATE INDEX idx_extraction_jobs_priority ON extraction_jobs(priority DESC);
```
3. Create Python migration script to run SQL
4. Test migration on local database

**Acceptance Criteria:**
- [ ] Table created successfully
- [ ] All indexes created
- [ ] Migration script is idempotent (can run multiple times)
- [ ] No data loss from existing tables

**Files:**
- `feedfocus/db/migrations/002_extraction_jobs.sql`
- `feedfocus/db/migrations/run_migration.py`

---

### Task 1.2: Build Topic Validation Module (with SLM)
**Component:** Topic Validation
**Estimated Time:** 2 hours
**Priority:** High

**Description:**
Create hybrid validation system using basic rules + local SLM for semantic understanding.

**Why SLM over pure rules:**
- Handles edge cases (new acronyms, emerging topics) without whitelist updates
- Semantic understanding prevents false rejections/accepts
- Local inference = fast (20-50ms), free, no API dependency
- Better UX than strict rules

**Implementation:**
1. Create `backend/topic_validation.py`
2. Install lightweight SLM:
   - Use Llama 3.2 1B Instruct (~150MB) or Phi-3 Mini
   - Load model at startup (one-time 1-2 second cost)
3. Implement **two-tier validation**:

**Tier 1: Fast rule-based checks (< 1ms)**
```python
def basic_validation(topic: str) -> tuple[bool, str, bool]:
    """
    Quick checks that catch obvious bad input.
    Returns: (is_valid, error_message, needs_slm_check)
    """
    # Length check
    if len(topic) < 2:
        return False, "Topic too short (min 2 characters)", False
    if len(topic) > 50:
        return False, "Topic too long (max 50 characters)", False

    # Character validation
    if not re.match(r'^[a-zA-Z0-9\s\-\'&]+$', topic):
        return False, "Only letters, numbers, spaces, hyphens allowed", False

    # Obvious banned words (no SLM needed)
    banned = ['test', 'asdf', 'qwerty', 'xxx', 'fuck', 'shit']
    if topic.lower() in banned:
        return False, "Invalid topic name", False

    # Passes basic checks, needs semantic validation
    return True, "", True
```

**Tier 2: SLM semantic validation (20-50ms)**
```python
def validate_with_slm(topic: str) -> tuple[bool, str, str]:
    """
    Use local SLM to check if topic is meaningful.
    Returns: (is_valid, error_message, suggestion)
    """
    prompt = f"""Is "{topic}" a valid topic for a content feed?

Valid examples: AI agents, startup fundraising, DeFi, Web3, Y Combinator
Invalid examples: asdf jkl, stuff and things, random gibberish

Rules:
- Accept real topics, even emerging/niche ones
- Accept standard acronyms (AI, ML, SaaS, B2B, etc.)
- Reject gibberish, test words, overly vague terms
- Reject single letters unless standard acronym

Respond with:
VALID or INVALID
Reason: <brief explanation>
Suggestion: <better topic if invalid, or empty>"""

    response = slm_pipeline(prompt, max_new_tokens=50)

    # Parse response
    valid = "VALID" in response and "INVALID" not in response
    reason = extract_between(response, "Reason:", "Suggestion:")
    suggestion = extract_after(response, "Suggestion:")

    return valid, reason, suggestion
```

4. Main validation function:
```python
async def validate_topic(topic: str) -> tuple[bool, str, str]:
    """
    Main validation entry point.
    Returns: (is_valid, error_message, suggestion)
    """
    # Tier 1: Fast checks
    valid, error, needs_slm = basic_validation(topic)
    if not needs_slm:
        return valid, error, ""

    # Tier 2: SLM semantic check
    return validate_with_slm(topic)
```

5. Setup SLM at application startup:
```python
# In main.py startup
from transformers import pipeline

@app.on_event("startup")
async def startup():
    global slm_pipeline
    slm_pipeline = pipeline(
        "text-generation",
        model="meta-llama/Llama-3.2-1B-Instruct",
        device="cpu",  # or "cuda" if GPU available
        max_length=100
    )
    logger.info("Topic validation SLM loaded")
```

**Acceptance Criteria:**
- [ ] SLM model loads successfully at startup (< 3 seconds)
- [ ] "ML" and "AI" are accepted (valid acronyms)
- [ ] "f" is rejected (too short)
- [ ] "test" and "asdf" are rejected (tier 1 catches these, no SLM call)
- [ ] "stuff about things" is rejected by SLM (vague)
- [ ] "startup fundraising" is accepted
- [ ] "Web3" and "DeFi" are accepted (emerging topics)
- [ ] "Y Combinator" is accepted (real entity with space)
- [ ] Validation completes in < 100ms (tier 1: 1ms, tier 2: 50ms)
- [ ] Helpful suggestions for invalid topics
- [ ] Graceful fallback if SLM fails (use strict rules)

**Files:**
- `feedfocus/backend/topic_validation.py`
- `feedfocus/backend/main.py` (add SLM startup)
- `feedfocus/requirements-backend.txt` (add transformers, torch)

**Test Cases:**
```python
# Tier 1 rejections (fast, no SLM call)
assert validate_topic("f") == (False, "Topic too short (min 2 characters)", "")
assert validate_topic("test") == (False, "Invalid topic name", "")
assert validate_topic("x" * 51) == (False, "Topic too long (max 50 characters)", "")

# Tier 2 SLM validation (semantic)
assert validate_topic("ML")[0] == True
assert validate_topic("AI agents")[0] == True
assert validate_topic("startup fundraising")[0] == True
assert validate_topic("Web3")[0] == True
assert validate_topic("DeFi")[0] == True
assert validate_topic("Y Combinator")[0] == True
assert validate_topic("stuff about things")[0] == False
assert validate_topic("asdfgh jklmn")[0] == False

# Suggestions
valid, error, suggestion = validate_topic("how do I learn programming")
assert valid == False
assert suggestion != ""  # Should suggest "programming tutorials" or similar
```

**Dependencies:**
```
transformers>=4.40.0
torch>=2.0.0
sentencepiece>=0.1.99  # For Llama tokenizer
```

**Performance:**
- Model loading: 1-2 seconds (startup only)
- Tier 1 validation: < 1ms (80% of rejections)
- Tier 2 validation: 20-50ms on CPU, <10ms on GPU
- Memory: ~500MB RAM for model
- Cost: $0 (local inference)

---

### Task 1.3: Build Semantic Similarity Function
**Component:** Semantic Search
**Estimated Time:** 2 hours
**Priority:** High

**Description:**
Create function to find similar existing topics using ChromaDB.

**Implementation:**
1. Create `backend/semantic_search.py`
2. Implement `find_similar_topic(topic: str, threshold: float = 0.85) -> dict`:
   - Query ChromaDB for similar topics
   - Return top 3 similar topics with scores
   - Categorize by similarity:
     - > 0.85: Very similar (reuse existing)
     - > 0.65: Related (show existing, queue new)
     - < 0.65: New topic (queue extraction)
3. Return format:
```python
{
    "action": "reuse" | "related" | "new",
    "existing_topic": str or None,
    "similarity_score": float,
    "similar_topics": [{"topic": str, "score": float}]
}
```

**Acceptance Criteria:**
- [ ] "AI agents" vs "artificial intelligence agents" returns "reuse" (>0.85)
- [ ] "startup fundraising" vs "venture capital" returns "related" (>0.65)
- [ ] "AI agents" vs "college football" returns "new" (<0.65)
- [ ] Returns top 3 similar topics
- [ ] Handles ChromaDB not having any collections gracefully

**Files:**
- `feedfocus/backend/semantic_search.py`

---

### Task 1.4: Build ExtractionQueue Class (Part 1 - Core)
**Component:** Extraction Queue
**Estimated Time:** 2 hours
**Priority:** Critical

**Description:**
Create the core ExtractionQueue class with worker threads.

**Implementation:**
1. Create `backend/extraction_queue.py`
2. Implement `ExtractionQueue` class:
   - Initialize with `num_workers` parameter
   - Create `queue.Queue()` for jobs
   - Spawn worker threads (daemon=True)
   - Each worker runs `_worker_loop()`
3. Implement `add_job(topic, user_id, priority)`:
   - Check if job already queued/processing
   - Insert into `extraction_jobs` table
   - Add to queue with priority
4. Implement `get_job_status(topic)`:
   - Query `extraction_jobs` table
   - Return status dict
5. Implement `stop()`:
   - Set shutdown flag
   - Wait for workers to finish

**Acceptance Criteria:**
- [ ] Can initialize with 2 workers
- [ ] Workers are daemon threads
- [ ] Can add job to queue
- [ ] Duplicate jobs are rejected
- [ ] Can retrieve job status
- [ ] Graceful shutdown works

**Files:**
- `feedfocus/backend/extraction_queue.py`

**Mock Test:**
```python
queue = ExtractionQueue(num_workers=2)
queue.add_job("test topic", "user123", priority=10)
status = queue.get_job_status("test topic")
assert status["status"] == "queued"
queue.stop()
```

---

### Task 1.5: Build ExtractionQueue Class (Part 2 - Worker Logic)
**Component:** Extraction Queue
**Estimated Time:** 3 hours
**Priority:** Critical
**Depends On:** Task 1.4

**Description:**
Implement the worker loop with timeout protection and error handling.

**Implementation:**
1. Implement `_worker_loop()`:
   - Get job from queue
   - Update status to 'processing'
   - Set 15-minute timeout using `threading.Timer`
   - Call extraction function
   - Handle success, timeout, and failure cases
2. Implement auto-retry logic:
   - Check error type (transient vs permanent)
   - Auto-retry if transient and retry_count < 3
   - Update retry_count and last_retry_at
3. Implement progress tracking:
   - Update sources_processed periodically
   - Update estimated_completion_at
4. Use thread-local database connections

**Acceptance Criteria:**
- [ ] Worker processes jobs from queue
- [ ] Status updates to 'processing' when job starts
- [ ] Timeout after 15 minutes
- [ ] Success updates status to 'complete'
- [ ] Transient failures auto-retry
- [ ] Non-transient failures don't auto-retry
- [ ] Retry count increments correctly
- [ ] Thread-local DB connections prevent conflicts

**Files:**
- `feedfocus/backend/extraction_queue.py` (continued)

---

### Task 1.6: Enable SQLite WAL Mode & Add Stale Job Recovery
**Component:** Database Configuration
**Estimated Time:** 1 hour
**Priority:** High

**Description:**
Enable Write-Ahead Logging mode for better concurrency and implement stale job recovery for backend restarts.

**Implementation:**
1. Update `backend/main.py` startup event
2. Add WAL mode enablement:
```python
@app.on_event("startup")
async def startup():
    conn = sqlite3.connect('insights.db')
    conn.execute('PRAGMA journal_mode=WAL')
    conn.close()
    # ... rest of startup
```
3. Add stale job recovery method to `ExtractionQueue`:
```python
def recover_stale_jobs(self):
    """Recover jobs stuck in 'processing' state after restart."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Find jobs that were processing > 20 minutes ago (stale)
        cursor.execute("""
            SELECT id, topic, user_id, priority
            FROM extraction_jobs
            WHERE status = 'processing'
            AND updated_at < datetime('now', '-20 minutes')
        """)

        stale_jobs = cursor.fetchall()

        for job in stale_jobs:
            job_id, topic, user_id, priority = job

            # Reset to queued and re-add to queue
            cursor.execute("""
                UPDATE extraction_jobs
                SET status = 'queued',
                    updated_at = ?
                WHERE id = ?
            """, (datetime.now().isoformat(), job_id))

            self.job_queue.put((priority, job_id, topic, user_id))
            logger.info(f"Recovered stale job: {topic}")

        conn.commit()

        if stale_jobs:
            logger.info(f"Recovered {len(stale_jobs)} stale jobs")
```
4. Call `recover_stale_jobs()` in startup event after queue initialization
5. Verify WAL files are created (`.db-wal`, `.db-shm`)

**Acceptance Criteria:**
- [ ] WAL mode enabled on startup
- [ ] Multiple workers can write simultaneously
- [ ] No database locked errors
- [ ] WAL files created in db directory
- [ ] Stale jobs (processing > 20 min) recovered on startup
- [ ] Recovered jobs re-queued with original priority
- [ ] Frontend polling resumes correctly after backend restart

**Files:**
- `feedfocus/backend/main.py`
- `feedfocus/backend/extraction_queue.py`

**Why This Matters:**
- **Client disconnect (app close/reopen):** Already works - database persists state, polling resumes
- **Backend restart:** Without recovery, jobs stuck in "processing" are lost - this fixes it
- **Production resilience:** Ensures no extraction jobs are lost due to server restarts or crashes

---

### Task 1.7: Update Extraction Pipeline for Rate Limiting
**Component:** Extraction Pipeline
**Estimated Time:** 1.5 hours
**Priority:** Medium

**Description:**
Add rate limiting and progress tracking to extraction pipeline.

**Implementation:**
1. Update `automation/extract_insights()` function
2. Add `rate_limit_delay` parameter (default 1.0 seconds)
3. Add `time.sleep(rate_limit_delay)` between API calls
4. Add callback for progress updates:
```python
def extract_insights(
    topic: str,
    num_sources: int = 40,
    min_quality: float = 7.0,
    rate_limit_delay: float = 1.0,
    progress_callback: callable = None
):
    for i, source in enumerate(sources):
        time.sleep(rate_limit_delay)
        # Process source
        if progress_callback and i % 5 == 0:
            progress_callback(i)
```
5. Update extraction_jobs table with sources_processed

**Acceptance Criteria:**
- [ ] 1 second delay between API calls
- [ ] Progress callback called every 5 sources
- [ ] extraction_jobs.sources_processed updates
- [ ] No rate limit errors during parallel extraction

**Files:**
- `feedfocus/automation/extraction_pipeline.py` (or wherever extract_insights lives)

---

### Task 1.8: Test Queue with Mock Extraction
**Component:** Testing
**Estimated Time:** 1 hour
**Priority:** High
**Depends On:** Tasks 1.4, 1.5

**Description:**
Create test script to verify queue works with mock extraction.

**Implementation:**
1. Create `tests/test_extraction_queue.py`
2. Create mock extraction function that sleeps for 5 seconds
3. Test scenarios:
   - Add 1 job, verify completes
   - Add 3 jobs, verify 2 run in parallel
   - Force timeout, verify marked failed
   - Force error, verify auto-retry
4. Verify thread safety with concurrent access

**Acceptance Criteria:**
- [ ] Single job completes successfully
- [ ] 3 jobs: 2 process in parallel, 1 queues
- [ ] Timeout is detected and handled
- [ ] Transient errors trigger retry
- [ ] Database updates are correct
- [ ] No race conditions or deadlocks

**Files:**
- `feedfocus/tests/test_extraction_queue.py`

---

## 📅 Day 2: API Integration (10 tasks)

### Task 2.1: Update POST /api/topics/follow Endpoint
**Component:** API Endpoints
**Estimated Time:** 2 hours
**Priority:** Critical
**Depends On:** Tasks 1.2, 1.3, 1.4

**Description:**
Integrate queue into the follow topic endpoint.

**Implementation:**
1. Update `backend/main.py` endpoint
2. Flow:
   - Validate topic (Task 1.2)
   - Check semantic similarity (Task 1.3)
   - Add user to user_topics table immediately
   - Check if >= 30 insights exist
   - If not, queue extraction
3. Return different responses based on scenario:
```python
# Ready (enough insights)
{"status": "ready", "topic": str, "insight_count": int}

# Extracting (queued)
{"status": "extracting", "topic": str, "message": str, "existing_count": int}

# Invalid
{"status": "invalid", "error": str}

# Reused (similar topic found)
{"status": "ready", "topic": existing_topic, "insight_count": int}
```

**Acceptance Criteria:**
- [ ] Invalid topics rejected with error
- [ ] Similar topics reuse existing
- [ ] User added to user_topics immediately
- [ ] Extraction queued if < 30 insights
- [ ] Returns correct status for each scenario
- [ ] High priority (10) for user-triggered jobs

**Files:**
- `feedfocus/backend/main.py`

---

### Task 2.2: Create GET /api/topics/{topic}/status Endpoint
**Component:** API Endpoints
**Estimated Time:** 1 hour
**Priority:** High

**Description:**
Create endpoint to check topic and extraction status.

**Implementation:**
1. Add new endpoint to `backend/main.py`
2. Query user_topics for is_following
3. Query insights table for count
4. Query extraction_jobs for job status
5. Return comprehensive status:
```python
{
    "topic": str,
    "is_following": bool,
    "insight_count": int,
    "extraction_job": {
        "status": "queued" | "processing" | "complete" | "failed",
        "insight_count": int,
        "error": {"type": str, "message": str, "retry_eligible": bool} | None,
        "sources_processed": int,
        "estimated_completion_at": str | None,
        "retry_count": int,
        "created_at": str,
        "updated_at": str
    } | None
}
```

**Acceptance Criteria:**
- [ ] Returns correct following status
- [ ] Returns correct insight count
- [ ] Returns extraction job if exists
- [ ] Returns null if no extraction job
- [ ] Works for authenticated user

**Files:**
- `feedfocus/backend/main.py`

---

### Task 2.3: Create POST /api/topics/{topic}/retry Endpoint
**Component:** API Endpoints
**Estimated Time:** 1 hour
**Priority:** Medium

**Description:**
Create endpoint for manual retry of failed extractions.

**Implementation:**
1. Add new endpoint to `backend/main.py`
2. Check for failed job in extraction_jobs
3. Verify retry_count < 3
4. Increment retry_count, update last_retry_at
5. Re-queue with priority=10
6. Return status

**Acceptance Criteria:**
- [ ] Finds failed job correctly
- [ ] Rejects if retry_count >= 3
- [ ] Increments retry_count
- [ ] Re-queues successfully
- [ ] Returns attempt number

**Files:**
- `feedfocus/backend/main.py`

**Response:**
```python
# Success
{"status": "retrying", "attempt": 2, "message": "Extraction requeued"}

# Max retries
{"status": "max_retries", "error": "Max retries reached (3)"}

# No failed job
{"status": "not_found", "error": "No failed extraction found"}
```

---

### Task 2.4: Create GET /api/queue/health Endpoint
**Component:** API Endpoints
**Estimated Time:** 1 hour
**Priority:** Low

**Description:**
Create monitoring endpoint for queue health.

**Implementation:**
1. Add new endpoint to `backend/main.py`
2. Query extraction_jobs for statistics
3. Get queue size from ExtractionQueue
4. Calculate averages and recent failures
5. Return health metrics

**Acceptance Criteria:**
- [ ] Returns active worker count
- [ ] Returns queue size
- [ ] Returns jobs processing count
- [ ] Returns last 5 failures
- [ ] Returns average completion time
- [ ] Returns jobs completed today

**Files:**
- `feedfocus/backend/main.py`

**Response:**
```python
{
    "workers_active": 2,
    "queue_size": 3,
    "jobs_processing": 2,
    "recent_failures": [
        {"topic": str, "error": str, "retry_count": int}
    ],
    "avg_completion_time": 4.5,  # minutes
    "total_completed_today": 15
}
```

---

### Task 2.5: Add Startup Event Handlers
**Component:** Application Lifecycle
**Estimated Time:** 30 minutes
**Priority:** Critical
**Depends On:** Task 1.6

**Description:**
Initialize queue on startup, clean up on shutdown.

**Implementation:**
1. Update `backend/main.py` startup event:
```python
@app.on_event("startup")
async def startup():
    # Enable WAL mode
    conn = sqlite3.connect('insights.db')
    conn.execute('PRAGMA journal_mode=WAL')
    conn.close()

    # Initialize extraction queue
    global extraction_queue
    extraction_queue = ExtractionQueue(num_workers=2)
    logger.info("Extraction queue started with 2 workers")
```
2. Add shutdown event:
```python
@app.on_event("shutdown")
async def shutdown():
    global extraction_queue
    if extraction_queue:
        extraction_queue.stop()
        logger.info("Extraction queue stopped")
```

**Acceptance Criteria:**
- [ ] Queue initializes on startup
- [ ] Workers start automatically
- [ ] Shutdown waits for jobs to complete
- [ ] Logs startup/shutdown events

**Files:**
- `feedfocus/backend/main.py`

---

### Task 2.6: Test Full Flow - New Topic
**Component:** Integration Testing
**Estimated Time:** 1.5 hours
**Priority:** Critical
**Depends On:** Tasks 2.1, 2.2

**Description:**
Test complete flow for adding a new topic.

**Implementation:**
1. Create integration test script
2. Test flow:
   - POST /api/topics/follow with new topic
   - Verify status='extracting'
   - Poll GET /api/topics/{topic}/status
   - Wait for extraction to complete
   - Verify insights appear in database
   - Verify status='complete'
3. Test with valid topic: "machine learning for robotics"

**Acceptance Criteria:**
- [ ] Topic is accepted and queued
- [ ] Status shows 'extracting' immediately
- [ ] Progress updates (sources_processed increases)
- [ ] Extraction completes successfully
- [ ] Insights appear in insights table
- [ ] Final status is 'complete'
- [ ] User is in user_topics table

**Files:**
- `feedfocus/tests/test_integration_new_topic.py`

---

### Task 2.7: Test Full Flow - Similar Topic
**Component:** Integration Testing
**Estimated Time:** 1 hour
**Priority:** High
**Depends On:** Tasks 2.1, 1.3

**Description:**
Test flow when user adds topic similar to existing one.

**Implementation:**
1. Setup: Create topic "artificial intelligence"
2. Test: Add topic "AI agents" (should be similar)
3. Verify: Returns existing topic
4. Verify: User added to user_topics for existing topic
5. Verify: No new extraction queued

**Acceptance Criteria:**
- [ ] Similar topic detected (>0.85)
- [ ] Returns existing topic name
- [ ] User added to user_topics
- [ ] No extraction queued
- [ ] Insights immediately available

**Files:**
- `feedfocus/tests/test_integration_similar_topic.py`

---

### Task 2.8: Test Retry Flow
**Component:** Integration Testing
**Estimated Time:** 1.5 hours
**Priority:** Medium
**Depends On:** Task 2.3

**Description:**
Test manual retry of failed extractions.

**Implementation:**
1. Force extraction to fail (mock API error)
2. Verify status='failed'
3. Call POST /api/topics/{topic}/retry
4. Verify re-queued
5. Let retry succeed
6. Verify status='complete'
7. Test max retries (fail 3 times, verify 4th retry rejected)

**Acceptance Criteria:**
- [ ] Failed job detected correctly
- [ ] Retry increments retry_count
- [ ] Re-queued job processes
- [ ] Max retries (3) enforced
- [ ] Error messages are helpful

**Files:**
- `feedfocus/tests/test_integration_retry.py`

---

### Task 2.9: Test Concurrent Extractions
**Component:** Integration Testing
**Estimated Time:** 1 hour
**Priority:** High

**Description:**
Test that 2 extractions run in parallel.

**Implementation:**
1. Add 3 topics simultaneously:
   - "quantum computing"
   - "blockchain technology"
   - "renewable energy"
2. Monitor extraction_jobs table
3. Verify 2 have status='processing'
4. Verify 1 has status='queued'
5. Wait for first to complete
6. Verify queued job starts immediately

**Acceptance Criteria:**
- [ ] 2 jobs process simultaneously
- [ ] 1 job waits in queue
- [ ] Queue is processed in priority order
- [ ] No database lock errors
- [ ] All 3 eventually complete

**Files:**
- `feedfocus/tests/test_concurrent_extraction.py`

---

### Task 2.10: Test Error Categorization
**Component:** Integration Testing
**Estimated Time:** 1 hour
**Priority:** Medium

**Description:**
Test that different error types are handled correctly.

**Implementation:**
1. Mock different error scenarios:
   - API rate limit (transient)
   - Network error (transient)
   - No results found (permanent)
   - Invalid content (permanent)
2. Verify auto-retry for transient errors
3. Verify no auto-retry for permanent errors
4. Verify error structure in database

**Acceptance Criteria:**
- [ ] Rate limit errors auto-retry
- [ ] Network errors auto-retry
- [ ] "No results" errors don't auto-retry
- [ ] Error JSON has type, message, retry_eligible
- [ ] Retry count tracked correctly

**Files:**
- `feedfocus/tests/test_error_handling.py`

---

## 📅 Day 3: Mobile + Daily Refresh (9 tasks)

### Task 3.1: Update Mobile API Service
**Component:** Mobile - API Client
**Estimated Time:** 1 hour
**Priority:** Critical

**Description:**
Add new API methods to mobile api.ts.

**Implementation:**
1. Update `feedfocus-mobile/src/services/api.ts`
2. Add methods:
```typescript
async getTopicStatus(topic: string): Promise<TopicStatus> {
  const response = await apiClient.get(`/api/topics/${topic}/status`);
  return response.data;
}

async retryExtraction(topic: string): Promise<RetryResponse> {
  const response = await apiClient.post(`/api/topics/${topic}/retry`);
  return response.data;
}
```
3. Add TypeScript interfaces for responses

**Acceptance Criteria:**
- [ ] Methods added to api.ts
- [ ] TypeScript types defined
- [ ] Error handling included
- [ ] JWT token sent in headers

**Files:**
- `feedfocus-mobile/src/services/api.ts`
- `feedfocus-mobile/src/types.ts`

---

### Task 3.2: Update AddTopicScreen with Queue Support
**Component:** Mobile - UI
**Estimated Time:** 2 hours
**Priority:** Critical
**Depends On:** Task 3.1

**Description:**
Update topic add screen to handle queue status.

**Implementation:**
1. Update `feedfocus-mobile/src/screens/AddTopicScreen.tsx`
2. Modify handleFollowTopic:
```typescript
const handleFollowTopic = async (topic: string) => {
  const response = await api.followTopic(topic);

  if (response.status === 'ready') {
    Toast.show('Following ' + topic);
    navigation.navigate('Feed');
  } else if (response.status === 'extracting') {
    navigation.navigate('ExtractionProgress', {
      topic,
      existingCount: response.existing_count
    });
  } else if (response.status === 'invalid') {
    Alert.alert('Invalid Topic', response.error);
  }
};
```

**Acceptance Criteria:**
- [ ] Shows appropriate message for each status
- [ ] Navigates to feed if ready
- [ ] Navigates to progress screen if extracting
- [ ] Shows error for invalid topics
- [ ] Loading state while API call in progress

**Files:**
- `feedfocus-mobile/src/screens/AddTopicScreen.tsx`

---

### Task 3.3: Create ExtractionProgressScreen
**Component:** Mobile - UI
**Estimated Time:** 3 hours
**Priority:** High

**Description:**
Create new screen to show extraction progress.

**Implementation:**
1. Create `feedfocus-mobile/src/screens/ExtractionProgressScreen.tsx`
2. Display:
   - Topic name
   - Status (queued/processing)
   - Progress bar or sources processed count
   - Estimated completion time
   - "Browse Feed" button to leave screen
   - Related insights if existing_count > 0
3. Implement polling with exponential backoff
4. Show retry button if failed
5. Navigate to feed when complete

**Acceptance Criteria:**
- [ ] Shows topic name
- [ ] Displays current status
- [ ] Shows progress (sources processed)
- [ ] Polls with exponential backoff (5s, 10s, 15s, 30s)
- [ ] Shows retry button if failed
- [ ] Navigates to feed on completion
- [ ] "Browse Feed" button works
- [ ] Shows related insights while waiting

**Files:**
- `feedfocus-mobile/src/screens/ExtractionProgressScreen.tsx`

**UI Components:**
```typescript
<View>
  <Text>{topic}</Text>
  <Text>Status: {status}</Text>
  <ProgressBar progress={sourcesProcessed / 40} />
  <Text>Processing source {sourcesProcessed}/40</Text>
  {estimatedCompletion && <Text>Est. {estimatedCompletion}</Text>}
  <Button onPress={browseAnyway}>Browse Feed</Button>
  {failed && <Button onPress={retry}>Retry</Button>}
</View>
```

---

### Task 3.4: Implement Exponential Backoff Polling
**Component:** Mobile - Logic
**Estimated Time:** 1 hour
**Priority:** Medium
**Depends On:** Task 3.3

**Description:**
Add smart polling that reduces frequency over time.

**Implementation:**
1. In ExtractionProgressScreen, implement:
```typescript
const pollIntervals = [5, 10, 15, 30, 30, 30]; // seconds
const [pollCount, setPollCount] = useState(0);

useEffect(() => {
  const poll = async () => {
    const status = await api.getTopicStatus(topic);
    updateUI(status);

    if (status.extraction_job?.status === 'processing') {
      const interval = pollIntervals[Math.min(pollCount, pollIntervals.length - 1)];
      setPollCount(prev => prev + 1);
      setTimeout(poll, interval * 1000);
    }
  };

  poll();
}, []);
```

**Acceptance Criteria:**
- [ ] First poll after 5 seconds
- [ ] Second poll after 10 seconds
- [ ] Third poll after 15 seconds
- [ ] Subsequent polls every 30 seconds
- [ ] Stops polling when complete or failed
- [ ] Resumes normal interval on retry

**Files:**
- `feedfocus-mobile/src/screens/ExtractionProgressScreen.tsx`

---

### Task 3.5: Add Retry Functionality to Mobile
**Component:** Mobile - Logic
**Estimated Time:** 1 hour
**Priority:** Medium
**Depends On:** Task 3.3

**Description:**
Implement retry button in progress screen.

**Implementation:**
1. Add retry handler:
```typescript
const handleRetry = async () => {
  setRetrying(true);
  try {
    const response = await api.retryExtraction(topic);
    if (response.status === 'retrying') {
      Toast.show(`Retry attempt ${response.attempt}`);
      setPollCount(0); // Reset polling
      startPolling();
    } else if (response.status === 'max_retries') {
      Alert.alert('Max Retries', response.error);
    }
  } catch (error) {
    Alert.alert('Error', 'Failed to retry extraction');
  } finally {
    setRetrying(false);
  }
};
```
2. Show retry button only when status='failed' and retry_count < 3
3. Disable retry button while retrying

**Acceptance Criteria:**
- [ ] Retry button appears when failed
- [ ] Calls retry API endpoint
- [ ] Shows attempt number in toast
- [ ] Resumes polling after retry
- [ ] Shows max retries error appropriately
- [ ] Button disabled while processing

**Files:**
- `feedfocus-mobile/src/screens/ExtractionProgressScreen.tsx`

---

### Task 3.6: Create Daily Refresh Script
**Component:** Daily Refresh
**Estimated Time:** 2 hours
**Priority:** Medium

**Description:**
Create scheduler script for daily content refresh.

**Implementation:**
1. Create `feedfocus/automation/daily_refresh.py`
2. Implement daily_refresh() function:
   - Query active topics with engagement SQL
   - For each topic, queue extraction with priority=1
   - Log results
3. Setup scheduler:
```python
import schedule
import time

def daily_refresh():
    # Get active topics
    topics = get_active_topics()

    for topic in topics:
        extraction_queue.add_job(
            topic=topic,
            user_id='system',
            priority=1
        )

    logger.info(f"Daily refresh queued {len(topics)} topics")

schedule.every().day.at("02:00").do(daily_refresh)

while True:
    schedule.run_pending()
    time.sleep(60)
```
4. Add to systemd or cron for production

**Acceptance Criteria:**
- [ ] Queries top 20 active topics
- [ ] Prioritizes topics with recent engagement
- [ ] Requires >= 3 active users in last 7 days
- [ ] Queues with low priority (1)
- [ ] Logs completion
- [ ] Runs at 2am daily
- [ ] Can be run manually for testing

**Files:**
- `feedfocus/automation/daily_refresh.py`

**Query:**
```sql
SELECT topic,
       COUNT(DISTINCT ut.user_id) as followers,
       COUNT(DISTINCT ue.user_id) as active_users_7d
FROM user_topics ut
LEFT JOIN user_engagement ue
  ON ue.insight_id IN (SELECT id FROM insights WHERE topic = ut.topic)
  AND ue.created_at > datetime('now', '-7 days')
WHERE topic IN (SELECT DISTINCT topic FROM insights)
GROUP BY topic
HAVING
  COUNT(DISTINCT ut.user_id) >= 30 AND
  COUNT(DISTINCT ue.user_id) >= 3
ORDER BY active_users_7d DESC, followers DESC
LIMIT 20
```

---

### Task 3.7: Test Daily Refresh Manually
**Component:** Testing
**Estimated Time:** 1 hour
**Priority:** Medium
**Depends On:** Task 3.6

**Description:**
Run daily refresh manually to verify it works.

**Implementation:**
1. Setup test data:
   - Create 25 topics with varying engagement
   - Add user engagement for last 7 days
2. Run daily_refresh() function manually
3. Verify correct topics are queued
4. Verify priority is 1 (low)
5. Verify user jobs (priority 10) process first

**Acceptance Criteria:**
- [ ] Selects correct 20 topics (most engaged)
- [ ] Queues all 20 topics
- [ ] All jobs have priority=1
- [ ] User-triggered jobs (priority 10) go first
- [ ] Logs helpful information
- [ ] No errors or crashes

**Files:**
- `feedfocus/tests/test_daily_refresh.py`

---

### Task 3.8: Create SystemD Service (Optional)
**Component:** Deployment
**Estimated Time:** 1 hour
**Priority:** Low

**Description:**
Create SystemD service file for daily refresh scheduler.

**Implementation:**
1. Create `/etc/systemd/system/feedfocus-refresh.service`:
```ini
[Unit]
Description=FeedFocus Daily Refresh Scheduler
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/feedfocus
Environment="PYTHONPATH=/home/ubuntu/feedfocus"
ExecStart=/usr/bin/python3 automation/daily_refresh.py
Restart=always

[Install]
WantedBy=multi-user.target
```
2. Enable and start service
3. Verify it runs

**Acceptance Criteria:**
- [ ] Service file created
- [ ] Service starts on boot
- [ ] Service restarts on failure
- [ ] Logs to journalctl
- [ ] Can check status with systemctl

**Files:**
- `/etc/systemd/system/feedfocus-refresh.service` (production)
- `feedfocus/deployment/feedfocus-refresh.service` (template)

---

### Task 3.9: End-to-End Testing
**Component:** Final Testing
**Estimated Time:** 2 hours
**Priority:** Critical
**Depends On:** All previous tasks

**Description:**
Comprehensive end-to-end testing of entire system.

**Test Scenarios:**
1. **Happy Path - New Topic:**
   - User adds new topic via mobile
   - Sees extraction progress screen
   - Extraction completes
   - Insights appear in feed

2. **Happy Path - Similar Topic:**
   - User adds topic similar to existing
   - Immediately sees existing topic insights
   - No wait time

3. **Error Recovery:**
   - Extraction fails
   - User sees error with retry button
   - User retries successfully
   - Insights appear

4. **Concurrent Users:**
   - 5 users add topics simultaneously
   - 2 process in parallel
   - 3 queue appropriately
   - All complete successfully

5. **Daily Refresh:**
   - Run refresh script
   - Verify low priority
   - Verify user jobs go first
   - Verify fresh insights added

6. **Invalid Topics:**
   - Submit invalid topics ("f", "test", etc.)
   - Verify rejected with helpful errors
   - Verify no queue entries created

**Acceptance Criteria:**
- [ ] All 6 scenarios pass
- [ ] No crashes or errors
- [ ] UI updates correctly
- [ ] Database state is correct
- [ ] Performance is acceptable (<1s response times)

**Files:**
- `feedfocus/tests/test_end_to_end.py`

---

## 📋 Final Checklist

### Pre-Deployment
- [ ] All 27 tasks completed
- [ ] All tests passing
- [ ] Database migration tested
- [ ] SQLite WAL mode enabled
- [ ] No console errors in mobile app
- [ ] API endpoints return correct status codes
- [ ] Error messages are user-friendly

### Performance
- [ ] Extraction completes in < 10 minutes (avg)
- [ ] 2 extractions can run in parallel
- [ ] No database lock errors
- [ ] API response time < 1 second
- [ ] Mobile app doesn't freeze during polling

### Production Readiness
- [ ] Environment variables documented
- [ ] Logs are structured and searchable
- [ ] Health endpoint returns useful metrics
- [ ] Daily refresh scheduler configured
- [ ] Backup strategy for extraction_jobs table
- [ ] Monitoring/alerting for failed jobs

---

## 🚀 Deployment Steps

### Backend Deployment
1. Run database migration (Task 1.1)
2. Deploy updated backend code
3. Restart backend service
4. Verify WAL mode enabled
5. Verify queue starts with 2 workers
6. Test with one topic extraction

### Mobile Deployment
1. Build mobile app with new screens
2. Test on iOS and Android
3. Submit to TestFlight/Google Play Beta
4. Monitor for crash reports

### Daily Refresh
1. Deploy daily_refresh.py script
2. Setup SystemD service or cron job
3. Test manual run
4. Verify runs at 2am next day

---

## 📊 Success Metrics

### Technical Metrics
- **Queue Processing Rate:** 2 topics/10 minutes (parallel)
- **Success Rate:** >95% extraction success
- **Auto-Retry Rate:** <10% of jobs need retry
- **Average Completion Time:** <8 minutes per topic
- **Concurrent Workers:** 2 active at all times

### User Experience Metrics
- **Time to First Insight:** <1 second (if topic exists)
- **Wait Time (New Topic):** <10 minutes average
- **Extraction Success Rate:** >95%
- **Failed Extractions with Retry:** <5%
- **Daily Active Topics Refreshed:** 20 topics

---

## 🐛 Known Issues & Mitigation

### ChromaDB Concurrent Writes
**Issue:** Multiple workers writing to ChromaDB simultaneously may conflict
**Mitigation:** Use file locking or ChromaDB's built-in concurrency handling
**Task:** Included in Task 1.7

### SQLite Lock Errors
**Issue:** SQLite may lock under heavy concurrent writes
**Mitigation:** WAL mode + thread-local connections + max 2-4 workers
**Task:** Included in Tasks 1.5, 1.6

### API Rate Limits
**Issue:** Claude API may throttle during parallel extraction
**Mitigation:** 1 second delay between calls + auto-retry on rate limit
**Task:** Included in Task 1.7

### Memory Leaks
**Issue:** Long-running workers may accumulate memory
**Mitigation:** Restart workers after N jobs (future enhancement)
**Status:** Not in current plan, monitor in production

---

## 📚 Documentation Updates Needed

After implementation:
- [ ] Add extraction queue to ARCHITECTURE.md (when created)
- [ ] Document retry logic in troubleshooting guide
- [ ] Add monitoring guide for queue health
- [ ] Update mobile development guide with new screens

---

**Total Estimated Time:** 35-40 hours
**Recommended Team Size:** 1-2 developers
**Risk Level:** Medium (new concurrent processing system)

**Next Steps:**
1. Review this implementation plan
2. Assign tasks to developer(s)
3. Setup task tracking (GitHub Issues, Jira, etc.)
4. Begin Day 1 tasks
5. Daily standup to track progress
