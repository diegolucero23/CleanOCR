import pytesseract
from pdf2image import convert_from_path, pdfinfo_from_path
import os
import sys
import gc
from PIL import Image, ImageEnhance, ImageOps

# ==========================================
# CONFIGURATION
# ==========================================

pdf_path = "THE LATTER DAY SAINT’S MESSENGER AND ADVOCATE Volumnes 1 - 24 - Broken OCR.pdf"
output_filename = "enhanced_text_test.txt"

# PATHS
tesseract_location = r'C:\Program Files\tesseract.exe'
poppler_path = r'C:\Program Files\poppler-25.12.0\Library\bin' 

# TEST MODE: Set to True to only process the first 3 pages for a quality check
TEST_MODE = True 

# ==========================================
# IMAGE ENHANCEMENT
# ==========================================

def preprocess_image(image):
    # 1. Convert to Grayscale
    image = image.convert('L')
    
    # 2. Resize/Upscale (2x) to help OCR read small/fuzzy text
    width, height = image.size
    image = image.resize((width * 2, height * 2), Image.Resampling.LANCZOS)
    
    # 3. Increase Contrast (helps separate text from background)
    enhancer = ImageEnhance.Contrast(image)
    image = enhancer.enhance(2.0) # Double the contrast
    
    # 4. Binarize (Force to pure Black and White)
    # This removes gray "fuzz" around letters
    thresh = 150 # Threshold (0-255). Adjust if text is too thin/thick.
    image = image.point(lambda p: 255 if p > thresh else 0)
    
    return image

# ==========================================
# MAIN PROCESS
# ==========================================

def re_ocr_pdf():
    pytesseract.pytesseract.tesseract_cmd = tesseract_location
    
    if not os.path.exists(pdf_path):
        print(f"Error: PDF not found.")
        return

    print("Step 1: Reading PDF structure...")
    try:
        info = pdfinfo_from_path(pdf_path, poppler_path=poppler_path)
        total_pages = info["Pages"]
        print(f"Found {total_pages} pages.")
    except Exception as e:
        print(f"Error reading PDF info: {e}")
        return

    # If testing, only do 3 pages
    limit = 3 if TEST_MODE else total_pages
    print(f"Starting OCR on first {limit} pages..." if TEST_MODE else "Starting full OCR...")

    full_text = ""

    for i in range(1, limit + 1):
        print(f"Processing page {i}...", end="\r")
        
        try:
            # Convert page
            pages = convert_from_path(
                pdf_path, 
                dpi=300, 
                first_page=i, 
                last_page=i, 
                poppler_path=poppler_path
            )
            
            # ENHANCE THE IMAGE
            raw_image = pages[0]
            clean_image = preprocess_image(raw_image)
            
            # Run OCR on the CLEAN image
            # --psm 1 (Auto Layout)
            text = pytesseract.image_to_string(clean_image, config='--psm 1')
            
            # Save incrementally
            with open(output_filename, "a", encoding="utf-8") as f:
                header = f"\n\n--- PAGE {i} (Enhanced) ---\n\n"
                f.write(header + text)

            del pages, raw_image, clean_image, text
            gc.collect()
            
        except Exception as e:
            print(f"\nError on page {i}: {e}")
            continue

    print(f"\n\nDONE! Check the file '{output_filename}' to see if it's readable now.")

if __name__ == "__main__":
    re_ocr_pdf()