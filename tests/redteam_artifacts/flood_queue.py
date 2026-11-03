import requests
import concurrent.futures
import time
import sys

# --- SAFETY ---
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

def run_flood():
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
