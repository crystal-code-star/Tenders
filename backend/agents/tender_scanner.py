"""
tender_scanner.py — Africa Tenders Intelligence Module (v12.1 - DAILY SCAN)
========================================================================
CrystalWater — Traitement d'eau & Refroidissement industriel
https://crystalwater.ma/

SCAN QUOTIDIEN:
1. Scan les pages du site
2. Filtre les AO publiés entre 6h hier et 6h aujourd'hui
3. Pour chaque AO: Télécharge DCE → Extrait Avis → Extrait RC → Extrait BP
"""

import os, re, sys, json, uuid, time, logging, warnings, zipfile, io, tempfile
import threading, signal, importlib.util
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any, Tuple, Set
from urllib.parse import urljoin
from pathlib import Path

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except: pass
    os.environ['PYTHONIOENCODING'] = 'utf-8'

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

warnings.filterwarnings("ignore")
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

load_dotenv()

# Icônes
ICON_SCAN = "🔍"
ICON_AO = "📋"
ICON_DCE = "📥"
ICON_OK = "✅"
ICON_ERR = "❌"
ICON_WARN = "⚠️"
ICON_CLOCK = "🕐"
ICON_PAGE = "📄"
ICON_STATS = "📈"
ICON_SKIP = "⏭️"
ICON_EXTRACT = "📦"
ICON_START = "🚀"
ICON_FINISH = "🏁"
ICON_PROGRESS = "📊"

# Configuration du scan quotidien
DAILY_SCAN_HOUR = 6  # Heure de scan (6h du matin)
MAX_PAGES_PER_DAY = 200  # Pages max à scanner par jour

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "") or os.getenv("SUPABASE_KEY", "")
BASE_URL = "https://www.marchespublics.gov.ma"
SEARCH_URL = f"{BASE_URL}/index.php?page=entreprise.EntrepriseAdvancedSearch&AllCons&EnCours&domaineActivite=1.13"
TENDERS_TABLE = os.getenv("TENDERS_TABLE", "tenders_3")

CRYSTAL_FORM_DATA = {"nom":"Crystal","prenom":"Water","email":"marketing@crystalwater.ma","raisonSocial":"CrystalWater","address":"Adresse CrystalWater"}

# ═══════════════ LOGGING ═══════════════
logger = logging.getLogger("tender_scanner")
logger.setLevel(logging.INFO)
if not logger.handlers:
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter('%(message)s'))
    logger.addHandler(ch)
    if not os.path.exists('logs'): os.makedirs('logs')
    fh = logging.FileHandler(f'logs/scanner_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log', encoding='utf-8')
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(fh)

scan_stats = {
    "pages_scanned": 0,
    "total_pages": 0,
    "rows_checked": 0,
    "new_tenders": 0,
    "dce_downloaded": 0,
    "dce_failed": 0,
    "avis_extracted": 0,
    "rc_extracted": 0,
    "bp_extracted": 0,
    "start_time": None,
    "end_time": None,
    "skipped": {"deja_en_base": 0, "non_pertinent": 0, "date_depassee": 0, "titre_court": 0, "hors_periode": 0, "erreur": 0}
}

STRONG_KEYWORDS = ["station de traitement","station d'epuration","step","eau potable","aep","adduction d'eau","potabilisation","assainissement","eaux usees","eaux pluviales","reservoir d'eau","chateau d'eau","dessalement","osmose inverse","traitement des eaux","surpression","forage d'eau","captage","puits","vannes","clapets","debitmetre","pompe immergee","tour de refroidissement","refroidissement industriel","chloration","desinfection","filtration","lagunage","station de pompage","irrigation"]
MEDIUM_KEYWORDS = ["travaux","reseaux","canalisation","genie civil","fourniture","installation","rehabilitation","extension","construction","renouvellement","renforcement"]
STRICT_EXCLUSIONS = ["nettoyage des locaux","entretien des locaux","informatique","logiciel","site web","photovoltaique","solaire","dechets solides","gardiennage","restauration","cantine","fournitures de bureau","mobilier","climatiseurs","vehicule","voiture","ambulance"]

SKIP_REASONS = {
    "already_in_db": "Déjà en base",
    "not_related": "Non pertinent",
    "deadline_passed": "Date dépassée",
    "title_too_short": "Titre trop court",
    "outside_time_window": "Hors période (6h-6h)",
    "error": "Erreur extraction"
}

def get_daily_time_window():
    """Retourne la fenêtre de temps [6h hier, 6h aujourd'hui]"""
    now = datetime.now()
    today_6am = datetime(now.year, now.month, now.day, DAILY_SCAN_HOUR, 0, 0)
    
    if now < today_6am:
        # Avant 6h aujourd'hui => on scanne de 6h avant-hier à 6h hier
        end_time = today_6am - timedelta(days=1)
        start_time = end_time - timedelta(days=1)
    else:
        # Après 6h aujourd'hui => on scanne de 6h hier à 6h aujourd'hui
        end_time = today_6am
        start_time = end_time - timedelta(days=1)
    
    return start_time, end_time

def _sb_headers(): return {"apikey":SUPABASE_KEY,"Authorization":f"Bearer {SUPABASE_KEY}","Content-Type":"application/json","Prefer":"return=representation"}

def _sb_get(table,params=None):
    if not SUPABASE_URL: return []
    try:
        r=requests.get(f"{SUPABASE_URL}/rest/v1/{table}",headers=_sb_headers(),params=params or {},timeout=15)
        r.raise_for_status(); return r.json() or []
    except: return []

def _sb_upsert(rows):
    if not SUPABASE_URL or not rows: return False
    url=f"{SUPABASE_URL}/rest/v1/{TENDERS_TABLE}"
    headers={**_sb_headers(),"Prefer":"resolution=merge-duplicates,return=minimal"}
    ok=0
    for i in range(0,len(rows),50):
        try:
            r=requests.post(url,headers=headers,json=rows[i:i+50],params={"on_conflict":"reference"},timeout=30)
            if r.status_code in (200,201,204): ok+=len(rows[i:i+50])
        except: pass
    return ok>0

def _sb_patch(ref,data):
    if not SUPABASE_URL: return False
    try:
        h=_sb_headers(); h["Prefer"]="return=minimal"
        r=requests.patch(f"{SUPABASE_URL}/rest/v1/{TENDERS_TABLE}?reference=eq.{ref}",headers=h,json=data,timeout=60)
        return r.status_code in (200,204)
    except: return False

def _sb_get_refs():
    refs=set()
    try:
        for t in _sb_get(TENDERS_TABLE,{"select":"reference","limit":"10000"}):
            if t.get("reference"): refs.add(t["reference"])
    except: pass
    return refs

def _sb_upload_zip(zip_content,tender_ref):
    if not SUPABASE_URL or len(zip_content)>50*1024*1024: return None
    try:
        safe_ref=tender_ref.replace("/","_")
        r=requests.post(f"{SUPABASE_URL}/storage/v1/object/zip_files_tenders/{safe_ref}.zip",headers={"apikey":SUPABASE_KEY,"Authorization":f"Bearer {SUPABASE_KEY}","Content-Type":"application/zip","x-upsert":"true"},data=zip_content,timeout=120)
        if r.status_code in (200,201): return f"{SUPABASE_URL}/storage/v1/object/public/zip_files_tenders/{safe_ref}.zip"
    except: pass
    return None

def parse_deadline(s):
    if not s: return None
    try:
        for fmt in ("%d/%m/%Y %H:%M","%d/%m/%Y"):
            try: return datetime.strptime(re.sub(r'[^\d/:\s]','',s).strip()[:16],fmt)
            except: continue
    except: pass
    return None

def parse_date(s):
    """Parse une date au format jj/mm/aaaa"""
    if not s: return None
    try:
        for fmt in ("%d/%m/%Y","%d-%m-%Y","%Y-%m-%d"):
            try: return datetime.strptime(s.strip()[:10],fmt)
            except: continue
    except: pass
    return None

def is_cw_related(title,desc,acheteur=""):
    t=f"{title} {desc} {acheteur}".lower()
    for a,b in [('é','e'),('è','e'),('ê','e'),('à','a'),('â','a'),('ù','u'),('û','u'),('ô','o'),('î','i'),('ç','c')]: t=t.replace(a,b)
    for e in STRICT_EXCLUSIONS:
        if e in t: return False
    return any(k in t for k in STRONG_KEYWORDS)

def compute_score(title,desc,deadline,acheteur=""):
    t=f"{title} {desc} {acheteur}".lower()
    for a,b in [('é','e'),('è','e'),('ê','e'),('à','a'),('â','a'),('ù','u'),('û','u'),('ô','o'),('î','i'),('ç','c')]: t=t.replace(a,b)
    sh=[k for k in STRONG_KEYWORDS if k in t]
    if not sh: return 0
    mh=[k for k in MEDIUM_KEYWORDS if k in t]
    base=len(sh)*10+len(mh)*3
    dl=parse_deadline(deadline); ds=5
    if dl:
        d=(dl-datetime.now()).days
        if d<0: ds=-10
        elif d<=7: ds=3
        elif d<=14: ds=6
        elif d<=30: ds=9
        else: ds=12
    cb=8 if any(c in t for c in ["onee","onep","onas","amendis","commune","province"]) else 3
    return max(0,min(100,base+ds+cb))

def _extract_row(row, page_url, existing_refs, time_window_start, time_window_end):
    """Extrait les données d'une ligne avec filtrage par période"""
    try:
        ref=(row.select_one("input[name*='refCons']") or {}).get("value","")
        rs=row.select_one("span.ref"); rv=rs.get_text(strip=True) if rs else ""
        ot=""; od=row.select_one("div[id*='panelBlocObjet']")
        if od: ot=re.sub(r'^Objet\s*:\s*','',od.get_text(strip=True)).strip()
        ac=""; ad=row.select_one("div[id*='panelBlocDenomination']")
        if ad: ac=re.sub(r'^Acheteur\s+public\s*:\s*','',ad.get_text(strip=True)).strip()
        ct=""; cd=row.select_one("div[id*='panelBlocCategorie']")
        if cd: ct=cd.get_text(strip=True)
        dp=""; td=row.select_one("td.col-90")
        if td:
            for d in td.find_all("div"):
                t=d.get_text(strip=True)
                if re.match(r'\d{2}/\d{2}/\d{4}',t): dp=t; break
        dl_str=""; dl_parsed=None; dl_div=row.select_one("div.cloture-line")
        if dl_div:
            dl_str=dl_div.get_text(separator=' ',strip=True)
            dl_parsed=parse_deadline(dl_str)
            if dl_parsed: dl_parsed=dl_parsed.isoformat()
        if dl_parsed and parse_deadline(dl_str) and parse_deadline(dl_str)<datetime.now(): return None,"deadline_passed"
        re_elec=None
        if row.select_one("img[src*='reponse-elec-oblig']"): re_elec=True
        elif row.select_one("img[src*='reponse-elec-non']"): re_elec=False
        pr=""; pd=row.select_one("div[id*='type_procedure']")
        if pd: pr=pd.get_text(strip=True)
        le=""; ld=row.select_one("div[id*='panelBlocLieuxExec']")
        if ld: le=re.sub(r'\s+',' ',ld.get_text(strip=True)).strip()
        detail_url=""; at=row.select_one("td.actions")
        if at:
            lk=at.select_one("a[href*='DetailConsultation']")
            if lk:
                h=lk.get("href","")
                detail_url=f"{BASE_URL}/{h}" if h.startswith("?") else urljoin(BASE_URL,h)
        title=ot or f"{rv or ref} - {ct}"
        if len(title)<10: return None,"title_too_short"
        if not is_cw_related(title,f"{ct} {pr} {le}",ac): return None,"not_related"
        fr=rv or ref
        if fr and fr in existing_refs: return None,"already_in_db"
        
        # Vérification de la date de publication
        dpp=None
        pub_date = None
        if dp:
            pub_date = parse_date(dp)
            if pub_date:
                dpp = pub_date.date().isoformat()
                # Vérifier si la date est dans la fenêtre temporelle
                if not (time_window_start <= pub_date < time_window_end):
                    return None, "outside_time_window"
        
        # Si pas de date de publication trouvée, on ignore (hors période)
        if not dpp:
            return None, "outside_time_window"
            
        score=compute_score(ot or "",f"{ct} {pr} {le}",dl_str,ac)
        return {"reference":fr or str(uuid.uuid4()),"procedure":pr[:100] if pr else None,"categorie":ct[:200] if ct else None,"date_publication":dpp,"objet":ot[:500] if ot else None,"acheteur_public":ac[:300] if ac else None,"lieu_execution":le[:300] if le else None,"date_limite_remise_plis":dl_parsed,"reponse_electronique_obligatoire":re_elec,"source_url":detail_url or page_url,"dce_zip_url":None,"status":"new","qualification_status":"unseen","seen":False,"relevance_score":score},"success"
    except Exception as e:
        return None,"error"

def download_dce_sync(page,detail_url,tender_ref):
    try:
        page.goto(detail_url,wait_until="domcontentloaded",timeout=30000); page.wait_for_timeout(5000)
        clicked=False
        for sel in ["a:has-text('Dossier de Consultation')","a:has-text('Telecharger le DCE')","a:has-text('Telecharger')","a[href*='TelechargerDCE']"]:
            try:
                for el in page.query_selector_all(sel):
                    if el.is_visible(): el.click(); clicked=True; break
                if clicked: break
            except: continue
        if not clicked: return None
        page.wait_for_timeout(5000)
        for sel,val in [("#ctl0_CONTENU_PAGE_EntrepriseFormulaireDemande_nom",CRYSTAL_FORM_DATA["nom"]),("#ctl0_CONTENU_PAGE_EntrepriseFormulaireDemande_prenom",CRYSTAL_FORM_DATA["prenom"]),("#ctl0_CONTENU_PAGE_EntrepriseFormulaireDemande_email",CRYSTAL_FORM_DATA["email"])]:
            try:
                f=page.query_selector(sel)
                if f and f.is_visible(): f.fill(val)
            except: pass
        try:
            cb=page.query_selector("#ctl0_CONTENU_PAGE_EntrepriseFormulaireDemande_accepterConditions")
            if cb and not cb.is_checked(): cb.click()
        except: pass
        page.wait_for_timeout(1000)
        vb=page.query_selector("#ctl0_CONTENU_PAGE_validateButton")
        if not vb: return None
        vb.click(); page.wait_for_timeout(5000)
        db=None
        for sel in ["#ctl0_CONTENU_PAGE_EntrepriseDownloadDce_completeDownload","a.bouton-telecharger-long230"]:
            try:
                b=page.query_selector(sel)
                if b and b.is_visible(): db=b; break
            except: continue
        if not db: return None
        with page.expect_download(timeout=300000) as di: db.click()
        dl=di.value
        try: zp=dl.path()
        except: return None
        if not zp: return None
        with open(zp,'rb') as f: zc=f.read()
        if not zc or len(zc)<100: return None
        sup_url=_sb_upload_zip(zc,tender_ref)
        if sup_url: return {"dce_zip_url":sup_url,"zip_content":zc}
        return None
    except: return None

def extract_all_from_zip(tender_ref,zip_content):
    tmp_path=None
    try:
        with tempfile.NamedTemporaryFile(suffix='.zip',delete=False) as tmp:
            tmp.write(zip_content); tmp_path=tmp.name
        avis_ok = _do_extract_avis(tender_ref,tmp_path)
        rc_ok = _do_extract_rc(tender_ref,tmp_path)
        bp_ok = _do_extract_bp(tender_ref,tmp_path)
        if avis_ok: scan_stats["avis_extracted"] += 1
        if rc_ok: scan_stats["rc_extracted"] += 1
        if bp_ok: scan_stats["bp_extracted"] += 1
        return {"avis": avis_ok, "rc": rc_ok, "bp": bp_ok}
    except: return {"avis": False, "rc": False, "bp": False}
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try: os.unlink(tmp_path)
            except: pass

def _load_module(name,rel_path):
    mp=Path(__file__).resolve().parent/rel_path
    if not mp.exists(): return None
    try:
        spec=importlib.util.spec_from_file_location(name,mp)
        mod=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except: return None

def _do_extract_avis(tender_ref,zip_path):
    mod=_load_module('avis_ext','document/00_avis_Extraction.py')
    result={}
    if mod:
        try:
            with open(zip_path,'rb') as f: zb=f.read()
            files=mod.extract_files_from_zip(zb)
            if files:
                for fd in files[:3]:
                    try:
                        r=mod.process_avis_file(fd["filename"],fd["file_bytes"])
                        if r.get("success") and r.get("avis_fields"):
                            fs=r["avis_fields"]
                            if fs.get("Estimation (DHS TTC)"): result["avis_estimation_ttc"]=fs["Estimation (DHS TTC)"]
                            if fs.get("Caution Provisoire"): result["avis_caution_dhs"]=fs["Caution Provisoire"]
                            if fs.get("Date et Heure Visite des Lieux"): result["avis_visite_lieux"]=fs["Date et Heure Visite des Lieux"]
                    except: pass
        except: pass
    if not result: result=_avis_fallback(zip_path)
    if result:
        _sb_patch(tender_ref,result)
        return True
    return False

def _avis_fallback(zip_path):
    try:
        with zipfile.ZipFile(zip_path) as zf:
            all_text=""
            for fn in zf.namelist():
                if fn.endswith('/'): continue
                try:
                    c=zf.read(fn)
                    if fn.lower().endswith('.pdf'):
                        try:
                            import fitz; doc=fitz.open(stream=c,filetype="pdf")
                            all_text+="\n".join([p.get_text() for p in doc]); doc.close()
                        except: all_text+=c.decode('latin-1',errors='ignore')
                    elif fn.lower().endswith(('.docx','.doc')):
                        try:
                            from docx import Document
                            doc=Document(io.BytesIO(c))
                            all_text+="\n".join([p.text for p in doc.paragraphs])
                        except: all_text+=c.decode('latin-1',errors='ignore')
                    else:
                        try: all_text+=c.decode('utf-8',errors='ignore')+"\n"
                        except: pass
                except: pass
        if not all_text.strip(): return {}
        r={}
        for pat in [r"estimation[\s\w]{0,60}?:?\s*\(?([\d]{1,3}(?:[.\s]\d{3})*(?:,\d{2})?)\)?\s*(?:DH|DHS)",r"montant\s+(?:total|estim[ée])[\s\w]{0,40}?:?\s*([\d]{1,3}(?:[.\s]\d{3})*(?:,\d{2})?)"]:
            m=re.search(pat,all_text,re.IGNORECASE)
            if m:
                try:
                    v=float(m.group(1).replace(' ','').replace(',','.'))
                    if v>100: r["avis_estimation_ttc"]=f"{v:,.0f} DHS".replace(',',' '); break
                except: pass
        return r
    except: return {}

def _do_extract_rc(tender_ref,zip_path):
    mod=_load_module('rc_ext','document/00_rc_Extraction.py')
    if not mod: return False
    try:
        with open(zip_path,'rb') as f: zb=f.read()
        rc_files=[]
        with zipfile.ZipFile(io.BytesIO(zb)) as zf:
            for fn in zf.namelist():
                if fn.endswith('/'): continue
                if mod.is_rc_file(fn) and mod.is_supported_format(fn):
                    rc_files.append({"filename":Path(fn).name,"file_bytes":zf.read(fn)})
        if not rc_files: return False
        results=[]
        for rc in rc_files:
            try:
                r=mod.process_rc_file(rc["filename"],rc["file_bytes"])
                if r and "error" not in r: results.append(r)
            except: pass
        if results:
            mod.save_rc_extraction_to_supabase(tender_ref,results)
            return True
        return False
    except: return False

def _do_extract_bp(tender_ref,zip_path):
    mod=_load_module('bp_ext','document/BP_Extractor.py')
    if not mod: return False
    try:
        with open(zip_path,'rb') as f: zb=f.read()
        bp_files=mod.extract_files_from_zip(zb)
        if not bp_files: return False
        best,max_items=None,0
        for fd in bp_files:
            try:
                r=mod.process_bp_file(fd["filename"],fd["file_bytes"])
                if r.get("success") and r.get("items_count",0)>max_items: max_items=r["items_count"]; best=r
            except: pass
        if best:
            bp_result=best["bp_result"]
            mod.save_bp_to_supabase(tender_ref,bp_result,best["filename"])
            return True
        return False
    except: return False

def navigate_to_results(page):
    try:
        logger.info(f"  🌐 Connexion au site des marchés publics...")
        page.goto(SEARCH_URL, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(5000)
        try:
            page.click("#ctl0_CONTENU_PAGE_AdvancedSearch_lancerRecherche", timeout=15000)
        except:
            page.evaluate("document.querySelector('form').submit()")
        page.wait_for_timeout(5000)
        try:
            page.wait_for_selector("tr:has(td.col-450)", timeout=45000)
            logger.info(f"  ✅ Site atteint avec succès")
            return True
        except:
            logger.info(f"  ❌ Erreur: Impossible de charger les résultats")
            return False
    except Exception as e:
        logger.info(f"  ❌ Erreur de connexion: {e}")
        return False

def navigate_to_page(page,page_num):
    if page_num==1: return True
    try:
        page.fill("#ctl0_CONTENU_PAGE_resultSearch_numPageTop",str(page_num)); page.wait_for_timeout(1000)
        page.press("#ctl0_CONTENU_PAGE_resultSearch_numPageTop","Enter"); page.wait_for_timeout(8000)
        try: page.wait_for_selector("tr:has(td.col-450)",timeout=30000); return True
        except: return False
    except: return False

# ═══════════════ AFFICHAGE ═══════════════

def print_banner():
    """Affiche la bannière de démarrage"""
    logger.info(f"""
╔════════════════════════════════════════════════════════════════════════════════╗
║                                                                                ║
║  {ICON_START} CRYSTALWATER - SCAN QUOTIDIEN DES APPELS D'OFFRES                ║
║                                                                                ║
║  📅 {datetime.now().strftime('%A %d %B %Y %H:%M:%S')}                          ║
║                                                                                ║
╚════════════════════════════════════════════════════════════════════════════════╝
""")

def print_tender_compact(tender, index, extract_status=""):
    """Affiche un AO sur une ligne avec statut d'extraction"""
    objet = (tender.get("objet", "") or "")[:75]
    score = tender.get("relevance_score", 0)
    stars = "⭐" * min(5, score // 20)
    
    deadline = tender.get("date_limite_remise_plis", "")
    dl_disp = ""
    if deadline:
        try:
            d = datetime.fromisoformat(deadline.replace('Z', '+00:00'))
            days = (d - datetime.now()).days
            dl_disp = f"⏰ {days}j" if days >= 0 else "⏰ EXP"
        except:
            dl_disp = ""
    
    pub_date = tender.get("date_publication", "")
    pub_disp = f"📅 {pub_date}" if pub_date else ""
    
    logger.info(f"  #{index:<4} {ICON_AO} {objet:<70} {stars} {score:>3}%  {dl_disp:<10} {pub_disp:<12} {extract_status}")

def print_page_header(page_num, total_pages, start_time, end_time):
    """Affiche l'en-tête d'une page"""
    logger.info(f"\n{'─'*110}")
    logger.info(f"  {ICON_PAGE} PAGE {page_num}/{total_pages}  |  Période: {start_time.strftime('%d/%m/%Y %H:%M')} → {end_time.strftime('%d/%m/%Y %H:%M')}")
    logger.info(f"{'─'*110}")

def print_page_footer(page_num, rows, new_count, skipped):
    """Affiche le résumé d'une page avec les raisons des skip"""
    total_skipped = sum(skipped.values())
    logger.info(f"  {'─'*90}")
    logger.info(f"  📊 Page {page_num}: {rows} lignes analysées | {new_count} nouveaux AO | {total_skipped} ignorés")
    if total_skipped > 0:
        skip_details = []
        for reason, count in skipped.items():
            if count > 0:
                label = SKIP_REASONS.get(reason, reason)
                skip_details.append(f"{label}: {count}")
        logger.info(f"     {ICON_SKIP} Raisons: {', '.join(skip_details)}")
    logger.info(f"  {'─'*90}")

def print_progress():
    """Affiche la progression du scan en temps réel"""
    elapsed = (datetime.now() - scan_stats["start_time"]).total_seconds() if scan_stats["start_time"] else 0
    h, m, s = int(elapsed // 3600), int((elapsed % 3600) // 60), int(elapsed % 60)
    
    logger.info(f"\n  {ICON_PROGRESS} PROGRESSION DU SCAN")
    logger.info(f"  {'─'*50}")
    logger.info(f"  📄 Pages: {scan_stats['pages_scanned']}/{scan_stats['total_pages']}")
    logger.info(f"  📋 Nouveaux AO: {scan_stats['new_tenders']}")
    logger.info(f"  📥 DCE téléchargés: {scan_stats['dce_downloaded']}")
    logger.info(f"  ⏱️  Temps écoulé: {h}h {m}m {s}s")
    logger.info(f"  {'─'*50}")

def print_final_summary(start_time, end_time):
    """Affiche le résumé final"""
    elapsed = (scan_stats["end_time"] - scan_stats["start_time"]).total_seconds() if scan_stats["end_time"] and scan_stats["start_time"] else 0
    h, m, s = int(elapsed // 3600), int((elapsed % 3600) // 60), int(elapsed % 60)
    total_skipped = sum(scan_stats["skipped"].values())
    
    logger.info(f"""
╔════════════════════════════════════════════════════════════════════════════════╗
║  {ICON_FINISH} SCAN QUOTIDIEN TERMINÉ AVEC SUCCÈS                               ║
╚════════════════════════════════════════════════════════════════════════════════╝

  📅 Période scannée    : {start_time.strftime('%d/%m/%Y %H:%M')} → {end_time.strftime('%d/%m/%Y %H:%M')}
  
  📊 STATISTIQUES DÉTAILLÉES:
  {'─'*50}
  📄 Pages scannées     : {scan_stats['pages_scanned']}/{scan_stats['total_pages']}
  📋 Nouveaux AO        : {scan_stats['new_tenders']}
  📥 DCE téléchargés    : {scan_stats['dce_downloaded']}
  📦 Avis extraits      : {scan_stats['avis_extracted']}
  📜 RC extraits        : {scan_stats['rc_extracted']}
  📊 BP extraits        : {scan_stats['bp_extracted']}
  
  {ICON_SKIP} AO ignorés        : {total_skipped}""")
    
    if total_skipped > 0:
        for reason, count in scan_stats["skipped"].items():
            if count > 0:
                label = SKIP_REASONS.get(reason, reason)
                logger.info(f"     └─ {label}: {count}")
    
    logger.info(f"""
  ⏱️  Durée totale       : {h}h {m}m {s}s
  🏁 Fin du scan        : {scan_stats['end_time'].strftime('%Y-%m-%d %H:%M:%S') if scan_stats['end_time'] else 'N/A'}
  
{'═'*70}
""")

# ═══════════════ SCAN QUOTIDIEN ═══════════════

def run_daily_scan():
    """Exécute le scan quotidien des AO publiés entre 6h hier et 6h aujourd'hui"""
    
    # Afficher la bannière de démarrage
    print_banner()
    
    # Déterminer la fenêtre temporelle
    start_time, end_time = get_daily_time_window()
    
    # Réinitialiser les statistiques
    scan_stats["start_time"] = datetime.now()
    scan_stats["end_time"] = None
    scan_stats["skipped"] = {"already_in_db": 0, "not_related": 0, "deadline_passed": 0, "title_too_short": 0, "outside_time_window": 0, "error": 0}
    scan_stats["pages_scanned"] = 0
    scan_stats["new_tenders"] = 0
    scan_stats["dce_downloaded"] = 0
    scan_stats["dce_failed"] = 0
    scan_stats["avis_extracted"] = 0
    scan_stats["rc_extracted"] = 0
    scan_stats["bp_extracted"] = 0
    
    logger.info(f"""
  📋 CONFIGURATION DU SCAN:
  {'─'*50}
  📅 Période: {start_time.strftime('%d/%m/%Y %H:%M')} → {end_time.strftime('%d/%m/%Y %H:%M')}
  ⏱️  Début: {scan_stats['start_time'].strftime('%Y-%m-%d %H:%M:%S')}
  📄 Pages max: {MAX_PAGES_PER_DAY}
  🎯 Filtre: Mots-clés CrystalWater
  {'─'*50}
""")
    
    existing_refs = _sb_get_refs()
    logger.info(f"  🗄️  {len(existing_refs)} AO déjà en base\n")
    
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
        context = browser.new_context(viewport={"width": 1366, "height": 768}, accept_downloads=True)
        page = context.new_page()
        
        if not navigate_to_results(page):
            logger.info(f"  ❌ Impossible d'accéder au site. Arrêt.")
            browser.close()
            return
        
        # Récupérer le nombre total de pages
        total_pages = MAX_PAGES_PER_DAY
        try:
            nb = page.query_selector("#ctl0_CONTENU_PAGE_resultSearch_nombrePageTop")
            if nb: 
                total_pages = min(int(nb.inner_text().strip()), MAX_PAGES_PER_DAY)
        except: pass
        
        scan_stats["total_pages"] = total_pages
        logger.info(f"  📚 {total_pages} pages disponibles à scanner\n")
        logger.info(f"  {ICON_SCAN} LANCEMENT DU SCAN...\n")
        
        dce_page = context.new_page()
        found_any = False
        page_counter = 0
        
        for page_num in range(1, total_pages + 1):
            if page_num > 1:
                if not navigate_to_page(page, page_num):
                    logger.info(f"  ⚠️ Page {page_num} inaccessible, arrêt du scan.")
                    break
                time.sleep(1)
            
            rows = BeautifulSoup(page.content(), "html.parser").select("tr:has(td.col-450)")
            if not rows:
                logger.info(f"  📄 Page {page_num}: vide, fin des résultats.")
                break
            
            scan_stats["pages_scanned"] += 1
            scan_stats["rows_checked"] += len(rows)
            page_counter += 1
            
            page_new = []
            page_skipped = {"already_in_db": 0, "not_related": 0, "deadline_passed": 0, "title_too_short": 0, "outside_time_window": 0, "error": 0}
            
            for row in rows:
                result, status = _extract_row(row, page.url, existing_refs, start_time, end_time)
                if result is None:
                    if status in page_skipped:
                        page_skipped[status] += 1
                        scan_stats["skipped"][status] += 1
                    continue
                page_new.append(result)
                existing_refs.add(result.get("reference", ""))
            
            if page_new:
                found_any = True
                print_page_header(page_num, total_pages, start_time, end_time)
            else:
                # Afficher quand même si des AO ont été skipés
                total_skipped = sum(page_skipped.values())
                if total_skipped > 0:
                    print_page_header(page_num, total_pages, start_time, end_time)
                    logger.info(f"     Tous ignorés ({total_skipped} AO)")
            
            for i, tender in enumerate(page_new, 1):
                scan_stats["new_tenders"] += 1
                
                # Télécharger DCE
                dce_status = ""
                extract_status = ""
                detail_url = tender.get("source_url", "")
                
                if detail_url:
                    dce_result = download_dce_sync(dce_page, detail_url, tender["reference"])
                    if dce_result and dce_result.get("dce_zip_url"):
                        tender["dce_zip_url"] = dce_result["dce_zip_url"]
                        _sb_patch(tender["reference"], {"dce_zip_url": dce_result["dce_zip_url"]})
                        scan_stats["dce_downloaded"] += 1
                        dce_status = "📥"
                        
                        # Extraction
                        if dce_result.get("zip_content"):
                            ext = extract_all_from_zip(tender["reference"], dce_result["zip_content"])
                            parts = []
                            if ext.get("avis"): parts.append("Avis")
                            if ext.get("rc"): parts.append("RC")
                            if ext.get("bp"): parts.append("BP")
                            extract_status = f"{ICON_EXTRACT} {', '.join(parts)}" if parts else f"{ICON_EXTRACT} —"
                        else:
                            extract_status = ""
                    else:
                        scan_stats["dce_failed"] += 1
                        dce_status = "⚠️"
                else:
                    dce_status = "—"
                
                # Sauvegarder
                _sb_upsert([tender])
                
                # Afficher
                status_combo = f"{dce_status} {extract_status}".strip()
                print_tender_compact(tender, scan_stats["new_tenders"], status_combo)
            
            if page_new or sum(page_skipped.values()) > 0:
                print_page_footer(page_num, len(rows), len(page_new), page_skipped)
            
            # Afficher la progression toutes les 5 pages
            if page_num % 5 == 0:
                print_progress()
            
            # Si on a atteint la fin des résultats
            if not rows or len(rows) < 10:
                break
        
        dce_page.close()
        browser.close()
    
    # Enregistrer la fin du scan
    scan_stats["end_time"] = datetime.now()
    
    if not found_any:
        logger.info(f"\n  {ICON_WARN} Aucun nouvel AO trouvé dans la période.")
    
    print_final_summary(start_time, end_time)

# ═══════════════ FONCTIONS API ═══════════════

def load_tenders(status_filter=None):
    params={"order":"relevance_score.desc","limit":"10000"}
    if status_filter: params["status"]=f"eq.{status_filter}"
    return _sb_get(TENDERS_TABLE,params)

def load_suppliers(status_filter=None):
    params={"order":"reference","limit":"10000"}
    if status_filter: params["status"]=f"eq.{status_filter}"
    return _sb_get("suppliers",params)

def load_sectors(status_filter=None):
    params={"order":"reference","limit":"10000"}
    if status_filter: params["status"]=f"eq.{status_filter}"
    return _sb_get("sectors",params)

def update_tender_status(i,s): return _sb_patch(i,{"status":s})

def update_supplier_status(i,s):
    try:
        r=requests.patch(f"{SUPABASE_URL}/rest/v1/suppliers?reference=eq.{i}",headers=_sb_headers(),json={"status":s},timeout=60)
        return r.status_code in (200,204)
    except: return False

def update_sector_status(i,s):
    try:
        r=requests.patch(f"{SUPABASE_URL}/rest/v1/sectors?reference=eq.{i}",headers=_sb_headers(),json={"status":s},timeout=60)
        return r.status_code in (200,204)
    except: return False

def generate_email(tender,**kwargs):
    body=f"Madame, Monsieur,\n\n{kwargs.get('sender_name','CrystalWater Team')}\n"
    body+=f"AO: {tender.get('objet','')}\nRef: {tender.get('reference','')}\n"
    return {"subject":f"CrystalWater - {tender.get('objet','')[:80]}","body":body}

def send_email_via_resend(email_data):
    try:
        r=requests.post("https://api.resend.com/emails",headers={"Authorization":f"Bearer {os.getenv('RESEND_API_KEY','')}","Content-Type":"application/json"},json=email_data,timeout=15)
        return {"success":r.status_code in (200,201)}
    except: return {"success":False}

# ═══════════════ KEYWORDS ═══════════════
def get_active_keywords(): return _sb_get_keywords({"is_active": "eq.true", "order": "keyword.asc"})
def _sb_get_keywords(params=None):
    if not SUPABASE_URL: return []
    try:
        r=requests.get(f"{SUPABASE_URL}/rest/v1/tender_keywords",headers=_sb_headers(),params=params or {"order":"keyword.asc"},timeout=15)
        r.raise_for_status(); return r.json() or []
    except: return []
def _sb_add_keyword(data):
    if not SUPABASE_URL: return None
    try:
        r=requests.post(f"{SUPABASE_URL}/rest/v1/tender_keywords",headers={**_sb_headers(),"Prefer":"return=representation"},json=data,timeout=15)
        r.raise_for_status(); result=r.json(); return result[0] if result else None
    except: return None
def _sb_delete_keyword(kid):
    if not SUPABASE_URL: return False
    try:
        r=requests.delete(f"{SUPABASE_URL}/rest/v1/tender_keywords?id=eq.{kid}",headers=_sb_headers(),timeout=15)
        return r.status_code in (200,204)
    except: return False
def _sb_update_keyword(kid,data):
    if not SUPABASE_URL: return False
    try:
        r=requests.patch(f"{SUPABASE_URL}/rest/v1/tender_keywords?id=eq.{kid}",headers={**_sb_headers(),"Prefer":"return=minimal"},json=data,timeout=15)
        return r.status_code in (200,204)
    except: return False

# ═══════════════ SCORING ═══════════════
def _sb_get_criteria(params=None):
    if not SUPABASE_URL: return []
    try:
        r=requests.get(f"{SUPABASE_URL}/rest/v1/scoring_criteria",headers=_sb_headers(),params=params or {"order":"created_at"},timeout=15)
        r.raise_for_status(); return r.json() or []
    except: return []
def _sb_add_criteria(data):
    if not SUPABASE_URL: return None
    try:
        r=requests.post(f"{SUPABASE_URL}/rest/v1/scoring_criteria",headers={**_sb_headers(),"Prefer":"return=representation"},json=data,timeout=15)
        r.raise_for_status(); result=r.json(); return result[0] if result else None
    except: return None
def _sb_delete_criteria(cid):
    if not SUPABASE_URL: return False
    try:
        r=requests.delete(f"{SUPABASE_URL}/rest/v1/scoring_criteria?id=eq.{cid}",headers=_sb_headers(),timeout=15)
        return r.status_code in (200,204)
    except: return False
def _sb_get_tenders_2(params=None): return _sb_get(TENDERS_TABLE,params)
def _sb_patch_tenders_2(ref,data): return _sb_patch(ref,data)
def recalculate_all_scores():
    if not SUPABASE_URL: return 0
    try:
        criteria=_sb_get_criteria({"is_active":"eq.true"})
        if not criteria: return 0
        tenders=_sb_get(TENDERS_TABLE,{"select":"reference,objet,categorie,procedure,lieu_execution,acheteur_public,date_limite_remise_plis","limit":"10000"})
        updated=0
        for tender in tenders:
            score=0
            for c in criteria:
                fv=str(tender.get(c["field_name"],"")).lower(); cv=str(c["value"]).lower()
                if c["operator"]=="=" and cv in fv: score+=c["weight"]
                elif c["operator"]==">":
                    try:
                        if float(fv)>float(cv): score+=c["weight"]
                    except: pass
                elif c["operator"]==">=":
                    try:
                        if float(fv)>=float(cv): score+=c["weight"]
                    except: pass
                elif c["operator"]=="<":
                    try:
                        if float(fv)<float(cv): score+=c["weight"]
                    except: pass
                elif c["operator"]=="<=":
                    try:
                        if float(fv)<=float(cv): score+=c["weight"]
                    except: pass
            score=min(100,score)
            if _sb_patch(tender["reference"],{"relevance_score":score}): updated+=1
        return updated
    except: return 0

# Stubs
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

# ═══════════════ POINT D'ENTRÉE ═══════════════

if __name__ == "__main__":
    # Exécuter le scan quotidien
    run_daily_scan()