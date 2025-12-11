"""Extraction service that integrates queue with extraction pipeline."""

import asyncio
import os
import sys
from typing import Dict, Any

from automation.topic_handler import process_topic
from backend.extraction_queue import ExtractionQueue
from backend.utils.logger import setup_logger

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

logger = setup_logger(__name__)


async def run_extraction(
    topic: str,
    user_id: str,
    rate_limit_delay: float = 1.0,
    progress_callback=None
) -> Dict[str, Any]:
    """
    Run extraction for a topic with rate limiting and progress tracking.

    Args:
        topic: Topic to extract
        user_id: User who requested extraction
        rate_limit_delay: Delay between API calls in seconds
        progress_callback: Optional callback for progress updates

    Returns:
        Dict with extraction results
    """
    try:
        logger.info(f"Starting extraction for topic '{topic}' (user: {user_id})")

        result = await process_topic(
            user_topic=topic,
            rate_limit_delay=rate_limit_delay,
            progress_callback=progress_callback
        )

        logger.info(
            f"Extraction complete: {result.get('insights_count', 0)} insights "
            f"from {result.get('sources_count', 0)} sources"
        )

        return {
            "insight_count": result.get('insights_count', 0),
            "sources_processed": result.get('sources_count', 0)
        }

    except Exception as e:
        logger.error(f"Extraction failed for '{topic}': {e}")
        raise


def create_extraction_function(queue: ExtractionQueue):
    """
    Create extraction function with progress tracking for queue.

    Args:
        queue: ExtractionQueue instance

    Returns:
        Extraction function that can be passed to queue
    """
    def extraction_wrapper(topic: str, user_id: str) -> Dict[str, Any]:
        """
        Wrapper that runs async extraction in sync context.

        Args:
            topic: Topic to extract
            user_id: User who requested extraction

        Returns:
            Dict with extraction results
        """
        # Get job_id from active_jobs
        job_id = None
        with queue.active_jobs_lock:
            job_id = queue.active_jobs.get(topic)

        # Create progress callback
        def progress_callback(sources_processed: int):
            if job_id:
                queue.update_progress(job_id, sources_processed)

        # Run async extraction in event loop
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(
                run_extraction(topic, user_id, progress_callback=progress_callback)
            )
            loop.close()
            return result
        except Exception as e:
            logger.error(f"Extraction wrapper error: {e}")
            raise

    return extraction_wrapper
