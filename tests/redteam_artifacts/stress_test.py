import os
import time

# --- SAFETY CAP ---
# Allocation stops at STRESS_MAX_MB (default 512 MB) so running this outside the
# resource-capped redteam container cannot exhaust host RAM.
DEFAULT_MAX_MB = int(os.getenv("STRESS_MAX_MB", "512"))
CHUNK_MB = 10


def run_stress(max_mb=DEFAULT_MAX_MB, chunk_mb=CHUNK_MB):
    """Allocate memory in chunk_mb steps up to max_mb; return the MB allocated."""
    print(f"🚀 Starting Memory Stress Test (cap: {max_mb} MB)...", flush=True)
    data = []
    try:
        while (len(data) + 1) * chunk_mb <= max_mb:
            data.append(" " * chunk_mb * 1024 * 1024)
            print(f"Used: {len(data) * chunk_mb} MB", flush=True)
            time.sleep(0.5)
        print(f"✅ Reached cap of {max_mb} MB without MemoryError", flush=True)
    except MemoryError:
        print("❌ Caught MemoryError (Soft Limit)", flush=True)
    except Exception as e:
        print(f"❌ Error: {e}", flush=True)
    return len(data) * chunk_mb


if __name__ == "__main__":
    run_stress()
