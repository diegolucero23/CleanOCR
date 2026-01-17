import os
from pdf2image import convert_from_path
from pdf2image.exceptions import PDFInfoNotInstalledError, PDFPageCountError, PDFSyntaxError

# --- CONFIGURATION ---
# REPLACE THIS with your actual file name
PDF_PATH = "THE LATTER DAY SAINT’S MESSENGER AND ADVOCATE Volumnes 1 - 24 - Broken OCR.pdf"  

OUTPUT_DIR = "output_images"
DPI = 300  # High fidelity
FMT = "png" # Lossless quality

# Your specific path
POPPLER_PATH = r"C:\Program Files\poppler-25.12.0\Library\bin"

# --- SETUP ---
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

def convert_pdf_in_chunks(path, output_folder, dpi=300, chunk_size=10):
    try:
        page_counter = 1
        current_page = 1
        
        print(f"Starting conversion of {path} at {dpi} DPI...")
        print(f"Using Poppler at: {POPPLER_PATH}")

        while True:
            print(f"Processing pages {current_page} to {current_page + chunk_size - 1}...")
            
            try:
                # Convert a specific range of pages
                pages = convert_from_path(
                    path, 
                    dpi=dpi, 
                    first_page=current_page, 
                    last_page=current_page + chunk_size - 1,
                    poppler_path=POPPLER_PATH
                )
            except PDFPageCountError:
                # This usually happens if we ask for a page beyond the end of the file
                # We can assume we are done or check if pages were returned
                if current_page > 1:
                    break
                else:
                    raise

            if not pages:
                break

            for page in pages:
                # Save page as image
                filename = f"page_{page_counter:03}.{FMT}"
                save_path = os.path.join(output_folder, filename)
                page.save(save_path, FMT.upper())
                page_counter += 1
            
            # If we got fewer pages than the chunk size, we've reached the end
            if len(pages) < chunk_size:
                break
                
            current_page += chunk_size
            
        print(f"Done! {page_counter - 1} images saved to folder '{output_folder}'.")

    except (PDFInfoNotInstalledError, PDFPageCountError, PDFSyntaxError) as e:
        print(f"Error: {e}")
        print("Double check that the PDF filename is correct.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

# --- RUN ---
if __name__ == "__main__":
    if os.path.exists(PDF_PATH):
        convert_pdf_in_chunks(PDF_PATH, OUTPUT_DIR, DPI)
    else:
        print(f"Error: Could not find file '{PDF_PATH}'. Please update the PDF_PATH variable in the script.")