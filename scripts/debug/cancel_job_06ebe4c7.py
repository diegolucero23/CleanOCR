import sqlite3
import subprocess

# 1. Update SQLite DB
conn = sqlite3.connect('workspaces/cleanocr.db')
c = conn.cursor()
c.execute("""
    UPDATE jobs 
    SET status = 'cancelled', 
        error_message = 'Job cancelled by user: broadsheet 5-column newspaper payload exceeded model timeout on pages 1 and 2; preserved for internal autopsy.'
    WHERE id LIKE '06ebe4c7%'
""")
conn.commit()
print(f"SQLite updated: {c.rowcount} row(s)")

# 2. Update Redis inside Docker container
job_full_id = "06ebe4c7-33dd-404c-99a2-67b5fc305e64"
msg = "Job cancelled by user: broadsheet 5-column newspaper payload exceeded model timeout on pages 1 and 2; preserved for internal autopsy."
cmd1 = ["docker", "exec", "cleanocr-redis-1", "redis-cli", "set", f"cache:{job_full_id}:status", "cancelled"]
cmd2 = ["docker", "exec", "cleanocr-redis-1", "redis-cli", "set", f"cache:{job_full_id}:error", msg]
subprocess.run(cmd1, check=True)
subprocess.run(cmd2, check=True)
print("Redis updated successfully in cleanocr-redis-1")

