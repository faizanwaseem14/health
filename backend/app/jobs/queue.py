"""
The background job queue, backed by Upstash Redis via its REST API -
not a raw TCP connection. REST is what Upstash recommends for
serverless/edge environments (and what we were asked to use): every
call here is a plain HTTPS request, not a persistent connection.

Redis here is deliberately "dumb": it only ever holds a job's ID, never
the job's actual data. The `jobs` table in Postgres (app/jobs/service.py)
is the real source of truth for a job's state - Redis is just a signal
saying "a job is ready to be worked on". That split is what makes
idempotency straightforward later: even if the same job ID gets
delivered to a worker twice (queues like this only promise
AT-LEAST-once delivery), the database - not Redis - decides whether
it's actually still safe to process.
"""

from upstash_redis import Redis

from app.config import settings

QUEUE_KEY = "medvault:jobs:queue"

# One shared client, built once when this module is first imported -
# same pattern as the R2 client. Building it doesn't make any network
# call; that only happens when a method below is actually called.
_redis_client = Redis(
    url=settings.upstash_redis_rest_url, token=settings.upstash_redis_rest_token
)


def enqueue_job(job_id) -> None:
    """Puts a job ID on the queue for a worker to pick up."""
    _redis_client.rpush(QUEUE_KEY, str(job_id))


def dequeue_job() -> str | None:
    """
    Takes the next job ID off the queue, or None if the queue is empty.

    Non-blocking - the worker (app/jobs/worker.py) polls this in a
    loop. We use plain LPOP rather than a blocking pop: each REST API
    call is a separate HTTP request, so there's no persistent
    connection to block on the way a raw Redis client could.
    """
    return _redis_client.lpop(QUEUE_KEY)


def queue_length() -> int:
    """How many job IDs are currently waiting. Useful for tests/monitoring."""
    return _redis_client.llen(QUEUE_KEY)
