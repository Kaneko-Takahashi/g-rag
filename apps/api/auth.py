"""
認証モジュール（DEMO/将来拡張用）
"""
import os
from jose import jwt
from jose.exceptions import ExpiredSignatureError, JWTError
from typing import Optional
from fastapi import HTTPException, Header

JWT_SECRET = os.getenv("JWT_SECRET", "demo-secret")
AUTH_MODE = os.getenv("AUTH_MODE", "demo")

def verify_token(token: str) -> dict:
    """JWT検証"""
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

