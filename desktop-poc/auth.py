"""
auth.py — VECTOMEC™ Local User Authentication & Role Management
═══════════════════════════════════════════════════════════════════════════
Local SQLite-backed auth system. No server, no network dependency.
Passwords stored as sha256(salt + password) with a per-user random salt.
Three roles in ascending privilege order:

    designer   Create/edit designs.  Can advance design stage to Preliminary.
    reviewer   All designer capabilities + can advance to Detailed.
    approver   All reviewer capabilities + can advance to Released.
               Also the only role that can create / deactivate users.

Role check helpers are intentionally strict -- callers check the role
explicitly rather than using a catch-all "is_admin" flag.
"""
import hashlib
import json
import os
import secrets
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

ROLES = ("designer", "reviewer", "approver")
_ROLE_LEVEL = {r: i for i, r in enumerate(ROLES)}

STAGE_REQUIRED_ROLE = {
    2: "designer",    # Concept → Preliminary
    3: "reviewer",    # Preliminary → Detailed
    4: "approver",    # Detailed → Released
}


def _hash_password(password: str, salt: str) -> str:
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()


class UserRecord:
    def __init__(self, row: tuple):
        (self.user_id, self.username, self.display_name, self.title,
         self.company, self.role, self._pw_hash, self._salt,
         self.active, self.created_at) = row

    @property
    def role_level(self) -> int:
        return _ROLE_LEVEL.get(self.role, 0)

    def can_advance_to(self, target_stage: int) -> bool:
        required = STAGE_REQUIRED_ROLE.get(target_stage, "approver")
        return self.role_level >= _ROLE_LEVEL[required]

    def can_manage_users(self) -> bool:
        return self.role == "approver"

    def to_dict(self) -> dict:
        return {
            "user_id":      self.user_id,
            "username":     self.username,
            "display_name": self.display_name,
            "title":        self.title,
            "company":      self.company,
            "role":         self.role,
            "active":       bool(self.active),
            "created_at":   self.created_at,
        }

    def __repr__(self):
        return f"<User {self.username} ({self.role})>"


class AuthDB:
    """Thin wrapper around the users SQLite database."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_schema()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id      INTEGER PRIMARY KEY AUTOINCREMENT,
                    username     TEXT    NOT NULL UNIQUE,
                    display_name TEXT    NOT NULL,
                    title        TEXT    NOT NULL DEFAULT '',
                    company      TEXT    NOT NULL DEFAULT '',
                    role         TEXT    NOT NULL CHECK(role IN ('designer','reviewer','approver')),
                    pw_hash      TEXT    NOT NULL,
                    salt         TEXT    NOT NULL,
                    active       INTEGER NOT NULL DEFAULT 1,
                    created_at   TEXT    NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sign_off_log (
                    log_id      INTEGER PRIMARY KEY AUTOINCREMENT,
                    design_file TEXT    NOT NULL,
                    stage       INTEGER NOT NULL,
                    stage_label TEXT    NOT NULL,
                    user_id     INTEGER NOT NULL,
                    username    TEXT    NOT NULL,
                    display_name TEXT   NOT NULL,
                    role        TEXT    NOT NULL,
                    signed_at   TEXT    NOT NULL
                )
            """)
            conn.commit()

    # ── User management ────────────────────────────────────────────────
    def has_any_users(self) -> bool:
        with self._conn() as conn:
            return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] > 0

    def create_user(self, username: str, password: str, display_name: str,
                     title: str, company: str, role: str) -> UserRecord:
        if role not in ROLES:
            raise ValueError(f"Invalid role '{role}'. Must be one of {ROLES}")
        username = username.strip().lower()   # normalize — stored and matched as lowercase
        salt = secrets.token_hex(16)
        pw_hash = _hash_password(password, salt)
        created_at = datetime.now().isoformat()
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO users
                   (username, display_name, title, company, role, pw_hash, salt, active, created_at)
                   VALUES (?,?,?,?,?,?,?,1,?)""",
                (username, display_name, title, company, role, pw_hash, salt, created_at)
            )
            conn.commit()
        user = self.get_by_username(username)
        assert user is not None, f"User '{username}' not found immediately after insert -- database error"
        return user

    def authenticate(self, username: str, password: str) -> Optional[UserRecord]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE LOWER(username)=? AND active=1",
                (username.strip().lower(),)
            ).fetchone()
        if not row:
            return None
        user = UserRecord(tuple(row))
        if _hash_password(password, user._salt) != user._pw_hash:
            return None
        return user

    def get_by_username(self, username: str) -> Optional[UserRecord]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE LOWER(username)=?",
                (username.strip().lower(),)
            ).fetchone()
        return UserRecord(tuple(row)) if row else None

    def get_by_id(self, user_id: int) -> Optional[UserRecord]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE user_id=?", (user_id,)
            ).fetchone()
        return UserRecord(tuple(row)) if row else None

    def list_users(self) -> list[UserRecord]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM users ORDER BY role DESC, username"
            ).fetchall()
        return [UserRecord(tuple(r)) for r in rows]

    def update_user(self, user_id: int, display_name: str, title: str,
                     company: str, role: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE users SET display_name=?, title=?, company=?, role=? WHERE user_id=?",
                (display_name, title, company, role, user_id)
            )
            conn.commit()

    def change_password(self, user_id: int, new_password: str) -> None:
        salt = secrets.token_hex(16)
        pw_hash = _hash_password(new_password, salt)
        with self._conn() as conn:
            conn.execute(
                "UPDATE users SET pw_hash=?, salt=? WHERE user_id=?",
                (pw_hash, salt, user_id)
            )
            conn.commit()

    def deactivate_user(self, user_id: int) -> None:
        with self._conn() as conn:
            conn.execute("UPDATE users SET active=0 WHERE user_id=?", (user_id,))
            conn.commit()

    # ── Sign-off log ───────────────────────────────────────────────────
    def record_sign_off(self, design_file: str, stage: int, stage_label: str,
                         user: UserRecord) -> None:
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO sign_off_log
                   (design_file, stage, stage_label, user_id, username,
                    display_name, role, signed_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (design_file, stage, stage_label, user.user_id, user.username,
                 user.display_name, user.role, datetime.now().isoformat())
            )
            conn.commit()

    def get_sign_offs(self, design_file: str) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM sign_off_log WHERE design_file=? ORDER BY stage",
                (design_file,)
            ).fetchall()
        return [dict(r) for r in rows]


# ── Module-level current session user ─────────────────────────────────────
_current_user: Optional[UserRecord] = None


def set_current_user(user: UserRecord) -> None:
    global _current_user
    _current_user = user


def current_user() -> Optional[UserRecord]:
    return _current_user


def require_role(role: str) -> bool:
    """Returns True if the current user has at least the given role level."""
    if _current_user is None:
        return False
    return _current_user.role_level >= _ROLE_LEVEL.get(role, 99)