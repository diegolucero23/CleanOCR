import re

def debug_file(filename):
    print(f"--- DEBUGGING {filename} ---")
    with open(f"ocr_jsonv2/{filename}", "r", encoding="utf-8") as f:
        content = f.read()
        
    print(f"Total Length: {len(content)}")
    
    # Check for "markdown_content"
    start_idx = content.find('"markdown_content"')
    if start_idx == -1:
        print("ERROR: 'markdown_content' key not found!")
        return

    print(f"Key found at index: {start_idx}")
    snippet = content[start_idx:start_idx+100]
    print(f"Snippet around key: {snippet}")
    
    # Try Regex
    match = re.search(r'"markdown_content"\s*:\s*"(.*?)"(?:\s*,\s*"|\s*})', content, re.DOTALL)
    if match:
        print("REGEX SUCCESS!")
        print(f"Captured Stats: {len(match.group(1))} chars")
    else:
        print("REGEX FAILED!")
        # Print where it might be failing (look for unescaped quotes)
        # We start looking after the key
        val_start = content.find('"', start_idx + 19) # skip "markdown_content": 
        print(f"Value starts around: {val_start}")
        print(f"Next 50 chars of value: {content[val_start+1:val_start+51]}")

debug_file("page_294.json")
debug_file("page_382.json")
