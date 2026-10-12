"""Database operations for categories."""

from app.database import get_connection
from app.schemas.categories import CategoryResponse


def list_categories() -> list[CategoryResponse]:
    """Return registered categories ordered by ID."""
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id, name FROM categories ORDER BY id")
            rows = cursor.fetchall()

    return [CategoryResponse(id=row[0], name=row[1]) for row in rows]
