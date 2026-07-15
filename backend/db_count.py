import sqlite3
c = sqlite3.connect("vectrix.db")

total = c.execute("SELECT COUNT(*) FROM materials").fetchone()[0]
distinct_ids = c.execute("SELECT COUNT(DISTINCT mat_id) FROM materials").fetchone()[0]
print(f"total rows:        {total}")
print(f"distinct mat_id:   {distinct_ids}")
print(f"duplicate rows:    {total - distinct_ids}")

# show a few mat_ids that appear more than once
dups = c.execute("""
    SELECT mat_id, COUNT(*) n FROM materials
    GROUP BY mat_id HAVING n > 1 ORDER BY n DESC LIMIT 10
""").fetchall()
if dups:
    print("\nmost-duplicated mat_ids:")
    for mid, n in dups:
        print(f"  {mid}: {n} copies")
else:
    print("\nno duplicate mat_ids — the 864 are all distinct")