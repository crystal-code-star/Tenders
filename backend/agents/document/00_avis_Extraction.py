"""
00_avis_Extraction.py — Avis Field Extraction avec Groq AI
Utilise Groq pour comprendre le texte et extraire les champs
"""
import os
import sys
import logging
import argparse
import base64
import tempfile
import zipfile
import subprocess
import re
import json
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from dotenv import load_dotenv
from colorama import init, Fore, Style, Back
import supabase
from groq import Groq

init(autoreset=True)

current_dir = Path(__file__).resolve().parent
avis_dir = current_dir / "avis"
sys.path.insert(0, str(current_dir))

env_path = current_dir.parent.parent / ".env"
load_dotenv(env_path)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

from dce_classifier import classify_dce_file
from extractors import route_extractor

DEBUG_TEXT = os.getenv("DEBUG_AVIS_TEXT", "0") == "1"
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    print(f"\n{Fore.RED}❌ ERREUR: Identifiants Supabase manquants dans .env")
    sys.exit(1)

if not GROQ_API_KEY:
    print(f"\n{Fore.RED}❌ ERREUR: GROQ_API_KEY manquante dans .env")
    sys.exit(1)

supabase_client = supabase.create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
groq_client = Groq(api_key=GROQ_API_KEY)

# Statistiques globales
global_stats = {
    "total_tenders": 0,
    "processed": 0,
    "skipped_no_zip": 0,
    "skipped_already_done": 0,
    "errors": 0,
    "total_fields_found": 0,
    "total_fields_possible": 0
}

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

def is_french_avis_file(filename: str) -> bool:
    """Détecte si c'est un fichier Avis en français"""
    filename_lower = filename.lower()
    french_keywords = ['avis', 'aoo', 'ao', 'appel', 'consultation', 'dce', 'cahier', 'prescriptions', 'cps']
    exclude_keywords = ['rc', 'bp', 'bpu', 'bordereau', 'acte', 'engagement', 
                       'attestation', 'certificat', 'plan', 'planning', 'rapport',
                       'cv', 'curriculum', 'rib', 'releve', 'bancaire']
    
    has_french = any(kw in filename_lower for kw in french_keywords)
    is_excluded = any(kw in filename_lower for kw in exclude_keywords)
    
    return has_french and not is_excluded

def ocr_pdf_bytes_pymupdf(file_bytes: bytes, filename: str = "") -> str:
    """OCR avec PyMuPDF (pas besoin de Poppler)"""
    text = ""
    
    print_info(f"OCR en cours: {filename}")
    
    try:
        import fitz
        pdf_doc = fitz.open(stream=file_bytes, filetype="pdf")
        all_text = []
        
        for page in pdf_doc:
            page_text = page.get_text()
            if page_text.strip():
                all_text.append(page_text)
        
        pdf_doc.close()
        text = "\n".join(all_text)
        
        if len(text.strip()) > 100:
            print_success(f"Texte extrait via PyMuPDF ({len(text)} caractères)")
            return text
    except ImportError:
        print_error("PyMuPDF non installé. Faites: pip install PyMuPDF")
        return ""
    except Exception as e:
        print_warning(f"Erreur PyMuPDF texte: {e}")
    
    try:
        import fitz
        import pytesseract
        from PIL import Image
        import io
        
        print_info("OCR avec PyMuPDF + Tesseract...")
        pdf_doc = fitz.open(stream=file_bytes, filetype="pdf")
        all_text = []
        
        for i, page in enumerate(pdf_doc):
            pix = page.get_pixmap(dpi=300)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            page_text = pytesseract.image_to_string(img, lang='fra', config='--psm 6')
            
            if page_text.strip():
                all_text.append(page_text)
            
            if pdf_doc.page_count > 1:
                print_info(f"Page {i+1}/{pdf_doc.page_count} ({len(page_text)} caractères)")
        
        pdf_doc.close()
        text = "\n".join(all_text)
        
        if len(text.strip()) > 50:
            print_success(f"OCR terminé ({len(text)} caractères)")
            return text
        else:
            print_warning("OCR a extrait peu de texte")
            
    except ImportError as e:
        print_error(f"Modules manquants: {e}")
    except Exception as e:
        print_error(f"Erreur OCR: {e}")
    
    try:
        import pdfplumber
        with pdfplumber.open(BytesIO(file_bytes)) as pdf:
            all_text = [page.extract_text() for page in pdf.pages if page.extract_text()]
            text = "\n".join(all_text)
            if len(text.strip()) > 100:
                print_success(f"Texte via pdfplumber ({len(text)} caractères)")
                return text
    except:
        pass
    
    return text

def extract_with_groq(text: str, filename: str) -> dict:
    """
    Utilise Groq AI pour extraire les champs du texte
    Avec LLaMA 3.1 70B ou Mixtral 8x7B
    """
    print_info("🤖 Analyse avec Groq AI...")
    
    # Tronquer le texte si trop long (limite de contexte)
    max_chars = 15000
    if len(text) > max_chars:
        text = text[:max_chars] + "\n... (texte tronqué)"
        print_info(f"Texte tronqué à {max_chars} caractères pour l'analyse")
    
    prompt = f"""Tu es un expert en extraction d'informations d'appels d'offres marocains.
    
Analyse ce texte d'Avis d'Appel d'Offres et extrait UNIQUEMENT ces 3 informations :

1. **Estimation (DHS TTC)** : Le montant estimé du marché en Dirhams Marocains (DHS/DH/MAD)
2. **Caution Provisoire** : Le montant ou pourcentage de la caution provisoire
3. **Date et Heure Visite des Lieux** : La date et l'heure de la visite des lieux/site/chantier

⚠️ RÈGLES IMPORTANTES :
- Si l'information n'est PAS présente dans le texte, laisse le champ VIDE
- Pour l'estimation : extrait uniquement le montant numérique et la devise (ex: "1 500 000 DHS")
- Pour la caution : indique si c'est un montant (DHS) ou un pourcentage (%)
- Pour la visite : format "JJ/MM/AAAA à HHhMM" ou "JJ/MM/AAAA"
- Ne pas inventer d'informations
- Réponds UNIQUEMENT en JSON valide

---

TEXTE À ANALYSER :
{text}

---

RÉPONDS UNIQUEMENT AVEC CE JSON (sans texte avant/après) :
{{
  "estimation_ttc": "MONTANT DHS ou vide",
  "caution_provisoire": "MONTANT DHS ou POURCENTAGE% ou vide",
  "visite_lieux": "DATE et HEURE ou vide"
}}
"""
    
    try:
        response = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",  # ou "mixtral-8x7b-32768"
            messages=[
                {"role": "system", "content": "Tu es un assistant qui extrait des données d'appels d'offres. Tu réponds UNIQUEMENT en JSON valide, sans aucun autre texte."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=500,
            top_p=0.95
        )
        
        result_text = response.choices[0].message.content.strip()
        
        # Nettoyer la réponse (parfois Groq ajoute des ```json)
        result_text = result_text.replace("```json", "").replace("```", "").strip()
        
        # Parser le JSON
        data = json.loads(result_text)
        
        fields = {
            "Estimation (DHS TTC)": data.get("estimation_ttc", "").strip(),
            "Caution Provisoire": data.get("caution_provisoire", "").strip(),
            "Date et Heure Visite des Lieux": data.get("visite_lieux", "").strip()
        }
        
        # Nettoyer les valeurs "vide"
        for key in fields:
            if fields[key].lower() in ["vide", "null", "none", "", "n/a"]:
                fields[key] = ""
        
        print_success(f"Groq a extrait {sum(1 for v in fields.values() if v)}/3 champs")
        
        return fields
        
    except json.JSONDecodeError as e:
        print_error(f"Erreur parsing JSON Groq: {e}")
        print_info(f"Réponse brute: {result_text[:300]}")
        return {"Estimation (DHS TTC)": "", "Caution Provisoire": "", "Date et Heure Visite des Lieux": ""}
    
    except Exception as e:
        print_error(f"Erreur Groq API: {e}")
        return {"Estimation (DHS TTC)": "", "Caution Provisoire": "", "Date et Heure Visite des Lieux": ""}

def extract_avis_fields_hybrid(text: str, filename: str) -> dict:
    """
    Extraction hybride : Regex d'abord, puis Groq pour les champs manquants
    """
    # Étape 1: Extraction par regex (rapide et gratuite)
    regex_fields = extract_avis_fields_regex(text)
    
    found_regex = sum(1 for v in regex_fields.values() if v)
    print_info(f"Regex: {found_regex}/3 champs trouvés")
    
    # Si tous les champs sont trouvés par regex, on s'arrête là
    if found_regex == 3:
        print_success("Tous les champs extraits par regex ✅")
        return regex_fields
    
    # Étape 2: Pour les champs manquants, utiliser Groq
    missing_fields = [k for k, v in regex_fields.items() if not v]
    print_info(f"Champs manquants: {', '.join(missing_fields)} → Analyse Groq...")
    
    # Demander à Groq tous les champs mais on gardera seulement les manquants
    groq_fields = extract_with_groq(text, filename)
    
    # Fusionner : garder les champs regex s'ils existent, sinon prendre Groq
    final_fields = {}
    for key in regex_fields:
        if regex_fields[key]:
            final_fields[key] = regex_fields[key]
        else:
            final_fields[key] = groq_fields.get(key, "")
    
    total_found = sum(1 for v in final_fields.values() if v)
    print_success(f"Total après Groq: {total_found}/3 champs")
    
    return final_fields

def extract_avis_fields_regex(text: str) -> dict:
    """Extraction par regex (version améliorée)"""
    fields = {
        "Estimation (DHS TTC)": "",
        "Caution Provisoire": "",
        "Date et Heure Visite des Lieux": ""
    }
    
    if not text or not text.strip():
        return fields
    
    text_clean = re.sub(r'\s+', ' ', text.replace('\n', ' ').replace('\r', ' '))
    
    # ─── ESTIMATION ─────────────────────────────────────────────
    estimation_patterns = [
        r'[Ee]stimation\s*(?:du\s*(?:marché|projet|coût|cout))?\s*:?\s*([\d\s,.]+)\s*(?:DHS|DH|dirhams|MAD)',
        r'[Mm]ontant\s*(?:total|global|estim[ée]|prévisionnel)?\s*(?:du\s*(?:marché|projet))?\s*(?:est\s*)?(?:estim[ée]\s*)?(?:à|:)?\s*([\d\s,.]+)\s*(?:DHS|DH|dirhams|MAD)',
        r'(?:estim[ée]|estimé)\s*(?:à|:)?\s*([\d\s,.]+)\s*(?:DHS|DH|dirhams|MAD)\s*(?:TTC|toutes\s*taxes)',
        r'([\d\s,.]+)\s*(?:DHS|DH|dirhams|MAD)\s*(?:TTC|toutes\s*taxes\s*comprises)',
        r'(?:coût|cout)\s*(?:total|global)?\s*(?:du\s*(?:marché|projet))?\s*:?\s*([\d\s,.]+)\s*(?:DHS|DH|dirhams|MAD)',
    ]
    
    for pattern in estimation_patterns:
        match = re.search(pattern, text_clean, re.IGNORECASE)
        if match:
            montant = re.sub(r'[^\d]', '', match.group(1))
            if montant and len(montant) >= 4:
                montant_format = f"{int(montant):,}".replace(',', ' ') + " DHS"
                fields["Estimation (DHS TTC)"] = montant_format
                break
    
    # ─── CAUTION PROVISOIRE ─────────────────────────────────────
    caution_patterns = [
        r'[Cc]aution\s*provisoire\s*:?\s*([\d\s,.]+)\s*(?:DHS|DH|dirhams|MAD)',
        r'[Cc]aution\s*provisoire\s*(?:est\s*fix[ée]e?\s*)?(?:à|de|:)?\s*([\d\s,.]+)\s*(?:DHS|DH|dirhams|MAD)',
        r'[Cc]autionnement\s*provisoire\s*:?\s*([\d\s,.]+)\s*(?:DHS|DH|dirhams|MAD)',
        r'(?:montant\s*(?:de\s*la)?\s*)?[Cc]aution\s*(?:provisoire)?\s*:?\s*([\d\s,.]+)\s*(?:DHS|DH|dirhams)',
        r'[Cc]aution\s*provisoire\s*(?:fix[ée]e?\s*)?(?:à|de|:)?\s*([\d,.]+)\s*%',
        r'[Cc]aution\s*provisoire\s*:?\s*([\d,.]+)\s*%\s*(?:du\s*montant)',
        r'[Cc]autionnement\s*provisoire\s*(?:est\s*fix[ée]\s*)?(?:à|de)?\s*([\d,.]+)\s*%',
    ]
    
    for pattern in caution_patterns:
        match = re.search(pattern, text_clean, re.IGNORECASE)
        if match:
            valeur = match.group(1).strip()
            contexte = match.group(0)
            
            if '%' in contexte or '%' in valeur:
                fields["Caution Provisoire"] = f"{valeur} %"
            else:
                montant = re.sub(r'[^\d]', '', valeur)
                if montant and len(montant) >= 2:
                    montant_format = f"{int(montant):,}".replace(',', ' ') + " DHS"
                    fields["Caution Provisoire"] = montant_format
            break
    
    # Si pas trouvé, chercher "caution" seul avec contexte
    if not fields["Caution Provisoire"]:
        caution_match = re.search(r'[Cc]aution\s*:?\s*([\d\s,.]+)\s*(?:DHS|DH|dirhams|MAD)', text_clean)
        if caution_match:
            montant = re.sub(r'[^\d]', '', caution_match.group(1))
            if montant and len(montant) >= 2:
                fields["Caution Provisoire"] = f"{int(montant):,} DHS".replace(',', ' ')
    
    # ─── VISITE DES LIEUX ─────────────────────────────────────
    visite_patterns = [
        r'[Vv]isite\s*(?:des|de)\s*(?:lieux|locaux|site|chantier|ouvrage|installation)s?\s*(?:aura\s*lieu|est\s*prévue|est\s*fix[ée]e|se\s*d[ée]roulera)?\s*(?:le|,)?\s*(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})\s*(?:à|,)?\s*(\d{1,2}[hH:]\d{0,2})',
        r'[Vv]isite\s*(?:des|de)\s*(?:lieux|locaux|site|chantier|ouvrage|installation)s?\s*:?\s*(?:le\s*)?(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})',
        r'[Vv]isite\s*(?:des|de)\s*lieux.*?(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})',
        r'(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})\s*(?:à|,)?\s*(\d{1,2}[hH:]\d{0,2}).*?visite',
        r'[Vv]isite.*?(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}).*?(\d{1,2}[hH]\d{0,2})',
    ]
    
    for pattern in visite_patterns:
        match = re.search(pattern, text_clean, re.IGNORECASE | re.DOTALL)
        if match:
            if len(match.groups()) >= 2 and match.group(2):
                date = match.group(1).strip()
                heure = match.group(2).strip().replace('H', 'h')
                fields["Date et Heure Visite des Lieux"] = f"{date} à {heure}"
            else:
                fields["Date et Heure Visite des Lieux"] = match.group(1).strip()
            break
    
    # Recherche élargie
    if not fields["Date et Heure Visite des Lieux"]:
        visite_match = re.search(r'[Vv]isite\s*(?:des|de)\s*lieux.{0,300}', text_clean, re.DOTALL)
        if visite_match:
            contexte = visite_match.group(0)
            date_match = re.search(r'(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})', contexte)
            heure_match = re.search(r'(\d{1,2}[hH:]\d{0,2})', contexte)
            
            if date_match and heure_match:
                fields["Date et Heure Visite des Lieux"] = f"{date_match.group(1)} à {heure_match.group(1).replace('H', 'h')}"
            elif date_match:
                fields["Date et Heure Visite des Lieux"] = date_match.group(1)
    
    return fields

def extract_files_from_zip(zip_data):
    """Extrait les fichiers Avis du ZIP"""
    try:
        if isinstance(zip_data, str):
            zip_bytes = base64.b64decode(zip_data)
        else:
            zip_bytes = zip_data
        
        with zipfile.ZipFile(BytesIO(zip_bytes)) as zip_file:
            all_files = zip_file.namelist()
            avis_files = [f for f in all_files if is_french_avis_file(Path(f).name)]
            
            if not avis_files:
                avis_files = [f for f in all_files if f.lower().endswith('.pdf')]
                if avis_files:
                    print_warning(f"Aucun fichier Avis détecté, utilisation de tous les PDF ({len(avis_files)})")
            
            extracted = []
            for filename in avis_files:
                file_bytes = zip_file.read(filename)
                extracted.append({
                    "filename": Path(filename).name,
                    "full_path": filename,
                    "file_bytes": file_bytes,
                    "size_kb": len(file_bytes) / 1024
                })
            
            return extracted
    except Exception as e:
        print_error(f"Erreur extraction ZIP: {e}")
        return []

def get_all_tenders_to_process():
    """Récupère tous les AO qui ont un ZIP mais pas encore traités pour les avis"""
    print_header("RECHERCHE DE TOUS LES APPELS D'OFFRES À TRAITER")
    
    try:
        # Récupérer tous les AO qui ont un ZIP (base64 ou URL)
        response = supabase_client.table("tenders_3").select(
            "reference, objet, acheteur_public, dce_zip_base64, dce_zip_url, avis_extraction_status"
        ).not_.is_("dce_zip_base64", "null").execute()
        
        tenders_base64 = response.data if response.data else []
        
        response2 = supabase_client.table("tenders_3").select(
            "reference, objet, acheteur_public, dce_zip_base64, dce_zip_url, avis_extraction_status"
        ).not_.is_("dce_zip_url", "null").execute()
        
        tenders_url = response2.data if response2.data else []
        
        # Fusionner et dédupliquer
        all_tenders = {}
        for t in tenders_base64 + tenders_url:
            ref = t.get('reference')
            if ref and ref not in all_tenders:
                all_tenders[ref] = t
        
        # Filtrer ceux qui ont déjà été traités avec succès
        to_process = []
        for ref, tender in all_tenders.items():
            status = tender.get('avis_extraction_status')
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
    """Récupère les fichiers depuis Supabase pour une référence"""
    try:
        response = supabase_client.table("tenders_3").select("*").eq("reference", reference).execute()
        
        if not response.data:
            print_error(f"Aucun appel d'offre: {reference}")
            return None
        
        tender = response.data[0]
        
        base64_zip = tender.get('dce_zip_base64')
        zip_url = tender.get('dce_zip_url')
        
        if base64_zip:
            files = extract_files_from_zip(base64_zip)
        elif zip_url:
            print_info(f"Téléchargement: {zip_url}")
            import requests as req
            resp = req.get(zip_url, timeout=120)
            if resp.status_code == 200:
                print_success(f"ZIP téléchargé ({len(resp.content):,} octets)")
                files = extract_files_from_zip(resp.content)
            else:
                print_error(f"Échec téléchargement: HTTP {resp.status_code}")
                return None
        else:
            return None
        
        return {"tender": tender, "files": files, "reference": reference}
        
    except Exception as e:
        print_error(f"Erreur Supabase: {e}")
        return None

def process_avis_file(filename: str, file_bytes: bytes) -> dict:
    """Traite un fichier Avis avec OCR + Groq"""
    print_section(f"FICHIER AVIS: {filename}")
    print_info(f"Taille: {len(file_bytes)/1024:.1f} Ko")
    
    classification = classify_dce_file(filename, file_bytes)
    file_info = classification.get("file_type", {})
    is_scanned = classification.get("is_scanned", False)
    file_ext = file_info.get("ext", Path(filename).suffix.lower().lstrip('.'))
    
    print_info(f"Type: {file_info.get('type', 'inconnu').upper()} (.{file_ext})")
    
    if is_scanned or file_ext == 'pdf':
        if is_scanned:
            print_warning("Document scanné → OCR")
        extracted_text = ocr_pdf_bytes_pymupdf(file_bytes, filename)
    elif file_ext == 'docx':
        print_info("Extraction texte Word...")
        extracted = route_extractor(file_bytes, file_info)
        if extracted.get("skipped"):
            print_error(f"Échec extraction: {extracted.get('skip_reason')}")
            return {"success": False, "error": extracted.get('skip_reason')}
        extracted_text = extracted.get("text", "")
    elif file_ext == 'doc':
        extracted_text = extract_text_from_doc_bytes(file_bytes)
    else:
        extracted = route_extractor(file_bytes, file_info)
        if extracted.get("skipped"):
            print_error(f"Échec extraction: {extracted.get('skip_reason')}")
            return {"success": False, "error": extracted.get('skip_reason')}
        extracted_text = extracted.get("text", "")
    
    if not extracted_text or len(extracted_text.strip()) < 20:
        print_error("Pas assez de texte extrait")
        return {"success": False, "error": "Pas de texte"}
    
    print_success(f"Texte extrait: {len(extracted_text):,} caractères")
    
    if DEBUG_TEXT:
        print(f"\n{Fore.CYAN}{'─'*80}")
        print(f"{Fore.CYAN}  APERÇU TEXTE:")
        print(f"{Fore.CYAN}{'─'*80}")
        print(extracted_text[:3000])
        if len(extracted_text) > 3000:
            print(f"\n... ({len(extracted_text) - 3000} caractères supplémentaires)")
        print(f"{Fore.CYAN}{'─'*80}\n")
    
    # Extraction hybride : Regex + Groq
    print_info("Extraction hybride (Regex + Groq AI)...")
    avis_fields = extract_avis_fields_hybrid(extracted_text, filename)
    
    return {
        "success": True,
        "filename": filename,
        "is_scanned": is_scanned,
        "text_length": len(extracted_text),
        "avis_fields": avis_fields
    }

def extract_text_from_doc_bytes(file_bytes: bytes) -> str:
    """Extraction .doc"""
    try:
        from docx import Document
        doc = Document(BytesIO(file_bytes))
        return "\n".join([p.text.strip() for p in doc.paragraphs if p.text.strip()])
    except:
        pass
    
    text = file_bytes.decode('latin-1', errors='ignore')
    text = re.sub(r'[^\x20-\x7E\xA0-\xFF\n\r\t\.\,\;\:\!\?\(\)\[\]\{\}\-\+\/\@\#\$\%\^\&\*\=]', ' ', text)
    return re.sub(r'\s+', ' ', text)

def save_to_supabase(reference: str, fields: dict, filename: str, is_scanned: bool = False):
    """Sauvegarde dans Supabase"""
    try:
        update_data = {
            "avis_estimation_ttc": fields.get("Estimation (DHS TTC)", ""),
            "avis_caution_dhs": fields.get("Caution Provisoire", ""),
            "avis_visite_lieux": fields.get("Date et Heure Visite des Lieux", ""),
            "avis_source_file": filename,
            "avis_is_scanned": is_scanned,
            "avis_extraction_status": "completed",
            "avis_extracted_at": datetime.now(timezone.utc).isoformat()
        }
        supabase_client.table("tenders_3").update(update_data).eq("reference", reference).execute()
        return True
    except Exception as e:
        print_error(f"Erreur sauvegarde: {e}")
        return False

def process_single_reference(reference: str, save: bool = True, groq_only: bool = False):
    """Traite une seule référence d'AO"""
    print(f"\n{Back.BLUE}{Fore.WHITE}{Style.BRIGHT}{'='*80}")
    print(f"{Back.BLUE}{Fore.WHITE}{Style.BRIGHT}  EXTRACTION AVIS - OCR + GROQ AI")
    print(f"{Back.BLUE}{Fore.WHITE}{Style.BRIGHT}  Estimation | Caution Provisoire | Visite des Lieux")
    print(f"{Back.BLUE}{Fore.WHITE}{Style.BRIGHT}{'='*80}")
    
    print_header(f"TRAITEMENT: {reference}")
    
    tender_data = get_tender_files(reference)
    
    if not tender_data or not tender_data.get("files"):
        print_error("❌ EXTRACTION IMPOSSIBLE - Pas de fichiers Avis trouvés")
        return {"success": False, "error": "Pas de fichiers"}
    
    files = tender_data["files"]
    
    print_section(f"📁 {len(files)} FICHIER(S) AVIS")
    for f in files:
        icon = "📄" if f['filename'].endswith('.pdf') else "📝"
        print(f"  {icon} {f['filename']} ({f['size_kb']:.1f} Ko)")
    
    all_results = []
    for file_data in files:
        result = process_avis_file(file_data["filename"], file_data["file_bytes"])
        all_results.append(result)
        
        if result.get("success"):
            fields = result["avis_fields"]
            
            print_section("📊 RÉSULTATS")
            print(f"  {Fore.WHITE}┌{'─'*65}┐")
            print(f"  {Fore.WHITE}│ {Fore.YELLOW}{'CHAMP':<28} {Fore.WHITE}│ {Fore.YELLOW}{'VALEUR':<33} {Fore.WHITE}│")
            print(f"  {Fore.WHITE}├{'─'*65}┤")
            
            for label, key in [
                ("Estimation (DHS TTC)", "Estimation (DHS TTC)"), 
                ("Caution Provisoire", "Caution Provisoire"),
                ("Visite des Lieux", "Date et Heure Visite des Lieux")
            ]:
                val = fields.get(key, "")
                icon = "✓" if val else "✗"
                color = Fore.GREEN if val else Fore.RED
                print(f"  {Fore.WHITE}│ {color}{icon} {label:<25} {Fore.WHITE}│ {color}{val:<33} {Fore.WHITE}│")
            
            print(f"  {Fore.WHITE}└{'─'*65}┘")
            
            found = sum(1 for v in fields.values() if v)
            pct = int(found/3*100)
            print(f"\n  {Fore.CYAN}📈 Taux d'extraction: {Fore.WHITE}{found}/3 ({pct}%)")
            
            # Mettre à jour les stats globales
            global_stats["total_fields_found"] += found
            global_stats["total_fields_possible"] += 3
            
            if save:
                if save_to_supabase(reference, fields, file_data["filename"], result.get("is_scanned", False)):
                    print_success("✅ Sauvegardé dans Supabase")
        else:
            print_error(f"Échec: {result.get('error')}")
    
    global_stats["processed"] += 1
    
    return {"success": True, "results": all_results}

def process_all_tenders(save: bool = True, groq_only: bool = False, limit: int = None):
    """Traite tous les AO non traités"""
    print(f"\n{Back.MAGENTA}{Fore.WHITE}{Style.BRIGHT}{'='*80}")
    print(f"{Back.MAGENTA}{Fore.WHITE}{Style.BRIGHT}  TRAITEMENT PAR LOT - TOUS LES APPELS D'OFFRES")
    print(f"{Back.MAGENTA}{Fore.WHITE}{Style.BRIGHT}  Mode: {'Groq Only' if groq_only else 'Hybride Regex + Groq'}")
    print(f"{Back.MAGENTA}{Fore.WHITE}{Style.BRIGHT}{'='*80}")
    
    tenders = get_all_tenders_to_process()
    
    if not tenders:
        print_warning("Aucun AO à traiter")
        return
    
    # Appliquer la limite si spécifiée
    if limit and limit > 0:
        tenders = tenders[:limit]
        print_info(f"Limite appliquée: {limit} AO maximum")
    
    total = len(tenders)
    print_header(f"🚀 DÉBUT DU TRAITEMENT - {total} AO")
    
    start_time = datetime.now()
    
    for i, tender in enumerate(tenders, 1):
        reference = tender.get('reference')
        objet = tender.get('objet', 'N/A')[:100]
        
        print(f"\n{Back.CYAN}{Fore.WHITE} {'='*80}")
        print(f"{Back.CYAN}{Fore.WHITE}  AO {i}/{total}: {reference}")
        print(f"{Back.CYAN}{Fore.WHITE}  Objet: {objet}")
        print(f"{Back.CYAN}{Fore.WHITE} {'='*80}")
        
        result = process_single_reference(reference, save=save, groq_only=groq_only)
        
        if not result.get("success"):
            global_stats["errors"] += 1
        
        # Afficher progression
        elapsed = datetime.now() - start_time
        avg_time = elapsed / i if i > 0 else elapsed
        remaining = avg_time * (total - i)
        
        print_section("📊 PROGRESSION")
        print_stat(f"Traités: {i}/{total} ({i/total*100:.1f}%)")
        print_stat(f"Temps écoulé: {str(elapsed).split('.')[0]}")
        print_stat(f"Temps restant estimé: {str(remaining).split('.')[0]}")
        print_stat(f"Champs trouvés: {global_stats['total_fields_found']}/{global_stats['total_fields_possible']}")
    
    # Résumé final
    print_header("📊 RÉSUMÉ FINAL DU TRAITEMENT PAR LOT")
    print(f"  {Fore.WHITE}┌{'─'*50}┐")
    print(f"  {Fore.WHITE}│ {Fore.YELLOW}{'STATISTIQUE':<30} {Fore.WHITE}│ {Fore.YELLOW}{'VALEUR':<16} {Fore.WHITE}│")
    print(f"  {Fore.WHITE}├{'─'*50}┤")
    print(f"  {Fore.WHITE}│ Total AO dans la BD          │ {global_stats['total_tenders']:<16} {Fore.WHITE}│")
    print(f"  {Fore.WHITE}│ AO déjà traités              │ {global_stats['skipped_already_done']:<16} {Fore.WHITE}│")
    print(f"  {Fore.WHITE}│ AO traités cette session     │ {global_stats['processed']:<16} {Fore.WHITE}│")
    print(f"  {Fore.WHITE}│ Erreurs                      │ {global_stats['errors']:<16} {Fore.WHITE}│")
    print(f"  {Fore.WHITE}│ Champs extraits              │ {global_stats['total_fields_found']}/{global_stats['total_fields_possible']:<13} {Fore.WHITE}│")
    
    success_rate = (global_stats['total_fields_found'] / global_stats['total_fields_possible'] * 100) if global_stats['total_fields_possible'] > 0 else 0
    print(f"  {Fore.WHITE}│ Taux de succès               │ {success_rate:.1f}%{'':<11} {Fore.WHITE}│")
    print(f"  {Fore.WHITE}└{'─'*50}┘")
    
    total_time = datetime.now() - start_time
    print(f"\n  {Fore.CYAN}⏱️  Temps total: {str(total_time).split('.')[0]}")
    
    print(f"\n{Back.GREEN}{Fore.WHITE}{Style.BRIGHT}{'='*80}")
    print(f"{Back.GREEN}{Fore.WHITE}{Style.BRIGHT}  TRAITEMENT PAR LOT TERMINÉ")
    print(f"{Back.GREEN}{Fore.WHITE}{Style.BRIGHT}{'='*80}\n")

def main():
    parser = argparse.ArgumentParser(description="Extraction Avis - OCR + Groq AI")
    
    # Groupe mutuellement exclusif: soit --all, soit --reference
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true", help="Traiter tous les AO non traités")
    group.add_argument("--reference", "-r", type=str, help="Référence AO spécifique")
    
    parser.add_argument("--save", "-s", action="store_true", default=True, 
                       help="Sauvegarder dans Supabase (activé par défaut pour --all)")
    parser.add_argument("--no-save", action="store_true", 
                       help="Ne pas sauvegarder dans Supabase")
    parser.add_argument("--groq-only", action="store_true", 
                       help="Utiliser uniquement Groq (pas de regex)")
    parser.add_argument("--limit", "-l", type=int, default=None,
                       help="Limiter le nombre d'AO à traiter (pour --all)")
    
    args = parser.parse_args()
    
    # Déterminer si on sauvegarde
    save_to_db = args.save and not args.no_save
    
    if args.all:
        # Mode traitement par lot
        process_all_tenders(save=save_to_db, groq_only=args.groq_only, limit=args.limit)
    else:
        # Mode traitement unique
        process_single_reference(args.reference, save=save_to_db, groq_only=args.groq_only)

if __name__ == "__main__":
    main()