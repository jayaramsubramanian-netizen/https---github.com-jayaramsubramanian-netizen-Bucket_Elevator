"""
reset_password.py — VECTOMEC™ Emergency Password Reset
Run from PowerShell:
    python reset_password.py

Lists all users, then prompts for username and new password.
No login required.

FIX (v2): SQLite = comparison is case-sensitive for text by default.
Previously, searching WHERE username='jsmith' would miss any row
stored as 'JSmith' or 'JAYARAM'. Now uses LOWER(username)=? so it
finds the account regardless of how the username was stored, and also
writes the username back to lowercase to clean up the stored value.
"""
import hashlib
import os
import secrets
import sqlite3
from pathlib import Path


def _db_path():
    appdata = os.environ.get("APPDATA", "")
    if appdata:
        p = Path(appdata) / "VECTOMEC" / "db" / "users.db"
        if p.exists():
            return p
    local = Path("users.db")
    if local.exists():
        return local
    return None


def main():
    db_path = _db_path()
    if not db_path:
        print("ERROR: Could not find users.db")
        print("Expected at: %APPDATA%\\VECTOMEC\\db\\users.db")
        return

    print(f"Found database: {db_path}\n")
    conn = sqlite3.connect(str(db_path))

    users = conn.execute(
        "SELECT user_id, username, display_name, role, active FROM users ORDER BY user_id"
    ).fetchall()

    if not users:
        print("No users found in database.")
        conn.close()
        return

    print("Existing users:")
    for uid, uname, name, role, active in users:
        status = "active" if active else "INACTIVE"
        print(f"  [{uid}] {uname:20s} {name:25s} ({role}) — {status}")

    print()
    username_input = input("Enter username to reset: ").strip().lower()

    # Use LOWER(username)=? so it finds accounts stored with any casing
    # (SQLite's = is case-sensitive by default -- this was the bug)
    row = conn.execute(
        "SELECT user_id, username FROM users WHERE LOWER(username)=?",
        (username_input,)
    ).fetchone()

    if not row:
        print(f"ERROR: User '{username_input}' not found.")
        conn.close()
        return

    user_id, stored_username = row
    if stored_username != username_input:
        print(f"Note: found account stored as '{stored_username}' — will normalize to '{username_input}'")

    new_password = input("Enter new password (min 8 chars): ").strip()
    if len(new_password) < 8:
        print("ERROR: Password must be at least 8 characters.")
        conn.close()
        return

    salt    = secrets.token_hex(16)
    pw_hash = hashlib.sha256((salt + new_password).encode("utf-8")).hexdigest()

    # Reset password AND normalize the stored username to lowercase
    conn.execute(
        "UPDATE users SET pw_hash=?, salt=?, username=? WHERE user_id=?",
        (pw_hash, salt, username_input, user_id)
    )
    conn.commit()
    conn.close()

    print(f"\nPassword for '{username_input}' has been reset successfully.")
    if stored_username != username_input:
        print(f"Username also normalized from '{stored_username}' to '{username_input}'.")
    print("You can now log in to VECTOMEC with the new password.")


if __name__ == "__main__":
    main()