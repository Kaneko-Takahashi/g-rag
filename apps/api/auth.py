"""
認証モジュール（DEMO / Supabase / GitHub OAuth 対応）
"""
import os
from jose import jwt
from jose.exceptions import ExpiredSignatureError, JWTError
from typing import Optional, Tuple
from fastapi import HTTPException, Header

JWT_SECRET = os.getenv("JWT_SECRET", "demo-secret")
AUTH_MODE = os.getenv("AUTH_MODE", "demo")


def _require_strong_secret_in_production():
    """本番では JWT_SECRET の強度をチェック"""
    if os.getenv("NODE_ENV") == "production" or os.getenv("ENV") == "production":
        secret = os.getenv("JWT_SECRET", "")
        if len(secret) < 32 or secret in ("demo-secret", "your-super-secret-jwt-key-change-in-production"):
            raise HTTPException(
                status_code=500,
                detail="Production requires a strong JWT_SECRET (32+ chars). Set JWT_SECRET in environment.",
            )


def verify_token(token: str) -> dict:
    """JWT検証"""
    _require_strong_secret_in_production()
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


def get_current_user_id(authorization: Optional[str] = None) -> str:
    """Authorizationヘッダーからuser_idを取得"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization required")

    if authorization.startswith("Bearer "):
        token = authorization[7:]
    else:
        token = authorization

    payload = verify_token(token)
    return payload.get("user_id", "unknown")


def verify_supabase_token(access_token: str) -> Tuple[str, str]:
    """
    Supabase のアクセストークンを検証し (user_id, email) を返す。
    SUPABASE_URL, SUPABASE_JWT_SECRET が設定されている必要あり。
    """
    url = os.getenv("SUPABASE_URL")
    secret = os.getenv("SUPABASE_JWT_SECRET")
    if not url or not secret:
        raise HTTPException(
            status_code=501,
            detail="Supabase auth not configured. Set SUPABASE_URL and SUPABASE_JWT_SECRET.",
        )
    try:
        payload = jwt.decode(access_token, secret, algorithms=["HS256"], audience="authenticated")
        user_id = payload.get("sub") or payload.get("user_id") or "unknown"
        email = payload.get("email", "")
        return (user_id, email)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid Supabase token: {e}")


async def verify_github_token_async(access_token: str) -> Tuple[str, str]:
    """GitHub トークン検証（非同期）"""
    if not access_token:
        raise HTTPException(status_code=401, detail="GitHub token required")
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.github.com/user",
                headers={"Authorization": f"Bearer {access_token}"},
            ) as resp:
                if resp.status != 200:
                    raise HTTPException(status_code=401, detail="Invalid GitHub token")
                data = await resp.json()
                return (str(data.get("id", "")), data.get("login", ""))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"GitHub verification failed: {e}")
