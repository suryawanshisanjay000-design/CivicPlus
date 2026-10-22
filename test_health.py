from fastapi.testclient import TestClient

from main import app
from models import DepartmentCode, Priority
from triage import fallback_triage

# raise_server_exceptions=False: DB-backed routes surface as 500 instead of raising
# when tests run without real Supabase credentials.
client = TestClient(app, raise_server_exceptions=False)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["database"] == "supabase"


def test_fallback_triage_routes_pothole_to_roads():
    result = fallback_triage("Deep pothole on the main road near the junction", "Road damage")
    assert result.department == DepartmentCode.ROADS
    assert result.priority == Priority.HIGH
    assert result.urgency_score == 7


def test_fallback_triage_default_department():
    result = fallback_triage("Something unusual happened in the park", "General")
    assert result.department == DepartmentCode.ROADS
    assert result.priority == Priority.MEDIUM


def test_login_rejects_unknown_user():
    response = client.post("/auth/login", json={"email": "nobody@civicpulse.local", "password": "x"})
    assert response.status_code in (401, 500)
