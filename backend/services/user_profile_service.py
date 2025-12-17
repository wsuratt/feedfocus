"""User Profile Service for personalized feed algorithm"""
import sqlite3
from typing import Dict
from datetime import datetime
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(PROJECT_ROOT, "insights.db")


class UserProfile:
    """User profile data class"""
    def __init__(
        self,
        user_id: str,
        quality_preference: float = 0.7,
        freshness_preference: float = 0.5,
        avg_session_length: int = 15,
        total_views: int = 0,
        total_likes: int = 0,
        total_saves: int = 0
    ):
        self.user_id = user_id
        self.quality_preference = quality_preference
        self.freshness_preference = freshness_preference
        self.avg_session_length = avg_session_length
        self.total_views = total_views
        self.total_likes = total_likes
        self.total_saves = total_saves

    def is_new_user(self) -> bool:
        """Check if user is new (< 50 total views)"""
        return self.total_views < 50


class UserProfileService:
    """Service for managing user profiles and topic affinities"""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path

    def get_or_create_profile(self, user_id: str) -> UserProfile:
        """Get user profile or create if doesn't exist"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT user_id, quality_preference, freshness_preference,
                   avg_session_length, total_views, total_likes, total_saves
            FROM user_profiles
            WHERE user_id = ?
        """, (user_id,))

        row = cursor.fetchone()

        if row:
            conn.close()
            return UserProfile(
                user_id=row[0],
                quality_preference=row[1],
                freshness_preference=row[2],
                avg_session_length=row[3],
                total_views=row[4],
                total_likes=row[5],
                total_saves=row[6]
            )

        # Create new profile with defaults
        cursor.execute("""
            INSERT INTO user_profiles (user_id)
            VALUES (?)
        """, (user_id,))
        conn.commit()
        conn.close()

        return UserProfile(user_id=user_id)

    def get_topic_affinities(
        self,
        user_id: str,
        apply_decay: bool = True
    ) -> Dict[str, float]:
        """
        Get topic affinities for user with optional time decay.

        Time decay formula: affinity * (0.95 ** weeks_since_last_engagement)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT topic, affinity_score, last_engagement_at
            FROM user_topic_affinities
            WHERE user_id = ?
        """, (user_id,))

        affinities = {}
        now = datetime.now()

        for row in cursor.fetchall():
            topic = row[0]
            base_affinity = row[1]
            last_engagement = row[2]

            if apply_decay and last_engagement:
                # Calculate weeks since last engagement
                last_dt = datetime.fromisoformat(last_engagement)
                weeks_since = (now - last_dt).days / 7.0

                # Apply exponential decay: 0.95 per week
                decayed_affinity = self.apply_time_decay(base_affinity, weeks_since)
                affinities[topic] = decayed_affinity
            else:
                affinities[topic] = base_affinity

        conn.close()
        return affinities

    def apply_time_decay(self, affinity: float, weeks_since: float) -> float:
        """
        Apply time decay to affinity score.
        affinity * (0.95 ** weeks_since_last_engagement)

        Examples:
        - 8 weeks: drops ~33% (0.95^8 ≈ 0.66)
        - 16 weeks: drops ~55% (0.95^16 ≈ 0.44)
        """
        decay_rate = 0.95
        return affinity * (decay_rate ** weeks_since)

    def update_topic_affinity(
        self,
        user_id: str,
        topic: str,
        delta: float
    ):
        """
        Update topic affinity by delta amount.
        Creates affinity if doesn't exist.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get current affinity
        cursor.execute("""
            SELECT affinity_score FROM user_topic_affinities
            WHERE user_id = ? AND topic = ?
        """, (user_id, topic))

        row = cursor.fetchone()

        if row:
            # Update existing affinity
            new_affinity = max(0.0, min(1.0, row[0] + delta))  # Clamp to [0, 1]
            cursor.execute("""
                UPDATE user_topic_affinities
                SET affinity_score = ?,
                    last_engagement_at = ?,
                    updated_at = ?
                WHERE user_id = ? AND topic = ?
            """, (new_affinity, datetime.now().isoformat(), datetime.now().isoformat(), user_id, topic))
        else:
            # Create new affinity
            initial_affinity = max(0.0, min(1.0, 0.5 + delta))  # Start at 0.5, apply delta
            cursor.execute("""
                INSERT INTO user_topic_affinities
                (user_id, topic, affinity_score, last_engagement_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, topic, initial_affinity, datetime.now().isoformat(), datetime.now().isoformat()))

        conn.commit()
        conn.close()

    def increment_view_count(self, user_id: str):
        """Increment total view count for user"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE user_profiles
            SET total_views = total_views + 1,
                updated_at = ?
            WHERE user_id = ?
        """, (datetime.now().isoformat(), user_id))

        conn.commit()
        conn.close()

    def increment_like_count(self, user_id: str):
        """Increment total like count for user"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE user_profiles
            SET total_likes = total_likes + 1,
                updated_at = ?
            WHERE user_id = ?
        """, (datetime.now().isoformat(), user_id))

        conn.commit()
        conn.close()

    def increment_save_count(self, user_id: str):
        """Increment total save count for user"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE user_profiles
            SET total_saves = total_saves + 1,
                updated_at = ?
            WHERE user_id = ?
        """, (datetime.now().isoformat(), user_id))

        conn.commit()
        conn.close()
