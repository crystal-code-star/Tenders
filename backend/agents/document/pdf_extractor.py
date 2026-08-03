"""
PDF Extractor — Enhanced for Tender Intelligence
=================================================
Extracts text from PDFs with scan detection and OCR fallback.
"""

import io
import re
import os
import logging
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any, List
from fastapi import HTTPException

logger = logging.getLogger("pdf_extractor")

# ─── PyMuPDF ──────────────────────────────────────────────
_fitz_available = False

try:
    import fitz
    _fitz_available = True
except ImportError:
    logger.warning("PyMuPDF not installed. Run: pip install PyMuPDF")

# ─── Docling ──────────────────────────────────────────────
_docling_converter = None
_docling_available = False

try:
    from docling.document_converter import DocumentConverter
    _docling_converter = DocumentConverter()
    _docling_available = True
except ImportError:
    logger.warning("Docling not installed. Run: pip install docling")
except Exception as e:
    logger.warning(f"Docling init error: {e}")

# ─── Content classification ───────────────────────────────
_PRICING_KW = ["prix", "bpu", "bp", "dqe", "dp", "quantité", "unitaire", "total",
               "montant", "devise", "dh", "mad", "bordereau"]
_TECH_KW = ["équipement", "matériel", "specification", "technique", "données",
            "performance", "puissance", "débit", "pression", "tension"]
_ADMIN_KW = ["administratif", "conditions", "clauses", "attestation", "certificat",
             "qualification", "référence", "caution", "soumissionnaire", "candidature"]


def _classify_text(text: str) -> str:
    t = text.lower()
    scores = {
        "Pricing": sum(1 for kw in _PRICING_KW if kw in t),
        "Technical": sum(1 for kw in _TECH_KW if kw in t),
        "Administrative": sum(1 for kw in _ADMIN_KW if kw in t),
    }
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "General"


def extract_pdf_structured(file_bytes: bytes, file_name: str = "") -> dict:
    """
    Extract structured data from a PDF file.
    """
    if not _fitz_available:
        raise HTTPException(422, "PyMuPDF (fitz) not installed. Run: pip install PyMuPDF")
    
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
    except Exception as e:
        raise HTTPException(422, f"Invalid PDF file: {e}")
    
    total_pages = len(doc)
    pages = []
    total_images = 0
    pages_with_text = 0
    pages_without_text = 0
    full_text_parts = []
    
    for page_num in range(total_pages):
        page = doc[page_num]
        text = page.get_text("text").strip()
        images = page.get_images(full=True)
        total_images += len(images)
        
        page_data = {
            "page_num": page_num + 1,
            "text": text,
            "char_count": len(text),
            "image_count": len(images),
            "has_text": len(text) >= 50,
            "content_type": _classify_text(text) if text.strip() else "General",
        }
        
        if len(text) >= 50:
            pages_with_text += 1
            full_text_parts.append(text)
        else:
            pages_without_text += 1
        
        pages.append(page_data)
    
    doc.close()
    
    # Build full text
    full_text = "\n\n".join(full_text_parts)
    
    # Determine if scanned
    is_scanned = pages_without_text > 0 and pages_with_text == 0
    needs_ocr = pages_without_text > 0
    scanned_confidence = "high" if is_scanned else ("medium" if pages_without_text > pages_with_text else ("low" if pages_without_text > 0 else "none"))
    
    ocr_warning = ""
    if is_scanned:
        ocr_warning = f"⚠️ PDF entièrement scanné ({total_pages} pages sans texte extractible). L'OCR est nécessaire pour analyser ce document."
    elif pages_without_text > pages_with_text:
        ocr_warning = f"⚠️ PDF majoritairement scanné ({pages_without_text}/{total_pages} pages sans texte)."
    elif pages_without_text > 0:
        ocr_warning = f"⚠️ {pages_without_text}/{total_pages} page(s) scannée(s) détectée(s)."
    
    # Try OCR fallback if needed
    ocr_text = ""
    if needs_ocr and _docling_available:
        try:
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
                tmp.write(file_bytes)
                tmp_path = tmp.name
            try:
                result = _docling_converter.convert(tmp_path)
                ocr_text = result.document.export_to_markdown()
                ocr_text = re.sub(r'#{1,6}\s+', '', ocr_text)
                ocr_text = re.sub(r'\*\*(.*?)\*\*', r'\1', ocr_text)
                ocr_text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', ocr_text)
                if ocr_text.strip():
                    full_text = ocr_text
                    ocr_warning += f" ✅ OCR partiel réussi ({len(ocr_text)} caractères extraits)."
            finally:
                os.unlink(tmp_path)
        except Exception as e:
            logger.warning(f"OCR fallback failed: {e}")
            ocr_warning += " ❌ OCR échoué."
    
    stats = {
        "page_count": total_pages,
        "text_pages": pages_with_text,
        "scanned_pages": pages_without_text,
        "total_images": total_images,
        "total_chars": len(full_text),
        "is_scanned": is_scanned,
        "scanned_confidence": scanned_confidence,
        "needs_ocr": needs_ocr,
        "ocr_applied": bool(ocr_text),
        "ocr_warning": ocr_warning,
    }
    
    return {
        "pages": pages,
        "full_text": full_text,
        "stats": stats,
        "type": "pdf",
        "is_scanned": is_scanned,
        "scanned_confidence": scanned_confidence,
        "needs_ocr": needs_ocr,
        "ocr_warning": ocr_warning,
    }