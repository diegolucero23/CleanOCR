import os
from pdf2image import convert_from_path
from pdf2image.exceptions import PDFInfoNotInstalledError, PDFPageCountError
import config # <--- NEW IMPORT
import image_utils # <--- NEW IMPORT

def convert_pdf_in_chunks(pdf_path, output_folder, chunk_size=10):
    # output_folder passed as arg
    
    # Check if pdf_path is valid
    if pdf_path is None:
        print("Error: PDF Path is None")
        return
    
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    if not os.path.exists(pdf_path):
        print(f"Error: PDF not found at {pdf_path}")
        return

    try:
        page_counter = 1
        current_page = 1
        print(f"Converting '{pdf_path}'...")

        while True:
            print(f"Processing pages {current_page} to {current_page + chunk_size - 1}...")
            try:
                pages = convert_from_path(
                    pdf_path, 
                    dpi=300, 
                    first_page=current_page, 
                    last_page=current_page + chunk_size - 1,
                    poppler_path=config.POPPLER_PATH # <--- Config
                )
            except PDFPageCountError:
                if current_page > 1: break
                else: raise

            if not pages: break

            for page in pages:
                # Apply Deskew and Padding
                processed_page = image_utils.preprocess_image(page)
                
                filename = f"page_{page_counter:03}.png"
                processed_page.save(os.path.join(output_folder, filename), "PNG")
                page_counter += 1
            
            if len(pages) < chunk_size: break
            current_page += chunk_size
            
        print(f"Done! Saved to '{output_folder}'.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    if config.PDF_SOURCE:
        convert_pdf_in_chunks(config.PDF_SOURCE, config.INPUT_IMAGE_FOLDER)
    else:
        print("Please configure PDF_SOURCE in .env for standalone mode.")