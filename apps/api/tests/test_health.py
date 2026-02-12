"""ヘルスチェック・認証の単体テスト"""
import pytest


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data.get("status") == "ok"
    assert "mode" in data
    assert "auth_mode" in data


def test_login_demo(client):
    r = client.post("/auth/login", json={"passcode": "test123"})
    assert r.status_code == 200
    data = r.json()
    assert "token" in data
    assert "user_id" in data
    assert len(data["token"]) > 0


def test_login_demo_missing_passcode(client):
    r = client.post("/auth/login", json={})
    # demo mode requires passcode -> 400
    assert r.status_code in (400, 422)
