"""
tender_scanner.py — Africa Tenders Intelligence Module (v12.0 - FINAL)
========================================================================
CrystalWater — Traitement d'eau & Refroidissement industriel
https://crystalwater.ma/

PIPELINE SÉQUENTIEL:
1. Scan page → trouve les AO
2. Pour chaque AO: Télécharge DCE → Extrait Avis → Extrait RC → Extrait BP
3. Passe à l'AO suivant
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

ICON_SCAN = "🔍"; ICON_AO = "📋"; ICON_DCE = "📥"; ICON_ZIP = "📦"
ICON_OK = "✅"; ICON_ERR = "❌"; ICON_WARN = "⚠️"
ICON_AVIS = "📢"; ICON_RC = "📜"; ICON_BP = "📊"; ICON_DB = "🗄️"
ICON_CLOCK = "🕐"; ICON_PAGE = "📄"; ICON_STATS = "📈"
ICON_MONEY = "💰"; ICON_VISIT = "🏗️"; ICON_CAUTION = "🔒"
ICON_REF = "🔖"; ICON_SCORE = "⭐"; ICON_DEADLINE = "⏰"

BACKFILL_MONTHS = 3
POLL_INTERVAL = 300
MAX_PAGES_PER_POLL = 3

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "") or os.getenv("SUPABASE_KEY", "")
BASE_URL = "https://www.marchespublics.gov.ma"
SEARCH_URL = f"{BASE_URL}/index.php?page=entreprise.EntrepriseAdvancedSearch&AllCons&EnCours&domaineActivite=1.13"
TENDERS_TABLE = os.getenv("TENDERS_TABLE", "tenders_3")

CRYSTAL_FORM_DATA = {"nom":"Crystal","prenom":"Water","email":"marketing@crystalwater.ma","raisonSocial":"CrystalWater","address":"Adresse CrystalWater"}

logger = logging.getLogger("tender_scanner")
logger.setLevel(logging.INFO)
if not logger.handlers:
    ch = logging.StreamHandler(sys.stdout); ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter('%(message)s')); logger.addHandler(ch)
    if not os.path.exists('logs'): os.makedirs('logs')
    fh = logging.FileHandler(f'logs/scanner_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log', encoding='utf-8')
    fh.setLevel(logging.DEBUG); fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(fh)

scan_stats = {"pages_scanned":0,"total_pages":0,"rows_checked":0,"new_tenders":0,"dce_downloaded":0,"dce_failed":0,"avis_extracted":0,"rc_extracted":0,"bp_extracted":0,"start_time":None}

STRONG_KEYWORDS = ["station de traitement","station d'epuration","step","eau potable","aep","adduction d'eau","potabilisation","assainissement","eaux usees","eaux pluviales","reservoir d'eau","chateau d'eau","dessalement","osmose inverse","traitement des eaux","surpression","forage d'eau","captage","puits","vannes","clapets","debitmetre","pompe immergee","tour de refroidissement","refroidissement industriel","chloration","desinfection","filtration","lagunage","station de pompage","irrigation"]
MEDIUM_KEYWORDS = ["travaux","reseaux","canalisation","genie civil","fourniture","installation","rehabilitation","extension","construction","renouvellement","renforcement"]
STRICT_EXCLUSIONS = ["nettoyage des locaux","entretien des locaux","informatique","logiciel","site web","photovoltaique","solaire","dechets solides","gardiennage","restauration","cantine","fournitures de bureau","mobilier","climatiseurs","vehicule","voiture","ambulance"]

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

def _extract_row(row,page_url,existing_refs):
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
        dpp=None
        if dp:
            try:
                for f in ("%d/%m/%Y","%d-%m-%Y","%Y-%m-%d"):
                    try: dpp=datetime.strptime(dp.strip()[:10],f).date().isoformat(); break
                    except: continue
            except: pass
        score=compute_score(ot or "",f"{ct} {pr} {le}",dl_str,ac)
        return {"reference":fr or str(uuid.uuid4()),"procedure":pr[:100] if pr else None,"categorie":ct[:200] if ct else None,"date_publication":dpp,"objet":ot[:500] if ot else None,"acheteur_public":ac[:300] if ac else None,"lieu_execution":le[:300] if le else None,"date_limite_remise_plis":dl_parsed,"reponse_electronique_obligatoire":re_elec,"source_url":detail_url or page_url,"dce_zip_url":None,"status":"new","qualification_status":"unseen","seen":False,"relevance_score":score},"success"
    except Exception as e:
        logger.error(f"  {ICON_ERR} Extract error: {e}"); return None,"error"

def download_dce_sync(page,detail_url,tender_ref):
    start=time.time()
    logger.info(f"     {ICON_DCE} Téléchargement DCE...")
    try:
        page.goto(detail_url,wait_until="domcontentloaded",timeout=30000); page.wait_for_timeout(5000)
        clicked=False
        for sel in ["a:has-text('Dossier de Consultation')","a:has-text('Telecharger le DCE')","a:has-text('Telecharger')","a[href*='TelechargerDCE']"]:
            try:
                for el in page.query_selector_all(sel):
                    if el.is_visible(): el.click(); clicked=True; break
                if clicked: break
            except: continue
        if not clicked: logger.info(f"     {ICON_WARN} Aucun lien DCE trouvé"); return None
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
        if not vb: logger.info(f"     {ICON_ERR} Bouton validation introuvable"); return None
        vb.click(); page.wait_for_timeout(5000)
        db=None
        for sel in ["#ctl0_CONTENU_PAGE_EntrepriseDownloadDce_completeDownload","a.bouton-telecharger-long230"]:
            try:
                b=page.query_selector(sel)
                if b and b.is_visible(): db=b; break
            except: continue
        if not db: logger.info(f"     {ICON_ERR} Bouton download introuvable"); return None
        with page.expect_download(timeout=300000) as di: db.click()
        dl=di.value
        try: zp=dl.path()
        except: logger.info(f"     {ICON_WARN} Download annulé"); return None
        if not zp: logger.info(f"     {ICON_ERR} Chemin vide"); return None
        with open(zp,'rb') as f: zc=f.read()
        if not zc or len(zc)<100: logger.info(f"     {ICON_ERR} ZIP vide"); return None
        sup_url=_sb_upload_zip(zc,tender_ref)
        dt=time.time()-start
        if sup_url:
            logger.info(f"     {ICON_OK} DCE téléchargé ({dt:.1f}s, {len(zc)//1024} KB)")
            return {"dce_zip_url":sup_url,"zip_content":zc,"download_time":dt}
        else: logger.info(f"     {ICON_ERR} Échec upload Supabase"); return None
    except Exception as e: logger.error(f"     {ICON_ERR} DCE error: {e}"); return None

def extract_all_from_zip(tender_ref,zip_content):
    logger.info(f"  ┌─ EXTRACTION ─────────────────────────────")
    tmp_path=None
    try:
        with tempfile.NamedTemporaryFile(suffix='.zip',delete=False) as tmp:
            tmp.write(zip_content); tmp_path=tmp.name
        _do_extract_avis(tender_ref,tmp_path)
        _do_extract_rc(tender_ref,tmp_path)
        _do_extract_bp(tender_ref,tmp_path)
    except Exception as e: logger.error(f"  │ {ICON_ERR} Extraction error: {e}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try: os.unlink(tmp_path)
            except: pass
    logger.info(f"  └──────────────────────────────────────────")

def _load_module(name,rel_path):
    mp=Path(__file__).resolve().parent/rel_path
    if not mp.exists(): logger.info(f"  │ {ICON_WARN} Module {name} introuvable: {mp}"); return None
    try:
        spec=importlib.util.spec_from_file_location(name,mp)
        mod=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception as e: logger.error(f"  │ {ICON_ERR} Erreur chargement {name}: {e}"); return None

def _do_extract_avis(tender_ref,zip_path):
    logger.info(f"  │ {ICON_AVIS} Avis...")
    mod=_load_module('avis_ext','document/00_avis_Extraction.py')
    result={}
    if mod:
        try:
            with open(zip_path,'rb') as f: zb=f.read()
            files=mod.extract_files_from_zip(zb)
            if files:
                for fd in files[:3]:  # Limiter à 3 fichiers
                    try:
                        r=mod.process_avis_file(fd["filename"],fd["file_bytes"])
                        if r.get("success") and r.get("avis_fields"):
                            fs=r["avis_fields"]
                            if fs.get("Estimation (DHS TTC)"): result["avis_estimation_ttc"]=fs["Estimation (DHS TTC)"]
                            if fs.get("Caution Provisoire"): result["avis_caution_dhs"]=fs["Caution Provisoire"]
                            if fs.get("Date et Heure Visite des Lieux"): result["avis_visite_lieux"]=fs["Date et Heure Visite des Lieux"]
                    except: pass
        except Exception as e: logger.debug(f"  │   Avis module error: {e}")
    if not result: result=_avis_fallback(zip_path)
    if result:
        _sb_patch(tender_ref,result); scan_stats["avis_extracted"]+=1
        logger.info(f"  │   {ICON_OK} {len(result)} champ(s) extrait(s)")
        if result.get("avis_estimation_ttc"): logger.info(f"  │     {ICON_MONEY} Estimation: {result['avis_estimation_ttc']}")
        if result.get("avis_caution_dhs"): logger.info(f"  │     {ICON_CAUTION} Caution: {result['avis_caution_dhs']}")
        if result.get("avis_visite_lieux"): logger.info(f"  │     {ICON_VISIT} Visite: {result['avis_visite_lieux']}")
    else: logger.info(f"  │   {ICON_WARN} Aucune info Avis trouvée")

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
        for pat in [r"caution(?:nement)?\s+provisoire[\s\w]{0,40}?:?\s*\(?([\d]{1,3}(?:[.\s]\d{3})*(?:,\d{2})?)\)?"]:
            m=re.search(pat,all_text,re.IGNORECASE)
            if m:
                try:
                    v=float(m.group(1).replace(' ','').replace(',','.'))
                    if v>0: r["avis_caution_dhs"]=f"{v}%" if '%' in m.group(0) else f"{v:,.0f} DHS".replace(',',' '); break
                except: pass
        m=re.search(r'[Vv]isite\s*(?:des|de)\s*lieux.*?(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})',all_text,re.DOTALL)
        if m: r["avis_visite_lieux"]=m.group(1)
        if re.search(r"tenu[e]?\s+(de|d')\s+(faire|effectuer)\s+une\s+visite",all_text,re.IGNORECASE): r["visite_lieux_obligatoire"]=True
        return r
    except: return {}

def _do_extract_rc(tender_ref,zip_path):
    logger.info(f"  │ {ICON_RC} RC...")
    mod=_load_module('rc_ext','document/00_rc_Extraction.py')
    if not mod: logger.info(f"  │   {ICON_WARN} Module RC non disponible"); return
    try:
        with open(zip_path,'rb') as f: zb=f.read()
        rc_files=[]
        with zipfile.ZipFile(io.BytesIO(zb)) as zf:
            for fn in zf.namelist():
                if fn.endswith('/'): continue
                if mod.is_rc_file(fn) and mod.is_supported_format(fn):
                    rc_files.append({"filename":Path(fn).name,"file_bytes":zf.read(fn)})
        if not rc_files: logger.info(f"  │   {ICON_WARN} Aucun fichier RC trouvé"); return
        results=[]
        for rc in rc_files:
            try:
                r=mod.process_rc_file(rc["filename"],rc["file_bytes"])
                if r and "error" not in r: results.append(r)
            except: pass
        if results:
            mod.save_rc_extraction_to_supabase(tender_ref,results); scan_stats["rc_extracted"]+=1
            merged={}
            for r in results:
                if "error" in r: continue
                for k,v in r.items():
                    if k not in ['filename','text_length','extraction_diag','acheteur','method','is_scanned','total_pages']:
                        if v and not merged.get(k): merged[k]=v
            logger.info(f"  │   {ICON_OK} RC: {len(merged)} champs extraits")
            for k in ['attestations_demandees','nombre_references','classe_qualification','caution_provisoire']:
                if k in merged: logger.info(f"  │     {k}: {merged[k]}")
        else: logger.info(f"  │   {ICON_WARN} Aucune info RC extraite")
    except Exception as e: logger.error(f"  │   {ICON_ERR} RC error: {e}")

def _do_extract_bp(tender_ref,zip_path):
    logger.info(f"  │ {ICON_BP} BP...")
    mod=_load_module('bp_ext','document/BP_Extractor.py')
    if not mod: logger.info(f"  │   {ICON_WARN} Module BP non disponible"); return
    try:
        with open(zip_path,'rb') as f: zb=f.read()
        bp_files=mod.extract_files_from_zip(zb)
        if not bp_files: logger.info(f"  │   {ICON_WARN} Aucun fichier BP trouvé"); return
        best,max_items=None,0
        for fd in bp_files:
            try:
                r=mod.process_bp_file(fd["filename"],fd["file_bytes"])
                if r.get("success") and r.get("items_count",0)>max_items: max_items=r["items_count"]; best=r
            except: pass
        if best:
            bp_result=best["bp_result"]
            mod.save_bp_to_supabase(tender_ref,bp_result,best["filename"]); scan_stats["bp_extracted"]+=1
            dl=bp_result.get("document_level",{}); th=dl.get("Total_HT")
            logger.info(f"  │   {ICON_OK} BP: {max_items} items extraits")
            if th: logger.info(f"  │     {ICON_MONEY} Total HT: {th:,.2f} DHS")
        else: logger.info(f"  │   {ICON_WARN} Aucun item BP extrait")
    except Exception as e: logger.error(f"  │   {ICON_ERR} BP error: {e}")

def navigate_to_results(page):
    try:
        page.goto(SEARCH_URL,wait_until="networkidle",timeout=60000); page.wait_for_timeout(5000)
        try: page.click("#ctl0_CONTENU_PAGE_AdvancedSearch_lancerRecherche",timeout=15000)
        except: page.evaluate("document.querySelector('form').submit()")
        page.wait_for_timeout(5000)
        try: page.wait_for_selector("tr:has(td.col-450)",timeout=45000); return True
        except: return False
    except: return False

def navigate_to_page(page,page_num):
    if page_num==1: return True
    try:
        page.fill("#ctl0_CONTENU_PAGE_resultSearch_numPageTop",str(page_num)); page.wait_for_timeout(1000)
        page.press("#ctl0_CONTENU_PAGE_resultSearch_numPageTop","Enter"); page.wait_for_timeout(8000)
        try: page.wait_for_selector("tr:has(td.col-450)",timeout=30000); return True
        except: return False
    except: return False

def print_tender_header(tender,index):
    ref=tender.get("reference","N/A"); objet=(tender.get("objet","") or "")[:100]
    score=tender.get("relevance_score",0); acheteur=(tender.get("acheteur_public","") or "")[:60]
    deadline=tender.get("date_limite_remise_plis",""); dl_disp="N/A"
    if deadline:
        try:
            d=datetime.fromisoformat(deadline.replace('Z','+00:00'))
            days=(d-datetime.now()).days
            if days<0: dl_disp=f"EXPIRÉ"
            elif days<=7: dl_disp=f"{d.strftime('%d/%m/%Y')} ({days}j) 🔴"
            elif days<=30: dl_disp=f"{d.strftime('%d/%m/%Y')} ({days}j) 🟡"
            else: dl_disp=f"{d.strftime('%d/%m/%Y')} ({days}j) 🟢"
        except: dl_disp=deadline[:10]
    stars="⭐"*min(5,score//20)
    logger.info(f"\n  ╔{'═'*70}╗")
    logger.info(f"  ║ {ICON_AO} AO #{index}  |  {ICON_SCORE} {score}/100 {stars}  |  {ICON_REF} {ref}")
    logger.info(f"  ╠{'═'*70}╣")
    logger.info(f"  ║ 📝 {objet}")
    logger.info(f"  ║ 🏢 {acheteur}")
    logger.info(f"  ║ {ICON_DEADLINE} {dl_disp}")
    logger.info(f"  ╚{'═'*70}╝")

def print_page_summary(page_num,total_pages,rows,new_found,skipped):
    logger.info(f"\n  ┌─ {ICON_PAGE} PAGE {page_num}/{total_pages} ──────────────────────────────")
    logger.info(f"  │  Lignes: {rows}  |  {ICON_AO} Nouveaux AO: {new_found}  |  Ignorés: {sum(skipped.values())}")
    logger.info(f"  └{'─'*50}")

def print_scan_summary():
    e=(datetime.now()-scan_stats["start_time"]).total_seconds() if scan_stats["start_time"] else 0
    h,m,s=int(e//3600),int((e%3600)//60),int(e%60)
    logger.info(f"\n{'═'*70}")
    logger.info(f"  {ICON_STATS} RÉSUMÉ DU SCAN")
    logger.info(f"{'═'*70}")
    logger.info(f"  {ICON_PAGE} Pages: {scan_stats['pages_scanned']}/{scan_stats['total_pages']}")
    logger.info(f"  {ICON_AO} Nouveaux: {scan_stats['new_tenders']}")
    logger.info(f"  {ICON_ZIP} DCE: {scan_stats['dce_downloaded']}")
    logger.info(f"  {ICON_AVIS} Avis: {scan_stats['avis_extracted']} | {ICON_RC} RC: {scan_stats['rc_extracted']} | {ICON_BP} BP: {scan_stats['bp_extracted']}")
    logger.info(f"  {ICON_CLOCK} Durée: {h}h {m}m {s}s")
    logger.info(f"{'═'*70}")

def run_backfill():
    scan_stats["start_time"]=datetime.now()
    logger.info(f"\n{'═'*70}\n  {ICON_SCAN} BACKFILL - {BACKFILL_MONTHS} DERNIERS MOIS\n  {ICON_CLOCK} Début: {scan_stats['start_time'].strftime('%Y-%m-%d %H:%M:%S')}\n{'═'*70}")
    existing_refs=_sb_get_refs()
    logger.info(f"  {ICON_DB} {len(existing_refs)} AO déjà en base\n")
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
        context=browser.new_context(viewport={"width":1366,"height":768},accept_downloads=True)
        page=context.new_page()
        if not navigate_to_results(page): browser.close(); return
        total_pages=200
        try:
            nb=page.query_selector("#ctl0_CONTENU_PAGE_resultSearch_nombrePageTop")
            if nb: total_pages=int(nb.inner_text().strip())
        except: pass
        scan_stats["total_pages"]=total_pages
        logger.info(f"  {ICON_PAGE} Pages à scanner: {total_pages}\n")
        cutoff_date=datetime.now()-timedelta(days=BACKFILL_MONTHS*30)
        dce_page=context.new_page()
        for page_num in range(1,total_pages+1):
            if page_num>1:
                if not navigate_to_page(page,page_num): continue
                time.sleep(1)
            rows=BeautifulSoup(page.content(),"html.parser").select("tr:has(td.col-450)")
            if not rows: continue
            scan_stats["pages_scanned"]+=1; scan_stats["rows_checked"]+=len(rows)
            page_new=[]; page_skipped={"already_in_db":0,"not_related":0,"deadline_passed":0}
            for row in rows:
                result,status=_extract_row(row,page.url,existing_refs)
                if result is None:
                    if status in page_skipped: page_skipped[status]+=1
                    continue
                if result.get("date_publication"):
                    try:
                        if datetime.fromisoformat(result["date_publication"])<cutoff_date: continue
                    except: pass
                page_new.append(result); existing_refs.add(result.get("reference",""))
            if page_new: print_page_summary(page_num,total_pages,len(rows),len(page_new),page_skipped)
            for tender in page_new:
                scan_stats["new_tenders"]+=1; print_tender_header(tender,scan_stats["new_tenders"])
                _sb_upsert([tender])
                detail_url=tender.get("source_url","")
                if detail_url:
                    dce_result=download_dce_sync(dce_page,detail_url,tender["reference"])
                    if dce_result and dce_result.get("dce_zip_url"):
                        tender["dce_zip_url"]=dce_result["dce_zip_url"]
                        _sb_patch(tender["reference"],{"dce_zip_url":dce_result["dce_zip_url"]})
                        scan_stats["dce_downloaded"]+=1
                        if dce_result.get("zip_content"): extract_all_from_zip(tender["reference"],dce_result["zip_content"])
                    else: scan_stats["dce_failed"]+=1; logger.info(f"     {ICON_WARN} Pas de DCE disponible")
                else: logger.info(f"     {ICON_WARN} Pas d'URL de détail")
            if page_num%50==0:
                e=(datetime.now()-scan_stats["start_time"]).total_seconds()
                logger.info(f"\n  {ICON_STATS} Page {page_num}/{total_pages} | {scan_stats['new_tenders']} AO | {scan_stats['dce_downloaded']} DCE | {int(e//60)}min\n")
        dce_page.close(); browser.close()
    print_scan_summary()

class RealtimeScanner:
    def __init__(self):
        self.existing_refs=_sb_get_refs(); self.running=True
        self.poll_count=0; self.new_count=0; self.dce_count=0
        self.start_time=datetime.now()
        signal.signal(signal.SIGINT,self._handler); signal.signal(signal.SIGTERM,self._handler)
    def _handler(self,signum,frame): logger.info(f"\n  {ICON_SCAN} Arrêt..."); self.running=False
    def run(self):
        logger.info(f"\n{'═'*70}\n  {ICON_SCAN} SURVEILLANCE TEMPS RÉEL\n  Intervalle: {POLL_INTERVAL}s | {ICON_DB} {len(self.existing_refs)} en base\n{'═'*70}")
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
            context=browser.new_context(viewport={"width":1366,"height":768},accept_downloads=True)
            page=context.new_page(); dce_page=context.new_page()
            if not navigate_to_results(page): browser.close(); return
            while self.running:
                self.poll_count+=1; poll_start=datetime.now()
                logger.info(f"\n  {ICON_SCAN} POLL #{self.poll_count} - {poll_start.strftime('%H:%M:%S')}")
                poll_new=0
                try:
                    navigate_to_page(page,1)
                    for pg in range(1,MAX_PAGES_PER_POLL+1):
                        if pg>1:
                            if not navigate_to_page(page,pg): break
                            time.sleep(1)
                        rows=BeautifulSoup(page.content(),"html.parser").select("tr:has(td.col-450)")
                        page_new=[]
                        for row in rows:
                            result,_=_extract_row(row,page.url,self.existing_refs)
                            if result: page_new.append(result); self.existing_refs.add(result.get("reference",""))
                        if page_new:
                            logger.info(f"  {ICON_AO} Page {pg}: {len(page_new)} NOUVEAU(X) !")
                            for tender in page_new:
                                poll_new+=1; self.new_count+=1; print_tender_header(tender,self.new_count)
                                _sb_upsert([tender])
                                detail_url=tender.get("source_url","")
                                if detail_url:
                                    dce_result=download_dce_sync(dce_page,detail_url,tender["reference"])
                                    if dce_result and dce_result.get("dce_zip_url"):
                                        tender["dce_zip_url"]=dce_result["dce_zip_url"]
                                        _sb_patch(tender["reference"],{"dce_zip_url":dce_result["dce_zip_url"]})
                                        self.dce_count+=1
                                        if dce_result.get("zip_content"): extract_all_from_zip(tender["reference"],dce_result["zip_content"])
                    if poll_new==0: logger.info(f"  {ICON_OK} Aucun nouveau")
                    if self.poll_count%12==0: self.existing_refs=_sb_get_refs()
                except Exception as ex:
                    logger.error(f"  {ICON_ERR} Erreur: {ex}")
                    try: navigate_to_results(page)
                    except: pass
                if self.running:
                    wait=max(0,POLL_INTERVAL-(datetime.now()-poll_start).total_seconds())
                    logger.info(f"  {ICON_CLOCK} Prochain poll dans {int(wait)}s")
                    for _ in range(int(wait)):
                        if not self.running: break
                        time.sleep(1)
            dce_page.close(); browser.close()

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

def get_active_keywords(): return []
def _sb_get_keywords(params=None): return []
def _sb_add_keyword(data): return None
def _sb_delete_keyword(kid): return False
def _sb_update_keyword(kid,data): return False
def _sb_get_tenders_2(params=None): return _sb_get(TENDERS_TABLE,params)
def _sb_patch_tenders_2(ref,data): return _sb_patch(ref,data)
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