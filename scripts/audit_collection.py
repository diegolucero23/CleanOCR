import os
import re
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.core import config

# --- CONFIGURATION ---
MARKDOWN_FOLDER = "CleanOCR_Final"  # Where your stitched files are
TOTAL_EXPECTED_PAGES = 384
MIN_PAGE_CHARS = 200  # Threshold: pages with fewer chars than this are flagged as "Low Content"
REPAIR_TARGETS = config.REPAIR_TARGETS

def main():
    print("--- STARTING DATA INTEGRITY AUDIT (FIXED) ---\n")
    
    # 1. Map all generated Markdown files
    if not os.path.exists(MARKDOWN_FOLDER):
        print(f"Error: Folder '{MARKDOWN_FOLDER}' not found!")
        return

    md_files = [f for f in os.listdir(MARKDOWN_FOLDER) if f.endswith('.md')]
    print(f"Found {len(md_files)} Volume/Issue files.")
    
    found_pages = set()
    low_content_pages = []
    
    # 2. Scan every Markdown file for Source Tags
    for md_file in md_files:
        path = os.path.join(MARKDOWN_FOLDER, md_file)
        
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Check overall file health
        if len(content) < 500:
            print(f"WARNING: File '{md_file}' is suspiciously short ({len(content)} chars).")

        # --- UPDATED REGEX ---
        # Matches: "**Source File:** page_123.json"
        # It is case insensitive and handles the bold markers
        matches = list(re.finditer(r'Source File:\*\*\s*(page_\d+)\.json', content, re.IGNORECASE))
        
        for i, match in enumerate(matches):
            page_id = match.group(1)
            found_pages.add(page_id)
            
            # CALCULATE CONTENT LENGTH FOR THIS PAGE
            start_pos = match.end()
            
            # If there is a next match, stop there; otherwise go to end of file
            if i + 1 < len(matches):
                end_pos = matches[i+1].start()
            else:
                end_pos = len(content)
                
            page_text = content[start_pos:end_pos].strip()
            
            # Threshold Check
            if len(page_text) < MIN_PAGE_CHARS:
                # We show the length to help you decide if it's a real fail or just a short page
                low_content_pages.append(f"{page_id} (in {md_file}) - {len(page_text)} chars")

    # 3. Analyze Results
    print(f"\n--- AUDIT RESULTS (Found {len(found_pages)} unique pages) ---")
    
    # A. Check for Missing Pages
    # Generate expected list: page_001, page_002 ... page_384
    expected_pages = {f"page_{i:03d}" for i in range(1, TOTAL_EXPECTED_PAGES + 1)}
    missing_pages = sorted(list(expected_pages - found_pages))
    
    if missing_pages:
        print(f"\n[!] CRITICAL: {len(missing_pages)} pages are missing entirely:")
        if len(missing_pages) > 20:
             print(", ".join(missing_pages[:20]) + f" ... and {len(missing_pages)-20} more.")
        else:
             print(", ".join(missing_pages))
    else:
        print("\n[OK] All 384 page IDs are present.")

    # B. Check Low Content (Empty Pages)
    if low_content_pages:
        print(f"\n[!] WARNING: {len(low_content_pages)} pages have low text content (<{MIN_PAGE_CHARS} chars):")
        for p in low_content_pages[:10]: # Show first 10 only to avoid spamming
            print(f"    - {p}")
        if len(low_content_pages) > 10:
            print(f"    ... and {len(low_content_pages)-10} others.")
    else:
        print("\n[OK] All pages appear to have sufficient text content.")

    # C. Verify Repair Targets specifically
    print("\n--- REPAIR TARGET VERIFICATION ---")
    all_targets_found = True
    for target in REPAIR_TARGETS:
        if target in found_pages:
            status = "FOUND"
            # Check if it was in the low content list
            if any(target in s for s in low_content_pages):
                status = "FOUND BUT LOW CONTENT"
                all_targets_found = False # Technically found, but might need review
            
            print(f"Target {target}: {status}")
        else:
            print(f"Target {target}: MISSING")
            all_targets_found = False

    if all_targets_found and not missing_pages:
        print("\nSUCCESS: Dataset appears clean and complete.")
    else:
        print("\nFAILURE: Dataset requires attention.")

if __name__ == "__main__":
    main()