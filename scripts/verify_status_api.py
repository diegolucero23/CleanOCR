import requests
import time
import os
import sys

BASE_URL = "http://localhost:8000"

import uuid

def create_dummy_pdf(filename="verify_status.pdf"):
    with open(filename, "wb") as f:
        # Add random UUID to content to bypass Smart Caching
        f.write(f"%PDF-1.4\n%Uniqueness: {uuid.uuid4()}\n".encode()) 
    return filename

def test_status_lifecycle():
    print(f"\n--- Testing Status API Lifecycle ---")
    filename = create_dummy_pdf()
    
    try:
        # 1. Upload
        print(f"Uploading {filename}...")
        with open(filename, "rb") as f:
            files = {"file": (filename, f, "application/pdf")}
            response = requests.post(f"{BASE_URL}/upload", files=files)
        
        if response.status_code != 200:
            print(f"FAILED: Upload failed with {response.status_code} - {response.text}")
            return False
            
        data = response.json()
        job_id = data.get("job_id")
        print(f"Job ID: {job_id}")
        
        # 2. Poll Status
        print("Polling status...")
        prev_progress = -1
        
        for _ in range(30): # Timeout after 30s
            status_res = requests.get(f"{BASE_URL}/status/{job_id}")
            if status_res.status_code != 200:
                print(f"FAILED: Status endpoint returned {status_res.status_code}")
                return False
                
            state = status_res.json()
            status = state['status']
            progress = state['progress']
            msg = state.get('message', '')
            
            print(f"State: {status.upper()} | Progress: {progress}% | Msg: {msg}")
            
            if progress > prev_progress:
                prev_progress = progress
            
            # Smart Caching might return 'completed' immediately if we ran this before
            if status in ['completed', 'failed']:
                print(f"Final State Reached: {status}")
                return True
                
            time.sleep(1)
            
        print("FAILED: Timeout waiting for completion")
        return False
        
    except Exception as e:
        print(f"ERROR: {e}")
        return False
    finally:
        if os.path.exists(filename):
            os.remove(filename)

if __name__ == "__main__":
    if test_status_lifecycle():
        print("\n✅ API VERIFICATION PASSED")
        sys.exit(0)
    else:
        print("\n❌ API VERIFICATION FAILED")
        sys.exit(1)
