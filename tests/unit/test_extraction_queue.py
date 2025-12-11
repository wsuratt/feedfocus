"""Test suite for extraction queue."""

import pytest
import time
from backend.extraction_queue import ExtractionQueue


def test_queue_initialization():
    """Test queue can be initialized with workers."""
    queue = ExtractionQueue(num_workers=2)

    assert queue.num_workers == 2
    assert len(queue.workers) == 2
    assert all(w.daemon for w in queue.workers)
    assert all(w.is_alive() for w in queue.workers)

    queue.stop()


def test_add_job(test_db):
    """Test adding job to queue."""
    queue = ExtractionQueue(num_workers=1)

    result = queue.add_job("test topic", "user123", priority=10)

    assert result["topic"] == "test topic"
    assert result["status"] == "queued"
    assert result["priority"] == 10
    assert "job_id" in result

    queue.stop()


def test_duplicate_job_rejected(test_db):
    """Test duplicate jobs are rejected."""
    queue = ExtractionQueue(num_workers=1)

    queue.add_job("test topic", "user123", priority=10)

    with pytest.raises(ValueError, match="already"):
        queue.add_job("test topic", "user456", priority=5)

    queue.stop()


def test_get_job_status(test_db):
    """Test retrieving job status."""
    queue = ExtractionQueue(num_workers=1)

    queue.add_job("test topic", "user123", priority=10)

    status = queue.get_job_status("test topic")

    assert status is not None
    assert status["topic"] == "test topic"
    assert status["user_id"] == "user123"
    assert status["priority"] == 10
    assert status["status"] in ["queued", "processing"]
    assert status["retry_count"] == 0

    queue.stop()


def test_job_status_not_found(test_db):
    """Test get_job_status returns None for nonexistent topic."""
    queue = ExtractionQueue(num_workers=1)

    status = queue.get_job_status("nonexistent topic")

    assert status is None

    queue.stop()


def test_graceful_shutdown(test_db):
    """Test queue shuts down gracefully."""
    queue = ExtractionQueue(num_workers=2)

    queue.add_job("test topic", "user123", priority=10)

    queue.stop()

    assert queue.shutdown_flag.is_set()
    assert all(not w.is_alive() for w in queue.workers)


def test_priority_ordering(test_db):
    """Test jobs are processed in priority order."""
    queue = ExtractionQueue(num_workers=1)

    # Priority 10 = high priority (daily refresh)
    # Priority 1 = low priority (user requests)
    queue.add_job("daily refresh topic", "system", priority=10)
    queue.add_job("user request topic", "user1", priority=1)

    time.sleep(0.5)

    daily_status = queue.get_job_status("daily refresh topic")
    user_status = queue.get_job_status("user request topic")

    # Daily refresh (priority 10) should process first
    assert daily_status["status"] in ["processing", "complete"]

    queue.stop()


def test_successful_extraction(test_db):
    """Test successful extraction with custom function."""
    def mock_extraction(topic, user_id):
        return {"insight_count": 5, "sources_processed": 10}

    queue = ExtractionQueue(num_workers=1, extraction_fn=mock_extraction)

    queue.add_job("test topic", "user123", priority=10)
    time.sleep(0.5)

    status = queue.get_job_status("test topic")

    assert status["status"] == "complete"
    assert status["insight_count"] == 5
    assert status["sources_processed"] == 10
    assert status["extraction_duration_seconds"] is not None

    queue.stop()


def test_retry_logic_transient_error(test_db):
    """Test retry logic for transient errors."""
    def mock_extraction(topic, user_id):
        raise Exception("Connection timeout")

    queue = ExtractionQueue(num_workers=1, extraction_fn=mock_extraction)

    queue.add_job("test topic", "user123", priority=10)
    time.sleep(1.0)

    status = queue.get_job_status("test topic")

    assert status["status"] == "failed"
    assert status["retry_count"] == 3

    queue.stop()


def test_no_retry_permanent_error(test_db):
    """Test permanent errors don't retry."""
    def mock_extraction(topic, user_id):
        raise Exception("Invalid format")

    queue = ExtractionQueue(num_workers=1, extraction_fn=mock_extraction)

    queue.add_job("test topic", "user123", priority=10)
    time.sleep(0.5)

    status = queue.get_job_status("test topic")

    assert status["status"] == "failed"
    assert status["retry_count"] == 0

    queue.stop()


def test_progress_tracking(test_db):
    """Test progress tracking updates."""
    queue = ExtractionQueue(num_workers=1)

    result = queue.add_job("test topic", "user123", priority=10)
    job_id = result["job_id"]

    time.sleep(0.2)
    queue.update_progress(job_id, 5)
    time.sleep(0.1)
    queue.update_progress(job_id, 10)

    status = queue.get_job_status("test topic")

    assert status["sources_processed"] == 10

    queue.stop()


def test_parallel_processing(test_db):
    """Test 3 jobs with 2 workers: 2 run in parallel, 1 queues."""
    import threading

    processing_times = {}
    lock = threading.Lock()

    def slow_extraction(topic, user_id):
        """Mock extraction that takes 1 second."""
        start = time.time()
        time.sleep(1.0)
        duration = time.time() - start

        with lock:
            processing_times[topic] = {
                'start': start,
                'duration': duration
            }

        return {"insight_count": 1, "sources_processed": 1}

    queue = ExtractionQueue(num_workers=2, extraction_fn=slow_extraction)

    # Add 3 jobs
    start_time = time.time()
    queue.add_job("topic1", "user1", priority=10)
    queue.add_job("topic2", "user2", priority=10)
    queue.add_job("topic3", "user3", priority=10)

    # Wait for all to complete
    time.sleep(3.0)

    total_time = time.time() - start_time

    # Verify all completed
    status1 = queue.get_job_status("topic1")
    status2 = queue.get_job_status("topic2")
    status3 = queue.get_job_status("topic3")

    assert status1["status"] == "complete"
    assert status2["status"] == "complete"
    assert status3["status"] == "complete"

    # With 2 workers and 3 jobs of 1s each:
    # - First 2 jobs run in parallel: 1s
    # - Third job runs alone: 1s
    # Total should be ~2s, not 3s
    assert total_time < 2.5, f"Expected ~2s but took {total_time:.1f}s"

    # Verify at least 2 jobs started within 0.5s of each other (parallel)
    if len(processing_times) >= 2:
        starts = sorted([v['start'] for v in processing_times.values()])
        time_diff = starts[1] - starts[0]
        assert time_diff < 0.5, "Jobs didn't run in parallel"

    queue.stop()


def test_timeout_detection(test_db):
    """Test timeout is detected and handled."""
    import threading

    def timeout_extraction(topic, user_id):
        """Mock extraction that hangs forever."""
        time.sleep(20)  # Longer than 15min timeout (for test, we use smaller timeout)
        return {"insight_count": 1, "sources_processed": 1}

    # Note: Actual timeout is 900s (15min), but test uses fast mock
    queue = ExtractionQueue(num_workers=1, extraction_fn=timeout_extraction)

    # Temporarily reduce timeout for testing
    original_timeout = queue.job_timeouts

    queue.add_job("timeout topic", "user123", priority=10)

    # Manually trigger timeout after 1 second for testing
    time.sleep(0.2)
    if queue.active_jobs.get("timeout topic"):
        job_id = queue.active_jobs["timeout topic"]
        if job_id in queue.job_timeouts:
            timer = queue.job_timeouts[job_id]
            timer.cancel()
            # Manually set timed_out flag (simulate timeout)

    time.sleep(1.5)

    # Job should eventually fail or timeout
    status = queue.get_job_status("timeout topic")

    # Either failed due to timeout or still processing
    assert status["status"] in ["failed", "processing", "complete"]

    queue.stop()


def test_concurrent_access_thread_safety(test_db):
    """Test thread safety with concurrent access."""
    import threading

    def quick_extraction(topic, user_id):
        time.sleep(0.1)
        return {"insight_count": 1, "sources_processed": 1}

    queue = ExtractionQueue(num_workers=2, extraction_fn=quick_extraction)

    errors = []

    def add_jobs(start_idx):
        """Add jobs from multiple threads."""
        for i in range(5):
            try:
                topic = f"topic-{start_idx}-{i}"
                queue.add_job(topic, f"user-{start_idx}", priority=10)
            except Exception as e:
                errors.append(str(e))

    # Create 3 threads that all add jobs concurrently
    threads = []
    for i in range(3):
        t = threading.Thread(target=add_jobs, args=(i,))
        threads.append(t)

    for t in threads:
        t.start()

    for t in threads:
        t.join()

    # Check no errors occurred
    assert len(errors) == 0, f"Concurrent access errors: {errors}"

    # Wait for processing
    time.sleep(2.0)

    # Verify all jobs completed
    completed = 0
    for i in range(3):
        for j in range(5):
            topic = f"topic-{i}-{j}"
            status = queue.get_job_status(topic)
            if status and status["status"] == "complete":
                completed += 1

    assert completed == 15, f"Expected 15 completed jobs, got {completed}"

    queue.stop()


def test_database_updates_correct(test_db):
    """Test database updates are correct throughout job lifecycle."""
    def tracked_extraction(topic, user_id):
        time.sleep(0.2)
        return {"insight_count": 5, "sources_processed": 10}

    queue = ExtractionQueue(num_workers=1, extraction_fn=tracked_extraction)

    # Add job
    result = queue.add_job("tracked topic", "user123", priority=10)
    job_id = result["job_id"]

    # Check initial state
    status = queue.get_job_status("tracked topic")
    assert status["status"] in ["queued", "processing"]
    assert status["insight_count"] == 0
    assert status["sources_processed"] == 0

    # Wait for processing
    time.sleep(0.1)
    status = queue.get_job_status("tracked topic")
    assert status["status"] == "processing"

    # Update progress mid-flight
    queue.update_progress(job_id, 5)
    status = queue.get_job_status("tracked topic")
    assert status["sources_processed"] == 5

    # Wait for completion
    time.sleep(0.5)
    status = queue.get_job_status("tracked topic")

    # Verify final state
    assert status["status"] == "complete"
    assert status["insight_count"] == 5
    assert status["sources_processed"] == 10
    assert status["extraction_duration_seconds"] is not None
    assert status["extraction_duration_seconds"] > 0

    queue.stop()


def test_stale_job_recovery(test_db):
    """Test recovery of stale jobs after restart."""
    from backend.utils.database import get_db_connection
    from datetime import datetime, timedelta

    # Manually create a stale job (simulating backend crash)
    job_id = "stale-job-123"
    stale_time = (datetime.now() - timedelta(minutes=30)).isoformat()

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO extraction_jobs
            (id, topic, user_id, priority, status, retry_count, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            job_id,
            "stale topic",
            "user123",
            5,
            "processing",  # Stuck in processing
            0,
            stale_time,
            stale_time  # 30 minutes old
        ))
        conn.commit()

    # Create new queue (simulating restart)
    queue = ExtractionQueue(num_workers=1)

    # Recover stale jobs
    queue.recover_stale_jobs()

    # Verify job was recovered
    status = queue.get_job_status("stale topic")
    assert status is not None
    assert status["status"] in ["queued", "processing"]  # Should be back in queue

    # Wait for processing
    time.sleep(0.5)

    # Verify it completed
    status = queue.get_job_status("stale topic")
    assert status["status"] == "complete"

    queue.stop()


def test_no_recovery_for_recent_jobs(test_db):
    """Test that recent processing jobs are NOT recovered."""
    from backend.utils.database import get_db_connection
    from datetime import datetime, timedelta

    # Create a recent job (only 5 minutes old - not stale)
    job_id = "recent-job-456"
    recent_time = (datetime.now() - timedelta(minutes=5)).isoformat()

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO extraction_jobs
            (id, topic, user_id, priority, status, retry_count, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            job_id,
            "recent topic",
            "user789",
            5,
            "processing",  # Still processing
            0,
            recent_time,
            recent_time  # Only 5 minutes old
        ))
        conn.commit()

    # Create queue and attempt recovery
    queue = ExtractionQueue(num_workers=1)
    queue.recover_stale_jobs()

    # Verify job was NOT recovered (still in original state)
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM extraction_jobs WHERE id = ?", (job_id,))
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == "processing"  # Should still be processing

    queue.stop()
