from src.api import auth_session


def test_issue_and_verify_roundtrip():
    token = auth_session.issue_token("admin", "secret", now=1000)
    assert auth_session.verify_token(token, "admin", "secret", now=1001) is True


def test_expired_token_rejected():
    token = auth_session.issue_token("admin", "secret", now=1000)
    expired_at = 1000 + auth_session.SESSION_TTL_SECONDS + 1
    assert auth_session.verify_token(token, "admin", "secret", now=expired_at) is False


def test_password_change_invalidates_token():
    token = auth_session.issue_token("admin", "old-password", now=1000)
    assert auth_session.verify_token(token, "admin", "new-password", now=1001) is False


def test_tampered_or_malformed_token_rejected():
    token = auth_session.issue_token("admin", "secret", now=1000)
    encoded, signature = token.split(".")
    assert auth_session.verify_token(f"{encoded}x.{signature}", "admin", "secret", now=1001) is False
    assert auth_session.verify_token("not-a-token", "admin", "secret", now=1001) is False
    assert auth_session.verify_token(None, "admin", "secret", now=1001) is False
