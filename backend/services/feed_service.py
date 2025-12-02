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
            # User not following any topics yet
            conn.close()
            return []
        
        # Get all insights from these topics
        placeholders = ','.join('?' * len(topics))
        cursor.execute(f"""
            SELECT 
                id, topic, category, text, source_url, source_domain,
                quality_score, engagement_score, created_at
            FROM insights
            WHERE topic IN ({placeholders})
            AND is_archived = 0
        """, topics)
        
        insights = [dict(row) for row in cursor.fetchall()]
        
        # Filter out already seen
        seen_ids = self._get_seen_insight_ids(user_id, cursor)
        unseen = [i for i in insights if i['id'] not in seen_ids]
        
        # Score each insight
        for insight in unseen:
            insight['score'] = self.scorer.calculate_feed_score(
                user_id,
                insight,
                feed_type='following',
                cursor=cursor
            )
        
        # Sort by score
        ranked = sorted(unseen, key=lambda x: x['score'], reverse=True)
        
        # Paginate
        result = ranked[offset:offset + limit]
        
        # Mark as viewed (async - don't block response)
        if result:
            self._mark_viewed(user_id, [i['id'] for i in result], cursor)
            conn.commit()
        
        conn.close()
        return result
    
    def generate_for_you_feed(
        self,
        user_id: str,
        limit: int = 30,
        offset: int = 0
    ) -> List[Dict]:
        """
        Generate For You feed - algorithmic recommendations from ALL topics
        
        Args:
            user_id: User identifier
            limit: Number of insights to return
            offset: Pagination offset
            
        Returns:
            List of ranked insights with metadata
        """
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        # Get ALL insights (not just followed topics)
        cursor.execute("""
            SELECT 
                id, topic, category, text, source_url, source_domain,
                quality_score, engagement_score, created_at
            FROM insights
            WHERE is_archived = 0
        """)
        
        all_insights = [dict(row) for row in cursor.fetchall()]
        
        # Filter out already seen
        seen_ids = self._get_seen_insight_ids(user_id, cursor)
        unseen = [i for i in all_insights if i['id'] not in seen_ids]
        
        # Predict engagement for each
        for insight in unseen:
            insight['predicted_score'] = self.scorer.predict_engagement(
                user_id,
                insight,
                cursor=cursor
            )
        
        # Sort by prediction
        ranked = sorted(unseen, key=lambda x: x['predicted_score'], reverse=True)
        
        # Paginate
        result = ranked[offset:offset + limit]
        
        # Mark as viewed
        if result:
            self._mark_viewed(user_id, [i['id'] for i in result], cursor)
            conn.commit()
        
        conn.close()
        return result
    
    def record_engagement(
        self,
        user_id: str,
        insight_id: str,
        action: str
    ):
        """
        Record user engagement with an insight
        
        Args:
            user_id: User identifier
            insight_id: Insight ID
            action: 'view', 'like', 'save', 'dismiss'
        """
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        # Insert engagement record
        engagement_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO user_engagement (id, user_id, insight_id, action, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (engagement_id, user_id, insight_id, action, datetime.now().isoformat()))
        
        conn.commit()
        
        # Update engagement score asynchronously (simple version for now)
        self._update_insight_engagement_score(insight_id, cursor)
        conn.commit()
        
        conn.close()
    
    def follow_topic(self, user_id: str, topic: str):
        """Add topic to user's following list"""
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR IGNORE INTO user_topics (user_id, topic, followed_at)
            VALUES (?, ?, ?)
        """, (user_id, topic, datetime.now().isoformat()))
        
        conn.commit()
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
        max_similarity = 0
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
        except:
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
