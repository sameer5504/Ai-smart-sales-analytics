import pytest


@pytest.fixture
def as_user():
    """Override get_current_user for this test, acting as the given user id.

    Usage: call as_user(1) inside a test to make subsequent requests through
    the TestClient authenticate as that user. Mirrors the root
    authenticated_user fixture, but lets a single test act as more than one
    user -- needed to prove one user cannot see or fetch another user's
    reports.

    Imports app.main lazily so importing this conftest (which pytest does
    for the whole tests/reports package) doesn't force-load the entire app
    graph for tests that don't need a live TestClient at all.
    """

    from app.auth.dependencies import get_current_user
    from app.main import app

    def _set(user_id: int) -> dict:
        app.dependency_overrides[get_current_user] = lambda: {"user_id": user_id}
        return {"user_id": user_id}

    yield _set

    app.dependency_overrides.pop(get_current_user, None)
