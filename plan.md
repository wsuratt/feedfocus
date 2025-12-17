# For You Algorithm v2 - Implementation Plan

## Overview
Upgrade from simple scoring to personalized recommendation system with user modeling, engagement feedback, and diversity-aware feed composition.

---

## Phase 1: User Profile Foundation
**Goal:** Build persistent user profiles with topic affinities and preferences

### 1.1 Database Schema
**File:** `db/migrations/004_user_profiles.sql`

```sql
-- User profile table
CREATE TABLE IF NOT EXISTS user_profiles (
    user_id TEXT PRIMARY KEY,
    quality_preference REAL DEFAULT 0.7,      -- 0-1, preferred quality level
    freshness_preference REAL DEFAULT 0.5,    -- 0-1, how much they prefer new content
    avg_session_length INTEGER DEFAULT 15,    -- Typical insights per session
    total_views INTEGER DEFAULT 0,
    total_likes INTEGER DEFAULT 0,
    total_saves INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Topic affinity scores (replaces simple follow/unfollow)
CREATE TABLE IF NOT EXISTS user_topic_affinities (
    user_id TEXT NOT NULL,
    topic TEXT NOT NULL,
    affinity_score REAL DEFAULT 0.5,  -- 0-1, how interested user is
    last_engagement_at TIMESTAMP,     -- For time decay calculation
    view_count INTEGER DEFAULT 0,
    like_count INTEGER DEFAULT 0,
    save_count INTEGER DEFAULT 0,
    dismiss_count INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, topic)
);

CREATE INDEX idx_user_topic_affinity ON user_topic_affinities(user_id, affinity_score DESC);
CREATE INDEX idx_topic_affinity ON user_topic_affinities(topic, affinity_score DESC);
```

### 1.2 User Profile Service
**File:** `backend/services/user_profile_service.py`

```python
class UserProfileService:
    def get_or_create_profile(user_id: str) -> UserProfile
    def get_topic_affinities(user_id: str, apply_decay=True) -> Dict[str, float]
    def update_topic_affinity(user_id: str, topic: str, delta: float)
    def get_quality_preference(user_id: str) -> float  # Default 0.7
    def get_freshness_preference(user_id: str) -> float  # Default 0.5
    def is_new_user(user_id: str) -> bool  # < 50 total views
    def apply_time_decay(affinity: float, weeks_since: int) -> float
        """affinity * (0.95 ** weeks_since_last_engagement)"""
```

**Initial Affinity Sources:**
- Topics user follows → 0.70 base affinity
- Topics user liked insights from → 0.40 base affinity
- Topics user saved insights from → 0.50 base affinity

**Time Decay:**
```python
effective_affinity = base_affinity * (0.95 ** weeks_since_last_engagement)
```
- No engagement for 8 weeks: affinity drops ~33% (0.95^8 ≈ 0.66)
- No engagement for 16 weeks: affinity drops ~55% (0.95^16 ≈ 0.44)
- Prevents stale interests from dominating feed

---

## Phase 2: Topic Similarity System
**Goal:** Enable "similar topic" discovery using existing embeddings

### 2.1 Topic Embedding Storage
**File:** `automation/topic_embeddings.py`

```python
def compute_topic_embedding(topic: str) -> List[float]:
    """Average embeddings of top 20 insights for this topic"""

def build_topic_similarity_index():
    """Pre-compute similarity matrix for all topics"""
    # Store in new table: topic_similarity

def get_similar_topics(topic: str, min_similarity=0.7) -> List[Tuple[str, float]]:
    """Return topics similar to given topic"""
```

### 2.2 Database Schema Addition
**File:** `db/migrations/004_user_profiles.sql` (append)

```sql
CREATE TABLE IF NOT EXISTS topic_similarities (
    topic_a TEXT NOT NULL,
    topic_b TEXT NOT NULL,
    similarity_score REAL NOT NULL,  -- Cosine similarity 0-1
    PRIMARY KEY (topic_a, topic_b)
);

CREATE INDEX idx_topic_sim_a ON topic_similarities(topic_a, similarity_score DESC);
```

**Run once on migration:** Compute similarities for all topic pairs > 0.7 threshold

---

## Phase 3: Enhanced Scoring Algorithm
**Goal:** Replace simple scoring with personalized multi-factor system

### 3.1 New Scoring Service
**File:** `backend/services/personalized_scorer.py`

```python
class PersonalizedScorer:
    def score_insight(
        insight: Dict,
        user_profile: UserProfile,
        context: FeedContext
    ) -> float:
        """
        Returns composite score 0-2+ range

        Components:
        - quality_fit (0-0.20): How well quality matches user preference
        - topic_affinity (0-0.30): Direct + similar topic affinities
        - social_proof (0-0.20): Engagement from other users
        - freshness (0-0.15): Recency with personalized decay
        - exploration (0-0.15): Random boost for discovery
        - diversity_penalty (-0.30-0): Reduce recent topic repetition
        """

class FeedContext:
    """Tracks feed composition state"""
    recent_topics: List[str]  # Last 10 topics shown
    recent_categories: List[str]

    def get_topic_penalty(topic: str) -> float:
        """-0.1 per occurrence in last 5 items"""
```

### 3.2 Quality Fit Calculation
```python
def calculate_quality_fit(insight_quality: float, user_preference: float) -> float:
    """
    User preference 0.7 means they prefer 7/10 content
    insight_quality 8/10 with preference 0.7 = slight mismatch
    Returns 0-1 where 1 = perfect match
    """
    return 1.0 - abs((insight_quality / 10.0) - user_preference)
```

### 3.3 Topic Affinity with Similar Topics
```python
def calculate_topic_score(
    insight_topic: str,
    user_affinities: Dict[str, float],
    topic_similarities: Dict[str, List[Tuple[str, float]]]
) -> float:
    # Direct affinity
    direct = user_affinities.get(insight_topic, 0)
    if direct:
        return direct

    # Similar topic affinity (discounted)
    similar_topics = topic_similarities.get(insight_topic, [])
    similar_scores = [
        user_affinities.get(sim_topic, 0) * sim_score * 0.7
        for sim_topic, sim_score in similar_topics
    ]
    return max(similar_scores) if similar_scores else 0
```

---

## Phase 4: Diversity-Aware Feed Composition
**Goal:** Move from pure score-sorting to curated sequencing with multi-layer deduplication

**Problem:** When extracting from newsletters (e.g., newsletter.gamediscover.co), you get 5+ insights with:
- Same source domain
- Same extraction timestamp
- Similar quality scores
- Same topic

Without diversity rules, these cluster together in the feed (all GameDiscover insights in a row).

**Solution:** 4 diversity layers:
1. **Topic diversity**: Max 2 same topic in last 3 items
2. **Category diversity**: Max 3 same category in last 5 items
3. **Source diversity**: Max 1 same domain in last 4 items ← Solves newsletter clustering
4. **Content near-duplicate**: Cosine similarity check (optional)

**Result with source diversity:**
```
✅ GameDiscover insight (score 0.82)
✅ Sacra insight (score 0.79)
✅ a16z blog insight (score 0.78)
✅ TechCrunch insight (score 0.77)
✅ GameDiscover insight (score 0.81) ← Now allowed again
```

Instead of:
```
❌ GameDiscover insight #1 (score 0.82)
❌ GameDiscover insight #2 (score 0.81)
❌ GameDiscover insight #3 (score 0.80)
❌ GameDiscover insight #4 (score 0.79)
❌ GameDiscover insight #5 (score 0.78)
```

### 4.1 Feed Builder
**File:** `backend/services/feed_builder.py`

```python
from functools import lru_cache
from typing import Dict, List, Optional, Tuple, Set
import time

class FeedBuilder:
    # Class-level cache for topic similarities (loaded once at startup)
    _topic_similarities: Optional[Dict[str, List[Tuple[str, float]]]] = None

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.scorer = PersonalizedScorer(db_path)

    @classmethod
    def get_topic_similarities(cls) -> Dict[str, List[Tuple[str, float]]]:
        """Load topic similarities once and cache in memory"""
        if cls._topic_similarities is None:
            cls._topic_similarities = cls._load_all_topic_similarities()
        return cls._topic_similarities

    @classmethod
    def _load_all_topic_similarities(cls) -> Dict[str, List[Tuple[str, float]]]:
        """Load entire topic similarity matrix into memory"""
        # Implementation: read from topic_similarities table
        pass

    def build_feed(
        self,
        user_id: str,
        candidates: List[Dict],
        length: int = 50
    ) -> List[Dict]:
        """
        Multi-stage feed construction with deduplication layers:

        1. **Insight-level dedup**: Already filtered in SQL
        2. **Batch load data**: Embeddings, user context (avoid N+1 queries)
        3. **Score**: Apply PersonalizedScorer to all candidates
        4. **Sort**: Order by predicted score
        5. **Select with diversity**: Apply topic/category/source/content diversity rules
        6. **Inject exploration**: Add discovery items every 10th position
        """

        # OPTIMIZATION: Batch load embeddings upfront (if near-dup enabled)
        embeddings_map = {}
        if DIVERSITY_RULES.get("near_duplicate_enabled", False):
            chroma_ids = [c.get('chroma_id') for c in candidates if c.get('chroma_id')]
            embeddings_map = self._batch_load_embeddings(chroma_ids)

        # OPTIMIZATION: Get cached user context (profile + affinities)
        user_profile, user_affinities = get_cached_user_context(user_id)
        topic_similarities = self.get_topic_similarities()

        # LAYER 1: Score all candidates (no DB calls in loop)
        context = FeedContext()
        scored = [
            (insight, self.scorer.score_insight(
                insight,
                user_profile,
                user_affinities,
                topic_similarities,
                context
            ))
            for insight in candidates
        ]
        scored.sort(key=lambda x: x[1], reverse=True)

        # LAYER 2: Select with diversity constraints
        feed = []
        recent_insights = []  # For content similarity checking

        for insight, score in scored:
            # Topic diversity check
            if self._violates_topic_diversity(insight, context):
                continue

            # Category diversity check
            if self._violates_category_diversity(insight, context):
                continue

            # Source diversity check (prevents same domain clustering)
            if self._violates_source_diversity(insight, context):
                continue

            # Content near-duplicate detection (optional, uses pre-loaded embeddings)
            if self._is_near_duplicate(insight, recent_insights, embeddings_map):
                continue

            feed.append(insight)
            context.add_to_recent(insight)
            recent_insights.append(insight)

            # Inject exploration every 10 items
            if len(feed) % 10 == 0 and len(feed) < length:
                exploration_insight = self._get_exploration_insight(
                    user_id,
                    user_affinities,
                    exclude_ids={i['id'] for i in feed}
                )
                if exploration_insight:
                    feed.append(exploration_insight)
                    context.add_to_recent(exploration_insight)

            if len(feed) >= length:
                break

        return feed

    def _get_viewed_insight_ids(self, user_id: str) -> Set[str]:
        """Get all insight IDs user has viewed (ever)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT insight_id
            FROM user_engagement
            WHERE user_id = ? AND action = 'view'
        """, (user_id,))
        viewed = {row[0] for row in cursor.fetchall()}
        conn.close()
        return viewed

    def _violates_topic_diversity(self, insight: Dict, context: FeedContext) -> bool:
        """Don't show same topic 2+ times in last 3 items"""
        recent_topics = context.recent_topics[-3:]
        return recent_topics.count(insight['topic']) >= 2

    def _violates_category_diversity(self, insight: Dict, context: FeedContext) -> bool:
        """Don't show same category 3+ times in last 5 items"""
        recent_categories = context.recent_categories[-5:]
        return recent_categories.count(insight['category']) >= 3

    def _violates_source_diversity(self, insight: Dict, context: FeedContext) -> bool:
        """Don't show same source domain more than once in last 4 items"""
        recent_sources = context.recent_sources[-4:]
        return insight.get('source_domain') in recent_sources

    def _batch_load_embeddings(self, chroma_ids: List[str]) -> Dict[str, List[float]]:
        """
        OPTIMIZATION: Load all embeddings in one ChromaDB call.
        Returns dict mapping chroma_id -> embedding vector.
        """
        if not chroma_ids:
            return {}

        from automation.semantic_db import collection

        try:
            result = collection.get(
                ids=chroma_ids,
                include=['embeddings']
            )

            # Build lookup map
            embeddings_map = {}
            for chroma_id, embedding in zip(result['ids'], result['embeddings']):
                if embedding:
                    embeddings_map[chroma_id] = embedding

            return embeddings_map

        except Exception as e:
            logger.warning(f"Batch embedding load failed: {e}")
            return {}

    def _is_near_duplicate(
        self,
        insight: Dict,
        recent_insights: List[Dict],
        embeddings_map: Dict[str, List[float]]
    ) -> bool:
        """
        OPTIMIZED: Check semantic similarity using pre-loaded embeddings.
        No ChromaDB calls in this method - just dict lookups + numpy math.
        """
        if not DIVERSITY_RULES.get("near_duplicate_enabled", False):
            return False  # Feature disabled

        if len(recent_insights) == 0:
            return False

        chroma_id = insight.get('chroma_id')
        if not chroma_id or chroma_id not in embeddings_map:
            return False

        current_embedding = embeddings_map[chroma_id]
        lookback = DIVERSITY_RULES.get("near_duplicate_lookback", 5)
        threshold = DIVERSITY_RULES.get("near_duplicate_threshold", 0.92)

        # Check similarity with recent insights
        for recent in recent_insights[-lookback:]:
            recent_chroma_id = recent.get('chroma_id')
            if not recent_chroma_id or recent_chroma_id not in embeddings_map:
                continue

            recent_embedding = embeddings_map[recent_chroma_id]
            similarity = self._cosine_similarity(current_embedding, recent_embedding)

            if similarity > threshold:
                return True

        return False

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Calculate cosine similarity between two vectors"""
        import numpy as np
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

    def _get_exploration_insight(
        self,
        user_id: str,
        user_affinities: Dict[str, float],
        exclude_ids: Set[str]
    ) -> Optional[Dict]:
        """
        Get random high-quality insight from topic user has 0 affinity with.
        For discovery.
        """
        if not user_affinities:
            return None  # New user, nothing to exclude

        user_topics = set(user_affinities.keys())

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Build placeholders for SQL IN clauses
        topic_placeholders = ','.join('?' * len(user_topics))
        exclude_placeholders = ','.join('?' * len(exclude_ids))

        # Get random high-quality insight from unfamiliar topic
        query = f"""
            SELECT id, topic, category, text, source_url, source_domain,
                   quality_score, engagement_score, created_at, chroma_id
            FROM insights
            WHERE quality_score >= 7
              AND is_archived = 0
        """
        params = []

        if user_topics:
            query += f" AND topic NOT IN ({topic_placeholders})"
            params.extend(user_topics)

        if exclude_ids:
            query += f" AND id NOT IN ({exclude_placeholders})"
            params.extend(exclude_ids)

        query += " ORDER BY RANDOM() LIMIT 1"

        cursor.execute(query, params)
        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                "id": row[0],
                "topic": row[1],
                "category": row[2],
                "text": row[3],
                "source_url": row[4],
                "source_domain": row[5],
                "quality_score": row[6],
                "engagement_score": row[7],
                "created_at": row[8],
                "chroma_id": row[9],
            }

        return None


class FeedContext:
    """Tracks feed composition state for diversity checks"""
    def __init__(self):
        self.recent_topics: List[str] = []
        self.recent_categories: List[str] = []
        self.recent_sources: List[str] = []  # Track source domains

    def add_to_recent(self, insight: Dict):
        self.recent_topics.append(insight['topic'])
        self.recent_categories.append(insight['category'])
        self.recent_sources.append(insight.get('source_domain', ''))

    def get_topic_penalty(self, topic: str) -> float:
        """Calculate penalty for topic repetition (-0.1 per occurrence in last 5)"""
        recent = self.recent_topics[-5:]
        return -0.1 * recent.count(topic)


# OPTIMIZATION: Cache user context with TTL to avoid repeated DB lookups
from cachetools import TTLCache
from threading import Lock

_user_context_cache = TTLCache(maxsize=1000, ttl=60)
_cache_lock = Lock()

def get_cached_user_context(user_id: str) -> Tuple[UserProfile, Dict[str, float]]:
    """
    Get user profile and topic affinities with 60s TTL cache.
    Thread-safe with lock.
    """
    with _cache_lock:
        if user_id in _user_context_cache:
            return _user_context_cache[user_id]

    # Cache miss - fetch from DB
    service = UserProfileService()
    profile = service.get_or_create_profile(user_id)
    affinities = service.get_topic_affinities(user_id, apply_decay=True)
    result = (profile, affinities)

    with _cache_lock:
        _user_context_cache[user_id] = result

    return result
```

### 4.2 Update FeedService
**File:** `backend/services/feed_service.py`

Modify `generate_for_you_feed()`:
```python
def generate_for_you_feed(
    self,
    user_id: str,
    limit: int = 30,
    offset: int = 0
) -> List[Dict]:
    """
    OPTIMIZED: Pre-filter candidates in SQL, then use FeedBuilder for scoring.
    """
    conn = self.get_db_connection()
    cursor = conn.cursor()

    # OPTIMIZATION: Pre-filter in SQL to reduce candidate pool
    # - Exclude already-viewed insights (not in FeedBuilder)
    # - Exclude low-quality insights (< threshold)
    # - Get recent insights first (for freshness)
    min_quality = PERFORMANCE.get("min_quality_threshold", 5)

    cursor.execute("""
        SELECT
            i.id, i.topic, i.category, i.text, i.source_url,
            i.source_domain, i.quality_score, i.engagement_score,
            i.created_at, i.chroma_id
        FROM insights i
        WHERE i.is_archived = 0
          AND i.quality_score >= ?  -- Pre-filter low quality
          AND i.id NOT IN (  -- Pre-filter already viewed
              SELECT insight_id
              FROM user_engagement
              WHERE user_id = ? AND action = 'view'
          )
        ORDER BY i.created_at DESC  -- Recent first
        LIMIT ?
    """, (min_quality, user_id, PERFORMANCE.get("candidate_pool_size", 200)))

    candidates = [dict(row) for row in cursor.fetchall()]
    conn.close()

    # Use FeedBuilder for scoring + diversity (no dedup needed - done in SQL)
    builder = FeedBuilder(self.db_path)
    feed = builder.build_feed(user_id, candidates, length=limit)

    # Mark as viewed
    if feed:
        self._mark_viewed(user_id, [f['id'] for f in feed])

    return feed
```

**Key Changes from v1:**
- Deduplication moved from SQL to FeedBuilder (more flexible)
- Fetch 200 candidates (was 30) to allow filtering
- Topic/category/source diversity enforced during selection
- Source diversity prevents newsletter clustering (GameDiscover, Sacra, etc.)
- Optional content near-duplicate detection using embeddings

---

## Phase 5: Engagement Feedback Loop
**Goal:** Update user profiles based on behavior

### 5.1 Engagement Tracking Enhancement
**File:** `backend/services/engagement_tracker.py`

```python
class EngagementTracker:
    def on_insight_viewed(
        user_id: str,
        insight_id: str,
        dwell_time_ms: int
    ):
        """
        Track view + update affinity based on dwell time
        Expected dwell = 2000ms per 100 chars
        engagement_signal = actual / expected (0.5-2.0 typical)
        affinity_delta = 0.05 * (signal - 0.5)  # Can be negative
        """

    def on_insight_liked(user_id: str, insight_id: str):
        """affinity_delta = +0.15"""

    def on_insight_saved(user_id: str, insight_id: str):
        """affinity_delta = +0.12"""

    def on_insight_dismissed(user_id: str, insight_id: str):
        """affinity_delta = -0.10"""

    def update_user_preferences(user_id: str):
        """
        Periodically (every 20 engagements) recalculate:
        - quality_preference: median quality of liked insights
        - freshness_preference: correlation between age and engagement
        """
```

### 5.2 Frontend Changes - Weighted Dwell Tracking
**Note:** Feed is scroll-based (multiple cards visible), not card-by-card like TikTok.
Use weighted tracking that considers both visibility % and position in viewport.

#### Custom Hook: `hooks/useDwellTracking.ts`

```typescript
interface DwellState {
  insightId: string;
  startTime: number;
  accumulatedMs: number;
  currentWeight: number;
}

export function useDwellTracking() {
  const dwellStates = useRef<Map<string, DwellState>>(new Map());

  const getVisibilityWeight = useCallback((entry: IntersectionObserverEntry): number => {
    if (entry.intersectionRatio < 0.3) return 0; // Below threshold, ignore

    // Factor 1: How much of the card is visible
    const visibleRatio = entry.intersectionRatio;

    // Factor 2: How centered the card is in viewport
    const rect = entry.boundingClientRect;
    const viewportCenter = window.innerHeight / 2;
    const cardCenter = rect.top + rect.height / 2;
    const maxDistance = window.innerHeight / 2;
    const distanceFromCenter = Math.abs(viewportCenter - cardCenter);
    const centerBonus = Math.max(0, 1 - (distanceFromCenter / maxDistance));

    // Combine: fully visible + centered = weight of 1.0
    return visibleRatio * centerBonus;
  }, []);

  const flushDwell = useCallback((insightId: string) => {
    const state = dwellStates.current.get(insightId);
    if (!state || state.accumulatedMs < 500) return; // Min threshold

    // Send to batched service
    recordDwellTime(insightId, Math.round(state.accumulatedMs));
    dwellStates.current.delete(insightId);
  }, []);

  const observer = useMemo(() => {
    return new IntersectionObserver(
      (entries) => {
        const now = Date.now();

        entries.forEach((entry) => {
          const insightId = (entry.target as HTMLElement).dataset.insightId;
          if (!insightId) return;

          const weight = getVisibilityWeight(entry);
          const existing = dwellStates.current.get(insightId);

          if (weight > 0) {
            if (existing) {
              // Update accumulated time with previous weight
              const elapsed = now - existing.startTime;
              existing.accumulatedMs += elapsed * existing.currentWeight;
              existing.startTime = now;
              existing.currentWeight = weight;
            } else {
              // Start tracking
              dwellStates.current.set(insightId, {
                insightId,
                startTime: now,
                accumulatedMs: 0,
                currentWeight: weight,
              });
            }
          } else if (existing) {
            // Card left viewport — finalize and flush
            const elapsed = now - existing.startTime;
            existing.accumulatedMs += elapsed * existing.currentWeight;
            flushDwell(insightId);
          }
        });
      },
      { threshold: [0, 0.3, 0.5, 0.7, 1.0] }  // Multiple thresholds for smooth tracking
    );
  }, [getVisibilityWeight, flushDwell]);

  // Flush when tab becomes hidden (user switches away)
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.hidden) {
        const now = Date.now();
        dwellStates.current.forEach((state, insightId) => {
          const elapsed = now - state.startTime;
          state.accumulatedMs += elapsed * state.currentWeight;
          flushDwell(insightId);
        });
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => document.removeEventListener('visibilitychange', handleVisibilityChange);
  }, [flushDwell]);

  const trackRef = useCallback((element: HTMLElement | null) => {
    if (element) {
      observer.observe(element);
    }
  }, [observer]);

  // Cleanup: disconnect observer and flush any remaining dwell states
  useEffect(() => {
    return () => {
      observer.disconnect();
      // Flush all remaining tracked insights
      const now = Date.now();
      dwellStates.current.forEach((state, insightId) => {
        const elapsed = now - state.startTime;
        state.accumulatedMs += elapsed * state.currentWeight;
        flushDwell(insightId);
      });
    };
  }, [observer, flushDwell]);

  return { trackRef };
}
```

#### Batched API Service: `services/dwellService.ts`

```typescript
const dwellBuffer: Array<{ insightId: string; dwellMs: number }> = [];
let flushTimeout: NodeJS.Timeout | null = null;

export function recordDwellTime(insightId: string, dwellMs: number) {
  dwellBuffer.push({ insightId, dwellMs });

  if (!flushTimeout) {
    flushTimeout = setTimeout(flushBuffer, 2000); // Batch every 2s
  }
}

async function flushBuffer() {
  if (dwellBuffer.length === 0) return;

  const batch = [...dwellBuffer];
  dwellBuffer.length = 0;
  flushTimeout = null;

  try {
    const token = await getAccessToken();
    await fetch(`${API_URL}/api/feed/dwell-batch`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify({ events: batch }),
    });
  } catch (e) {
    // Dwell is best-effort, drop on failure
    console.error('Dwell batch failed', e);
  }
}

// Flush on page unload using sendBeacon (more reliable)
if (typeof window !== 'undefined') {
  window.addEventListener('beforeunload', () => {
    if (dwellBuffer.length > 0) {
      navigator.sendBeacon(
        `${API_URL}/api/feed/dwell-batch`,
        JSON.stringify({ events: dwellBuffer })
      );
    }
  });
}
```

#### Usage in Feed: `components/InsightCard.tsx`

```typescript
function InsightCard({ insight }: { insight: Insight }) {
  const { trackRef } = useDwellTracking();

  return (
    <div
      ref={trackRef}
      data-insight-id={insight.id}
      className="insight-card"
    >
      {/* Card content */}
    </div>
  );
}
```

**Key Improvements:**
- **Weighted accumulation**: Cards centered in viewport count more
- **Gradual tracking**: 5 thresholds capture smooth scrolling
- **Batched requests**: Groups events every 2s (not per-card)
- **No data loss**: Uses `sendBeacon` on page unload
- **Tab visibility**: Flushes when user switches tabs

### 5.3 Batched API Endpoint
**File:** `backend/main.py`

```python
from pydantic import BaseModel
from typing import List

class DwellEvent(BaseModel):
    insightId: str
    dwellMs: int

class DwellBatch(BaseModel):
    events: List[DwellEvent]

@app.post("/api/feed/dwell-batch")
async def record_dwell_batch(
    batch: DwellBatch,
    user_id: str = Depends(verify_token) if AUTH_ENABLED else "default"
):
    """
    Process batch of weighted dwell events.
    Updates topic affinities based on engagement signals.
    """
    if not batch.events:
        return {"processed": 0}

    # OPTIMIZATION: Batch load all insights in one query (not N queries)
    insight_ids = [e.insightId for e in batch.events]
    conn = get_db_connection()
    cursor = conn.cursor()

    placeholders = ','.join('?' * len(insight_ids))
    cursor.execute(f"""
        SELECT id, topic, text FROM insights
        WHERE id IN ({placeholders})
    """, insight_ids)

    # Build lookup map
    insights_map = {row[0]: {"topic": row[1], "text": row[2]} for row in cursor.fetchall()}
    conn.close()

    # Process each event
    processed = 0
    engagement_tracker = EngagementTracker(DB_PATH)

    for event in batch.events:
        try:
            insight = insights_map.get(event.insightId)
            if not insight:
                continue

            topic = insight["topic"]
            text = insight["text"]

            # Expected dwell: ~20ms per character, min 2s, max 30s
            content_length = len(text)
            expected_dwell = min(max(content_length * 20, 2000), 30000)

            # Signal: 1.0 = met expectations, >1 = high interest, <1 = low
            engagement_signal = event.dwellMs / expected_dwell

            # Clamp to reasonable range (0.2 - 2.0)
            engagement_signal = min(max(engagement_signal, 0.2), 2.0)

            # Affinity delta: ranges from -0.03 to +0.05
            # 0.6 is the "neutral" point (60% of expected dwell)
            delta = 0.05 * (engagement_signal - 0.6)

            # Update topic affinity
            engagement_tracker = EngagementTracker(DB_PATH)
            engagement_tracker.update_topic_affinity(
                user_id=user_id,
                topic=topic,
                delta=delta
            )

            processed += 1

        except Exception as e:
            logger.error(f"Failed to process dwell event: {e}")
            continue

    return {"processed": processed}
```

**Engagement Signal Math:**
```python
# Examples:
# 1000ms dwell on 2000ms expected → signal = 0.5 → delta = -0.03 (negative)
# 2000ms dwell on 2000ms expected → signal = 1.0 → delta = +0.02
# 3000ms dwell on 2000ms expected → signal = 1.5 → delta = +0.045
# 4000ms dwell on 2000ms expected → signal = 2.0 → delta = +0.05 (capped)
```

---

## Phase 6: Preference Learning (OPTIONAL - Ship Later)
**Goal:** Automatically infer user preferences from behavior

**⚠️ Recommendation:** Skip this phase for initial launch. Ship with hardcoded defaults:
- `quality_preference = 0.7` (everyone)
- `freshness_preference = 0.5` (everyone)

Add learning layer later once you have:
- 1000+ users with 20+ likes each
- Data to validate learning actually improves engagement

This simplifies launch and lets you focus on core algorithm correctness.

### 6.1 Preference Calculator
**File:** `backend/services/preference_learner.py`

```python
def calculate_quality_preference(user_id: str) -> float:
    """
    Analyze liked insights:
    - Get quality_scores of all liked insights
    - Return median (robust to outliers)
    - ONLY if user has 20+ likes, else default to 0.7
    """

    liked_count = get_user_like_count(user_id)
    if liked_count < 20:
        return 0.7  # Not enough data, use default

def calculate_freshness_preference(user_id: str) -> float:
    """
    Correlation analysis:
    - Compare age_days vs engagement_rate
    - High correlation → low freshness preference
    - Low/negative → high freshness preference
    """

def update_user_preferences_async(user_id: str):
    """
    Background task triggered every 20 engagements
    Recalculate quality_preference and freshness_preference
    """
```

---

## Dependencies

**New Python packages required:**
```txt
cachetools>=5.3.0  # For TTLCache (user context caching)
numpy>=1.24.0      # For cosine similarity (if not already installed)
```

Add to `requirements-backend.txt`.

**Database Schema Verification:**
Ensure `insights` table has `chroma_id` column:
```sql
-- Should already exist from migration 001
ALTER TABLE insights ADD COLUMN chroma_id TEXT;  -- Only if missing
CREATE INDEX IF NOT EXISTS idx_insights_chroma ON insights(chroma_id);
```

---

## Implementation Order

### Sprint 1: Topic Similarity (Days 1-2) ⭐ QUICK WIN
- [ ] Implement topic_embeddings.py
- [ ] Build similarity matrix for all topics
- [ ] Add topic_similarities table
- [ ] Verify similar topic queries
- **Why first:** Independent of user profiles, immediate value in feed

### Sprint 2: Foundation (Days 3-5)
- [ ] Create migration 004_user_profiles.sql
- [ ] Implement UserProfileService
- [ ] Backfill user_topic_affinities from existing user_topics + engagement
- [ ] Run migration and verify data

### Sprint 3: Scoring v2 (Days 6-8)
- [ ] Implement PersonalizedScorer
- [ ] Implement FeedContext
- [ ] Write unit tests for scoring components
- [ ] Compare v1 vs v2 scores on sample data

### Sprint 4: Feed Composition (Days 9-10)
- [ ] Implement FeedBuilder
- [ ] Update FeedService.generate_for_you_feed()
- [ ] Test diversity rules
- [ ] Verify exploration injection

### Sprint 5: Engagement Loop (Days 11-13)
- [ ] Implement EngagementTracker
- [ ] Add dwell time tracking to frontend
- [ ] Create /api/feed/dwell endpoint
- [ ] Wire up all engagement updates

### Sprint 6: Polish & Monitoring (Days 14-15)
- [ ] Add analytics for scoring component breakdown
- [ ] Dashboard for affinity distribution per user
- [ ] A/B test preparation (feature flags)
- [ ] Load testing with 1000+ users

### Sprint 6.5: Learning (OPTIONAL - Post-Launch)
- [ ] Implement PreferenceLearner
- [ ] Add background job for preference updates
- [ ] Test on sample users
- [ ] Monitor preference drift

### Sprint 7: Polish & Deploy (Days 16-17)
- [ ] A/B test old vs new algorithm
- [ ] Monitor engagement metrics
- [ ] Tune weights and thresholds
- [ ] Full production deploy

---

## Success Metrics

**User Engagement:**
- [ ] +20% in avg session length (insights/session)
- [ ] +15% in like rate (likes/views)
- [ ] -30% in dismiss rate

**Diversity:**
- [ ] Avg unique topics per 30-insight session: 12+ (up from ~8)
- [ ] Max consecutive same-topic insights: ≤2

**Personalization:**
- [ ] New users see more exploration (>15% random)
- [ ] Established users see 80%+ from high-affinity topics

---

## Configuration

**Tunable Parameters:**
```python
SCORING_WEIGHTS = {
    "quality_fit": 0.20,
    "topic_affinity": 0.30,
    "social_proof": 0.20,
    "freshness": 0.15,
    "exploration": 0.15,  # New users
}

EXPLORATION_RATES = {
    "new_user": 0.15,      # < 50 views
    "established": 0.03,   # >= 50 views (start low, tune up if needed)
}

TIME_DECAY = {
    "base_rate": 0.95,     # Decay factor per week
    "enabled": True,
}

ENGAGEMENT_DELTAS = {
    "view_low_dwell": -0.02,   # < 50% expected
    "view_high_dwell": +0.05,  # > 100% expected
    "like": +0.15,
    "save": +0.12,
    "dismiss": -0.10,
}

DIVERSITY_RULES = {
    "max_same_topic_in_last_3": 2,
    "max_same_category_in_last_5": 3,
    "max_same_source_in_last_4": 1,  # Prevent source domain clustering
    "exploration_interval": 10,  # Every 10th item
    "near_duplicate_enabled": False,  # ⚠️ Disabled by default (enable after benchmarking)
    "near_duplicate_threshold": 0.92,  # Cosine similarity (0-1)
    "near_duplicate_lookback": 5,  # Check last 5 insights
}

PERFORMANCE = {
    "candidate_pool_size": 200,          # Fetch N candidates for filtering
    "min_quality_threshold": 5,          # Pre-filter insights < this score
    "user_context_cache_ttl_sec": 60,    # Cache user profiles for 60s
    "topic_similarity_cache": True,      # Load similarities at startup (not per-request)
    "batch_load_embeddings": True,       # Load all embeddings upfront (not per-check)
}

PREFERENCE_THRESHOLDS = {
    "new_user_views": 50,              # < 50 views = new
    "min_likes_for_learning": 20,      # Need 20+ likes to learn quality pref
    "preference_update_interval": 20,  # Recalc every 20 engagements
}

DWELL_TIME_THRESHOLDS = {
    "min_meaningful_view_ms": 1000,         # < 1s ignored
    "expected_dwell_per_100_chars": 2000,   # 2s per 100 characters
    "low_engagement_threshold": 0.5,        # < 50% expected = low engagement
    "high_engagement_threshold": 1.5,       # > 150% expected = high engagement
}
```

---

## Performance Estimates

### With Optimizations (Current Plan)

| Step | Time |
|------|------|
| SQL query (200 pre-filtered candidates) | ~20ms |
| Batch load embeddings (if enabled) | ~50ms |
| Get cached user context | ~1ms (cache hit) |
| Get cached topic similarities | ~1ms (in-memory) |
| Score 200 candidates | ~30ms |
| Diversity filtering + selection | ~5ms |
| **Total** | **~100ms** ✅ |

### Without Optimizations (Original Naive Approach)

| Step | Time |
|------|------|
| SQL query (no pre-filtering) | ~20ms |
| Get user profile (uncached) | ~50ms |
| Get user affinities (uncached) | ~80ms |
| Get topic similarities (per-request) | ~100ms |
| Score 200 (with N+1 DB queries) | ~200ms |
| Near-dup checks (1000 ChromaDB calls) | ~2000ms |
| **Total** | **~2.5s** ❌ |

**Key Optimizations:**
1. **SQL pre-filtering** saves FeedBuilder from processing low-quality/viewed insights
2. **Batch embedding load** (1 call) replaces 1000 individual ChromaDB calls
3. **60s user context cache** avoids repeated profile/affinity lookups
4. **Startup topic similarity cache** eliminates per-request DB queries
5. **Near-duplicate disabled by default** until benchmarked in production

**Near-Duplicate Trade-off:**
- **Disabled**: 100ms feed load, topic diversity handles most repetition
- **Enabled**: 150ms feed load (+50ms batch embeddings), catches semantic dups

Enable `near_duplicate_enabled = True` after verifying:
- ChromaDB query performance with your data size
- Whether topic/category diversity is sufficient
- A/B test showing engagement improvement

---

## Rollback Plan

**If metrics decline:**
1. Feature flag to toggle between v1/v2 algorithms
2. Keep v1 code in `feed_service.py` as `generate_for_you_feed_v1()`
3. Monitor for 48 hours before full rollback decision

**Migration Safety:**
- All new tables have `IF NOT EXISTS`
- Old tables untouched
- Can run both algorithms in parallel
