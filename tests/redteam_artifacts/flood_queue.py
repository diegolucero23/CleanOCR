import requests
import concurrent.futures
import time
import sys
from pathlib import Path

# --- SAFETY INTERLOCK ---
REQUIRED_KEY = "MOCK_KEY_DO_NOT_CHARGE"
ENV_FILE = Path(__file__).resolve().parents[2] / ".env.redteam"
TARGET_PORT = 8001
BASE_URL = f"http://localhost:{TARGET_PORT}"
JOB_COUNT = 50

def submit_job(i):
    # Dummy PDF content
    files = {"file": (f"flood_{i}.pdf", b"%PDF-1.4\n%Mock", "application/pdf")}
    try:
        res = requests.post(f"{BASE_URL}/upload", files=files, data={"title": f"Flood {i}"})
        return res.status_code
    except:
        return 0

def check_interlock():
    """Abort unless .env.redteam exists and pins the mock kill-switch key."""
    print("🔒 Checking Safety Interlocks...")
    try:
        content = Path(ENV_FILE).read_text()
    except FileNotFoundError:
        print(f"❌ FATAL: {ENV_FILE} not found. Create it with: cp .env.redteam.example .env.redteam")
        sys.exit(1)
    if f"GOOGLE_API_KEY={REQUIRED_KEY}" not in content:
        print(f"❌ FATAL: {ENV_FILE} does not set GOOGLE_API_KEY={REQUIRED_KEY}. Aborting.")
        sys.exit(1)
    print("✅ Interlock Passed: Environment is mocked.")

def run_flood():
    check_interlock()
    print(f"🌊 Starting Flood: {JOB_COUNT} requests...")
    start = time.time()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(submit_job, range(JOB_COUNT)))
        
    duration = time.time() - start
    print(f"✅ Finished in {duration:.2f}s")
    
    success = results.count(200)
    failed = len(results) - success
    print(f"📊 Results: {success} Success | {failed} Failed")
    print(f"🚀 RPS: {JOB_COUNT / duration:.2f}")

if __name__ == "__main__":
    run_flood()
