import sqlite3, os

db_path = "screw_conveyor.db"
if not os.path.exists(db_path):
    print(f"FILE NOT FOUND: {db_path}")
else:
    print(f"File size: {os.path.getsize(db_path):,} bytes")
    try:
        con = sqlite3.connect(db_path)
        tables = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        print("Tables:", [t[0] for t in tables])
        for t in tables:
            count = con.execute(f"SELECT count(*) FROM {t[0]}").fetchone()[0]
            print(f"  {t[0]}: {count} rows")
        con.close()
    except Exception as e:
        print(f"Error: {e}")