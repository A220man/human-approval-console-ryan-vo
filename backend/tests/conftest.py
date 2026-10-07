"""Test configuration and shared fixtures for backend tests."""
import os
import tempfile
import pytest
from fastapi.testclient import TestClient

# Ensure test settings before importing app
os.environ["ENVIRONMENT"] = "testing"
os.environ["DEMO_MODE"] = "true"
os.environ["SECRET_KEY"] = "test-secret-key-for-unit-tests-32chars"
os.environ["RECEIPT_SIGNING_KEY"] = "test-receipt-signing-key-for-tests"


@pytest.fixture(autouse=True)
def setup_test_db(monkeypatch):
    """Sets up an isolated temporary SQLite database for each test session."""
    fd, temp_db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    from app.core.config import settings
    monkeypatch.setattr(settings, "database_path", temp_db_path)

    # Re-initialize thread-local connection and database
    from app.core import database
    if hasattr(database._local, "conn") and database._local.conn is not None:
        database._local.conn.close()
        database._local.conn = None

    database.init_db()

    yield

    if hasattr(database._local, "conn") and database._local.conn is not None:
        database._local.conn.close()
        database._local.conn = None
    if os.path.exists(temp_db_path):
        os.remove(temp_db_path)


@pytest.fixture
def client():
    """Provides a TestClient instance with cookies support."""
    from app.main import app
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def admin_client(client):
    """Provides a TestClient authenticated as demo-admin with CSRF token set."""
    resp = client.post("/api/auth/demo-login", json={"role": "admin"})
    assert resp.status_code == 200
    csrf_resp = client.get("/api/auth/csrf")
    assert csrf_resp.status_code == 200
    token = csrf_resp.json()["csrf_token"]
    client.headers.update({"x-csrf-token": token})
    return client


@pytest.fixture
def analyst_client(client):
    """Provides a TestClient authenticated as demo-analyst with CSRF token set."""
    resp = client.post("/api/auth/demo-login", json={"role": "analyst"})
    assert resp.status_code == 200
    csrf_resp = client.get("/api/auth/csrf")
    assert csrf_resp.status_code == 200
    token = csrf_resp.json()["csrf_token"]
    client.headers.update({"x-csrf-token": token})
    return client


@pytest.fixture
def viewer_client(client):
    """Provides a TestClient authenticated as demo-viewer with CSRF token set."""
    resp = client.post("/api/auth/demo-login", json={"role": "viewer"})
    assert resp.status_code == 200
    csrf_resp = client.get("/api/auth/csrf")
    assert csrf_resp.status_code == 200
    token = csrf_resp.json()["csrf_token"]
    client.headers.update({"x-csrf-token": token})
    return client
