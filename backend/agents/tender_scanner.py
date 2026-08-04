"""
tender_scanner.py — Africa Tenders Intelligence Module
======================================================
CrystalWater — Traitement d'eau & Refroidissement industriel
https://crystalwater.ma/

FULL SCAN MODE: Scan all pages, only CrystalWater-related tenders.
SKIP EXISTING: Skip tenders already in database.
ENHANCED FILTERS: Strict false positive detection for cleaning/IT/electricity.
VISUAL TERMINAL: Icons for better readability.
ROBUST NAVIGATION: Auto-retry on page timeout, progressive wait, session reset.
SCORING ENGINE: Rule-based scoring using scoring_criteria table (score normalisé 0-100).
"""

import os
import re
import json
import uuid
import sys
import time
import logging
import warnings
import zipfile
import io
import tempfile
import hashlib
import threading
from datetime import datetime, date, timezone
from typing import Optional, List, Dict, Any, Tuple
from urllib.parse import urljoin
from pathlib import Path

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except:
        pass
    os.environ['PYTHONIOENCODING'] = 'utf-8'

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

warnings.filterwarnings("ignore")
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

load_dotenv()

# ─── EMOJIS & ICONS ─────────────────────────────────────────
ICON_WATER = "💧"
ICON_NEW = "🆕"
ICON_SKIP = "⏭️"
ICON_DOWNLOAD = "📥"
ICON_SUCCESS = "✅"
ICON_ERROR = "❌"
ICON_WARN = "⚠️"
ICON_PAGE = "📄"
ICON_DB = "🗄️"
ICON_CLOCK = "🕐"
ICON_STATS = "📊"
ICON_SEARCH = "🔍"
ICON_FILTER = "🔬"
ICON_STOP = "🚫"
ICON_DEADLINE = "⏰"
ICON_SCORE = "⭐"
ICON_ZIP = "📦"
ICON_INDEX = "🤖"
ICON_RETRY = "🔄"
ICON_PAUSE = "⏳"
ICON_RESET = "🔃"

# ─── SCAN CONFIGURATION ───────────────────────────────────────
SCAN_ALL = True
MAX_TEST_TENDERS = float('inf')
MAX_CONSECUTIVE_ERRORS = 10
PAGE_RETRY_ATTEMPTS = 3
ERROR_WAIT_BASE = 15
SESSION_RESET_AFTER_ERRORS = 3
# ────────────────────────────────────────────────────────────────

logger = logging.getLogger("tender_scanner")
logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter('%(message)s'))
logger.addHandler(console_handler)
if not os.path.exists('logs'):
    os.makedirs('logs')
file_handler = logging.FileHandler(f'logs/tender_scanner_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log', encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)

# ─── Docling ─────────────────────────────────────────────────
_docling_converter = None
_docling_available = False

def _init_docling():
    global _docling_converter, _docling_available
    if _docling_converter is not None: return
    try:
        from docling.document_converter import DocumentConverter
        _docling_converter = DocumentConverter()
        _docling_available = True
        logger.info(f"  {ICON_SUCCESS} [DOCLING] Initialisé avec succès")
    except ImportError:
        logger.critical(f"  {ICON_ERROR} [DOCLING] Docling NON INSTALLÉ. pip install docling")
        _docling_available = False
    except Exception as e:
        logger.critical(f"  {ICON_ERROR} [DOCLING] Erreur initialisation: {e}")
        _docling_available = False

# ─── PyMuPDF ──────────────────────────────────────────────
_fitz_available = False

def _check_fitz():
    global _fitz_available
    try:
        import fitz
        _fitz_available = True
        logger.info(f"  {ICON_SUCCESS} [PDF] PyMuPDF disponible")
    except ImportError:
        logger.warning(f"  {ICON_WARN} [PDF] PyMuPDF non installé")
        _fitz_available = False

# ─── PaddleOCR ────────────────────────────────────────────
_paddle_ocr = None
_paddle_ocr_available = False

def _init_paddleocr_fallback():
    global _paddle_ocr, _paddle_ocr_available
    if _paddle_ocr is not None: return
    try:
        from paddleocr import PaddleOCR
    except Exception as e:
        logger.warning(f"  {ICON_WARN} [OCR] PaddleOCR non installé: {e}")
        _paddle_ocr_available = False
        return
    candidate_configs = [
        dict(lang='fr', use_doc_orientation_classify=False, use_doc_unwarping=False, use_textline_orientation=False),
        dict(lang='fr'),
        dict(lang='fr', use_angle_cls=True, show_log=False),
        dict(lang='fr', use_angle_cls=True),
    ]
    try:
        import numpy as np
        test_img = np.full((64, 64, 3), 255, dtype=np.uint8)
    except Exception:
        test_img = None
    for cfg in candidate_configs:
        try:
            engine = PaddleOCR(**cfg)
            if test_img is not None:
                try: engine.ocr(test_img)
                except TypeError: pass
            _paddle_ocr = engine
            _paddle_ocr_available = True
            logger.info(f"  {ICON_SUCCESS} [OCR] PaddleOCR initialisé")
            return
        except Exception as e:
            continue
    logger.warning(f"  {ICON_WARN} [OCR] PaddleOCR indisponible")
    _paddle_ocr_available = False


def _ocr_pdf_fallback(pdf_bytes: bytes, max_pages: int = 10) -> str:
    global _paddle_ocr, _paddle_ocr_available
    if not _paddle_ocr_available or _paddle_ocr is None: return ""
    try:
        from pdf2image import convert_from_bytes
        import numpy as np
        images = convert_from_bytes(pdf_bytes, first_page=1, last_page=max_pages, dpi=200, fmt='jpeg')
        all_text = []
        for image in images:
            img_array = np.array(image.convert('RGB'))
            try: result = _paddle_ocr.ocr(img_array, cls=True)
            except TypeError: result = _paddle_ocr.ocr(img_array)
            if not result: continue
            page_result = result[0] if isinstance(result, list) and result else result
            if isinstance(page_result, dict) and 'rec_texts' in page_result:
                for txt, score in zip(page_result.get('rec_texts', []), page_result.get('rec_scores', [])):
                    if score is None or score > 0.5: all_text.append(txt)
            elif page_result:
                for line in page_result:
                    if line and len(line) >= 2 and line[1][1] > 0.5: all_text.append(line[1][0])
        return "\n".join(all_text)
    except Exception as e:
        logger.debug(f"  [OCR] Erreur PaddleOCR fallback: {e}")
        return ""


def _extract_pdf_with_fitz(file_bytes: bytes) -> str:
    if not _fitz_available: return ""
    try:
        import fitz
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        text_parts = []
        for page in doc:
            text = page.get_text("text")
            if text.strip(): text_parts.append(text.strip())
        doc.close()
        return "\n\n".join(text_parts)
    except Exception as e:
        logger.warning(f"  [PDF] PyMuPDF erreur: {e}")
        return ""


def _convert_doc_to_docx(doc_bytes: bytes) -> Optional[bytes]:
    try:
        text = doc_bytes.decode('latin-1', errors='ignore')
        text = re.sub(r'[^\x20-\x7E\xA0-\xFF\n\r\t\.\,\;\:\!\?\(\)\[\]\{\}\-\+\/\@\#\$\%\^\&\*\=]', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        return text.encode('utf-8')
    except: pass
    try:
        import subprocess
        with tempfile.NamedTemporaryFile(suffix='.doc', delete=False) as tmp_in:
            tmp_in.write(doc_bytes); tmp_in_path = tmp_in.name
        tmp_out_dir = tempfile.mkdtemp()
        subprocess.run(['libreoffice', '--headless', '--convert-to', 'docx', '--outdir', tmp_out_dir, tmp_in_path], timeout=30, capture_output=True)
        docx_files = list(Path(tmp_out_dir).glob('*.docx'))
        if docx_files:
            with open(docx_files[0], 'rb') as f: return f.read()
    except: pass
    return None


def _convert_xls_to_xlsx_bytes(xls_bytes: bytes) -> Optional[bytes]:
    try:
        import xlrd, openpyxl
    except ImportError as e:
        logger.warning(f"  [XLS] xlrd/openpyxl non installes: {e}")
        return None
    try:
        xls_book = xlrd.open_workbook(file_contents=xls_bytes)
        new_wb = openpyxl.Workbook(); new_wb.remove(new_wb.active)
        for sheet in xls_book.sheets():
            ws = new_wb.create_sheet(title=sheet.name[:31] or "Sheet")
            for r in range(sheet.nrows):
                for c in range(sheet.ncols):
                    value = sheet.cell_value(r, c)
                    if value == '': continue
                    ws.cell(row=r + 1, column=c + 1, value=value)
        if not new_wb.sheetnames: return None
        buf = io.BytesIO(); new_wb.save(buf); return buf.getvalue()
    except Exception as e:
        logger.warning(f"  [XLS] Conversion .xls -> .xlsx echouee: {e}")
        return None


def _extract_xls_via_xlrd_text(xls_bytes: bytes) -> str:
    try:
        import xlrd
        wb = xlrd.open_workbook(file_contents=xls_bytes)
        text = ""
        for sheet in wb.sheets()[:10]:
            rows_text = []
            for r in range(sheet.nrows):
                cells = [str(c).strip() for c in sheet.row_values(r) if str(c).strip()]
                if cells: rows_text.append(" | ".join(cells))
            if rows_text: text += f"\n--- {sheet.name} ---\n" + "\n".join(rows_text)
        return text
    except Exception as e:
        logger.warning(f"  [XLS] Extraction directe xlrd echouee: {e}")
        return ""


SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "") or os.getenv("SUPABASE_KEY", "")
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "contact@crystalwater.ma")
BASE_URL = "https://www.marchespublics.gov.ma"
SEARCH_URL = f"{BASE_URL}/index.php?page=entreprise.EntrepriseAdvancedSearch&AllCons&EnCours&domaineActivite=1.13"
TENDERS_TABLE = os.getenv("TENDERS_TABLE", "tenders_3")

CRYSTAL_FORM_DATA = {"nom": "Crystal", "prenom": "Water", "email": "marketing@crystalwater.ma", "raisonSocial": "CrystalWater", "address": "Adresse CrystalWater"}

# ═══════════════ ENHANCED KEYWORDS & FILTERS ═══════════════

STRONG_KEYWORDS = [
    "station de traitement", "station d'epuration", "step", "station de pretraitement", 
    "station de pompage", "ouvrages d'epuration", "eau potable", "aep", 
    "alimentation en eau potable", "adduction d'eau", "production d'eau", 
    "potabilisation", "purification d'eau", "assainissement", "eaux usees", 
    "eaux pluviales", "reseau d'assainissement", "reseau d'evacuation", 
    "reservoir d'eau", "chateau d'eau", "bache a eau", "stockage d'eau", 
    "bassin d'eau", "reservoir sureleve", "dessalement", "osmose inverse", 
    "osmoseur", "demineralisation", "traitement des eaux", "refoulement", 
    "surpression", "groupe electropompe", "surpresseur", "forage d'eau", 
    "forage d'exploitation", "captage", "puits", "borne fontaine", "forage", 
    "conduite d'adduction", "reseau d'eau potable", "reseau de distribution", 
    "canalisation d'eau", "branchement d'eau", "vannes", "clapets", "debitmetre", 
    "debitmetres", "vanne", "clapet", "hydrophone", "pompe immergee", 
    "pompe de surface", "reducteurs de pression", "materiel hydromecanique", 
    "tour de refroidissement", "refroidissement industriel", "circuit de refroidissement", 
    "eau industrielle", "chloration", "desinfection", "coagulation", "floculation", 
    "decantation", "filtration", "lagunage", "boues activees", "soude caustique", 
    "entretien du reseau de distribution d'eau", "entretien du reseau d'assainissement", 
    "rehabilitation des reseaux d'eau", "telegestion d'eau potable", 
    "recherche des fuites", "analyse de la qualite de l'eau", 
    "analyses physico-chimiques et bacteriologiques", "prelevement et d'analyses", 
    "irrigation", "reseaux d'irrigation"
]

MEDIUM_KEYWORDS = ["travaux", "reseaux", "canalisation", "genie civil", "equipement", 
                   "fourniture", "installation", "rehabilitation", "extension", 
                   "construction", "renouvellement", "renforcement", "etude", 
                   "suivi", "schema directeur"]

WATER_DESINFECTION_CONTEXT = [
    "desinfection de l'eau", "desinfection des eaux",
    "desinfection eau potable", "desinfection par chloration",
    "desinfection uv", "desinfection par ozone",
    "station de desinfection", "traitement de desinfection",
    "desinfection du reseau", "desinfection des conduites",
    "desinfection des canalisations", "desinfection reservoir",
    "desinfection chateau d'eau", "desinfection forage"
]

STRICT_EXCLUSIONS = [
    "construction du siege", "batiments industriels", "nettoyage des locaux",
    "nettoyage des batiments", "entretien des locaux", "entretien des batiments",
    "entretien des espaces verts", "entretien menager", "nettoyage et desinfection",
    "desinfection des locaux", "desinfection des batiments", "desinfection des surfaces",
    "prestation de nettoyage", "produits d'entretien", "produits d'hygiene",
    "entretien et nettoyage", "nettoyage et entretien",
    "vetements de travail", "tenues de travail", "chaussures de securite",
    "effets speciaux", "ustensiles de cuisine", "equipements de protection",
    "centrales diesel", "groupe diesel", "pylones 225", "poste 225", 
    "ligne htb", "postes 225/60kv", "postes 60", "lignes 225 kv", 
    "lignes 60 kv", "deviation de lignes", "transport 245 kv",
    "ligne de transport", "separation de lignes", "acheminement distinct",
    "opgw", "relais rph", "analyseurs de soufre",
    "informatique", "logiciel", "licence antivirale", "site web",
    "application mobile", "base de donnees", "certification iso",
    "audit", "formation", "vehicule", "voiture", "ambulance",
    "photovoltaique", "solaire", "dechets solides", "ordures", "decharge",
    "gardiennage", "restauration", "cantine", "imprimerie",
    "fournitures de bureau", "mobilier", "cablage informatique",
    "systeme d'information", "sig", "assistance technique",
    "developpement", "climatiseurs", "rehabilitation des postes",
    "effets speciaux de protection", "protection individuels",
    "achat des imprimes", "graisse silicone", "degagement des dunes",
    "poste 400/225kv", "division exploitation transport"
]

FALSE_POSITIVE_PATTERNS = [
    r"nettoyage\s+(des\s+)?(locaux|batiments|bureaux|administratifs|espaces)",
    r"entretien\s+(des\s+)?(locaux|batiments|bureaux|administratifs|espaces\s+verts)",
    r"desinfection\s+(des\s+)?(locaux|batiments|bureaux|surfaces)",
    r"prestation\s+de\s+nettoyage", r"prestation\s+de\s+lavage",
    r"produits?\s+d'entretien", r"produits?\s+d'hygiene",
    r"entretien,\s+le\s+nettoyage\s+et\s+la\s+desinfection",
    r"entretien,\s+nettoyage\s+et\s+desinfection",
    r"nettoyage\s+et\s+la\s+desinfection",
    r"poste\s+225", r"poste\s+60\s*kv", r"reseau\s+225\s*kv",
    r"ligne\s+htb", r"transformateur", r"huiles?\s+dielectriques?",
    r"groupe\s+diesel", r"centrale\s+diesel", r"centrale\s+tag",
    r"turbine", r"opgw", r"fibre\s+optique",
    r"sectionneurs?\s+72", r"sectionneurs?\s+245", r"disjoncteurs?",
    r"batteries?\s+&?\s*redresseurs?", r"relais\s+rph",
    r"reseau\s+de\s+distribution\s+d'electricite",
    r"reseau\s+de\s+distribution\s+aerien\s+hta",
    r"lignes?\s+225\s*kv", r"lignes?\s+60\s*kv",
    r"postes?\s+225\s*/\s*60\s*kv", r"poste\s+60\s*/\s*22\s*kv",
    r"deviation\s+de\s+lignes", r"pylones?\s+225",
    r"protection\s+des\s+pylones", r"amenagement\s+des\s+troncons\s+opgw",
    r"separation\s+de\s+lignes", r"acheminement\s+distinct",
    r"transport\s+245\s*kv", r"ligne\s+de\s+transport",
    r"remplacement\s+et\s+protection\s+des\s+pylones",
    r"refonte\s+des\s+lignes",
    r"licence\s+(de\s+)?(la\s+)?solution",
    r"certification\s+iso",
    r"systeme\s+d'information\s+geographique",
    r"assistance\s+technique.*informatique",
    r"developpement.*application",
    r"audit\s+(de\s+)?(renouvellement\s+)?(de\s+)?(la\s+)?certification",
    r"detecteurs?\s+de\s+flamme", r"bruleurs?",
    r"eclairage\s+led", r"materiel\s+d'eclairage",
    r"pieces?\s+de\s+rechange\s+electriques?",
    r"chaussures?\s+de\s+securite", r"vetements?\s+de\s+travail",
    r"tenues?\s+de\s+travail", r"ustensiles?\s+de\s+cuisine",
    r"ascenseurs?", r"installations?\s+telephoniques?",
    r"construction\s+du\s+siege", r"points?\s+d'ancrage",
    r"canons?\s+d'arrosage", r"extincteurs?",
    r"acquisition\s+d'un\s+camion", r"acquisition\s+des\s+engins",
    r"vente\s+aux\s+encheres",
    r"materiel\s+medico\s+technique", r"analyseur\s+de\s+coagulation",
    r"panneaux\s+thematiques", r"calibration\s+des\s+spintrem",
    r"controle\s+non\s+destructif", r"vestiaires",
    r"etalonnage\s+des\s+appareils", r"analyses\s+chimiques.*micrographiques",
    r"effets\s+speciaux\s+de\s+protection",
    r"acquisition\s+des\s+effets\s+speciaux",
    r"protection\s+physique\s+des\s+regards",
    r"pose\s+des\s+tampons\s+anti.vandale",
    r"achat\s+des\s+imprimes", r"imprimes\s+pour\s+le\s+compte",
    r"graisse\s+silicone", r"degagement\s+des\s+dunes",
    r"poste\s+400.*kv", r"electrification\s+de\s+la\s+nouvelle",
]


# ═══════════════ SUPABASE HELPERS ═══════════════

def _sb_headers() -> dict:
    return {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", 
            "Content-Type": "application/json", "Prefer": "return=representation"}

def _sb_get(table: str, params: dict = None) -> List[dict]:
    if not SUPABASE_URL or not SUPABASE_KEY: return []
    try:
        r = requests.get(f"{SUPABASE_URL}/rest/v1/{table}", headers=_sb_headers(), 
                        params=params or {}, timeout=15)
        r.raise_for_status(); return r.json() or []
    except: return []

def _sb_upsert_tenders_2(rows: List[dict]) -> bool:
    if not SUPABASE_URL or not SUPABASE_KEY or not rows: return False
    url = f"{SUPABASE_URL}/rest/v1/{TENDERS_TABLE}"
    headers = {**_sb_headers(), "Prefer": "resolution=merge-duplicates,return=minimal"}
    success = 0
    for i in range(0, len(rows), 50):
        try:
            r = requests.post(url, headers=headers, json=rows[i:i+50], 
                            params={"on_conflict": "reference"}, timeout=30)
            if r.status_code in (200, 201, 204): success += len(rows[i:i+50])
        except: pass
    if success: logger.info(f"  [OK] Supabase {TENDERS_TABLE}: {success}/{len(rows)} rows")
    return success > 0

def _sb_patch_tenders_2(reference: str, data: dict) -> bool:
    if not SUPABASE_URL or not SUPABASE_KEY: return False
    try:
        r = requests.patch(f"{SUPABASE_URL}/rest/v1/{TENDERS_TABLE}?reference=eq.{reference}", 
                          headers=_sb_headers(), json=data, timeout=60)
        return r.status_code in (200, 204)
    except: return False

def _sb_delete_tenders_2(reference: str) -> bool:
    if not SUPABASE_URL or not SUPABASE_KEY: return False
    try:
        r = requests.delete(f"{SUPABASE_URL}/rest/v1/{TENDERS_TABLE}?reference=eq.{reference}", 
                           headers=_sb_headers(), timeout=15)
        return r.status_code in (200, 204)
    except: return False

def _sb_get_tenders_2(params: dict = None) -> List[dict]:
    if not SUPABASE_URL or not SUPABASE_KEY: return []
    try:
        r = requests.get(f"{SUPABASE_URL}/rest/v1/{TENDERS_TABLE}", headers=_sb_headers(), 
                        params=params or {}, timeout=15)
        r.raise_for_status(); return r.json() or []
    except: return []

def _sb_upload_zip_to_storage(zip_content: bytes, tender_ref: str) -> Optional[str]:
    if not SUPABASE_URL or not SUPABASE_KEY: return None
    if len(zip_content) > 50 * 1024 * 1024:
        logger.error(f"  [ZIP] Fichier trop volumineux (>50MB) pour {tender_ref}")
        return None
    try:
        safe_ref = tender_ref.replace("/", "_")
        url = f"{SUPABASE_URL}/storage/v1/object/zip_files_tenders/{safe_ref}.zip"
        headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", 
                   "Content-Type": "application/zip", "x-upsert": "true"}
        r = requests.post(url, headers=headers, data=zip_content, timeout=120)
        if r.status_code in (200, 201): 
            return f"{SUPABASE_URL}/storage/v1/object/public/zip_files_tenders/{safe_ref}.zip"
        return None
    except: return None


# ═══════════════ PARSING HELPERS ═══════════════

def parse_deadline(deadline_str: str) -> Optional[datetime]:
    if not deadline_str: return None
    try:
        dl_clean = re.sub(r'[^\d/:\s]', '', deadline_str).strip()
        dl_clean = re.sub(r'\s+', ' ', dl_clean).strip()
        for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y"):
            try: return datetime.strptime(dl_clean[:16], fmt)
            except ValueError: continue
    except: pass
    return None

def is_deadline_passed(deadline_str: str) -> bool:
    dl_date = parse_deadline(deadline_str)
    return dl_date is not None and dl_date < datetime.now()

def is_crystalwater_related(title: str, description: str, acheteur: str = "") -> bool:
    """Vérifie si l'appel d'offre est en relation avec CrystalWater."""
    full_text = f"{title} {description} {acheteur}".lower()
    full_text = full_text.replace('é','e').replace('è','e').replace('ê','e').replace('ë','e')
    full_text = full_text.replace('à','a').replace('â','a').replace('ä','a')
    full_text = full_text.replace('ù','u').replace('û','u').replace('ü','u')
    full_text = full_text.replace('ô','o').replace('ö','o')
    full_text = full_text.replace('î','i').replace('ï','i')
    full_text = full_text.replace('ç','c')
    
    for excl in STRICT_EXCLUSIONS:
        if excl in full_text: 
            return False
    
    if "desinfection" in full_text:
        if not any(ctx in full_text for ctx in WATER_DESINFECTION_CONTEXT):
            return False
    
    water_exceptions = [
        "eau potable", "aep", "assainissement", "station d'epuration", "step", 
        "station de traitement", "station de pompage", "adduction d'eau", 
        "reseau d'eau", "reseau d'assainissement", "vannes", "clapets", 
        "debitmetre", "forage d'eau", "reservoir d'eau", "chateau d'eau", 
        "conduite d'adduction", "traitement des eaux", "dessalement", 
        "eaux pluviales", "eaux usees", "irrigation", "potabilisation"
    ]
    
    for pattern in FALSE_POSITIVE_PATTERNS:
        if re.search(pattern, full_text):
            if not any(exc in full_text for exc in water_exceptions): 
                return False
    
    if not any(kw in full_text for kw in STRONG_KEYWORDS): 
        return False
    
    return True

def is_false_positive(title: str, description: str) -> bool:
    """Détecte les faux positifs pour le nettoyage de la base de données."""
    full_text = f"{title} {description}".lower()
    water_exceptions = [
        "eau potable", "aep", "assainissement", "station d'epuration", "step", 
        "station de traitement", "station de pompage", "adduction d'eau", 
        "reseau d'eau", "reseau d'assainissement", "vannes", "clapets", 
        "debitmetre", "forage d'eau", "reservoir d'eau", "chateau d'eau", 
        "conduite d'adduction", "traitement des eaux", "dessalement"
    ]
    for pattern in FALSE_POSITIVE_PATTERNS:
        if re.search(pattern, full_text):
            if not any(exc in full_text for exc in water_exceptions): 
                return True
    return False


# ═══════════════ SCORING ENGINE ═══════════════

def _sb_get_criteria(params: dict = None) -> List[dict]:
    """Récupère les critères de scoring depuis la table scoring_criteria."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return []
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/scoring_criteria",
            headers=_sb_headers(),
            params=params or {},
            timeout=15
        )
        r.raise_for_status()
        return r.json() or []
    except:
        return []


def _get_tender_field_value(tender: dict, field_name: str) -> str:
    """
    Extrait la valeur d'un champ de l'AO pour la comparaison.
    Gère le mapping entre les field_name logiques et les colonnes réelles de tenders_3.
    """
    import re as _re

    if field_name in tender:
        val = tender[field_name]
        if val is None: return "0"
        if isinstance(val, (int, float)): return str(val)
        return str(val)

    if field_name == "turnover":
        val = tender.get("chiffre_affaires", "0")
        return str(val) if val else "0"
    
    if field_name == "experience":
        val = tender.get("nombre_references", "0")
        return str(val) if val else "0"
    
    if field_name == "estimated_amount":
        val = tender.get("avis_estimation_ttc", "0")
        if val:
            cleaned = _re.sub(r'[^\d.]', '', str(val))
            return cleaned if cleaned else "0"
        val = tender.get("estimation", "0")
        if val:
            cleaned = _re.sub(r'[^\d.]', '', str(val))
            return cleaned if cleaned else "0"
        return "0"

    if field_name == "city":
        val = tender.get("lieu_execution", "")
        return str(val) if val else ""

    if field_name == "region":
        val = tender.get("lieu_execution", "")
        return str(val) if val else ""

    if field_name == "acheteur":
        val = tender.get("acheteur_public", "") or tender.get("acheteur_detecte", "")
        return str(val) if val else ""

    for key in ["objet", "categorie", "procedure", "lieu_execution"]:
        if field_name == key:
            val = tender.get(key, "")
            return str(val) if val else ""

    return str(tender.get(field_name, "0") or "0")


def _compare_values(ao_value: str, operator: str, target_value: str) -> bool:
    """
    Compare deux valeurs selon l'opérateur.
    Nettoie les valeurs pour permettre la comparaison numérique même avec du texte (DHS, espaces, etc.).
    """
    import re as _re

    ao_clean = _re.sub(r'[^\d.]', '', str(ao_value))
    target_clean = _re.sub(r'[^\d.]', '', str(target_value))

    try:
        ao_num = float(ao_clean) if ao_clean else 0
        target_num = float(target_clean) if target_clean else 0
        
        if operator == '=':   return ao_num == target_num
        if operator == '<':   return ao_num < target_num
        if operator == '<=':  return ao_num <= target_num
        if operator == '>':   return ao_num > target_num
        if operator == '>=':  return ao_num >= target_num
    except (ValueError, TypeError):
        pass

    ao_str = str(ao_value).lower().strip()
    target_str = str(target_value).lower().strip()
    
    for char in "éèêëàâäùûüôöîïç":
        replacement = {'é':'e','è':'e','ê':'e','ë':'e','à':'a','â':'a','ä':'a',
                       'ù':'u','û':'u','ü':'u','ô':'o','ö':'o','î':'i','ï':'i','ç':'c'}[char]
        ao_str = ao_str.replace(char, replacement)
        target_str = target_str.replace(char, replacement)

    if operator == '=':   return ao_str == target_str
    if operator == '<':   return ao_str < target_str
    if operator == '<=':  return ao_str <= target_str
    if operator == '>':   return ao_str > target_str
    if operator == '>=':  return ao_str >= target_str

    return False


def compute_score(title: str = "", description: str = "", country: str = "",
                  deadline: str = "", acheteur: str = "", tender_data: dict = None) -> int:
    """
    Calcule le score d'un AO en pourcentage (0-100) selon les critères actifs.
    
    Formule : (points_obtenus / points_max_possibles) * 100
    
    Si aucun critère en base, fallback sur STRONG_KEYWORDS.
    """
    if tender_data is None:
        tender_data = {}

    try:
        criteria = _sb_get_criteria({"is_active": "eq.true", "order": "weight.desc"})
    except:
        criteria = []

    # Fallback keywords si pas de critères en BD
    if not criteria:
        full_text = f"{title} {description} {acheteur}".lower()
        full_text = full_text.replace('é','e').replace('è','e').replace('ê','e').replace('ë','e')
        full_text = full_text.replace('à','a').replace('â','a').replace('ä','a')
        full_text = full_text.replace('ù','u').replace('û','u').replace('ü','u')
        full_text = full_text.replace('ô','o').replace('ö','o')
        full_text = full_text.replace('î','i').replace('ï','i')
        full_text = full_text.replace('ç','c')
        
        score = 0
        max_possible = 0
        for i, kw in enumerate(STRONG_KEYWORDS):
            weight = 10 if i < 10 else 8 if i < 20 else 6
            max_possible += weight
            if kw in full_text:
                score += weight
        
        if max_possible > 0:
            score = int((score / max_possible) * 100)
        
        dl_date = parse_deadline(deadline)
        if dl_date:
            days_left = (dl_date - datetime.now()).days
            if days_left < 0:
                score = max(0, score - 10)
            elif days_left <= 7:
                score = min(100, score + 5)
            elif days_left <= 30:
                score = min(100, score + 3)
        
        return max(0, min(100, score))

    # Scoring basé sur les critères de la BD
    score = 0
    max_possible = 0
    matched = []
    
    for c in criteria:
        field_name = c.get("field_name", "")
        operator = c.get("operator", "=")
        target_value = c.get("value", "")
        weight = c.get("weight", 1)
        
        max_possible += weight
        
        ao_value = _get_tender_field_value(tender_data, field_name)
        
        if _compare_values(ao_value, operator, target_value):
            score += weight
            matched.append(f"{field_name} {operator} {target_value} (+{weight})")
    
    # Normaliser le score sur 100 (pourcentage)
    if max_possible > 0:
        percentage = int((score / max_possible) * 100)
    else:
        percentage = 0
    
    # Bonus/Malus deadline
    dl_date = parse_deadline(deadline)
    if dl_date:
        days_left = (dl_date - datetime.now()).days
        if days_left < 0:
            percentage = max(0, percentage - 10)
        elif days_left <= 7:
            percentage = min(100, percentage + 5)
        elif days_left <= 14:
            percentage = min(100, percentage + 3)
        elif days_left <= 30:
            percentage = min(100, percentage + 2)
    
    final_score = max(0, min(100, percentage))
    
    if matched:
        logger.debug(f"[Scoring] {tender_data.get('reference', '?')}: {score}/{max_possible} = {final_score}%, matched={matched}")
    
    return final_score


def recalculate_all_scores() -> int:
    """
    Recalcule le score de tous les AO en base.
    À appeler après chaque modification des critères.
    """
    logger.info(f"{ICON_SCORE} Recalcul des scores pour tous les AO...")
    
    try:
        tenders = _sb_get_tenders_2({
            "select": "*",
            "limit": "10000",
            "order": "reference"
        })

        if not tenders:
            logger.info("Aucun AO à mettre à jour")
            return 0

        updated = 0
        for tender in tenders:
            try:
                new_score = compute_score(
                    title=tender.get("objet", ""),
                    description=f"{tender.get('categorie', '')} {tender.get('procedure', '')} {tender.get('lieu_execution', '')}",
                    country="Morocco",
                    deadline=str(tender.get("date_limite_remise_plis", "")),
                    acheteur=tender.get("acheteur_public", ""),
                    tender_data=tender
                )

                old_score = tender.get("relevance_score", 0)
                if new_score != old_score:
                    success = _sb_patch_tenders_2(tender["reference"], {"relevance_score": new_score})
                    if success:
                        updated += 1
                        logger.debug(f"[Scoring] {tender['reference']}: {old_score} → {new_score}")
            except Exception as e:
                logger.debug(f"Erreur recalcul pour {tender.get('reference')}: {e}")
                continue

        logger.info(f"{ICON_SUCCESS} Scores recalculés : {updated} AO mis à jour sur {len(tenders)}")
        return updated
    except Exception as e:
        logger.error(f"Erreur lors du recalcul des scores: {e}")
        return 0


def make_tender_key(title: str, reference: str = "") -> str:
    if reference: return f"ref:{reference}"
    return f"title:{re.sub(r'\s+', ' ', title[:150].lower().strip())}"


# ═══════════════ ROW EXTRACTION ═══════════════

def _extract_row_data(row, page_url, seen_refs, existing_refs, existing_references, existing_objects):
    """Extrait les données d'une ligne d'appel d'offre."""
    try:
        ref_input = row.select_one("input[name*='refCons']")
        reference = ref_input.get("value", "") if ref_input else ""
        
        ref_span = row.select_one("span.ref")
        ref_visible = ref_span.get_text(strip=True) if ref_span else ""
        
        objet_text = ""
        objet_div = row.select_one("div[id*='panelBlocObjet']")
        if objet_div: 
            objet_text = re.sub(r'^Objet\s*:\s*', '', objet_div.get_text(strip=True)).strip()
        
        acheteur = ""
        acheteur_div = row.select_one("div[id*='panelBlocDenomination']")
        if acheteur_div: 
            acheteur = re.sub(r'^Acheteur\s+public\s*:\s*', '', acheteur_div.get_text(strip=True)).strip()
        
        categorie = ""
        cat_div = row.select_one("div[id*='panelBlocCategorie']")
        if cat_div: 
            categorie = cat_div.get_text(strip=True)
        
        date_pub = ""
        td_col90 = row.select_one("td.col-90")
        if td_col90:
            for d in td_col90.find_all("div"):
                text = d.get_text(strip=True)
                if re.match(r'\d{2}/\d{2}/\d{4}', text): 
                    date_pub = text
                    break
        
        deadline = ""
        deadline_parsed = None
        dl_div = row.select_one("div.cloture-line")
        if dl_div:
            deadline_parts = []
            for child in dl_div.children:
                if child.name == 'br': deadline_parts.append(' ')
                elif child.string: deadline_parts.append(child.string.strip())
            deadline = ''.join(deadline_parts).strip()
            if not deadline: deadline = dl_div.get_text(separator=' ', strip=True)
            parsed_dl = parse_deadline(deadline)
            if parsed_dl: deadline_parsed = parsed_dl.isoformat()
        
        if is_deadline_passed(deadline): 
            return None, "deadline_passed"
        
        reponse_electronique_obligatoire = None
        if row.select_one("img[src*='reponse-elec-oblig']"): 
            reponse_electronique_obligatoire = True
        elif row.select_one("img[src*='reponse-elec-non']"): 
            reponse_electronique_obligatoire = False
        
        procedure = ""
        proc_div = row.select_one("div[id*='type_procedure']")
        if proc_div: 
            procedure = proc_div.get_text(strip=True)
        
        lieu_exec = ""
        lieu_div = row.select_one("div[id*='panelBlocLieuxExec']")
        if lieu_div: 
            lieu_exec = re.sub(r'\s+', ' ', lieu_div.get_text(strip=True)).strip()
        
        detail_url = ""
        actions_td = row.select_one("td.actions")
        if actions_td:
            link = actions_td.select_one("a[href*='DetailConsultation']")
            if link:
                href = link.get("href", "")
                detail_url = f"{BASE_URL}/{href}" if href.startswith("?") else urljoin(BASE_URL, href)
        
        title = objet_text or f"{ref_visible or reference} - {categorie}"
        if len(title) < 10: 
            return None, "title_too_short"
        
        if not is_crystalwater_related(title, f"{categorie} {procedure} {lieu_exec}", acheteur): 
            return None, "not_crystalwater_related"
        
        final_reference = ref_visible or reference
        
        if final_reference and final_reference in existing_references:
            return None, "already_in_db_by_ref"
        
        key = make_tender_key(title, final_reference)
        if key in seen_refs or key in existing_refs:
            return None, "already_in_db_by_key"
        
        normalized_obj = re.sub(r'\s+', ' ', objet_text[:200].lower().strip())
        if normalized_obj and normalized_obj in existing_objects:
            return None, "already_in_db_by_obj"
        
        seen_refs.add(key)
        if normalized_obj:
            existing_objects.add(normalized_obj)
        
        date_publication_parsed = None
        if date_pub:
            try:
                for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
                    try: 
                        date_publication_parsed = datetime.strptime(date_pub.strip()[:10], fmt).date().isoformat()
                        break
                    except: continue
            except: pass

        score = compute_score(
            title=objet_text or "",
            description=f"{categorie} {procedure} {lieu_exec}",
            country="Morocco",
            deadline=deadline,
            acheteur=acheteur or "",
            tender_data={
                "objet": objet_text or "",
                "categorie": categorie or "",
                "procedure": procedure or "",
                "lieu_execution": lieu_exec or "",
                "acheteur_public": acheteur or "",
                "chiffre_affaires": "0",
                "nombre_references": "0",
                "estimation": "0",
                "avis_estimation_ttc": "0",
            }
        )
        
        tender_data = {
            "reference": final_reference or str(uuid.uuid4()),
            "procedure": procedure[:100] if procedure else None,
            "categorie": categorie[:200] if categorie else None,
            "date_publication": date_publication_parsed,
            "objet": objet_text[:500] if objet_text else None,
            "acheteur_public": acheteur[:300] if acheteur else None,
            "lots": None,
            "lieu_execution": lieu_exec[:300] if lieu_exec else None,
            "date_limite_remise_plis": deadline_parsed,
            "reponse_electronique_obligatoire": reponse_electronique_obligatoire,
            "source_url": detail_url or page_url,
            "dce_zip_url": None,
            "dce_zip_base64": None,
            "status": "new",
            "qualification_status": "unseen",
            "nb_fichiers": None,
            "seen": False,
            "relevance_score": score,
            "estimation": None,
            "caution_provisoire": None,
            "caution_definitive": None,
            "visite_lieux_obligatoire": None,
            "classe_demandee": None,
            "attestation_reference_demandee": None
        }
        
        return tender_data, "success"
        
    except Exception as e:
        logger.error(f"  [ERROR] _extract_row_data: {e}")
        return None, "error"


# ═══════════════ AUTO-INDEXATION ═══════════════

def auto_index_tender(tender_ref: str):
    try:
        from agents.zip_chatbot import index_tender_documents
        tender = get_tender_row(tender_ref)
        zip_bytes = fetch_zip_bytes(tender_ref, tender.get("dce_zip_url"))
        if zip_bytes:
            logger.info(f"  [AUTO-INDEX] Démarrage indexation pour {tender_ref}...")
            result = index_tender_documents(tender_ref, zip_bytes=zip_bytes)
            logger.info(f"  [AUTO-INDEX] {tender_ref}: {result.get('chunks_created', 0)} chunks créés")
    except Exception as e:
        logger.warning(f"  [AUTO-INDEX] Échec pour {tender_ref}: {e}")


# ═══════════════ ZIP VIEWER COMPATIBILITY ═══════════════

def get_tender_row(tender_id: str) -> dict:
    if not SUPABASE_URL or not SUPABASE_KEY: raise Exception("Supabase not configured")
    try:
        r = requests.get(f"{SUPABASE_URL}/rest/v1/{TENDERS_TABLE}", headers=_sb_headers(),
            params={"reference": f"eq.{tender_id}", "select": "reference,objet,dce_zip_url"}, timeout=15)
        r.raise_for_status(); rows = r.json()
    except Exception as e: raise Exception(f"Database error: {e}")
    if not rows: raise Exception(f"Tender {tender_id} not found")
    return rows[0]

def fetch_zip_bytes(tender_id: str, dce_zip_url: Optional[str]) -> bytes:
    if not dce_zip_url:
        safe_ref = tender_id.replace("/", "_")
        dce_zip_url = f"{SUPABASE_URL}/storage/v1/object/public/zip_files_tenders/{safe_ref}.zip"
    try:
        r = requests.get(dce_zip_url, timeout=30)
        if r.status_code == 404: raise Exception("ZIP not found")
        r.raise_for_status()
    except Exception as e: raise Exception(f"Storage error: {e}")
    data = r.content
    if not data or len(data) < 100: raise Exception("Empty or corrupted ZIP")
    return data

def open_zip(data: bytes) -> zipfile.ZipFile:
    try: return zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile: raise Exception("Invalid ZIP")


# ═══════════════ DCE DOWNLOAD ═══════════════

def download_dce_with_form_fast(page, detail_url: str, tender_ref: str) -> Optional[Dict[str, Any]]:
    start_time = time.time()
    logger.info(f"  [DOWNLOAD] DCE: {tender_ref}")
    try:
        page.goto(detail_url, wait_until="domcontentloaded", timeout=30000); page.wait_for_timeout(5000)
        download_selectors = ["a:has-text('Dossier de Consultation')", "a:has-text('Telecharger le DCE')", 
                            "a:has-text('Telecharger')", "a:has-text('DCE')", "a[href*='TelechargerDCE']", 
                            "a[href*='telecharger']", "a[href*='DCE']"]
        download_clicked = False
        for selector in download_selectors:
            try:
                for el in page.query_selector_all(selector):
                    if el.is_visible(): 
                        el.scroll_into_view_if_needed(); page.wait_for_timeout(1000)
                        el.click(); download_clicked = True; break
                if download_clicked: break
            except: continue
        if not download_clicked: 
            logger.warning("  [WARN] No download link found"); return None
        page.wait_for_timeout(5000); page.wait_for_load_state("domcontentloaded")
        if not page.query_selector("#ctl0_CONTENU_PAGE_EntrepriseFormulaireDemande_nom") or \
           not page.query_selector("#ctl0_CONTENU_PAGE_EntrepriseFormulaireDemande_nom").is_visible():
            logger.warning("  [WARN] Form not found"); return None
        logger.info("  [FORM] Filling form...")
        for selector, value in [
            ("#ctl0_CONTENU_PAGE_EntrepriseFormulaireDemande_nom", CRYSTAL_FORM_DATA["nom"]),
            ("#ctl0_CONTENU_PAGE_EntrepriseFormulaireDemande_prenom", CRYSTAL_FORM_DATA["prenom"]),
            ("#ctl0_CONTENU_PAGE_EntrepriseFormulaireDemande_email", CRYSTAL_FORM_DATA["email"]),
            ("#ctl0_CONTENU_PAGE_EntrepriseFormulaireDemande_raisonSocial", CRYSTAL_FORM_DATA.get("raisonSocial", "")),
            ("#ctl0_CONTENU_PAGE_EntrepriseFormulaireDemande_address", CRYSTAL_FORM_DATA.get("address", ""))]:
            if not value: continue
            try:
                field = page.query_selector(selector)
                if field and field.is_visible(): 
                    field.scroll_into_view_if_needed(); page.wait_for_timeout(300)
                    field.click(); field.fill(""); field.type(value, delay=50)
            except: pass
        try:
            cb = page.query_selector("#ctl0_CONTENU_PAGE_EntrepriseFormulaireDemande_accepterConditions")
            if cb and not cb.is_checked(): 
                cb.scroll_into_view_if_needed(); page.wait_for_timeout(500)
                cb.click(); page.wait_for_timeout(500)
            if cb and not cb.is_checked(): 
                page.evaluate("var c=document.getElementById('ctl0_CONTENU_PAGE_EntrepriseFormulaireDemande_accepterConditions');if(c){c.checked=true;c.dispatchEvent(new Event('change',{bubbles:true}));}")
        except: pass
        page.wait_for_timeout(1000)
        validate_btn = page.query_selector("#ctl0_CONTENU_PAGE_validateButton")
        if not validate_btn: logger.error("  [ERROR] Validate button not found"); return None
        page.evaluate("var b=document.getElementById('ctl0_CONTENU_PAGE_validateButton');if(b){b.removeAttribute('onclick');b.style.display='inline-block';}")
        page.wait_for_timeout(500); validate_btn.scroll_into_view_if_needed(); page.wait_for_timeout(1000)
        validate_btn.click()
        page.wait_for_timeout(5000); page.wait_for_load_state("domcontentloaded")
        download_btn = None
        for selector in ["#ctl0_CONTENU_PAGE_EntrepriseDownloadDce_completeDownload", 
                        "a.bouton-telecharger-long230", 
                        "a:has-text('Telecharger le Dossier de consultation')"]:
            try:
                btn = page.query_selector(selector)
                if btn and btn.is_visible(): download_btn = btn; break
            except: continue
        if not download_btn: logger.error("  [ERROR] Download button not found"); return None
        page.evaluate("var b=document.getElementById('ctl0_CONTENU_PAGE_EntrepriseDownloadDce_completeDownload');if(b){b.removeAttribute('onclick');b.style.display='inline-block';}")
        page.wait_for_timeout(500); download_btn.scroll_into_view_if_needed(); page.wait_for_timeout(1000)
        logger.info("  [WAIT] Waiting for ZIP...")
        try:
            with page.expect_download(timeout=300000) as download_info: download_btn.click()
            download = download_info.value
            try: zip_path = download.path()
            except Exception as e: logger.warning(f"  [STOP] Download cancelled: {e}"); return None
            if not zip_path: logger.error("  [ERROR] Empty path"); return None
            with open(zip_path, 'rb') as f: zip_content = f.read()
            if not zip_content or len(zip_content) < 100: logger.error("  [ERROR] ZIP empty"); return None
            download_time = time.time() - start_time
            logger.info(f"  [OK] ZIP received: {len(zip_content)} bytes in {download_time:.2f}s")
            supabase_url = _sb_upload_zip_to_storage(zip_content, tender_ref)
            total_time = time.time() - start_time
            if supabase_url:
                threading.Thread(target=auto_index_tender, args=(tender_ref,), daemon=True).start()
            return {"dce_zip_url": supabase_url, "download_time": download_time, "total_time": total_time}
        except PlaywrightTimeout: logger.error("  [ERROR] Timeout (5 min)"); return None
        except KeyboardInterrupt: logger.warning("  [STOP] Ctrl+C"); return None
    except Exception as e: logger.error(f"  [ERROR] DCE: {type(e).__name__}: {e}"); return None


# ═══════════════ SCAN ENGINE ═══════════════

def clean_database():
    try:
        tenders = _sb_get_tenders_2({"select": "reference,objet,source_url", "limit": "10000", "order": "reference"})
        if not tenders: return 0, 0
        seen_keys = set(); duplicates_removed = 0; false_positives_removed = 0
        for t in tenders:
            if is_false_positive(t.get("objet", ""), ""):
                if _sb_delete_tenders_2(t.get("reference", "")): false_positives_removed += 1; continue
            key = make_tender_key(t.get("objet", ""), t.get("reference", ""))
            if key in seen_keys:
                if _sb_delete_tenders_2(t.get("reference", "")): duplicates_removed += 1
            else: seen_keys.add(key)
        return duplicates_removed, false_positives_removed
    except: return 0, 0

def load_existing_data() -> Tuple[set, set, set]:
    existing_keys = set(); existing_references = set(); existing_objects = set()
    try:
        tenders = _sb_get_tenders_2({"select": "reference,objet", "limit": "10000"})
        for t in tenders:
            ref = t.get("reference", ""); obj = t.get("objet", "")
            key = make_tender_key(obj, ref)
            if key: existing_keys.add(key)
            if ref: existing_references.add(ref)
            if obj:
                normalized_obj = re.sub(r'\s+', ' ', obj[:200].lower().strip())
                if normalized_obj: existing_objects.add(normalized_obj)
        logger.info(f"  [DB] {len(existing_keys)} offres existantes chargées")
    except Exception as e: logger.warning(f"  [DB] Erreur chargement données existantes: {e}")
    return existing_keys, existing_references, existing_objects

def _save_tender_to_supabase(tender: dict):
    if not SUPABASE_URL or not SUPABASE_KEY: return
    try: _sb_upsert_tenders_2([tender])
    except: pass

def scan_single_page_modified(page, context, page_num, existing_keys, existing_references, 
                             existing_objects, seen_refs, tenders_extracted_count, 
                             skipped_count, extraction_times, cw_on_page):
    new_tenders = []
    rows = BeautifulSoup(page.content(), "html.parser").select("tr:has(td.col-450)")
    if not rows: return new_tenders
    for row in rows:
        if not SCAN_ALL and tenders_extracted_count[0] >= MAX_TEST_TENDERS: return new_tenders
        result, status = _extract_row_data(row, page.url, seen_refs, existing_keys, existing_references, existing_objects)
        if result is None:
            skipped_count[status] = skipped_count.get(status, 0) + 1
            continue
        cw_on_page[0] += 1
        _save_tender_to_supabase(result)
        if result.get("reference"): existing_references.add(result["reference"])
        detail_url = result.get("source_url", "")
        tenders_extracted_count[0] += 1
        tender_num = tenders_extracted_count[0]
        score = result.get('relevance_score', 0)
        score_stars = "⭐" * min(5, score // 20)
        obj_short = result['objet'][:70] + "..." if len(result.get('objet', '')) > 70 else result.get('objet', '')
        print(f"  {ICON_WATER} [TENDER #{tender_num}] {obj_short}")
        print(f"       {ICON_SCORE} Score: {score}/100 {score_stars}  |  {ICON_DB} {result['reference']}")
        tender_start = time.time()
        if detail_url:
            dce_page = context.new_page()
            try:
                dce_info = download_dce_with_form_fast(dce_page, detail_url, result["reference"])
                if dce_info:
                    if dce_info.get("dce_zip_url"): 
                        _sb_patch_tenders_2(result["reference"], {"dce_zip_url": dce_info["dce_zip_url"]})
                    total_tender_time = time.time() - tender_start
                    extraction_times.append({"tender_ref": result["reference"], "objet": result.get("objet", "")[:100], "total_time": total_tender_time})
                    print(f"       {ICON_ZIP} DCE téléchargé en {total_tender_time:.1f}s {ICON_INDEX}")
                    new_tenders.append(result)
            finally: dce_page.close()
        else: print(f"       {ICON_SKIP} Pas de DCE disponible")
    return new_tenders


def _reset_search_session(page):
    try:
        print(f"  {ICON_RESET} Réinitialisation de la session de recherche...")
        page.goto(SEARCH_URL, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(5000)
        try: page.click("#ctl0_CONTENU_PAGE_AdvancedSearch_lancerRecherche", timeout=15000)
        except:
            try: page.click("input[value='Lancer la recherche']", timeout=10000)
            except: page.evaluate("document.querySelector('form').submit()")
        page.wait_for_timeout(5000)
        try: page.wait_for_selector("tr:has(td.col-450)", timeout=45000)
        except: pass
        print(f"  {ICON_SUCCESS} Session réinitialisée avec succès")
        return True
    except Exception as e:
        print(f"  {ICON_ERROR} Échec réinitialisation: {e}")
        return False


def run_tender_scan():
    _init_docling(); _check_fitz()
    if not _docling_available: return
    tenders_extracted_count = [0]; skipped_count = {}; extraction_times = []; cw_on_page = [0]
    consecutive_errors = 0
    
    print("\n" + "=" * 70)
    print(f"  {ICON_WATER} CrystalWater - Tender Scanner {ICON_WATER}")
    print("=" * 70)
    if SCAN_ALL: print(f"  {ICON_DB} Table: {TENDERS_TABLE}  |  Mode: SCAN COMPLET")
    else: print(f"  {ICON_DB} Table: {TENDERS_TABLE}  |  Max: {MAX_TEST_TENDERS}")
    print(f"  {ICON_FILTER} Filtre: CrystalWater UNIQUEMENT (faux positifs exclus)")
    print(f"  {ICON_CLOCK} Début: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 70 + "\n")
    print(f"  {ICON_DB} Chargement des offres existantes...")
    existing_keys, existing_references, existing_objects = load_existing_data()
    print(f"  {ICON_DB} {len(existing_keys)} offres déjà en base\n")
    seen_refs = set(); total_pages = 0; last_successful_page = 1
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'])
        context = browser.new_context(viewport={"width": 1366, "height": 768}, locale="fr-FR", timezone_id="Africa/Casablanca", accept_downloads=True)
        page = context.new_page()
        
        print(f"  {ICON_SEARCH} Navigation vers le site...")
        for attempt in range(3):
            try: page.goto(SEARCH_URL, wait_until="networkidle", timeout=60000); break
            except:
                if attempt == 2: raise
                time.sleep(5)
        print(f"  {ICON_SUCCESS} Site chargé\n")
        page.wait_for_timeout(5000)
        
        try: page.click("#ctl0_CONTENU_PAGE_AdvancedSearch_lancerRecherche", timeout=15000)
        except:
            try: page.click("input[value='Lancer la recherche']", timeout=10000)
            except: page.evaluate("document.querySelector('form').submit()")
        page.wait_for_timeout(5000)
        try: page.wait_for_selector("tr:has(td.col-450)", timeout=45000)
        except: browser.close(); return
        
        total_pages = 500
        try:
            nb = page.query_selector("#ctl0_CONTENU_PAGE_resultSearch_nombrePageTop")
            if nb: total_pages = int(nb.inner_text().strip())
            print(f"  {ICON_PAGE} Nombre total de pages: {total_pages}\n")
        except: print(f"  {ICON_WARN} Pages estimées: {total_pages}\n")
        
        print("=" * 70)
        print(f"  {ICON_SEARCH} DÉBUT DU SCAN")
        print("=" * 70 + "\n")
        page_num = 1
        
        while page_num <= total_pages:
            if not SCAN_ALL and tenders_extracted_count[0] >= MAX_TEST_TENDERS: break
            
            if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                print(f"\n  {ICON_STOP} Trop d'erreurs consécutives ({MAX_CONSECUTIVE_ERRORS}). Arrêt du scan.")
                break
            
            if consecutive_errors > 0 and consecutive_errors % SESSION_RESET_AFTER_ERRORS == 0:
                wait_time = ERROR_WAIT_BASE * consecutive_errors
                print(f"\n  {ICON_RESET} {consecutive_errors} erreurs - Reset session (pause {wait_time}s)...")
                time.sleep(wait_time)
                if _reset_search_session(page):
                    consecutive_errors = 0
                    page_num = last_successful_page + 1
                    continue
                else:
                    consecutive_errors += 1
            
            if page_num > 1:
                if consecutive_errors > 0:
                    wait_time = ERROR_WAIT_BASE * consecutive_errors
                    print(f"  {ICON_PAUSE} Pause de {wait_time}s avant page {page_num}...")
                    time.sleep(wait_time)
                
                nav_success = False
                last_error = None
                
                for retry in range(PAGE_RETRY_ATTEMPTS):
                    try:
                        page.fill("#ctl0_CONTENU_PAGE_resultSearch_numPageTop", str(page_num))
                        page.wait_for_timeout(1000)
                        page.press("#ctl0_CONTENU_PAGE_resultSearch_numPageTop", "Enter")
                        page.wait_for_timeout(8000)
                        
                        try: 
                            page.wait_for_selector("tr:has(td.col-450)", timeout=30000)
                            nav_success = True
                            break
                        except PlaywrightTimeout:
                            last_error = "timeout"
                            if retry < PAGE_RETRY_ATTEMPTS - 1:
                                print(f"  {ICON_RETRY} Page {page_num} - Timeout, tentative {retry+2}/{PAGE_RETRY_ATTEMPTS}...")
                                page.wait_for_timeout(5000)
                            else:
                                print(f"  {ICON_WARN} Page {page_num}/{total_pages} - Timeout après {PAGE_RETRY_ATTEMPTS} tentatives")
                                try:
                                    next_link = page.query_selector("a[href*='page='] >> text=Suivant")
                                    if next_link:
                                        next_link.click()
                                        page.wait_for_timeout(8000)
                                        page.wait_for_selector("tr:has(td.col-450)", timeout=30000)
                                        nav_success = True
                                        break
                                except:
                                    pass
                                nav_success = True
                                break
                    except Exception as e:
                        last_error = str(e)[:100]
                        if retry < PAGE_RETRY_ATTEMPTS - 1:
                            print(f"  {ICON_RETRY} Page {page_num} - Erreur, tentative {retry+2}/{PAGE_RETRY_ATTEMPTS}...")
                            page.wait_for_timeout(5000)
                        else:
                            print(f"  {ICON_ERROR} Page {page_num} - Échec après {PAGE_RETRY_ATTEMPTS} tentatives")
                            if last_error:
                                print(f"       Détail: {last_error}")
                
                if not nav_success:
                    consecutive_errors += 1
                    page_num += 1
                    continue
                
                last_successful_page = page_num
                consecutive_errors = 0
            
            rows = BeautifulSoup(page.content(), "html.parser").select("tr:has(td.col-450)")
            
            if not rows:
                print(f"  {ICON_PAGE} Page {page_num}/{total_pages} - Vide (skip)")
                page_num += 1
                continue
            
            cw_on_page[0] = 0; skipped_this_page = {}
            new_on_page = scan_single_page_modified(page, context, page_num, existing_keys, existing_references, existing_objects, seen_refs, tenders_extracted_count, skipped_this_page, extraction_times, cw_on_page)
            total_skipped = sum(skipped_this_page.values())
            
            print(f"  ┌─ {ICON_PAGE} PAGE {page_num}/{total_pages} ─────────────────────────────")
            print(f"  │  Offres sur la page: {len(rows)}")
            print(f"  │  {ICON_WATER} CrystalWater: {cw_on_page[0]}")
            print(f"  │  {ICON_NEW} Nouveaux extraits: {len(new_on_page)}")
            print(f"  │  {ICON_SKIP} Skippés: {total_skipped}")
            if total_skipped > 0:
                for status, count in sorted(skipped_this_page.items(), key=lambda x: x[1], reverse=True)[:3]:
                    status_icon = {"already_in_db_by_ref": ICON_DB, "already_in_db_by_key": ICON_DB, "already_in_db_by_obj": ICON_DB, "not_crystalwater_related": ICON_STOP, "deadline_passed": ICON_DEADLINE, "title_too_short": ICON_WARN}.get(status, ICON_SKIP)
                    print(f"  │     {status_icon} {status}: {count}")
            print(f"  │  {ICON_STATS} Total extraits: {tenders_extracted_count[0]}")
            print(f"  └{'─' * 50}")
            for k, v in skipped_this_page.items(): skipped_count[k] = skipped_count.get(k, 0) + v
            page_num += 1
        
        browser.close()
    
    print("\n" + "=" * 70)
    print(f"  {ICON_STATS} RÉSUMÉ DU SCAN")
    print("=" * 70)
    scan_status = "TERMINÉ" if consecutive_errors < MAX_CONSECUTIVE_ERRORS else "INTERROMPU (erreurs)"
    if SCAN_ALL:
        print(f"  {ICON_SUCCESS} SCAN {scan_status}")
        print(f"  {ICON_NEW} Nouveaux appels d'offres: {tenders_extracted_count[0]}")
        print(f"  {ICON_PAGE} Pages scannées: {last_successful_page}/{total_pages}")
    else: print(f"  {ICON_NEW} Appels d'offres extraits: {tenders_extracted_count[0]}")
    total_skipped = sum(skipped_count.values())
    if total_skipped > 0:
        print(f"  {ICON_SKIP} Offres ignorées: {total_skipped}")
        for status, count in sorted(skipped_count.items(), key=lambda x: x[1], reverse=True):
            status_label = {"not_crystalwater_related": "Non pertinent", "already_in_db_by_ref": "Déjà en base (ref)", "already_in_db_by_key": "Déjà en base (clé)", "already_in_db_by_obj": "Déjà en base (objet)", "deadline_passed": "Date limite passée", "title_too_short": "Titre trop court", "error": "Erreur"}.get(status, status)
            print(f"    - {status_label}: {count}")
    if extraction_times:
        avg_time = sum(t["total_time"] for t in extraction_times) / len(extraction_times)
        print(f"  {ICON_CLOCK} Temps moyen par offre: {avg_time:.1f}s")
    print(f"  {ICON_CLOCK} Fin: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 70 + "\n")


# ═══════════════ PUBLIC API ═══════════════

def load_tenders(status_filter=None):
    params = {"order": "relevance_score.desc", "limit": "10000"}
    if status_filter: params["status"] = f"eq.{status_filter}"
    return _sb_get_tenders_2(params)

def load_suppliers(status_filter=None):
    params = {"order": "reference", "limit": "10000"}
    if status_filter: params["status"] = f"eq.{status_filter}"
    return _sb_get("suppliers", params)

def load_sectors(status_filter=None):
    params = {"order": "reference", "limit": "10000"}
    if status_filter: params["status"] = f"eq.{status_filter}"
    return _sb_get("sectors", params)

def update_tender_status(i, s): return _sb_patch_tenders_2(i, {"status": s})
def update_supplier_status(i, s): return _sb_patch("suppliers", i, {"status": s, "updated_at": datetime.now(timezone.utc).isoformat()})
def update_sector_status(i, s): return _sb_patch("sectors", i, {"status": s, "updated_at": datetime.now(timezone.utc).isoformat()})

def generate_email(tender, template_key="information_request", language="french", 
                  sender_name="CrystalWater Team", sender_title="Directeur Commercial",
                  sender_email="contact@crystalwater.ma", sender_phone="+212 6 10 10 74 75"):
    body = f"Madame, Monsieur,\n\n{sender_name} - {sender_title}\n"
    body += f"CrystalWater (crystalwater.ma) - Expert en traitement d'eau.\n\n"
    body += f"AO: {tender.get('objet','')}\n"
    body += f"Reference: {tender.get('reference','')}\n"
    body += f"Deadline: {tender.get('date_limite_remise_plis','')}\n"
    if tender.get("dce_zip_url"): body += f"\nDCE: {tender['dce_zip_url']}\n"
    body += f"\nEmail: {sender_email}  Tel: {sender_phone}"
    return {
        "subject": f"CrystalWater - {tender.get('objet','')[:80]}", 
        "body": body, 
        "to": tender.get("contact_email", ""), 
        "from": sender_email
    }

def send_email_via_resend(email_data):
    RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
    if not RESEND_API_KEY: return {"success": False}
    try:
        r = requests.post("https://api.resend.com/emails", 
                         headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"}, 
                         json={"from": email_data.get("from", SENDER_EMAIL), "to": [email_data.get("to", "")], 
                               "subject": email_data.get("subject", ""), "text": email_data.get("body", "")}, timeout=15)
        return {"success": r.status_code in (200, 201)}
    except: return {"success": False}


# ═══════════════ KEYWORDS ═══════════════
KEYWORDS_TABLE = os.getenv("KEYWORDS_TABLE", "tender_keywords")

def _sb_get_keywords(params: dict = None) -> List[dict]:
    if not SUPABASE_URL or not SUPABASE_KEY: return []
    try:
        r = requests.get(f"{SUPABASE_URL}/rest/v1/{KEYWORDS_TABLE}", headers=_sb_headers(), params=params or {}, timeout=15)
        r.raise_for_status(); return r.json() or []
    except: return []

def _sb_add_keyword(keyword_data: dict) -> Optional[dict]:
    if not SUPABASE_URL or not SUPABASE_KEY: return None
    try:
        r = requests.post(f"{SUPABASE_URL}/rest/v1/{KEYWORDS_TABLE}", headers=_sb_headers(), json=keyword_data, timeout=15)
        if r.status_code in (200, 201): return r.json()[0] if r.json() else keyword_data
        return None
    except: return None

def _sb_delete_keyword(keyword_id: int) -> bool:
    if not SUPABASE_URL or not SUPABASE_KEY: return False
    try:
        r = requests.delete(f"{SUPABASE_URL}/rest/v1/{KEYWORDS_TABLE}?id=eq.{keyword_id}", headers=_sb_headers(), timeout=15)
        return r.status_code in (200, 204)
    except: return False

def _sb_update_keyword(keyword_id: int, data: dict) -> bool:
    if not SUPABASE_URL or not SUPABASE_KEY: return False
    try:
        r = requests.patch(f"{SUPABASE_URL}/rest/v1/{KEYWORDS_TABLE}?id=eq.{keyword_id}", headers=_sb_headers(), json=data, timeout=15)
        return r.status_code in (200, 204)
    except: return False

def get_active_keywords() -> List[str]:
    keywords_data = _sb_get_keywords({"is_active": "eq.true", "order": "keyword.asc"})
    return [k["keyword"].lower().strip() for k in keywords_data if k.get("keyword")]

def filter_tenders_by_keywords(tenders: List[dict], keywords: List[str], match_all: bool = False) -> List[dict]:
    if not keywords: return tenders
    filtered = []
    for tender in tenders:
        text_to_search = " ".join([str(tender.get(k, "")) for k in ["objet", "acheteur_public", "lieu_execution", "categorie", "procedure", "reference"]]).lower()
        for char in "éèêëàâäùûüôöîïç":
            text_to_search = text_to_search.replace(char, {'é':'e','è':'e','ê':'e','ë':'e','à':'a','â':'a','ä':'a','ù':'u','û':'u','ü':'u','ô':'o','ö':'o','î':'i','ï':'i','ç':'c'}[char])
        matches = [kw for kw in keywords if kw.lower().replace('é','e').replace('è','e').replace('ê','e').replace('à','a').replace('â','a').replace('ç','c') in text_to_search]
        if match_all:
            if len(matches) == len(keywords): filtered.append(tender)
        elif matches: filtered.append(tender)
    return filtered


# ═══════════════ STUB FUNCTIONS ═══════════════

def scrape_kenya(): return []
def scrape_ghana(): return []
def scrape_rwanda(): return []
def scrape_uganda(): return []
def scrape_cotedivoire(): return []
def scrape_senegal(): return []
def scrape_tunisia(): return []
def scrape_southafrica(): return []
def scrape_nigeria(): return []
def scrape_suppliers(): return []
def build_sector_intelligence(): return []


if __name__ == "__main__":
    _init_docling(); _check_fitz(); _init_paddleocr_fallback()
    if not _docling_available: sys.exit(1)
    print("\n" + "=" * 70)
    print(f"  {ICON_WATER} CrystalWater - Tender Scanner")
    print("=" * 70)
    if SCAN_ALL: print(f"  Mode: SCAN COMPLET - Tous les appels d'offres")
    else: print(f"  Mode: TEST - Max {MAX_TEST_TENDERS}")
    print(f"  {ICON_FILTER} Filtres actifs: Contexte désinfection, Nettoyage, IT, Électricité")
    print("=" * 70)
    choice = input(f"\n  {ICON_SEARCH} Appuyez sur Entrée pour lancer le scan: ").strip() or "1"
    if choice == "1": run_tender_scan()
    else: print(f"  {ICON_STOP} Fin du programme.")