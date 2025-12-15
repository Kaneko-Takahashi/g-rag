"""
データベース初期化（SQLite）
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from main import Base

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/grag.db")

# SQLite用にディレクトリ作成
if DATABASE_URL.startswith("sqlite"):
    db_path = DATABASE_URL.replace("sqlite:///", "")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """データベーステーブル作成"""
    Base.metadata.create_all(bind=engine)

def get_db():
    """DBセッション取得"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

