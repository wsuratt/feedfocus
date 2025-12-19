"""
Feed Service: Unified feed generation with Following and For You

This service handles:
- Following feed: Insights from user's followed topics
- For You feed: Algorithmic recommendations
- Personalized ranking
- Engagement tracking
"""

import sqlite3
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set
import uuid
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "insights.db")


class FeedService:
    """Main feed generation service"""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.scorer = InsightScorer(db_path)

    def get_db_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def generate_following_feed(
        self,
        user_id: str,
        limit: int = 30,
        offset: int = 0
    ) -> List[Dict]:
        """
        Generate Following feed - insights from user's followed topics
        Optimized with database-level scoring and pagination

        Args:
            user_id: User identifier
            limit: Number of insights to return
            offset: Pagination offset

        Returns:
            List of ranked insights with metadata
        """
        conn = self.get_db_connection()
        cursor = conn.cursor()

        # Get user's followed topics
        cursor.execute("""
            SELECT topic FROM user_topics WHERE user_id = ?
        """, (user_id,))

        topics = [row['topic'] for row in cursor.fetchall()]

        if not topics:
            conn.close()
            return []

        # SQL-level scoring and pagination
        placeholders = ','.join('?' * len(topics))

        # Calculate days_old in SQL for freshness score
        query = f"""
        WITH scored_insights AS (
            SELECT
                i.id, i.topic, i.category, i.text, i.source_url, i.source_domain,
                i.quality_score, i.engagement_score, i.created_at,
                -- Calculate composite score in SQL
                (
                    (i.quality_score / 10.0 * 0.20) +  -- Base quality (20%)
                    (i.engagement_score * 0.15) +      -- Social proof (15%)
                    (1.0) +                              -- Topic match boost (100%)
                    (MAX(0, 1.0 - (julianday('now') - julianday(i.created_at)) / 30.0) * 0.20)  -- Freshness (20%)
                ) as score
            FROM insights i
            LEFT JOIN user_engagement ue ON
                i.id = ue.insight_id AND
                ue.user_id = ? AND
                ue.action = 'view'
            WHERE i.topic IN ({placeholders})
            AND i.is_archived = 0
            AND ue.insight_id IS NULL  -- Exclude seen insights
            GROUP BY i.id
            ORDER BY score DESC
            LIMIT ? OFFSET ?
        )
        SELECT * FROM scored_insights
        """

        params = [user_id] + topics + [limit, offset]
        cursor.execute(query, params)

        results = [dict(row) for row in cursor.fetchall()]

        # Mark as viewed
        if results:
            self._mark_viewed(user_id, [r['id'] for r in results], cursor)
            conn.commit()

        conn.close()
        return results

    def generate_for_you_feed(
        self,
        user_id: str,
        limit: int = 30,
        offset: int = 0,
        check_has_more: bool = False
    ) -> List[Dict] | tuple[List[Dict], bool]:
        """
        Generate For You feed using v2 algorithm with personalized scoring
        and diversity-aware composition.

        Args:
            user_id: User identifier
            limit: Number of insights to return
            offset: Pagination offset (not used in v2 - loads larger pool)
            check_has_more: If True, also return whether more insights exist

        Returns:
            Tuple of (insights list, has_more boolean) if check_has_more=True
            Just insights list if check_has_more=False (for backwards compatibility)
        """
        from backend.services.feed_builder import FeedBuilder

        conn = self.get_db_connection()
        cursor = conn.cursor()

        # Get candidate pool (200 insights, pre-filtered by SQL)
        # This is larger than requested to allow diversity filtering
        candidate_pool_size = min(200, (limit + 1) * 4)

        # Get viewed insights to exclude
        cursor.execute("""
            SELECT DISTINCT insight_id
            FROM user_engagement
            WHERE user_id = ? AND action = 'view'
        """, (user_id,))
        viewed_ids = [row['insight_id'] for row in cursor.fetchall()]

        # Build exclusion list for SQL
        if viewed_ids:
            placeholders = ','.join('?' * len(viewed_ids))
            exclusion_clause = f"AND i.id NOT IN ({placeholders})"
            params = viewed_ids + [candidate_pool_size]
        else:
            exclusion_clause = ""
            params = [candidate_pool_size]

        # Fetch candidate pool with basic quality filtering
        query = f"""
            SELECT
                i.id, i.topic, i.category, i.text, i.source_url, i.source_domain,
                i.quality_score, i.engagement_score, i.created_at, i.chroma_id
            FROM insights i
            WHERE i.is_archived = 0
              AND i.quality_score >= 5
              {exclusion_clause}
            ORDER BY i.quality_score DESC, i.created_at DESC
            LIMIT ?
        """

        cursor.execute(query, params)
        candidates = [dict(row) for row in cursor.fetchall()]

        conn.close()

        if not candidates:
            return ([], False) if check_has_more else []

        # Use FeedBuilder for personalized scoring and diversity
        # Request limit+1 to check if more exist
        builder = FeedBuilder(self.db_path)
        feed = builder.build_feed(user_id, candidates, length=limit + 1)

        # Check if more insights exist
        has_more = len(feed) > limit

        # Return only requested limit
        feed = feed[:limit]

        # Mark as viewed
        if feed:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            self._mark_viewed(user_id, [insight['id'] for insight in feed], cursor)
            conn.commit()
            conn.close()

        return (feed, has_more) if check_has_more else feed

    def record_engagement(
        self,
        user_id: str,
        insight_id: str,
        action: str
    ):
        """
        Record user engagement with an insight and update topic affinities

        Args:
            user_id: User identifier
            insight_id: Insight ID
            action: 'view', 'like', 'save', 'dismiss'
        """
        from backend.services.user_profile_service import UserProfileService

        conn = self.get_db_connection()
        cursor = conn.cursor()

        # Get insight topic for affinity updates
        cursor.execute("""
            SELECT topic FROM insights WHERE id = ?
        """, (insight_id,))
        row = cursor.fetchone()
        topic = row['topic'] if row else None

        # Track whether action is being added or removed
        affinity_delta = 0.0
        action_applied = False

        # For like/save actions, check if already exists and toggle
        if action in ['like', 'save']:
            cursor.execute("""
                SELECT id FROM user_engagement
                WHERE user_id = ? AND insight_id = ? AND action = ?
            """, (user_id, insight_id, action))
            existing = cursor.fetchone()

            if existing:
                # Already exists, remove it (toggle off)
                cursor.execute("""
                    DELETE FROM user_engagement
                    WHERE user_id = ? AND insight_id = ? AND action = ?
                """, (user_id, insight_id, action))
                action_applied = False
                # Negative delta when removing
                affinity_delta = -0.15 if action == 'like' else -0.12
            else:
                # Doesn't exist, add it (toggle on)
                engagement_id = str(uuid.uuid4())
                cursor.execute("""
                    INSERT INTO user_engagement (id, user_id, insight_id, action, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (engagement_id, user_id, insight_id, action, datetime.now().isoformat()))
                action_applied = True
                # Positive delta when adding
                affinity_delta = 0.15 if action == 'like' else 0.12
        else:
            # For view/dismiss, just insert
            engagement_id = str(uuid.uuid4())
            cursor.execute("""
                INSERT OR IGNORE INTO user_engagement (id, user_id, insight_id, action, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (engagement_id, user_id, insight_id, action, datetime.now().isoformat()))
            action_applied = True
            # Small negative for dismiss, no change for view
            affinity_delta = -0.10 if action == 'dismiss' else 0.0

        conn.commit()

        # Update insight engagement score
        self._update_insight_engagement_score(insight_id, cursor)
        conn.commit()

        # Update user profile counts
        profile_service = UserProfileService(self.db_path)
        if action == 'view':
            profile_service.increment_view_count(user_id)
        elif action == 'like' and action_applied:
            profile_service.increment_like_count(user_id)
        elif action == 'save' and action_applied:
            profile_service.increment_save_count(user_id)

        # Update topic affinity if we have a topic and delta
        if topic and affinity_delta != 0.0:
            profile_service.update_topic_affinity(user_id, topic, affinity_delta)

        conn.close()

    def follow_topic(self, user_id: str, topic: str):
        """Add topic to user's following list and create affinity"""
        from backend.services.user_profile_service import UserProfileService

        conn = self.get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR IGNORE INTO user_topics (user_id, topic, followed_at)
            VALUES (?, ?, ?)
        """, (user_id, topic, datetime.now().isoformat()))

        conn.commit()
        conn.close()

        # Create or boost topic affinity (0.70 for followed topics)
        profile_service = UserProfileService(self.db_path)
        conn = self.get_db_connection()
        cursor = conn.cursor()

        # Check if affinity exists
        cursor.execute("""
            SELECT affinity_score FROM user_topic_affinities
            WHERE user_id = ? AND topic = ?
        """, (user_id, topic))
        row = cursor.fetchone()

        if row:
            # Update existing affinity to at least 0.70
            current = row['affinity_score']
            if current < 0.70:
                delta = 0.70 - current
                profile_service.update_topic_affinity(user_id, topic, delta)
        else:
            # Create new affinity at 0.70
            profile_service.update_topic_affinity(user_id, topic, 0.20)  # +0.20 from default 0.5 = 0.70

        conn.close()

    def unfollow_topic(self, user_id: str, topic: str):
        """Remove topic from user's following list"""
        conn = self.get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            DELETE FROM user_topics WHERE user_id = ? AND topic = ?
        """, (user_id, topic))

        conn.commit()
        conn.close()

    def get_user_topics(self, user_id: str) -> List[str]:
        """Get list of topics user is following"""
        conn = self.get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT topic FROM user_topics WHERE user_id = ?
        """, (user_id,))

        topics = [row['topic'] for row in cursor.fetchall()]
        conn.close()

        return topics

    def get_user_liked_insights(self, user_id: str, limit: int = 50, offset: int = 0) -> List[Dict]:
        """Get user's liked insights"""
        conn = self.get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                i.id, i.topic, i.category, i.text, i.source_url, i.source_domain,
                i.quality_score, i.engagement_score, i.created_at,
                ue.created_at as liked_at
            FROM insights i
            INNER JOIN user_engagement ue ON i.id = ue.insight_id
            WHERE ue.user_id = ? AND ue.action = 'like'
            ORDER BY ue.created_at DESC
            LIMIT ? OFFSET ?
        """, (user_id, limit, offset))

        insights = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return insights

    def get_user_bookmarked_insights(self, user_id: str, limit: int = 50, offset: int = 0) -> List[Dict]:
        """Get user's bookmarked (saved) insights"""
        conn = self.get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                i.id, i.topic, i.category, i.text, i.source_url, i.source_domain,
                i.quality_score, i.engagement_score, i.created_at,
                ue.created_at as bookmarked_at
            FROM insights i
            INNER JOIN user_engagement ue ON i.id = ue.insight_id
            WHERE ue.user_id = ? AND ue.action = 'save'
            ORDER BY ue.created_at DESC
            LIMIT ? OFFSET ?
        """, (user_id, limit, offset))

        insights = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return insights

    def _get_seen_insight_ids(self, user_id: str, cursor) -> Set[str]:
        """Get set of insight IDs user has already seen"""
        cursor.execute("""
            SELECT DISTINCT insight_id
            FROM user_engagement
            WHERE user_id = ? AND action = 'view'
        """, (user_id,))

        return {row['insight_id'] for row in cursor.fetchall()}

    def _mark_viewed(self, user_id: str, insight_ids: List[str], cursor):
        """Mark insights as viewed by user"""
        for insight_id in insight_ids:
            engagement_id = str(uuid.uuid4())
            cursor.execute("""
                INSERT OR IGNORE INTO user_engagement (id, user_id, insight_id, action, created_at)
                VALUES (?, ?, ?, 'view', ?)
            """, (engagement_id, user_id, insight_id, datetime.now().isoformat()))

    def _update_insight_engagement_score(self, insight_id: str, cursor):
        """Recalculate engagement score for an insight"""
        cursor.execute("""
            SELECT
                COUNT(DISTINCT CASE WHEN action = 'view' THEN user_id END) as views,
                COUNT(DISTINCT CASE WHEN action = 'like' THEN user_id END) as likes,
                COUNT(DISTINCT CASE WHEN action = 'save' THEN user_id END) as saves
            FROM user_engagement
            WHERE insight_id = ?
        """, (insight_id,))

        row = cursor.fetchone()
        views = row['views']
        likes = row['likes']
        saves = row['saves']

        # Calculate engagement score: (likes + saves) / views
        if views > 0:
            engagement_score = min((likes + saves) / views, 1.0)
        else:
            engagement_score = 0.0

        # Update insight
        cursor.execute("""
            UPDATE insights
            SET engagement_score = ?, updated_at = ?
            WHERE id = ?
        """, (engagement_score, datetime.now().isoformat(), insight_id))


class InsightScorer:
    """Calculates personalized scores for insights"""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def calculate_feed_score(
        self,
        user_id: str,
        insight: Dict,
        feed_type: str = 'following',
        cursor = None
    ) -> float:
        """
        Calculate personalized score for an insight

        Args:
            user_id: User identifier
            insight: Insight dictionary
            feed_type: 'following' or 'for_you'
            cursor: Optional database cursor

        Returns:
            Score (0-10+)
        """
        score = 0.0

        close_conn = False
        if cursor is None:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            close_conn = True

        # Get user preferences
        prefs = self._get_user_preferences(user_id, cursor)
        user_topics = self._get_user_topics(user_id, cursor)

        # 1. Base Quality (20%)
        score += (insight['quality_score'] / 10) * 0.20

        # 2. Category Preference (20%)
        category_weight = self._calculate_category_weight(
            insight.get('category'),
            prefs
        )
        score += category_weight * 0.20

        # 3. Source Trust (15%)
        source_weight = self._calculate_source_weight(
            insight.get('source_domain'),
            prefs
        )
        score += source_weight * 0.15

        # 4. Topic Match (varies by feed type)
        if insight['topic'] in user_topics:
            # Following feed: Big boost
            score += 1.0
        else:
            # For You feed: Use topic affinity
            affinity = prefs.get('topic_affinity', {}).get(insight['topic'], 0)
            score += affinity * 0.30

        # 5. Social Proof (15%)
        score += insight.get('engagement_score', 0) * 0.15

        # 6. Freshness (20%)
        days_old = self._days_since_created(insight['created_at'])
        freshness = max(0, 1 - (days_old / 30))
        score += freshness * 0.20

        # 7. Diversity Penalty (avoid same topic back-to-back)
        last_topic = self._get_last_shown_topic(user_id, cursor)
        if insight['topic'] == last_topic:
            score -= 0.30

        if close_conn:
            cursor.connection.close()

        return max(0, score)

    def predict_engagement(
        self,
        user_id: str,
        insight: Dict,
        cursor = None
    ) -> float:
        """
        Predict likelihood of user engaging with insight (For You feed)

        Args:
            user_id: User identifier
            insight: Insight dictionary
            cursor: Optional database cursor

        Returns:
            Predicted engagement score
        """
        # Start with base score
        base_score = self.calculate_feed_score(user_id, insight, 'for_you', cursor)

        close_conn = False
        if cursor is None:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            close_conn = True

        # Additional discovery factors

        # 1. Topic Similarity to followed topics
        user_topics = self._get_user_topics(user_id, cursor)
        max_similarity = 0.0
        for followed_topic in user_topics:
            sim = self._calculate_topic_similarity(insight['topic'], followed_topic, cursor)
            max_similarity = max(max_similarity, sim)
        base_score += max_similarity * 0.25

        # 2. Trending Bonus (recently popular insights)
        recent_engagement = self._get_recent_engagement_count(insight['id'], cursor, days=7)
        if recent_engagement > 5:
            base_score += 0.2

        if close_conn:
            cursor.connection.close()

        return max(0, base_score)

    def _get_user_preferences(self, user_id: str, cursor) -> Dict:
        """Get user preferences (or create default)"""
        cursor.execute("""
            SELECT liked_categories, saved_sources, topic_affinity
            FROM user_preferences
            WHERE user_id = ?
        """, (user_id,))

        row = cursor.fetchone()

        if row:
            return {
                'liked_categories': json.loads(row['liked_categories'] or '{}'),
                'saved_sources': json.loads(row['saved_sources'] or '{}'),
                'topic_affinity': json.loads(row['topic_affinity'] or '{}')
            }
        else:
            # Return defaults
            return {
                'liked_categories': {},
                'saved_sources': {},
                'topic_affinity': {}
            }

    def _get_user_topics(self, user_id: str, cursor) -> List[str]:
        """Get topics user is following"""
        cursor.execute("""
            SELECT topic FROM user_topics WHERE user_id = ?
        """, (user_id,))

        return [row['topic'] for row in cursor.fetchall()]

    def _calculate_category_weight(self, category: Optional[str], prefs: Dict) -> float:
        """Calculate weight for a category based on user preferences"""
        if not category or not prefs.get('liked_categories'):
            return 0.5  # Default neutral

        liked_categories = prefs['liked_categories']
        category_likes = liked_categories.get(category, 0)
        max_likes = max(liked_categories.values()) if liked_categories else 1

        return category_likes / max_likes if max_likes > 0 else 0.5

    def _calculate_source_weight(self, source_domain: Optional[str], prefs: Dict) -> float:
        """Calculate weight for a source based on user trust"""
        if not source_domain or not prefs.get('saved_sources'):
            return 0.5  # Default neutral

        saved_sources = prefs['saved_sources']
        source_saves = saved_sources.get(source_domain, 0)
        max_saves = max(saved_sources.values()) if saved_sources else 1

        return source_saves / max_saves if max_saves > 0 else 0.5

    def _days_since_created(self, created_at: str) -> int:
        """Calculate days since insight was created"""
        try:
            created_date = datetime.fromisoformat(created_at)
            delta = datetime.now() - created_date
            return delta.days
        except Exception:
            return 0

    def _get_last_shown_topic(self, user_id: str, cursor) -> Optional[str]:
        """Get the topic of the last insight shown to user"""
        cursor.execute("""
            SELECT i.topic
            FROM user_engagement e
            JOIN insights i ON e.insight_id = i.id
            WHERE e.user_id = ? AND e.action = 'view'
            ORDER BY e.created_at DESC
            LIMIT 1
        """, (user_id,))

        row = cursor.fetchone()
        return row['topic'] if row else None

    def _calculate_topic_similarity(self, topic_a: str, topic_b: str, cursor) -> float:
        """Calculate similarity between two topics (0-1)"""
        if topic_a == topic_b:
            return 1.0

        # Check if we have precomputed similarity
        cursor.execute("""
            SELECT similarity_score
            FROM topic_similarity
            WHERE (topic_a = ? AND topic_b = ?) OR (topic_a = ? AND topic_b = ?)
        """, (topic_a, topic_b, topic_b, topic_a))

        row = cursor.fetchone()
        if row:
            return row['similarity_score']

        # Simple heuristic: word overlap (will improve later)
        words_a = set(topic_a.lower().split())
        words_b = set(topic_b.lower().split())

        if not words_a or not words_b:
            return 0.0

        overlap = len(words_a & words_b)
        total = len(words_a | words_b)

        return overlap / total if total > 0 else 0.0

    def _get_recent_engagement_count(self, insight_id: str, cursor, days: int = 7) -> int:
        """Count recent engagements (likes/saves) for an insight"""
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()

        cursor.execute("""
            SELECT COUNT(*)
            FROM user_engagement
            WHERE insight_id = ?
            AND action IN ('like', 'save')
            AND created_at >= ?
        """, (insight_id, cutoff_date))

        row = cursor.fetchone()
        return row[0] if row else 0
