import batch_ocr
import os

WORKSPACE_ID = "0f420d4e-8c15-404b-993a-64802aa9291a"
WORKSPACE_DIR = os.path.join(r"c:\Users\dluce\Projects\CleanOCR\workspaces", WORKSPACE_ID)
INPUT_DIR = os.path.join(WORKSPACE_DIR, "images")
OUTPUT_DIR = os.path.join(WORKSPACE_DIR, "ocr_json")

print(f"Debugging OCR for workspace {WORKSPACE_ID}")
print(f"Input: {INPUT_DIR}")
print(f"Output: {OUTPUT_DIR}")

batch_ocr.process_images(INPUT_DIR, OUTPUT_DIR)
