import requests
import uuid
import sys

BASE_URL = "http://localhost:8000"

def test_static_serve():
    print("--- Testing Static File Serving ---")
    
    # 1. Create Dummy PDF
    filename = f"static_test_{uuid.uuid4()}.pdf"
    content = b"%PDF-1.4\n%StaticTest"
    with open(filename, "wb") as f:
        f.write(content)
        
    try:
        # 2. Upload
        print(f"Uploading {filename}...")
        with open(filename, "rb") as f:
            files = {"file": (filename, f, "application/pdf")}
            res = requests.post(f"{BASE_URL}/upload", files=files)
            
        if res.status_code != 200:
            print(f"Upload Failed: {res.text}")
            return False
            
        job_id = res.json()["job_id"]
        print(f"Job ID: {job_id}")
        
        # 3. Try to Download via Static Path
        # The server saves it as {job_id}.pdf
        static_url = f"{BASE_URL}/uploads/{job_id}.pdf"
        print(f"Fetching {static_url}...")
        
        static_res = requests.get(static_url)
        
        if static_res.status_code == 200:
            print("✅ Success! File served.")
            if static_res.content == content:
                 print("✅ Content matches.")
                 return True
            else:
                 print("❌ Content mismatch.")
                 return False
        else:
            print(f"❌ Failed to fetch static file. Status: {static_res.status_code}")
            return False
            
    finally:
        # Cleanup local
        import os
        if os.path.exists(filename):
            os.remove(filename)

if __name__ == "__main__":
    if test_static_serve():
        sys.exit(0)
    else:
        sys.exit(1)
