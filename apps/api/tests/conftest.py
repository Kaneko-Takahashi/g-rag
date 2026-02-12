"""pytest fixtures: テスト用の環境変数とクライアント"""
import os
import pytest

# テスト用環境変数（import 前に設定）
os.environ.setdefault("JWT_SECRET", "test-secret-at-least-32-characters-long")
os.environ.setdefault("AUTH_MODE", "demo")
os.environ.setdefault("EMBEDDING_MODE", "demo")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("VECTOR_DB", "memory")


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from main import app
    from database import init_db
    init_db()
    return TestClient(app)
