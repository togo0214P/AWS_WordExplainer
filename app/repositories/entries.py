"""Database operations for entries."""

from app.database import get_connection
from app.schemas.entries import (
    CreateEntryRequest,
    CreateEntryResponse,
    EntrySearchResult,
)


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


def search_entries(
    word: str | None = None,
    category_id: int | None = None,
) -> list[EntrySearchResult]:
    """Return active entries matching the optional search filters."""
    query = """
        SELECT id, word, category_id, explanation
        FROM entries
        WHERE deleted_at IS NULL
    """
    conditions: list[str] = []
    parameters: list[str | int] = []

    if word is not None:
        conditions.append("word ILIKE %s")
        parameters.append(f"%{word}%")
    if category_id is not None:
        conditions.append("category_id = %s")
        parameters.append(category_id)

    if conditions:
        query += " AND " + " AND ".join(conditions)
    query += " ORDER BY id"

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, parameters)
            rows = cursor.fetchall()

    return [
        EntrySearchResult(
            id=row[0],
            word=row[1],
            category_id=row[2],
            explanation=row[3],
        )
        for row in rows
    ]
