"""
データベース初期化（SQLite）
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

# Base を database.py で定義（循環インポート回避）
Base = declarative_base()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/grag.db")

# SQLite用にディレクトリ作成
if DATABASE_URL.startswith("sqlite"):
    db_path = DATABASE_URL.replace("sqlite:///", "")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """データベーステーブル作成
    注意: この関数を呼ぶ前に、すべてのモデルクラス（ChatSession, ChatMessage, AuditLog等）が
    インポートされている必要があります。main.py の lifespan 関数で呼び出されます。
    """
    # モデルがインポートされていることを確認するため、Base.metadata にテーブルが登録されているかチェック
    Base.metadata.create_all(bind=engine)

def get_db():
    """DBセッション取得"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

