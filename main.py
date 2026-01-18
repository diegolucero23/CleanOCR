import sys
import config
import convert_pdf
import batch_ocr
import stitch_to_markdown
import audit_collection
import repair_pages

def print_menu():
    print("\n--- CleanOCR Pipeline ---")
    print("1. Full Pipeline (PDF -> Markdown)")
    print("2. Convert PDF Only")
    print("3. Run Batch OCR (Gemini)")
    print("4. Stitch & Audit")
    print("5. Repair Failed Pages (from log)")
    print("q. Quit")

def run_full_pipeline():
    print("\n>>> STEP 1: CONVERT PDF")
    convert_pdf.convert_pdf_in_chunks()
    
    print("\n>>> STEP 2: BATCH OCR")
    batch_ocr.process_images()
    
    print("\n>>> STEP 3: STITCHING")
    stitch_to_markdown.main()
    
    print("\n>>> STEP 4: AUDIT")
    audit_collection.main()

if __name__ == "__main__":
    while True:
        print_menu()
        choice = input("Select an option: ").strip().lower()
        
        if choice == '1':
            run_full_pipeline()
        elif choice == '2':
            convert_pdf.convert_pdf_in_chunks()
        elif choice == '3':
            batch_ocr.process_images()
        elif choice == '4':
            stitch_to_markdown.main()
            audit_collection.main()
        elif choice == '5':
            # You will need to update repair_pages.py to read from log
            # or just call the function if you updated it.
            # Assuming you might update repair_pages.py similarly to batch_ocr
            if hasattr(repair_pages, 'repair_from_log'):
                repair_pages.repair_from_log()
            else:
                print("Update repair_pages.py to support log-based repair!")
        elif choice == 'q':
            sys.exit()
        else:
            print("Invalid selection.")