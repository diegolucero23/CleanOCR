import time
import sys

print("🚀 Starting Memory Stress Test...", flush=True)
data = []
try:
    while True:
        # Appending 10MB chunks
        chunk = " " * 10 * 1024 * 1024
        data.append(chunk)
        print(f"Used: {len(data) * 10} MB", flush=True)
        time.sleep(0.5)
except MemoryError:
    print("❌ Caught MemoryError (Soft Limit)", flush=True)
except Exception as e:
    print(f"❌ Error: {e}", flush=True)
