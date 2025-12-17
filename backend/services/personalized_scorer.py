"""Personalized scoring for feed algorithm v2"""
from typing import Dict
from datetime import datetime
import random


# Scoring weights (tunable)
SCORING_WEIGHTS = {
    "quality_fit": 0.20,
    "topic_affinity": 0.30,
    "social_proof": 0.20,
    "freshness": 0.15,
    "exploration": 0.15,  # New users
}

EXPLORATION_RATES = {
    "new_user": 0.15,      # < 50 views
    "established": 0.03,   # >= 50 views
}


class PersonalizedScorer:
    """
    Multi-factor personalized scoring for insights.

    Components:
    - quality_fit: How well quality matches user preference
    - topic_affinity: Direct + similar topic affinities
    - social_proof: Engagement from other users
    - freshness: Recency with personalized decay
    - exploration: Random boost for discovery
    """

    def __init__(self, db_path: str = None):
        self.db_path = db_path

    def score_insight(
        self,
        insight: Dict,
        user_profile,
        user_affinities: Dict[str, float],
        topic_similarities: Dict[str, list] = None,
        context = None
    ) -> float:
        """
        Calculate composite score for an insight.

        Returns score in range 0-2+ (higher is better)
        """
        # 1. Quality fit (0-0.20)
        quality_fit = self._calculate_quality_fit(
            insight.get('quality_score', 0),
            user_profile.quality_preference
        )

        # 2. Topic affinity (0-0.30)
        topic_affinity = self._calculate_topic_affinity(
            insight.get('topic', ''),
            user_affinities,
            topic_similarities or {}
        )

        # 3. Social proof (0-0.20)
        social_proof = self._calculate_social_proof(
            insight.get('engagement_score', 0)
        )

        # 4. Freshness (0-0.15)
        freshness = self._calculate_freshness(
            insight.get('created_at', ''),
            user_profile.freshness_preference
        )

        # 5. Exploration (0-0.15 for new users, 0-0.03 for established)
        exploration = self._calculate_exploration(
            user_profile.is_new_user()
        )

        # 6. Diversity penalty (context-based, can be negative)
        diversity_penalty = 0
        if context:
            diversity_penalty = context.get_topic_penalty(insight.get('topic', ''))

        # Composite score
        score = (
            quality_fit * SCORING_WEIGHTS["quality_fit"] +
            topic_affinity * SCORING_WEIGHTS["topic_affinity"] +
            social_proof * SCORING_WEIGHTS["social_proof"] +
            freshness * SCORING_WEIGHTS["freshness"] +
            exploration * SCORING_WEIGHTS["exploration"] +
            diversity_penalty
        )

        return max(0, score)  # Ensure non-negative

    def _calculate_quality_fit(
        self,
        insight_quality: float,
        user_preference: float
    ) -> float:
        """
        Quality fit: 1.0 = perfect match, 0.0 = complete mismatch

        User preference 0.7 → prefers 7/10 content
        Insight quality 8/10 with preference 0.7 → slight mismatch

        Returns 0-1 where 1 = perfect match
        """
        normalized_quality = insight_quality / 10.0  # Normalize to 0-1
        fit = 1.0 - abs(normalized_quality - user_preference)
        return max(0, fit)

    def _calculate_topic_affinity(
        self,
        insight_topic: str,
        user_affinities: Dict[str, float],
        topic_similarities: Dict[str, list]
    ) -> float:
        """
        Topic affinity with fallback to similar topics.

        Direct affinity: user explicitly follows/engaged with this topic
        Similar affinity: user follows similar topics (discounted by 0.7)

        Returns 0-1
        """
        # Direct affinity
        direct = user_affinities.get(insight_topic, 0)
        if direct:
            return direct

        # Similar topic affinity (discounted)
        if topic_similarities and insight_topic in topic_similarities:
            similar_topics = topic_similarities[insight_topic]
            similar_scores = [
                user_affinities.get(sim_topic, 0) * sim_score * 0.7
                for sim_topic, sim_score in similar_topics
            ]
            return max(similar_scores) if similar_scores else 0

        return 0

    def _calculate_social_proof(self, engagement_score: float) -> float:
        """
        Social proof from other users' engagement.

        engagement_score is already normalized (likes + saves + shares)
        Returns 0-1
        """
        # engagement_score is typically 0-10, normalize to 0-1
        return min(1.0, engagement_score / 10.0)

    def _calculate_freshness(
        self,
        created_at: str,
        freshness_preference: float
    ) -> float:
        """
        Freshness with personalized decay.

        freshness_preference:
        - 1.0 = wants breaking news (steep decay)
        - 0.5 = balanced (moderate decay)
        - 0.0 = timeless content (no decay)

        Returns 0-1
        """
        try:
            created_dt = datetime.fromisoformat(created_at)
            now = datetime.now()
            age_days = (now - created_dt).days

            # Personalized decay window (days)
            decay_window = 30 * freshness_preference

            if decay_window == 0:
                return 1.0  # No decay for timeless content lovers

            # Linear decay over window
            freshness = max(0, 1.0 - (age_days / decay_window))
            return freshness

        except Exception:
            # If date parsing fails, assume recent
            return 0.8

    def _calculate_exploration(self, is_new_user: bool) -> float:
        """
        Random exploration boost for discovery.

        New users get more exploration to help them find interests.
        Established users get less (they already know what they like).

        Returns 0-0.15 for new users, 0-0.03 for established
        """
        rate = EXPLORATION_RATES["new_user"] if is_new_user else EXPLORATION_RATES["established"]
        return random.random() * rate
