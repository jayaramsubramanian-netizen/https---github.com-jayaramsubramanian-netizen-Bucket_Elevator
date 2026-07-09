"""
reset_password.py — VECTOMEC™ Emergency Password Reset
Run from PowerShell:
    python reset_password.py

Lists all users, then prompts for username and new password.
No login required.
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
    # Fallback: look in the current directory
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
    username = input("Enter username to reset: ").strip()

    row = conn.execute(
        "SELECT user_id FROM users WHERE username=?", (username,)
    ).fetchone()

    if not row:
        print(f"ERROR: User '{username}' not found.")
        conn.close()
        return

    new_password = input("Enter new password (min 8 chars): ").strip()
    if len(new_password) < 8:
        print("ERROR: Password must be at least 8 characters.")
        conn.close()
        return

    salt     = secrets.token_hex(16)
    pw_hash  = hashlib.sha256((salt + new_password).encode("utf-8")).hexdigest()

    conn.execute(
        "UPDATE users SET pw_hash=?, salt=? WHERE username=?",
        (pw_hash, salt, username)
    )
    conn.commit()
    conn.close()

    print(f"\nPassword for '{username}' has been reset successfully.")
    print("You can now log in to VECTOMEC with the new password.")

if __name__ == "__main__":
    main()