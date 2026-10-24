from app.db.connection import get_connection


def _rows_to_dicts(cur, rows):
    columns = [desc[0] for desc in cur.description]
    return [dict(zip(columns, row)) for row in rows]


def insert_dataset(
    user_id: int,
    filename: str,
    blob_path: str,
    row_count: int,
    stored: bool,
    currency: str | None = None,
    content_hash: str | None = None,
) -> dict:
    """Create a new dataset row for this upload.

    Always inserts - re-uploading the same filename creates a separate
    dataset row (and a separate blob, see AzureStorage/preparation.py),
    rather than overwriting a previous upload. Two uploads named
    "sales.csv" with different mappings/currencies are two independent
    reports, both visible in the user's file list.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO datasets (user_id, filename, blob_path, row_count, stored, currency, content_hash)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id, user_id, filename, blob_path, row_count, stored, currency, content_hash, created_at
                """,
                (user_id, filename, blob_path, row_count, stored, currency, content_hash),
            )
            return _rows_to_dicts(cur, [cur.fetchone()])[0]


def find_matching_dataset(user_id: int, content_hash: str, currency: str | None) -> dict | None:
    """Return the most recent previous dataset with identical content (same
    data AND mapping, since a different mapping changes the hash - see
    preparation.PreparedUpload.content_hash) and the same currency, for
    this user - or None if this would be a genuinely new upload.

    Used to warn the user before saving an exact duplicate (see
    /api/mapping/apply), not to block it outright - the caller decides
    whether to proceed anyway.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, user_id, filename, blob_path, row_count, stored, currency, content_hash, created_at
                FROM datasets
                WHERE user_id = %s AND content_hash = %s AND currency = %s AND stored = TRUE
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (user_id, content_hash, currency),
            )
            row = cur.fetchone()
            if row is None:
                return None
            return _rows_to_dicts(cur, [row])[0]


def list_datasets_for_user(user_id: int) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, user_id, filename, blob_path, row_count, stored, currency, content_hash, created_at
                FROM datasets
                WHERE user_id = %s
                ORDER BY created_at DESC
                """,
                (user_id,),
            )
            return _rows_to_dicts(cur, cur.fetchall())


def get_dataset_for_user(dataset_id: int, user_id: int) -> dict | None:
    """Ownership check: returns the dataset only if it belongs to
    user_id, otherwise None.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, user_id, filename, blob_path, row_count, stored, currency, content_hash, created_at
                FROM datasets
                WHERE id = %s AND user_id = %s
                """,
                (dataset_id, user_id),
            )
            row = cur.fetchone()
            if row is None:
                return None
            return _rows_to_dicts(cur, [row])[0]


def delete_dataset(dataset_id: int, user_id: int) -> bool:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM datasets WHERE id = %s AND user_id = %s",
                (dataset_id, user_id),
            )
            return cur.rowcount > 0
