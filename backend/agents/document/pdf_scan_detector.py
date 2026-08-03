"""
pdf_scan_detector.py — Robust scanned-vs-normal PDF detection.

Why this replaces "count characters from extract_text()":
    extract_text() reconstructs reading order from character positions.
    On multi-column layouts, dense tables, or rotated cells, that
    reconstruction can legitimately fail or return near-empty text even
    though the PDF has a completely normal text layer. A char-count
    threshold then misclassifies real text PDFs as scanned.

This detector instead checks two layout-independent signals per page:
    1. word_count  — via page.get_text("words"), which returns each word
       as (x0, y0, x1, y1, text, ...) directly from the content stream,
       with no reading-order assembly step. Survives tables/columns/
       rotation that break extract_text().
    2. image_coverage — fraction of the page area covered by embedded
       images. A scanned page is, physically, one big raster image.
       High image coverage + near-zero words is a much stronger signal
       than "extract_text() returned little", because it rules out the
       "text exists but extraction failed" false positive.

Requires: pip install pymupdf
"""

import logging
from typing import Any, Dict, List

import fitz  # PyMuPDF

logger = logging.getLogger("pdf_scan_detector")


def _page_signals(page: "fitz.Page") -> Dict[str, float]:
    words = page.get_text("words")  # position-based, not reading-order based
    word_count = len(words)

    page_area = abs(page.rect.width * page.rect.height) or 1.0

    image_area = 0.0
    for img in page.get_images(full=True):
        xref = img[0]
        try:
            rects = page.get_image_rects(xref)
        except Exception:
            rects = []
        for rect in rects:
            image_area += abs(rect.width * rect.height)

    image_coverage = min(image_area / page_area, 1.0)

    return {"word_count": word_count, "image_coverage": image_coverage}


def detect_pdf_type(
    file_bytes: bytes,
    sample_pages: int = 5,
    min_words_per_page: float = 8.0,
    image_coverage_threshold: float = 0.85,
) -> Dict[str, Any]:
    """
    Classify a PDF as scanned (image-based) or normal (has a text layer).

    Decision logic (in order):
      - avg word count per sampled page >= min_words_per_page
            -> NORMAL (there's clearly a text layer, regardless of what
               extract_text() would have produced)
      - avg word count is near zero (< 2) AND max image coverage is high
            -> SCANNED, high confidence (classic full-page-scan case)
      - avg word count is low but nonzero, no dominant image
            -> SCANNED, low confidence — flagged "uncertain" so callers
               can route it to a human/OCR-with-fallback path rather than
               silently guessing
    """
    result: Dict[str, Any] = {
        "is_scanned": False,
        "has_text": False,
        "needs_ocr": False,
        "confidence": "high",
        "detection_method": "word_position+image_coverage",
        "page_count": 0,
        "avg_word_count": 0.0,
        "max_image_coverage": 0.0,
        "per_page": [],
    }

    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
    except Exception as e:
        logger.warning(f"Failed to open PDF: {e}")
        result["confidence"] = "low"
        result["error"] = str(e)
        return result

    try:
        page_count = doc.page_count
        result["page_count"] = page_count
        check_pages = min(sample_pages, page_count) if page_count else 0

        per_page: List[Dict[str, float]] = []
        for i in range(check_pages):
            per_page.append(_page_signals(doc[i]))

        result["per_page"] = per_page

        if not per_page:
            result["confidence"] = "low"
            return result

        avg_words = sum(p["word_count"] for p in per_page) / len(per_page)
        max_image_coverage = max(p["image_coverage"] for p in per_page)

        result["avg_word_count"] = avg_words
        result["max_image_coverage"] = max_image_coverage

        if avg_words >= min_words_per_page:
            result["has_text"] = True
            result["is_scanned"] = False
            result["needs_ocr"] = False
            result["confidence"] = "high"
        elif avg_words < 2 and max_image_coverage >= image_coverage_threshold:
            result["has_text"] = False
            result["is_scanned"] = True
            result["needs_ocr"] = True
            result["confidence"] = "high"
        elif avg_words < min_words_per_page:
            # Low words, but no dominant full-page image to confirm it's a
            # scan (e.g. a near-blank cover page, or a form with sparse
            # text). Don't guess with false confidence — flag it.
            result["has_text"] = avg_words > 0
            result["is_scanned"] = True
            result["needs_ocr"] = True
            result["confidence"] = "uncertain"
        else:
            result["has_text"] = True
            result["is_scanned"] = False
            result["needs_ocr"] = False
            result["confidence"] = "medium"

        return result

    finally:
        doc.close()


if __name__ == "__main__":
    import sys

    for path in sys.argv[1:]:
        with open(path, "rb") as f:
            data = f.read()
        r = detect_pdf_type(data)
        print(
            f"{path}: scanned={r['is_scanned']} confidence={r['confidence']} "
            f"avg_words={r['avg_word_count']:.1f} "
            f"max_img_coverage={r['max_image_coverage']:.2f} "
            f"pages_checked={len(r['per_page'])}/{r['page_count']}"
        )