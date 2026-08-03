"""
dce_classifier.py — Complete DCE file classifier with:
- Filename matching (AVIS, RC, CPS, BP)
- File type detection (PDF, DOCX, DOC, XLSX, XLS, etc.)
- PDF type detection using PyMuPDF (word positions + image coverage)
- Content fallback for all file types
"""

import io
import logging
import re
import unicodedata
import zipfile
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

# Import the new PDF detector
from pdf_scan_detector import detect_pdf_type

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("dce_classifier")
logger.setLevel(logging.INFO)


# ─── Normalization ──────────────────────────────────────────────────────

def _normalize(text: str) -> str:
    """Lowercase + strip accents."""
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", text)
    ascii_only = nfkd.encode("ascii", "ignore").decode("ascii")
    return ascii_only.lower()


# ─── FILE TYPE DETECTION ───────────────────────────────────────────────

def detect_file_type(filename: str, file_bytes: Optional[bytes] = None) -> Dict[str, Any]:
    """
    Detect file type by extension and content.
    Uses PyMuPDF for PDF detection (word positions + image coverage).
    """
    ext = Path(filename).suffix.lower().lstrip(".")
    
    result = {
        "ext": ext,
        "type": "unknown",
        "is_scanned": False,
        "has_text": False,
        "mime": None,
        "is_ocr_needed": False,
        "char_count": 0,
        "page_count": 0,
        "pages_with_text": 0,
        "detection_method": "word_position+image_coverage",
        "confidence": "high",
        "text_sample": "",
        "avg_word_count": 0.0,
        "max_image_coverage": 0.0
    }
    
    # ─── Detect by extension ──────────────────────────────────────────
    if ext in ["pdf"]:
        result["type"] = "pdf"
        result["mime"] = "application/pdf"
        
        # Use PyMuPDF detection
        if file_bytes:
            pdf_info = detect_pdf_type(file_bytes)
            result.update(pdf_info)
            result["is_ocr_needed"] = pdf_info.get("needs_ocr", False)
            result["confidence"] = pdf_info.get("confidence", "low")
            result["avg_word_count"] = pdf_info.get("avg_word_count", 0.0)
            result["max_image_coverage"] = pdf_info.get("max_image_coverage", 0.0)
    
    elif ext in ["docx", "docm"]:
        result["type"] = "word"
        result["mime"] = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        result["has_text"] = True
        result["confidence"] = "high"
    
    elif ext in ["doc"]:
        result["type"] = "word"
        result["mime"] = "application/msword"
        result["has_text"] = True
        result["confidence"] = "high"
    
    elif ext in ["xlsx", "xlsm"]:
        result["type"] = "excel"
        result["mime"] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        result["has_text"] = True
        result["confidence"] = "high"
    
    elif ext in ["xls"]:
        result["type"] = "excel"
        result["mime"] = "application/vnd.ms-excel"
        result["has_text"] = True
        result["confidence"] = "high"
    
    elif ext in ["txt", "csv", "rtf"]:
        result["type"] = "text"
        result["has_text"] = True
        result["confidence"] = "high"
    
    return result


# ─── CONTENT EXTRACTION ────────────────────────────────────────────────

def extract_text_content(file_bytes: bytes, file_info: Dict[str, Any]) -> str:
    """
    Extract text content from file for fallback classification.
    For scanned PDFs, returns empty string (needs OCR).
    """
    file_type = file_info.get("type", "unknown")
    ext = file_info.get("ext", "")
    
    # ─── If scanned PDF, skip content extraction ────────────────────
    if file_type == "pdf" and file_info.get("is_scanned", False):
        logger.info(f"Skipping content extraction for scanned PDF (needs OCR)")
        return ""
    
    try:
        # ─── PDF (normal, with text) ─────────────────────────────────
        if file_type == "pdf":
            try:
                import fitz  # PyMuPDF
                doc = fitz.open(stream=file_bytes, filetype="pdf")
                text_parts = []
                for i, page in enumerate(doc):
                    if i >= 2:
                        break
                    text = page.get_text()
                    if text.strip():
                        text_parts.append(text)
                doc.close()
                return "\n".join(text_parts)
            except ImportError:
                logger.warning("PyMuPDF not installed — trying pdfplumber")
                try:
                    import pdfplumber
                    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                        if not pdf.pages:
                            return ""
                        text_parts = []
                        for page in pdf.pages[:2]:
                            text = page.extract_text() or ""
                            if text.strip():
                                text_parts.append(text)
                        return "\n".join(text_parts)
                except ImportError:
                    logger.warning("pdfplumber not installed")
                    return ""
        
        # ─── WORD (DOCX) ─────────────────────────────────────────────
        elif file_type == "word":
            if ext in ["docx", "docm"]:
                try:
                    import docx
                    doc = docx.Document(io.BytesIO(file_bytes))
                    paras = [p.text for p in doc.paragraphs[:20] if p.text.strip()]
                    return "\n".join(paras[:10])
                except ImportError:
                    logger.warning("python-docx not installed")
                    return ""
                except Exception as e:
                    logger.warning(f"DOCX extraction failed: {e}")
                    return ""
            
            elif ext == "doc":
                # Legacy DOC - try with textract or antiword
                try:
                    import textract
                    text = textract.process(io.BytesIO(file_bytes)).decode('utf-8')
                    return text[:2000]
                except ImportError:
                    logger.warning("textract not installed")
                    return ""
                except Exception as e:
                    logger.warning(f"DOC extraction failed: {e}")
                    return ""
        
        # ─── EXCEL ────────────────────────────────────────────────────
        elif file_type == "excel":
            try:
                import openpyxl
                
                if ext in ["xlsx", "xlsm"]:
                    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True, read_only=True)
                    ws = wb.worksheets[0]
                    
                    lines = []
                    for row in ws.iter_rows(min_row=1, max_row=15, values_only=True):
                        cells = [str(c) for c in row if c is not None and str(c).strip() != ""]
                        if cells:
                            lines.append(" ".join(cells))
                    
                    return "\n".join(lines[:10])
                    
                elif ext == "xls":
                    try:
                        import xlrd
                        workbook = xlrd.open_workbook(file_contents=file_bytes)
                        sheet = workbook.sheet_by_index(0)
                        
                        lines = []
                        for row_idx in range(min(15, sheet.nrows)):
                            cells = [str(sheet.cell_value(row_idx, col)) for col in range(sheet.ncols)]
                            cells = [c for c in cells if c.strip()]
                            if cells:
                                lines.append(" ".join(cells))
                        
                        return "\n".join(lines[:10])
                    except ImportError:
                        logger.warning("xlrd not installed")
                        return ""
                        
            except ImportError:
                logger.warning("openpyxl not installed")
                return ""
            except Exception as e:
                logger.warning(f"Excel extraction failed: {e}")
                return ""
        
        # ─── TEXT FILES ──────────────────────────────────────────────
        elif file_type == "text":
            try:
                text = file_bytes.decode('utf-8', errors='ignore')
                return text[:2000]
            except Exception:
                return ""
        
        return ""
        
    except Exception as e:
        logger.warning(f"Content extraction failed: {e}")
        return ""


# ─── FILENAME PATTERNS ────────────────────────────────────────────────

_FILENAME_PATTERNS = [
    # AVIS
    ("avis", re.compile(r"avis[\s_-]*(?:ao|ar|fr|d'?appel|d'?offres)?")),
    ("avis", re.compile(r"annonce")),
    
    # RC (Règlement de Consultation)
    ("rc", re.compile(r"rcd[pg]")),        # RCDG, RCDP
    ("rc", re.compile(r"ccafp")),          # Cadre de Clauses Administratives
    ("rc", re.compile(r"reglement.*consultation")),
    ("rc", re.compile(r"\brc\b")),
    
    # CPS (Cahier des Prescriptions Spéciales)
    ("cps", re.compile(r"\bcps\b")),
    ("cps", re.compile(r"cctp")),          # Cahier des Clauses Techniques
    ("cps", re.compile(r"cahier.*prescription")),
    
    # BP (Bordereau des Prix)
    ("bp", re.compile(r"\bbp\b")),
    ("bp", re.compile(r"bordereau(?:x)?[\s_-]*prix")),
    ("bp", re.compile(r"bordereau[\s_-]*des[\s_-]*prix")),
]

_LOT_RE = re.compile(r"lot[\s_\-]?(\d+)")


# ─── CONTENT PATTERNS (Fallback) ──────────────────────────────────────

_CONTENT_PATTERNS = [
    ("rc", re.compile(r"reglement de consultation")),
    ("rc", re.compile(r"rcd[pg]")),
    ("cps", re.compile(r"cahier des prescriptions speciales")),
    ("cps", re.compile(r"cctp")),
    ("avis", re.compile(r"avis d.?appel d.?offres")),
    ("bp", re.compile(r"bordereau.*prix")),
    ("bp", re.compile(r"\bbp\b")),
]


# ─── CLASSIFICATION ────────────────────────────────────────────────────

def classify_dce_file(filename: str, file_bytes: Optional[bytes] = None) -> Dict[str, Any]:
    """
    Classify a single file using:
    1. Filename matching (primary)
    2. Content matching (fallback, requires file_bytes)
    3. PDF detection using PyMuPDF (word positions + image coverage)
    """
    normalized_name = _normalize(filename)
    
    # Detect file type (includes PDF detection)
    file_info = detect_file_type(filename, file_bytes)
    
    # ─── STEP 1: Try filename matching ──────────────────────────────
    type_doc = None
    matched_by = "none"
    
    for pattern_type, pattern in _FILENAME_PATTERNS:
        if pattern.search(normalized_name):
            type_doc = pattern_type
            matched_by = "filename"
            break
    
    # ─── STEP 2: Try content matching (if filename failed) ──────────
    if type_doc is None and file_bytes and not file_info.get("is_scanned", False):
        content_text = extract_text_content(file_bytes, file_info)
        if content_text:
            normalized_content = _normalize(content_text)
            for pattern_type, pattern in _CONTENT_PATTERNS:
                if pattern.search(normalized_content):
                    type_doc = pattern_type
                    matched_by = "content"
                    break
    
    # ─── STEP 3: Extract lot number ──────────────────────────────────
    lot_scope = "global"
    m = _LOT_RE.search(normalized_name)
    if m:
        lot_scope = f"lot_{m.group(1)}"
    
    # ─── STEP 4: If no match ─────────────────────────────────────────
    if type_doc is None:
        logger.warning(f"[GAP] {filename} (type: {file_info.get('type', 'unknown')})")
        type_doc = "autre"
    
    return {
        "filename": filename,
        "type_doc": type_doc,
        "lot_scope": lot_scope,
        "matched_by": matched_by,
        "file_type": file_info,
        "is_scanned": file_info.get("is_scanned", False),
        "is_ocr_needed": file_info.get("is_ocr_needed", False),
        "confidence": file_info.get("confidence", "low"),
        "avg_word_count": file_info.get("avg_word_count", 0.0),
        "max_image_coverage": file_info.get("max_image_coverage", 0.0),
        "page_count": file_info.get("page_count", 0),
        "detection_method": file_info.get("detection_method", "unknown")
    }


# ─── ZIP PROCESSING ────────────────────────────────────────────────────

def classify_dce_zip(zf: zipfile.ZipFile) -> List[Dict[str, Any]]:
    """
    Classify every file in the ZIP.
    Reads files only when needed (for content fallback).
    """
    results = []
    
    for name in zf.namelist():
        if name.endswith("/"):
            continue
        
        # Try to read file for content fallback
        file_bytes = None
        try:
            file_bytes = zf.read(name)
        except Exception as e:
            logger.warning(f"Cannot read {name}: {e}")
        
        # Classify
        record = classify_dce_file(name, file_bytes)
        results.append(record)
        
        # Log OCR needs
        if record.get("is_ocr_needed", False):
            logger.info(f"[OCR NEEDED] {name} — scanned PDF requires OCR")
            logger.info(f"  Confidence: {record.get('confidence', 'unknown')}")
            logger.info(f"  Avg words: {record.get('avg_word_count', 0):.1f}")
            logger.info(f"  Max image coverage: {record.get('max_image_coverage', 0):.2f}")
    
    return results


# ─── STANDALONE TEST ──────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "="*70)
    print("DCE CLASSIFIER — PyMuPDF WORD POSITION + IMAGE COVERAGE")
    print("="*70)
    
    test_files = [
        ("Avis AO 2026.pdf", None),
        ("RCDP Travaux.docx", None),
        ("CPS LOT 1.xlsx", None),
        ("BP.xlsm", None),
        ("CCTP.doc", None),
        ("RCDG Fournitures.pdf", None),
        ("Page de garde.pdf", None),
        ("Tableau.xlsx", None),
    ]
    
    print("\n📄 Testing with PyMuPDF detection:")
    for fname, _ in test_files:
        # Just test with empty bytes for display
        result = classify_dce_file(fname)
        icon = {"avis": "📢", "rc": "📋", "cps": "📊", "bp": "💰", "autre": "📎"}.get(result['type_doc'], "📄")
        lot = result['lot_scope'] if result['lot_scope'] != 'global' else '🌍'
        
        if result.get('is_scanned', False):
            status = f"{Fore.RED}🔍 SCANNED{Style.RESET_ALL}"
            if result.get('confidence') == 'uncertain':
                status = f"{Fore.YELLOW}⚠️ UNCERTAIN{Style.RESET_ALL}"
        else:
            status = f"{Fore.GREEN}✅ NORMAL{Style.RESET_ALL}"
        
        words = f"words: {result.get('avg_word_count', 0):.1f}"
        img = f"img: {result.get('max_image_coverage', 0):.2f}"
        print(f"  {icon} {fname:40} → {result['type_doc']:6} | lot: {lot} | {status} | {words} | {img}")
    
    print("\n" + "="*70)