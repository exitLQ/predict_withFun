import hashlib
import os
import re
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

from database import _connection, _placeholder, initialize_database
from models import UserProfile

SESSION_COOKIE = "predict_session"
CSRF_COOKIE = "predict_csrf"
_email_pattern = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,190}$")


class AuthError(RuntimeError):
    pass


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _password_hash(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    derived = hashlib.scrypt(
        password.encode(),
        salt=salt,
        n=2**14,
        r=8,
        p=1,
        dklen=32,
    )
    return f"scrypt${salt.hex()}${derived.hex()}"


def _password_matches(password: str, encoded: str) -> bool:
    try:
        algorithm, salt, expected = encoded.split("$", 2)
        if algorithm != "scrypt":
            return False
        actual = _password_hash(password, bytes.fromhex(salt)).split("$", 2)[2]
        return secrets.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def _normalize_email(email: str) -> str:
    normalized = email.strip().casefold()
    if not _email_pattern.fullmatch(normalized):
        raise AuthError("Enter a valid email address.")
    return normalized


def create_user(
    email: str,
    password: str,
    role: Literal["user", "admin"] = "user",
) -> UserProfile:
    if len(password) < 12 or len(password) > 256:
        raise AuthError("Password must contain between 12 and 256 characters.")
    initialize_database()
    normalized = _normalize_email(email)
    user_id = str(uuid.uuid4())
    created_at = datetime.now(UTC).isoformat()
    placeholders = ", ".join([_placeholder()] * 6)
    try:
        with _connection() as connection:
            connection.execute(
                f"""
                INSERT INTO users (
                    id, email, password_hash, role, created_at, active
                ) VALUES ({placeholders})
                """,
                (
                    user_id,
                    normalized,
                    _password_hash(password),
                    role,
                    created_at,
                    True,
                ),
            )
    except Exception as error:
        raise AuthError("An account with this email already exists.") from error
    return UserProfile(
        id=user_id,
        email=normalized,
        role=role,
        created_at=created_at,
    )


def authenticate(email: str, password: str) -> UserProfile | None:
    initialize_database()
    normalized = _normalize_email(email)
    with _connection() as connection:
        row = connection.execute(
            f"""
            SELECT id, email, password_hash, role, created_at, active
            FROM users WHERE email = {_placeholder()}
            """,
            (normalized,),
        ).fetchone()
    if not row or not row[5] or not _password_matches(password, row[2]):
        return None
    return UserProfile(
        id=str(row[0]),
        email=str(row[1]),
        role=row[3],
        created_at=row[4],
    )


def create_session(user_id: str) -> tuple[str, str]:
    initialize_database()
    token = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(24)
    now = datetime.now(UTC)
    expires = now + timedelta(
        hours=max(1, min(int(os.getenv("SESSION_TTL_HOURS", "168")), 720))
    )
    placeholders = ", ".join([_placeholder()] * 5)
    with _connection() as connection:
        connection.execute(
            f"""
            INSERT INTO user_sessions (
                token_hash, user_id, csrf_hash, created_at, expires_at
            ) VALUES ({placeholders})
            """,
            (
                _digest(token),
                user_id,
                _digest(csrf),
                now.isoformat(),
                expires.isoformat(),
            ),
        )
    return token, csrf


def session_user(token: str | None) -> UserProfile | None:
    if not token:
        return None
    initialize_database()
    with _connection() as connection:
        row = connection.execute(
            f"""
            SELECT u.id, u.email, u.role, u.created_at, u.active, s.expires_at
            FROM user_sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.token_hash = {_placeholder()}
            """,
            (_digest(token),),
        ).fetchone()
    if not row or not row[4]:
        return None
    expires = datetime.fromisoformat(str(row[5]))
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    if expires <= datetime.now(UTC):
        delete_session(token)
        return None
    return UserProfile(
        id=str(row[0]),
        email=str(row[1]),
        role=row[2],
        created_at=row[3],
    )


def valid_csrf(token: str | None, csrf: str | None) -> bool:
    if not token or not csrf:
        return False
    initialize_database()
    with _connection() as connection:
        row = connection.execute(
            f"""
            SELECT csrf_hash FROM user_sessions
            WHERE token_hash = {_placeholder()}
            """,
            (_digest(token),),
        ).fetchone()
    return bool(row and secrets.compare_digest(str(row[0]), _digest(csrf)))


def delete_session(token: str | None) -> None:
    if not token:
        return
    initialize_database()
    with _connection() as connection:
        connection.execute(
            f"DELETE FROM user_sessions WHERE token_hash = {_placeholder()}",
            (_digest(token),),
        )


def bootstrap_admin() -> None:
    email = os.getenv("BOOTSTRAP_ADMIN_EMAIL")
    password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD")
    if not email or not password:
        return
    try:
        create_user(email, password, "admin")
    except AuthError:
        return
