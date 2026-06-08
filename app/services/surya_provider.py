"""
Self-hosted OCR provider: Surya (image → text) + optional Gemma (text → JSON).

Pipeline:
  1. Surya extracts raw text lines with bounding boxes from the image.
  2. Lines are sorted into reading order (row-first, then left-to-right).
  3. Gemma structures the raw text into the CleanOCR JSON schema.
     If Gemma is unavailable, regex heuristics extract metadata and the raw
     text is returned as markdown_content.

For text-only calls (e.g. the stitcher's two-pass boundary fix), the image
path is skipped and the prompt is sent directly to Gemma.
"""

import json
import logging
import re
from typing import Any, Optional

import PIL.Image

from .ocr_interface import OCRProvider
from app.core import prompts as app_prompts

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Surya lazy-load helpers
# ---------------------------------------------------------------------------

_surya_models: Optional[dict] = None


def _load_surya() -> dict:
    """Import and cache Surya models on first use."""
    global _surya_models
    if _surya_models is not None:
        return _surya_models

    try:
        # surya-ocr >= 0.6 ships predictor classes
        from surya.recognition import RecognitionPredictor
        from surya.detection import DetectionPredictor

        logger.info("Loading Surya detection and recognition models…")
        _surya_models = {
            "det": DetectionPredictor(),
            "rec": RecognitionPredictor(),
            "api": "predictors",
        }
        logger.info("Surya models loaded.")
        return _surya_models

    except ImportError:
        pass  # try legacy API below

    try:
        # Legacy surya-ocr < 0.6
        from surya.ocr import run_ocr
        from surya.model.detection.segformer import (
            load_model as load_det_model,
            load_processor as load_det_processor,
        )
        from surya.model.recognition.model import load_model as load_rec_model
        from surya.model.recognition.processor import load_processor as load_rec_processor

        logger.info("Loading Surya models (legacy API)…")
        _surya_models = {
            "run_ocr": run_ocr,
            "det_model": load_det_model(),
            "det_processor": load_det_processor(),
            "rec_model": load_rec_model(),
            "rec_processor": load_rec_processor(),
            "api": "legacy",
        }
        logger.info("Surya models loaded (legacy API).")
        return _surya_models

    except ImportError as exc:
        raise ImportError(
            "surya-ocr is required for OCR_TIER=local. "
            "Install with: pip install -r requirements-local.txt"
        ) from exc


# ---------------------------------------------------------------------------
# Reading-order helpers
# ---------------------------------------------------------------------------

def _assemble_reading_order(text_lines: list, image_width: int) -> str:
    """
    Sort Surya TextLine objects into natural reading order.

    Strategy: bucket lines into horizontal rows (lines whose y1 values are
    within 60 % of the median line height are considered the same row), then
    sort rows top-to-bottom and cells within each row left-to-right.
    """
    if not text_lines:
        return ""

    heights = [tl.bbox[3] - tl.bbox[1] for tl in text_lines]
    median_h = sorted(heights)[len(heights) // 2] if heights else 20
    threshold = max(median_h * 0.6, 5)

    lines_sorted = sorted(text_lines, key=lambda tl: tl.bbox[1])

    rows: list[list] = []
    current_row = [lines_sorted[0]]
    current_y = lines_sorted[0].bbox[1]

    for tl in lines_sorted[1:]:
        if abs(tl.bbox[1] - current_y) <= threshold:
            current_row.append(tl)
        else:
            rows.append(current_row)
            current_row = [tl]
            current_y = tl.bbox[1]
    rows.append(current_row)

    ordered: list[str] = []
    for row in rows:
        for tl in sorted(row, key=lambda tl: tl.bbox[0]):
            if tl.text.strip():
                ordered.append(tl.text.strip())

    return "\n".join(ordered)


def _detect_layout_type(text_lines: list, image_width: int) -> str:
    """Heuristic: if >20 % of lines start in the right half, call it multi-column."""
    if not text_lines or image_width <= 0:
        return "single-column"
    mid = image_width * 0.55
    right_count = sum(1 for tl in text_lines if tl.bbox[0] > mid)
    return "multi-column" if right_count / len(text_lines) > 0.20 else "single-column"


def _extract_metadata(text: str) -> dict:
    """Regex-based metadata extraction for historical newspaper headers."""
    meta: dict = {"volume": None, "issue": None, "date": None, "page_number": None}

    vol = re.search(r"\bvol(?:ume)?\s*[.:]?\s*([ivxlcdmIVXLCDM]+|\d+)", text, re.I)
    if vol:
        meta["volume"] = vol.group(1)

    iss = re.search(
        r"\b(?:no|number|issue|num)\s*[.:]?\s*([ivxlcdmIVXLCDM]+|\d+)", text, re.I
    )
    if iss:
        meta["issue"] = iss.group(1)

    date = re.search(
        r"\b(January|February|March|April|May|June|July|August|"
        r"September|October|November|December)\s+\d{1,2},?\s+\d{4}\b",
        text,
        re.I,
    )
    if date:
        meta["date"] = date.group(0)

    pg = re.search(r"\bpage\s+(\d+)\b", text, re.I)
    if pg:
        meta["page_number"] = pg.group(1)

    return meta


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------


class SuryaOCRProvider(OCRProvider):
    """
    OCRProvider implementation for the self-hosted tier.

    Accepts the same `generate_content(contents, config)` interface as
    GoogleVisionProvider so the rest of the pipeline is unchanged.

    - contents = [str_prompt, PIL.Image]  → OCR mode (Surya + optional Gemma)
    - contents = [str_prompt]             → text-generation mode (Gemma only)
    """

    def generate_content(self, contents: list, config: Any) -> str:
        images = [c for c in contents if isinstance(c, PIL.Image.Image)]
        texts = [c for c in contents if isinstance(c, str)]

        if images:
            return self._ocr_image(images[0], texts[0] if texts else "")
        else:
            return self._generate_text("\n".join(texts))

    # ------------------------------------------------------------------
    # Image OCR path
    # ------------------------------------------------------------------

    def _ocr_image(self, image: PIL.Image.Image, prompt: str) -> str:
        text_lines = self._run_surya(image)
        raw_text = _assemble_reading_order(text_lines, image.width)

        # Attempt Gemma structuring
        try:
            from .gemma_provider import get_gemma_provider
            gemma = get_gemma_provider()
            structuring_prompt = (
                f"{app_prompts.OCR_PROMPT}\n\n"
                "The image has already been processed by Surya OCR. "
                "Use the raw extracted text below — do NOT re-read the image.\n\n"
                f"Raw OCR text:\n{raw_text}"
            )
            return gemma.generate(structuring_prompt, temperature=0.1)
        except Exception as exc:
            logger.warning("Gemma structuring unavailable (%s); using regex fallback.", exc)

        # Regex fallback
        layout = _detect_layout_type(text_lines, image.width)
        meta = _extract_metadata(raw_text)
        return json.dumps(
            {"metadata": meta, "layout_type": layout, "markdown_content": raw_text},
            ensure_ascii=False,
        )

    def _run_surya(self, image: PIL.Image.Image) -> list:
        """Run Surya OCR and return a flat list of TextLine objects."""
        models = _load_surya()

        if models["api"] == "predictors":
            results = models["rec"]([image], [["en"]], models["det"])
            return results[0].text_lines if results else []

        # Legacy API
        results = models["run_ocr"](
            [image],
            [["en"]],
            models["det_model"],
            models["det_processor"],
            models["rec_model"],
            models["rec_processor"],
        )
        return results[0].text_lines if results else []

    # ------------------------------------------------------------------
    # Text-only path (two-pass stitching)
    # ------------------------------------------------------------------

    def _generate_text(self, prompt: str) -> str:
        from .gemma_provider import get_gemma_provider
        return get_gemma_provider().generate(prompt, temperature=0.0)
