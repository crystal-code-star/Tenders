#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
winner_to_csv.py — CrystalWater Winner Results Exporter
========================================================
Scans ONLY the 'Résultats définitifs' (award notices) and
saves results directly to a CSV file.

COMPLETELY STANDALONE - does not use Supabase at all.
"""

import os
import re
import sys
import time
import csv
import logging
import warnings
import zipfile
import io
from datetime import datetime
from typing import Optional, List, Dict, Any
from urllib.parse import urljoin
from pathlib import Path

# ===== CORRECTION ENCODAGE WINDOWS =====
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except:
        pass
    os.environ['PYTHONIOENCODING'] = 'utf-8'
# ========================================

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

warnings.filterwarnings("ignore")
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

load_dotenv()

# ─────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────
BASE_URL = "https://www.marchespublics.gov.ma"
CSV_FILENAME = "winner_results.csv"

# Groq Configuration (optional - for AI summaries)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
GROQ_ENABLED = bool(GROQ_API_KEY)

# ─────────────────────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────────────────────
logger = logging.getLogger("winner_csv")
logger.setLevel(logging.INFO)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_format = logging.Formatter('[%(levelname)s] %(message)s')
console_handler.setFormatter(console_format)
logger.addHandler(console_handler)

if not os.path.exists('logs'):
    os.makedirs('logs')
file_handler = logging.FileHandler(
    f'logs/winner_csv_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log',
    encoding='utf-8'
)
file_handler.setLevel(logging.DEBUG)
file_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_format)
logger.addHandler(file_handler)

# ─────────────────────────────────────────────────────────────
# CSV HELPER
# ─────────────────────────────────────────────────────────────

class WinnerCSV:
    """Simple CSV storage for winner results."""
    
    def __init__(self, filename: str = CSV_FILENAME):
        self.filename = filename
        self.headers = [
            'tender_reference',
            'buyer',
            'winner',
            'awarded_amount',
            'award_date',
            'object',
            'source_url',
            'summary',
            'scraped_at'
        ]
        self.existing_refs = set()
        self._load_existing()
    
    def _load_existing(self):
        """Load existing references from CSV to avoid duplicates."""
        if not os.path.exists(self.filename):
            return
        
        try:
            with open(self.filename, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    ref = row.get('tender_reference', '')
                    if ref:
                        self.existing_refs.add(ref)
            logger.info(f"  [CSV] Loaded {len(self.existing_refs)} existing winners")
        except Exception as e:
            logger.warning(f"  [CSV] Could not load existing: {e}")
    
    def exists(self, ref: str) -> bool:
        """Check if a reference already exists."""
        return ref in self.existing_refs
    
    def save(self, record: Dict[str, Any]):
        """Save a record to CSV."""
        # Check if exists
        ref = record.get('tender_reference', '')
        if ref in self.existing_refs:
            return False
        
        # Prepare row
        row = {
            'tender_reference': ref,
            'buyer': record.get('buyer', ''),
            'winner': record.get('winner', ''),
            'awarded_amount': record.get('awarded_amount', ''),
            'award_date': record.get('award_date', ''),
            'object': record.get('object', '')[:500],
            'source_url': record.get('source_url', ''),
            'summary': record.get('summary', '')[:1000],
            'scraped_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # Write to CSV
        file_exists = os.path.exists(self.filename)
        
        try:
            with open(self.filename, 'a', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=self.headers)
                if not file_exists:
                    writer.writeheader()
                writer.writerow(row)
            
            self.existing_refs.add(ref)
            logger.info(f"  [CSV] Saved: {ref}")
            return True
        except Exception as e:
            logger.error(f"  [CSV] Error saving: {e}")
            return False
    
    def get_count(self) -> int:
        """Get total count."""
        return len(self.existing_refs)

# ─────────────────────────────────────────────────────────────
# TEXT EXTRACTION HELPERS
# ─────────────────────────────────────────────────────────────

def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    """Extract text from PDF bytes using simple parsing."""
    text = ""
    try:
        content = pdf_bytes.decode('latin-1', errors='ignore')
        
        # Extract text between BT and ET operators
        text_parts = []
        for match in re.finditer(r'BT(.*?)ET', content, re.DOTALL):
            text_parts.append(match.group(1))
        
        if text_parts:
            result = ' '.join(text_parts)
            result = re.sub(r'\\([\d]+)', '', result)
            result = re.sub(r'[\(\)\[\]TJjTfTmTd]', ' ', result)
            result = re.sub(r'\s+', ' ', result)
            text = result.strip()
        
        if not text or len(text) < 50:
            paren_texts = re.findall(r'\(([^)]{5,})\)', content)
            if paren_texts:
                text = ' '.join(paren_texts)
        
    except Exception as e:
        logger.debug(f"  [PDF] Extraction error: {e}")
    
    return text

def make_tender_key(title: str, reference: str = "") -> str:
    """Create a unique key for deduplication."""
    if reference:
        return f"ref:{reference}"
    return f"title:{re.sub(r'\s+', ' ', title[:150].lower().strip())}"

# ─────────────────────────────────────────────────────────────
# GROQ SUMMARY GENERATION (optional)
# ─────────────────────────────────────────────────────────────

def generate_summary(pdf_text: str, ref: str, buyer: str = "") -> str:
    """Generate professional summary using Groq or fallback."""
    if not GROQ_ENABLED:
        return generate_fallback_summary(pdf_text, ref, buyer)
    
    if not pdf_text or len(pdf_text) < 100:
        return "Texte insuffisant pour générer un résumé."
    
    system_prompt = """Tu es un expert en analyse des avis d'attribution des marchés publics marocains.
    Rédige un résumé professionnel, fluide et concis en français (3 à 5 phrases).
    Mets en évidence :
    - Attributaire (société gagnante)
    - Montant de l'offre retenue
    - Dates importantes
    - Objet du marché
    Termine par une conclusion pertinente.
    """
    
    user_prompt = f"""Référence: {ref}
Acheteur: {buyer}

Texte de l'avis d'attribution:
{pdf_text[:6000]}
"""
    
    try:
        response = requests.post(
            GROQ_API_URL,
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": GROQ_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.3,
                "max_tokens": 400
            },
            timeout=90
        )
        
        if response.status_code == 200:
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
        else:
            logger.warning(f"  [GROQ] Error {response.status_code}")
            return generate_fallback_summary(pdf_text, ref, buyer)
    except Exception as e:
        logger.warning(f"  [GROQ] Exception: {e}")
        return generate_fallback_summary(pdf_text, ref, buyer)

def generate_fallback_summary(pdf_text: str, ref: str, buyer: str = "") -> str:
    """Fallback summary using regex extraction."""
    # Extract winner
    winner_match = re.search(r'(?:attributaire|concurrent retenu|société)[\s:]*([^\n]+)', pdf_text, re.IGNORECASE)
    winner = winner_match.group(1).strip() if winner_match else "non spécifié"
    
    # Extract amount
    amount_match = re.search(r'(\d[\d\s]*[\d,.]*)\s*(?:Dhs?|MAD|DH)', pdf_text, re.IGNORECASE)
    amount = amount_match.group(1).strip() if amount_match else "non spécifié"
    
    # Extract dates
    dates = re.findall(r'(\d{2}/\d{2}/\d{4})', pdf_text)
    open_date = dates[0] if dates else "non spécifiée"
    
    # Extract object
    obj_match = re.search(r'objet\s*:?\s*([^\n]+)', pdf_text, re.IGNORECASE)
    obj = obj_match.group(1).strip()[:150] if obj_match else "non spécifié"
    
    summary = (f"Le marché {ref} a été attribué à {winner}. "
               f"Montant retenu : {amount} Dhs. "
               f"Ouverture des plis : {open_date}. "
               f"Objet : {obj}. "
               f"Ce résultat est à suivre pour CrystalWater.")
    
    return summary

# ─────────────────────────────────────────────────────────────
# WEB SCRAPING FUNCTIONS
# ─────────────────────────────────────────────────────────────

def extract_award_row(row, seen_refs: set) -> Optional[dict]:
    """Extract data from a single result row."""
    try:
        # Get reference
        ref_input = row.select_one("input[name*='refCons']")
        reference = ref_input.get("value", "") if ref_input else ""
        ref_span = row.select_one("span.ref")
        ref_visible = ref_span.get_text(strip=True) if ref_span else ""
        
        # Get object
        objet_div = row.select_one("div[id*='panelBlocObjet']")
        objet_text = ""
        if objet_div:
            objet_text = re.sub(r'^Objet\s*:\s*', '', objet_div.get_text(strip=True)).strip()
        
        # Get buyer
        acheteur_div = row.select_one("div[id*='panelBlocDenomination']")
        acheteur = ""
        if acheteur_div:
            acheteur = re.sub(r'^Acheteur public\s*:\s*', '', acheteur_div.get_text(strip=True)).strip()
        
        # Get category
        cat_div = row.select_one("div[id*='panelBlocCategorie']")
        categorie = cat_div.get_text(strip=True) if cat_div else ""
        
        # Get detail URL
        detail_url = ""
        actions_td = row.select_one("td.actions")
        if actions_td:
            link = actions_td.select_one("a[href*='DetailConsultation']")
            if link:
                href = link.get("href", "")
                detail_url = f"{BASE_URL}/{href}" if href.startswith("?") else urljoin(BASE_URL, href)
        
        # Check if it's a definitive result (has the award icon)
        lieu_td = row.select_one("td.col-90[headers='cons_lieuExe']")
        is_award = False
        if lieu_td:
            img = lieu_td.select_one("img[title='Résultat définitif']")
            if img:
                is_award = True
        
        if not is_award:
            return None
        
        # Deduplicate within this scan
        key = make_tender_key(objet_text or reference, reference or ref_visible)
        if key in seen_refs:
            return None
        seen_refs.add(key)
        
        return {
            "tender_reference": ref_visible or reference,
            "buyer": acheteur,
            "object": objet_text,
            "category": categorie,
            "detail_url": detail_url,
        }
        
    except Exception as e:
        logger.debug(f"  [ROW] Error: {e}")
        return None

def download_award_pdf(page, detail_url: str, ref: str) -> Optional[Dict[str, Any]]:
    """Download the award PDF from the detail page."""
    logger.info(f"  [DOWNLOAD] {ref}")
    
    try:
        page.goto(detail_url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)
        
        # Find download link
        download_link = None
        links = page.query_selector_all("li.picto-link a")
        for link in links:
            href = link.get_attribute("href")
            if href and "DownloadAvisJAL" in href:
                download_link = link
                break
        
        if not download_link:
            logger.warning(f"  [WARN] No download link for {ref}")
            return None
        
        # Download file
        with page.expect_download(timeout=120000) as download_info:
            download_link.click()
        
        download = download_info.value
        file_path = download.path()
        
        with open(file_path, "rb") as f:
            file_content = f.read()
        
        if not file_content or len(file_content) < 100:
            logger.error(f"  [ERROR] Empty file for {ref}")
            return None
        
        # If ZIP, extract PDF
        if download.suggested_filename.endswith(".zip"):
            try:
                with zipfile.ZipFile(io.BytesIO(file_content)) as zf:
                    pdf_files = [f for f in zf.namelist() if f.lower().endswith(".pdf")]
                    if not pdf_files:
                        logger.warning(f"  [WARN] No PDF in ZIP for {ref}")
                        return None
                    file_content = zf.read(pdf_files[0])
            except Exception as e:
                logger.error(f"  [ERROR] Unzipping: {e}")
                return None
        
        # Extract text from PDF
        pdf_text = extract_text_from_pdf_bytes(file_content)
        if not pdf_text or len(pdf_text) < 50:
            logger.warning(f"  [WARN] Could not extract text from {ref}")
            pdf_text = ""
        
        return {
            "pdf_content": pdf_text,
        }
        
    except Exception as e:
        logger.error(f"  [ERROR] Download: {type(e).__name__}: {e}")
        return None

# ─────────────────────────────────────────────────────────────
# MAIN SCAN FUNCTION
# ─────────────────────────────────────────────────────────────

def scan_winners_to_csv():
    """Main function to scan winners and save to CSV."""
    print("\n" + "="*70)
    print("  CrystalWater - Winner Results → CSV Exporter")
    print("  " + datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    print("  Output: winner_results.csv")
    if GROQ_ENABLED:
        print(f"  [IA] Groq active - Model: {GROQ_MODEL}")
    else:
        print(f"  [IA] Groq DISABLED - using fallback")
    print("="*70 + "\n")
    
    # Initialize CSV storage
    csv_storage = WinnerCSV()
    print(f"[CSV] Found {csv_storage.get_count()} existing winners")
    
    seen_refs = set()
    total_new = 0
    browser = None
    context = None
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=[
                '--no-sandbox', '--disable-setuid-sandbox',
                '--disable-dev-shm-usage', '--disable-blink-features=AutomationControlled',
            ])
            context = browser.new_context(
                viewport={"width": 1366, "height": 768},
                locale="fr-FR",
                timezone_id="Africa/Casablanca",
                accept_downloads=True,
            )
            page = context.new_page()
            
            # Go to search page
            print("\n[NAV] Navigating to portal...")
            page.goto(
                "https://www.marchespublics.gov.ma/index.php?page=entreprise.EntrepriseAdvancedSearch&AllAnn",
                wait_until="domcontentloaded",
                timeout=60000
            )
            page.wait_for_timeout(3000)
            
            # Click "Résultats définitifs"
            try:
                link = page.query_selector("a[href*='AvisAttribution']")
                if link:
                    link.click()
                    page.wait_for_timeout(3000)
                    print("[NAV] Clicked 'Résultats définitifs'")
                else:
                    page.goto(
                        "https://www.marchespublics.gov.ma/index.php?page=entreprise.EntrepriseAdvancedSearch&AvisAttribution",
                        wait_until="domcontentloaded"
                    )
                    page.wait_for_timeout(3000)
            except Exception as e:
                logger.warning(f"  [NAV] Error: {e}")
            
            # Click search
            try:
                search_btn = page.query_selector("#ctl0_CONTENU_PAGE_AdvancedSearch_lancerRecherche")
                if search_btn:
                    search_btn.click()
                    page.wait_for_timeout(5000)
                    print("[NAV] Clicked search button")
                else:
                    page.evaluate("document.querySelector('form').submit()")
                    page.wait_for_timeout(5000)
            except:
                pass
            
            # Wait for results
            try:
                page.wait_for_selector("tr:has(td.col-450)", timeout=60000)
                print("[NAV] Results loaded")
            except:
                print("[ERROR] No results found")
                return 0
            
            # Get total pages
            total_pages = 1
            try:
                nb = page.query_selector("#ctl0_CONTENU_PAGE_resultSearch_nombrePageTop")
                if nb:
                    total_pages = int(nb.inner_text().strip())
                    print(f"[PAGES] Total: {total_pages}")
            except:
                pass
            
            # ──────────────────────
            # Paginate
            # ──────────────────────
            page_num = 1
            consecutive_empty = 0
            STOP_AFTER = 15
            
            print(f"\n[SCAN] Starting...")
            
            while page_num <= total_pages and consecutive_empty < STOP_AFTER:
                if page_num > 1:
                    try:
                        page.fill("#ctl0_CONTENU_PAGE_resultSearch_numPageTop", str(page_num))
                        page.wait_for_timeout(500)
                        page.press("#ctl0_CONTENU_PAGE_resultSearch_numPageTop", "Enter")
                        page.wait_for_timeout(5000)
                        page.wait_for_selector("tr:has(td.col-450)", timeout=20000)
                    except:
                        consecutive_empty += 1
                        page_num += 1
                        continue
                
                # Parse page
                soup = BeautifulSoup(page.content(), "html.parser")
                rows = soup.select("tr:has(td.col-450)")
                
                if not rows:
                    consecutive_empty += 1
                    page_num += 1
                    continue
                
                # Process rows
                for idx, row in enumerate(rows):
                    try:
                        data = extract_award_row(row, seen_refs)
                        if not data:
                            continue
                        
                        ref = data.get("tender_reference")
                        if csv_storage.exists(ref):
                            logger.debug(f"  [SKIP] Already exists: {ref}")
                            continue
                        
                        detail_url = data.get("detail_url")
                        if not detail_url:
                            continue
                        
                        print(f"\n[NEW] {ref}")
                        print(f"  Buyer: {data.get('buyer', '')[:50]}")
                        print(f"  Object: {data.get('object', '')[:80]}...")
                        
                        # Download PDF
                        dce_page = context.new_page()
                        try:
                            result = download_award_pdf(dce_page, detail_url, ref)
                            
                            if result:
                                pdf_text = result.get("pdf_content", "")
                                
                                # Generate summary
                                summary = generate_summary(
                                    pdf_text, 
                                    ref, 
                                    data.get("buyer", "")
                                )
                                print(f"  Summary: {summary[:150]}...")
                                
                                # Parse extracted data
                                winner_match = re.search(r'(?:attributaire|concurrent retenu|société)[\s:]*([^\n]+)', 
                                                        summary + "\n" + pdf_text, re.IGNORECASE)
                                winner = winner_match.group(1).strip() if winner_match else ""
                                
                                amount_match = re.search(r'(\d[\d\s]*[\d,.]*)\s*(?:Dhs?|MAD|DH)', pdf_text, re.IGNORECASE)
                                amount = ""
                                if amount_match:
                                    amount = amount_match.group(1).strip()
                                
                                date_match = re.search(r'(\d{2}/\d{2}/\d{4})', pdf_text)
                                award_date = date_match.group(1) if date_match else ""
                                
                                # Save to CSV
                                record = {
                                    "tender_reference": ref,
                                    "buyer": data.get("buyer", ""),
                                    "winner": winner,
                                    "awarded_amount": amount,
                                    "award_date": award_date,
                                    "object": data.get("object", ""),
                                    "source_url": detail_url,
                                    "summary": summary,
                                }
                                
                                if csv_storage.save(record):
                                    total_new += 1
                                    print(f"  ✅ SAVED to CSV")
                                else:
                                    print(f"  ❌ Failed to save")
                            else:
                                print(f"  ⚠️ No PDF downloaded")
                                
                        except Exception as e:
                            logger.error(f"  [ERROR] Processing {ref}: {e}")
                        finally:
                            dce_page.close()
                            
                    except Exception as e:
                        logger.error(f"  [ERROR] Row {idx}: {e}")
                        continue
                
                consecutive_empty = 0
                print(f"\n[PAGE] {page_num}/{total_pages} - {len(rows)} rows | Total winners: {total_new}")
                page_num += 1
            
            print(f"\n[SCAN] Completed")
            
    except Exception as e:
        logger.error(f"  [FATAL] {type(e).__name__}: {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        if context:
            try:
                context.close()
            except:
                pass
        if browser:
            try:
                browser.close()
            except:
                pass
    
    # Final summary
    print("\n" + "="*70)
    print(f"  ✅ SCAN COMPLETE")
    print(f"  New winners saved to CSV: {total_new}")
    print(f"  Total winners in CSV: {csv_storage.get_count()}")
    print(f"  File: {CSV_FILENAME}")
    print("="*70 + "\n")
    return total_new

# ─────────────────────────────────────────────────────────────
# CONTINUOUS MODE
# ─────────────────────────────────────────────────────────────

def scan_winners_continuous():
    """Run winner scan every 30 minutes."""
    SCAN_INTERVAL = 1800  # 30 minutes
    
    while True:
        try:
            scan_winners_to_csv()
        except Exception as e:
            logger.error(f"Scan error: {e}")
        
        print(f"\n[WAIT] Next scan in {SCAN_INTERVAL//60} minutes...")
        time.sleep(SCAN_INTERVAL)

# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--continuous":
        scan_winners_continuous()
    else:
        scan_winners_to_csv()