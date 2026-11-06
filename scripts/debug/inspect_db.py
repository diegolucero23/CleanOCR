import sqlite3
import json

conn = sqlite3.connect('workspaces/cleanocr.db')
c = conn.cursor()

print("--- Recent Jobs in DB ---")
rows = c.execute("SELECT id, status, original_filename, file_size, total_pages, processed_pages, model_name, duration_seconds, upload_time, end_time, created_at, error_message FROM jobs ORDER BY created_at DESC LIMIT 15").fetchall()
for r in rows:
    print(r)

print("\n--- Looking specifically for 06ebe4c7 ---")
r06 = c.execute("SELECT * FROM jobs WHERE id LIKE '06ebe4c7%'").fetchone()
print(r06)

print("\n--- Looking specifically for 5446a1b6 ---")
r54 = c.execute("SELECT * FROM jobs WHERE id LIKE '5446a1b6%'").fetchone()
print(r54)

