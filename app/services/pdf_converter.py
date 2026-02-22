import os
import concurrent.futures
from pdf2image import convert_from_path, pdfinfo_from_path
from pdf2image.exceptions import PDFInfoNotInstalledError, PDFPageCountError
from app.core import config
from app.core import image_utils

def process_pdf_chunk(pdf_path, output_folder, start_page, end_page, poppler_path):
    print(f"Processing pages {start_page} to {end_page}...")
    try:
        pages = convert_from_path(
            pdf_path, 
            dpi=300, 
            first_page=start_page, 
            last_page=end_page,
            poppler_path=poppler_path
        )
    except PDFPageCountError:
        return []

    processed_files = []
    for i, page in enumerate(pages):
        processed_page = image_utils.preprocess_image(page)
        page_num = start_page + i
        filename = f"page_{page_num:03}.png"
        filepath = os.path.join(output_folder, filename)
        processed_page.save(filepath, "PNG")
        processed_files.append(filepath)
    return processed_files

def convert_pdf_in_chunks(pdf_path, output_folder, chunk_size=10):
    if pdf_path is None:
        print("Error: PDF Path is None")
        return []
    
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    if not os.path.exists(pdf_path):
        print(f"Error: PDF not found at {pdf_path}")
        return []

    try:
        print(f"Converting '{pdf_path}'...")
        # Get total pages
        info = pdfinfo_from_path(pdf_path, poppler_path=config.POPPLER_PATH)
        total_pages = info["Pages"]
        
        chunks = []
        for start_page in range(1, total_pages + 1, chunk_size):
            end_page = min(start_page + chunk_size - 1, total_pages)
            chunks.append((start_page, end_page))
            
        generated_files = []
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [
                executor.submit(process_pdf_chunk, pdf_path, output_folder, start, end, config.POPPLER_PATH)
                for start, end in chunks
            ]
            for future in concurrent.futures.as_completed(futures):
                try:
                    generated_files.extend(future.result())
                except Exception as exc:
                    print(f"Chunk generation generated an exception: {exc}")
                    
        print(f"Done! Saved to '{output_folder}'.")
        return generated_files

    except Exception as e:
        print(f"Error: {e}")
        return []

if __name__ == "__main__":
    if config.PDF_SOURCE:
        convert_pdf_in_chunks(config.PDF_SOURCE, config.INPUT_IMAGE_FOLDER)
    else:
        print("Please configure PDF_SOURCE in .env for standalone mode.")