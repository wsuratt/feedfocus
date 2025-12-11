# Feed Focus: Unified Feed Implementation Plan

## 🎯 Vision: From Topic Sections → TikTok-Style Social Feed

**Current (Wrong):** Separate sections per topic - user picks which to browse
**New (Right):** Unified infinite scroll with Following + For You tabs - algorithmically blended

---

## 📊 The Architecture Shift

### Before: Per-Topic Feeds
```
User's Feed:
├─ AI Agents (40 insights)
├─ Value Investing (40 insights)
└─ Gen Z Consumer (40 insights)
Total: 120 insights in silos
```
**Problems:**
- ❌ User exhausts each topic
- ❌ No cross-pollination
- ❌ Hard to discover new topics
- ❌ Maintenance per topic

### After: Unified Feed (Twitter/TikTok Model)
```
Global Pool: 10,000+ insights across 50 topics

User's Feed (algorithmically ranked):
├─ AI Agents insight
├─ Value Investing insight
├─ Gen Z Consumer insight
├─ AI Agents insight
├─ Startup Fundraising insight (discovery!)
└─ ... (infinite scroll)
```
**Benefits:**
- ✅ Never exhausts content
- ✅ Seamless blended experience
- ✅ Organic topic discovery
- ✅ Scales with user base
- ✅ Addictive UX

---

## 🏗️ Two-Feed System (Like Twitter)

### Feed 1: Following
**What:** Insights from topics the user selected
**Source:** User's followed topics only
**Ranking:** Quality + personalization + freshness
**Purpose:** Comfort, familiar content

### Feed 2: For You
**What:** Algorithmic recommendations from ANY topic
**Source:** Entire database (all topics)
**Ranking:** Predicted engagement + similarity to user's interests
**Purpose:** Discovery, introduce new topics

---

## 💾 Database Architecture

### New Tables

#### 1. Global Insights Table
```sql
CREATE TABLE insights (
    id UUID PRIMARY KEY,
    topic VARCHAR(100) NOT NULL,
    category VARCHAR(50),  -- CASE STUDY, PLAYBOOK, etc.
    text TEXT NOT NULL,
    source_url TEXT,
    source_domain VARCHAR(100),
    quality_score DECIMAL(3,2),  -- 0-10 from extraction
    engagement_score DECIMAL(3,2) DEFAULT 0,  -- % who liked/saved
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    is_archived BOOLEAN DEFAULT FALSE
);

CREATE INDEX idx_topic ON insights(topic);
CREATE INDEX idx_created_at ON insights(created_at);
CREATE INDEX idx_quality_score ON insights(quality_score);
CREATE INDEX idx_engagement_score ON insights(engagement_score);
```

#### 2. User Following (Topics)
```sql
CREATE TABLE user_topics (
    user_id VARCHAR(50),
    topic VARCHAR(100),
    followed_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (user_id, topic)
);

CREATE INDEX idx_user_topics ON user_topics(user_id);
```

#### 3. User Engagement Tracking
```sql
CREATE TABLE user_engagement (
    id UUID PRIMARY KEY,
    user_id VARCHAR(50) NOT NULL,
    insight_id UUID NOT NULL,
    action VARCHAR(20),  -- 'view', 'like', 'save', 'dismiss'
    created_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (insight_id) REFERENCES insights(id)
);

CREATE INDEX idx_user_engagement ON user_engagement(user_id, insight_id);
CREATE INDEX idx_engagement_action ON user_engagement(action);
```

#### 4. User Preferences (Derived)
```sql
CREATE TABLE user_preferences (
    user_id VARCHAR(50) PRIMARY KEY,
    liked_categories JSONB,  -- {"CASE STUDY": 15, "PLAYBOOK": 8, ...}
    saved_sources JSONB,  -- {"anthropic.com": 5, "a16z.com": 3, ...}
    topic_affinity JSONB,  -- {"AI agents": 0.95, "Value Investing": 0.78, ...}
    updated_at TIMESTAMP DEFAULT NOW()
);
```

---

## 🔄 API Endpoints

### New Backend Routes

#### 1. Get Following Feed
```python
@app.get("/api/feed/following")
async def get_following_feed(
    user_id: str,
    limit: int = 30,
    offset: int = 0
):
    """
    Returns unified feed of insights from user's followed topics
    Sorted by personalized ranking algorithm
    """
    # Get user's followed topics
    topics = db.get_user_topics(user_id)

    # Get all insights from these topics
    insights = db.get_insights_by_topics(topics)

    # Remove already seen
    seen_ids = db.get_seen_insights(user_id)
    unseen = [i for i in insights if i.id not in seen_ids]

    # Calculate personalized score for each
    for insight in unseen:
        insight.score = calculate_feed_score(user_id, insight)

    # Sort by score
    ranked = sorted(unseen, key=lambda x: x.score, reverse=True)

    # Paginate
    return ranked[offset:offset+limit]
```

#### 2. Get For You Feed
```python
@app.get("/api/feed/for-you")
async def get_for_you_feed(
    user_id: str,
    limit: int = 30,
    offset: int = 0
):
    """
    Returns algorithmic recommendations from ALL topics
    Includes topic discovery and collaborative filtering
    """
    # Get ALL insights (not just followed topics)
    all_insights = db.get_all_insights()

    # Remove already seen
    seen_ids = db.get_seen_insights(user_id)
    unseen = [i for i in all_insights if i.id not in seen_ids]

    # Calculate predicted engagement
    for insight in unseen:
        insight.predicted_score = predict_engagement(user_id, insight)

    # Sort by prediction
    ranked = sorted(unseen, key=lambda x: x.predicted_score, reverse=True)

    # Paginate
    return ranked[offset:offset+limit]
```

#### 3. Record Engagement
```python
@app.post("/api/feed/engage")
async def record_engagement(
    user_id: str,
    insight_id: str,
    action: str  # 'view', 'like', 'save', 'dismiss'
):
    """
    Track user engagement for algorithm improvement
    """
    # Record engagement
    db.record_engagement(user_id, insight_id, action)

    # Update user preferences (async)
    update_user_preferences.delay(user_id)

    # Update insight engagement score (async)
    update_insight_engagement_score.delay(insight_id)

    return {"status": "recorded"}
```

#### 4. Follow/Unfollow Topic
```python
@app.post("/api/topics/follow")
async def follow_topic(user_id: str, topic: str):
    """Add topic to user's following list"""
    db.add_user_topic(user_id, topic)
    return {"status": "following", "topic": topic}

@app.delete("/api/topics/follow")
async def unfollow_topic(user_id: str, topic: str):
    """Remove topic from user's following list"""
    db.remove_user_topic(user_id, topic)
    return {"status": "unfollowed", "topic": topic}
```

---

## 🧮 Ranking Algorithm

### Unified Scoring Function

```python
def calculate_feed_score(user_id: str, insight: dict) -> float:
    """
    Calculate personalized score for any insight
    Used for both Following and For You feeds
    """
    score = 0.0
    user_prefs = get_user_preferences(user_id)

    # 1. Base Quality (20%)
    # From extraction quality score (0-10)
    score += (insight['quality_score'] / 10) * 0.20

    # 2. Category Preference (20%)
    # User's historical preference for this category type
    category = insight['category']
    category_likes = user_prefs['liked_categories'].get(category, 0)
    max_category_likes = max(user_prefs['liked_categories'].values() or [1])
    category_weight = category_likes / max_category_likes
    score += category_weight * 0.20

    # 3. Source Trust (15%)
    # User's historical trust in this source domain
    source_domain = insight['source_domain']
    source_saves = user_prefs['saved_sources'].get(source_domain, 0)
    max_source_saves = max(user_prefs['saved_sources'].values() or [1])
    source_weight = source_saves / max_source_saves
    score += source_weight * 0.15

    # 4. Topic Match (varies by feed type)
    user_topics = get_user_topics(user_id)
    if insight['topic'] in user_topics:
        # Following feed: Big boost
        score += 1.0
    else:
        # For You feed: Topic similarity
        topic_affinity = user_prefs['topic_affinity'].get(insight['topic'], 0)
        score += topic_affinity * 0.30

    # 5. Social Proof (15%)
    # Global engagement from all users
    score += insight['engagement_score'] * 0.15

    # 6. Freshness (20%)
    # Decay over 30 days
    days_old = (datetime.now() - insight['created_at']).days
    freshness = max(0, 1 - (days_old / 30))
    score += freshness * 0.20

    # 7. Diversity Penalty (-30%)
    # Don't show same topic back-to-back
    last_topic = get_last_shown_topic(user_id)
    if insight['topic'] == last_topic:
        score -= 0.30

    return score
```

### For You: Predicted Engagement

```python
def predict_engagement(user_id: str, insight: dict) -> float:
    """
    Predict likelihood user will engage with this insight
    Used for For You feed discovery
    """
    score = calculate_feed_score(user_id, insight)

    # Additional discovery factors

    # 1. Topic Similarity
    # How similar is this topic to what user already follows?
    user_topics = get_user_topics(user_id)
    similarities = [
        calculate_topic_similarity(insight['topic'], followed_topic)
        for followed_topic in user_topics
    ]
    max_similarity = max(similarities) if similarities else 0
    score += max_similarity * 0.25

    # 2. Collaborative Filtering
    # Users similar to you also liked this
    similar_users = find_similar_users(user_id)
    collab_score = 0
    for similar_user in similar_users[:10]:
        if has_engaged(similar_user, insight['id']):
            collab_score += 0.1
    score += min(collab_score, 0.5)

    # 3. Trending Bonus
    # Recently popular insights get boost
    recent_engagement = get_recent_engagement_count(insight['id'], days=7)
    if recent_engagement > 10:
        score += 0.2

    return score
```

---

## 📱 Mobile UI Changes

### Component Structure

```tsx
// New unified feed component
<FeedTabs>
  <Tab name="Following">
    <InfiniteScrollFeed
      endpoint="/api/feed/following"
      renderItem={InsightCard}
    />
  </Tab>

  <Tab name="For You">
    <InfiniteScrollFeed
      endpoint="/api/feed/for-you"
      renderItem={InsightCard}
    />
  </Tab>
</FeedTabs>

// Insight card with topic tag
<InsightCard insight={insight}>
  <TopicTag>{insight.topic}</TopicTag>  {/* NEW */}
  <CategoryBadge>{insight.category}</CategoryBadge>
  <InsightText>{insight.text}</InsightText>
  <SourceLink>{insight.source_domain}</SourceLink>
  <Actions>
    <LikeButton />
    <SaveButton />
    <DismissButton />
  </Actions>
</InsightCard>
```

### Screen Layout

```
┌─────────────────────────────────┐
│  Feed Focus                  ⚙️ │
├─────────────────────────────────┤
│                                 │
│  [ Following ]  [ For You ]     │  ← NEW: Two tabs
│   ▔▔▔▔▔▔▔▔▔                   │
│                                 │
│  ┌───────────────────────────┐ │
│  │ #AI agents            💡   │ │  ← Topic tag (NEW)
│  │ CASE STUDY                │ │
│  │                           │ │
│  │ Duolingo grew 40M → 100M  │ │
│  │ users by making mascot    │ │
│  │ "unhinged" on TikTok...   │ │
│  │                           │ │
│  │ 🔗 anthropic.com          │ │
│  │ ♥ 💾 ✕                    │ │
│  └───────────────────────────┘ │
│                                 │
│  ┌───────────────────────────┐ │
│  │ #Value Investing      📊   │ │  ← Different topic
│  │ PLAYBOOK                  │ │     (blended in feed!)
│  │                           │ │
│  │ Buffett's Bank of America │ │
│  │ structure...              │ │
│  └───────────────────────────┘ │
│                                 │
│         ⋮                       │
│    (infinite scroll)            │
│         ⋮                       │
│                                 │
└─────────────────────────────────┘
```

### Mobile Implementation Files

#### 1. Update InsightFeed.tsx
```typescript
// src/screens/InsightFeed.tsx
import { useState } from 'react';
import { Tabs } from '../components/Tabs';
import { InfiniteScrollFeed } from '../components/InfiniteScrollFeed';

export function InsightFeed() {
  const [activeTab, setActiveTab] = useState<'following' | 'for-you'>('following');

  return (
    <View>
      <Tabs active={activeTab} onChange={setActiveTab}>
        <Tab value="following" label="Following" />
        <Tab value="for-you" label="For You" />
      </Tabs>

      {activeTab === 'following' && (
        <InfiniteScrollFeed endpoint="/api/feed/following" />
      )}

      {activeTab === 'for-you' && (
        <InfiniteScrollFeed endpoint="/api/feed/for-you" />
      )}
    </View>
  );
}
```

#### 2. Create InfiniteScrollFeed.tsx
```typescript
// src/components/InfiniteScrollFeed.tsx
import { useState, useEffect } from 'react';
import { FlatList, RefreshControl } from 'react-native';
import { InsightCard } from './InsightCard';
import { api } from '../services/api';

export function InfiniteScrollFeed({ endpoint }: { endpoint: string }) {
  const [insights, setInsights] = useState([]);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(true);

  const loadInsights = async (refresh = false) => {
    if (loading || (!hasMore && !refresh)) return;

    setLoading(true);
    const currentOffset = refresh ? 0 : offset;

    try {
      const response = await api.get(endpoint, {
        params: { limit: 30, offset: currentOffset }
      });

      const newInsights = response.data;

      if (refresh) {
        setInsights(newInsights);
        setOffset(30);
      } else {
        setInsights([...insights, ...newInsights]);
        setOffset(currentOffset + 30);
      }

      setHasMore(newInsights.length === 30);
    } catch (error) {
      console.error('Failed to load insights:', error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadInsights(true);
  }, [endpoint]);

  const onRefresh = () => {
    setRefreshing(true);
    loadInsights(true);
  };

  const onEndReached = () => {
    loadInsights(false);
  };

  return (
    <FlatList
      data={insights}
      renderItem={({ item }) => <InsightCard insight={item} />}
      keyExtractor={(item) => item.id}
      onEndReached={onEndReached}
      onEndReachedThreshold={0.5}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
      }
    />
  );
}
```

#### 3. Update InsightCard.tsx
```typescript
// src/components/InsightCard.tsx (add topic tag)
export function InsightCard({ insight }: { insight: Insight }) {
  return (
    <View style={styles.card}>
      {/* NEW: Topic tag */}
      <View style={styles.header}>
        <Text style={styles.topicTag}>#{insight.topic}</Text>
        <Text style={styles.category}>{insight.category}</Text>
      </View>

      <Text style={styles.text}>{insight.text}</Text>

      <Text style={styles.source}>{insight.source_domain}</Text>

      <View style={styles.actions}>
        <LikeButton insightId={insight.id} />
        <SaveButton insightId={insight.id} />
        <DismissButton insightId={insight.id} />
      </View>
    </View>
  );
}
```

---

## 🔄 Content Strategy

### Initial Pool (Week 1-2)

**Goal:** 1,000 insights across 10 starter topics

```
Topics to populate:
├─ AI agents (100 insights)
├─ Value investing (100 insights)
├─ Gen Z consumer (100 insights)
├─ Startup fundraising (100 insights)
├─ Remote work (100 insights)
├─ Product management (100 insights)
├─ Marketing strategy (100 insights)
├─ SaaS metrics (100 insights)
├─ Creator economy (100 insights)
└─ College football (100 insights)

Cost: 10 topics × $0.12 = $1.20
Time: Run in parallel (2-3 days)
```

### Ongoing Maintenance

**Daily Refresh:** 5-10 insights/day distributed across ALL topics

```python
# Weekly rotation schedule
REFRESH_SCHEDULE = {
    'monday': ['AI agents', 'Value investing'],
    'tuesday': ['Startup fundraising', 'Remote work'],
    'wednesday': ['Gen Z consumer', 'Product management'],
    'thursday': ['Marketing strategy', 'SaaS metrics'],
    'friday': ['Creator economy', 'College football'],
}

# Daily extraction
def daily_refresh():
    today = datetime.now().strftime('%A').lower()
    topics_to_refresh = REFRESH_SCHEDULE[today]

    for topic in topics_to_refresh:
        extract_insights(topic, num_insights=5)

    # Cost: 5 insights × 2 topics × $0.01 = $0.10/day
    # Total: $3/month
```

### Smart Allocation (As You Scale)

```python
def get_refresh_priority():
    """
    Allocate refresh budget based on active usage
    """
    topics = db.get_all_topics()

    for topic in topics:
        # Count daily active users following this topic
        dau = db.count_topic_dau(topic, days=1)

        if dau >= 20:
            topic.refresh_frequency = 'daily'
            topic.insights_per_refresh = 5
        elif dau >= 5:
            topic.refresh_frequency = '2x_week'
            topic.insights_per_refresh = 3
        elif dau >= 1:
            topic.refresh_frequency = 'weekly'
            topic.insights_per_refresh = 2
        else:
            topic.refresh_frequency = 'paused'
            topic.insights_per_refresh = 0

    return topics
```

**Result:** Content budget automatically scales with usage

---

## 📈 Success Metrics

### Track These KPIs

```python
# Engagement metrics
def calculate_feed_health():
    return {
        # Per-user metrics
        'avg_session_length': ...,  # Time spent per session
        'insights_per_session': ...,  # How many insights viewed
        'scroll_depth': ...,  # How far down feed they scroll
        'engagement_rate': ...,  # % of insights liked/saved

        # Feed quality
        'following_exhaustion_rate': ...,  # % who run out of Following content
        'for_you_click_rate': ...,  # % who try For You tab
        'topic_discovery_rate': ...,  # % who add new topics from For You

        # Retention
        'day_1_retention': ...,
        'day_7_retention': ...,
        'day_30_retention': ...,
    }
```

### Success Targets

```
Week 1 (MVP):
✅ Following feed works
✅ For You feed works
✅ Infinite scroll works
✅ Topic tags display

Week 2 (Polish):
✅ Algorithm ranks intelligently
✅ Users can scroll 100+ insights
✅ Performance optimized

Week 3 (Growth):
✅ Avg session length > 5 min
✅ Insights per session > 15
✅ Topic discovery rate > 20%
✅ Day 7 retention > 40%
```

---

## 🚀 Implementation Timeline

### Week 1: Core Infrastructure (5 days)

#### Day 1: Database Migration
- [ ] Create new tables (insights, user_topics, user_engagement, user_preferences)
- [ ] Migrate existing insights to new schema
- [ ] Add indexes for performance
- [ ] Test queries

#### Day 2: Backend API
- [ ] Build `/api/feed/following` endpoint
- [ ] Build `/api/feed/for-you` endpoint
- [ ] Implement basic scoring algorithm
- [ ] Add engagement tracking endpoint
- [ ] Add follow/unfollow topic endpoints

#### Day 3: Scoring Algorithm
- [ ] Implement `calculate_feed_score()`
- [ ] Implement `predict_engagement()`
- [ ] Add diversity logic (no back-to-back same topic)
- [ ] Test ranking quality

#### Day 4: Mobile UI - Part 1
- [ ] Create tabs component (Following / For You)
- [ ] Build infinite scroll component
- [ ] Update InsightCard with topic tags
- [ ] Wire up API endpoints

#### Day 5: Mobile UI - Part 2
- [ ] Polish animations and transitions
- [ ] Add loading states
- [ ] Add pull-to-refresh
- [ ] Test on device

### Week 2: Algorithm & Polish (3-4 days)

#### Day 6: User Preferences
- [ ] Build preference calculation (liked categories, saved sources)
- [ ] Create background job to update preferences
- [ ] Add collaborative filtering logic
- [ ] Test personalization

#### Day 7: For You Intelligence
- [ ] Topic similarity matching
- [ ] Trending insights detection
- [ ] Similar user recommendations
- [ ] Test discovery quality

#### Day 8: Performance
- [ ] Add caching for feed generation
- [ ] Optimize database queries
- [ ] Precompute scores where possible
- [ ] Load test with 1000 insights

#### Day 9 (Optional): Analytics
- [ ] Add event tracking (views, scrolls, time spent)
- [ ] Build analytics dashboard
- [ ] Set up A/B testing framework

### Week 3: Content & Launch (2-3 days)

#### Day 10: Initial Content Pool
- [ ] Run extraction for 10 starter topics (100 each)
- [ ] Verify quality of extracted insights
- [ ] Set up daily refresh cron job

#### Day 11: Beta Testing
- [ ] Deploy to beta users
- [ ] Collect feedback
- [ ] Monitor metrics

#### Day 12: Iterate
- [ ] Fix bugs from feedback
- [ ] Tune algorithm weights
- [ ] Improve UI based on usage

---

## 🔧 Technical Details

### Backend: FastAPI Changes

```python
# backend/main.py - Add new routes

@app.get("/api/feed/following")
async def get_following_feed(
    user_id: str = Header(None, alias="X-User-ID"),
    limit: int = 30,
    offset: int = 0
):
    """Unified Following feed"""
    feed_service = FeedService()
    return feed_service.generate_following_feed(user_id, limit, offset)

@app.get("/api/feed/for-you")
async def get_for_you_feed(
    user_id: str = Header(None, alias="X-User-ID"),
    limit: int = 30,
    offset: int = 0
):
    """Algorithmic For You feed"""
    feed_service = FeedService()
    return feed_service.generate_for_you_feed(user_id, limit, offset)

@app.post("/api/topics/follow")
async def follow_topic(
    user_id: str = Header(None, alias="X-User-ID"),
    topic: str = Body(...)
):
    """Add topic to user's following"""
    db.add_user_topic(user_id, topic)
    return {"status": "following", "topic": topic}
```

### Backend: Feed Service

```python
# backend/services/feed_service.py

class FeedService:
    def __init__(self):
        self.db = get_database()
        self.scorer = InsightScorer()

    def generate_following_feed(
        self,
        user_id: str,
        limit: int = 30,
        offset: int = 0
    ) -> List[dict]:
        """
        Generate Following feed - insights from user's topics
        """
        # Get user's followed topics
        topics = self.db.get_user_topics(user_id)

        if not topics:
            return []

        # Get all insights from these topics
        insights = self.db.get_insights_by_topics(topics)

        # Filter out seen insights
        seen_ids = self.db.get_seen_insight_ids(user_id)
        unseen = [i for i in insights if i['id'] not in seen_ids]

        # Score each insight
        for insight in unseen:
            insight['score'] = self.scorer.calculate_feed_score(
                user_id,
                insight,
                feed_type='following'
            )

        # Sort by score
        ranked = sorted(unseen, key=lambda x: x['score'], reverse=True)

        # Paginate
        result = ranked[offset:offset+limit]

        # Mark as viewed (async)
        self._mark_viewed_async(user_id, [i['id'] for i in result])

        return result

    def generate_for_you_feed(
        self,
        user_id: str,
        limit: int = 30,
        offset: int = 0
    ) -> List[dict]:
        """
        Generate For You feed - algorithmic recommendations
        """
        # Get ALL insights
        all_insights = self.db.get_all_insights(is_archived=False)

        # Filter out seen
        seen_ids = self.db.get_seen_insight_ids(user_id)
        unseen = [i for i in all_insights if i['id'] not in seen_ids]

        # Predict engagement for each
        for insight in unseen:
            insight['predicted_score'] = self.scorer.predict_engagement(
                user_id,
                insight
            )

        # Sort by prediction
        ranked = sorted(unseen, key=lambda x: x['predicted_score'], reverse=True)

        # Paginate
        result = ranked[offset:offset+limit]

        # Mark as viewed (async)
        self._mark_viewed_async(user_id, [i['id'] for i in result])

        return result
```

### Backend: Scorer Class

```python
# backend/services/scorer.py

class InsightScorer:
    def calculate_feed_score(
        self,
        user_id: str,
        insight: dict,
        feed_type: str = 'following'
    ) -> float:
        """Calculate personalized score"""
        score = 0.0

        # Get user preferences
        prefs = self.db.get_user_preferences(user_id)
        user_topics = self.db.get_user_topics(user_id)

        # 1. Base quality (20%)
        score += (insight['quality_score'] / 10) * 0.20

        # 2. Category preference (20%)
        category_weight = self._calculate_category_weight(
            insight['category'],
            prefs
        )
        score += category_weight * 0.20

        # 3. Source trust (15%)
        source_weight = self._calculate_source_weight(
            insight['source_domain'],
            prefs
        )
        score += source_weight * 0.15

        # 4. Topic match (varies)
        if insight['topic'] in user_topics:
            score += 1.0  # Big boost for Following feed
        else:
            # For You feed: Use topic affinity
            affinity = prefs.get('topic_affinity', {}).get(insight['topic'], 0)
            score += affinity * 0.30

        # 5. Social proof (15%)
        score += insight['engagement_score'] * 0.15

        # 6. Freshness (20%)
        days_old = (datetime.now() - insight['created_at']).days
        freshness = max(0, 1 - (days_old / 30))
        score += freshness * 0.20

        # 7. Diversity penalty
        last_topic = self.db.get_last_shown_topic(user_id)
        if insight['topic'] == last_topic:
            score -= 0.30

        return score

    def predict_engagement(self, user_id: str, insight: dict) -> float:
        """Predict engagement for For You feed"""
        base_score = self.calculate_feed_score(user_id, insight, 'for_you')

        # Topic similarity to followed topics
        user_topics = self.db.get_user_topics(user_id)
        max_similarity = 0
        for followed_topic in user_topics:
            sim = self._calculate_topic_similarity(
                insight['topic'],
                followed_topic
            )
            max_similarity = max(max_similarity, sim)

        base_score += max_similarity * 0.25

        # Collaborative filtering
        similar_users = self._find_similar_users(user_id, limit=10)
        collab_score = 0
        for similar_user in similar_users:
            if self.db.has_engaged(similar_user, insight['id']):
                collab_score += 0.1
        base_score += min(collab_score, 0.5)

        # Trending bonus
        recent_engagement = self.db.get_engagement_count(
            insight['id'],
            days=7
        )
        if recent_engagement > 10:
            base_score += 0.2

        return base_score
```

---

## 🎯 Migration Path

### Phase 1: Backend Only (Week 1 Days 1-3)
- Deploy new database tables alongside old ones
- Deploy new API endpoints (don't remove old ones yet)
- Test with Postman/curl
- No mobile changes yet

### Phase 2: Mobile Beta (Week 1 Days 4-5)
- Update mobile app with new UI
- Release to TestFlight beta only
- Keep production app on old feed for now
- Collect feedback

### Phase 3: Full Rollout (Week 2)
- Fix bugs from beta
- Deploy to production
- Monitor metrics closely
- Remove old feed code after 1 week if successful

### Rollback Plan
If unified feed doesn't work:
- Old API endpoints still exist
- Old mobile build still available
- Can revert in < 1 hour

---

## 📊 Cost Analysis

### Before (Per-Topic Model)
```
100 users, 5 topics each:
- Need content per user per topic
- 5 topics × 10 insights/day = 50 insights/day
- Cost: $0.50/day = $15/month
- Scales linearly with users ❌
```

### After (Unified Feed Model)
```
100 users, global pool:
- 1,000 insights across 10 topics
- 10 new insights/day distributed
- Cost: $0.10/day = $3/month
- Scales with content pool, not users ✅

10,000 users, global pool:
- 5,000 insights across 50 topics
- 50 new insights/day distributed
- Cost: $0.50/day = $15/month
- 100x users, 5x cost ✅
```

---

## ✅ Success Criteria

### Week 1: Technical Success
- [ ] Following feed loads in < 2s
- [ ] For You feed loads in < 2s
- [ ] Infinite scroll works smoothly
- [ ] Can scroll 100+ insights without lag
- [ ] Topic tags display correctly

### Week 2: Engagement Success
- [ ] Avg session length > 5 minutes
- [ ] Insights per session > 15
- [ ] Scroll depth > 50 insights
- [ ] Engagement rate > 10% (like/save)

### Week 3: Discovery Success
- [ ] 20%+ users try For You tab
- [ ] 10%+ users add new topic from For You
- [ ] Day 7 retention > 40%
- [ ] Day 30 retention > 20%

---

## 🚨 Risks & Mitigation

### Risk 1: Users Exhaust Following Feed
**Mitigation:**
- Always have 300+ insights per topic
- Show For You suggestions when Following runs low
- Add "Discover More Topics" CTA

### Risk 2: Algorithm Doesn't Personalize Well
**Mitigation:**
- Start with simple quality-based ranking
- Gradually add personalization as data accumulates
- A/B test algorithm changes

### Risk 3: For You Doesn't Get Engagement
**Mitigation:**
- Make it discoverable (prominent tab)
- Show notification badges for trending insights
- Pre-populate with high-quality content

### Risk 4: Performance Degrades at Scale
**Mitigation:**
- Cache feed results (5 min TTL)
- Precompute scores nightly
- Use pagination aggressively

---

## 🎓 Key Learnings from Original Design

### What We Got Wrong
1. **Per-topic feeds** → User exhausts content, leaves
2. **Equal content per topic** → Wastes resources on inactive topics
3. **No discovery mechanism** → Users stuck in their bubble
4. **Separate sections** → Siloed experience, no flow

### What We Got Right
1. **Quality extraction** → Keep this
2. **Topic-based organization** → Still useful (as tags)
3. **Engagement tracking** → Essential for algorithm
4. **Clean UI** → Maintain simplicity

---

## 📚 References & Inspiration

**Twitter/X:**
- Following vs For You tabs
- Unified timeline
- Topic tags on tweets
- Engagement-based ranking

**TikTok:**
- Infinite scroll
- Algorithmic "For You"
- Never runs out of content
- Highly addictive UX

**Instagram:**
- Following vs Explore
- Interest-based discovery
- Like/Save signals
- Clean card-based UI

---

## 🎬 Next Steps

1. **Review this plan** with team/stakeholders
2. **Set up dev environment** for new feed system
3. **Start Week 1 Day 1:** Database migration
4. **Ship MVP in 2 weeks** 🚀

---

## 📞 Questions to Resolve

Before starting implementation:

1. **Authentication:** How do we identify users? Device ID? Login?
2. **Content moderation:** Do we need manual review before publishing?
3. **Topic expansion:** Who decides new topics? User requests? Data-driven?
4. **Monetization:** Sponsored insights? Premium topics? Free for now?
5. **Analytics:** What tool? Mixpanel? Amplitude? Custom?

---

**This is the blueprint. Time to build.** 🚀
