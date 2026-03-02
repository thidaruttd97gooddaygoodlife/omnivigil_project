from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
import psycopg
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext
from pydantic import BaseModel
from psycopg.rows import dict_row

app = FastAPI(title="MS1 Auth Service", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://omni:omni_password@localhost:5432/auth")
JWT_SECRET = os.getenv("JWT_SECRET", "change_me_in_production")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
bearer_scheme = HTTPBearer()


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: str
    role: str


class VerifyResponse(BaseModel):
    valid: bool
    username: str
    role: str
    exp: int


class UserProfile(BaseModel):
    username: str
    role: str


def _get_conn() -> psycopg.Connection:
    return psycopg.connect(POSTGRES_URL, row_factory=dict_row)


def _create_access_token(username: str, role: str) -> tuple[str, datetime]:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES)
    payload = {
        "sub": username,
        "role": role,
        "exp": expires_at,
        "iat": datetime.now(timezone.utc),
    }
    encoded = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return encoded, expires_at


def _decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc


def _verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def _seed_users() -> None:
    default_users = [
        ("security_admin", "admin", "admin1234"),
        ("technician_a", "technician", "tech1234"),
        ("viewer_a", "viewer", "view1234"),
    ]
    with _get_conn() as conn:
        with conn.cursor() as cursor:
            for username, role, password in default_users:
                hashed_password = pwd_context.hash(password)
                cursor.execute(
                    """
                    INSERT INTO users (username, password_hash, role)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (username) DO NOTHING
                    """,
                    (username, hashed_password, role),
                )
        conn.commit()


def _init_db() -> None:
    with _get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(80) UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role VARCHAR(40) NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
        conn.commit()
    _seed_users()


def _get_user_by_username(username: str) -> Optional[dict]:
    with _get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT username, password_hash, role FROM users WHERE username = %s",
                (username,),
            )
            return cursor.fetchone()


def _current_token_payload(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    return _decode_token(credentials.credentials)


@app.on_event("startup")
def startup() -> None:
    _init_db()


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "ms1-auth"}


@app.post("/auth/login", response_model=LoginResponse)
def login(request: LoginRequest) -> LoginResponse:
    user = _get_user_by_username(request.username)
    if not user or not _verify_password(request.password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token, expires_at = _create_access_token(username=user["username"], role=user["role"])
    return LoginResponse(
        access_token=token,
        expires_at=expires_at.isoformat(),
        role=user["role"],
    )


@app.get("/auth/verify", response_model=VerifyResponse)
def verify(payload: dict = Depends(_current_token_payload)) -> VerifyResponse:
    return VerifyResponse(
        valid=True,
        username=payload["sub"],
        role=payload["role"],
        exp=payload["exp"],
    )


@app.get("/auth/me", response_model=UserProfile)
def me(payload: dict = Depends(_current_token_payload)) -> UserProfile:
    return UserProfile(username=payload["sub"], role=payload["role"])


@app.get("/auth/authorize")
def authorize(required_role: str, payload: dict = Depends(_current_token_payload)) -> dict:
    role = payload["role"]
    allowed = role == required_role or role == "admin"
    return {
        "allowed": allowed,
        "required_role": required_role,
        "current_role": role,
    }