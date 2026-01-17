import pytesseract
from pdf2image import convert_from_path
import os
import sys

# ==========================================
# CONFIGURATION
# ==========================================

# 1. INPUT FILE
# Make sure this file is in the same folder as this script!
pdf_path = "THE LATTER DAY SAINT’S MESSENGER AND ADVOCATE Volumnes 1 - 24 - Broken OCR.pdf"
output_filename = "fixed_text_for_RAG.txt"

# 2. TESSERACT CONFIGURATION
# We explicitly point to the .exe so Windows doesn't need it in PATH
# If you installed Tesseract to the default location, this should be correct:
tesseract_location = r'C:\Program Files\tesseract.exe'

# 3. POPPLER CONFIGURATION
# We explicitly point to the 'bin' folder so pdf2image can find it
# Based on your previous message, your poppler is at C:\Program Files\poppler-25.12.0
# We need the 'bin' folder inside it. 
# CHECK: Does 'C:\Program Files\poppler-25.12.0\bin' exist? 
# Or is it 'C:\Program Files\poppler-25.12.0\Library\bin'?
# Update the line below to match the folder that actually contains 'pdftoppm.exe'
poppler_path = r'C:\Program Files\poppler-25.12.0\Library\bin' 

# ==========================================
# SETUP & VALIDATION
# ==========================================

def setup_tools():
    # 1. Validate Tesseract
    if not os.path.exists(tesseract_location):
        print(f"ERROR: Tesseract not found at: {tesseract_location}")
        print("Please check if the folder is 'Tesseract-OCR' or something else in Program Files.")
        return False
    
    # Set the tesseract command
    pytesseract.pytesseract.tesseract_cmd = tesseract_location
    
    # 2. Validate Poppler
    if not os.path.exists(poppler_path):
        print(f"ERROR: Poppler bin folder not found at: {poppler_path}")
        print("Go to that folder in File Explorer and verify where the 'bin' folder is.")
        return False
        
    # 3. Validate PDF
    if not os.path.exists(pdf_path):
        print(f"ERROR: Could not find PDF: {pdf_path}")
        print("Make sure the PDF is in the same folder as this script.")
        return False
        
    return True

# ==========================================
# MAIN PROCESS
# ==========================================

def re_ocr_pdf():
    print("Checking configuration...")
    if not setup_tools():
        return

    print(f"\nConfiguration OK. converting PDF to images...")
    print("(This handles the 'poppler not in PATH' warning for you)")
    
    try:
        # We pass poppler_path explicitly to avoid system PATH issues
        pages = convert_from_path(pdf_path, dpi=300, poppler_path=poppler_path)
    except Exception as e:
        print(f"\nCRITICAL ERROR converting PDF: {e}")
        return

    full_text = ""
    total_pages = len(pages)
    print(f"Success! Found {total_pages} pages. Starting OCR scanning...")

    for i, page_image in enumerate(pages):
        print(f"Processing page {i + 1} of {total_pages}...")
        
        try:
            # --psm 1: Automatic page segmentation with OSD (Detects Columns)
            text = pytesseract.image_to_string(page_image, config='--psm 1')
            
            full_text += f"\n\n--- PAGE {i + 1} ---\n\n"
            full_text += text
        except Exception as e:
            print(f"Error on page {i+1}: {e}")
            continue

    # Save to file
    with open(output_filename, "w", encoding="utf-8") as f:
        f.write(full_text)
    
    print(f"\nDONE! Fixed text saved to: {os.path.join(os.getcwd(), output_filename)}")

if __name__ == "__main__":
    re_ocr_pdf()