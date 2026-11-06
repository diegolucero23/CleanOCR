import sqlite3

conn = sqlite3.connect('workspaces/cleanocr.db')
c = conn.cursor()
rows = c.execute('SELECT id, original_filename, total_pages, file_size, duration_seconds, status, created_at FROM jobs ORDER BY created_at DESC LIMIT 25').fetchall()
print(f"{'Pages':<6} | {'Actual (s)':<10} | {'Est (s)':<9} | {'Est (min)':<10} | {'Actual/pg (s)':<14} | {'Filename':<35} | {'Status'}")
print("-" * 110)
for r in rows:
    job_id, fn, pages, size, dur, status, created = r
    if pages and dur is not None:
        est = 600 + pages * 30
        est_min = round(est / 60, 1)
        per_page = round(dur / pages, 2)
        print(f"{pages:<6} | {dur:<10.1f} | {est:<9} | {est_min:<10.1f} | {per_page:<14.2f} | {fn[:35]:<35} | {status}")
    elif pages:
        est = 600 + pages * 30
        est_min = round(est / 60, 1)
        print(f"{pages:<6} | {'None':<10} | {est:<9} | {est_min:<10.1f} | {'N/A':<14} | {fn[:35]:<35} | {status}")

