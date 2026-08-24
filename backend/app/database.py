"""
Sets up the connection to our Neon PostgreSQL database.

SQLAlchemy is the library we use to talk to Postgres from Python. Here we
create one shared "engine" (the thing that manages a pool of database
connections) and one "SessionLocal" factory (used later to open a
conversation with the database for a single request).

This connection has to survive being used from an unreliable network (a
laptop on a mobile hotspot, a connection that can drop mid-request) and
from Neon specifically, whose compute can suspend when idle and takes a
moment to wake back up. Three separate defenses work together for that:
  1. pool_pre_ping - checks a pooled connection is actually still alive
     right before handing it to a request, replacing it silently if not.
  2. pool_recycle - never lets SQLAlchemy hand out a connection older
     than this, so a connection can't survive long enough to be one Neon
     (or an in-between load balancer) decided to close on its own.
  3. commit_with_retry() - for a connection that dies WHILE a request is
     using it (mid-flight, not just sitting idle in the pool), pre_ping
     can't help - that failure only shows up as an error from the write
     itself. commit_with_retry() catches exactly that class of error
     (never a real data/schema error - see its own docstring) and
     retries with a fresh connection.
"""

import logging
import time
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.exc import InterfaceError, OperationalError
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.config import settings

logger = logging.getLogger("medvault")

# How long a pooled connection is allowed to live before SQLAlchemy
# discards and reopens it, regardless of whether pre_ping thinks it's
# still alive - Neon (and most managed Postgres/poolers in front of it)
# can close a connection server-side after a period that pre_ping alone
# doesn't always catch in time. 300s is comfortably under every such
# timeout we've seen in practice while still keeping the pool warm for
# normal traffic.
_POOL_RECYCLE_SECONDS = 300

# libpq-level settings, passed straight through to psycopg2.connect().
# connect_timeout keeps a bad connection attempt (e.g. the mobile
# hotspot dropping right as we're dialing) from hanging the request for
# the OS's own multi-minute TCP timeout. The keepalive settings ask the
# OS to probe an otherwise-idle connection every 10s after 30s of
# silence, and give up after 3 missed probes (~30s) - so a connection
# that's actually gone gets noticed and reported as a real error
# quickly, instead of looking "fine" until the next query hits a dead
# socket. sslmode=require is already in DATABASE_URL's query string
# (Neon requires it) - repeating it here is redundant but harmless
# (SQLAlchemy's psycopg2 dialect just overwrites it with the same
# value), and keeps this explicit and correct even if the URL is ever
# changed to omit it.
_CONNECT_ARGS = {
    "connect_timeout": 10,
    "sslmode": "require",
    "keepalives": 1,
    "keepalives_idle": 30,
    "keepalives_interval": 10,
    "keepalives_count": 3,
}

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_recycle=_POOL_RECYCLE_SECONDS,
    connect_args=_CONNECT_ARGS,
)

# Later, each request will get its own Session created from this factory.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# All our database models (Task 5) will inherit from this Base class.
Base = declarative_base()

# The two SQLAlchemy exception classes that specifically mean "the
# DB-API driver couldn't talk to the server" - a dropped/reset TCP
# connection, a timed-out connect, the server closing an idle socket,
# Neon's compute still waking up. Deliberately NOT sqlalchemy.exc.
# ProgrammingError (a real SQL/schema problem - e.g. a column that
# doesn't exist because a migration hasn't been applied yet), NOT
# IntegrityError (a real constraint violation), and NOT any other
# DBAPIError subclass - retrying those would just fail the same way
# three times instead of failing clearly once.
_TRANSIENT_DB_ERRORS = (OperationalError, InterfaceError)


def describe_db_error(error: Exception) -> str:
    """
    The real driver-level error text (e.g. psycopg2's own exception
    class and message - "SSL SYSCALL error: EOF detected",
    "connection already closed", "server closed the connection
    unexpectedly") pulled out explicitly, rather than left buried inside
    a long SQLAlchemy-wrapped stack trace. This is what actually
    explains WHY a connection failed.
    """
    orig = getattr(error, "orig", None)
    if orig is not None:
        return f"{type(orig).__module__}.{type(orig).__name__}: {orig}"
    return f"{type(error).__name__}: {error}"


def commit_with_retry(
    db: Session,
    mutate,
    *,
    attempts: int = 3,
    base_delay: float = 0.3,
) -> None:
    """
    Runs `mutate()` (a callable that stages whatever change(s) belong in
    this write - db.add(...), db.delete(...), a setattr(...), or several
    of those together) and commits, automatically retrying up to
    `attempts` times if the commit fails with a TRANSIENT connection
    error (see _TRANSIENT_DB_ERRORS above) - never for a real data or
    schema error, which is raised immediately exactly as a plain
    db.commit() would be.

    `mutate` is REQUIRED, and is called fresh on every attempt,
    INCLUDING THE FIRST - never call db.add()/db.delete()/setattr()
    yourself before calling this. That's not a style preference: a
    rollback() (which this does before every retry, to leave the
    session clean) reverts ALL of the session's pending, uncommitted
    work - a pending add(), delete(), or attribute change alike. Retried
    with a bare db.commit() and no re-applied mutate(), the write is
    silently lost - no exception, no data, and the caller gets a normal
    success (verified empirically: a rollback()-then-retry commit()
    with nothing re-staged produces zero rows changed, not an error).
    That failure mode is worse than the connection error this exists to
    paper over, so there is no lower-risk "just commit()" variant of
    this function.

    Every retryable failure is logged with the real underlying error
    text.
    """
    last_error: Exception | None = None

    for attempt in range(1, attempts + 1):
        try:
            mutate()
            db.commit()
            return
        except _TRANSIENT_DB_ERRORS as error:
            last_error = error
            logger.warning(
                "Database commit failed on attempt %d/%d - transient, retrying: %s",
                attempt,
                attempts,
                describe_db_error(error),
            )
            db.rollback()
            if attempt < attempts:
                time.sleep(base_delay * (2 ** (attempt - 1)))

    logger.error(
        "Database commit failed after %d attempt(s), giving up: %s",
        attempts,
        describe_db_error(last_error),
    )
    raise last_error


def check_database_connection() -> None:
    """
    Opens a real connection to Neon and runs the simplest possible query
    ("SELECT 1"). This proves the connection actually works end to end -
    not just that the URL is formatted correctly - and raises an error
    (sqlalchemy.exc.SQLAlchemyError) if it doesn't.

    Also compares the database's actual migration state against what
    the running code expects (its Alembic "head") and logs a loud,
    specific warning if they've drifted apart - a mismatch here causes
    exactly the kind of confusing mid-request database error (a column
    the code expects that the live table doesn't have yet) that's easy
    to mistake for a flaky connection. Also warns if the test_aliases
    catalog is empty - a database that's never had
    `python -m app.test_names.seed` run against it, which silently
    disables trend tracking (every result stays unmatched) without ever
    raising an error anywhere. Neither check ever raises on its own -
    both are diagnostics, not a hard requirement to serve traffic.
    """
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))

    _warn_if_migrations_are_behind()
    _warn_if_test_alias_catalog_is_empty()


def _warn_if_migrations_are_behind() -> None:
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        backend_dir = Path(__file__).resolve().parent.parent
        alembic_cfg = Config(str(backend_dir / "alembic.ini"))
        alembic_cfg.set_main_option("script_location", str(backend_dir / "alembic"))
        code_head = ScriptDirectory.from_config(alembic_cfg).get_current_head()

        with engine.connect() as connection:
            db_version = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar()
    except Exception:
        # Best-effort only - never let a diagnostic check itself take
        # down the health check or an unrelated request.
        logger.debug("Could not compare database migration state.", exc_info=True)
        return

    if db_version != code_head:
        logger.warning(
            "DATABASE SCHEMA IS BEHIND THE RUNNING CODE: the database is at "
            "migration %r but this code expects %r. This will cause real "
            "errors (e.g. 'column does not exist') on any write that "
            "touches a column added since - NOT a network/connection "
            "problem, and retrying will not fix it. Fix: run "
            "`alembic upgrade head` against this database.",
            db_version,
            code_head,
        )


def _warn_if_test_alias_catalog_is_empty() -> None:
    try:
        from app.models import TestAlias

        with SessionLocal() as session:
            has_any_alias = session.query(TestAlias.id).first() is not None
    except Exception:
        logger.debug("Could not check the test_aliases catalog.", exc_info=True)
        return

    if not has_any_alias:
        logger.warning(
            "TEST ALIAS CATALOG IS EMPTY: the test_aliases table has no rows, "
            "so no result on any report can match the catalog - trends will "
            "show every test as 'not tracked over time' no matter how many "
            "reports are uploaded. Fix: run `python -m app.test_names.seed` "
            "against this database, then `python -m app.test_names.backfill` "
            "to re-resolve any reports already processed before the catalog "
            "was seeded."
        )
