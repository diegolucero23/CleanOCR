import easyocr
from pdf2image import convert_from_path, pdfinfo_from_path
import os
import numpy as np

# ==========================================
# CONFIGURATION
# ==========================================

pdf_path = "THE LATTER DAY SAINT’S MESSENGER AND ADVOCATE Volumnes 1 - 24 - Broken OCR.pdf"
output_filename = "deep_learning_ocr_result.txt"

# Poppler path is still needed to convert PDF to Image
poppler_path = r'C:\Program Files\poppler-25.12.0\Library\bin' 

# TEST MODE: Process only first 3 pages to check quality?
TEST_MODE = False

# ==========================================
# MAIN PROCESS
# ==========================================

def run_deep_ocr():
    print("Step 1: Initializing AI Model (This runs once and may take a moment)...")
    # gpu=False ensures it runs on your CPU if you don't have a complex NVIDIA setup.
    # It will download the model files (~100MB) the first time you run it.
    reader = easyocr.Reader(['en'], gpu=False) 

    if not os.path.exists(pdf_path):
        print("Error: PDF not found.")
        return

    # Get page count
    try:
        info = pdfinfo_from_path(pdf_path, poppler_path=poppler_path)
        total_pages = info["Pages"]
        print(f"PDF Loaded: {total_pages} pages found.")
    except Exception as e:
        print(f"Error reading PDF info: {e}")
        return

    limit = 3 if TEST_MODE else total_pages
    print(f"Starting OCR on first {limit} pages..." if TEST_MODE else "Starting full OCR...")

    for i in range(1, limit + 1):
        print(f"Reading Page {i}...", end="\r")
        
        try:
            # 1. Get image of the page
            images = convert_from_path(
                pdf_path, 
                dpi=300, # Higher DPI helps EasyOCR
                first_page=i, 
                last_page=i, 
                poppler_path=poppler_path
            )
            page_image = images[0]
            
            # 2. Convert to format EasyOCR likes (Numpy Array)
            image_np = np.array(page_image)

            # 3. Run AI OCR
            # detail=0 returns just the text
            # paragraph=True combines lines into blocks (Fixes columns!)
            result = reader.readtext(image_np, detail=0, paragraph=True)
            
            # 4. Save results
            with open(output_filename, "a", encoding="utf-8") as f:
                f.write(f"\n\n--- PAGE {i} ---\n\n")
                # Join the paragraphs with newlines
                for paragraph in result:
                    f.write(paragraph + "\n\n")
            
        except Exception as e:
            print(f"\nError on page {i}: {e}")
            continue

    print(f"\n\nDONE! Results saved to: {output_filename}")

if __name__ == "__main__":
    run_deep_ocr()