"""Database operations for entries."""

from app.database import get_connection
from app.schemas.entries import CreateEntryRequest, CreateEntryResponse


class CategoryNotFoundError(Exception):
    """Raised when an entry refers to a category that does not exist."""


def create_entry(entry: CreateEntryRequest) -> CreateEntryResponse:
    """Insert an entry after confirming its category exists."""
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM categories WHERE id = %s",
                (entry.category_id,),
            )
            if cursor.fetchone() is None:
                raise CategoryNotFoundError

            cursor.execute(
                """
                INSERT INTO entries (word, category_id, explanation)
                VALUES (%s, %s, %s)
                RETURNING id
                """,
                (entry.word, entry.category_id, entry.explanation),
            )
            row = cursor.fetchone()

    return CreateEntryResponse(
        id=row[0],
        word=entry.word,
        category_id=entry.category_id,
        explanation=entry.explanation,
    )
