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
        subprocess.run(["docker-compose", "exec", "redis", "redis-cli", "FLUSHALL"], check=True)
        print("✅ Cache Flushed.")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to flush cache: {e}")
        sys.exit(1)


def flush_job(prefix: str):
    """Delete all Redis keys for a job identified by its first 8 characters.

    Removes both the job-state keys (cache:<job_id>:*) and the file-hash
    dedup key (cache:<sha256>) whose value starts with the same prefix.
    """
    if len(prefix) != 8:
        print(f"❌ --flush-job requires exactly 8 characters (got {len(prefix)})")
        sys.exit(1)

    print(f"🔍 Looking up Redis keys for job prefix: {prefix}...")
    try:
        # 1. Job-state keys: cache:<job_id>:status, :completed_pages, etc.
        result = subprocess.run(
            ["docker-compose", "exec", "-T", "redis", "redis-cli", "KEYS", f"cache:{prefix}*"],
            check=True, capture_output=True, text=True
        )
        job_keys = [k.strip() for k in result.stdout.splitlines() if k.strip()]

        # 2. File-hash dedup key: value is the full job_id starting with prefix
        result2 = subprocess.run(
            ["docker-compose", "exec", "-T", "redis", "redis-cli", "KEYS", "cache:*"],
            check=True, capture_output=True, text=True
        )
        all_keys = [k.strip() for k in result2.stdout.splitlines() if k.strip()]
        hash_keys = []
        for key in all_keys:
            if key in job_keys:
                continue  # already included
            val_result = subprocess.run(
                ["docker-compose", "exec", "-T", "redis", "redis-cli", "GET", key],
                capture_output=True, text=True
            )
            val = val_result.stdout.strip()
            if val.startswith(prefix):
                hash_keys.append(key)

        all_to_delete = job_keys + hash_keys
        if not all_to_delete:
            print(f"⚠️  No Redis keys found for prefix '{prefix}'.")
            return

        print(f"   Job keys  : {job_keys or '(none)'}")
        print(f"   Hash keys : {hash_keys or '(none)'}")

        subprocess.run(
            ["docker-compose", "exec", "-T", "redis", "redis-cli", "DEL"] + all_to_delete,
            check=True
        )
        print(f"✅ Deleted {len(all_to_delete)} key(s) for prefix '{prefix}'.")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to flush job: {e}")
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
    parser.add_argument("-f", "--flush", action="store_true", help="Flush entire Redis cache before starting")
    parser.add_argument("--flush-job", metavar="PREFIX", help="Delete Redis keys for a job by its first 8 characters")
    parser.add_argument("--file", help="Path to PDF file to upload")
    parser.add_argument("--dummy", action="store_true", help="Use a generated dummy PDF")
    parser.add_argument("--port", type=int, default=8000, help="Target port (default: 8000)")

    args = parser.parse_args()

    BASE_URL = f"http://localhost:{args.port}"

    if args.flush:
        flush_redis()

    if args.flush_job:
        flush_job(args.flush_job)

    if args.file or args.dummy:
        success = run_test(args.file, args.dummy)
        if not success:
            sys.exit(1)
