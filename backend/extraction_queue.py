"""Background extraction queue with worker threads."""

import queue
import threading
import uuid
import json
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Callable
import sqlite3

from backend.utils.database import get_db_connection
from backend.utils.logger import setup_logger

logger = setup_logger(__name__)

MAX_RETRIES = 3
TIMEOUT_SECONDS = 900  # 15 minutes


class ExtractionQueue:
    """
    Thread-safe queue for background extraction jobs.

    Manages worker threads that process extraction jobs in priority order.
    Prevents duplicate jobs and tracks job status in database.
    """

    def __init__(self, num_workers: int = 2, extraction_fn: Optional[Callable] = None):
        """
        Initialize extraction queue with worker threads.

        Args:
            num_workers: Number of worker threads to spawn
            extraction_fn: Optional extraction function (for testing/future use)
        """
        self.num_workers = num_workers
        self.job_queue: queue.PriorityQueue = queue.PriorityQueue()
        self.shutdown_flag = threading.Event()
        self.active_jobs: Dict[str, str] = {}
        self.active_jobs_lock = threading.Lock()
        self.extraction_fn = extraction_fn
        self.job_timeouts: Dict[str, threading.Timer] = {}

        self.workers = []
        for i in range(num_workers):
            worker = threading.Thread(
                target=self._worker_loop,
                name=f"ExtractionWorker-{i}",
                daemon=True
            )
            worker.start()
            self.workers.append(worker)

        logger.info(f"ExtractionQueue initialized with {num_workers} workers")

    def recover_stale_jobs(self):
        """
        Recover jobs stuck in 'processing' state after backend restart.

        This handles the case where the backend crashes or restarts while
        jobs are in progress. Jobs that have been 'processing' for more than
        20 minutes are considered stale and will be re-queued.
        """
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()

                # Find jobs that were processing > 20 minutes ago (stale)
                cursor.execute("""
                    SELECT id, topic, user_id, priority
                    FROM extraction_jobs
                    WHERE status = 'processing'
                    AND updated_at < datetime('now', '-20 minutes')
                """)

                stale_jobs = cursor.fetchall()

                for job_row in stale_jobs:
                    job_id, topic, user_id, priority = job_row

                    # Reset to queued and re-add to queue
                    cursor.execute("""
                        UPDATE extraction_jobs
                        SET status = 'queued',
                            updated_at = ?
                        WHERE id = ?
                    """, (datetime.now().isoformat(), job_id))

                    # Add back to priority queue
                    self.job_queue.put((priority, job_id, topic, user_id))

                    # Track in active jobs
                    with self.active_jobs_lock:
                        self.active_jobs[topic] = job_id

                    logger.info(f"Recovered stale job: {topic} (id: {job_id})")

                conn.commit()

                if stale_jobs:
                    logger.info(f"Recovered {len(stale_jobs)} stale jobs from previous session")
                else:
                    logger.info("No stale jobs found - clean startup")

        except Exception as e:
            logger.error(f"Error recovering stale jobs: {e}")

    def add_job(
        self,
        topic: str,
        user_id: str,
        priority: int = 5
    ) -> Dict[str, Any]:
        """
        Add extraction job to queue.

        Args:
            topic: Topic to extract insights for
            user_id: User who requested extraction
            priority: Job priority (lower number = higher priority)

        Returns:
            Dict with job_id and status

        Raises:
            ValueError: If job already queued or processing
        """
        with self.active_jobs_lock:
            if topic in self.active_jobs:
                raise ValueError(f"Job already exists for topic: {topic}")

        job_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT id, status FROM extraction_jobs
                    WHERE topic = ? AND status IN ('queued', 'processing')
                """, (topic,))

                existing = cursor.fetchone()
                if existing:
                    raise ValueError(
                        f"Job already {existing[1]} for topic: {topic}"
                    )

                cursor.execute("""
                    INSERT INTO extraction_jobs (
                        id, topic, user_id, priority, status,
                        retry_count, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    job_id, topic, user_id, priority, 'queued',
                    0, now, now
                ))

                conn.commit()

        except sqlite3.IntegrityError as e:
            logger.error(f"Database error adding job: {e}")
            raise ValueError(f"Failed to add job: {e}")

        with self.active_jobs_lock:
            self.active_jobs[topic] = job_id

        self.job_queue.put((priority, job_id, topic, user_id))

        logger.info(f"Added job {job_id} for topic '{topic}' with priority {priority}")

        return {
            "job_id": job_id,
            "topic": topic,
            "status": "queued",
            "priority": priority
        }

    def get_job_status(self, topic: str) -> Optional[Dict[str, Any]]:
        """
        Get status of extraction job for topic.

        Args:
            topic: Topic to check status for

        Returns:
            Dict with job status or None if not found
        """
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT
                        id, topic, user_id, priority, status,
                        insight_count, error, retry_count,
                        sources_processed, extraction_duration_seconds,
                        created_at, updated_at
                    FROM extraction_jobs
                    WHERE topic = ?
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (topic,))

                row = cursor.fetchone()

                if not row:
                    return None

                return {
                    "job_id": row[0],
                    "topic": row[1],
                    "user_id": row[2],
                    "priority": row[3],
                    "status": row[4],
                    "insight_count": row[5],
                    "error": row[6],
                    "retry_count": row[7],
                    "sources_processed": row[8],
                    "extraction_duration_seconds": row[9],
                    "created_at": row[10],
                    "updated_at": row[11]
                }

        except Exception as e:
            logger.error(f"Error getting job status: {e}")
            return None

    def get_health_metrics(self) -> Dict[str, Any]:
        """
        Get queue health and status metrics.

        Returns:
            Dict with queue health information
        """
        with self.active_jobs_lock:
            queue_size = self.job_queue.qsize()
            jobs_processing = len(self.active_jobs)

        return {
            "workers_active": self.num_workers,
            "queue_size": queue_size,
            "jobs_processing": jobs_processing
        }

    def stop(self):
        """
        Gracefully shutdown queue and wait for workers to finish.
        """
        logger.info("Shutting down ExtractionQueue...")
        self.shutdown_flag.set()

        for _ in range(self.num_workers):
            self.job_queue.put((float('inf'), None, None, None))

        for worker in self.workers:
            worker.join(timeout=5.0)

        logger.info("ExtractionQueue shutdown complete")

    def _worker_loop(self):
        """
        Worker thread main loop.

        Continuously processes jobs from queue until shutdown.
        """
        worker_name = threading.current_thread().name
        logger.info(f"{worker_name} started")

        while not self.shutdown_flag.is_set():
            try:
                priority, job_id, topic, user_id = self.job_queue.get(timeout=1.0)

                if job_id is None:
                    break

                logger.info(f"{worker_name} processing job {job_id} for topic '{topic}'")

                self._process_job(job_id, topic, user_id)

                self.job_queue.task_done()

            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"{worker_name} unexpected error: {e}")
                if job_id and topic:
                    self._handle_job_failure(
                        job_id,
                        topic,
                        user_id,
                        str(e),
                        is_transient=False
                    )

        logger.info(f"{worker_name} stopped")

    def _process_job(self, job_id: str, topic: str, user_id: str):
        """
        Process extraction job with timeout protection.

        Args:
            job_id: Job identifier
            topic: Topic to extract
            user_id: User who requested extraction
        """
        start_time = time.time()
        timed_out = threading.Event()

        def timeout_handler():
            timed_out.set()
            logger.warning(f"Job {job_id} timed out after {TIMEOUT_SECONDS}s")

        timeout_timer = threading.Timer(TIMEOUT_SECONDS, timeout_handler)
        self.job_timeouts[job_id] = timeout_timer

        try:
            self._update_job_status(job_id, 'processing')
            self._set_estimated_completion(job_id, TIMEOUT_SECONDS)

            timeout_timer.start()

            if self.extraction_fn:
                result = self._run_extraction_with_progress(
                    job_id, topic, user_id, timed_out
                )
            else:
                time.sleep(0.1)
                result = {"insight_count": 0, "sources_processed": 0}

            if timed_out.is_set():
                self._handle_job_failure(
                    job_id,
                    topic,
                    user_id,
                    "Extraction timed out",
                    is_transient=True
                )
            else:
                duration = time.time() - start_time
                self._complete_job(job_id, topic, result, duration)

        except Exception as e:
            logger.error(f"Error processing job {job_id}: {e}")
            is_transient = self._is_transient_error(str(e))
            self._handle_job_failure(job_id, topic, user_id, str(e), is_transient)

        finally:
            timeout_timer.cancel()
            self.job_timeouts.pop(job_id, None)
            with self.active_jobs_lock:
                self.active_jobs.pop(topic, None)

    def _run_extraction_with_progress(
        self,
        job_id: str,
        topic: str,
        user_id: str,
        timed_out: threading.Event
    ) -> Dict[str, Any]:
        """
        Run extraction function with progress tracking.

        Args:
            job_id: Job identifier
            topic: Topic to extract
            user_id: User identifier
            timed_out: Event to check for timeout

        Returns:
            Dict with extraction results
        """
        try:
            result = self.extraction_fn(topic, user_id)
            return result
        except Exception:
            raise

    def _complete_job(
        self,
        job_id: str,
        topic: str,
        result: Dict[str, Any],
        duration: float
    ):
        """
        Mark job as complete and update stats.

        Args:
            job_id: Job identifier
            topic: Topic that was extracted
            result: Extraction results
            duration: Time taken in seconds
        """
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                now = datetime.now().isoformat()

                cursor.execute("""
                    UPDATE extraction_jobs
                    SET status = ?,
                        insight_count = ?,
                        sources_processed = ?,
                        extraction_duration_seconds = ?,
                        updated_at = ?
                    WHERE id = ?
                """, (
                    'complete',
                    result.get('insight_count', 0),
                    result.get('sources_processed', 0),
                    duration,
                    now,
                    job_id
                ))

                conn.commit()

            logger.info(
                f"Job {job_id} completed: {result.get('insight_count', 0)} insights "
                f"from {result.get('sources_processed', 0)} sources in {duration:.1f}s"
            )

        except Exception as e:
            logger.error(f"Error completing job: {e}")

    def _handle_job_failure(
        self,
        job_id: str,
        topic: str,
        user_id: str,
        error: str,
        is_transient: bool
    ):
        """
        Handle job failure with retry logic.

        Args:
            job_id: Job identifier
            topic: Topic that failed
            user_id: User identifier
            error: Error message
            is_transient: Whether error is transient (retry-eligible)
        """
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    "SELECT retry_count FROM extraction_jobs WHERE id = ?",
                    (job_id,)
                )
                row = cursor.fetchone()
                retry_count = row[0] if row else 0

                now = datetime.now().isoformat()

                error_data = json.dumps({
                    "type": "transient" if is_transient else "permanent",
                    "message": error,
                    "retry_eligible": is_transient and retry_count < MAX_RETRIES
                })

                if is_transient and retry_count < MAX_RETRIES:
                    new_retry_count = retry_count + 1
                    logger.info(
                        f"Job {job_id} failed (transient), "
                        f"retry {new_retry_count}/{MAX_RETRIES}"
                    )

                    cursor.execute("""
                        UPDATE extraction_jobs
                        SET status = ?,
                            error = ?,
                            retry_count = ?,
                            last_retry_at = ?,
                            updated_at = ?
                        WHERE id = ?
                    """, ('queued', error_data, new_retry_count, now, now, job_id))

                    conn.commit()

                    priority = 1
                    self.job_queue.put((priority, job_id, topic, user_id))

                    with self.active_jobs_lock:
                        self.active_jobs[topic] = job_id

                else:
                    logger.error(
                        f"Job {job_id} failed permanently: {error}"
                    )

                    cursor.execute("""
                        UPDATE extraction_jobs
                        SET status = ?,
                            error = ?,
                            updated_at = ?
                        WHERE id = ?
                    """, ('failed', error_data, now, job_id))

                    conn.commit()

        except Exception as e:
            logger.error(f"Error handling job failure: {e}")

    def _is_transient_error(self, error: str) -> bool:
        """
        Check if error is transient and retry-eligible.

        Args:
            error: Error message

        Returns:
            True if error is transient
        """
        transient_patterns = [
            "timeout",
            "connection",
            "rate limit",
            "503",
            "502",
            "429",
            "temporary"
        ]

        error_lower = error.lower()
        return any(pattern in error_lower for pattern in transient_patterns)

    def _set_estimated_completion(
        self,
        job_id: str,
        estimated_seconds: int
    ):
        """
        Set estimated completion time for job.

        Args:
            job_id: Job identifier
            estimated_seconds: Estimated duration in seconds
        """
        try:
            completion_time = datetime.now() + timedelta(seconds=estimated_seconds)

            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE extraction_jobs
                    SET estimated_completion_at = ?
                    WHERE id = ?
                """, (completion_time.isoformat(), job_id))
                conn.commit()

        except Exception as e:
            logger.error(f"Error setting estimated completion: {e}")

    def update_progress(
        self,
        job_id: str,
        sources_processed: int
    ):
        """
        Update job progress.

        Args:
            job_id: Job identifier
            sources_processed: Number of sources processed so far
        """
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE extraction_jobs
                    SET sources_processed = ?
                    WHERE id = ?
                """, (sources_processed, job_id))
                conn.commit()

        except Exception as e:
            logger.error(f"Error updating progress: {e}")

    def _update_job_status(
        self,
        job_id: str,
        status: str,
        error: Optional[str] = None
    ):
        """
        Update job status in database.

        Args:
            job_id: Job identifier
            status: New status ('queued', 'processing', 'complete', 'failed')
            error: Optional error message if status is 'failed'
        """
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()

                now = datetime.now().isoformat()

                if error:
                    cursor.execute("""
                        UPDATE extraction_jobs
                        SET status = ?, error = ?, updated_at = ?
                        WHERE id = ?
                    """, (status, error, now, job_id))
                else:
                    cursor.execute("""
                        UPDATE extraction_jobs
                        SET status = ?, updated_at = ?
                        WHERE id = ?
                    """, (status, now, job_id))

                conn.commit()

        except Exception as e:
            logger.error(f"Error updating job status: {e}")
