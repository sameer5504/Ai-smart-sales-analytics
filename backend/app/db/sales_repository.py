from app.db.connection import get_connection


def fetch_user_sales_data(user_id: int, limit: int = 200) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT transaction_date, order_id, product_id, product_name,
                       quantity, unit_price
                FROM sales_transactions
                WHERE user_id = %s
                ORDER BY transaction_date DESC
                LIMIT %s
                """,
                (user_id, limit),
            )
            columns = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
            return [dict(zip(columns, row)) for row in rows]
