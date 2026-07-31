"""
Sets up the connection to our Neon PostgreSQL database.

SQLAlchemy is the library we use to talk to Postgres from Python. Here we
create one shared "engine" (the thing that manages a pool of database
connections) and one "SessionLocal" factory (used later to open a
conversation with the database for a single request).
"""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings

# The "engine" manages a pool of connections to Postgres. Neon's
# connection string (in your .env) already includes `sslmode=require`,
# so every connection SQLAlchemy opens through it is encrypted.
engine = create_engine(
    settings.database_url,
    # pool_pre_ping checks that a pooled connection is still alive right
    # before it's used. Cloud databases like Neon can silently close idle
    # connections, so without this you'd occasionally hit a confusing
    # "connection closed" error on an old, reused connection.
    pool_pre_ping=True,
)

# Later, each request will get its own Session created from this factory.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# All our database models (Task 5) will inherit from this Base class.
Base = declarative_base()


def check_database_connection() -> None:
    """
    Opens a real connection to Neon and runs the simplest possible query
    ("SELECT 1"). This proves the connection actually works end to end -
    not just that the URL is formatted correctly - and raises an error
    (sqlalchemy.exc.SQLAlchemyError) if it doesn't.
    """
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
