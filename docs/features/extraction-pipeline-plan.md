FEED FOCUS: Search, Extract, and Refresh Pipeline

=== OVERVIEW ===
Build complete system for:
1. User searches/adds topics → Queue extraction if needed
2. Background workers extract insights in parallel
3. Daily refresh adds fresh content to active topics

=== DATABASE SCHEMA ===

New tables needed:

extraction_jobs:
- id, topic, user_id, priority (1-10)
- status (queued/processing/complete/failed)
- insight_count, error, created_at, updated_at
- retry_count (int, default 0)
- last_retry_at (text, nullable)
- estimated_completion_at (text, nullable)
- sources_processed (int, default 0)
- extraction_duration_seconds (float, nullable)
- Indexes on: topic, status, user_id

Keep existing:
- insights (id, topic, category, text, source_url, source_domain, quality_score, created_at)
- user_topics (user_id, topic, followed_at)
- user_seen_insights (user_id, insight_id, seen_at)

=== COMPONENT 1: TOPIC VALIDATION ===

Create validate_topic(topic: str) function:
- Minimum 2 chars, maximum 50 chars
- Only letters, numbers, spaces, hyphens allowed
- For 2-3 char topics: Must be in recognized acronym list (ML, AI, NFT, iOS, DeFi, SaaS, B2B, etc.)
- For 4+ char topics: Normal validation (no special vowel requirement)
- Banned words list: NSFW terms, test words (test, asdf, qwerty)
- Reject overly vague terms (stuff, things, content)
- Return: (is_valid: bool, error_message: str)

Create suggest_topic_improvements(topic: str):
- Detect vague terms (stuff, things, content) → suggest being specific
- Detect overly broad terms (business, technology) → suggest narrowing
- Detect questions (starts with how/what/why) → suggest phrase format
- Return: helpful suggestion string or empty if topic looks good

=== COMPONENT 2: SEMANTIC SIMILARITY CHECK ===

Create find_similar_topic(topic: str, threshold: float) function:

Uses ChromaDB to check if topic semantically similar to existing:
- Query ChromaDB across all collections
- Get top 3 similar topics with similarity scores
- Return tiered response:

If max_similarity > 0.85:
  → Return existing topic (very similar, just reuse)
  Example: "AI agents" vs "artificial intelligence agents"

Elif max_similarity > 0.65:
  → Return existing topic BUT also queue extraction for new topic
  → Show user existing insights immediately
  → Extract new topic in background
  Example: "startup fundraising" vs "venture capital"

Else:
  → Return None (completely new topic, need full extraction)
  Example: "AI agents" vs "college football"

=== COMPONENT 3: EXTRACTION QUEUE ===

Build ExtractionQueue class with 2 worker threads:

Initialization:
- Create Queue() for jobs
- Spawn 2 worker threads (daemon=True)
- Each worker runs in infinite loop processing jobs

Worker logic:
- Get job from queue (topic, user_id, priority)
- Update extraction_jobs table: status = 'processing', estimated_completion_at = now + 5min
- Set timeout (15 minutes max per extraction using threading.Timer)
- Call extract_insights(topic, num_sources=40, min_quality=7.0, rate_limit_delay=1.0)
- On success:
  * Save insights to SQLite + ChromaDB
  * Update extraction_jobs: status='complete', insight_count=N, extraction_duration_seconds=X
  * TODO: Send push notification to user
- On timeout:
  * Log timeout error
  * Update extraction_jobs: status='failed', error={"type": "timeout", "message": "Extraction exceeded 15 minutes", "retry_eligible": true}
  * Auto-retry if retry_count < 3
- On failure:
  * Log error with categorization (api_rate_limit, no_results, network_error, etc.)
  * Update extraction_jobs: status='failed', error={type, message, retry_eligible}
  * Auto-retry if error is transient (api_rate_limit, network_error) and retry_count < 3
- Mark queue.task_done()

add_job(topic, user_id, priority) method:
- Check if job already queued/processing (query extraction_jobs table)
- If exists, return False (don't duplicate)
- Insert into extraction_jobs table: status='queued'
- Add (topic, user_id, priority) to queue
- Return True

get_job_status(topic) method:
- Query extraction_jobs table for latest job
- Return: {status, insight_count, error, created_at, updated_at}

Priority levels:
- 10 = User-triggered (someone just followed topic)
- 1 = Daily refresh (background batch job)
- Higher priority = processed first

Global instance:
- extraction_queue = None
- init_queue(num_workers=2) → creates global instance
- Call on app startup

=== COMPONENT 4: API ENDPOINTS ===

POST /api/topics/follow:
Input: topic (string), user_id (string)

Flow:
1. Validate topic using validate_topic()
   - If invalid: return {error, status: 'invalid'}

2. Check semantic similarity using find_similar_topic(threshold=0.85)
   - If very similar (>0.85):
     * Use existing topic
     * Add user to that topic
     * Return {status: 'ready', topic: existing_topic}

3. Add user to topic immediately (even if extracting)
   - INSERT INTO user_topics (user_id, topic, followed_at)

4. Check existing insight count
   - SELECT COUNT(*) FROM insights WHERE topic = ?
   - If >= 30 insights exist:
     * Return {status: 'ready', topic, insight_count}

5. Need extraction - add to queue
   - extraction_queue.add_job(topic, user_id, priority=10)
   - Return {status: 'extracting', topic, message, existing_count}

GET /api/topics/{topic}/status:
Input: topic (string), user_id (string)

Return:
- topic: string
- is_following: bool (check user_topics)
- insight_count: int (count from insights table)
- extraction_job: object or null (get_job_status from queue)
  * status: queued/processing/complete/failed
  * insight_count: int
  * error: object or null (with type, message, retry_eligible)
  * sources_processed: int
  * estimated_completion_at: timestamp or null
  * retry_count: int
  * created_at, updated_at: timestamps

POST /api/topics/{topic}/retry:
Input: topic (string), user_id (string)

Flow:
1. Check extraction_jobs for failed job
2. If retry_count >= 3: Return {error: "Max retries reached (3)", status: 'max_retries'}
3. Increment retry_count, update last_retry_at
4. Re-queue with priority=10
5. Return {status: 'retrying', attempt: retry_count+1, message: "Extraction requeued"}

GET /api/queue/health:

Return:
- workers_active: int (number of active workers)
- queue_size: int (pending jobs)
- jobs_processing: int (currently running)
- recent_failures: list (last 5 failed jobs with topics and errors)
- avg_completion_time: float (average extraction duration in minutes)
- total_completed_today: int

=== COMPONENT 5: EXTRACTION PIPELINE (MODIFY EXISTING) ===

Update extract_insights() to support incremental refresh:

Parameters:
- topic: string
- num_sources: int (40 for new topics, 10 for refresh)
- recency_days: int (None for new topics, 7 for daily refresh)
- min_quality: float (7.0 default)
- rate_limit_delay: float (1.0 seconds between API calls, prevents rate limiting)

Changes needed:
1. When recency_days specified:
   - Only search for sources published in last N days
   - Filter out sources already processed (check insights table)
   - Extract fewer sources (10 vs 40)

2. Rate limiting:
   - Add time.sleep(rate_limit_delay) between API calls
   - Prevents hitting Claude API rate limits during parallel extraction
   - Update sources_processed count in extraction_jobs table every 5 sources

3. Deduplication check:
   - Before adding insight, check ChromaDB similarity
   - Skip if similarity > 0.20 (duplicate)
   - Also check SQLite for exact text match

4. Save to both:
   - SQLite insights table (source of truth for feeds)
   - ChromaDB (for deduplication only)
   - Use file locking or ChromaDB's concurrency handling for multi-worker writes

=== COMPONENT 6: DAILY REFRESH SCHEDULER ===

Create daily_refresh.py script:

Run at 2am daily using schedule library:
- schedule.every().day.at("02:00").do(daily_refresh)

daily_refresh() function:
1. Query active topics (prioritize engagement over just follower count):
   SELECT topic,
          COUNT(DISTINCT ut.user_id) as followers,
          COUNT(DISTINCT ue.user_id) as active_users_7d,
          MAX(ue.created_at) as last_engagement
   FROM user_topics ut
   LEFT JOIN user_engagement ue
     ON ue.insight_id IN (SELECT id FROM insights WHERE topic = ut.topic)
     AND ue.created_at > datetime('now', '-7 days')
   WHERE topic IN (SELECT DISTINCT topic FROM insights)
   GROUP BY topic
   HAVING
     COUNT(DISTINCT ut.user_id) >= 30 AND  -- Enough content
     COUNT(DISTINCT ue.user_id) >= 3        -- At least 3 active users recently
   ORDER BY
     active_users_7d DESC,  -- Prioritize topics people are engaging with
     followers DESC
   LIMIT 20  -- Only refresh top 20 most active topics

2. For each active topic:
   - extraction_queue.add_job(topic, 'system', priority=1)
   - Low priority = runs after user-triggered jobs

3. Log completion

Run in infinite loop:
- while True: schedule.run_pending(); time.sleep(60)

=== COMPONENT 7: MOBILE UX ===

Update AddTopicScreen:

handleFollowTopic(topic):
1. Call POST /api/topics/follow
2. If status='ready':
   - Show toast "Following {topic}"
   - Navigate to feed
3. If status='extracting':
   - Show toast with message
   - Navigate to ExtractionProgressScreen
   - Start polling for status every 10 seconds

Create ExtractionProgressScreen:

Display:
- Topic name
- Current status (queued/processing)
- Progress message
- "Browse Feed" button (let user leave screen)
- If existing_count > 0: Show related insights while waiting

Polling logic (exponential backoff to reduce server load):
- Poll intervals: [5, 10, 15, 30, 30, 30] seconds
- Track pollCount, use pollIntervals[min(pollCount, 5)]
- GET /api/topics/{topic}/status on each poll
- Update UI based on extraction_job.status and sources_processed
- Show progress: "Processing source {sources_processed}/40"
- If complete: Show notification, navigate to feed
- If failed: Show error with type and message, show "Retry" button
  * Retry button calls POST /api/topics/{topic}/retry
  * If max retries: Show "Contact support" message

Add push notification:
- When extraction completes, send notification
- "Insights ready for {topic}!" with deep link to feed

=== COMPONENT 8: STARTUP & SHUTDOWN ===

FastAPI app events:

@app.on_event("startup"):
- Enable SQLite WAL mode for better concurrency:
  * conn = sqlite3.connect('insights.db')
  * conn.execute('PRAGMA journal_mode=WAL')
- Use thread-local SQLite connections in workers
- init_queue(num_workers=2)
- Log "Extraction queue started with 2 workers"

@app.on_event("shutdown"):
- extraction_queue.stop()
- Wait for workers to finish current jobs
- Log "Extraction queue stopped"

=== IMPLEMENTATION ORDER ===

Day 1 (Backend Core):
1. Create extraction_jobs table
2. Build topic validation functions
3. Build semantic similarity function
4. Build ExtractionQueue class (150 lines)
5. Test queue with mock extraction

Day 2 (API Integration):
1. Update POST /api/topics/follow endpoint
2. Create GET /api/topics/{topic}/status endpoint
3. Create POST /api/topics/{topic}/retry endpoint
4. Create GET /api/queue/health endpoint
5. Integrate queue with existing extraction pipeline
6. Add startup/shutdown hooks with SQLite WAL mode
7. Test full flow: add topic → queue → extract → complete
8. Test retry flow: force failure → retry → success

Day 3 (Mobile + Daily Refresh):
1. Update mobile AddTopicScreen with queue support
2. Create ExtractionProgressScreen with polling
3. Build daily_refresh.py scheduler script
4. Test daily refresh (run manually, verify priority)
5. Deploy both backend + mobile

=== KEY DECISIONS ===

Why 2 workers?
- Balance: Can process 2 topics in parallel
- Cost: Doesn't overwhelm API or Claude API rate limits
- Latency: User waits max 5 min (if 1 job ahead)
- Scale: Handles 100+ users easily

Why threading not Celery?
- Simpler: 150 lines vs 500+ lines + Redis
- Fast enough: 2 workers = 24 topics/hour (with rate limiting)
- Sufficient: Handles first 1,000 users
- SQLite WAL mode + thread-local connections = safe for 2-4 workers
- Upgrade path: Migrate to Celery + Redis later if needed (>1000 daily users)

Why priority system?
- User experience: User-triggered jobs never wait for batch
- Fairness: Daily refresh runs in background at low priority
- Simple: Just an integer 1-10, higher = first

Why track in database?
- Persistence: Survives app restart
- Visibility: User can check status with progress updates
- Debugging: Can see failed jobs with categorized errors
- Retry: Auto-retry transient failures, manual retry for others
- Metrics: Track extraction performance over time

=== SUCCESS METRICS ===

After implementation, verify:
- User adds topic → sees "extracting" immediately (< 1 sec)
- User can browse feed while extraction happens
- 2 users add topics simultaneously → both process in parallel
- User gets notification when extraction completes (~5 min)
- Daily refresh runs at 2am without blocking user requests
- Failed extractions logged with error message
- No duplicate extractions for same topic

=== TESTING CHECKLIST ===

Manual tests:
☐ Add new topic → verify queued → verify completes → verify insights appear
☐ Add 3 topics rapidly → verify 2 process in parallel, 1 queues
☐ Add duplicate topic → verify rejects with "already queued"
☐ Add similar topic (e.g., "AI agents" when "artificial intelligence" exists) → verify returns existing
☐ Check status endpoint while extraction in progress → verify shows "processing" with sources_processed count
☐ Kill worker mid-extraction → verify job marked failed with timeout, auto-retries
☐ Force rate limit error → verify categorized as transient, auto-retries
☐ Max out retries (3) → verify shows max retries error, no auto-retry
☐ Manual retry via POST endpoint → verify requeues with incremented retry_count
☐ Run daily refresh → verify low priority jobs wait for user jobs
☐ Check health endpoint → verify shows queue stats and recent failures
☐ Invalid topic ("f") → verify rejects with helpful error
☐ Valid acronym ("ML", "AI") → verify accepts
☐ Polling with exponential backoff → verify intervals increase (5s, 10s, 15s, 30s...)
☐ SQLite WAL mode → verify concurrent writes from 2 workers work smoothly

=== FILES TO CREATE/MODIFY ===

New files:
- backend/extraction_queue.py (ExtractionQueue class)
- backend/topic_validation.py (validation functions)
- backend/semantic_search.py (similarity function)
- automation/daily_refresh.py (scheduler script)
- mobile/screens/ExtractionProgressScreen.tsx

Modified files:
- backend/main.py (add endpoints, startup/shutdown)
- backend/extraction_pipeline.py (add recency filter, modify dedup)
- backend/database.py (add extraction_jobs table)
- mobile/screens/AddTopicScreen.tsx (add queue support)
- mobile/services/api.ts (add status endpoint)

=== NOTES ===

- Keep ChromaDB for deduplication, SQLite for feeds (hybrid approach)
- SQLite WAL mode enables safe concurrent writes from multiple workers
- Thread-local database connections prevent connection conflicts
- Start with 2 workers, increase to 4-6 if needed in Month 2
- Daily refresh prioritizes topics with recent engagement (not just follower count)
- Priority system ensures users never wait for batch jobs
- Extraction status visible to user with progress tracking
- Auto-retry transient failures (rate limits, network errors)
- Manual retry for non-transient failures (max 3 attempts)
- Rate limiting (1s delay) prevents API throttling during parallel extraction
- Timeout protection (15 min) prevents hung extractions
- Health endpoint for monitoring queue performance
- Can upgrade to Celery + Redis later if traffic demands it (>1000 daily users)
- Push notifications on completion improve perceived performance
