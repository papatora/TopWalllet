"""API v2 smoke tests (no-DB endpoints)."""
from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


def test_bad_ca_returns_400():
    r = client.get("/api/v2/token/0x123/whale-map")
    assert r.status_code == 400
    assert r.json()["detail"]["error"]["code"] == "BAD_CA"


def test_methodology_has_verifier_rules():
    r = client.get("/api/v2/methodology")
    assert r.status_code == 200
    body = r.json()
    assert "weights" in body and "verifier_rules" in body
    assert "R1" in body["verifier_rules"]
    assert body["generated_at"]
