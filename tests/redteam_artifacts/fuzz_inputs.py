import requests
import os
import sys
from pathlib import Path

# --- SAFETY INTERLOCK ---
REQUIRED_KEY = "MOCK_KEY_DO_NOT_CHARGE"
ENV_FILE = Path(__file__).resolve().parents[2] / ".env.redteam"
TARGET_PORT = 8001
BASE_URL = f"http://localhost:{TARGET_PORT}"

def check_interlock():
    print("🔒 Checking Safety Interlocks...")
    try:
        with open(ENV_FILE, "r") as f:
            content = f.read()
            if REQUIRED_KEY not in content:
                print(f"❌ FATAL: {ENV_FILE} does not contain {REQUIRED_KEY}")
                sys.exit(1)
        print("✅ Interlock Passed: Environment is mocked.")
    except FileNotFoundError:
        print(f"❌ FATAL: {ENV_FILE} not found. Create it with: cp .env.redteam.example .env.redteam")
        sys.exit(1)

# --- ATTACK VECTORS ---
def attack(name, files, expected_status):
    print(f"⚔️  Attacking: {name} ...", end=" ")
    try:
        response = requests.post(f"{BASE_URL}/upload", files=files, data={"title": "Fuzz"})
        if response.status_code == expected_status:
            print(f"✅ BLOCKED ({response.status_code})")
        elif response.status_code == 500:
            print(f"🔥 CRASH (500) - VULNERABILITY FOUND!")
        else:
            print(f"⚠️  UNEXPECTED ({response.status_code})")
            print(f"    Response: {response.text[:100]}")
    except Exception as e:
        print(f"❌ NETWORK ERROR: {e}")

def run_fuzzing():
    # 1. Fake PDF (Real text file)
    with open("fake.pdf", "wb") as f:
        f.write(b"This is not a PDF")
    
    with open("fake.pdf", "rb") as f:
        attack("Fake Magic Header", {"file": ("fake.pdf", f, "application/pdf")}, 400)

    # 2. Empty File
    with open("empty.pdf", "wb") as f:
        pass
        
    with open("empty.pdf", "rb") as f:
        attack("Zero-Byte File", {"file": ("empty.pdf", f, "application/pdf")}, 400)

    # 3. Shell Injection Filename
    # We want to see if the server sanitizes the filename or lets it crash filesystem logic
    with open("valid.pdf", "wb") as f:
        f.write(b"%PDF-1.4\n%Mock")
        
    with open("valid.pdf", "rb") as f:
        # Note: requests might sanitize this before sending, but let's try
        unsafe_name = "../../etc/passwd.pdf"
        attack("Path Traversal Name", {"file": (unsafe_name, f, "application/pdf")}, 400)

    # 4. Huge Header (Buffer Overflow Attempt)
    with open("huge_header.pdf", "wb") as f:
        f.write(b"A" * 10 * 1024 * 1024) # 10MB "Header"
        
    with open("huge_header.pdf", "rb") as f:
        attack("10MB Garbage Header", {"file": ("huge_header.pdf", f, "application/pdf")}, 400)

    # Cleanup
    for f in ["fake.pdf", "empty.pdf", "valid.pdf", "huge_header.pdf"]:
        if os.path.exists(f):
            os.remove(f)

if __name__ == "__main__":
    check_interlock()
    print(f"🎯 Target: {BASE_URL}")
    run_fuzzing()
