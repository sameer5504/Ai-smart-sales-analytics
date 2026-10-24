from datetime import datetime, timezone

from app.auth.jwt import create_access_token, create_refresh_token, hash_refresh_token
from app.auth.password import hash_password, verify_password
from app.db.connection import get_connection


def register_user(username, password):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id FROM users WHERE username = %s", (username,))

        if cur.fetchone():
            return None

        password_hash = hash_password(password)

        cur.execute(
            """
            INSERT INTO users (username, display_name, password_hash)
            VALUES (%s, %s, %s)
            RETURNING id, username, display_name
            """,
            (username, "", password_hash),
        )

        new_user = cur.fetchone()
        user_id = new_user[0]
        access_token = create_access_token(user_id)
        refresh_token, refresh_expires_at = create_refresh_token()
        refresh_token_hash = hash_refresh_token(refresh_token)

        cur.execute(
            """
            INSERT INTO refresh_tokens (
                user_id,
                token_hash,
                expires_at
            )
            VALUES (%s, %s, %s)
            """,
            (user_id, refresh_token_hash, refresh_expires_at),
        )

        conn.commit()

        return {
            "id": new_user[0],
            "username": new_user[1],
            "display_name": new_user[2],
            "access_token": access_token,
            "refresh_token": refresh_token,
        }
    finally:
        cur.close()
        conn.close()


def login_user(username, password):
    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT id, username, display_name, password_hash
            FROM users
            WHERE username = %s
            """,
            (username,),
        )

        user = cur.fetchone()

        if not user:
            return "user_not_found"

        if not verify_password(password, user[3]):
            return "wrong_password"

        access_token = create_access_token(user[0])

        refresh_token, refresh_expires_at = create_refresh_token()

        refresh_token_hash = hash_refresh_token(refresh_token)

        cur.execute(
            """
                INSERT INTO refresh_tokens (
                user_id,
                token_hash,
                expires_at
            )
            VALUES (%s, %s, %s)
            """,
            (user[0], refresh_token_hash, refresh_expires_at),
        )

        conn.commit()

        return {
            "id": user[0],
            "username": user[1],
            "display_name": user[2],
            "access_token": access_token,
            "refresh_token": refresh_token,
        }
    finally:
        cur.close()
        conn.close()


def update_display_name(user_id, display_name):
    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            UPDATE users
            SET display_name = %s
            WHERE id = %s
            RETURNING id, username, display_name
            """,
            (display_name, user_id),
        )

        user = cur.fetchone()
        conn.commit()

        if not user:
            return None

        return {"id": user[0], "username": user[1], "display_name": user[2]}
    finally:
        cur.close()
        conn.close()


def get_user_profile(user_id):
    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT id, username, display_name
            FROM users
            WHERE id = %s
            """,
            (user_id,),
        )

        user = cur.fetchone()

        if not user:
            return None

        return {"id": user[0], "username": user[1], "display_name": user[2]}
    finally:
        cur.close()
        conn.close()


def refresh_access_token(refresh_token: str):
    conn = get_connection()
    cur = conn.cursor()

    try:
        token_hash = hash_refresh_token(refresh_token)

        cur.execute(
            """
            SELECT user_id, expires_at, revoked_at
            FROM refresh_tokens
            WHERE token_hash = %s
            FOR UPDATE
            """,
            (token_hash,),
        )

        token_record = cur.fetchone()

        if not token_record:
            return None

        user_id, expires_at, revoked_at = token_record

        if revoked_at is not None:
            return None

        if expires_at <= datetime.now(timezone.utc).replace(tzinfo=None):
            return None

        cur.execute(
            """
            UPDATE refresh_tokens
            SET revoked_at = CURRENT_TIMESTAMP
            WHERE token_hash = %s
            AND revoked_at IS NULL
            """,
            (token_hash,),
        )

        if cur.rowcount != 1:
            return None

        new_refresh_token, new_refresh_expires_at = create_refresh_token()
        new_refresh_token_hash = hash_refresh_token(new_refresh_token)

        cur.execute(
            """
            INSERT INTO refresh_tokens (
                user_id,
                token_hash,
                expires_at
            )
            VALUES (%s, %s, %s)
            """,
            (
                user_id,
                new_refresh_token_hash,
                new_refresh_expires_at,
            ),
        )

        access_token = create_access_token(user_id)

        conn.commit()

        return {
            "access_token": access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer",
        }
    finally:
        cur.close()
        conn.close()


def revoke_refresh_token(refresh_token: str):
    conn = get_connection()
    cur = conn.cursor()

    try:
        token_hash = hash_refresh_token(refresh_token)

        cur.execute(
            """
            UPDATE refresh_tokens
            SET revoked_at = CURRENT_TIMESTAMP
            WHERE token_hash = %s
            AND revoked_at IS NULL
            """,
            (token_hash,),
        )

        revoked = cur.rowcount > 0

        conn.commit()

        return revoked

    finally:
        cur.close()
        conn.close()
