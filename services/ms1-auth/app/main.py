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


class UserCreate(BaseModel):
    username: str
    password: str
    role: str
    full_name: Optional[str] = None
    email: Optional[str] = None


class UserUpdate(BaseModel):
    password: Optional[str] = None
    role: Optional[str] = None
    full_name: Optional[str] = None
    email: Optional[str] = None


class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    full_name: Optional[str]
    email: Optional[str]
    created_at: str


class UserProfile(BaseModel):
    username: str
    role: str
    full_name: Optional[str]
    email: Optional[str]


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
        ("security_admin", "admin", "admin1234", "System Administrator", "admin@omnivigil.io"),
    ]
    with _get_conn() as conn:
        with conn.cursor() as cursor:
            # Clean up obsolete roles/users
            cursor.execute("DELETE FROM users WHERE username IN ('technician_a', 'viewer_a')")
            
            for username, role, password, name, email in default_users:
                hashed_password = pwd_context.hash(password)
                cursor.execute(
                    """
                    INSERT INTO users (username, password_hash, role, full_name, email)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (username) DO UPDATE 
                    SET full_name = EXCLUDED.full_name, email = EXCLUDED.email
                    """,
                    (username, hashed_password, role, name, email),
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
                    full_name VARCHAR(255),
                    email VARCHAR(255),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            # Ensure columns exist if table was already created
            cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS full_name VARCHAR(255)")
            cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS email VARCHAR(255)")
        conn.commit()
    _seed_users()


def _get_user_by_username(username: str) -> Optional[dict]:
    with _get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT username, password_hash, role, full_name, email FROM users WHERE username = %s",
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
    user = _get_user_by_username(payload["sub"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserProfile(
        username=user["username"], 
        role=user["role"],
        full_name=user.get("full_name"),
        email=user.get("email")
    )


@app.get("/auth/authorize")
def authorize(required_role: str, payload: dict = Depends(_current_token_payload)) -> dict:
    role = payload["role"]
    allowed = role == required_role or role == "admin"
    return {
        "allowed": allowed,
        "required_role": required_role,
        "current_role": role,
    }


# ==========================================
# User Management CRUD API
# ==========================================

def _require_admin_or_supervisor(payload: dict = Depends(_current_token_payload)) -> dict:
    if payload["role"] not in ["supervisor", "admin"]:
        raise HTTPException(status_code=403, detail="Not authorized to manage users")
    return payload


@app.get("/users", response_model=list[UserResponse])
def get_users(_=Depends(_require_admin_or_supervisor)) -> list[UserResponse]:
    with _get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, username, role, full_name, email, created_at FROM users ORDER BY id ASC")
            users = cursor.fetchall()
            return [
                UserResponse(
                    id=u["id"],
                    username=u["username"],
                    role=u["role"],
                    full_name=u.get("full_name"),
                    email=u.get("email"),
                    created_at=u["created_at"].isoformat() if isinstance(u["created_at"], datetime) else str(u["created_at"])
                ) for u in users
            ]


@app.post("/users", response_model=UserResponse)
def create_user(user: UserCreate, caller=Depends(_require_admin_or_supervisor)) -> UserResponse:
    hashed_password = pwd_context.hash(user.password)
    with _get_conn() as conn:
        with conn.cursor() as cursor:
            try:
                cursor.execute(
                    "INSERT INTO users (username, password_hash, role, full_name, email) VALUES (%s, %s, %s, %s, %s) RETURNING id, created_at",
                    (user.username, hashed_password, user.role, user.full_name, user.email),
                )
                res = cursor.fetchone()
                conn.commit()
                return UserResponse(
                    id=res["id"],
                    username=user.username,
                    role=user.role,
                    full_name=user.full_name,
                    email=user.email,
                    created_at=res["created_at"].isoformat() if isinstance(res["created_at"], datetime) else str(res["created_at"])
                )
            except psycopg.errors.UniqueViolation:
                conn.rollback()
                raise HTTPException(status_code=400, detail="Username already exists")


@app.put("/users/{username}", response_model=UserResponse)
def update_user(username: str, updates: UserUpdate, caller=Depends(_require_admin_or_supervisor)) -> UserResponse:

    with _get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
            existing = cursor.fetchone()
            if not existing:
                raise HTTPException(status_code=404, detail="User not found")

            # Update fields
            new_role = updates.role if updates.role else existing["role"]
            new_hash = pwd_context.hash(updates.password) if updates.password else existing["password_hash"]
            new_name = updates.full_name if updates.full_name is not None else existing["full_name"]
            new_email = updates.email if updates.email is not None else existing["email"]

            cursor.execute(
                "UPDATE users SET role = %s, password_hash = %s, full_name = %s, email = %s WHERE username = %s RETURNING id, created_at",
                (new_role, new_hash, new_name, new_email, username)
            )
            res = cursor.fetchone()
            conn.commit()

            return UserResponse(
                id=res["id"],
                username=username,
                role=new_role,
                full_name=new_name,
                email=new_email,
                created_at=res["created_at"].isoformat() if isinstance(res["created_at"], datetime) else str(res["created_at"])
            )


@app.delete("/users/{username}")
def delete_user(username: str, caller=Depends(_require_admin_or_supervisor)) -> dict:
    if username == "admin":
        raise HTTPException(status_code=400, detail="Cannot delete admin user")

    with _get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM users WHERE username = %s RETURNING id", (username,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="User not found")
        conn.commit()
    return {"status": "deleted", "username": username}