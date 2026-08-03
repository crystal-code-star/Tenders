"""
COMPLETE BP (Bordereau des Prix) EXTRACTION SYSTEM
==================================================
Single-file implementation for extracting BP (Price Schedule) data
from Excel, Word, and PDF documents with OCR support.
Integrated with Supabase for batch processing.

Version: 3.1 - Added detailed item display before saving
"""

import os
import sys
import re
import json
import logging
import io
import base64
import zipfile
import argparse
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple, Union
from io import BytesIO

# Load environment variables
from dotenv import load_dotenv
from colorama import init, Fore, Style, Back

init(autoreset=True)

current_dir = Path(__file__).resolve().parent
env_path = current_dir.parent.parent / ".env"
load_dotenv(env_path)

# ============================================================================
# LOGGING SETUP
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s: %(message)s'
)
logger = logging.getLogger("BP_extractor")

# ============================================================================
# SUPABASE SETUP
# ============================================================================

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    print(f"\n{Fore.RED}❌ ERREUR: Identifiants Supabase manquants dans .env")
    sys.exit(1)

try:
    import supabase
    supabase_client = supabase.create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
except Exception as e:
    print(f"\n{Fore.RED}❌ ERREUR: Impossible de se connecter à Supabase: {e}")
    sys.exit(1)

# ============================================================================
# COLORAMA PRINT FUNCTIONS
# ============================================================================

def print_header(text):
    print(f"\n{Fore.CYAN}{Style.BRIGHT}{'═'*80}")
    print(f"{Fore.CYAN}{Style.BRIGHT}  {text}")
    print(f"{Fore.CYAN}{Style.BRIGHT}{'═'*80}")

def print_section(text):
    print(f"\n{Fore.YELLOW}{'─'*80}")
    print(f"{Fore.YELLOW}  {text}")
    print(f"{Fore.YELLOW}{'─'*80}")

def print_success(text):
    print(f"  {Fore.GREEN}✅ {text}")

def print_error(text):
    print(f"  {Fore.RED}❌ {text}")

def print_warning(text):
    print(f"  {Fore.YELLOW}⚠️  {text}")

def print_info(text):
    print(f"  {Fore.WHITE}📌 {text}")

def print_stat(text):
    print(f"  {Fore.MAGENTA}📊 {text}")

# ============================================================================
# GLOBAL STATISTICS
# ============================================================================

global_stats = {
    "total_tenders": 0,
    "processed": 0,
    "skipped_no_zip": 0,
    "skipped_already_done": 0,
    "skipped_no_bp_file": 0,
    "errors": 0,
    "total_items_extracted": 0,
}

# ============================================================================
# DISPLAY FUNCTIONS
# ============================================================================

def display_bp_items(items: List[Dict[str, str]], max_display: int = 20):
    """Affiche les items BP extraits dans un tableau formaté."""
    if not items:
        print_warning("Aucun item à afficher")
        return
    
    total_items = len(items)
    display_items = items[:max_display]
    
    print_section(f"📋 ITEMS BP EXTRAITS ({total_items} au total, affichage des {len(display_items)} premiers)")
    
    # En-tête du tableau
    header = f"  {Fore.WHITE}┌{'─'*6}┬{'─'*6}┬{'─'*35}┬{'─'*6}┬{'─'*10}┬{'─'*12}┬{'─'*12}┐"
    col_headers = f"  {Fore.WHITE}│ {Fore.YELLOW}{'#':<4} {Fore.WHITE}│ {Fore.YELLOW}{'N° Prix':<4} {Fore.WHITE}│ {Fore.YELLOW}{'Désignation':<33} {Fore.WHITE}│ {Fore.YELLOW}{'Unité':<4} {Fore.WHITE}│ {Fore.YELLOW}{'Quantité':<8} {Fore.WHITE}│ {Fore.YELLOW}{'PU HT':<10} {Fore.WHITE}│ {Fore.YELLOW}{'Total HT':<10} {Fore.WHITE}│"
    separator = f"  {Fore.WHITE}├{'─'*6}┼{'─'*6}┼{'─'*35}┼{'─'*6}┼{'─'*10}┼{'─'*12}┼{'─'*12}┤"
    
    print(header)
    print(col_headers)
    print(separator)
    
    for i, item in enumerate(display_items, 1):
        n_prix = item.get("N° Prix", "")[:4]
        designation = item.get("Désignation", "")[:33]
        unite = item.get("Unité", "")[:4]
        quantite = item.get("Quantité", "")[:8]
        pu_ht = item.get("Prix Unitaire HT", "")[:10]
        total_ht = item.get("Total HT", "")[:10]
        
        row = f"  {Fore.WHITE}│ {Fore.CYAN}{i:<4} {Fore.WHITE}│ {Fore.WHITE}{n_prix:<4} {Fore.WHITE}│ {Fore.WHITE}{designation:<33} {Fore.WHITE}│ {Fore.WHITE}{unite:<4} {Fore.WHITE}│ {Fore.WHITE}{quantite:<8} {Fore.WHITE}│ {Fore.GREEN}{pu_ht:<10} {Fore.WHITE}│ {Fore.GREEN}{total_ht:<10} {Fore.WHITE}│"
        print(row)
    
    footer = f"  {Fore.WHITE}└{'─'*6}┴{'─'*6}┴{'─'*35}┴{'─'*6}┴{'─'*10}┴{'─'*12}┴{'─'*12}┘"
    print(footer)
    
    if total_items > max_display:
        print_info(f"... et {total_items - max_display} items supplémentaires")

def display_bp_summary(doc_level: Dict[str, Any], items_count: int):
    """Affiche le résumé des informations extraites du BP."""
    print_section("📊 RÉSUMÉ BP")
    
    ref_ao = doc_level.get('Ref_AO', 'N/A')
    objet = doc_level.get('Objet', 'N/A')
    maitre_ouvrage = doc_level.get('Maitre_Ouvrage', 'N/A')
    total_ht = doc_level.get('Total_HT', 'N/A')
    tva = doc_level.get('TVA_20', 'N/A')
    total_ttc = doc_level.get('Total_TTC', 'N/A')
    totals_status = doc_level.get('totals_status', 'not_found')
    
    print(f"  {Fore.WHITE}┌{'─'*60}┐")
    print(f"  {Fore.WHITE}│ {Fore.YELLOW}{'CHAMP':<20} {Fore.WHITE}│ {Fore.YELLOW}{'VALEUR':<36} {Fore.WHITE}│")
    print(f"  {Fore.WHITE}├{'─'*60}┤")
    
    rows = [
        ("Réf. AO", ref_ao),
        ("Objet", objet[:80]),
        ("Maître d'ouvrage", maitre_ouvrage),
        ("Nombre d'items", str(items_count)),
        ("Total HT", str(total_ht) if total_ht else "Non trouvé"),
        ("TVA", str(tva) if tva else "Non trouvé"),
        ("Total TTC", str(total_ttc) if total_ttc else "Non trouvé"),
        ("Statut totaux", totals_status),
    ]
    
    for label, value in rows:
        color = Fore.GREEN if value and value != "Non trouvé" else Fore.YELLOW
        print(f"  {Fore.WHITE}│ {Fore.CYAN}{label:<20} {Fore.WHITE}│ {color}{str(value)[:36]:<36} {Fore.WHITE}│")
    
    print(f"  {Fore.WHITE}└{'─'*60}┘")

def display_price_analysis(items: List[Dict[str, str]]):
    """Affiche une analyse rapide des prix."""
    if not items:
        return
    
    prices = []
    quantities = []
    totals = []
    
    for item in items:
        pu = item.get("Prix Unitaire HT", "")
        qte = item.get("Quantité", "")
        th = item.get("Total HT", "")
        
        try:
            if pu and pu != "FORMULA":
                prices.append(float(pu))
        except ValueError:
            pass
        
        try:
            if qte and qte != "FORMULA":
                quantities.append(float(qte))
        except ValueError:
            pass
        
        try:
            if th and th != "FORMULA":
                totals.append(float(th))
        except ValueError:
            pass
    
    if prices or totals:
        print_section("💰 ANALYSE DES PRIX")
        
        print(f"  {Fore.WHITE}┌{'─'*50}┐")
        print(f"  {Fore.WHITE}│ {Fore.YELLOW}{'ANALYSE':<30} {Fore.WHITE}│ {Fore.YELLOW}{'VALEUR':<16} {Fore.WHITE}│")
        print(f"  {Fore.WHITE}├{'─'*50}┤")
        
        if prices:
            avg_price = sum(prices) / len(prices)
            min_price = min(prices)
            max_price = max(prices)
            print(f"  {Fore.WHITE}│ {Fore.CYAN}{'Prix unitaire moyen':<30} {Fore.WHITE}│ {Fore.GREEN}{avg_price:>14,.2f} {Fore.WHITE}│")
            print(f"  {Fore.WHITE}│ {Fore.CYAN}{'Prix unitaire min':<30} {Fore.WHITE}│ {Fore.GREEN}{min_price:>14,.2f} {Fore.WHITE}│")
            print(f"  {Fore.WHITE}│ {Fore.CYAN}{'Prix unitaire max':<30} {Fore.WHITE}│ {Fore.GREEN}{max_price:>14,.2f} {Fore.WHITE}│")
        
        if totals:
            sum_totals = sum(totals)
            print(f"  {Fore.WHITE}│ {Fore.CYAN}{'Somme des totaux HT':<30} {Fore.WHITE}│ {Fore.GREEN}{sum_totals:>14,.2f} {Fore.WHITE}│")
        
        if quantities:
            total_qty = sum(quantities)
            print(f"  {Fore.WHITE}│ {Fore.CYAN}{'Quantité totale':<30} {Fore.WHITE}│ {Fore.GREEN}{total_qty:>14,.2f} {Fore.WHITE}│")
        
        print(f"  {Fore.WHITE}└{'─'*50}┘")

# ============================================================================
# FILE DETECTION
# ============================================================================

def is_bp_file(filename: str) -> bool:
    """Détecte si c'est un fichier BP (Bordereau des Prix)"""
    filename_lower = filename.lower()
    
    bp_keywords = [
        'bp', 'bordereau', 'bpu', 'prix', 'bordereau des prix',
        'dp', 'devis', 'estimatif', 'quantitatif', 'dq',
        'bq', 'bordereau quantitatif', 'mercuriale',
        'serie', 'prix unitaire', 'prix total'
    ]
    
    exclude_keywords = [
        'rc', 'acte', 'engagement', 'attestation', 'certificat',
        'cv', 'curriculum', 'rib', 'bancaire', 'plan',
        'planning', 'rapport', 'avis', 'aoo', 'ao',
        'cahier', 'cps', 'ccp', 'cctp', 'ccag',
        'reglement', 'consultation', 'prospectus',
        'declaration', 'honneur', 'moyens', 'memoire',
        'methodologie', 'echantillon', 'note'
    ]
    
    has_bp = any(kw in filename_lower for kw in bp_keywords)
    is_excluded = any(kw in filename_lower for kw in exclude_keywords)
    
    return has_bp and not is_excluded

# ============================================================================
# EXTRACTION STATUS
# ============================================================================

class ExtractionStatus:
    SUCCESS = "success"
    EXTRACTION_ERROR = "extraction_error"
    NO_DATA = "no_data"
    SKIPPED_TEMP = "skipped_temp"
    UNSUPPORTED_TYPE = "unsupported_type"

# ============================================================================
# PDF SCAN DETECTOR
# ============================================================================

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None
    logger.warning("PyMuPDF not installed. PDF detection will be limited.")

def detect_pdf_type(file_bytes: bytes, sample_pages: int = 5) -> Dict[str, Any]:
    """Detect if PDF is scanned (image-based) or has text layer."""
    result = {
        "is_scanned": False,
        "has_text": False,
        "needs_ocr": False,
        "confidence": "high",
        "page_count": 0,
        "avg_word_count": 0.0,
        "max_image_coverage": 0.0,
    }
    
    if fitz is None:
        result["confidence"] = "low"
        result["error"] = "PyMuPDF not installed"
        return result
    
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
        
        if check_pages == 0:
            return result
        
        word_counts = []
        image_coverages = []
        
        for i in range(check_pages):
            page = doc[i]
            words = page.get_text("words")
            word_count = len(words)
            word_counts.append(word_count)
            
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
            image_coverages.append(image_coverage)
        
        avg_words = sum(word_counts) / len(word_counts) if word_counts else 0
        max_image_coverage = max(image_coverages) if image_coverages else 0
        
        result["avg_word_count"] = avg_words
        result["max_image_coverage"] = max_image_coverage
        
        if avg_words >= 8:
            result["has_text"] = True
            result["is_scanned"] = False
            result["needs_ocr"] = False
            result["confidence"] = "high"
        elif avg_words < 2 and max_image_coverage >= 0.85:
            result["has_text"] = False
            result["is_scanned"] = True
            result["needs_ocr"] = True
            result["confidence"] = "high"
        elif avg_words < 8:
            result["has_text"] = avg_words > 0
            result["is_scanned"] = True
            result["needs_ocr"] = True
            result["confidence"] = "uncertain"
        
        return result
        
    finally:
        doc.close()

# ============================================================================
# EXTRACTORS - PDF
# ============================================================================

def extract_pdf_text(file_bytes: bytes) -> Dict[str, Any]:
    """Extract text from PDF using PyMuPDF."""
    if fitz is None:
        return {"text": "", "pages": [], "page_count": 0, "total_words": 0, 
                "tables": [], "error": "PyMuPDF not installed"}
    
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        all_text_parts = []
        pages = []
        tables = []
        
        for page_num, page in enumerate(doc):
            blocks = page.get_text("blocks")
            blocks.sort(key=lambda b: (round(b[1] / 10) * 10, b[0]))
            
            page_text_parts = []
            for block in blocks:
                block_text = block[4].strip() if len(block) > 4 else ""
                if block_text:
                    page_text_parts.append(block_text)
            
            page_text = "\n".join(page_text_parts)
            all_text_parts.append(page_text)
            
            pages.append({
                "page_num": page_num + 1,
                "text": page_text,
                "word_count": len(page.get_text("words")),
            })
        
        doc.close()
        full_text = "\n\n".join(all_text_parts)
        
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                for page in pdf.pages:
                    raw_tables = page.extract_tables() or []
                    for table in raw_tables:
                        grid = [[str(c) if c is not None else "" for c in row] for row in table]
                        if grid and any(any(c for c in row if c) for row in grid):
                            tables.append({"grid": grid})
        except ImportError:
            pass
        except Exception:
            pass
        
        return {
            "text": full_text,
            "pages": pages,
            "page_count": len(pages),
            "total_words": sum(p["word_count"] for p in pages),
            "tables": tables
        }
        
    except Exception as e:
        logger.error(f"PDF extraction failed: {e}")
        return {"text": "", "pages": [], "page_count": 0, "total_words": 0,
                "tables": [], "error": str(e)}

def extract_pdf_ocr(file_bytes: bytes) -> Dict[str, Any]:
    """Extract text from scanned PDF using OCR."""
    try:
        import pytesseract
        from PIL import Image
        import pdf2image
    except ImportError as e:
        return {"text": "", "pages": [], "page_count": 0, "total_words": 0,
                "tables": [], "error": f"Missing library: {e}"}
    
    try:
        images = pdf2image.convert_from_bytes(file_bytes, dpi=300)
        all_text = ""
        pages = []
        
        for page_num, img in enumerate(images):
            text = pytesseract.image_to_string(img, lang='fra+eng')
            all_text += text + "\n\n"
            pages.append({
                "page_num": page_num + 1,
                "text": text,
                "word_count": len(text.split())
            })
        
        return {
            "text": all_text,
            "pages": pages,
            "page_count": len(pages),
            "total_words": sum(p["word_count"] for p in pages),
            "tables": []
        }
        
    except Exception as e:
        logger.error(f"OCR extraction failed: {e}")
        return {"text": "", "pages": [], "page_count": 0, "total_words": 0,
                "tables": [], "error": str(e)}

# ============================================================================
# EXTRACTORS - Word
# ============================================================================

def extract_word_text(file_bytes: bytes, ext: str = ".docx") -> Dict[str, Any]:
    """Extract text from Word document."""
    try:
        if ext in [".docx", ".docm"]:
            try:
                import docx
                doc = docx.Document(io.BytesIO(file_bytes))
                text_parts = []
                tables = []
                
                for para in doc.paragraphs:
                    para_text = para.text.strip()
                    if para_text:
                        text_parts.append(para_text)
                
                for table in doc.tables:
                    grid = []
                    for row in table.rows:
                        row_cells = []
                        for cell in row.cells:
                            cell_text = cell.text.strip() if cell.text else ""
                            row_cells.append(cell_text)
                        grid.append(row_cells)
                    if grid:
                        tables.append({"grid": grid})
                
                full_text = "\n".join(text_parts)
                return {
                    "text": full_text,
                    "tables": tables,
                    "total_words": len(full_text.split()),
                    "type": "word_docx"
                }
            except ImportError:
                return {"error": "python-docx not installed", "tables": [], "text": ""}
        
        elif ext == ".doc":
            try:
                import textract
                text = textract.process(io.BytesIO(file_bytes)).decode('utf-8', errors='ignore')
                return {
                    "text": text,
                    "tables": [],
                    "total_words": len(text.split()),
                    "type": "word_doc"
                }
            except ImportError:
                return {"error": "textract not installed", "tables": [], "text": ""}
        
        return {"error": f"Unsupported Word format: {ext}", "tables": [], "text": ""}
        
    except Exception as e:
        logger.error(f"Word extraction failed: {e}")
        return {"text": "", "tables": [], "total_words": 0, "error": str(e)}

# ============================================================================
# EXTRACTORS - Excel
# ============================================================================

def extract_excel_text(file_bytes: bytes, ext: str = ".xlsx") -> Dict[str, Any]:
    """Extract text from Excel document."""
    try:
        if ext in [".xlsx", ".xlsm"]:
            try:
                import openpyxl
                wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True, read_only=True)
                text_parts = []
                sheets = []
                
                for sheet_name in wb.sheetnames:
                    ws = wb[sheet_name]
                    grid = []
                    sheet_text_parts = []
                    
                    for row in ws.iter_rows(values_only=True):
                        row_cells = [str(c) if c is not None else "" for c in row]
                        if any(c and c.strip() for c in row_cells):
                            grid.append(row_cells)
                            row_text = " | ".join(c for c in row_cells if c and c.strip())
                            if row_text:
                                sheet_text_parts.append(row_text)
                    
                    if sheet_text_parts:
                        text_parts.append(f"--- Sheet: {sheet_name} ---")
                        text_parts.extend(sheet_text_parts)
                    
                    sheets.append({
                        "name": sheet_name,
                        "grid": grid,
                        "row_count": len(grid),
                        "col_count": max(len(r) for r in grid) if grid else 0
                    })
                
                wb.close()
                full_text = "\n".join(text_parts)
                return {
                    "text": full_text,
                    "sheets": sheets,
                    "total_words": len(full_text.split()),
                    "type": "excel_xlsx"
                }
            except ImportError:
                return {"error": "openpyxl not installed", "sheets": [], "text": ""}
        
        elif ext == ".xls":
            try:
                import xlrd
                wb = xlrd.open_workbook(file_contents=file_bytes)
                text_parts = []
                sheets = []
                
                for sheet_idx in range(wb.nsheets):
                    ws = wb.sheet_by_index(sheet_idx)
                    grid = []
                    sheet_text_parts = []
                    
                    for row_idx in range(min(ws.nrows, 500)):
                        row_cells = []
                        for col_idx in range(ws.ncols):
                            cell = ws.cell(row_idx, col_idx)
                            value = str(cell.value) if cell.value is not None else ""
                            if cell.ctype == xlrd.XL_CELL_NUMBER:
                                if cell.value == int(cell.value):
                                    value = str(int(cell.value))
                            row_cells.append(value)
                        
                        if any(c and c.strip() for c in row_cells):
                            grid.append(row_cells)
                            row_text = " | ".join(c for c in row_cells if c and c.strip())
                            if row_text:
                                sheet_text_parts.append(row_text)
                    
                    if sheet_text_parts:
                        text_parts.append(f"--- Sheet: {ws.name} ---")
                        text_parts.extend(sheet_text_parts)
                    
                    sheets.append({
                        "name": ws.name,
                        "grid": grid,
                        "row_count": len(grid),
                        "col_count": max(len(r) for r in grid) if grid else 0
                    })
                
                full_text = "\n".join(text_parts)
                return {
                    "text": full_text,
                    "sheets": sheets,
                    "total_words": len(full_text.split()),
                    "type": "excel_xls"
                }
            except ImportError:
                return {"error": "xlrd not installed", "sheets": [], "text": ""}
        
        return {"error": f"Unsupported Excel format: {ext}", "sheets": [], "text": ""}
        
    except Exception as e:
        logger.error(f"Excel extraction failed: {e}")
        return {"text": "", "sheets": [], "total_words": 0, "error": str(e)}

# ============================================================================
# BP TEXT NORMALIZATION
# ============================================================================

def _normalize_text(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\u00a0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()

_ACCENT_MAP = str.maketrans({
    "à": "a", "â": "a", "ä": "a", "á": "a",
    "é": "e", "è": "e", "ê": "e", "ë": "e",
    "î": "i", "ï": "i",
    "ô": "o", "ö": "o",
    "ù": "u", "û": "u", "ü": "u",
    "ç": "c",
    "œ": "oe",
})

def _normalize_headers(text: str) -> str:
    """Normalize header text for matching."""
    if not text:
        return ""
    text = str(text).lower().strip()
    text = text.translate(_ACCENT_MAP)
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def _safe_extract_group(match) -> str:
    """Safely extract group 1 if exists, else group 0."""
    if match is None:
        return ""
    if match.lastindex and match.lastindex >= 1:
        return match.group(1).strip()
    return match.group(0).strip()

# ============================================================================
# BP HEADER PATTERNS
# ============================================================================

BP_HEADER_PATTERNS = {
    "Ref_AO": [
        r"AO\s*n[°º]?\s*[:]?\s*([\d\-/A-Za-z]+)",
        r"AO\s*[:]?\s*([\d\-/A-Za-z]+)",
        r"AON\s*N[°º]?\s*[:]?\s*([\d\-/A-Za-z]+)",
        r"Num[ée]ro\s+DA\s*/\s*March[ée]\s*[:]?\s*([\d\-/A-Za-z]+)",
        r"Appel\s+d[']offres?\s*N[°º]?\s*[:]?\s*([\d\-/A-Za-z]+)",
        r"AO\s+N[°º]?\s*[:]?\s*([\d\-/A-Za-z]+)",
        r"N[°º]\s*[:]?\s*(\d{1,4}[\-/][\dA-Za-z\-/]+)",
        r"\b(\d{1,4}/\d{4}/[A-Z]{2,10}(?:-[A-Z]{2,10})?)\b",
        r"AON\s+N[°º]?\s*[:]?\s*([\d\-/A-Za-z]+)",
        r"AO-([\d\-/A-Za-z]+)",
        r"AON\s*N[°]\s*([\d\-/A-Za-z]+)",
        r"AO\s+n[°]\s*([\d\-/A-Za-z]+)",
    ],
    "Objet": [
        r"^ÉTUDE\s+DE\s+([^\n]{10,200})",
        r"^ÉTUDE\s+D[']\s*([^\n]{10,200})",
        r"Objet\s*[:;]\s*([^\n]{5,200})",
        r"^TRAVAUX\s+(?:DE|D[']|D[EU])\s+([^\n]{5,200})",
        r"FOURNITURE\s+(?:DE|D['])\s+([^\n]{5,200})",
        r"ETUDES?\s+(?:DE|D['])\s+([^\n]{5,200})",
        r"الموضوع\s*[:;]\s*([^\n]{5,200})",
        r"Projet\s*[:;]?\s*([^\n]{5,200})",
        r"Bordereau\s+des\s+prix[^\n]*\n\s*([^\n]{10,200})",
        r"^([A-ZÀ-Ü][A-ZÀ-Ü\s\-]{10,200}?)(?:\s*[;,]|\s*$)",
        r"Contrôle\s+([^\n]{10,200})",
    ],
    "Maitre_Ouvrage": [
        r"Ma[îi]tre\s+d[']ouvrage\s*[:;]\s*([^\n]{3,100})",
        r"(Commune\s+[A-ZÀ-Ü][A-ZÀ-Ü\s\-]{2,40})(?=\s+Province)",
        r"(Province\s+[A-ZÀ-Ü][A-ZÀ-Ü\s\-]{2,40})",
        r"(Direction\s+(?:Provinciale|Régionale|Générale)\s+[^\n]{3,60})",
        r"(Office\s+(?:National|Régional)\s+[^\n]{3,60})",
        r"(Agence\s+(?:Nationale|Régionale)\s+[^\n]{3,60})",
        r"(Soci[ée]t[ée]\s+[^\n]{3,60})",
        r"(ONEE[^\n]{3,60})",
    ],
}

# ============================================================================
# BP TABLE HEADER VOCABULARY
# ============================================================================

TABLE_HEADER_VOCAB = {
    "N° Prix": [
        r"\bprix\s*n\b",
        r"\bn\s*prix\b",
        r"\bn\s*du\s*prix\b",
        r"num[ée]ro",
        r"\barticle\b",
        r"\bitem\b",
        r"^n$",
        r"^n\s*prix$",
    ],
    "Code Ouvrage PEQ": [
        r"code\s+ouvrage\s+peq",
        r"code\s+ouvrage",
        r"ouvrage\s+peq",
    ],
    "Code Série PEQ": [
        r"code\s+s[ée]rie\s+peq",
        r"code\s+s[ée]rie",
        r"s[ée]rie\s+peq",
    ],
    "Code Prix PEQ": [
        r"code\s+prix\s+peq",
        r"code\s+prix",
        r"prix\s+peq",
    ],
    "Désignation": [
        r"designation\s+des\s+travaux",
        r"designation\s+des\s+prestations",
        r"designation",
        r"description",
        r"intitule",
        r"objet",
        r"libell[ée]",
        r"consistence",
        r"البيان",
        r"التسمية",
        r"الوصف",
    ],
    "Unité": [
        r"unit[ée]\s+de\s+mesure",
        r"unit[ée]\s+de\s+compte",
        r"unit[ée]",
        r"^u$",
        r"وحدة",
    ],
    "Quantité": [
        r"quantit[ée]\s+totale",
        r"quantit[ée]\s+annuelle\s+maximale",
        r"quantit[ée]\s+annuelle",
        r"quantit[ée]",
        r"\bqte\b",
        r"\bqty\b",
        r"الكمية",
    ],
    "Prix Unitaire HT": [
        r"prix\s+unitaire",
        r"\bp\s*u\b",
        r"\bp\s*u\s+ht\b",
        r"pu\s+ht\s+en\s+chiffres?",
    ],
    "Prix Unitaire HT Lettres": [
        r"prix\s+unitaire\s+ht\s+en\s+toutes\s+lettres",
        r"pu\s+ht\s+en\s+lettres?",
        r"pu\s+en\s+lettres",
    ],
    "Total HT": [
        r"prix\s+total",
        r"total\s+ht\b",
        r"pt\s+ht",
        r"montant\s+ht",
        r"prix\s+partiel",
        r"\bpp\s+ht\b",
        r"prix\s+partiel\s+en\s+dh\s+ht",
        r"^montant$",
        r"^total$",
        r"المبلغ",
    ],
    "Observations": [
        r"observations",
        r"remarques",
        r"notes",
        r"ملاحظات",
        r"مخصص",
    ],
}

# ============================================================================
# BP UTILITY FUNCTIONS
# ============================================================================

def _is_formula(value: str) -> bool:
    if not value:
        return False
    value = str(value).strip()
    return value.startswith("=") or "=SUM" in value or "=+" in value

def _clean_number(value: str) -> Optional[float]:
    if not value or not str(value).strip():
        return None
    
    value = str(value).strip()
    value = re.sub(r'\s', '', value)
    
    if ',' in value:
        parts = value.split(',')
        if len(parts) == 2:
            integer_part = parts[0].replace('.', '')
            decimal_part = parts[1]
            value = f"{integer_part}.{decimal_part}"
        else:
            integer_part = ''.join(parts[:-1]).replace('.', '')
            decimal_part = parts[-1]
            value = f"{integer_part}.{decimal_part}"
    else:
        value = value.replace('.', '')
    
    try:
        return float(value)
    except ValueError:
        return None

def _match_header(cell_text: str) -> Optional[str]:
    """Match header text against vocabulary using word boundaries."""
    if not cell_text:
        return None
    
    cell_norm = _normalize_headers(cell_text)
    
    for field, patterns in TABLE_HEADER_VOCAB.items():
        for pattern in patterns:
            if re.search(pattern, cell_norm, re.IGNORECASE):
                return field
    
    return None

# ============================================================================
# BP HEADER EXTRACTION
# ============================================================================

def extract_bp_header(text: str, grid: List[List[str]] = None, header_idx: int = None) -> Dict[str, str]:
    """Extract document-level fields from BP."""
    result = {
        "Ref_AO": "",
        "Objet": "",
        "Maitre_Ouvrage": "",
    }
    
    if not text and not grid:
        return result
    
    if text:
        for field, patterns in BP_HEADER_PATTERNS.items():
            for pattern in patterns:
                m = re.search(pattern, text, re.IGNORECASE)
                if m:
                    value = _safe_extract_group(m)
                    if len(value) > 3:
                        result[field] = value
                        break
            if result[field]:
                continue
    
    if not result["Objet"] and grid and header_idx is not None:
        scan_start = max(0, header_idx - 15)
        for row_idx in range(header_idx - 1, scan_start - 1, -1):
            if row_idx < 0:
                break
            row = grid[row_idx]
            if not row:
                continue
            row_text = " ".join(str(c) for c in row if c)
            
            if len(row_text) > 30 and not re.search(r'(?:N°|prix|unite|quantite|code|peq|mission|bordereau|PU|HT)', row_text, re.IGNORECASE):
                if re.search(r'Bordereau|TRAVAUX|FOURNITURE|ETUDE|PROJET|FORAGE|CONSTRUCTION|ALIMENTATION|Contrôle', row_text, re.IGNORECASE):
                    result["Objet"] = row_text.strip()
                    break
    
    return result

# ============================================================================
# BP TABLE DETECTION
# ============================================================================

def _is_section_header_row(row: List[str]) -> bool:
    """Check if a row is a section header."""
    if not row:
        return False
    
    row_text = " ".join(str(c) for c in row if c)
    row_text_lower = row_text.lower()
    
    first_cell = str(row[0]).strip().lower() if row and row[0] else ""
    if first_cell == "prix.":
        return True
    
    if re.search(r'^part\s+[ivx]+\s*[:]', row_text_lower):
        return True
    if re.search(r'^part\s+[ivx]+\s*[:]\s*[a-zà-ÿ]', row_text_lower):
        return True
    
    if re.search(r'travaux\s+d[\']?equipement', row_text_lower):
        return True
    
    if re.search(r'^(sous-)?mission\s+([ivxlcdm]+|\d+)\b', row_text_lower):
        return True
    if re.search(r'^total\s+(sous-)?mission', row_text_lower):
        return True
    
    if row and row[0]:
        n0 = str(row[0]).strip()
        if re.match(r'^\d+\s*[-–]\s+[A-Za-zÀ-ÿ]', n0):
            return True
    
    if re.search(r'^montant\s+général', row_text_lower):
        return True
    if re.search(r'^montant\s+de\s+la\s+tva', row_text_lower):
        return True
    if re.search(r'^arrêté\s+le\s+présent', row_text_lower):
        return True
    
    if re.match(r'^\s*bordereau\s+des\s+prix', row_text_lower):
        return True
    
    section_phrases = ["travaux divers", "genie civil", "total serie", "total série"]
    for phrase in section_phrases:
        if phrase in row_text_lower and len(row_text) > 10:
            return True
    
    if row and row[0] and re.match(r'^\d+$', str(row[0]).strip()):
        designation = str(row[1]).strip() if len(row) > 1 and row[1] else ""
        if re.search(r'^part\s+[ivx]+', designation, re.IGNORECASE):
            return True
    
    return False

def _find_header_row(grid: List[List[str]]) -> Optional[int]:
    """Find the row containing BP table headers."""
    for idx, row in enumerate(grid[:25]):
        if not row:
            continue
        
        if _is_section_header_row(row):
            continue
        
        header_fields_found = set()
        for cell in row:
            field = _match_header(cell)
            if field:
                header_fields_found.add(field)
        
        if len(header_fields_found) >= 4:
            return idx
        
        if header_fields_found and idx + 1 < len(grid):
            next_row = grid[idx + 1]
            combined_fields = set(header_fields_found)
            for cell in next_row:
                field = _match_header(cell)
                if field:
                    combined_fields.add(field)
            if len(combined_fields) >= 4:
                return idx
    
    for idx, row in enumerate(grid[:25]):
        if not row:
            continue
        
        if _is_section_header_row(row):
            continue
        
        row_text = " ".join(str(c) for c in row if c)
        row_text_lower = row_text.lower()
        
        key_terms = ["prix", "n°", "designation", "libellé", "unité", "quantité", "total"]
        found_terms = sum(1 for term in key_terms if term in row_text_lower)
        
        if found_terms >= 3:
            return idx
    
    return None

# ============================================================================
# BP COLUMN MAPPING
# ============================================================================

def _map_columns(header_row: List[str], grid: List[List[str]] = None, header_idx: int = None) -> Dict[int, str]:
    """Map header columns to canonical field names."""
    col_map = {}
    mapped_fields = set()
    
    sub_header_row = None
    if grid is not None and header_idx is not None and header_idx + 1 < len(grid):
        candidate = grid[header_idx + 1]
        if candidate and not _is_section_header_row(candidate):
            first_cell = str(candidate[0]).strip() if candidate and candidate[0] else ""
            if not re.match(r'^\d', first_cell):
                sub_header_row = candidate
    
    for idx, cell in enumerate(header_row):
        if not cell or not str(cell).strip():
            continue
        
        matched_field = _match_header(cell)
        
        if matched_field and matched_field not in mapped_fields:
            col_map[idx] = matched_field
            mapped_fields.add(matched_field)
    
    fallback_order = ["N° Prix", "Désignation", "Unité", "Quantité", "Prix Unitaire HT", "Total HT"]
    fallback_idx = 0
    
    for idx in range(len(header_row)):
        if idx in col_map:
            continue
        
        cell_text = str(header_row[idx]).strip() if header_row[idx] else ""
        
        if not cell_text:
            continue
        
        while fallback_idx < len(fallback_order) and fallback_order[fallback_idx] in mapped_fields:
            fallback_idx += 1
        
        if fallback_idx < len(fallback_order):
            field = fallback_order[fallback_idx]
            col_map[idx] = field
            mapped_fields.add(field)
            fallback_idx += 1
    
    return col_map

# ============================================================================
# BP ROW EXTRACTION
# ============================================================================

_TOTAL_HT_ROW_RE = re.compile(
    r"total\s+(g[ée]n[ée]ral\s+)?(hors\s+(taxes?|tva)|ht)\b", re.IGNORECASE
)
_TVA_ROW_RE = re.compile(r"\btva\b|taxe\s+sur\s+la\s+valeur\s+ajout[ée]e", re.IGNORECASE)
_TOTAL_TTC_ROW_RE = re.compile(
    r"total\s+(toutes\s+taxes\s+comprises|(en\s+)?ttc)", re.IGNORECASE
)

def _extract_totals(grid: List[List[str]], start_idx: int) -> Dict[str, Any]:
    """Extract totals from the bottom of the table."""
    result = {
        "Total_HT": None,
        "TVA_20": None,
        "Total_TTC": None,
        "totals_status": "not_found"
    }
    
    totals_found = False
    
    for row in reversed(grid[start_idx:]):
        if not row:
            continue
        
        row_text = " ".join(str(cell) for cell in row if cell)
        
        if not result["Total_HT"] and _TOTAL_HT_ROW_RE.search(row_text):
            for cell in row:
                if str(cell).strip().startswith("="):
                    result["Total_HT"] = "FORMULA"
                    totals_found = True
                    break
                num = _clean_number(cell)
                if num is not None and num > 0:
                    result["Total_HT"] = num
                    totals_found = True
                    break
        
        if not result["TVA_20"] and _TVA_ROW_RE.search(row_text):
            for cell in row:
                if str(cell).strip().startswith("="):
                    result["TVA_20"] = "FORMULA"
                    totals_found = True
                    break
                num = _clean_number(cell)
                if num is not None:
                    result["TVA_20"] = num
                    totals_found = True
                    break
        
        if not result["Total_TTC"] and _TOTAL_TTC_ROW_RE.search(row_text):
            for cell in row:
                if str(cell).strip().startswith("="):
                    result["Total_TTC"] = "FORMULA"
                    totals_found = True
                    break
                num = _clean_number(cell)
                if num is not None and num > 0:
                    result["Total_TTC"] = num
                    totals_found = True
                    break
    
    if totals_found:
        result["totals_status"] = "found"
    
    return result

def _is_chapter_header_row(row: List[str], col_map: Dict[int, str]) -> bool:
    """Detect chapter/sub-chapter heading rows."""
    qty_col = next((c for c, f in col_map.items() if f == "Quantité"), None)
    pu_col = next((c for c, f in col_map.items() if f == "Prix Unitaire HT"), None)
    desig_col = next((c for c, f in col_map.items() if f == "Désignation"), None)
    
    if desig_col is None or desig_col >= len(row) or not str(row[desig_col]).strip():
        return False
    
    def _is_empty_or_zero(col_idx):
        if col_idx is None or col_idx >= len(row):
            return True
        val = str(row[col_idx]).strip() if row[col_idx] else ""
        if not val:
            return True
        if _is_formula(val):
            return False
        num = _clean_number(val)
        return num is None or num == 0
    
    return _is_empty_or_zero(qty_col) and _is_empty_or_zero(pu_col)

def _extract_rows(
    grid: List[List[str]],
    header_idx: int,
    col_map: Dict[int, str],
    max_rows: int = 500
) -> Tuple[List[Dict[str, str]], Dict[str, Any]]:
    """Extract items from the grid."""
    items = []
    
    start_idx = header_idx + 1
    
    for row_idx in range(start_idx, min(len(grid), start_idx + max_rows)):
        row = grid[row_idx]
        
        if not any(cell for cell in row if cell and str(cell).strip()):
            continue
        
        if _is_section_header_row(row):
            continue
        
        row_text = " ".join(str(c) for c in row if c)
        row_text_lower = row_text.lower()
        
        if _TOTAL_HT_ROW_RE.search(row_text) or _TOTAL_TTC_ROW_RE.search(row_text):
            continue
        if "total" in row_text_lower and "mission" in row_text_lower:
            continue
        
        first_cell = str(row[0]).strip().lower() if row and row[0] else ""
        if first_cell in ["mission", "total mission"]:
            continue
        
        if re.search(r'^part\s+[ivx]+\s*[:]', first_cell, re.IGNORECASE):
            continue
        if re.search(r'^travaux\s+d[\']?equipement', first_cell, re.IGNORECASE):
            continue
        
        if _is_chapter_header_row(row, col_map):
            continue
        
        item = {}
        has_data = False
        
        for col_idx, field in col_map.items():
            if col_idx < len(row):
                value = str(row[col_idx]).strip() if row[col_idx] else ""
                item[field] = value
                if value and value not in ["0", "0.00", ""]:
                    has_data = True
            else:
                item[field] = ""
        
        if not has_data:
            continue
        
        n_prix = item.get("N° Prix", "").strip()
        designation = item.get("Désignation", "").strip()
        
        if not n_prix and not designation:
            continue
        
        if designation and n_prix and not re.match(r'^\d+([\-/]\d+)*$', n_prix):
            pass
        elif not designation and n_prix and not re.match(r'^\d+([\-/]\d+)*$', n_prix):
            continue
        
        for field in ["Quantité", "Prix Unitaire HT", "Total HT"]:
            if field in item and item[field]:
                if _is_formula(item[field]):
                    item[field] = f"FORMULA: {item[field]}"
                else:
                    num = _clean_number(item[field])
                    if num is not None:
                        item[field] = str(num)
        
        items.append(item)
    
    totals = _extract_totals(grid, start_idx)
    
    return items, totals

# ============================================================================
# PDF TABLE PARSERS
# ============================================================================

def _parse_pdf_table_by_pattern(text: str) -> List[List[str]]:
    """Parse PDF table by pattern matching."""
    grid = []
    lines = text.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        if re.match(r'^\d{1,5}\s', line):
            parts = re.split(r'\s{2,}', line)
            if len(parts) >= 2:
                grid.append(parts)
        elif "|" in line:
            cells = [c.strip() for c in line.split("|") if c.strip()]
            if cells:
                grid.append(cells)
        elif "\t" in line:
            cells = [c.strip() for c in line.split("\t") if c.strip()]
            if cells:
                grid.append(cells)
    
    return grid

# ============================================================================
# MAIN BP EXTRACTION FUNCTIONS
# ============================================================================

def extract_bp_from_excel(file_bytes: bytes, ext: str = ".xlsx") -> Dict[str, Any]:
    """Extract BP from Excel file."""
    logger.info("📊 Extracting BP from Excel...")
    
    excel_result = extract_excel_text(file_bytes, ext)
    
    if excel_result.get("error"):
        return {
            "document_level": {},
            "items": [],
            "metadata": {"source_type": "excel", "error": excel_result["error"]}
        }
    
    sheets = excel_result.get("sheets", [])
    if not sheets:
        return {
            "document_level": {},
            "items": [],
            "metadata": {"source_type": "excel", "error": "No sheets found"}
        }
    
    all_items = []
    doc_level = {}
    totals_agg = {"Total_HT": None, "TVA_20": None, "Total_TTC": None, "totals_status": "not_found"}
    sheets_processed = []
    
    for sheet in sheets:
        grid = sheet.get("grid")
        sheet_name = sheet.get("name")
        if not grid or len(grid) == 0:
            continue
        
        header_idx = _find_header_row(grid)
        if header_idx is None:
            continue
        
        header_row = grid[header_idx]
        col_map = _map_columns(header_row, grid, header_idx)
        if not col_map:
            continue
        
        items, totals = _extract_rows(grid, header_idx, col_map)
        if not items:
            continue
        
        all_items.extend(items)
        sheets_processed.append(sheet_name)
        
        for key in ("Total_HT", "TVA_20", "Total_TTC"):
            if totals.get(key) is not None and totals_agg.get(key) is None:
                totals_agg[key] = totals[key]
        if totals.get("totals_status") == "found":
            totals_agg["totals_status"] = "found"
    
    primary_sheet = sheets[0]
    text = excel_result.get("text", "")
    primary_grid = None
    for sheet in sheets:
        if sheet.get("grid"):
            primary_grid = sheet["grid"]
            break
    primary_header_idx = _find_header_row(primary_grid) if primary_grid else None
    doc_level = extract_bp_header(text, primary_grid, primary_header_idx)
    
    doc_level.update({
        "Total_HT": totals_agg.get("Total_HT"),
        "TVA_20": totals_agg.get("TVA_20"),
        "Total_TTC": totals_agg.get("Total_TTC"),
        "totals_status": totals_agg.get("totals_status", "not_found"),
    })
    
    return {
        "document_level": doc_level,
        "items": all_items,
        "metadata": {
            "source_type": "excel",
            "sheets_processed": sheets_processed,
            "items_count": len(all_items),
        }
    }

def extract_bp_from_word(file_bytes: bytes, ext: str = ".docx") -> Dict[str, Any]:
    """Extract BP from Word document."""
    logger.info("📝 Extracting BP from Word...")
    
    word_result = extract_word_text(file_bytes, ext)
    
    if word_result.get("error"):
        return {
            "document_level": {},
            "items": [],
            "metadata": {"source_type": "word", "error": word_result["error"]}
        }
    
    text = word_result.get("text", "")
    tables = word_result.get("tables", [])
    
    if not tables:
        lines = text.split("\n")
        grid = []
        for line in lines:
            if "|" in line:
                cells = [c.strip() for c in line.split("|") if c.strip()]
                if cells:
                    grid.append(cells)
            elif "\t" in line:
                cells = [c.strip() for c in line.split("\t") if c.strip()]
                if cells:
                    grid.append(cells)
        
        if grid:
            tables = [{"grid": grid}]
    
    if not tables:
        return {
            "document_level": extract_bp_header(text),
            "items": [],
            "metadata": {"source_type": "word", "error": "No tables found"}
        }
    
    all_items = []
    doc_level = {}
    totals_agg = {"Total_HT": None, "TVA_20": None, "Total_TTC": None, "totals_status": "not_found"}
    tables_processed = 0
    first_header_idx = None
    first_grid = None
    
    for t_idx, table in enumerate(tables):
        grid = table.get("grid", [])
        if not grid:
            continue
        
        header_idx = _find_header_row(grid)
        if header_idx is None:
            continue
        
        if first_grid is None:
            first_grid = grid
            first_header_idx = header_idx
        
        header_row = grid[header_idx]
        col_map = _map_columns(header_row, grid, header_idx)
        if not col_map:
            continue
        
        items, totals = _extract_rows(grid, header_idx, col_map)
        if not items:
            continue
        
        all_items.extend(items)
        tables_processed += 1
        
        for key in ("Total_HT", "TVA_20", "Total_TTC"):
            if totals.get(key) is not None and totals_agg.get(key) is None:
                totals_agg[key] = totals[key]
        if totals.get("totals_status") == "found":
            totals_agg["totals_status"] = "found"
    
    doc_level = extract_bp_header(text, first_grid, first_header_idx)
    
    doc_level.update({
        "Total_HT": totals_agg.get("Total_HT"),
        "TVA_20": totals_agg.get("TVA_20"),
        "Total_TTC": totals_agg.get("Total_TTC"),
        "totals_status": totals_agg.get("totals_status", "not_found"),
    })
    
    return {
        "document_level": doc_level,
        "items": all_items,
        "metadata": {
            "source_type": "word",
            "tables_processed": tables_processed,
            "items_count": len(all_items),
        }
    }

def extract_bp_from_pdf(file_bytes: bytes, is_scanned: bool = False) -> Dict[str, Any]:
    """Extract BP from PDF."""
    logger.info("📄 Extracting BP from PDF...")
    
    if is_scanned:
        pdf_result = extract_pdf_ocr(file_bytes)
    else:
        pdf_result = extract_pdf_text(file_bytes)
    
    if pdf_result.get("error"):
        return {
            "document_level": {},
            "items": [],
            "metadata": {"source_type": "pdf", "error": pdf_result["error"]}
        }
    
    text = pdf_result.get("text", "")
    tables = pdf_result.get("tables", [])
    
    grid = []
    if tables:
        grid = tables[0].get("grid", [])
    
    if not grid:
        grid = _parse_pdf_table_by_pattern(text)
    
    header_idx = _find_header_row(grid)
    doc_level = extract_bp_header(text, grid, header_idx)
    
    if not grid:
        return {
            "document_level": doc_level,
            "items": [],
            "metadata": {"source_type": "pdf", "error": "No table found"}
        }
    
    if header_idx is None:
        return {
            "document_level": doc_level,
            "items": [],
            "metadata": {"source_type": "pdf", "error": "No header row found"}
        }
    
    header_row = grid[header_idx]
    col_map = _map_columns(header_row, grid, header_idx)
    
    if not col_map:
        return {
            "document_level": doc_level,
            "items": [],
            "metadata": {"source_type": "pdf", "error": "No columns mapped"}
        }
    
    items, totals = _extract_rows(grid, header_idx, col_map)
    
    doc_level.update({
        "Total_HT": totals.get("Total_HT"),
        "TVA_20": totals.get("TVA_20"),
        "Total_TTC": totals.get("Total_TTC"),
        "totals_status": totals.get("totals_status", "not_found"),
    })
    
    return {
        "document_level": doc_level,
        "items": items,
        "metadata": {
            "source_type": "pdf",
            "is_scanned": is_scanned,
            "row_count": len(grid),
            "header_row": header_idx,
            "col_count": len(header_row),
            "items_count": len(items),
        }
    }

# ============================================================================
# MAIN ENTRY POINT FOR BP EXTRACTION
# ============================================================================

def extract_bp_fields(file_bytes: bytes, file_info: Dict[str, Any]) -> Dict[str, Any]:
    """Main entry point for BP extraction."""
    file_type = file_info.get("type", "unknown")
    ext = file_info.get("ext", "")
    is_scanned = file_info.get("is_scanned", False)
    filename = file_info.get("filename", "")
    
    if "~$" in filename:
        return {
            "document_level": {},
            "items": [],
            "metadata": {"source_type": file_type, "error": "Temporary file skipped", "source_file": filename},
            "extraction_status": "skipped_temp"
        }
    
    if file_type == "excel":
        result = extract_bp_from_excel(file_bytes, ext)
    elif file_type == "word":
        result = extract_bp_from_word(file_bytes, ext)
    elif file_type == "pdf":
        result = extract_bp_from_pdf(file_bytes, is_scanned)
    else:
        return {
            "document_level": {},
            "items": [],
            "metadata": {"error": f"Unsupported file type: {file_type}", "source_type": file_type}
        }
    
    if file_info.get("filename"):
        result["metadata"]["source_file"] = file_info["filename"]
    
    if result.get("items") or result.get("document_level", {}).get("Ref_AO"):
        result["extraction_status"] = "success"
    elif result.get("metadata", {}).get("error"):
        result["extraction_status"] = "error"
    else:
        result["extraction_status"] = "no_data"
    
    return result

# ============================================================================
# SUPABASE INTEGRATION FUNCTIONS
# ============================================================================

def extract_files_from_zip(zip_data) -> List[Dict[str, Any]]:
    """Extrait les fichiers BP du ZIP."""
    try:
        if isinstance(zip_data, str):
            zip_bytes = base64.b64decode(zip_data)
        else:
            zip_bytes = zip_data
        
        with zipfile.ZipFile(BytesIO(zip_bytes)) as zip_file:
            all_files = zip_file.namelist()
            bp_files = [f for f in all_files if is_bp_file(Path(f).name)]
            
            if not bp_files:
                logger.info("Aucun fichier BP détecté par nom, recherche de fichiers Excel...")
                bp_files = [f for f in all_files if f.lower().endswith(('.xlsx', '.xls', '.xlsm'))]
            
            if not bp_files:
                logger.info("Aucun fichier Excel, recherche de fichiers Word...")
                bp_files = [f for f in all_files if f.lower().endswith(('.docx', '.doc'))]
            
            extracted = []
            for filename in bp_files:
                file_bytes = zip_file.read(filename)
                extracted.append({
                    "filename": Path(filename).name,
                    "full_path": filename,
                    "file_bytes": file_bytes,
                    "size_kb": len(file_bytes) / 1024
                })
            
            return extracted
    except Exception as e:
        logger.error(f"Erreur extraction ZIP: {e}")
        return []

def get_all_tenders_to_process():
    """Récupère tous les AO qui ont un ZIP mais pas encore traités pour BP."""
    print_header("RECHERCHE DE TOUS LES APPELS D'OFFRES À TRAITER (BP)")
    
    try:
        response = supabase_client.table("tenders_3").select(
            "reference, objet, acheteur_public, dce_zip_base64, dce_zip_url, bp_extraction_status"
        ).not_.is_("dce_zip_base64", "null").execute()
        
        tenders_base64 = response.data if response.data else []
        
        response2 = supabase_client.table("tenders_3").select(
            "reference, objet, acheteur_public, dce_zip_base64, dce_zip_url, bp_extraction_status"
        ).not_.is_("dce_zip_url", "null").execute()
        
        tenders_url = response2.data if response2.data else []
        
        all_tenders = {}
        for t in tenders_base64 + tenders_url:
            ref = t.get('reference')
            if ref and ref not in all_tenders:
                all_tenders[ref] = t
        
        to_process = []
        for ref, tender in all_tenders.items():
            status = tender.get('bp_extraction_status')
            if status != 'completed':
                to_process.append(tender)
            else:
                global_stats["skipped_already_done"] += 1
        
        global_stats["total_tenders"] = len(all_tenders)
        
        print_success(f"Total AO dans la BD: {len(all_tenders)}")
        print_stat(f"AO déjà traités: {global_stats['skipped_already_done']}")
        print_stat(f"AO à traiter: {len(to_process)}")
        
        return to_process
        
    except Exception as e:
        print_error(f"Erreur récupération des AO: {e}")
        return []

def get_tender_files(reference: str):
    """Récupère les fichiers depuis Supabase pour une référence."""
    try:
        response = supabase_client.table("tenders_3").select("*").eq("reference", reference).execute()
        
        if not response.data:
            return None
        
        tender = response.data[0]
        
        base64_zip = tender.get('dce_zip_base64')
        zip_url = tender.get('dce_zip_url')
        
        if base64_zip:
            files = extract_files_from_zip(base64_zip)
        elif zip_url:
            import requests as req
            resp = req.get(zip_url, timeout=120)
            if resp.status_code == 200:
                files = extract_files_from_zip(resp.content)
            else:
                return None
        else:
            return None
        
        return {"tender": tender, "files": files, "reference": reference}
        
    except Exception as e:
        logger.error(f"Erreur Supabase: {e}")
        return None

def save_bp_to_supabase(reference: str, bp_result: Dict[str, Any], filename: str):
    """Sauvegarde les résultats BP dans Supabase."""
    try:
        doc_level = bp_result.get("document_level", {})
        items = bp_result.get("items", [])
        
        # 1. Mettre à jour la table tenders_3
        update_data = {
            "bp_extraction_status": "completed",
            "bp_extracted_at": datetime.now(timezone.utc).isoformat(),
        }
        
        supabase_client.table("tenders_3").update(update_data).eq("reference", reference).execute()
        
        # 2. Supprimer les anciens items BP pour cette référence
        try:
            supabase_client.table("tenders_3_bp_items").delete().eq("tender_reference", reference).execute()
        except Exception as e:
            logger.warning(f"Erreur suppression anciens items: {e}")
        
        # 3. Insérer les nouveaux items
        if items:
            items_to_insert = []
            for item in items:
                n_prix = item.get("N° Prix", "").strip()
                designation = item.get("Désignation", "").strip()
                
                if not n_prix and not designation:
                    continue
                
                quantite = None
                if item.get("Quantité"):
                    q = _clean_number(item["Quantité"])
                    if q is not None:
                        quantite = q
                
                prix_unitaire_ht = None
                if item.get("Prix Unitaire HT"):
                    pu = _clean_number(item["Prix Unitaire HT"])
                    if pu is not None:
                        prix_unitaire_ht = pu
                
                total_ht = None
                if item.get("Total HT"):
                    th = _clean_number(item["Total HT"])
                    if th is not None:
                        total_ht = th
                
                items_to_insert.append({
                    "tender_reference": reference,
                    "n_prix": n_prix if n_prix else None,
                    "designation": designation if designation else None,
                    "unite": item.get("Unité", "").strip() if item.get("Unité") else None,
                    "quantite": quantite,
                    "prix_unitaire_ht": prix_unitaire_ht,
                    "total_ht": total_ht,
                    "code_ouvrage_peq": item.get("Code Ouvrage PEQ", "").strip() if item.get("Code Ouvrage PEQ") else None,
                    "code_serie_peq": item.get("Code Série PEQ", "").strip() if item.get("Code Série PEQ") else None,
                    "code_prix_peq": item.get("Code Prix PEQ", "").strip() if item.get("Code Prix PEQ") else None,
                })
            
            if items_to_insert:
                batch_size = 100
                for i in range(0, len(items_to_insert), batch_size):
                    batch = items_to_insert[i:i+batch_size]
                    supabase_client.table("tenders_3_bp_items").insert(batch).execute()
                
                logger.info(f"✅ {len(items_to_insert)} items BP sauvegardés pour {reference}")
        
        return True
        
    except Exception as e:
        logger.error(f"Erreur sauvegarde BP: {e}")
        
        try:
            supabase_client.table("tenders_3").update({
                "bp_extraction_status": "error"
            }).eq("reference", reference).execute()
        except:
            pass
        
        return False

def process_bp_file(filename: str, file_bytes: bytes) -> Dict[str, Any]:
    """Traite un fichier BP."""
    ext = Path(filename).suffix.lower()
    
    if ext in ['.xlsx', '.xlsm', '.xls']:
        file_type = "excel"
    elif ext in ['.docx', '.doc']:
        file_type = "word"
    elif ext == '.pdf':
        file_type = "pdf"
    else:
        return {"success": False, "error": f"Type non supporté: {ext}"}
    
    file_info = {
        "type": file_type,
        "ext": ext,
        "filename": filename,
        "is_scanned": False
    }
    
    if file_type == "pdf":
        pdf_info = detect_pdf_type(file_bytes)
        file_info["is_scanned"] = pdf_info.get("is_scanned", False)
    
    result = extract_bp_fields(file_bytes, file_info)
    
    if result.get("extraction_status") == "success":
        return {
            "success": True,
            "filename": filename,
            "items_count": len(result.get("items", [])),
            "bp_result": result
        }
    else:
        return {
            "success": False,
            "filename": filename,
            "error": result.get("metadata", {}).get("error", "Extraction failed"),
            "bp_result": result
        }

def process_single_reference(reference: str):
    """Traite une seule référence d'AO pour BP."""
    print_header(f"TRAITEMENT BP: {reference}")
    
    tender_data = get_tender_files(reference)
    
    if not tender_data or not tender_data.get("files"):
        print_error("❌ Pas de fichiers BP trouvés")
        return {"success": False, "error": "Pas de fichiers BP"}
    
    files = tender_data["files"]
    
    print_section(f"📁 {len(files)} FICHIER(S) BP")
    for f in files:
        icon = "📊" if f['filename'].endswith(('.xlsx', '.xls')) else "📝" if f['filename'].endswith(('.docx', '.doc')) else "📄"
        print(f"  {icon} {f['filename']} ({f['size_kb']:.1f} Ko)")
    
    all_results = []
    best_result = None
    max_items = 0
    
    for file_data in files:
        print_section(f"🔍 Analyse: {file_data['filename']}")
        result = process_bp_file(file_data["filename"], file_data["file_bytes"])
        all_results.append(result)
        
        if result.get("success"):
            items_count = result.get("items_count", 0)
            print_success(f"✅ {items_count} items extraits")
            
            if items_count > max_items:
                max_items = items_count
                best_result = result
    
    if best_result:
        bp_result = best_result["bp_result"]
        doc_level = bp_result.get("document_level", {})
        items = bp_result.get("items", [])
        
        # AFFICHAGE DÉTAILLÉ DES RÉSULTATS
        display_bp_summary(doc_level, max_items)
        display_bp_items(items, max_display=20)
        display_price_analysis(items)
        
        # Demander confirmation avant sauvegarde
        print_section("💾 SAUVEGARDE")
        print_info(f"Prêt à sauvegarder {max_items} items pour la référence '{reference}'")
        print_warning("Cette action va remplacer les données BP existantes dans la base de données.")
        
        # Sauvegarde automatique (ou avec confirmation)
        response = input(f"  {Fore.YELLOW}⚠️  Sauvegarder dans Supabase ? (o/N): ").strip().lower()
        
        if response in ['o', 'oui', 'y', 'yes']:
            if save_bp_to_supabase(reference, bp_result, best_result["filename"]):
                print_success("✅ Sauvegardé dans Supabase")
                global_stats["total_items_extracted"] += max_items
            else:
                print_error("❌ Erreur lors de la sauvegarde")
        else:
            print_warning("Sauvegarde annulée")
        
        global_stats["processed"] += 1
        return {"success": True, "items_count": max_items}
    else:
        global_stats["errors"] += 1
        return {"success": False, "error": "Aucun résultat valide"}

def process_all_tenders(limit: int = None):
    """Traite tous les AO non traités pour BP."""
    print(f"\n{Back.MAGENTA}{Fore.WHITE}{Style.BRIGHT}{'='*80}")
    print(f"{Back.MAGENTA}{Fore.WHITE}{Style.BRIGHT}  TRAITEMENT BP PAR LOT - TOUS LES APPELS D'OFFRES")
    print(f"{Back.MAGENTA}{Fore.WHITE}{Style.BRIGHT}{'='*80}")
    
    tenders = get_all_tenders_to_process()
    
    if not tenders:
        print_warning("Aucun AO à traiter")
        return
    
    if limit and limit > 0:
        tenders = tenders[:limit]
        print_info(f"Limite appliquée: {limit} AO maximum")
    
    total = len(tenders)
    print_header(f"🚀 DÉBUT DU TRAITEMENT BP - {total} AO")
    
    # En mode batch, sauvegarde automatique
    print_warning("Mode batch: sauvegarde automatique activée")
    
    start_time = datetime.now()
    
    for i, tender in enumerate(tenders, 1):
        reference = tender.get('reference')
        objet = tender.get('objet', 'N/A')[:80]
        
        print(f"\n{Back.CYAN}{Fore.WHITE} {'='*80}")
        print(f"{Back.CYAN}{Fore.WHITE}  AO {i}/{total}: {reference}")
        print(f"{Back.CYAN}{Fore.WHITE}  Objet: {objet}")
        print(f"{Back.CYAN}{Fore.WHITE} {'='*80}")
        
        # Traitement simplifié en mode batch (sans confirmation)
        tender_data = get_tender_files(reference)
        
        if not tender_data or not tender_data.get("files"):
            global_stats["errors"] += 1
            continue
        
        files = tender_data["files"]
        
        best_result = None
        max_items = 0
        
        for file_data in files:
            result = process_bp_file(file_data["filename"], file_data["file_bytes"])
            
            if result.get("success"):
                items_count = result.get("items_count", 0)
                
                if items_count > max_items:
                    max_items = items_count
                    best_result = result
        
        if best_result:
            bp_result = best_result["bp_result"]
            doc_level = bp_result.get("document_level", {})
            items = bp_result.get("items", [])
            
            # Affichage simplifié en mode batch
            display_bp_summary(doc_level, max_items)
            print_info(f"Items extraits: {max_items}")
            
            if save_bp_to_supabase(reference, bp_result, best_result["filename"]):
                print_success(f"✅ Sauvegardé ({max_items} items)")
                global_stats["total_items_extracted"] += max_items
                global_stats["processed"] += 1
            else:
                print_error("❌ Erreur sauvegarde")
                global_stats["errors"] += 1
        else:
            global_stats["errors"] += 1
        
        # Afficher progression
        elapsed = datetime.now() - start_time
        avg_time = elapsed / i if i > 0 else elapsed
        remaining = avg_time * (total - i)
        
        print_section("📊 PROGRESSION")
        print_stat(f"Traités: {i}/{total} ({i/total*100:.1f}%)")
        print_stat(f"Succès: {global_stats['processed']} | Erreurs: {global_stats['errors']}")
        print_stat(f"Items extraits: {global_stats['total_items_extracted']}")
        print_stat(f"Temps écoulé: {str(elapsed).split('.')[0]}")
        print_stat(f"Temps restant estimé: {str(remaining).split('.')[0]}")
    
    # Résumé final
    print_header("📊 RÉSUMÉ FINAL DU TRAITEMENT BP")
    print(f"  {Fore.WHITE}┌{'─'*50}┐")
    print(f"  {Fore.WHITE}│ {Fore.YELLOW}{'STATISTIQUE':<30} {Fore.WHITE}│ {Fore.YELLOW}{'VALEUR':<16} {Fore.WHITE}│")
    print(f"  {Fore.WHITE}├{'─'*50}┤")
    print(f"  {Fore.WHITE}│ Total AO dans la BD          │ {global_stats['total_tenders']:<16} {Fore.WHITE}│")
    print(f"  {Fore.WHITE}│ AO déjà traités              │ {global_stats['skipped_already_done']:<16} {Fore.WHITE}│")
    print(f"  {Fore.WHITE}│ AO traités cette session     │ {global_stats['processed']:<16} {Fore.WHITE}│")
    print(f"  {Fore.WHITE}│ Erreurs                      │ {global_stats['errors']:<16} {Fore.WHITE}│")
    print(f"  {Fore.WHITE}│ Items BP extraits            │ {global_stats['total_items_extracted']:<16} {Fore.WHITE}│")
    print(f"  {Fore.WHITE}└{'─'*50}┘")
    
    total_time = datetime.now() - start_time
    print(f"\n  {Fore.CYAN}⏱️  Temps total: {str(total_time).split('.')[0]}")
    
    print(f"\n{Back.GREEN}{Fore.WHITE}{Style.BRIGHT}{'='*80}")
    print(f"{Back.GREEN}{Fore.WHITE}{Style.BRIGHT}  TRAITEMENT BP PAR LOT TERMINÉ")
    print(f"{Back.GREEN}{Fore.WHITE}{Style.BRIGHT}{'='*80}\n")

# ============================================================================
# MAIN CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Extraction BP - Bordereau des Prix")
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true", help="Traiter tous les AO non traités")
    group.add_argument("--reference", "-r", type=str, help="Référence AO spécifique")
    
    parser.add_argument("--limit", "-l", type=int, default=None,
                       help="Limiter le nombre d'AO à traiter (pour --all)")
    parser.add_argument("--yes", "-y", action="store_true",
                       help="Sauvegarder automatiquement sans confirmation (pour -r)")
    
    args = parser.parse_args()
    
    print(f"\n{Back.BLUE}{Fore.WHITE}{Style.BRIGHT}{'='*80}")
    print(f"{Back.BLUE}{Fore.WHITE}{Style.BRIGHT}  EXTRACTION BP - BORDEREAU DES PRIX")
    print(f"{Back.BLUE}{Fore.WHITE}{Style.BRIGHT}  Supabase Integration v3.1")
    print(f"{Back.BLUE}{Fore.WHITE}{Style.BRIGHT}{'='*80}")
    
    if args.all:
        process_all_tenders(limit=args.limit)
    else:
        if args.yes:
            # Mode sans confirmation
            tender_data = get_tender_files(args.reference)
            if tender_data and tender_data.get("files"):
                files = tender_data["files"]
                best_result = None
                max_items = 0
                
                for file_data in files:
                    result = process_bp_file(file_data["filename"], file_data["file_bytes"])
                    if result.get("success"):
                        items_count = result.get("items_count", 0)
                        if items_count > max_items:
                            max_items = items_count
                            best_result = result
                
                if best_result:
                    bp_result = best_result["bp_result"]
                    doc_level = bp_result.get("document_level", {})
                    items = bp_result.get("items", [])
                    
                    display_bp_summary(doc_level, max_items)
                    display_bp_items(items, max_display=20)
                    display_price_analysis(items)
                    
                    if save_bp_to_supabase(args.reference, bp_result, best_result["filename"]):
                        print_success(f"\n✅ Extraction BP terminée pour {args.reference}")
                    else:
                        print_error(f"\n❌ Erreur sauvegarde pour {args.reference}")
            else:
                print_error(f"\n❌ Pas de fichiers BP pour {args.reference}")
        else:
            process_single_reference(args.reference)

if __name__ == "__main__":
    main()