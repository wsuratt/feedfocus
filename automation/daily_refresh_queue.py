"""
Daily refresh script using extraction queue.

Queries active topics with recent engagement and queues them
for background extraction with high priority (10).

Priority rationale:
- Daily refresh (priority 10): Benefits all users, refreshes popular content
- User-triggered (priority 1): Benefits single user, can wait

Can be run:
- Via cron: 0 2 * * * /path/to/python daily_refresh_queue.py
- Via systemd timer
- Manually for testing: python automation/daily_refresh_queue.py
"""

import sys
import os
import logging
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.utils.database import get_db_connection
from backend.extraction_queue import ExtractionQueue

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_active_topics(min_followers: int = 30, min_active_users: int = 3, limit: int = 20):
    """
    Get active topics with recent engagement for daily refresh.

    Args:
        min_followers: Minimum number of users following topic
        min_active_users: Minimum active users in last 7 days
        limit: Maximum number of topics to return

    Returns:
        List of tuples: (topic, followers, active_users)
    """
    query = """
    SELECT
        ut.topic,
        COUNT(DISTINCT ut.user_id) as followers,
        COUNT(DISTINCT ue.user_id) as active_users_7d
    FROM user_topics ut
    LEFT JOIN user_engagement ue
        ON ue.insight_id IN (
            SELECT id FROM insights WHERE topic = ut.topic
        )
        AND ue.created_at > datetime('now', '-7 days')
    WHERE ut.topic IN (
        SELECT DISTINCT topic FROM insights
    )
    GROUP BY ut.topic
    HAVING
        COUNT(DISTINCT ut.user_id) >= ? AND
        COUNT(DISTINCT ue.user_id) >= ?
    ORDER BY active_users_7d DESC, followers DESC
    LIMIT ?
    """

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, (min_followers, min_active_users, limit))
        return cursor.fetchall()


def daily_refresh():
    """
    Main daily refresh function.

    - Queries top 20 active topics
    - Queues them with low priority (1)
    - Logs results
    """
    logger.info("="*80)
    logger.info(f"DAILY REFRESH - {datetime.now().isoformat()}")
    logger.info("="*80)

    # Get active topics
    logger.info("Querying active topics...")
    try:
        topics = get_active_topics(
            min_followers=30,
            min_active_users=3,
            limit=20
        )
    except Exception as e:
        logger.error(f"Failed to query active topics: {e}")
        return

    if not topics:
        logger.warning("No active topics found matching criteria")
        return

    logger.info(f"Found {len(topics)} active topics for refresh")

    # Initialize extraction queue
    logger.info("Initializing extraction queue...")
    queue = ExtractionQueue(num_workers=2)

    # Queue each topic with high priority
    queued_count = 0
    failed_count = 0

    for topic, followers, active_users in topics:
        try:
            result = queue.add_job(
                topic=topic,
                user_id='system',  # System-triggered refresh
                priority=10  # High priority - benefits all users
            )

            logger.info(
                f"Queued: {topic} "
                f"(followers: {followers}, active: {active_users}, "
                f"job_id: {result['job_id'][:8]}...)"
            )
            queued_count += 1

        except Exception as e:
            logger.error(f"Failed to queue {topic}: {e}")
            failed_count += 1

    logger.info("="*80)
    logger.info(f"DAILY REFRESH QUEUING COMPLETE")
    logger.info(f"Queued: {queued_count}/{len(topics)}")
    logger.info(f"Failed: {failed_count}")
    logger.info(f"Workers will process these in background with priority 10")
    logger.info(f"Daily refresh jobs benefit all users and process before individual requests")
    logger.info("="*80)

    # Note: Don't stop the queue - let backend workers handle it
    # queue.stop()  # Comment out to let workers continue


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Daily refresh of active topics')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show topics without queueing')
    parser.add_argument('--limit', type=int, default=20,
                       help='Number of topics to refresh (default: 20)')
    parser.add_argument('--min-followers', type=int, default=30,
                       help='Minimum followers (default: 30)')
    parser.add_argument('--min-active', type=int, default=3,
                       help='Minimum active users in 7 days (default: 3)')

    args = parser.parse_args()

    if args.dry_run:
        logger.info("DRY RUN MODE - No jobs will be queued")
        topics = get_active_topics(
            min_followers=args.min_followers,
            min_active_users=args.min_active,
            limit=args.limit
        )

        logger.info(f"\nFound {len(topics)} topics that would be queued:\n")
        for i, (topic, followers, active_users) in enumerate(topics, 1):
            logger.info(
                f"{i:2d}. {topic:40s} "
                f"(followers: {followers:3d}, active: {active_users:2d})"
            )
        logger.info("\nRun without --dry-run to actually queue these topics")
    else:
        daily_refresh()
