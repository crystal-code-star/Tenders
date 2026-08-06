"""
main.py  —  FastAPI Backend (v7.5 — BP Items Fix avec ___)
═══════════════════════════════════════════════════════════════════════════════
CrystalWater — Traitement d'eau & Refroidissement industriel
https://crystalwater.ma/
"""

import os, sys, threading, time, traceback, logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

# Change 1: Added warning logs when supabase_client is None
if SUPABASE_URL and SUPABASE_SERVICE_KEY:
    import supabase
    supabase_client = supabase.create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    print(f"✅ Supabase client created — URL: {SUPABASE_URL[:30]}...")
else:
    supabase_client = None
    print(f"❌ Supabase NOT configured — SUPABASE_URL={'set' if SUPABASE_URL else 'MISSING'}, SUPABASE_SERVICE_KEY={'set' if SUPABASE_SERVICE_KEY else 'MISSING'}")

logger = logging.getLogger("main")
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

SCANNER_AVAILABLE = False
try:
    from agents.tender_scanner import (
        run_backfill, RealtimeScanner, load_tenders, load_suppliers, load_sectors,
        update_tender_status, update_supplier_status, update_sector_status,
        generate_email, send_email_via_resend, get_active_keywords,
        _sb_get_keywords, _sb_add_keyword, _sb_delete_keyword, _sb_update_keyword,
        _sb_get_tenders_2, _sb_patch_tenders_2, recalculate_all_scores, _sb_get_refs,
    )
    SCANNER_AVAILABLE = True
    logger.info("✅ Scanner module loaded")
except ImportError as e:
    logger.warning(f"Scanner module not available: {e}")
    def load_tenders(s=None): return []
    def load_suppliers(s=None): return []
    def load_sectors(s=None): return []
    def update_tender_status(i,s): return False
    def update_supplier_status(i,s): return False
    def update_sector_status(i,s): return False
    def generate_email(t,**kw): return {}
    def send_email_via_resend(e): return {"success":False}
    def get_active_keywords(): return []
    def _sb_get_keywords(p=None): return []
    def _sb_add_keyword(d): return None
    def _sb_delete_keyword(k): return False
    def _sb_update_keyword(k,d): return False
    def _sb_get_tenders_2(p=None): return []
    def _sb_patch_tenders_2(r,d): return False
    def recalculate_all_scores(): return 0
    def _sb_get_refs(): return set()
    def run_backfill(): pass
    class RealtimeScanner:
        def run(self): pass

ZIP_VIEWER_AVAILABLE = False
try:
    from agents.zip_viewer import list_files_in_dce, preview_file_from_dce
    ZIP_VIEWER_AVAILABLE = True
except ImportError:
    pass

AUTH_AVAILABLE = False
try:
    from auth_routes import router as auth_router, get_current_user
    AUTH_AVAILABLE = True
except ImportError:
    async def get_current_user(request: Request = None):
        return {"id":"default","email":"admin@crystalwater.ma"}

app = FastAPI(title="CrystalWater Tenders API", version="7.5.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
if AUTH_AVAILABLE:
    app.include_router(auth_router)

_scanner_running = False
_scanner_status = {"is_running":False,"mode":"stopped","started_at":None,"backfill_completed":False,"realtime_active":False,"tenders_found":0,"dce_downloaded":0}

def start_scanner_automatically():
    global _scanner_running, _scanner_status
    if not SCANNER_AVAILABLE or _scanner_running:
        return
    logger.info("🚀 AUTO-STARTING SCANNER")
    _scanner_running = True
    _scanner_status["is_running"] = True
    _scanner_status["mode"] = "full"
    _scanner_status["started_at"] = datetime.now().isoformat()
    def run():
        try:
            existing = _sb_get_refs()
            logger.info(f"📊 {len(existing)} offres déjà en base")
            run_backfill()
            _scanner_status["backfill_completed"] = True
            _scanner_status["mode"] = "realtime"
            _scanner_status["realtime_active"] = True
            RealtimeScanner().run()
        except Exception as e:
            logger.error(f"Scanner error: {e}")
        finally:
            _scanner_status["is_running"] = False
            _scanner_status["realtime_active"] = False
            global _scanner_running
            _scanner_running = False
    threading.Thread(target=run, daemon=True).start()

@app.on_event("startup")
async def startup():
    threading.Timer(2.0, start_scanner_automatically).start()

@app.get("/")
def root():
    return {"message":"CrystalWater Tenders API v7.5","scanner":{"auto_start":True,"status":_scanner_status},"docs":"/docs"}

@app.get("/health")
def health():
    return {"status":"ok","version":"7.5.0","scanner_running":_scanner_running,"scanner_status":_scanner_status}

def _build_stats(items):
    t = len(items)
    return {
        "total":t,
        "unseen":len([i for i in items if i.get("qualification_status")=="unseen"]),
        "seen":len([i for i in items if i.get("qualification_status")=="seen"]),
        "preselected":len([i for i in items if i.get("qualification_status")=="preselected"]),
        "qualified":len([i for i in items if i.get("qualification_status")=="qualified"]),
        "high_priority":len([i for i in items if i.get("relevance_score",0)>=70]),
        "medium_priority":len([i for i in items if 45<=i.get("relevance_score",0)<70])
    }

@app.get("/tenders")
def get_tenders(status:Optional[str]=None, current_user=Depends(get_current_user)):
    try:
        tenders = load_tenders(status_filter=status) if status else load_tenders()
        return {"success":True,"total":len(tenders or []),"tenders":tenders or [],"stats":_build_stats(tenders or []),"scanner_status":_scanner_status}
    except Exception as e:
        return {"success":True,"total":0,"tenders":[],"stats":_build_stats([])}

@app.get("/tenders/preselected")
def get_preselected(current_user=Depends(get_current_user)):
    try:
        all_tenders = _sb_get_tenders_2({"order":"relevance_score.desc","limit":"10000"}) or []
        filtered = [t for t in all_tenders if t.get("qualification_status") in ["preselected","qualified"]]
        return {"success":True,"total":len(filtered),"tenders":filtered,"stats":_build_stats(filtered)}
    except:
        return {"success":True,"total":0,"tenders":[],"stats":_build_stats([])}

@app.put("/tenders/{tender_id:path}/status")
def set_status(tender_id:str, status:str="contacted", current_user=Depends(get_current_user)):
    if status not in ["new","contacted","ignored","archived"]:
        raise HTTPException(400)
    if update_tender_status(tender_id,status):
        return {"success":True}
    raise HTTPException(404)

@app.put("/tenders/{tender_id:path}/qualify")
def set_qualification(tender_id:str, status:str="preselected", current_user=Depends(get_current_user)):
    if status not in ["unseen","seen","preselected","qualified"]:
        raise HTTPException(400)
    if _sb_patch_tenders_2(tender_id,{"qualification_status":status,"seen":status!="unseen"}):
        return {"success":True}
    raise HTTPException(404)

@app.put("/tenders/{tender_id:path}/seen")
def mark_seen(tender_id:str, current_user=Depends(get_current_user)):
    if _sb_patch_tenders_2(tender_id,{"seen":True}):
        return {"success":True}
    raise HTTPException(404)

@app.post("/tenders/scan")
def scan_manual(current_user=Depends(get_current_user)):
    if _scanner_running:
        return {"success":False,"message":"Scanner already running"}
    start_scanner_automatically()
    return {"success":True}

# ═══════════════ KEYWORDS ═══════════════
class KeywordCreate(BaseModel):
    keyword:str=Field(...,min_length=1,max_length=255)
    category:str=Field(default="custom")
    is_active:bool=Field(default=True)

class KeywordUpdate(BaseModel):
    keyword:Optional[str]=None
    category:Optional[str]=None
    is_active:Optional[bool]=None

@app.get("/keywords")
def get_keywords(current_user=Depends(get_current_user)):
    return {"success":True,"keywords":_sb_get_keywords({"order":"keyword.asc"}),"total":len(_sb_get_keywords({"order":"keyword.asc"}))}

@app.get("/keywords/active")
def get_active_kw(current_user=Depends(get_current_user)):
    return {"success":True,"keywords":get_active_keywords()}

@app.post("/keywords")
def create_kw(req:KeywordCreate, current_user=Depends(get_current_user)):
    kw = req.keyword.strip().lower()
    if not kw:
        raise HTTPException(400)
    if _sb_get_keywords({"keyword":f"eq.{kw}"}):
        raise HTTPException(400,f"'{kw}' exists")
    r = _sb_add_keyword({"keyword":kw,"category":req.category,"is_active":req.is_active,"created_at":datetime.now().isoformat()})
    if r:
        return {"success":True,"keyword":r}
    raise HTTPException(500)

@app.delete("/keywords/{kid}")
def delete_kw(kid:int, current_user=Depends(get_current_user)):
    if _sb_delete_keyword(kid):
        return {"success":True}
    raise HTTPException(404)

@app.patch("/keywords/{kid}")
def update_kw(kid:int, req:KeywordUpdate, current_user=Depends(get_current_user)):
    data = {}
    if req.keyword is not None:
        data["keyword"] = req.keyword.strip().lower()
    if req.category is not None:
        data["category"] = req.category
    if req.is_active is not None:
        data["is_active"] = req.is_active
    if not data:
        raise HTTPException(400)
    data["updated_at"] = datetime.now().isoformat()
    if _sb_update_keyword(kid,data):
        return {"success":True}
    raise HTTPException(404)


# ═══════════════ SCORING CRITERIA ═══════════════
class ScoringCriteriaCreate(BaseModel):
    field_name: str = Field(..., min_length=1)
    operator: str = Field(..., min_length=1)
    value: str = Field(..., min_length=1)
    weight: int = Field(default=1, ge=1, le=100)

class ScoringCriteriaUpdate(BaseModel):
    field_name: Optional[str] = None
    operator: Optional[str] = None
    value: Optional[str] = None
    weight: Optional[int] = Field(None, ge=1, le=100)
    is_active: Optional[bool] = None

@app.get("/scoring-criteria")
def get_scoring_criteria(current_user=Depends(get_current_user)):
    """Récupère tous les critères de scoring"""
    if not supabase_client:
        return {"success": True, "criteria": []}
    
    try:
        response = supabase_client.table("scoring_criteria").select("*").order("created_at").execute()
        criteria = response.data if response.data else []
        return {"success": True, "criteria": criteria}
    except Exception as e:
        logger.error(f"❌ Error fetching scoring criteria: {e}")
        return {"success": True, "criteria": []}

@app.post("/scoring-criteria")
def create_scoring_criteria(req: ScoringCriteriaCreate, current_user=Depends(get_current_user)):
    """Ajoute un nouveau critère de scoring"""
    if not supabase_client:
        raise HTTPException(500, "Database not available")
    
    try:
        data = {
            "field_name": req.field_name,
            "operator": req.operator,
            "value": req.value,
            "weight": req.weight,
            "is_active": True,
            "created_at": datetime.now().isoformat()
        }
        response = supabase_client.table("scoring_criteria").insert(data).execute()
        
        # Recalculer les scores après ajout
        if SCANNER_AVAILABLE:
            threading.Thread(target=recalculate_all_scores, daemon=True).start()
        
        return {"success": True, "criteria": response.data[0] if response.data else None}
    except Exception as e:
        logger.error(f"❌ Error creating scoring criteria: {e}")
        raise HTTPException(500, str(e))

@app.patch("/scoring-criteria/{criteria_id}")
def update_scoring_criteria(criteria_id: int, req: ScoringCriteriaUpdate, current_user=Depends(get_current_user)):
    """Met à jour un critère de scoring"""
    if not supabase_client:
        raise HTTPException(500, "Database not available")
    
    try:
        data = {}
        if req.field_name is not None:
            data["field_name"] = req.field_name
        if req.operator is not None:
            data["operator"] = req.operator
        if req.value is not None:
            data["value"] = req.value
        if req.weight is not None:
            data["weight"] = req.weight
        if req.is_active is not None:
            data["is_active"] = req.is_active
        
        if not data:
            raise HTTPException(400, "No fields to update")
        
        data["updated_at"] = datetime.now().isoformat()
        
        response = supabase_client.table("scoring_criteria").update(data).eq("id", criteria_id).execute()
        
        # Recalculer les scores après modification
        if SCANNER_AVAILABLE:
            threading.Thread(target=recalculate_all_scores, daemon=True).start()
        
        return {"success": True, "criteria": response.data[0] if response.data else None}
    except Exception as e:
        logger.error(f"❌ Error updating scoring criteria: {e}")
        raise HTTPException(500, str(e))

@app.delete("/scoring-criteria/{criteria_id}")
def delete_scoring_criteria(criteria_id: int, current_user=Depends(get_current_user)):
    """Supprime un critère de scoring"""
    if not supabase_client:
        raise HTTPException(500, "Database not available")
    
    try:
        supabase_client.table("scoring_criteria").delete().eq("id", criteria_id).execute()
        
        # Recalculer les scores après suppression
        if SCANNER_AVAILABLE:
            threading.Thread(target=recalculate_all_scores, daemon=True).start()
        
        return {"success": True}
    except Exception as e:
        logger.error(f"❌ Error deleting scoring criteria: {e}")
        raise HTTPException(500, str(e))

@app.post("/scoring/recalculate")
def recalculate_scores(current_user=Depends(get_current_user)):
    """Force le recalcul de tous les scores"""
    if not SCANNER_AVAILABLE:
        raise HTTPException(500, "Scanner not available")
    
    try:
        count = recalculate_all_scores()
        return {"success": True, "tenders_updated": count}
    except Exception as e:
        logger.error(f"❌ Error recalculating scores: {e}")
        raise HTTPException(500, str(e))


        
# ═══════════════ BP ITEMS - CORRIGÉ AVEC ___ ═══════════════
@app.get("/tenders/{tender_id:path}/bp-items")
def get_bp_items(tender_id: str, current_user=Depends(get_current_user)):
    # ⚠️ Décoder la référence : remplacer ___ par /
    decoded_ref = tender_id.replace('___', '/')
    logger.info(f"🔍 BP items for: '{decoded_ref}'")
    
    # Change 2: Added logging when supabase_client is None
    if not supabase_client:
        logger.error("⚠️ supabase_client is None — cannot fetch BP items!")
        return {"success": True, "items": [], "total_items": 0, "summary": {"total_ht": 0, "total_qty": 0, "avg_price": 0}, "tender_reference": decoded_ref}
    
    try:
        response = supabase_client.table("tenders_3_bp_items").select("*").eq("tender_reference", decoded_ref).order("id").execute()
        items = response.data if response.data else []
        logger.info(f"  ✅ {len(items)} items found")
        
        total_ht = sum(float(item.get("total_ht", 0) or 0) for item in items)
        total_qty = sum(float(item.get("quantite", 0) or 0) for item in items)
        prices = [float(item.get("prix_unitaire_ht", 0) or 0) for item in items if (item.get("prix_unitaire_ht") and float(item.get("prix_unitaire_ht", 0) or 0) > 0)]
        avg_price = round(sum(prices) / len(prices), 2) if prices else 0
        
        return {
            "success": True,
            "items": items,
            "total_items": len(items),
            "summary": {"total_ht": round(total_ht, 2), "total_qty": round(total_qty, 2), "avg_price": avg_price},
            "tender_reference": decoded_ref
        }
    except Exception as e:
        logger.error(f"❌ BP items error: {e}")
        return {"success": True, "items": [], "total_items": 0, "summary": {"total_ht": 0, "total_qty": 0, "avg_price": 0}, "tender_reference": decoded_ref}

# ═══════════════ ZIP VIEWER ═══════════════
@app.get("/tenders/{tender_id:path}/files")
def get_files(tender_id:str):
    if ZIP_VIEWER_AVAILABLE:
        return list_files_in_dce(tender_id)
    return {"files":[],"error":"ZIP viewer not available"}

@app.get("/tenders/{tender_id:path}/preview/{file_path:path}")
def get_preview(tender_id:str, file_path:str):
    if ZIP_VIEWER_AVAILABLE:
        return preview_file_from_dce(tender_id, file_path)
    raise HTTPException(501)

# ═══════════════ MAIN ═══════════════
if __name__=="__main__":
    import uvicorn
    port = int(os.environ.get("PORT",8000))
    print(f"\n{'='*60}\n  💧 CrystalWater Tenders API v7.5\n  🚀 AUTO-START SCANNER\n  🌐 http://0.0.0.0:{port}\n{'='*60}\n")
    uvicorn.run(app,host="0.0.0.0",port=port)