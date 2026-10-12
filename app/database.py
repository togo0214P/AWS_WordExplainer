"""PostgreSQL connection lifecycle helpers."""

from collections.abc import Iterator
from contextlib import contextmanager

import psycopg

from app.config import settings


@contextmanager
def get_connection() -> Iterator[psycopg.Connection]:
    """Yield a connection that commits on success and rolls back on failure.

    The Psycopg connection context also closes the connection when it exits.
    """
    with psycopg.connect(
        host=settings.db_host,
        port=settings.db_port,
        dbname=settings.db_name,
        user=settings.db_user,
        password=settings.db_password,
    ) as connection:
        yield connection
