"""
G-RAG API Server
FastAPI + LangGraph + RAG
"""
import os
import time
import hashlib
import logging
import json
from pathlib import Path
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, Text, DateTime, Float
from sqlalchemy.orm import Session
from datetime import datetime
from jose import jwt
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

try:
    from .langgraph_agent import LangGraphAgent
    from .rag import RAGSystem
    from .auth import verify_token, get_current_user_id, verify_supabase_token, verify_github_token_async
    from .database import get_db, init_db, Base
except ImportError:
    from langgraph_agent import LangGraphAgent
    from rag import RAGSystem
    from auth import verify_token, get_current_user_id, verify_supabase_token, verify_github_token_async
    from database import get_db, init_db, Base

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format='{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}',
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
logger = logging.getLogger("grag.api")

# Environment
AUTH_MODE = os.getenv("AUTH_MODE", "demo")
JWT_SECRET = os.getenv("JWT_SECRET", "demo-secret")
EMBEDDING_MODE = os.getenv("EMBEDDING_MODE", "demo")
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "0"))  # 0 = no limit
RATE_LIMIT_STR = f"{RATE_LIMIT_PER_MINUTE}/minute" if RATE_LIMIT_PER_MINUTE > 0 else "9999/minute"
limiter = Limiter(key_func=get_remote_address)

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
    lifespan=lifespan,
)
app.state.limiter = limiter

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001,http://localhost:3002,http://127.0.0.1:3002").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ルート GET / をミドルウェアで確実に返す（リロードやルート登録順に依存しない）
ROOT_PAYLOAD = {
    "message": "G-RAG API",
    "docs": "/docs",
    "health": "/health",
    "note": "チャットは Web アプリ (yarn dev:web → localhost:3002) から利用してください。",
}


class RootRouteMiddleware:
    """GET / をここで処理して 404 を防ぐ"""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "").rstrip("/") or "/"
        method = scope.get("method", "")
        if path == "/" and method == "GET":
            response = JSONResponse(ROOT_PAYLOAD)
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)


app.add_middleware(RootRouteMiddleware)

# Global exception handler
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.warning("http_error path=%s status=%s detail=%s", request.url.path, exc.status_code, exc.detail)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("unhandled_error path=%s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "type": type(exc).__name__},
    )


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    logger.warning("rate_limit path=%s", request.url.path)
    return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded. Try again later."})


def _root_payload():
    return ROOT_PAYLOAD


@app.get("/")
async def root():
    """ルート: API の案内。"""
    return _root_payload()


@app.get("/info")
async def info():
    """API 案内（/ が使えない環境用）。"""
    return _root_payload()


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
    passcode: Optional[str] = None
    provider: Optional[str] = None  # supabase | github
    access_token: Optional[str] = None  # 外部プロバイダのトークン

class LoginResponse(BaseModel):
    token: str
    user_id: str

# Routes (auth, ask, bench, etc.)
@app.post("/auth/login", response_model=LoginResponse)
@limiter.limit(RATE_LIMIT_STR)
async def login(request: Request, body: LoginRequest, db: Session = Depends(get_db)):
    """認証: DEMO(パスコード) / Supabase / GitHub OAuth"""
    if AUTH_MODE == "demo":
        if not body.passcode:
            raise HTTPException(status_code=400, detail="passcode required in demo mode")
        user_id = hashlib.md5(body.passcode.encode()).hexdigest()[:8]
        token = jwt.encode({"user_id": user_id, "mode": "demo"}, JWT_SECRET, algorithm="HS256")
        log = AuditLog(user_id=user_id, action="login", details='{"mode": "demo"}')
        db.add(log)
        db.commit()
        return LoginResponse(token=token, user_id=user_id)

    if AUTH_MODE == "supabase":
        if not body.access_token:
            raise HTTPException(status_code=400, detail="access_token required for Supabase")
        user_id, email = verify_supabase_token(body.access_token)
        token = jwt.encode({"user_id": user_id, "email": email, "mode": "supabase"}, JWT_SECRET, algorithm="HS256")
        log = AuditLog(user_id=user_id, action="login", details=json.dumps({"mode": "supabase", "email": email}))
        db.add(log)
        db.commit()
        return LoginResponse(token=token, user_id=user_id)

    if AUTH_MODE == "github":
        if not body.access_token:
            raise HTTPException(status_code=400, detail="access_token required for GitHub")
        user_id, login = await verify_github_token_async(body.access_token)
        token = jwt.encode({"user_id": user_id, "login": login, "mode": "github"}, JWT_SECRET, algorithm="HS256")
        log = AuditLog(user_id=user_id, action="login", details=json.dumps({"mode": "github", "login": login}))
        db.add(log)
        db.commit()
        return LoginResponse(token=token, user_id=user_id)

    raise HTTPException(status_code=501, detail=f"Auth mode '{AUTH_MODE}' not implemented")

@app.post("/ask")
@limiter.limit(RATE_LIMIT_STR)
async def ask(
    request: Request,
    body: AskRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """質問に回答（ストリーミング）"""
    user_id = get_current_user_id(authorization)

    async def generate():
        start_time = time.time()
        session_id = None

        try:
            session = ChatSession(user_id=user_id)
            db.add(session)
            db.commit()
            session_id = session.id

            msg = ChatMessage(session_id=session_id, role="user", content=body.question)
            db.add(msg)
            db.commit()

            result = None
            async for chunk in agent.run_stream(
                question=body.question,
                use_rerank=body.use_rerank,
                top_k=body.top_k
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
                    details=f'{{"question": "{body.question[:50]}...", "elapsed_ms": {elapsed:.2f}}}'
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
@limiter.limit(RATE_LIMIT_STR)
async def bench(
    request: Request,
    body: BenchRequest,
    authorization: Optional[str] = Header(None)
):
    """ベンチマーク実行"""
    user_id = get_current_user_id(authorization)

    times = []
    cache_hits = 0
    total_tokens = 0

    for run in range(body.runs):
        for question in body.questions:
            start = time.time()
            result = await agent.run(
                question=question,
                use_rerank=body.use_rerank,
                top_k=body.top_k
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

    cache_hit_rate = cache_hits / (body.runs * len(body.questions)) if body.questions else 0
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

@app.get("/eval/results")
async def get_eval_results(authorization: Optional[str] = Header(None)):
    """評価結果（eval/results.md）を返す。評価は eval/run_eval.py で事前実行すること。"""
    get_current_user_id(authorization)
    # プロジェクトルートの eval/results.md（main.py は apps/api にある）
    repo_root = Path(__file__).resolve().parent.parent.parent
    results_path = repo_root / "eval" / "results.md"
    if not results_path.is_file():
        raise HTTPException(status_code=404, detail="評価結果がありません。eval/run_eval.py を実行してください。")
    try:
        text = results_path.read_text(encoding="utf-8")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"結果の読み込みに失敗しました: {e}")
    return {"markdown": text}


@app.get("/health")
async def health():
    """ヘルスチェック（API 案内も含む）"""
    return {
        "status": "ok",
        "mode": EMBEDDING_MODE,
        "auth_mode": AUTH_MODE,
        "message": "G-RAG API",
        "docs": "/docs",
        "note": "チャットは Web アプリ (yarn dev:web → localhost:3000) から利用してください。",
    }

