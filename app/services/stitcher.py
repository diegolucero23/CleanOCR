import os
import json
import re
import shutil
from google.genai import types
from app.core import config
from app.core.secrets import redact
from app.services.ocr_factory import get_provider

# --- CONFIGURATION ---
# We now pull these paths from config.py to ensure consistency across the app
INPUT_FOLDER = config.OCR_JSON_FOLDER
OUTPUT_FOLDER = config.FINAL_MARKDOWN_FOLDER
PUBLICATION_TITLE = "The Latter Day Saint's Messenger And Advocate"

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

def load_and_repair_json(file_path):
    """
    Robustly loads JSON from a file, attempting multiple repair strategies:
    1. Standard JSON load (strict=False)
    2. Truncated output repair (finding last '}')
    3. Python string escaping (risky, skipped mostly)
    4. Regex extraction of 'markdown_content' and metadata (Last Resort)
    """
    filename = os.path.basename(file_path)
    with open(file_path, "r", encoding="utf-8") as f:
        raw_content = f.read()

    try:
        # 1. Try Standard Load with strict=False (allows newlines in string)
        return json.loads(raw_content, strict=False)
    except json.JSONDecodeError:
        try:
            # 2. Try Truncating Loop (Finding last '}')
            # Many times the model adds "--- OCR End ---"
            last_brace = raw_content.rfind('}')
            if last_brace == -1: raise ValueError("No closing brace")
            
            clean_content = raw_content[:last_brace+1]
            data = json.loads(clean_content, strict=False)
            print(f"[RECOVERED] Truncated output repair used for {filename}")
            return data

        except (json.JSONDecodeError, ValueError):
            # 3. Skip risky escaping for now as noted in original code
            
            # 4. Fallback: REGEX EXTRACTION (Last Resort)
            print(f"[FALLBACK] Using Regex Extraction for {filename}")
            
            key_marker = '"markdown_content"'
            start_idx = raw_content.find(key_marker)
            
            # Initialize data structure
            data = {"markdown_content": "", "metadata": {}}
            match_found = False
            
            if start_idx != -1:
                # Find the first quote after the key
                val_start = raw_content.find('"', start_idx + len(key_marker))
                if val_start != -1:
                    val_start += 1 # Move inside the quote
                    
                    # Find the last quote in the file
                    val_end = raw_content.rfind('"')
                    
                    if val_end > val_start:
                        extracted_text = raw_content[val_start:val_end]
                        # Manually unescape
                        extracted_text = extracted_text.replace('\\n', '\\n').replace('\\"', '"').replace('\\\\', '\\')
                        
                        data["markdown_content"] = extracted_text
                        match_found = True

            if match_found:
                # Try to snag metadata too
                vol_match = re.search(r'"volume"\s*:\s*(?:null|"?([^"]+)"?)', raw_content)
                iss_match = re.search(r'"issue"\s*:\s*(?:null|"?([^"]+)"?)', raw_content)
                pg_match  = re.search(r'"page_number"\s*:\s*(?:null|"?([^"]+)"?)', raw_content)
                
                data["metadata"] = {
                    "volume": vol_match.group(1) if vol_match else None,
                    "issue": iss_match.group(1) if iss_match else None,
                    "page_number": pg_match.group(1) if pg_match else None
                }
                return data
            else:
                print(f"[ERROR] All repair methods failed for: {filename}")
                return None

def audit_files(files):
    """Performs a pre-stitch audit to find missing pages."""
    print("--- 1. PRE-FLIGHT AUDIT ---")
    
    found_nums = set()
    found_filenames = set(files)
    
    for f in files:
        p = get_page_from_filename(f)
        if p: found_nums.add(p)

    if not found_nums:
        print("[!] No page numbers found in filenames.")
        return

    max_page = max(found_nums)
    expected = set(range(1, max_page + 1))
    missing = sorted(list(expected - found_nums))
    
    print(f"Detected {len(found_nums)} pages (Max Page detected: {max_page})")
    
    if missing:
        print(f"[!] WARNING: Missing {len(missing)} source files within range 1-{max_page}.")
        if len(missing) < 15:
            print(f"    Missing Pages: {missing}")
        else:
            print(f"    Missing Pages: {missing[:10]} ... and {len(missing)-10} others.")
    else:
        print(f"[OK] All {max_page} pages found in sequence.")

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
        print("\n[!] WARNING: Missing target pages. Proceeding anyway (Generic Mode).")
    else:
        print("\n[OK] Targets verified. Proceeding to stitch.\n")

# ... (Helpers remain)

def verify_boundary_text(prev_end_text, next_start_text):
    """
    Two-Pass Verification Step:
    Sends the boundary text between two pages to an LLM to resolve hyphenation
    splits and sentence breaks.
    """
    if config.OCR_TIER == "local":
        # Local tier: use SuryaOCRProvider which routes text-only calls to Gemma.
        try:
            provider = get_provider(None, tier="local")
        except ImportError:
            return prev_end_text + next_start_text
    elif not config.GOOGLE_API_KEY or config.GOOGLE_API_KEY.startswith("MOCK"):
        return prev_end_text + next_start_text
    else:
        provider = get_provider(config.GOOGLE_API_KEY)

    try:
        prompt = (
            "You are an expert OCR editor. The following two text blocks are from "
            "consecutive pages of a scanned historical document. They may be split across "
            "a hyphen or mid-sentence.\n\n"
            "Block 1 (End of Page N-1):\n---\n" + prev_end_text + "\n---\n\n"
            "Block 2 (Start of Page N):\n---\n" + next_start_text + "\n---\n\n"
            "Please merge these two blocks into a single continuous text string, fixing "
            "any hyphenation splits or awkward line breaks at the boundary. "
            "Do not alter the spelling of historical words. Return ONLY the merged text."
        )
        result = provider.generate_content(
            contents=[prompt],
            config=types.GenerateContentConfig(temperature=0.0),
        )
        return (result or "").strip() or prev_end_text + next_start_text
    except Exception as e:
        print(f"LLM Verification failed: {redact(e)}")
        return prev_end_text + next_start_text

def stitch_markdown(input_folder, output_folder, metadata_file=None):
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    # Sort naturally (1, 2, ... 10)
    files = sorted(
        [f for f in os.listdir(input_folder) if f.endswith(".json")],
        key=lambda x: int(re.search(r'\d+', x).group()) if re.search(r'\d+', x) else 0
    )
    
    # RUN THE AUDIT
    audit_files(files)

    print("--- 2. STITCHING FILES (COMBINED) ---")
    
    # ... (Rest of logic needs access to INPUT_FOLDER, so we must replace that global usage too)

    # Initialize State
    current_vol = 1
    current_issue = 1
    last_vol_issue_key = None # (Vol, Issue) tuple
    
    all_pages_content = []

    # --- 0. LOAD METADATA ---
    pub_title = PUBLICATION_TITLE
    citation_block = None

    if metadata_file and os.path.exists(metadata_file):
        try:
            with open(metadata_file, "r", encoding="utf-8") as f:
                meta_json = json.load(f)
                
                # Check for Opt-Out
                if str(meta_json.get("skip_metadata", "")).lower() == "true":
                    print("[INFO] Metadata skipped by user opt-out.")
                    pub_title = meta_json.get("original_filename", "Extracted Document")
                else:
                    # Extract fields
                    user_title = meta_json.get("title")
                    user_date = meta_json.get("date")
                    user_vol = meta_json.get("volume")
                    user_iss = meta_json.get("issue")
                    
                    if user_title: pub_title = user_title
                    
                    # Generate YAML Frontmatter
                    frontmatter = (
                        "---\n"
                        f"title: \"{pub_title}\"\n"
                        f"date: \"{user_date or ''}\"\n"
                        f"volume: \"{user_vol or ''}\"\n"
                        f"issue: \"{user_iss or ''}\"\n"
                        "generated_by: \"CleanOCR\"\n"
                        "---\n\n"
                    )
                    all_pages_content.append(frontmatter)

                    # Generate Citation Block
                    citation_block = (
                        "> [!CITATION]\n"
                        f"> **Source:** {pub_title}"
                    )
                    if user_date: citation_block += f" | **Date:** {user_date}"
                    if user_vol: citation_block += f" | **Vol:** {user_vol}"
                    if user_iss: citation_block += f" | **Iss:** {user_iss}"
                    citation_block += "\n\n"

        except Exception as e:
            print(f"[WARN] Failed to load metadata: {e}")

    # Add Main Title
    all_pages_content.append(f"# {pub_title}\n\n")
    if citation_block:
        all_pages_content.append(citation_block)

    for filename in files:
        file_path = os.path.join(input_folder, filename) # <--- LOCAL
        
        # USE ROBUST LOADER
        data = load_and_repair_json(file_path)
        if not data:
            continue

        meta = data.get("metadata", {})
        
        # --- BUILD PAGE CONTENT ---
        page_text = data.get("markdown_content") or data.get("full_text") or ""
        
        # TWO-PASS VERIFICATION (Context-Aware Boundary Stitching)
        # If we have previous content, let's look at the boundary
        if len(all_pages_content) > 1 and page_text.strip():
            # Get the very last block of text we appended (excluding headers)
            # A rough heuristic: the last 150 words of the previous page, and first 150 of this page
            prev_block = all_pages_content[-1]
            words_prev = prev_block.split()
            words_next = page_text.split()
            
            if len(words_prev) > 0 and len(words_next) > 0:
                prev_sample = " ".join(words_prev[-150:])
                next_sample = " ".join(words_next[:150])
                
                # Check for obvious hyphenation
                if prev_sample.endswith("-"):
                    print(f"[*] Hyphenation detected at boundary of {filename}. Running LLM Verification...")
                    verified_boundary = verify_boundary_text(prev_sample, next_sample)
                    
                    # We inject the LLM's opinion of the boundary into a blockquote for review
                    # (In a fully mature system we'd parse this back into the actual text, 
                    # but for now we append it as a unified crossing block to prevent dataloss)
                    all_pages_content.append(f"\n\n> **[LLM Boundary Fix]**\n> {verified_boundary}\n\n")

        # --- METADATA & FORWARD FILL ---
        v_norm = normalize_number(meta.get("volume"))
        i_norm = normalize_number(meta.get("issue"))

        # Sanity Check for Volume Jump
        if v_norm is not None:
            if v_norm > current_vol + MAX_VOL_JUMP:
                print(f"⚠️  [WARNING] Suspicious Volume Jump detected in {filename}: {current_vol} -> {v_norm}")
            else:
                current_vol = v_norm

        if i_norm is not None: current_issue = i_norm
            
        # The UI DiffViewer requires a strict 1:1 mapping to the physical PDF page
        phys_num = get_page_from_filename(filename)
        
        # Zero-Pad Physical Page Number (001, 002...) for Sorting and UI Sync
        try:
            if phys_num is not None:
                p_num = f"{int(phys_num):03d}"
            else:
                p_num = "000"
        except (ValueError, TypeError):
             p_num = str(phys_num) # Keep as is if it's not a number

        # --- ISSUE HEADER INJECTION ---
        # Check if the Issue has changed since the last page
        current_key = (current_vol, current_issue)
        
        if current_key != last_vol_issue_key:
            # Issue Boundary logic! Insert a big header.
            issue_header = f"\n\n# Volume {current_vol}, Issue {current_issue}\n\n"
            all_pages_content.append(issue_header)
            last_vol_issue_key = current_key

        # Page Separator / Metadata Block
        page_header = (
            f"\n\n----------"
            f"\n## METADATA: {pub_title}"
            f"\n**Volume:** {current_vol} | **Issue:** {current_issue} | **Page:** {p_num}"
            f"\n**Source File:** {filename}"
            f"\n---\n\n"
        )

        all_pages_content.append(page_header + page_text)

    # --- 3. WRITE OUTPUTS ---
    
    # A. Write Full Concatenated File
    out_path = os.path.join(output_folder, "full_extracted_content.md")
    print(f"Writing {len(files)} pages to {out_path}...")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("".join(all_pages_content))

    # B. Write Issue-Based Separated Files (The New Standard)
    issues_dir = os.path.join(output_folder, "issues")
    
    # Idempotency: Clean slate
    if os.path.exists(issues_dir):
        shutil.rmtree(issues_dir)
    os.makedirs(issues_dir)
    
    print(f"Writing Issue-based folders to {issues_dir}...")
    
    # We need to replay the logic to group by issue, but we didn't save the state 100% perfectly in the loop above
    # except in the string buffer.
    # Ideally, we should have stored a list of dicts. 
    # Let's do a quick re-parse of the files respecting the Forward Fill logic again to be safe and clean.
    
    # Reset State for Pass 2
    current_vol = 1
    current_issue = 1
    
    # Buffer to hold markdown content per issue
    # Key: "Vol_001_Issue_001" -> List of strings (page content)
    issue_buffers = {}
    
    for filename in files:
        file_path = os.path.join(input_folder, filename)
        data = load_and_repair_json(file_path)
        if not data: continue
        
        meta = data.get("metadata", {})
        
        # --- RE-APPLY FORWARD FILL LOGIC ---
        v_norm = normalize_number(meta.get("volume"))
        i_norm = normalize_number(meta.get("issue"))

        if v_norm is not None:
             if v_norm > current_vol + MAX_VOL_JUMP:
                 print(f"⚠️  [WARNING] Suspicious Volume Jump detected in {filename}: {current_vol} -> {v_norm}")
             else:
                 current_vol = v_norm

        if i_norm is not None: current_issue = i_norm
            
        phys_num = get_page_from_filename(filename)
        p_num = f"{int(phys_num):03d}" if phys_num is not None else "000"
        
        # Formulate Folder Name
        if current_vol is None or current_issue is None:
            folder_name = "Unassigned"
        else:
            folder_name = f"Vol_{int(current_vol):03d}_Issue_{int(current_issue):03d}"
            
        # Create Folder Structure
        issue_path = os.path.join(issues_dir, folder_name)
        pages_subpath = os.path.join(issue_path, "pages")
        
        if not os.path.exists(pages_subpath):
            os.makedirs(pages_subpath)
            
        # Write Page MD
        raw_text = data.get("markdown_content") or data.get("full_text") or ""
        page_filename = filename.replace(".json", ".md")
        with open(os.path.join(pages_subpath, page_filename), "w", encoding="utf-8") as f:
            f.write(raw_text)
            
        # Write Page JSON (Copy/Dump)
        with open(os.path.join(pages_subpath, filename), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            
        # Append to Issue Buffer
        if folder_name not in issue_buffers:
            issue_buffers[folder_name] = []
            # Add Title for the new file
            issue_buffers[folder_name].append(f"# {folder_name.replace('_', ' ')}\n\n")
            
        # Add Page Header for context in the Issue file
        p_str = f"{int(p_num):03d}" if p_num and str(p_num).isdigit() else str(p_num)
        issue_buffers[folder_name].append(f"\n\n## Page {p_str}\n\n")
        issue_buffers[folder_name].append(raw_text)

    # Write Volume/Issue Summaries
    for folder_name, content_list in issue_buffers.items():
        issue_md_path = os.path.join(issues_dir, folder_name, f"{folder_name}.md")
        with open(issue_md_path, "w", encoding="utf-8") as f:
            f.write("".join(content_list))

    print("Done.")

if __name__ == "__main__":
    stitch_markdown(config.OCR_JSON_FOLDER, config.FINAL_MARKDOWN_FOLDER)