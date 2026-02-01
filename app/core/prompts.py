# Centralized prompt storage to avoid duplication

OCR_PROMPT = """
You are a data ingestion engine for a Vector Database.
Analyze this document image.

1. **Metadata Extraction**: Identify Volume, Issue, Date, and Page Number.
2. **Text Extraction**:
   - **LAYOUT DETECTION**: Verify if the page is Single Column or Multi-Column. **Do not hallucinate columns** where none exist.
   - **STRICT READING ORDER**:
     - If Single Column: Read strict Top-to-Bottom.
     - If Multi-Column: Read columns sequentially Left-to-Right.
     - **Sentence Continuity**: If the previous page ending implies a mid-sentence break, you **MUST** start the transcription with the completion of that sentence (usually at the top-left), ignoring any large headers or boxes that might visually dominate the page start.
   - **DO NOT** attempt to visually reproduce columns with spacing or vertical bars.
   - Use standard Markdown headers (#, ##) for titles.
   - Ignore running headers and footers (page numbers, issue titles) in the main text body.

Return strictly this JSON structure:
{
    "metadata": {
        "volume": "string or null",
        "issue": "string or null",
        "date": "string or null",
        "page_number": "string or null"
    },
    "layout_type": "string",
    "markdown_content": "string"
}
"""