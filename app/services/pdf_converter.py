import os
import re
import concurrent.futures
from pdf2image import convert_from_path, pdfinfo_from_path
from pdf2image.exceptions import PDFInfoNotInstalledError, PDFPageCountError
from app.core import config
from app.core import image_utils

# Matches pdfinfo per-page size values, e.g. "612 x 792 pts (letter)"
_PAGE_SIZE_VALUE_RE = re.compile(r"([\d.]+)\s*x\s*([\d.]+)\s*pts")


def find_oversized_pages(pdf_info: dict, dpi: int) -> list:
    """
    Decompression-bomb guard. Given a pdfinfo_from_path() dict produced with
    first_page/last_page set (which yields one 'Page N size' entry per page),
    return the page numbers whose rasterized pixel count at `dpi` would
    exceed config.MAX_PAGE_PIXELS.

    Raises ValueError if no per-page sizes could be parsed, so callers fail
    closed rather than rasterizing a PDF of unknown geometry.
    """
    oversized = []
    pages_seen = 0
    for key, value in pdf_info.items():
        key_match = re.match(r"Page\s+(\d+)\s+size$", key)
        if not key_match:
            continue
        pages_seen += 1
        size_match = _PAGE_SIZE_VALUE_RE.search(str(value))
        if not size_match:
            raise ValueError(f"Unparseable page size for {key!r}: {value!r}")
        width_px = float(size_match.group(1)) / 72.0 * dpi
        height_px = float(size_match.group(2)) / 72.0 * dpi
        if width_px * height_px > config.MAX_PAGE_PIXELS:
            oversized.append(int(key_match.group(1)))
    if pages_seen == 0:
        raise ValueError("pdfinfo returned no per-page sizes")
    return oversized


def process_pdf_chunk(pdf_path, output_folder, start_page, end_page, poppler_path):
    print(f"Processing pages {start_page} to {end_page}...")
    try:
        pages = convert_from_path(
            pdf_path,
            dpi=config.PDF_RENDER_DPI,
            first_page=start_page,
            last_page=end_page,
            poppler_path=poppler_path,
            timeout=config.PDF_CONVERT_TIMEOUT
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
        # Get total pages plus per-page sizes (first_page/last_page makes
        # pdfinfo emit a 'Page N size' line for every page in the range;
        # a last_page beyond the real page count is clamped by poppler).
        info = pdfinfo_from_path(
            pdf_path,
            poppler_path=config.POPPLER_PATH,
            timeout=config.PDF_INFO_TIMEOUT,
            first_page=1,
            last_page=config.MAX_PDF_PAGES,
        )
        total_pages = info["Pages"]

        # Refuse to rasterize pages that would decompress into huge bitmaps.
        oversized = find_oversized_pages(info, config.PDF_RENDER_DPI)
        if oversized:
            print(
                f"Error: pages {oversized[:10]} of '{pdf_path}' would exceed "
                f"MAX_PAGE_PIXELS ({config.MAX_PAGE_PIXELS}) at "
                f"{config.PDF_RENDER_DPI} DPI. Refusing to convert."
            )
            return []
        if total_pages > config.MAX_PDF_PAGES:
            # The API rejects these at upload; enforce the same cap for PDFs
            # that reach the converter through other entry points (CLI).
            print(
                f"Error: '{pdf_path}' has {total_pages} pages; "
                f"the limit is {config.MAX_PDF_PAGES}."
            )
            return []

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