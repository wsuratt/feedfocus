"""Feed Builder for diversity-aware feed composition"""
import sqlite3
from typing import Dict, List, Optional, Set, Tuple
from backend.services.personalized_scorer import PersonalizedScorer
from backend.services.user_profile_service import UserProfileService
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(PROJECT_ROOT, "insights.db")

# Diversity rules configuration
DIVERSITY_RULES = {
    "max_same_topic_in_last_3": 2,
    "max_same_category_in_last_5": 3,
    "max_same_source_in_last_4": 1,  # Prevent source domain clustering
    "exploration_interval": 10,  # Every 10th item
    "near_duplicate_enabled": False,  # Disabled by default
    "near_duplicate_threshold": 0.92,
    "near_duplicate_lookback": 5,
}


class FeedContext:
    """Tracks feed composition state for diversity checks"""
    def __init__(self):
        self.recent_topics: List[str] = []
        self.recent_categories: List[str] = []
        self.recent_sources: List[str] = []  # Track source domains

    def add_to_recent(self, insight: Dict):
        self.recent_topics.append(insight.get('topic', ''))
        self.recent_categories.append(insight.get('category', ''))
        self.recent_sources.append(insight.get('source_domain', ''))

    def get_topic_penalty(self, topic: str) -> float:
        """Calculate penalty for topic repetition (-0.1 per occurrence in last 5)"""
        recent = self.recent_topics[-5:]
        return -0.1 * recent.count(topic)


class FeedBuilder:
    """
    Builds personalized feed with multi-layer diversity rules.

    Diversity layers:
    1. Topic diversity: Max 2 same topic in last 3 items
    2. Category diversity: Max 3 same category in last 5 items
    3. Source diversity: Max 1 same domain in last 4 items
    4. Content near-duplicate: Cosine similarity check (optional)
    """

    # Class-level cache for topic similarities (loaded once at startup)
    _topic_similarities: Optional[Dict[str, List[Tuple[str, float]]]] = None

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.scorer = PersonalizedScorer(db_path)
        self.profile_service = UserProfileService(db_path)

    @classmethod
    def get_topic_similarities(cls) -> Dict[str, List[Tuple[str, float]]]:
        """Load topic similarities once and cache in memory"""
        if cls._topic_similarities is None:
            cls._topic_similarities = cls._load_all_topic_similarities()
        return cls._topic_similarities

    @classmethod
    def _load_all_topic_similarities(cls) -> Dict[str, List[Tuple[str, float]]]:
        """
        Load entire topic similarity matrix into memory.
        Returns empty dict if table doesn't exist or is empty.
        """
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT topic_a, topic_b, similarity_score
                FROM topic_similarities
                ORDER BY topic_a, similarity_score DESC
            """)

            similarities: Dict[str, List[Tuple[str, float]]] = {}
            for topic_a, topic_b, score in cursor.fetchall():
                if topic_a not in similarities:
                    similarities[topic_a] = []
                similarities[topic_a].append((topic_b, score))

            conn.close()
            return similarities
        except Exception:
            # Table doesn't exist or is empty
            return {}

    def build_feed(
        self,
        user_id: str,
        candidates: List[Dict],
        length: int = 50
    ) -> List[Dict]:
        """
        Multi-stage feed construction with deduplication layers:

        1. **Insight-level dedup**: Already filtered in SQL
        2. **Batch load data**: User context (avoid N+1 queries)
        3. **Score**: Apply PersonalizedScorer to all candidates
        4. **Sort**: Order by predicted score
        5. **Select with diversity**: Apply topic/category/source diversity rules
        6. **Inject exploration**: Add discovery items every 10th position
        """

        # Get user context
        user_profile = self.profile_service.get_or_create_profile(user_id)
        user_affinities = self.profile_service.get_topic_affinities(user_id, apply_decay=True)
        topic_similarities = self.get_topic_similarities()

        # Score all candidates
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

        # Select with diversity constraints
        feed = []

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

            feed.append(insight)
            context.add_to_recent(insight)

            # Inject exploration every 10 items
            if len(feed) % DIVERSITY_RULES["exploration_interval"] == 0 and len(feed) < length:
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

    def _violates_topic_diversity(self, insight: Dict, context: FeedContext) -> bool:
        """Don't show same topic 2+ times in last 3 items"""
        recent_topics = context.recent_topics[-3:]
        max_allowed = DIVERSITY_RULES["max_same_topic_in_last_3"]
        return recent_topics.count(insight.get('topic', '')) >= max_allowed

    def _violates_category_diversity(self, insight: Dict, context: FeedContext) -> bool:
        """Don't show same category 3+ times in last 5 items"""
        recent_categories = context.recent_categories[-5:]
        max_allowed = DIVERSITY_RULES["max_same_category_in_last_5"]
        return recent_categories.count(insight.get('category', '')) >= max_allowed

    def _violates_source_diversity(self, insight: Dict, context: FeedContext) -> bool:
        """Don't show same source domain more than once in last 4 items"""
        recent_sources = context.recent_sources[-4:]
        max_allowed = DIVERSITY_RULES["max_same_source_in_last_4"]
        return recent_sources.count(insight.get('source_domain', '')) >= max_allowed

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
        topic_placeholders = ','.join('?' * len(user_topics)) if user_topics else "''"
        exclude_placeholders = ','.join('?' * len(exclude_ids)) if exclude_ids else "''"

        # Get random high-quality insight from unfamiliar topic
        query = """
            SELECT id, topic, category, text, source_url, source_domain,
                   quality_score, engagement_score, created_at, chroma_id
            FROM insights
            WHERE quality_score >= 7
              AND is_archived = 0
        """
        params: List[str] = []

        if user_topics:
            query += f" AND topic NOT IN ({topic_placeholders})"
            params.extend(user_topics)

        if exclude_ids:
            query += f" AND id NOT IN ({exclude_placeholders})"
            params.extend(exclude_ids)

        query += " ORDER BY RANDOM() LIMIT 1"

        try:
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
        except Exception as e:
            conn.close()
            print(f"Error getting exploration insight: {e}")

        return None
