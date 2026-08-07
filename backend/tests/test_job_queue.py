"""
Tests for the Redis job queue. The underlying Upstash client is mocked
entirely - no live Redis needed - since these tests are only checking
that OUR code calls it correctly (right key, right method, right
argument types), not that Upstash itself works.
"""

from unittest.mock import patch

from app.jobs.queue import QUEUE_KEY, dequeue_job, enqueue_job, queue_length


def test_enqueue_job_pushes_the_job_id_as_a_string():
    with patch("app.jobs.queue._redis_client") as mock_redis:
        enqueue_job("abc-123")

    mock_redis.rpush.assert_called_once_with(QUEUE_KEY, "abc-123")


def test_enqueue_job_converts_a_uuid_to_a_string():
    import uuid

    job_id = uuid.uuid4()
    with patch("app.jobs.queue._redis_client") as mock_redis:
        enqueue_job(job_id)

    mock_redis.rpush.assert_called_once_with(QUEUE_KEY, str(job_id))


def test_dequeue_job_returns_the_popped_value():
    with patch("app.jobs.queue._redis_client") as mock_redis:
        mock_redis.lpop.return_value = "abc-123"
        result = dequeue_job()

    mock_redis.lpop.assert_called_once_with(QUEUE_KEY)
    assert result == "abc-123"


def test_dequeue_job_returns_none_when_queue_is_empty():
    with patch("app.jobs.queue._redis_client") as mock_redis:
        mock_redis.lpop.return_value = None
        result = dequeue_job()

    assert result is None


def test_queue_length_returns_the_count():
    with patch("app.jobs.queue._redis_client") as mock_redis:
        mock_redis.llen.return_value = 7
        result = queue_length()

    mock_redis.llen.assert_called_once_with(QUEUE_KEY)
    assert result == 7
