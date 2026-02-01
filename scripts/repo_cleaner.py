# The "Repo Cleaner" Script
# This script will:
#   1. Scan the repository.
#   2. Ignore the .pdf file and any output/temp folders.
#   3. Read all valid .py files.
#   4. Combine them into one CleanOCR_Full_Context.md file.
#   5. Add a "File Source" header to each section so an LLM RAG knows which code belongs to which file.
# run this script from the root of the CleanOCR directory.

import os

# --- CONFIGURATION ---
# Folders to completely ignore
IGNORE_FOLDERS = {
    'output', 'temp', 'venv', 'env', '.git', '__pycache__', 
    'build', 'dist', '.idea', '.vscode', '_archive',
    'output_images',
}

# File extensions to ignore (specifically excluding the PDFs and images)
IGNORE_EXTENSIONS = {'.pdf', '.pyc', '.png', '.jpg', '.jpeg', '.zip', '.json', '.txt'}

# The name of the output file
OUTPUT_FILENAME = "CleanOCR_Full_Context.md"

def is_ignored(path, names):
    """Return a list of ignored files/folders for os.walk."""
    ignored = set()
    for name in names:
        if name in IGNORE_FOLDERS:
            ignored.add(name)
        elif os.path.splitext(name)[1].lower() in IGNORE_EXTENSIONS:
            ignored.add(name)
    return list(ignored)

def generate_repo_dump():
    current_dir = os.getcwd()
    output_path = os.path.join(current_dir, OUTPUT_FILENAME)
    
    print(f"🚀 Scanning directory: {current_dir}")
    print(f"🚫 Ignoring folders: {IGNORE_FOLDERS}")
    print(f"🚫 Ignoring extensions: {IGNORE_EXTENSIONS}")

    with open(output_path, 'w', encoding='utf-8') as outfile:
        # Write a preamble for NotebookLM
        outfile.write(f"# Repository Context: CleanOCR\n")
        outfile.write(f"Generated for NotebookLM analysis.\n\n")

        file_count = 0
        
        for root, dirs, files in os.walk(current_dir):
            # Modify dirs in-place to skip ignored folders
            dirs[:] = [d for d in dirs if d not in IGNORE_FOLDERS]
            
            for file in files:
                # Skip the output file itself and ignored extensions
                if file == OUTPUT_FILENAME:
                    continue
                if os.path.splitext(file)[1].lower() in IGNORE_EXTENSIONS:
                    continue
                
                file_path = os.path.join(root, file)
                relative_path = os.path.relpath(file_path, current_dir)
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as infile:
                        content = infile.read()
                        
                        # Write the file header (Markdown format)
                        outfile.write(f"\n\n---\n")
                        outfile.write(f"## FILE: {relative_path}\n")
                        outfile.write(f"### Path: `{relative_path}`\n")
                        outfile.write(f"```python\n")
                        outfile.write(content)
                        outfile.write(f"\n```\n")
                        
                        print(f"✅ Processed: {relative_path}")
                        file_count += 1
                except Exception as e:
                    print(f"⚠️ Could not read {relative_path}: {e}")

    print(f"\n🎉 Done! Combined {file_count} files into '{OUTPUT_FILENAME}'.")
    print(f"📂 Upload '{OUTPUT_FILENAME}' to NotebookLM.")

if __name__ == "__main__":
    generate_repo_dump()