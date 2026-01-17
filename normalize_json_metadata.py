import os
import json
import re

# --- CONFIGURATION ---
INPUT_FOLDER = "ocr_json"

def normalize_to_string_number(text):
    """
    Parses 'Vol II', 'No. 5', 'IV' and returns a clean string '2', '5', '4'.
    Returns None if no number is found.
    """
    if not text:
        return None
    
    # ensure string and strip
    s = str(text).upper().strip()
    
    # 1. Clean common prefixes
    s_clean = re.sub(r'^(VOL|VOLUME|ISSUE|NO|NUMBER|PART|PAGE)\.?\s*', '', s)
    
    # 2. Roman Numeral Map (1-50)
    romans = {
        'I': 1, 'II': 2, 'III': 3, 'IV': 4, 'V': 5, 
        'VI': 6, 'VII': 7, 'VIII': 8, 'IX': 9, 'X': 10,
        'XI': 11, 'XII': 12, 'XIII': 13, 'XIV': 14, 'XV': 15,
        'XVI': 16, 'XVII': 17, 'XVIII': 18, 'XIX': 19, 'XX': 20,
        'XXI': 21, 'XXII': 22, 'XXIII': 23, 'XXIV': 24, 'XXV': 25,
        'XXVI': 26, 'XXVII': 27, 'XXVIII': 28, 'XXIX': 29, 'XXX': 30,
        'XL': 40, 'L': 50
    }
    
    # Check exact Roman match first
    if s_clean in romans:
        return str(romans[s_clean])
        
    # 3. Extract first digit sequence (handles "October 15" -> "15" if passed strictly as number, 
    # but be careful with dates. Ideally we only pass volume/issue fields here)
    match = re.search(r'\d+', s)
    if match:
        return str(int(match.group())) # int() removes leading zeros, str() converts back
        
    return None

def main():
    if not os.path.exists(INPUT_FOLDER):
        print(f"Error: {INPUT_FOLDER} not found.")
        return

    files = [f for f in os.listdir(INPUT_FOLDER) if f.endswith(".json")]
    print(f"Scanning {len(files)} files for metadata normalization...")
    
    modified_count = 0

    for filename in files:
        filepath = os.path.join(INPUT_FOLDER, filename)
        
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            print(f"[SKIP] Corrupt JSON: {filename}")
            continue
            
        meta = data.get("metadata", {})
        original_meta = meta.copy()
        
        # --- NORMALIZE FIELDS ---
        # 1. Volume
        if meta.get("volume"):
            norm_vol = normalize_to_string_number(meta["volume"])
            if norm_vol: meta["volume"] = norm_vol

        # 2. Issue
        if meta.get("issue"):
            norm_issue = normalize_to_string_number(meta["issue"])
            # Special check: If Issue is "I" but Date suggests later, this script 
            # only fixes formatting. Logic checks belong in audit scripts.
            if norm_issue: meta["issue"] = norm_issue

        # 3. Page Number (Ensure it's a string)
        if meta.get("page_number") is not None:
             meta["page_number"] = str(meta["page_number"])
        
        # --- WRITE BACK IF CHANGED ---
        if meta != original_meta:
            data["metadata"] = meta
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            modified_count += 1
            # Optional: Print changes for the first few to verify
            if modified_count <= 5:
                print(f"Fixed {filename}: {original_meta} -> {meta}")

    print(f"\nDone. Normalized metadata in {modified_count} files.")

if __name__ == "__main__":
    main()