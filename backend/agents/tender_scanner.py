"""
tender_scanner.py — Africa Tenders Intelligence Module (v10.0 - FINAL)
=======================================================================
CrystalWater — Traitement d'eau & Refroidissement industriel
https://crystalwater.ma/

FULL PIPELINE INTÉGRÉ:
1. Scan des 3 derniers mois (backfill) + Temps réel
2. Téléchargement automatique des DCE (ZIP)
3. Extraction automatique via les modules spécialisés:
   - agents/document/00_avis_Extraction.py → Estimation, Caution, Visite
   - agents/document/00_rc_Extraction.py → 18 champs RC
   - agents/document/BP_Extractor.py → Bordereau des Prix
4. Stockage dans Supabase
5. Affichage détaillé dans le terminal
"""

import os
import re
import sys
import json
import uuid
import time
import logging
import warnings
import zipfile
import io
import tempfile
import threading
import signal
import importlib.util
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any, Tuple, Set
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

warnings.filterwarnings("ignore")
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

load_dotenv()

# ─── EMOJIS ──────────────────────────────────────────────
ICON_WATER = "💧"; ICON_NEW = "🆕"; ICON_DOWNLOAD = "📥"
ICON_SUCCESS = "✅"; ICON_ERROR = "❌"; ICON_WARN = "⚠️"
ICON_PAGE = "📄"; ICON_DB = "🗄️"; ICON_CLOCK = "🕐"
ICON_STATS = "📊"; ICON_ZIP = "📦"; ICON_REALTIME = "🔄"
ICON_POLL = "👁️"; ICON_BACKFILL = "📅"; ICON_EXTRACT = "🤖"
ICON_STOP = "🚫"; ICON_REF = "🔖"; ICON_SCORE = "⭐"
ICON_PROGRESS = "📈"; ICON_SKIP = "⏭️"; ICON_DEADLINE = "⏰"
ICON_AVIS = "📢"; ICON_RC = "📜"; ICON_BP = "📋"

# ─── CONFIG ──────────────────────────────────────────────
BACKFILL_MONTHS = 3
POLL_INTERVAL = 300
MAX_PAGES_PER_POLL = 3

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "") or os.getenv("SUPABASE_KEY", "")
BASE_URL = "https://www.marchespublics.gov.ma"
SEARCH_URL = f"{BASE_URL}/index.php?page=entreprise.EntrepriseAdvancedSearch&AllCons&EnCours&domaineActivite=1.13"
TENDERS_TABLE = os.getenv("TENDERS_TABLE", "tenders_3")

CRYSTAL_FORM_DATA = {
    "nom": "Crystal", "prenom": "Water",
    "email": "marketing@crystalwater.ma",
    "raisonSocial": "CrystalWater", "address": "Adresse CrystalWater"
}

# ─── LOGGER ──────────────────────────────────────────────
logger = logging.getLogger("tender_scanner")
logger.setLevel(logging.INFO)
if not logger.handlers:
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter('%(asctime)s | %(message)s', datefmt='%H:%M:%S'))
    logger.addHandler(ch)
    if not os.path.exists('logs'): os.makedirs('logs')
    fh = logging.FileHandler(f'logs/scanner_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log', encoding='utf-8')
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(fh)

# ─── STATS ───────────────────────────────────────────────
scan_stats = {
    "pages_scanned": 0, "total_pages": 0, "rows_checked": 0,
    "new_tenders": 0, "dce_downloaded": 0, "dce_failed": 0,
    "skipped_already_in_db": 0, "skipped_not_related": 0,
    "skipped_deadline_passed": 0, "start_time": None, "extractions_total": 0,
}

# ─── KEYWORDS ────────────────────────────────────────────
STRONG_KEYWORDS = [
    "station de traitement", "station d'epuration", "step", "eau potable", "aep",
    "adduction d'eau", "potabilisation", "assainissement", "eaux usees", "eaux pluviales",
    "reservoir d'eau", "chateau d'eau", "dessalement", "osmose inverse",
    "traitement des eaux", "surpression", "forage d'eau", "captage", "puits",
    "vannes", "clapets", "debitmetre", "pompe immergee",
    "tour de refroidissement", "refroidissement industriel",
    "chloration", "desinfection", "filtration", "lagunage",
    "station de pompage", "irrigation"
]

MEDIUM_KEYWORDS = [
    "travaux", "reseaux", "canalisation", "genie civil",
    "fourniture", "installation", "rehabilitation", "extension",
    "construction", "renouvellement", "renforcement"
]

STRICT_EXCLUSIONS = [
    "nettoyage des locaux", "entretien des locaux", "informatique", "logiciel", "site web",
    "photovoltaique", "solaire", "dechets solides", "gardiennage", "restauration", "cantine",
    "fournitures de bureau", "mobilier", "climatiseurs", "vehicule", "voiture", "ambulance"
]

# ═══════════════ SUPABASE HELPERS ═══════════════
def _sb_headers():
    return {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json", "Prefer": "return=representation"}

def _sb_get(table, params=None):
    if not SUPABASE_URL: return []
    try:
        r = requests.get(f"{SUPABASE_URL}/rest/v1/{table}", headers=_sb_headers(), params=params or {}, timeout=15)
        r.raise_for_status(); return r.json() or []
    except: return []

def _sb_upsert_tenders(rows):
    if not SUPABASE_URL or not rows: return False
    url = f"{SUPABASE_URL}/rest/v1/{TENDERS_TABLE}"
    headers = {**_sb_headers(), "Prefer": "resolution=merge-duplicates,return=minimal"}
    success = 0
    for i in range(0, len(rows), 50):
        try:
            r = requests.post(url, headers=headers, json=rows[i:i+50], params={"on_conflict": "reference"}, timeout=30)
            if r.status_code in (200, 201, 204): success += len(rows[i:i+50])
        except: pass
    if success > 0: logger.info(f"     {ICON_DB} {success} offres sauvegardées")
    return success > 0

def _sb_patch_tender(reference, data):
    if not SUPABASE_URL: return False
    try:
        headers = _sb_headers(); headers["Prefer"] = "return=minimal"
        r = requests.patch(f"{SUPABASE_URL}/rest/v1/{TENDERS_TABLE}?reference=eq.{reference}", headers=headers, json=data, timeout=60)
        return r.status_code in (200, 204)
    except: return False

def _sb_get_existing_refs():
    refs = set()
    try:
        tenders = _sb_get(TENDERS_TABLE, {"select": "reference", "limit": "10000"})
        for t in tenders:
            if t.get("reference"): refs.add(t["reference"])
        logger.info(f"  {ICON_DB} {len(refs)} références déjà en base")
    except: pass
    return refs

def _sb_upload_zip(zip_content, tender_ref):
    if not SUPABASE_URL or len(zip_content) > 50*1024*1024: return None
    try:
        safe_ref = tender_ref.replace("/", "_")
        url = f"{SUPABASE_URL}/storage/v1/object/zip_files_tenders/{safe_ref}.zip"
        headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/zip", "x-upsert": "true"}
        r = requests.post(url, headers=headers, data=zip_content, timeout=120)
        if r.status_code in (200, 201): return f"{SUPABASE_URL}/storage/v1/object/public/zip_files_tenders/{safe_ref}.zip"
        return None
    except: return None

# ═══════════════ PARSING ═══════════════
def parse_deadline(s):
    if not s: return None
    try:
        for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y"):
            try: return datetime.strptime(re.sub(r'[^\d/:\s]', '', s).strip()[:16], fmt)
            except: continue
    except: pass
    return None

def is_crystalwater_related(title, description, acheteur=""):
    full_text = f"{title} {description} {acheteur}".lower()
    for a,b in [('é','e'),('è','e'),('ê','e'),('à','a'),('â','a'),('ù','u'),('û','u'),('ô','o'),('î','i'),('ç','c')]:
        full_text = full_text.replace(a,b)
    for excl in STRICT_EXCLUSIONS:
        if excl in full_text: return False
    return any(kw in full_text for kw in STRONG_KEYWORDS)

def compute_score(title, description, deadline, acheteur=""):
    full_text = f"{title} {description} {acheteur}".lower()
    for a,b in [('é','e'),('è','e'),('ê','e'),('à','a'),('â','a'),('ù','u'),('û','u'),('ô','o'),('î','i'),('ç','c')]:
        full_text = full_text.replace(a,b)
    strong_hits = [kw for kw in STRONG_KEYWORDS if kw in full_text]
    if not strong_hits: return 0
    medium_hits = [kw for kw in MEDIUM_KEYWORDS if kw in full_text]
    base = len(strong_hits)*10 + len(medium_hits)*3
    dl_date = parse_deadline(deadline); dl_score = 5
    if dl_date:
        days = (dl_date - datetime.now()).days
        if days < 0: dl_score = -10
        elif days <= 7: dl_score = 3
        elif days <= 14: dl_score = 6
        elif days <= 30: dl_score = 9
        else: dl_score = 12
    clients = ["onee","onep","onas","regie autonome","amendis","commune","province"]
    client_bonus = 8 if any(c in full_text for c in clients) else 3
    return max(0, min(100, base + dl_score + client_bonus))

# ═══════════════ ROW EXTRACTION ═══════════════
def _extract_row_data(row, page_url, existing_refs):
    try:
        ref_input = row.select_one("input[name*='refCons']")
        reference = ref_input.get("value","") if ref_input else ""
        ref_span = row.select_one("span.ref"); ref_visible = ref_span.get_text(strip=True) if ref_span else ""
        objet_text = ""; objet_div = row.select_one("div[id*='panelBlocObjet']")
        if objet_div: objet_text = re.sub(r'^Objet\s*:\s*', '', objet_div.get_text(strip=True)).strip()
        acheteur = ""; acheteur_div = row.select_one("div[id*='panelBlocDenomination']")
        if acheteur_div: acheteur = re.sub(r'^Acheteur\s+public\s*:\s*', '', acheteur_div.get_text(strip=True)).strip()
        categorie = ""; cat_div = row.select_one("div[id*='panelBlocCategorie']")
        if cat_div: categorie = cat_div.get_text(strip=True)
        date_pub = ""; td_col90 = row.select_one("td.col-90")
        if td_col90:
            for d in td_col90.find_all("div"):
                text = d.get_text(strip=True)
                if re.match(r'\d{2}/\d{2}/\d{4}', text): date_pub = text; break
        deadline = ""; deadline_parsed = None; dl_div = row.select_one("div.cloture-line")
        if dl_div:
            deadline = dl_div.get_text(separator=' ', strip=True)
            parsed_dl = parse_deadline(deadline)
            if parsed_dl: deadline_parsed = parsed_dl.isoformat()
        if parsed_dl and parsed_dl < datetime.now(): return None, "deadline_passed"
        reponse_elec = None
        if row.select_one("img[src*='reponse-elec-oblig']"): reponse_elec = True
        elif row.select_one("img[src*='reponse-elec-non']"): reponse_elec = False
        procedure = ""; proc_div = row.select_one("div[id*='type_procedure']")
        if proc_div: procedure = proc_div.get_text(strip=True)
        lieu_exec = ""; lieu_div = row.select_one("div[id*='panelBlocLieuxExec']")
        if lieu_div: lieu_exec = re.sub(r'\s+', ' ', lieu_div.get_text(strip=True)).strip()
        detail_url = ""; actions_td = row.select_one("td.actions")
        if actions_td:
            link = actions_td.select_one("a[href*='DetailConsultation']")
            if link:
                href = link.get("href","")
                detail_url = f"{BASE_URL}/{href}" if href.startswith("?") else urljoin(BASE_URL, href)
        title = objet_text or f"{ref_visible or reference} - {categorie}"
        if len(title) < 10: return None, "title_too_short"
        if not is_crystalwater_related(title, f"{categorie} {procedure} {lieu_exec}", acheteur): return None, "not_related"
        final_ref = ref_visible or reference
        if final_ref and final_ref in existing_refs: return None, "already_in_db"
        date_pub_parsed = None
        if date_pub:
            try:
                for fmt in ("%d/%m/%Y","%d-%m-%Y","%Y-%m-%d"):
                    try: date_pub_parsed = datetime.strptime(date_pub.strip()[:10], fmt).date().isoformat(); break
                    except: continue
            except: pass
        score = compute_score(objet_text or "", f"{categorie} {procedure} {lieu_exec}", deadline, acheteur)
        return {"reference": final_ref or str(uuid.uuid4()), "procedure": procedure[:100] if procedure else None,
                "categorie": categorie[:200] if categorie else None, "date_publication": date_pub_parsed,
                "objet": objet_text[:500] if objet_text else None, "acheteur_public": acheteur[:300] if acheteur else None,
                "lieu_execution": lieu_exec[:300] if lieu_exec else None,
                "date_limite_remise_plis": deadline_parsed, "reponse_electronique_obligatoire": reponse_elec,
                "source_url": detail_url or page_url, "dce_zip_url": None,
                "status": "new", "qualification_status": "unseen", "seen": False, "relevance_score": score}, "success"
    except Exception as e:
        logger.error(f"  {ICON_ERROR} Extract error: {e}"); return None, "error"

# ═══════════════ DCE DOWNLOAD ═══════════════
def download_dce(page, detail_url, tender_ref):
    start = time.time()
    try:
        page.goto(detail_url, wait_until="domcontentloaded", timeout=30000); page.wait_for_timeout(5000)
        clicked = False
        for sel in ["a:has-text('Dossier de Consultation')","a:has-text('Telecharger le DCE')","a:has-text('Telecharger')","a[href*='TelechargerDCE']"]:
            try:
                for el in page.query_selector_all(sel):
                    if el.is_visible(): el.click(); clicked = True; break
                if clicked: break
            except: continue
        if not clicked: return None
        page.wait_for_timeout(5000)
        for sel, val in [("#ctl0_CONTENU_PAGE_EntrepriseFormulaireDemande_nom",CRYSTAL_FORM_DATA["nom"]),
                          ("#ctl0_CONTENU_PAGE_EntrepriseFormulaireDemande_prenom",CRYSTAL_FORM_DATA["prenom"]),
                          ("#ctl0_CONTENU_PAGE_EntrepriseFormulaireDemande_email",CRYSTAL_FORM_DATA["email"])]:
            try:
                field = page.query_selector(sel)
                if field and field.is_visible(): field.fill(val)
            except: pass
        try:
            cb = page.query_selector("#ctl0_CONTENU_PAGE_EntrepriseFormulaireDemande_accepterConditions")
            if cb and not cb.is_checked(): cb.click()
        except: pass
        page.wait_for_timeout(1000)
        validate_btn = page.query_selector("#ctl0_CONTENU_PAGE_validateButton")
        if not validate_btn: return None
        validate_btn.click(); page.wait_for_timeout(5000)
        download_btn = None
        for sel in ["#ctl0_CONTENU_PAGE_EntrepriseDownloadDce_completeDownload","a.bouton-telecharger-long230"]:
            try:
                btn = page.query_selector(sel)
                if btn and btn.is_visible(): download_btn = btn; break
            except: continue
        if not download_btn: return None
        with page.expect_download(timeout=300000) as download_info: download_btn.click()
        download = download_info.value
        try: zip_path = download.path()
        except: return None
        if not zip_path: return None
        with open(zip_path, 'rb') as f: zip_content = f.read()
        if not zip_content or len(zip_content) < 100: return None
        supabase_url = _sb_upload_zip(zip_content, tender_ref)
        download_time = time.time() - start
        if supabase_url: threading.Thread(target=run_full_extraction, args=(tender_ref, zip_content), daemon=True).start()
        return {"dce_zip_url": supabase_url, "download_time": download_time}
    except Exception as e:
        logger.error(f"     {ICON_ERROR} DCE error: {e}"); return None

# ═══════════════ FULL EXTRACTION ═══════════════
def run_full_extraction(tender_ref, zip_content):
    logger.info(f"\n  {'─'*60}")
    logger.info(f"  {ICON_EXTRACT} EXTRACTION COMPLÈTE: {tender_ref}")
    logger.info(f"  {'─'*60}")
    scan_stats["extractions_total"] += 1
    
    tmp_zip_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp:
            tmp.write(zip_content); tmp_zip_path = tmp.name
        
        _extract_avis(tender_ref, tmp_zip_path)
        _extract_rc(tender_ref, tmp_zip_path)
        _extract_bp(tender_ref, tmp_zip_path)
    except Exception as e:
        logger.error(f"  {ICON_ERROR} Extraction error: {e}")
        import traceback; traceback.print_exc()
    finally:
        if tmp_zip_path and os.path.exists(tmp_zip_path):
            try: os.unlink(tmp_zip_path)
            except: pass
    logger.info(f"  {'─'*60}")

# ═══════════════ MODULE LOADER ═══════════════
def _load_module(module_name, relative_path):
    current_dir = Path(__file__).resolve().parent
    module_path = current_dir / relative_path
    if not module_path.exists():
        logger.warning(f"     Module introuvable: {module_path}")
        return None
    try:
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except Exception as e:
        logger.error(f"     Erreur chargement module {module_name}: {e}")
        return None

def _extract_avis(tender_ref, zip_path):
    logger.info(f"  {ICON_AVIS} Extraction Avis...")
    avis_module = _load_module('avis_extraction', 'document/00_avis_Extraction.py')
    if avis_module is None:
        _extract_avis_fallback(tender_ref, zip_path)
        return
    try:
        with open(zip_path, 'rb') as f: zip_bytes = f.read()
        files = avis_module.extract_files_from_zip(zip_bytes)
        if not files:
            logger.info(f"     {ICON_WARN} Aucun fichier Avis trouvé")
            _extract_avis_fallback(tender_ref, zip_path)
            return
        logger.info(f"     {len(files)} fichier(s) Avis trouvé(s)")
        all_fields = {}
        for file_data in files:
            try:
                result = avis_module.process_avis_file(file_data["filename"], file_data["file_bytes"])
                if result.get("success") and result.get("avis_fields"):
                    fields = result["avis_fields"]
                    if fields.get("Estimation (DHS TTC)"): all_fields["avis_estimation_ttc"] = fields["Estimation (DHS TTC)"]
                    if fields.get("Caution Provisoire"): all_fields["avis_caution_dhs"] = fields["Caution Provisoire"]
                    if fields.get("Date et Heure Visite des Lieux"): all_fields["avis_visite_lieux"] = fields["Date et Heure Visite des Lieux"]
            except Exception as e:
                logger.debug(f"     Avis file error: {e}")
        if all_fields:
            _sb_patch_tender(tender_ref, all_fields)
            logger.info(f"     {ICON_SUCCESS} Avis: {len(all_fields)} champs extraits")
            for k,v in all_fields.items(): logger.info(f"        {k}: {v}")
        else:
            logger.info(f"     {ICON_WARN} Aucune info Avis, tentative fallback...")
            _extract_avis_fallback(tender_ref, zip_path)
    except Exception as e:
        logger.error(f"     {ICON_ERROR} Avis error: {e}")
        _extract_avis_fallback(tender_ref, zip_path)

def _extract_avis_fallback(tender_ref, zip_path):
    try:
        with zipfile.ZipFile(zip_path) as zf:
            all_text = ""
            for fn in zf.namelist():
                if fn.endswith('/'): continue
                try:
                    content = zf.read(fn)
                    if fn.lower().endswith('.pdf'):
                        try:
                            import fitz; doc = fitz.open(stream=content, filetype="pdf")
                            all_text += "\n".join([p.get_text() for p in doc]); doc.close()
                        except: all_text += content.decode('latin-1', errors='ignore')
                    elif fn.lower().endswith(('.docx','.doc')):
                        try:
                            from docx import Document
                            doc = Document(io.BytesIO(content))
                            all_text += "\n".join([p.text for p in doc.paragraphs])
                        except: all_text += content.decode('latin-1', errors='ignore')
                    else:
                        try: all_text += content.decode('utf-8', errors='ignore') + "\n"
                        except: pass
                except: pass
        if not all_text.strip():
            logger.info(f"     {ICON_WARN} Aucun texte extrait du ZIP")
            return
        logger.info(f"     📄 Texte fallback: {len(all_text)} caractères")
        result = {}
        # Estimation
        for pat in [r"estimation[\s\w]{0,60}?:?\s*\(?([\d]{1,3}(?:[.\s]\d{3})*(?:,\d{2})?)\)?\s*(?:DH|DHS)",
                     r"montant\s+(?:total|estim[ée])[\s\w]{0,40}?:?\s*([\d]{1,3}(?:[.\s]\d{3})*(?:,\d{2})?)"]:
            m = re.search(pat, all_text, re.IGNORECASE)
            if m:
                try:
                    v = float(m.group(1).replace(' ','').replace(',','.'))
                    if v > 100: result["avis_estimation_ttc"] = f"{v:,.0f} DHS".replace(',',' '); break
                except: pass
        # Caution
        for pat in [r"caution(?:nement)?\s+provisoire[\s\w]{0,40}?:?\s*\(?([\d]{1,3}(?:[.\s]\d{3})*(?:,\d{2})?)\)?"]:
            m = re.search(pat, all_text, re.IGNORECASE)
            if m:
                try:
                    v = float(m.group(1).replace(' ','').replace(',','.'))
                    if v > 0:
                        if '%' in m.group(0): result["avis_caution_dhs"] = f"{v}%"
                        else: result["avis_caution_dhs"] = f"{v:,.0f} DHS".replace(',',' ')
                    break
                except: pass
        # Visite
        m = re.search(r'[Vv]isite\s*(?:des|de)\s*lieux.*?(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})', all_text, re.DOTALL)
        if m: result["avis_visite_lieux"] = m.group(1)
        if re.search(r"tenu[e]?\s+(de|d')\s+(faire|effectuer)\s+une\s+visite", all_text, re.IGNORECASE):
            result["visite_lieux_obligatoire"] = True
        if result:
            _sb_patch_tender(tender_ref, result)
            logger.info(f"     {ICON_SUCCESS} Avis fallback: {len(result)} champs")
            for k,v in result.items(): logger.info(f"        {k}: {v}")
        else:
            logger.info(f"     {ICON_WARN} Aucune info Avis trouvée (fallback)")
    except Exception as e:
        logger.error(f"     Avis fallback error: {e}")

def _extract_rc(tender_ref, zip_path):
    logger.info(f"  {ICON_RC} Extraction RC...")
    rc_module = _load_module('rc_extraction', 'document/00_rc_Extraction.py')
    if rc_module is None: return
    try:
        with open(zip_path, 'rb') as f: zip_bytes = f.read()
        rc_files = []
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            for fn in zf.namelist():
                if fn.endswith('/'): continue
                if rc_module.is_rc_file(fn) and rc_module.is_supported_format(fn):
                    rc_files.append({"filename": Path(fn).name, "file_bytes": zf.read(fn)})
        if not rc_files:
            logger.info(f"     {ICON_WARN} Aucun fichier RC trouvé dans le ZIP")
            return
        logger.info(f"     {len(rc_files)} fichier(s) RC trouvé(s)")
        for rc in rc_files: logger.info(f"        📄 {rc['filename']}")
        all_results = []
        for rc in rc_files:
            try:
                result = rc_module.process_rc_file(rc["filename"], rc["file_bytes"])
                if result and "error" not in result: all_results.append(result)
            except Exception as e: logger.debug(f"     RC file error: {e}")
        if all_results:
            try:
                rc_module.save_rc_extraction_to_supabase(tender_ref, all_results)
                merged = {}
                for r in all_results:
                    if "error" in r: continue
                    for k,v in r.items():
                        if k not in ['filename','text_length','extraction_diag','acheteur','method','is_scanned','total_pages']:
                            if v and not merged.get(k): merged[k] = v
                logger.info(f"     {ICON_SUCCESS} RC: {len(merged)} champs extraits")
                for k in ['attestations_demandees','nombre_references','classe_qualification','chiffre_affaires','caution_provisoire']:
                    if k in merged: logger.info(f"        {k}: {merged[k]}")
            except Exception as e: logger.error(f"     RC save error: {e}")
        else:
            logger.info(f"     {ICON_WARN} Aucune info RC extraite")
    except Exception as e:
        logger.error(f"     {ICON_ERROR} RC error: {e}")

def _extract_bp(tender_ref, zip_path):
    logger.info(f"  {ICON_BP} Extraction BP...")
    bp_module = _load_module('bp_extraction', 'document/BP_Extractor.py')
    if bp_module is None: return
    try:
        with open(zip_path, 'rb') as f: zip_bytes = f.read()
        bp_files = bp_module.extract_files_from_zip(zip_bytes)
        if not bp_files:
            logger.info(f"     {ICON_WARN} Aucun fichier BP trouvé dans le ZIP")
            return
        logger.info(f"     {len(bp_files)} fichier(s) BP trouvé(s)")
        for bp in bp_files: logger.info(f"        📊 {bp['filename']}")
        best_result = None; max_items = 0
        for file_data in bp_files:
            try:
                result = bp_module.process_bp_file(file_data["filename"], file_data["file_bytes"])
                if result.get("success") and result.get("items_count",0) > max_items:
                    max_items = result["items_count"]; best_result = result
            except Exception as e: logger.debug(f"     BP file error: {e}")
        if best_result:
            bp_result = best_result["bp_result"]
            try:
                bp_module.save_bp_to_supabase(tender_ref, bp_result, best_result["filename"])
                doc_level = bp_result.get("document_level",{})
                total_ht = doc_level.get("Total_HT")
                logger.info(f"     {ICON_SUCCESS} BP: {max_items} items extraits")
                if total_ht: logger.info(f"        Total HT: {total_ht:,.2f} DHS")
            except Exception as e: logger.error(f"     BP save error: {e}")
        else:
            logger.info(f"     {ICON_WARN} Aucun item BP extrait")
    except Exception as e:
        logger.error(f"     {ICON_ERROR} BP error: {e}")

# ═══════════════ NAVIGATION ═══════════════
def navigate_to_results(page):
    try:
        page.goto(SEARCH_URL, wait_until="networkidle", timeout=60000); page.wait_for_timeout(5000)
        try: page.click("#ctl0_CONTENU_PAGE_AdvancedSearch_lancerRecherche", timeout=15000)
        except: page.evaluate("document.querySelector('form').submit()")
        page.wait_for_timeout(5000)
        try: page.wait_for_selector("tr:has(td.col-450)", timeout=45000); return True
        except: return False
    except: return False

def navigate_to_page(page, page_num):
    if page_num == 1: return True
    try:
        page.fill("#ctl0_CONTENU_PAGE_resultSearch_numPageTop", str(page_num)); page.wait_for_timeout(1000)
        page.press("#ctl0_CONTENU_PAGE_resultSearch_numPageTop", "Enter"); page.wait_for_timeout(8000)
        try: page.wait_for_selector("tr:has(td.col-450)", timeout=30000); return True
        except: return False
    except: return False

# ═══════════════ DISPLAY ═══════════════
def print_tender_found(tender, index):
    ref = tender.get("reference","N/A"); objet = (tender.get("objet","") or "")[:80]
    score = tender.get("relevance_score",0); acheteur = (tender.get("acheteur_public","") or "")[:50]
    deadline = tender.get("date_limite_remise_plis",""); dl_display = "N/A"
    if deadline:
        try:
            dl_date = datetime.fromisoformat(deadline.replace('Z','+00:00'))
            days_left = (dl_date - datetime.now()).days
            if days_left < 0: dl_display = f"{dl_date.strftime('%d/%m/%Y')} (EXPIRÉ)"
            elif days_left == 0: dl_display = f"{dl_date.strftime('%d/%m/%Y')} (AUJOURD'HUI!)"
            elif days_left <= 7: dl_display = f"{dl_date.strftime('%d/%m/%Y')} ({days_left}j URGENT)"
            else: dl_display = f"{dl_date.strftime('%d/%m/%Y')} ({days_left}j)"
        except: dl_display = deadline[:10]
    stars = "⭐"*min(5,score//20)
    logger.info(f"\n  ╔{'═'*66}╗")
    logger.info(f"  ║ {ICON_WATER} TENDER #{index:<4}  {ICON_SCORE} Score: {score}/100 {stars}")
    logger.info(f"  ╠{'═'*66}╣")
    logger.info(f"  ║ {ICON_REF} Réf: {ref}")
    logger.info(f"  ║ 📝 Objet: {objet}")
    logger.info(f"  ║ 🏢 Acheteur: {acheteur}")
    logger.info(f"  ║ {ICON_DEADLINE} Deadline: {dl_display}")
    logger.info(f"  ╚{'═'*66}╝")

def print_page_summary(page_num, total_pages, rows_on_page, new_found, skipped):
    logger.info(f"\n  ┌─ {ICON_PAGE} PAGE {page_num}/{total_pages} {'─'*40}")
    logger.info(f"  │  Lignes: {rows_on_page}  |  {ICON_NEW} Nouveaux: {new_found}")
    total_skipped = sum(skipped.values())
    if total_skipped > 0:
        logger.info(f"  │  {ICON_SKIP} Ignorés: {total_skipped}")
        for reason, count in sorted(skipped.items(), key=lambda x: x[1], reverse=True)[:3]:
            labels = {"already_in_db":f"{ICON_DB} Déjà en base","not_related":f"{ICON_STOP} Non lié","deadline_passed":f"{ICON_DEADLINE} Expiré"}
            logger.info(f"  │     {labels.get(reason,reason)}: {count}")
    logger.info(f"  └{'─'*56}")

def print_scan_summary():
    elapsed = (datetime.now() - scan_stats["start_time"]).total_seconds() if scan_stats["start_time"] else 0
    h,m,s = int(elapsed//3600), int((elapsed%3600)//60), int(elapsed%60)
    logger.info(f"\n{'='*70}")
    logger.info(f"  {ICON_STATS} RÉSUMÉ DU SCAN")
    logger.info(f"{'='*70}")
    logger.info(f"  {ICON_PAGE} Pages: {scan_stats['pages_scanned']}/{scan_stats['total_pages']}")
    logger.info(f"  {ICON_NEW} Nouveaux: {scan_stats['new_tenders']}")
    logger.info(f"  {ICON_ZIP} DCE: {scan_stats['dce_downloaded']}")
    logger.info(f"  {ICON_EXTRACT} Extractions: {scan_stats['extractions_total']}")
    logger.info(f"  {ICON_CLOCK} Durée: {h}h {m}m {s}s")
    logger.info(f"{'='*70}")

# ═══════════════ BACKFILL ═══════════════
def run_backfill():
    scan_stats["start_time"] = datetime.now()
    logger.info(f"\n{'='*70}\n  {ICON_BACKFILL} BACKFILL - {BACKFILL_MONTHS} DERNIERS MOIS\n  {ICON_CLOCK} Début: {scan_stats['start_time'].strftime('%Y-%m-%d %H:%M:%S')}\n{'='*70}")
    existing_refs = _sb_get_existing_refs()
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
        context = browser.new_context(viewport={"width":1366,"height":768}, accept_downloads=True)
        page = context.new_page()
        if not navigate_to_results(page): browser.close(); return
        total_pages = 200
        try:
            nb = page.query_selector("#ctl0_CONTENU_PAGE_resultSearch_nombrePageTop")
            if nb: total_pages = int(nb.inner_text().strip())
        except: pass
        scan_stats["total_pages"] = total_pages
        logger.info(f"  {ICON_PAGE} Pages à scanner: {total_pages}\n")
        cutoff_date = datetime.now() - timedelta(days=BACKFILL_MONTHS*30)
        for page_num in range(1, total_pages+1):
            if page_num > 1:
                if not navigate_to_page(page, page_num): continue
                time.sleep(1)
            rows = BeautifulSoup(page.content(), "html.parser").select("tr:has(td.col-450)")
            if not rows: continue
            scan_stats["pages_scanned"] += 1; scan_stats["rows_checked"] += len(rows)
            page_new = []; page_skipped = {"already_in_db":0,"not_related":0,"deadline_passed":0}
            for row in rows:
                result, status = _extract_row_data(row, page.url, existing_refs)
                if result is None:
                    if status in page_skipped: page_skipped[status] += 1
                    continue
                if result.get("date_publication"):
                    try:
                        if datetime.fromisoformat(result["date_publication"]) < cutoff_date: continue
                    except: pass
                page_new.append(result); existing_refs.add(result.get("reference",""))
            if page_num % 10 == 0 or page_new: print_page_summary(page_num, total_pages, len(rows), len(page_new), page_skipped)
            for tender in page_new:
                scan_stats["new_tenders"] += 1; print_tender_found(tender, scan_stats["new_tenders"])
                detail_url = tender.get("source_url","")
                if detail_url:
                    dce_page = context.new_page()
                    try:
                        dce_info = download_dce(dce_page, detail_url, tender["reference"])
                        if dce_info and dce_info.get("dce_zip_url"):
                            tender["dce_zip_url"] = dce_info["dce_zip_url"]; scan_stats["dce_downloaded"] += 1
                            logger.info(f"     {ICON_ZIP} DCE téléchargé ({dce_info.get('download_time',0):.1f}s)")
                        else: scan_stats["dce_failed"] += 1
                    finally: dce_page.close()
            if page_new: _sb_upsert_tenders(page_new)
            if page_num % 50 == 0:
                elapsed = (datetime.now() - scan_stats["start_time"]).total_seconds()
                logger.info(f"\n  {ICON_STATS} PROGRESSION: Page {page_num}/{total_pages} | {scan_stats['new_tenders']} nouveaux | {scan_stats['dce_downloaded']} DCE\n")
        browser.close()
    print_scan_summary()

# ═══════════════ REALTIME ═══════════════
class RealtimeScanner:
    def __init__(self):
        self.existing_refs = _sb_get_existing_refs(); self.running = True
        self.poll_count = 0; self.new_count = 0; self.dce_count = 0
        self.start_time = datetime.now()
        signal.signal(signal.SIGINT, self._handler); signal.signal(signal.SIGTERM, self._handler)
    def _handler(self, signum, frame): logger.info(f"\n  {ICON_STOP} Arrêt..."); self.running = False
    def run(self):
        logger.info(f"\n{'='*70}\n  {ICON_REALTIME} SURVEILLANCE TEMPS RÉEL\n  {ICON_POLL} Intervalle: {POLL_INTERVAL}s | {ICON_DB} {len(self.existing_refs)} en base\n{'='*70}")
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
            context = browser.new_context(viewport={"width":1366,"height":768}, accept_downloads=True)
            page = context.new_page()
            if not navigate_to_results(page): browser.close(); return
            while self.running:
                self.poll_count += 1; poll_start = datetime.now()
                logger.info(f"\n  {ICON_POLL} POLL #{self.poll_count} - {poll_start.strftime('%H:%M:%S')}")
                poll_new = 0
                try:
                    navigate_to_page(page, 1)
                    for pg in range(1, MAX_PAGES_PER_POLL+1):
                        if pg > 1:
                            if not navigate_to_page(page, pg): break
                            time.sleep(1)
                        rows = BeautifulSoup(page.content(), "html.parser").select("tr:has(td.col-450)")
                        page_new = []
                        for row in rows:
                            result, _ = _extract_row_data(row, page.url, self.existing_refs)
                            if result: page_new.append(result); self.existing_refs.add(result.get("reference",""))
                        if page_new:
                            logger.info(f"  {ICON_NEW} Page {pg}: {len(page_new)} NOUVEAU(X) !")
                            for tender in page_new:
                                poll_new += 1; self.new_count += 1; print_tender_found(tender, self.new_count)
                                detail_url = tender.get("source_url","")
                                if detail_url:
                                    dce_page = context.new_page()
                                    try:
                                        dce_info = download_dce(dce_page, detail_url, tender["reference"])
                                        if dce_info and dce_info.get("dce_zip_url"):
                                            tender["dce_zip_url"] = dce_info["dce_zip_url"]; self.dce_count += 1
                                            logger.info(f"     {ICON_ZIP} DCE téléchargé")
                                    finally: dce_page.close()
                            _sb_upsert_tenders(page_new)
                    elapsed = (datetime.now() - poll_start).total_seconds()
                    if poll_new == 0: logger.info(f"  {ICON_SUCCESS} Aucun nouveau ({elapsed:.1f}s)")
                    else: logger.info(f"  {ICON_NEW} {poll_new} nouveaux ({elapsed:.1f}s)")
                    if self.poll_count % 12 == 0: self.existing_refs = _sb_get_existing_refs()
                except Exception as e:
                    logger.error(f"  {ICON_ERROR} Erreur: {e}")
                    try: navigate_to_results(page)
                    except: pass
                if self.running:
                    wait = max(0, POLL_INTERVAL - (datetime.now() - poll_start).total_seconds())
                    logger.info(f"  {ICON_CLOCK} Prochain poll dans {int(wait)}s")
                    for _ in range(int(wait)):
                        if not self.running: break
                        time.sleep(1)
            browser.close()

# ═══════════════ PUBLIC API ═══════════════
def load_tenders(status_filter=None):
    params = {"order": "relevance_score.desc", "limit": "10000"}
    if status_filter: params["status"] = f"eq.{status_filter}"
    return _sb_get(TENDERS_TABLE, params)

def load_suppliers(status_filter=None):
    params = {"order": "reference", "limit": "10000"}
    if status_filter: params["status"] = f"eq.{status_filter}"
    return _sb_get("suppliers", params)

def load_sectors(status_filter=None):
    params = {"order": "reference", "limit": "10000"}
    if status_filter: params["status"] = f"eq.{status_filter}"
    return _sb_get("sectors", params)

def update_tender_status(i, s): return _sb_patch_tender(i, {"status": s})
def update_supplier_status(i, s):
    try:
        r = requests.patch(f"{SUPABASE_URL}/rest/v1/suppliers?reference=eq.{i}", headers=_sb_headers(), json={"status": s}, timeout=60)
        return r.status_code in (200,204)
    except: return False
def update_sector_status(i, s):
    try:
        r = requests.patch(f"{SUPABASE_URL}/rest/v1/sectors?reference=eq.{i}", headers=_sb_headers(), json={"status": s}, timeout=60)
        return r.status_code in (200,204)
    except: return False
def generate_email(tender, **kwargs):
    body = f"Madame, Monsieur,\n\n{kwargs.get('sender_name','CrystalWater Team')}\n"
    body += f"AO: {tender.get('objet','')}\nRef: {tender.get('reference','')}\n"
    return {"subject": f"CrystalWater - {tender.get('objet','')[:80]}", "body": body}
def send_email_via_resend(email_data):
    try:
        r = requests.post("https://api.resend.com/emails",
                         headers={"Authorization": f"Bearer {os.getenv('RESEND_API_KEY','')}", "Content-Type": "application/json"},
                         json=email_data, timeout=15)
        return {"success": r.status_code in (200,201)}
    except: return {"success": False}

# Stubs
def get_active_keywords(): return []
def _sb_get_keywords(params=None): return []
def _sb_add_keyword(data): return None
def _sb_delete_keyword(kid): return False
def _sb_update_keyword(kid, data): return False
def _sb_get_tenders_2(params=None): return _sb_get(TENDERS_TABLE, params)
def _sb_patch_tenders_2(ref, data): return _sb_patch_tender(ref, data)
def _sb_get_criteria(params=None): return []
def _sb_add_criteria(data): return None
def _sb_delete_criteria(cid): return False
def recalculate_all_scores(): return 0
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