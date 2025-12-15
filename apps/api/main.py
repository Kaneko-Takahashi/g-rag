"""
G-RAG API Server
FastAPI + LangGraph + RAG
"""
import os
import time
import hashlib
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, Text, DateTime, Float
from sqlalchemy.orm import Session
from datetime import datetime
from jose import jwt

try:
    from .langgraph_agent import LangGraphAgent
    from .rag import RAGSystem
    from .auth import verify_token, get_current_user_id
    from .database import get_db, init_db, Base
except ImportError:
    from langgraph_agent import LangGraphAgent
    from rag import RAGSystem
    from auth import verify_token, get_current_user_id
    from database import get_db, init_db, Base

# Environment
AUTH_MODE = os.getenv("AUTH_MODE", "demo")
JWT_SECRET = os.getenv("JWT_SECRET", "demo-secret")
EMBEDDING_MODE = os.getenv("EMBEDDING_MODE", "demo")

# Database Models
class ChatSession(Base):
    __tablename__ = "chat_sessions"
    id = Column(Integer, primary_key=True)
    user_id = Column(String, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, index=True)
    role = Column(String)  # user, assistant
    content = Column(Text)
    citations = Column(Text)  # JSON string
    created_at = Column(DateTime, default=datetime.utcnow)

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True)
    user_id = Column(String, index=True)
    action = Column(String)  # ask, bench, login, etc.
    details = Column(Text)  # JSON string
    created_at = Column(DateTime, default=datetime.utcnow)

# Initialize
rag_system = RAGSystem()
agent = LangGraphAgent(rag_system)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_db()
    await rag_system.initialize()
    yield
    # Shutdown
    pass

app = FastAPI(
    title="G-RAG API",
    description="RAG System with LangGraph",
    version="0.1.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request/Response Models
class AskRequest(BaseModel):
    question: str
    use_rerank: bool = True
    top_k: int = 4

class Citation(BaseModel):
    id: str
    title: str
    snippet: str
    score: Optional[float] = None

class AskResponse(BaseModel):
    answer: str
    citations: List[Citation]
    metrics: Dict[str, Any]

class BenchRequest(BaseModel):
    questions: List[str]
    runs: int = 3
    use_rerank: bool = True
    top_k: int = 4

class BenchResponse(BaseModel):
    p50_ms: float
    p95_ms: float
    avg_ms: float
    cache_hit_rate: float
    est_tokens: int
    est_cost_usd: float

class LoginRequest(BaseModel):
    email: Optional[str] = None
    passcode: str

class LoginResponse(BaseModel):
    token: str
    user_id: str

# Routes
@app.post("/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """DEMO認証: パスコードのみでログイン"""
    if AUTH_MODE == "demo":
        # DEMO: 任意のパスコードでOK（本番では検証）
        user_id = hashlib.md5(request.passcode.encode()).hexdigest()[:8]
        token = jwt.encode({"user_id": user_id, "mode": "demo"}, JWT_SECRET, algorithm="HS256")
        
        # 監査ログ
        log = AuditLog(user_id=user_id, action="login", details='{"mode": "demo"}')
        db.add(log)
        db.commit()
        
        return LoginResponse(token=token, user_id=user_id)
    else:
        raise HTTPException(status_code=501, detail="Auth mode not implemented")

@app.post("/ask")
async def ask(
    request: AskRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """質問に回答（ストリーミング）"""
    user_id = get_current_user_id(authorization)
    
    async def generate():
        start_time = time.time()
        session_id = None
        
        try:
            # セッション作成
            session = ChatSession(user_id=user_id)
            db.add(session)
            db.commit()
            session_id = session.id
            
            # ユーザーメッセージ保存
            msg = ChatMessage(session_id=session_id, role="user", content=request.question)
            db.add(msg)
            db.commit()
            
            # LangGraph実行
            result = None
            async for chunk in agent.run_stream(
                question=request.question,
                use_rerank=request.use_rerank,
                top_k=request.top_k
            ):
                if chunk["type"] == "text":
                    yield f"data: {chunk['data']}\n\n"
                elif chunk["type"] == "done":
                    result = chunk["data"]
            
            if result:
                # 回答保存
                import json as json_lib
                citations_json = json_lib.dumps(result["citations"], ensure_ascii=False)
                msg = ChatMessage(
                    session_id=session_id,
                    role="assistant",
                    content=result["answer"],
                    citations=citations_json
                )
                db.add(msg)
                db.commit()
                
                # 監査ログ
                elapsed = (time.time() - start_time) * 1000
                log = AuditLog(
                    user_id=user_id,
                    action="ask",
                    details=f'{{"question": "{request.question[:50]}...", "elapsed_ms": {elapsed:.2f}}}'
                )
                db.add(log)
                db.commit()
                
                # 最終データ送信
                yield f"event: citations\n"
                yield f"data: {json_lib.dumps(result['citations'], ensure_ascii=False)}\n\n"
                yield f"event: metrics\n"
                yield f"data: {json_lib.dumps(result['metrics'], ensure_ascii=False)}\n\n"
                yield f"event: done\n"
                yield f"data: [DONE]\n\n"
        except Exception as e:
            yield f"event: error\n"
            yield f"data: {str(e)}\n\n"
    
    return EventSourceResponse(generate())

@app.post("/bench", response_model=BenchResponse)
async def bench(
    request: BenchRequest,
    authorization: Optional[str] = Header(None)
):
    """ベンチマーク実行"""
    user_id = get_current_user_id(authorization)
    
    times = []
    cache_hits = 0
    total_tokens = 0
    
    for run in range(request.runs):
        for question in request.questions:
            start = time.time()
            result = await agent.run(
                question=question,
                use_rerank=request.use_rerank,
                top_k=request.top_k
            )
            elapsed = (time.time() - start) * 1000
            times.append(elapsed)
            
            if result["metrics"].get("cache_hit"):
                cache_hits += 1
            total_tokens += result["metrics"].get("est_tokens", 0)
    
    times.sort()
    n = len(times)
    p50 = times[n // 2] if n > 0 else 0
    p95 = times[int(n * 0.95)] if n > 0 else 0
    avg = sum(times) / n if n > 0 else 0
    
    cache_hit_rate = cache_hits / (request.runs * len(request.questions)) if request.questions else 0
    est_cost = (total_tokens / 1000) * 0.002  # 仮の単価
    
    return BenchResponse(
        p50_ms=p50,
        p95_ms=p95,
        avg_ms=avg,
        cache_hit_rate=cache_hit_rate,
        est_tokens=total_tokens,
        est_cost_usd=est_cost
    )

@app.get("/history")
async def get_history(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """会話履歴一覧"""
    user_id = get_current_user_id(authorization)
    sessions = db.query(ChatSession).filter(ChatSession.user_id == user_id).order_by(ChatSession.created_at.desc()).limit(50).all()
    return [{"id": s.id, "created_at": s.created_at.isoformat()} for s in sessions]

@app.get("/history/{session_id}")
async def get_history_detail(
    session_id: int,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """会話詳細"""
    user_id = get_current_user_id(authorization)
    session = db.query(ChatSession).filter(ChatSession.id == session_id, ChatSession.user_id == user_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    messages = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at).all()
    return {
        "session": {"id": session.id, "created_at": session.created_at.isoformat()},
        "messages": [
            {
                "role": m.role,
                "content": m.content,
                "citations": m.citations,
                "created_at": m.created_at.isoformat()
            }
            for m in messages
        ]
    }

@app.get("/audit")
async def get_audit(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
    limit: int = 100
):
    """監査ログ"""
    user_id = get_current_user_id(authorization)
    logs = db.query(AuditLog).filter(AuditLog.user_id == user_id).order_by(AuditLog.created_at.desc()).limit(limit).all()
    return [
        {
            "id": l.id,
            "action": l.action,
            "details": l.details,
            "created_at": l.created_at.isoformat()
        }
        for l in logs
    ]

@app.get("/health")
async def health():
    """ヘルスチェック"""
    return {"status": "ok", "mode": EMBEDDING_MODE, "auth_mode": AUTH_MODE}

