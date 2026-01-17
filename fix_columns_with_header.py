import easyocr
from pdf2image import convert_from_path, pdfinfo_from_path
import os
import numpy as np

# ==========================================
# CONFIGURATION
# ==========================================

pdf_path = "THE LATTER DAY SAINT’S MESSENGER AND ADVOCATE Volumnes 1 - 24 - Broken OCR.pdf"
output_filename = "header_aware_result.txt"
poppler_path = r'C:\Program Files\poppler-25.12.0\Library\bin' 

TEST_MODE = True
HEADER_PERCENTAGE = 0.13  # Top 15% of the page is treated as a full-width header

# ==========================================
# MAIN PROCESS
# ==========================================

def run_smart_split():
    print("Initializing AI...")
    reader = easyocr.Reader(['en'], gpu=False)

    if not os.path.exists(pdf_path):
        print("Error: PDF not found.")
        return

    try:
        info = pdfinfo_from_path(pdf_path, poppler_path=poppler_path)
        total_pages = info["Pages"]
        print(f"PDF Loaded: {total_pages} pages.")
    except Exception:
        total_pages = 100 

    limit = 3 if TEST_MODE else total_pages

    full_text = ""

    for i in range(1, limit + 1):
        print(f"Processing Page {i}...", end="\r")
        
        try:
            images = convert_from_path(
                pdf_path, dpi=300, first_page=i, last_page=i, poppler_path=poppler_path
            )
            img = images[0]
            w, h = img.size
            mid = w // 2
            
            # Calculate where the header ends
            header_cutoff = int(h * HEADER_PERCENTAGE)

            # === CROP 1: THE HEADER (Full Width) ===
            # (left, top, right, bottom)
            header_img = img.crop((0, 0, w, header_cutoff))
            
            # === CROP 2: LEFT COLUMN (Below Header) ===
            # We add +15 pixels to width to catch center margin drift
            left_col_img = img.crop((0, header_cutoff, mid + 15, h))
            
            # === CROP 3: RIGHT COLUMN (Below Header) ===
            # We subtract -15 pixels to catch center margin drift
            right_col_img = img.crop((mid - 15, header_cutoff, w, h))

            # === RUN OCR ===
            # 1. Read Header
            header_res = reader.readtext(np.array(header_img), detail=0, paragraph=True)
            header_txt = " ".join(header_res) # Join on space, not newline, for headers
            
            # 2. Read Left
            left_res = reader.readtext(np.array(left_col_img), detail=0, paragraph=True)
            left_txt = "\n".join(left_res)

            # 3. Read Right
            right_res = reader.readtext(np.array(right_col_img), detail=0, paragraph=True)
            right_txt = "\n".join(right_res)
            
            # === COMBINE ===
            page_content = (
                f"\n\n--- PAGE {i} ---\n"
                f"HEAD: {header_txt}\n"
                f"{'-'*20}\n"
                f"{left_txt}\n"
                f"{right_txt}"
            )
            
            with open(output_filename, "a", encoding="utf-8") as f:
                f.write(page_content)
            
        except Exception as e:
            print(f"\nError on page {i}: {e}")
            continue

    print(f"\n\nDONE! Results saved to: {output_filename}")

if __name__ == "__main__":
    run_smart_split()