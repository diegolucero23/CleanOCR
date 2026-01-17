# PDF Column Fixer (OCR Repair)

## Overview
This tool is designed to repair PDF text extraction for Retrieval-Augmented Generation (RAG) systems. 

Many historical documents (like newspapers) have multi-column layouts. Standard PDF text layers often read "horizontally" across the page (reading line 1 of column A, then line 1 of column B), resulting in jumbled, nonsensical text. 

This script converts the PDF pages into high-resolution images and uses **Tesseract OCR with Page Segmentation Mode 1** to correctly detect columns and extract text in the proper reading order.

## Prerequisites

### 1. System Tools (Required)
This script relies on two external tools that must be installed on your Windows system:

* **Poppler:** Used to convert PDF pages into images.
    * *Current Path:* `C:\Program Files\poppler-25.12.0\Library\bin`
* **Tesseract OCR:** The engine that reads the text.
    * *Current Path:* `C:\Program Files\Tesseract-OCR\tesseract.exe`

### 2. Python Environment
* **Python Version:** 3.15.2 (or newer)
* **Recommended Location:** `C:\Users\Beast 3\Projects\OCR_Fix`

## Installation

1.  **Install Python Dependencies:**
    Open your terminal in this folder and run:
    ```bash
    pip install pytesseract pdf2image pdfplumber pillow
    ```
    
    *(Note: `pdfplumber` is optional if you are using the Tesseract method, but good to have for testing).*

## Configuration

Open `fix_columns.py` in a text editor (VS Code, Notepad++, etc.) and check the **Configuration Section** at the top:

1.  **Input File:**
    Update the `pdf_path` variable with the filename of the PDF you want to process.
    ```python
    pdf_path = "YOUR_FILE_NAME.pdf"
    ```

2.  **Tool Paths:**
    Ensure these point to the correct locations on your machine.
    ```python
    # Path to Tesseract Executable
    tesseract_location = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

    # Path to Poppler 'bin' folder
    poppler_path = r'C:\Program Files\poppler-25.12.0\Library\bin'
    ```

## Usage

1.  Place your target PDF file in this folder.
2.  Open a terminal (Command Prompt or PowerShell) in this folder.
3.  Run the script:
    ```bash
    python fix_columns.py
    ```
4.  **Wait:** The script will print its progress. Large PDFs may take time as OCR is computationally expensive.

## Output

The script will generate a text file (default: `fixed_text_for_RAG.txt`) in the same directory. 
* **Format:** The text will include `--- PAGE X ---` separators.
* **Validation:** Open the text file and check that sentences flow correctly from the bottom of one column to the top of the next.

## Troubleshooting

* **"Poppler not found" / "Unable to get page count":** * Verify the `poppler_path` in the script. It must point to the folder containing `pdftoppm.exe` (usually the `bin` folder).
* **"Tesseract not found":**
    * Verify `tesseract_location` points explicitly to `tesseract.exe`.
* **"Module not found":**
    * Ensure you ran the pip install command. If it still fails, try `python -m pip install ...`.