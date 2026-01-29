import argparse
import subprocess
import requests
import time
import os
import sys
import uuid

BASE_URL = "http://localhost:8000"

def flush_redis():
    print("🧹 Flushing Redis Cache...")
    try:
        # We run the docker command directly
        subprocess.run(["docker-compose", "exec", "redis", "redis-cli", "FLUSHALL"], check=True)
        print("✅ Cache Flushed.")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to flush cache: {e}")
        sys.exit(1)

def create_dummy_pdf(filename="test_upload.pdf", unique=True):
    with open(filename, "wb") as f:
        content = b"%PDF-1.4\n"
        if unique:
             content += f"%Uniqueness: {uuid.uuid4()}\n".encode()
        f.write(content)
    return filename

def run_test(file_path=None, use_dummy=False):
    target_file = file_path
    
    # Validation
    if not target_file and not use_dummy:
        print("Error: Must specify --file or --dummy")
        sys.exit(1)
        
    if use_dummy:
        target_file = create_dummy_pdf()
        
    if not os.path.exists(target_file):
        print(f"Error: File {target_file} not found.")
        sys.exit(1)

    print(f"🚀 Starting Test Upload: {target_file}")
    
    try:
        # 1. Upload
        print(f"Uploading...")
        with open(target_file, "rb") as f:
            files = {"file": (target_file, f, "application/pdf")}
            data = {"title": "Test Upload", "skip_metadata": "true"}
            response = requests.post(f"{BASE_URL}/upload", files=files, data=data)
        
        if response.status_code != 200:
            print(f"❌ Upload Failed: {response.text}")
            return False
            
        data = response.json()
        job_id = data.get("job_id")
        print(f"✅ Uploaded! Job ID: {job_id}")
        
        # 2. Poll
        print("Polling status...")
        prev_progress = -1
        
        for _ in range(300): # 300s timeout -> 5 minutes
            res = requests.get(f"{BASE_URL}/status/{job_id}")
            if res.status_code != 200:
                print(f"❌ Poll Failed: {res.status_code}")
                return False
                
            state = res.json()
            status = state['status']
            progress = state.get('progress', 0)
            msg = state.get('message', '')
            
            # Clear line
            print(f"\rStatus: {status.upper()} | {progress}% | {msg}", end="")
            
            if status in ['completed', 'failed']:
                print(f"\nFinal State: {status}")
                if status == 'completed':
                    if 'markdown' in state:
                        print(f"📝 Markdown Preview: {state['markdown'][:100]}...")
                    else:
                        print("⚠️ No markdown content returned.")
                return status == 'completed'
                
            time.sleep(1)
            
        print("\n❌ Timeout waiting for completion.")
        return False

    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False
    finally:
        if use_dummy and os.path.exists(target_file):
            os.remove(target_file)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CleanOCR Upload Tester")
    parser.add_argument("-f", "--flush", action="store_true", help="Flush Redis cache before starting")
    parser.add_argument("--file", help="Path to PDF file to upload")
    parser.add_argument("--dummy", action="store_true", help="Use a generated dummy PDF")
    
    args = parser.parse_args()
    
    if args.flush:
        flush_redis()
        
    success = run_test(args.file, args.dummy)
    if not success:
        sys.exit(1)
