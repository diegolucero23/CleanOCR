import stitch_to_markdown
import os

WORKSPACE_ID = "0f420d4e-8c15-404b-993a-64802aa9291a"
WORKSPACE_DIR = os.path.join(r"c:\Users\dluce\Projects\CleanOCR\workspaces", WORKSPACE_ID)
OCR_JSON_DIR = os.path.join(WORKSPACE_DIR, "ocr_json")
OUTPUT_DIR = os.path.join(WORKSPACE_DIR, "output")
METADATA_FILE = os.path.join(WORKSPACE_DIR, "metadata.json")

print(f"Stitching for workspace {WORKSPACE_ID}")
print(f"Input: {OCR_JSON_DIR}")
print(f"Output: {OUTPUT_DIR}")

stitch_to_markdown.stitch_markdown(OCR_JSON_DIR, OUTPUT_DIR, METADATA_FILE)
