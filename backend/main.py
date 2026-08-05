"""
main.py  —  FastAPI Backend (v7.0 — Auto-Start Scanner + Backfill 3 mois + Real-Time)
═══════════════════════════════════════════════════════════════════════════════
CrystalWater — Traitement d'eau & Refroidissement industriel
https://crystalwater.ma/

🚀 DÉMARRAGE AUTOMATIQUE:
- Au lancement de l'API, le scanner démarre automatiquement
- Backfill des 3 derniers mois
- Puis surveillance en temps réel (polling automatique)
- Téléchargement DCE + extraction automatique
- Tout est stocké dans Supabase

USAGE:
  python main.py
  → L'API démarre sur le port 8000
  → Le scanner démarre automatiquement en arrière-plan
  → Les données apparaissent dans l'interface React

═══════════════════════════════════════════════════════════════════════════════
"""
import os
import sys
import threading
import time
import traceback
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

if SUPABASE_URL and SUPABASE_SERVICE_KEY:
    import supabase
    supabase_client = supabase.create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
else:
    supabase_client = None

logger = logging.getLogger("main")
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ═══════════════════════════════════════════════════════════════
# IMPORTS DES MODULES
# ═══════════════════════════════════════════════════════════════

try:
    from agents.tender_scanner import (
        run_backfill,
        RealtimeScanner,
        load_tenders,
        load_suppliers,
        load_sectors,
        update_tender_status,
        update_supplier_status,
        update_sector_status,
        generate_email,
        send_email_via_resend,
        get_active_keywords,
        _sb_get_keywords,
        _sb_add_keyword,
        _sb_delete_keyword,
        _sb_update_keyword,
        _sb_get_tenders_2,
        _sb_patch_tenders_2,
        recalculate_all_scores,
        _sb_get_existing_refs,
    )
    SCANNER_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Scanner module not available: {e}")
    SCANNER_AVAILABLE = False

try:
    from agents.zip_viewer import (
        list_files_in_dce,
        preview_file_from_dce,
        extract_text_from_dce,
        get_file_metadata,
        get_raw_file,
        get_tender_row,
        fetch_zip_bytes,
        open_zip,
    )
    ZIP_VIEWER_AVAILABLE = True
except ImportError:
    ZIP_VIEWER_AVAILABLE = False

try:
    from agents.zip_chatbot import (
        index_tender_documents,
        query_tender_chatbot,
        get_chatbot_status,
    )
    CHATBOT_AVAILABLE = True
except ImportError:
    CHATBOT_AVAILABLE = False

try:
    from auth_routes import router as auth_router, get_current_user
    AUTH_AVAILABLE = True
except ImportError:
    AUTH_AVAILABLE = False
    # Fallback auth
    from fastapi import Request
    async def get_current_user(request: Request = None):
        return {"id": "default", "email": "admin@crystalwater.ma"}

# ═══════════════════════════════════════════════════════════════
# FASTAPI APP
# ═══════════════════════════════════════════════════════════════

app = FastAPI(
    title="CrystalWater Tenders API",
    version="7.0.0",
    description="Auto-start scanner with 3-month backfill + real-time monitoring"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if AUTH_AVAILABLE:
    app.include_router(auth_router)

# ═══════════════════════════════════════════════════════════════
# ÉTAT DU SCANNER
# ═══════════════════════════════════════════════════════════════

_scanner_running = False
_scanner_thread = None
_scanner_status = {
    "is_running": False,
    "mode": "stopped",
    "started_at": None,
    "backfill_completed": False,
    "realtime_active": False,
    "tenders_found": 0,
    "dce_downloaded": 0,
    "last_poll": None,
    "current_page": 0,
    "total_pages": 0,
}

# ═══════════════════════════════════════════════════════════════
# DÉMARRAGE AUTOMATIQUE DU SCANNER
# ═══════════════════════════════════════════════════════════════

def start_scanner_automatically():
    """Démarre le scanner automatiquement au lancement de l'API"""
    global _scanner_running, _scanner_thread, _scanner_status
    
    if not SCANNER_AVAILABLE:
        logger.warning("Scanner module not available, skipping auto-start")
        return
    
    if _scanner_running:
        logger.info("Scanner already running")
        return
    
    logger.info("=" * 60)
    logger.info("🚀 AUTO-STARTING SCANNER")
    logger.info("=" * 60)
    
    _scanner_running = True
    _scanner_status["is_running"] = True
    _scanner_status["mode"] = "full"
    _scanner_status["started_at"] = datetime.now().isoformat()
    
    def run_scanner():
        global _scanner_status
        
        try:
            # Phase 1: Backfill 3 mois
            logger.info("📅 Phase 1: Backfill des 3 derniers mois...")
            _scanner_status["mode"] = "backfill"
            
            # Importer et exécuter le backfill
            from agents.tender_scanner import BACKFILL_MONTHS, _sb_get_existing_refs
            
            # Compter les tenders existants
            existing = _sb_get_existing_refs()
            logger.info(f"📊 {len(existing)} offres déjà en base")
            
            # Lancer le backfill
            try:
                from agents.tender_scanner import run_backfill as do_backfill
                do_backfill()
            except Exception as e:
                logger.error(f"Backfill error: {e}")
                traceback.print_exc()
            
            _scanner_status["backfill_completed"] = True
            
            # Phase 2: Surveillance temps réel
            logger.info("🔄 Phase 2: Surveillance temps réel...")
            _scanner_status["mode"] = "realtime"
            _scanner_status["realtime_active"] = True
            
            try:
                scanner = RealtimeScanner()
                scanner.run()
            except Exception as e:
                logger.error(f"Realtime error: {e}")
                traceback.print_exc()
            
        except Exception as e:
            logger.error(f"Scanner fatal error: {e}")
            traceback.print_exc()
        finally:
            _scanner_status["is_running"] = False
            _scanner_status["realtime_active"] = False
            logger.info("Scanner stopped")
    
    _scanner_thread = threading.Thread(target=run_scanner, daemon=True)
    _scanner_thread.start()
    
    logger.info("✅ Scanner démarré en arrière-plan")


# ═══════════════════════════════════════════════════════════════
# STARTUP EVENT
# ═══════════════════════════════════════════════════════════════

@app.on_event("startup")
async def startup_event():
    """Démarre le scanner automatiquement au lancement de l'API"""
    # Démarrer le scanner après un court délai pour laisser l'API s'initialiser
    threading.Timer(2.0, start_scanner_automatically).start()
    logger.info("API started - Scanner will auto-start in 2 seconds")


# ═══════════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@app.get("/")
def root():
    return {
        "message": "CrystalWater Tenders API v7.0",
        "scanner": {
            "auto_start": True,
            "status": _scanner_status
        },
        "docs": "/docs"
    }

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "version": "7.0.0",
        "scanner_running": _scanner_running,
        "scanner_status": _scanner_status
    }

@app.get("/scanner/status")
def get_scanner_status(current_user: dict = Depends(get_current_user)):
    """Retourne l'état du scanner"""
    return {
        "success": True,
        "scanner": _scanner_status
    }

@app.post("/scanner/start")
def start_scanner_manually(current_user: dict = Depends(get_current_user)):
    """Démarre le scanner manuellement (s'il n'est pas déjà lancé)"""
    if _scanner_running:
        return {"success": False, "message": "Scanner already running"}
    
    start_scanner_automatically()
    return {"success": True, "message": "Scanner started"}

@app.post("/scanner/stop")
def stop_scanner(current_user: dict = Depends(get_current_user)):
    """Arrête le scanner"""
    global _scanner_running, _scanner_status
    
    if not _scanner_running:
        return {"success": False, "message": "Scanner not running"}
    
    _scanner_running = False
    _scanner_status["is_running"] = False
    _scanner_status["realtime_active"] = False
    
    return {"success": True, "message": "Scanner stopping..."}


# ═══════════════════════════════════════════════════════════════
# TENDERS ENDPOINTS
# ═══════════════════════════════════════════════════════════════

def _build_stats(items):
    total = len(items)
    return {
        "total": total,
        "unseen": len([t for t in items if t.get("qualification_status") == "unseen"]),
        "seen": len([t for t in items if t.get("qualification_status") == "seen"]),
        "preselected": len([t for t in items if t.get("qualification_status") == "preselected"]),
        "qualified": len([t for t in items if t.get("qualification_status") == "qualified"]),
        "high_priority": len([t for t in items if t.get("relevance_score", 0) >= 70]),
        "medium_priority": len([t for t in items if 45 <= t.get("relevance_score", 0) < 70]),
    }

@app.get("/tenders")
def get_tenders(status: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    try:
        tenders = load_tenders(status_filter=status) if status else load_tenders()
        if not tenders:
            tenders = []
        return {
            "success": True,
            "total": len(tenders),
            "tenders": tenders,
            "stats": _build_stats(tenders),
            "scanner_status": _scanner_status
        }
    except Exception as e:
        logger.error(f"GET /tenders error: {e}")
        return {"success": True, "total": 0, "tenders": [], "stats": _build_stats([])}

@app.get("/tenders/preselected")
def get_preselected_tenders(current_user: dict = Depends(get_current_user)):
    try:
        all_tenders = _sb_get_tenders_2({
            "order": "relevance_score.desc",
            "limit": "10000"
        }) or []
        
        filtered = [t for t in all_tenders if t.get("qualification_status") in ["preselected", "qualified"]]
        
        return {
            "success": True,
            "total": len(filtered),
            "tenders": filtered,
            "stats": _build_stats(filtered)
        }
    except Exception as e:
        logger.error(f"GET /tenders/preselected error: {e}")
        return {"success": True, "total": 0, "tenders": [], "stats": _build_stats([])}

@app.put("/tenders/{tender_id:path}/status")
def set_tender_status(tender_id: str, status: str = "contacted", current_user: dict = Depends(get_current_user)):
    if status not in ["new", "contacted", "ignored", "archived"]:
        raise HTTPException(400, "Invalid status")
    try:
        if update_tender_status(tender_id, status):
            return {"success": True, "message": f"Tender updated to {status}"}
        raise HTTPException(404, "Tender not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.put("/tenders/{tender_id:path}/qualify")
def set_tender_qualification(tender_id: str, status: str = "preselected", current_user: dict = Depends(get_current_user)):
    if status not in ["unseen", "seen", "preselected", "qualified"]:
        raise HTTPException(400, "Invalid status")
    try:
        update_data = {"qualification_status": status}
        if status != "unseen":
            update_data["seen"] = True
        if _sb_patch_tenders_2(tender_id, update_data):
            return {"success": True, "message": f"Qualification updated to {status}"}
        raise HTTPException(404, "Tender not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.put("/tenders/{tender_id:path}/seen")
def mark_tender_seen(tender_id: str, current_user: dict = Depends(get_current_user)):
    try:
        if _sb_patch_tenders_2(tender_id, {"seen": True}):
            return {"success": True}
        raise HTTPException(404)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.put("/tenders/mark-all-seen")
def mark_all_tenders_seen(current_user: dict = Depends(get_current_user)):
    try:
        tenders = _sb_get_tenders_2({"select": "reference,seen", "seen": "eq.false"})
        count = 0
        for t in tenders:
            if _sb_patch_tenders_2(t["reference"], {"seen": True}):
                count += 1
        return {"success": True, "marked_count": count}
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.post("/tenders/scan")
def scan_tenders_manually(current_user: dict = Depends(get_current_user)):
    """Lance un scan manuel (backfill + realtime)"""
    if _scanner_running:
        return {
            "success": False,
            "message": "Scanner already running",
            "scanner_status": _scanner_status
        }
    
    start_scanner_automatically()
    return {
        "success": True,
        "message": "Scanner started (backfill 3 months + real-time)"
    }


# ═══════════════════════════════════════════════════════════════
# KEYWORDS ENDPOINTS
# ═══════════════════════════════════════════════════════════════

class KeywordCreate(BaseModel):
    keyword: str = Field(..., min_length=1, max_length=255)
    category: str = Field(default="custom")
    is_active: bool = Field(default=True)

class KeywordUpdate(BaseModel):
    keyword: Optional[str] = None
    category: Optional[str] = None
    is_active: Optional[bool] = None

@app.get("/keywords")
def get_keywords(current_user: dict = Depends(get_current_user)):
    try:
        keywords = _sb_get_keywords({"order": "keyword.asc"})
        return {"success": True, "keywords": keywords, "total": len(keywords)}
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.get("/keywords/active")
def get_active_keywords_endpoint(current_user: dict = Depends(get_current_user)):
    try:
        active = get_active_keywords()
        return {"success": True, "keywords": active, "total": len(active)}
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.post("/keywords")
def create_keyword(req: KeywordCreate, current_user: dict = Depends(get_current_user)):
    try:
        keyword = req.keyword.strip().lower()
        if not keyword:
            raise HTTPException(400, "Keyword cannot be empty")
        
        existing = _sb_get_keywords({"keyword": f"eq.{keyword}"})
        if existing:
            raise HTTPException(400, f"Keyword '{keyword}' already exists")
        
        result = _sb_add_keyword({
            "keyword": keyword,
            "category": req.category,
            "is_active": req.is_active,
            "created_at": datetime.now().isoformat()
        })
        
        if result:
            return {"success": True, "keyword": result}
        raise HTTPException(500, "Failed to add keyword")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.delete("/keywords/{keyword_id}")
def delete_keyword(keyword_id: int, current_user: dict = Depends(get_current_user)):
    try:
        if _sb_delete_keyword(keyword_id):
            return {"success": True, "message": f"Keyword #{keyword_id} deleted"}
        raise HTTPException(404, "Keyword not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.patch("/keywords/{keyword_id}")
def update_keyword(keyword_id: int, req: KeywordUpdate, current_user: dict = Depends(get_current_user)):
    try:
        update_data = {}
        if req.keyword is not None:
            update_data["keyword"] = req.keyword.strip().lower()
        if req.category is not None:
            update_data["category"] = req.category
        if req.is_active is not None:
            update_data["is_active"] = req.is_active
        
        if not update_data:
            raise HTTPException(400, "No fields to update")
        
        update_data["updated_at"] = datetime.now().isoformat()
        
        if _sb_update_keyword(keyword_id, update_data):
            return {"success": True, "message": f"Keyword #{keyword_id} updated"}
        raise HTTPException(404, "Keyword not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, detail=str(e))


# ═══════════════════════════════════════════════════════════════
# BP ITEMS ENDPOINT
# ═══════════════════════════════════════════════════════════════

@app.get("/tenders/{tender_id:path}/bp-items")
def get_bp_items(tender_id: str, current_user: dict = Depends(get_current_user)):
    if not supabase_client:
        raise HTTPException(500, "Supabase not configured")
    try:
        response = supabase_client.table("tenders_3_bp_items").select("*").eq("tender_reference", tender_id).order("id").execute()
        items = response.data if response.data else []
        
        total_ht = sum(float(item.get("total_ht", 0) or 0) for item in items)
        
        return {
            "success": True,
            "items": items,
            "total_items": len(items),
            "summary": {"total_ht": round(total_ht, 2)},
            "tender_reference": tender_id
        }
    except Exception as e:
        logger.error(f"Error fetching BP items: {e}")
        raise HTTPException(500, detail=str(e))


# ═══════════════════════════════════════════════════════════════
# ZIP VIEWER ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@app.get("/tenders/{tender_id:path}/files")
def get_dce_files(tender_id: str):
    if ZIP_VIEWER_AVAILABLE:
        return list_files_in_dce(tender_id)
    return {"files": [], "error": "ZIP viewer not available"}

@app.get("/tenders/{tender_id:path}/preview/{file_path:path}")
def get_dce_preview(tender_id: str, file_path: str):
    if ZIP_VIEWER_AVAILABLE:
        return preview_file_from_dce(tender_id, file_path)
    raise HTTPException(501, "Not available")


# ═══════════════════════════════════════════════════════════════
# EMAIL ENDPOINTS
# ═══════════════════════════════════════════════════════════════

class TenderEmailRequest(BaseModel):
    tender_id: str
    template_key: str = "information_request"
    sender_name: str = "CrystalWater Team"
    sender_title: str = "Directeur Commercial"
    sender_email: str = "contact@crystalwater.ma"
    sender_phone: str = "+212 6 10 10 74 75"

@app.post("/tenders/generate-email")
def generate_tender_email(req: TenderEmailRequest, current_user: dict = Depends(get_current_user)):
    try:
        tenders = load_tenders()
        tender = next((t for t in tenders if t.get("reference") == req.tender_id), None)
        if not tender:
            raise HTTPException(404, "Tender not found")
        
        email_data = generate_email(
            tender=tender,
            template_key=req.template_key,
            language="french",
            sender_name=req.sender_name,
            sender_title=req.sender_title,
            sender_email=req.sender_email,
            sender_phone=req.sender_phone
        )
        return {"success": True, "email": email_data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.post("/tenders/send-email")
def send_tender_email(req: dict, current_user: dict = Depends(get_current_user)):
    try:
        result = send_email_via_resend(req.get("email_data", {}))
        if result.get("success"):
            update_tender_status(str(req.get("tender_id", "")), "contacted")
        return result
    except Exception as e:
        raise HTTPException(500, detail=str(e))


# ═══════════════════════════════════════════════════════════════
# SCORING CRITERIA ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@app.get("/scoring-criteria")
def get_scoring_criteria(current_user: dict = Depends(get_current_user)):
    try:
        from agents.tender_scanner import _sb_get_criteria
        criteria = _sb_get_criteria({"order": "weight.desc"})
        return {"success": True, "criteria": criteria, "total": len(criteria)}
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.get("/scoring-criteria/active")
def get_active_scoring_criteria(current_user: dict = Depends(get_current_user)):
    try:
        from agents.tender_scanner import _sb_get_criteria
        criteria = _sb_get_criteria({"is_active": "eq.true", "order": "weight.desc"})
        return {"success": True, "criteria": criteria, "total": len(criteria)}
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.post("/scoring-criteria")
def create_scoring_criteria(req: dict, current_user: dict = Depends(get_current_user)):
    try:
        from agents.tender_scanner import _sb_add_criteria
        result = _sb_add_criteria({
            "field_name": req.get("field_name", ""),
            "operator": req.get("operator", "="),
            "value": req.get("value", ""),
            "weight": int(req.get("weight", 1)),
            "is_active": req.get("is_active", True),
            "created_at": datetime.now().isoformat()
        })
        if result:
            # Recalculer les scores
            threading.Thread(target=recalculate_all_scores, daemon=True).start()
            return {"success": True, "criteria": result}
        raise HTTPException(500, "Failed to add criteria")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.delete("/scoring-criteria/{criteria_id}")
def delete_scoring_criteria(criteria_id: int, current_user: dict = Depends(get_current_user)):
    try:
        from agents.tender_scanner import _sb_delete_criteria
        if _sb_delete_criteria(criteria_id):
            threading.Thread(target=recalculate_all_scores, daemon=True).start()
            return {"success": True, "message": f"Criteria #{criteria_id} deleted"}
        raise HTTPException(404, "Criteria not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, detail=str(e))


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    
    port = int(os.environ.get("PORT", 8000))
    
    print("\n" + "=" * 60)
    print("  💧 CrystalWater Tenders API v7.0")
    print("  🚀 AUTO-START SCANNER ENABLED")
    print("  📅 Backfill: 3 derniers mois")
    print("  🔄 Real-time: polling automatique")
    print(f"  🌐 http://0.0.0.0:{port}")
    print("  📚 http://0.0.0.0:{port}/docs")
    print("=" * 60 + "\n")
    print("  ⏳ Le scanner démarrera automatiquement dans 2 secondes...")
    print("  📊 Les appels d'offres apparaîtront dans l'interface React")
    print("\n")
    
    uvicorn.run(app, host="0.0.0.0", port=port)