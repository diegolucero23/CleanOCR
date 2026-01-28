import requests
import os
import time

BASE_URL = "http://localhost:8000"

def test_input_sanitization():
    print("\n--- Testing Input Sanitization ---")
    # Create a fake PDF
    with open("fake.pdf", "w") as f:
        f.write("This is not a PDF")
    
    files = {'file': ('fake.pdf', open('fake.pdf', 'rb'), 'application/pdf')}
    try:
        response = requests.post(f"{BASE_URL}/upload", files=files)
        if response.status_code == 400:
            print("SUCCESS: Rejected fake PDF (400 Bad Request)")
        else:
            print(f"FAILURE: Accepted fake PDF with status {response.status_code}")
            print(response.json())
    except Exception as e:
        print(f"FAILURE: Request error: {e}")
    finally:
        files['file'][1].close()
        os.remove("fake.pdf")

def test_smart_caching():
    print("\n--- Testing Smart Caching ---")
    # We need a valid PDF. Let's create a minimal valid PDF (header only)
    # or use an existing one. Minimal PDF header:
    pdf_content = b"%PDF-1.4\n%EOF"
    with open("minimal.pdf", "wb") as f:
        f.write(pdf_content)
    
    # 1. First Upload
    print("Uploading 'minimal.pdf' (1st time)...")
    files1 = {'file': ('minimal.pdf', open('minimal.pdf', 'rb'), 'application/pdf')}
    response1 = requests.post(f"{BASE_URL}/upload", files=files1)
    
    if response1.status_code != 200:
        print(f"FAILURE: First upload failed: {response1.status_code}")
        return

    data1 = response1.json()
    job_id_1 = data1.get("job_id")
    print(f"Job ID 1: {job_id_1}")
    
    # 2. Second Upload (Immediate)
    print("Uploading 'minimal.pdf' (2nd time)...")
    files2 = {'file': ('minimal.pdf', open('minimal.pdf', 'rb'), 'application/pdf')} # Re-open
    response2 = requests.post(f"{BASE_URL}/upload", files=files2)
    
    if response2.status_code != 200:
        print(f"FAILURE: Second upload failed: {response2.status_code}")
        return

    data2 = response2.json()
    status = data2.get("status")
    message = data2.get("message")
    
    if status == "cached":
        print(f"SUCCESS: Smart Caching worked! Status: {status}")
        print(f"Message: {message}")
        print(f"Cached Job ID: {data2.get('job_id')}")
    else:
        print(f"FAILURE: Did not hit cache. Status: {status}")
        print(f"Job ID 2: {data2.get('job_id')}")

    files1['file'][1].close()
    files2['file'][1].close()
    os.remove("minimal.pdf")

if __name__ == "__main__":
    # Wait a bit for server to be up
    print("Waiting 5s for server to stabilize...")
    time.sleep(5)
    
    try:
        test_input_sanitization()
        test_smart_caching()
    except requests.exceptions.ConnectionError:
        print("CRITICAL FAILURE: Could not connect to localhost:8000. Is the server running?")
