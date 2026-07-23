from pathlib import Path

import auth


def test_password_authentication_and_session_csrf(monkeypatch):
    database_path = "test-auth-round-trip.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")
    try:
        user = auth.create_user("Person@Example.com", "long-test-password")
        assert user.email == "person@example.com"
        assert auth.authenticate("person@example.com", "wrong-password") is None
        assert auth.authenticate(
            "person@example.com", "long-test-password"
        ).id == user.id

        session_token, csrf_token = auth.create_session(user.id)
        assert auth.session_user(session_token).id == user.id
        assert auth.valid_csrf(session_token, csrf_token) is True
        assert auth.valid_csrf(session_token, "wrong") is False

        auth.delete_session(session_token)
        assert auth.session_user(session_token) is None
    finally:
        Path(database_path).unlink(missing_ok=True)
