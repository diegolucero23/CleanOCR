import os
import json
import re
import config  # <--- NEW: Import your central config

# --- CONFIGURATION ---
# We now pull these paths from config.py to ensure consistency across the app
INPUT_FOLDER = config.OCR_JSON_FOLDER
OUTPUT_FOLDER = config.FINAL_MARKDOWN_FOLDER
PUBLICATION_TITLE = "The Latter Day Saint's Messenger And Advocate"
TOTAL_EXPECTED_PAGES = 384
REPAIR_TARGETS = ["page_004", "page_064", "page_110", "page_207", "page_295", "page_335"]

# NEW: A threshold for what constitutes a "suspicious" jump in volume numbers
MAX_VOL_JUMP = 2 

def normalize_number(text):
    """Converts 'Vol 1', 'I', 'No. 3' into a simple integer."""
    if not text: return None
    s = str(text).upper().strip()
    
    romans = {
        'I':1, 'II':2, 'III':3, 'IV':4, 'V':5, 'VI':6, 'VII':7, 'VIII':8, 'IX':9, 'X':10,
        'XI':11, 'XII':12, 'XIII':13, 'XIV':14, 'XV':15, 'XVI':16, 'XVII':17, 'XVIII':18,
        'XIX':19, 'XX':20, 'XXI':21, 'XXII':22, 'XXIII':23, 'XXIV':24
    }
    
    clean = re.sub(r'^(VOL|VOLUME|ISSUE|NO|NUMBER|PART)\.?\s*', '', s)
    if clean in romans: return romans[clean]
    match = re.search(r'\d+', s)
    if match: return int(match.group())
    return None

def get_page_from_filename(filename):
    """Extracts '4' from 'page_004.json'"""
    match = re.search(r'page_(\d+)', filename)
    if match: return int(match.group(1))
    return None

def audit_files(files):
    """Performs a pre-stitch audit to find missing pages."""
    print("--- 1. PRE-FLIGHT AUDIT ---")
    
    found_nums = set()
    found_filenames = set(files)
    
    for f in files:
        p = get_page_from_filename(f)
        if p: found_nums.add(p)

    expected = set(range(1, TOTAL_EXPECTED_PAGES + 1))
    missing = sorted(list(expected - found_nums))
    
    if missing:
        print(f"[!] CRITICAL: Missing {len(missing)} source files.")
        if len(missing) < 15:
            print(f"    Missing Pages: {missing}")
        else:
            print(f"    Missing Pages: {missing[:10]} ... and {len(missing)-10} others.")
    else:
        print("[OK] All 384 page numbers found.")

    print("\n[?] TARGET CHECK:")
    all_targets_ok = True
    for target_base in REPAIR_TARGETS:
        target_file = f"{target_base}.json"
        if target_file in found_filenames:
            print(f"    [FOUND] {target_base}")
        else:
            print(f"    [MISSING] {target_base} <<<< ACTION REQUIRED")
            all_targets_ok = False
            
    if not all_targets_ok:
        print("\n!!! STOPPING: Fix missing targets before stitching.")
        input("Press Enter to continue anyway, or Ctrl+C to abort...")
    else:
        print("\n[OK] Targets verified. Proceeding to stitch.\n")

def main():
    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)

    # Sort naturally (1, 2, ... 10)
    files = sorted(
        [f for f in os.listdir(INPUT_FOLDER) if f.endswith(".json")],
        key=lambda x: int(re.search(r'\d+', x).group()) if re.search(r'\d+', x) else 0
    )
    
    # RUN THE AUDIT
    audit_files(files)

    print("--- 2. STITCHING FILES ---")

    # Initialize State
    current_vol = 1
    current_issue = 1
    
    content_map = {} 
    ordered_keys = []

    for filename in files:
        file_path = os.path.join(INPUT_FOLDER, filename)
        
        with open(file_path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                print(f"[ERROR] Corrupt JSON file skipped: {filename}")
                continue

        meta = data.get("metadata", {})
        
        # --- METADATA & FORWARD FILL ---
        v_norm = normalize_number(meta.get("volume"))
        i_norm = normalize_number(meta.get("issue"))

        # --- NEW LOGIC START: Sanity Check for Volume Jump ---
        if v_norm is not None:
            # If the volume jumps by more than 2 (e.g. 1 to 5), warn us.
            if v_norm > current_vol + MAX_VOL_JUMP:
                print(f"⚠️  [WARNING] Suspicious Volume Jump detected in {filename}:")
                print(f"    Previous Volume: {current_vol} -> New Volume: {v_norm}")
                print(f"    (Keeping previous volume {current_vol} to be safe. Check file manually!)")
                # We do NOT update current_vol here to prevent the hallucination from spreading
            else:
                # If the jump is small (normal), update the volume
                current_vol = v_norm
        # --- NEW LOGIC END ---

        if i_norm is not None: current_issue = i_norm
            
        p_num = meta.get("page_number")
        if not p_num:
            p_num = get_page_from_filename(filename)

        file_key = f"Vol_{current_vol:02d}_Issue_{current_issue:02d}"

        if file_key not in content_map:
            content_map[file_key] = []
            ordered_keys.append(file_key)

        # --- BUILD CONTENT ---
        page_text = data.get("markdown_content") or data.get("full_text") or ""
        
        header = (
            f"\n\n---"
            f"\n## METADATA: {PUBLICATION_TITLE}"
            f"\n**Volume:** {current_vol} | **Issue:** {current_issue} | **Page:** {p_num}"
            f"\n**Source File:** {filename}"
            f"\n---\n\n"
        )

        content_map[file_key].append(header + page_text)

    # --- WRITE OUTPUT ---
    print(f"Writing {len(ordered_keys)} Issue files to '{OUTPUT_FOLDER}/'...")
    for key in ordered_keys:
        out_path = os.path.join(OUTPUT_FOLDER, f"{key}.md")
        pages = content_map[key]
        with open(out_path, "w", encoding="utf-8") as f:
            vol_str = key.split('_')[1]
            iss_str = key.split('_')[3]
            f.write(f"# {PUBLICATION_TITLE}\n## Volume {vol_str}, Issue {iss_str}\n\n")
            f.write("".join(pages))
            
    print("Done.")

if __name__ == "__main__":
    main()