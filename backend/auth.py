"""Accounts: password hashing, sessions, and the /api/auth routes.

Passwords are never stored or logged. We keep only a salted PBKDF2-SHA256 hash:
  new format:     pbkdf2_sha256$<iterations>$<salt>$<hex digest>
  seed (legacy):  pbkdf2_sha256$<salt>$<hex digest>   (120,000 iterations)
Legacy hashes are upgraded to the new format the next time that user logs in.

Sessions are random tokens sent in an HttpOnly cookie; the DB stores only the
SHA-256 of each token, so a leaked database cannot be used to hijack sessions.
"""

import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Cookie, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator

from db import connect_rw as connect

ALGORITHM = "pbkdf2_sha256"
ITERATIONS = 600_000  # OWASP 2023 guidance for PBKDF2-HMAC-SHA256
LEGACY_ITERATIONS = 120_000  # what the seed database used
MIN_PASSWORD, MAX_PASSWORD = 8, 128
SESSION_COOKIE = "cc_session"
SESSION_DAYS = 7
# Set COOKIE_SECURE=1 when served over HTTPS so the cookie never travels in plain text.
COOKIE_SECURE = os.getenv("COOKIE_SECURE") == "1"

MAX_FAILURES, FAILURE_WINDOW_SECONDS = 5, 15 * 60
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

router = APIRouter(prefix="/api/auth", tags=["auth"])


# ---------- password hashing ----------

def _pbkdf2(password: str, salt: str, iterations: int) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), iterations).hex()


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)  # unique random salt per user
    return f"{ALGORITHM}${ITERATIONS}${salt}${_pbkdf2(password, salt, ITERATIONS)}"


def verify_password(password: str, stored: str) -> bool:
    parts = stored.split("$")
    if parts[0] != ALGORITHM:
        return False
    if len(parts) == 4:
        _, iterations, salt, digest = parts
        iterations = int(iterations)
    elif len(parts) == 3:
        _, salt, digest = parts
        iterations = LEGACY_ITERATIONS
    else:
        return False
    # Constant-time compare so response timing does not leak how close a guess was.
    return hmac.compare_digest(_pbkdf2(password, salt, iterations), digest)


def needs_rehash(stored: str) -> bool:
    parts = stored.split("$")
    return len(parts) != 4 or int(parts[1]) < ITERATIONS


# Used when the email does not exist, so unknown and known emails take the same time.
_DUMMY_HASH = hash_password(secrets.token_hex(16))


# ---------- database ----------

def init_auth_tables() -> None:
    with connect() as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id),
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                expires_at TEXT NOT NULL
            )"""
        )
        conn.execute("DELETE FROM sessions WHERE expires_at < datetime('now')")


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def public_user(row: sqlite3.Row) -> dict:
    # Only these fields ever leave the server; password_hash never does.
    return {
        "user_id": row["id"],
        "first_name": row["first_name"] or row["name"].split(" ")[0],
        "last_name": row["last_name"] or "",
        "email": row["email"],
        "member_since": row["created_at"],
    }


def user_for_token(token: str | None) -> dict | None:
    if not token:
        return None
    with connect() as conn:
        row = conn.execute(
            """SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id
               WHERE s.token_hash = ? AND s.expires_at > datetime('now')""",
            (_token_hash(token),),
        ).fetchone()
    return public_user(row) if row else None


def _start_session(response: Response, user_id: int) -> None:
    token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)
    with connect() as conn:
        conn.execute(
            "INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
            (_token_hash(token), user_id, expires.strftime("%Y-%m-%d %H:%M:%S")),
        )
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_DAYS * 24 * 3600,
        httponly=True,  # page scripts (and injected scripts) cannot read it
        samesite="lax",  # not sent on cross-site POSTs, which blocks CSRF
        secure=COOKIE_SECURE,
        path="/",
    )


# ---------- brute-force protection ----------

_failures: dict[str, deque[float]] = defaultdict(deque)


def _throttle_key(request: Request, email: str) -> str:
    host = request.client.host if request.client else "unknown"
    return f"{host}|{email}"


def _check_throttle(key: str) -> None:
    attempts = _failures[key]
    now = time.monotonic()
    while attempts and now - attempts[0] > FAILURE_WINDOW_SECONDS:
        attempts.popleft()
    if len(attempts) >= MAX_FAILURES:
        raise HTTPException(429, "Too many failed attempts. Please wait 15 minutes and try again.")


# ---------- request models ----------

def _clean_email(value: str) -> str:
    value = value.strip().lower()
    if len(value) > 254 or not EMAIL_RE.match(value):
        raise ValueError("Enter a valid email address.")
    return value


class SignupIn(BaseModel):
    first_name: str = Field(min_length=1, max_length=50)
    last_name: str = Field(min_length=1, max_length=50)
    email: str
    password: str = Field(min_length=MIN_PASSWORD, max_length=MAX_PASSWORD)
    confirm_password: str

    @field_validator("first_name", "last_name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Name is required.")
        return v

    @field_validator("email")
    @classmethod
    def valid_email(cls, v: str) -> str:
        return _clean_email(v)


class LoginIn(BaseModel):
    email: str
    password: str = Field(max_length=MAX_PASSWORD)

    @field_validator("email")
    @classmethod
    def norm_email(cls, v: str) -> str:
        return v.strip().lower()


# ---------- routes ----------

@router.post("/signup", status_code=201)
def signup(body: SignupIn, response: Response) -> dict:
    if body.password != body.confirm_password:
        raise HTTPException(400, "Passwords do not match.")
    try:
        with connect() as conn:
            cur = conn.execute(
                "INSERT INTO users (name, first_name, last_name, email, password_hash) VALUES (?, ?, ?, ?, ?)",
                (
                    f"{body.first_name} {body.last_name}",
                    body.first_name,
                    body.last_name,
                    body.email,
                    hash_password(body.password),
                ),
            )
            row = conn.execute("SELECT * FROM users WHERE id = ?", (cur.lastrowid,)).fetchone()
    except sqlite3.IntegrityError:
        raise HTTPException(409, "An account with that email already exists. Try logging in.")
    _start_session(response, row["id"])
    return {"user": public_user(row)}


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response) -> dict:
    key = _throttle_key(request, body.email)
    _check_throttle(key)
    with connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (body.email,)).fetchone()
        ok = verify_password(body.password, row["password_hash"] if row else _DUMMY_HASH) and row is not None
        if ok and needs_rehash(row["password_hash"]):
            conn.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(body.password), row["id"])
            )
    if not ok:
        _failures[key].append(time.monotonic())
        # Same message whether the email or the password was wrong.
        raise HTTPException(401, "Incorrect email or password.")
    _failures.pop(key, None)
    _start_session(response, row["id"])
    return {"user": public_user(row)}


@router.post("/logout")
def logout(response: Response, cc_session: str | None = Cookie(None)) -> dict:
    if cc_session:
        with connect() as conn:
            conn.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(cc_session),))
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
def me(cc_session: str | None = Cookie(None)) -> dict:
    return {"user": user_for_token(cc_session)}
