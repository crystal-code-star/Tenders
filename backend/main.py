"""
main.py  —  FastAPI Backend (v6.8 — Tenders + Keywords + Scoring + ZIP Viewer + Chatbot + BP Items)
═══════════════════════════════════════════════════════════════════════════════
Entreprise: CrystalWater (crystalwater.ma)
  - Intégrateur de solutions de traitement d'eau et refroidissement industriel
  - Email: contact@crystalwater.ma
  - Tél: +212 6 10 10 74 75 / +212 5 22 35 23 36
═══════════════════════════════════════════════════════════════════════════════
"""
import os
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
from auth_routes import router as auth_router, get_current_user

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

from agents.tender_scanner import (
    run_tender_scan,
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
)

from agents.document.docx_extractor import extract_docx_structured
from agents.document.excel_extractor import extract_excel_structured
from agents.document.document_analyzer import analyze_document_with_llm

from agents.zip_chatbot import (
    index_tender_documents,
    query_tender_chatbot,
    get_chatbot_status,
)

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

app = FastAPI(title="CrystalWater Tenders API", version="6.8.0")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

app.include_router(auth_router)

_tender_scan_running = False


# ═══════════════════════════════════════════════════════════
#  PYDANTIC MODELS
# ═══════════════════════════════════════════════════════════

class TenderEmailRequest(BaseModel):
    tender_id: str
    item_type: Optional[str] = Field(default=None)
    template_key: str = Field(default="information_request")
    language: str = Field(default="french")
    sender_name: str = Field(default="CrystalWater Team")
    sender_title: str = Field(default="Directeur Commercial")
    sender_email: str = Field(default="contact@crystalwater.ma")
    sender_phone: str = Field(default="+212 6 10 10 74 75")

class TenderSendEmailRequest(BaseModel):
    tender_id: str
    item_type: Optional[str] = Field(default=None)
    email_data: dict

class KeywordCreate(BaseModel):
    keyword: str = Field(..., min_length=1, max_length=255)
    category: str = Field(default="custom")
    is_active: bool = Field(default=True)

class KeywordUpdate(BaseModel):
    keyword: Optional[str] = Field(default=None)
    category: Optional[str] = Field(default=None)
    is_active: Optional[bool] = Field(default=None)


# ═══════════════════════════════════════════════════════════
#  HEALTH / ROOT
# ═══════════════════════════════════════════════════════════

@app.get("/health")
def health_check(): return {"status": "ok", "version": "6.8.0"}

@app.get("/")
def root(): return {"message": "CrystalWater Tenders API v6.8", "docs": "/docs"}


# ═══════════════════════════════════════════════════════════
#  TENDERS / SUPPLIERS / SECTORS
# ═══════════════════════════════════════════════════════════

def _build_stats(items):
    total = len(items)
    unseen_count = len([t for t in items if t.get("qualification_status") == "unseen"])
    seen_count = len([t for t in items if t.get("qualification_status") == "seen"])
    preselected_count = len([t for t in items if t.get("qualification_status") == "preselected"])
    qualified_count = len([t for t in items if t.get("qualification_status") == "qualified"])
    high_priority = len([t for t in items if t.get("relevance_score", 0) >= 70])
    medium_priority = len([t for t in items if 45 <= t.get("relevance_score", 0) < 70])
    return {
        "total": total,
        "unseen": unseen_count,
        "seen": seen_count,
        "preselected": preselected_count,
        "qualified": qualified_count,
        "high_priority": high_priority,
        "medium_priority": medium_priority
    }

@app.get("/tenders")
def get_tenders(status: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    try:
        tenders = load_tenders(status_filter=status) if status else load_tenders()
        if not tenders: tenders = []
        unseen_count = len([t for t in tenders if not t.get("seen", False)])
        return {"success": True, "total": len(tenders), "tenders": tenders, "unseen_count": unseen_count, "stats": _build_stats(tenders)}
    except Exception as e:
        print(f"[Tenders] GET /tenders error: {e}")
        return {"success": True, "total": 0, "tenders": [], "unseen_count": 0, "stats": _build_stats([])}

@app.get("/suppliers")
def get_suppliers(status: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    try:
        suppliers = load_suppliers(status_filter=status) if status else load_suppliers()
        if not suppliers: suppliers = []
        return {"success": True, "total": len(suppliers), "suppliers": suppliers, "stats": _build_stats(suppliers)}
    except Exception as e:
        print(f"[Suppliers] GET /suppliers error: {e}")
        return {"success": True, "total": 0, "suppliers": [], "stats": _build_stats([])}

@app.get("/sectors")
def get_sectors(status: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    try:
        sectors = load_sectors(status_filter=status) if status else load_sectors()
        if not sectors: sectors = []
        return {"success": True, "total": len(sectors), "sectors": sectors, "stats": _build_stats(sectors)}
    except Exception as e:
        print(f"[Sectors] GET /sectors error: {e}")
        return {"success": True, "total": 0, "sectors": [], "stats": _build_stats([])}

@app.post("/tenders/scan")
def scan_tenders(background_tasks: BackgroundTasks, current_user: dict = Depends(get_current_user)):
    global _tender_scan_running
    if _tender_scan_running:
        return {"success": False, "message": "Scan already running"}
    _tender_scan_running = True
    
    def run():
        global _tender_scan_running
        try:
            run_tender_scan()
        except Exception as e:
            print(f"[Tenders] Scan error: {e}")
            traceback.print_exc()
        finally:
            _tender_scan_running = False
    
    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return {"success": True, "message": "Africa scan started. Refresh in 30-60 seconds."}

@app.put("/tenders/mark-all-seen")
def mark_all_tenders_seen(current_user: dict = Depends(get_current_user)):
    try:
        tenders = _sb_get_tenders_2({"select": "reference,seen", "seen": "eq.false"})
        count = 0
        for t in tenders:
            if _sb_patch_tenders_2(t["reference"], {"seen": True}): count += 1
        return {"success": True, "marked_count": count}
    except Exception as e: raise HTTPException(500, detail=str(e))

@app.post("/tenders/generate-email")
def generate_tender_email(req: TenderEmailRequest, current_user: dict = Depends(get_current_user)):
    try:
        item, table_used = _find_item_by_id(req.tender_id, req.item_type)
        if not item: raise HTTPException(404)
        email_data = generate_email(tender=item, template_key=req.template_key, language=req.language, sender_name=req.sender_name, sender_title=req.sender_title, sender_email=req.sender_email, sender_phone=req.sender_phone)
        return {"success": True, "email": email_data, "item_type": table_used}
    except HTTPException: raise
    except Exception as e: traceback.print_exc(); raise HTTPException(500, detail=str(e))

@app.post("/tenders/send-email")
def send_tender_email(req: TenderSendEmailRequest, current_user: dict = Depends(get_current_user)):
    try:
        result = send_email_via_resend(req.email_data)
        if result.get("success"):
            if req.item_type == "tender" or not req.item_type: update_tender_status(str(req.tender_id), "contacted")
            elif req.item_type == "supplier": update_supplier_status(str(req.tender_id), "contacted")
            elif req.item_type == "sector": update_sector_status(str(req.tender_id), "contacted")
            else: update_tender_status(str(req.tender_id), "contacted"); update_supplier_status(str(req.tender_id), "contacted"); update_sector_status(str(req.tender_id), "contacted")
        return result
    except Exception as e: raise HTTPException(500, detail=str(e))


# ═══════════════════════════════════════════════════════════
#  TENDER QUALIFICATION STATUS
# ═══════════════════════════════════════════════════════════

@app.put("/tenders/{tender_id:path}/qualify")
def set_tender_qualification(tender_id: str, status: str = "preselected", current_user: dict = Depends(get_current_user)):
    if status not in ["unseen", "seen", "preselected", "qualified"]:
        raise HTTPException(400, detail="Statut invalide. Valeurs acceptées: unseen, seen, preselected, qualified")
    
    try:
        update_data = {"qualification_status": status}
        if status != "unseen":
            update_data["seen"] = True
        
        success = _sb_patch_tenders_2(tender_id, update_data)
        if success:
            return {"success": True, "message": f"Tender qualification updated to {status}"}
        raise HTTPException(404, "Tender not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.get("/tenders/preselected")
def get_preselected_tenders(current_user: dict = Depends(get_current_user)):
    try:
        params_preselected = {
            "qualification_status": "eq.preselected",
            "order": "relevance_score.desc",
            "limit": "10000"
        }
        preselected = _sb_get_tenders_2(params_preselected)
        
        params_qualified = {
            "qualification_status": "eq.qualified",
            "order": "relevance_score.desc",
            "limit": "10000"
        }
        qualified = _sb_get_tenders_2(params_qualified)
        
        all_tenders = (preselected or []) + (qualified or [])
        
        seen_refs = set()
        unique_tenders = []
        for t in all_tenders:
            ref = t.get("reference")
            if ref and ref not in seen_refs:
                seen_refs.add(ref)
                unique_tenders.append(t)
        
        unique_tenders.sort(key=lambda t: t.get("relevance_score", 0), reverse=True)
        
        return {
            "success": True,
            "total": len(unique_tenders),
            "tenders": unique_tenders,
            "stats": _build_stats(unique_tenders)
        }
    except Exception as e:
        print(f"[Tenders] GET /tenders/preselected error: {e}")
        return {"success": True, "total": 0, "tenders": [], "stats": _build_stats([])}

@app.get("/tenders/qualified")
def get_qualified_tenders(current_user: dict = Depends(get_current_user)):
    try:
        params = {
            "qualification_status": "eq.qualified",
            "order": "relevance_score.desc",
            "limit": "10000"
        }
        tenders = _sb_get_tenders_2(params)
        return {
            "success": True,
            "total": len(tenders),
            "tenders": tenders,
            "stats": _build_stats(tenders)
        }
    except Exception as e:
        print(f"[Tenders] GET /tenders/qualified error: {e}")
        return {"success": True, "total": 0, "tenders": [], "stats": _build_stats([])}


# ═══════════════════════════════════════════════════════════
#  BP ITEMS
# ═══════════════════════════════════════════════════════════

@app.get("/api/tenders/{tender_id:path}/bp-items")
@app.get("/tenders/{tender_id:path}/bp-items")
def get_bp_items(tender_id: str, current_user: dict = Depends(get_current_user)):
    if not supabase_client:
        raise HTTPException(500, detail="Supabase client not configured")
    
    try:
        response = supabase_client.table("tenders_3_bp_items").select("*").eq("tender_reference", tender_id).order("id").execute()
        items = response.data if response.data else []
        
        tender_response = supabase_client.table("tenders_3").select("bp_extraction_status, bp_extracted_at").eq("reference", tender_id).execute()
        bp_status = None
        bp_extracted_at = None
        if tender_response.data:
            bp_status = tender_response.data[0].get("bp_extraction_status")
            bp_extracted_at = tender_response.data[0].get("bp_extracted_at")
        
        total_ht = 0
        total_qty = 0
        items_with_price = 0
        for item in items:
            if item.get("total_ht"):
                try:
                    total_ht += float(item["total_ht"])
                    items_with_price += 1
                except (ValueError, TypeError): pass
            if item.get("quantite"):
                try: total_qty += float(item["quantite"])
                except (ValueError, TypeError): pass
        
        return {
            "success": True,
            "items": items,
            "total_items": len(items),
            "summary": {
                "total_ht": round(total_ht, 2),
                "total_qty": round(total_qty, 2),
                "items_with_price": items_with_price,
                "avg_price": round(total_ht / items_with_price, 2) if items_with_price > 0 else 0
            },
            "extraction": {"status": bp_status, "extracted_at": bp_extracted_at},
            "tender_reference": tender_id
        }
    except Exception as e:
        logger.error(f"Error fetching BP items for {tender_id}: {e}")
        raise HTTPException(500, detail=str(e))

@app.get("/api/tenders/{tender_id:path}/bp-status")
@app.get("/tenders/{tender_id:path}/bp-status")
def get_bp_status(tender_id: str, current_user: dict = Depends(get_current_user)):
    if not supabase_client:
        raise HTTPException(500, detail="Supabase client not configured")
    
    try:
        tender_response = supabase_client.table("tenders_3").select("bp_extraction_status, bp_extracted_at").eq("reference", tender_id).execute()
        items_response = supabase_client.table("tenders_3_bp_items").select("id", count="exact").eq("tender_reference", tender_id).execute()
        
        bp_status = None
        bp_extracted_at = None
        items_count = items_response.count if hasattr(items_response, 'count') else 0
        if tender_response.data:
            bp_status = tender_response.data[0].get("bp_extraction_status")
            bp_extracted_at = tender_response.data[0].get("bp_extracted_at")
        
        return {
            "success": True,
            "tender_reference": tender_id,
            "bp_extraction_status": bp_status,
            "bp_extracted_at": bp_extracted_at,
            "items_count": items_count,
            "has_bp": bp_status == "completed" and items_count > 0
        }
    except Exception as e:
        logger.error(f"Error checking BP status for {tender_id}: {e}")
        raise HTTPException(500, detail=str(e))


# ═══════════════════════════════════════════════════════════
#  TENDER STATUS / SEEN
# ═══════════════════════════════════════════════════════════

@app.put("/tenders/{tender_id:path}/status")
def set_tender_status(tender_id: str, status: str = "contacted", current_user: dict = Depends(get_current_user)):
    if status not in ["new", "contacted", "ignored", "archived"]: raise HTTPException(400)
    try:
        updated = update_tender_status(tender_id, status)
        if not updated: raise HTTPException(404)
        return {"success": True, "message": f"Tender updated to {status}"}
    except HTTPException: raise
    except Exception as e: raise HTTPException(500, detail=str(e))

@app.put("/suppliers/{supplier_id}/status")
def set_supplier_status(supplier_id: str, status: str = "contacted", current_user: dict = Depends(get_current_user)):
    if status not in ["new", "contacted", "ignored", "archived"]: raise HTTPException(400)
    try:
        updated = update_supplier_status(supplier_id, status)
        if not updated: raise HTTPException(404)
        return {"success": True, "message": f"Supplier updated to {status}"}
    except HTTPException: raise
    except Exception as e: raise HTTPException(500, detail=str(e))

@app.put("/sectors/{sector_id}/status")
def set_sector_status(sector_id: str, status: str = "contacted", current_user: dict = Depends(get_current_user)):
    if status not in ["new", "contacted", "ignored", "archived"]: raise HTTPException(400)
    try:
        updated = update_sector_status(sector_id, status)
        if not updated: raise HTTPException(404)
        return {"success": True, "message": f"Sector updated to {status}"}
    except HTTPException: raise
    except Exception as e: raise HTTPException(500, detail=str(e))

@app.put("/tenders/{tender_id:path}/seen")
def mark_tender_seen(tender_id: str, current_user: dict = Depends(get_current_user)):
    try:
        success = _sb_patch_tenders_2(tender_id, {"seen": True})
        if success: return {"success": True, "message": "Tender marked as seen"}
        raise HTTPException(404, "Tender not found")
    except HTTPException: raise
    except Exception as e: raise HTTPException(500, detail=str(e))


# ═══════════════════════════════════════════════════════════
#  EMAIL HELPER
# ═══════════════════════════════════════════════════════════

def _find_item_by_id(item_id: str, item_type: Optional[str] = None):
    item = None; table_used = None
    if item_type == "tender" or not item_type:
        tenders = load_tenders() or []
        item = next((t for t in tenders if str(t.get("id")) == str(item_id)), None)
        if item: table_used = "tender"
    if not item and (item_type == "supplier" or not item_type):
        suppliers = load_suppliers() or []
        item = next((t for t in suppliers if str(t.get("id")) == str(item_id)), None)
        if item: table_used = "supplier"
    if not item and (item_type == "sector" or not item_type):
        sectors = load_sectors() or []
        item = next((t for t in sectors if str(t.get("id")) == str(item_id)), None)
        if item: table_used = "sector"
    return item, table_used


# ═══════════════════════════════════════════════════════════
#  KEYWORDS MANAGEMENT
# ═══════════════════════════════════════════════════════════

@app.get("/keywords")
def get_keywords(category: Optional[str] = None, is_active: Optional[bool] = None, current_user: dict = Depends(get_current_user)):
    try:
        params = {"order": "keyword.asc"}
        if category: params["category"] = f"eq.{category}"
        if is_active is not None: params["is_active"] = f"eq.{str(is_active).lower()}"
        keywords = _sb_get_keywords(params)
        return {"success": True, "keywords": keywords, "total": len(keywords)}
    except Exception as e: logger.error(f"Error fetching keywords: {e}"); raise HTTPException(500, detail=str(e))

@app.get("/keywords/active")
def get_active_keywords_endpoint(current_user: dict = Depends(get_current_user)):
    try:
        active = get_active_keywords()
        return {"success": True, "keywords": active, "total": len(active)}
    except Exception as e: logger.error(f"Error fetching active keywords: {e}"); raise HTTPException(500, detail=str(e))

@app.post("/keywords")
def create_keyword(req: KeywordCreate, current_user: dict = Depends(get_current_user)):
    try:
        keyword = req.keyword.strip().lower()
        if not keyword: raise HTTPException(400)
        existing = _sb_get_keywords({"keyword": f"eq.{keyword}"})
        if existing: raise HTTPException(400, f"Keyword '{keyword}' already exists")
        keyword_data = {"keyword": keyword, "category": req.category, "is_active": req.is_active, "created_at": datetime.now().isoformat()}
        result = _sb_add_keyword(keyword_data)
        if result: return {"success": True, "keyword": result, "message": f"Keyword '{keyword}' added"}
        raise HTTPException(500)
    except HTTPException: raise
    except Exception as e: logger.error(f"Error creating keyword: {e}"); raise HTTPException(500, detail=str(e))

@app.delete("/keywords/{keyword_id}")
def delete_keyword(keyword_id: int, current_user: dict = Depends(get_current_user)):
    try:
        success = _sb_delete_keyword(keyword_id)
        if success: return {"success": True, "message": f"Keyword #{keyword_id} deleted"}
        raise HTTPException(404)
    except HTTPException: raise
    except Exception as e: logger.error(f"Error deleting keyword: {e}"); raise HTTPException(500, detail=str(e))

@app.patch("/keywords/{keyword_id}")
def update_keyword(keyword_id: int, req: KeywordUpdate, current_user: dict = Depends(get_current_user)):
    try:
        update_data = {}
        if req.keyword is not None: update_data["keyword"] = req.keyword.strip().lower()
        if req.category is not None: update_data["category"] = req.category
        if req.is_active is not None: update_data["is_active"] = req.is_active
        if not update_data: raise HTTPException(400)
        update_data["updated_at"] = datetime.now().isoformat()
        success = _sb_update_keyword(keyword_id, update_data)
        if success: return {"success": True, "message": f"Keyword #{keyword_id} updated", "updates": update_data}
        raise HTTPException(404)
    except HTTPException: raise
    except Exception as e: logger.error(f"Error updating keyword: {e}"); raise HTTPException(500, detail=str(e))


# ═══════════════════════════════════════════════════════════
#  SCORING CRITERIA MANAGEMENT
# ═══════════════════════════════════════════════════════════

SCORING_TABLE = "scoring_criteria"

def _sb_get_criteria(params: dict = None) -> List[dict]:
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY: return []
    try:
        import requests
        r = requests.get(f"{SUPABASE_URL}/rest/v1/{SCORING_TABLE}", 
                        headers={
                            "apikey": SUPABASE_SERVICE_KEY, 
                            "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
                            "Content-Type": "application/json"
                        }, 
                        params=params or {}, timeout=15)
        r.raise_for_status(); return r.json() or []
    except: return []

def _sb_add_criteria(data: dict) -> Optional[dict]:
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY: return None
    try:
        import requests
        headers = {
            "apikey": SUPABASE_SERVICE_KEY, 
            "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
            "Content-Type": "application/json", 
            "Prefer": "return=representation"
        }
        r = requests.post(f"{SUPABASE_URL}/rest/v1/{SCORING_TABLE}", headers=headers, json=data, timeout=15)
        if r.status_code in (200, 201): return r.json()[0] if r.json() else data
        return None
    except: return None

def _sb_delete_criteria(criteria_id: int) -> bool:
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY: return False
    try:
        import requests
        headers = {
            "apikey": SUPABASE_SERVICE_KEY, 
            "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}"
        }
        r = requests.delete(f"{SUPABASE_URL}/rest/v1/{SCORING_TABLE}?id=eq.{criteria_id}", headers=headers, timeout=15)
        return r.status_code in (200, 204)
    except: return False

def _sb_update_criteria(criteria_id: int, data: dict) -> bool:
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY: return False
    try:
        import requests
        headers = {
            "apikey": SUPABASE_SERVICE_KEY, 
            "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }
        r = requests.patch(f"{SUPABASE_URL}/rest/v1/{SCORING_TABLE}?id=eq.{criteria_id}", headers=headers, json=data, timeout=15)
        return r.status_code in (200, 204)
    except: return False

@app.get("/scoring-criteria")
def get_scoring_criteria(category: Optional[str] = None, is_active: Optional[bool] = None, current_user: dict = Depends(get_current_user)):
    try:
        params = {"order": "category.asc,weight.desc"}
        if category: params["category"] = f"eq.{category}"
        if is_active is not None: params["is_active"] = f"eq.{str(is_active).lower()}"
        criteria = _sb_get_criteria(params)
        return {"success": True, "criteria": criteria, "total": len(criteria)}
    except Exception as e:
        logger.error(f"Error fetching scoring criteria: {e}")
        raise HTTPException(500, detail=str(e))

@app.get("/scoring-criteria/active")
def get_active_scoring_criteria(current_user: dict = Depends(get_current_user)):
    try:
        criteria = _sb_get_criteria({"is_active": "eq.true", "order": "category.asc,weight.desc"})
        return {"success": True, "criteria": criteria, "total": len(criteria)}
    except Exception as e:
        logger.error(f"Error fetching active scoring criteria: {e}")
        raise HTTPException(500, detail=str(e))

@app.post("/scoring-criteria")
def create_scoring_criteria(req: dict, current_user: dict = Depends(get_current_user)):
    try:
        name = req.get("name", "").strip()
        category = req.get("category", "keyword")
        value = req.get("value", "").strip().lower()
        weight = int(req.get("weight", 1))
        is_active = req.get("is_active", True)
        
        if not name or not value: raise HTTPException(400, "Name and value are required")
        if category not in ["strong_keyword", "medium_keyword", "specific_keyword", "strategic_client", "exclusion"]:
            raise HTTPException(400, "Invalid category")
        
        criteria_data = {
            "name": name,
            "category": category,
            "value": value,
            "weight": weight,
            "is_active": is_active,
            "created_at": datetime.now().isoformat()
        }
        result = _sb_add_criteria(criteria_data)
        if result: return {"success": True, "criteria": result, "message": f"Criteria '{name}' added"}
        raise HTTPException(500)
    except HTTPException: raise
    except Exception as e:
        logger.error(f"Error creating scoring criteria: {e}")
        raise HTTPException(500, detail=str(e))

@app.delete("/scoring-criteria/{criteria_id}")
def delete_scoring_criteria(criteria_id: int, current_user: dict = Depends(get_current_user)):
    try:
        success = _sb_delete_criteria(criteria_id)
        if success: return {"success": True, "message": f"Criteria #{criteria_id} deleted"}
        raise HTTPException(404)
    except HTTPException: raise
    except Exception as e:
        logger.error(f"Error deleting scoring criteria: {e}")
        raise HTTPException(500, detail=str(e))

@app.patch("/scoring-criteria/{criteria_id}")
def update_scoring_criteria(criteria_id: int, req: dict, current_user: dict = Depends(get_current_user)):
    try:
        update_data = {}
        if "name" in req: update_data["name"] = req["name"].strip()
        if "category" in req: update_data["category"] = req["category"]
        if "value" in req: update_data["value"] = req["value"].strip().lower()
        if "weight" in req: update_data["weight"] = int(req["weight"])
        if "is_active" in req: update_data["is_active"] = req["is_active"]
        
        if not update_data: raise HTTPException(400)
        update_data["updated_at"] = datetime.now().isoformat()
        
        success = _sb_update_criteria(criteria_id, update_data)
        if success: return {"success": True, "message": f"Criteria #{criteria_id} updated", "updates": update_data}
        raise HTTPException(404)
    except HTTPException: raise
    except Exception as e:
        logger.error(f"Error updating scoring criteria: {e}")
        raise HTTPException(500, detail=str(e))


# ═══════════════════════════════════════════════════════════
#  ZIP VIEWER
# ═══════════════════════════════════════════════════════════

def _get_extractor_for_file(file_path: str):
    ext = Path(file_path).suffix.lower()
    if ext == ".docx": return extract_docx_structured, "docx"
    if ext in [".xlsx", ".xlsm", ".xls"]: return extract_excel_structured, "xlsx" if ext in [".xlsx", ".xlsm"] else "xls"
    return None, None

@app.get("/api/tenders/{tender_id:path}/extract/{file_path:path}")
@app.get("/tenders/{tender_id:path}/extract/{file_path:path}")
def extract_document(tender_id: str, file_path: str):
    start_time = time.time()
    tender = get_tender_row(tender_id)
    zip_bytes = fetch_zip_bytes(tender_id, tender.get("dce_zip_url"))
    with open_zip(zip_bytes) as zf:
        if file_path not in zf.namelist(): raise HTTPException(404)
        file_bytes = zf.read(file_path)
    extractor, file_type = _get_extractor_for_file(file_path)
    if not extractor: raise HTTPException(400)
    result = extractor(file_bytes, file_path)
    result["extraction_time_ms"] = int((time.time() - start_time) * 1000)
    return result

_analysis_cache = {}

@app.post("/api/tenders/{tender_id:path}/analyze/{file_path:path}")
@app.post("/tenders/{tender_id:path}/analyze/{file_path:path}")
def analyze_document(tender_id: str, file_path: str, force: bool = False):
    cache_key = f"{tender_id}:{file_path}"
    if not force and cache_key in _analysis_cache: return _analysis_cache[cache_key]
    tender = get_tender_row(tender_id)
    zip_bytes = fetch_zip_bytes(tender_id, tender.get("dce_zip_url"))
    with open_zip(zip_bytes) as zf:
        if file_path not in zf.namelist(): raise HTTPException(404)
        file_bytes = zf.read(file_path)
    ext = Path(file_path).suffix.lower()
    if ext == ".docx":
        structured = extract_docx_structured(file_bytes, file_path)
        file_type = "docx"
    elif ext in [".xlsx", ".xlsm", ".xls"]:
        structured = extract_excel_structured(file_bytes, file_path)
        file_type = "xlsx" if ext in [".xlsx", ".xlsm"] else "xls"
    else:
        raise HTTPException(400, "Unsupported file type for analysis")
    analysis = analyze_document_with_llm(structured, file_type, Path(file_path).name, tender_id)
    _analysis_cache[cache_key] = analysis
    return analysis

def _dce_file_listing(tender_id: str) -> dict:
    result = list_files_in_dce(tender_id)
    try:
        row = get_tender_row(tender_id)
        result["dce_zip_url"] = row.get("dce_zip_url")
    except Exception: result["dce_zip_url"] = None
    return result

@app.get("/api/tenders/{tender_id:path}/files")
@app.get("/tenders/{tender_id:path}/files")
def get_dce_files(tender_id: str): return _dce_file_listing(tender_id)

@app.get("/tenders/{tender_id:path}/zip-contents")
def get_dce_zip_contents_legacy(tender_id: str): return _dce_file_listing(tender_id)

@app.get("/api/tenders/{tender_id:path}/preview/{file_path:path}")
@app.get("/tenders/{tender_id:path}/preview/{file_path:path}")
def get_dce_preview(tender_id: str, file_path: str, download: bool = False): return preview_file_from_dce(tender_id, file_path, download)

@app.get("/api/tenders/{tender_id:path}/text/{file_path:path}")
@app.get("/tenders/{tender_id:path}/text/{file_path:path}")
def get_dce_text(tender_id: str, file_path: str): return extract_text_from_dce(tender_id, file_path)

@app.get("/api/tenders/{tender_id:path}/metadata/{file_path:path}")
@app.get("/tenders/{tender_id:path}/metadata/{file_path:path}")
def get_dce_file_metadata(tender_id: str, file_path: str): return get_file_metadata(tender_id, file_path)

@app.get("/api/tenders/{tender_id:path}/raw/{file_path:path}")
@app.get("/tenders/{tender_id:path}/raw/{file_path:path}")
def get_dce_raw_file(tender_id: str, file_path: str, download: bool = False): return get_raw_file(tender_id, file_path, download)


# ═══════════════════════════════════════════════════════════
#  STRUCTURED EXTRACTION & ANALYSIS
# ═══════════════════════════════════════════════════════════

@app.get("/api/tenders/{tender_id:path}/extract/docx/{file_path:path}")
@app.get("/tenders/{tender_id:path}/extract/docx/{file_path:path}")
def extract_docx_endpoint(tender_id: str, file_path: str):
    tender = get_tender_row(tender_id)
    zip_bytes = fetch_zip_bytes(tender_id, tender.get("dce_zip_url"))
    with open_zip(zip_bytes) as zf:
        if file_path not in zf.namelist(): raise HTTPException(404)
        file_bytes = zf.read(file_path)
    if Path(file_path).suffix.lower() != ".docx": raise HTTPException(400, "Not a DOCX file")
    return extract_docx_structured(file_bytes, file_path)

@app.get("/api/tenders/{tender_id:path}/extract/excel/{file_path:path}")
@app.get("/tenders/{tender_id:path}/extract/excel/{file_path:path}")
def extract_excel_endpoint(tender_id: str, file_path: str):
    tender = get_tender_row(tender_id)
    zip_bytes = fetch_zip_bytes(tender_id, tender.get("dce_zip_url"))
    with open_zip(zip_bytes) as zf:
        if file_path not in zf.namelist(): raise HTTPException(404)
        file_bytes = zf.read(file_path)
    ext = Path(file_path).suffix.lower()
    if ext not in [".xlsx", ".xlsm", ".xls"]: raise HTTPException(400)
    return extract_excel_structured(file_bytes, file_path)

@app.get("/api/tenders/{tender_id:path}/analyze/{file_path:path}")
@app.get("/tenders/{tender_id:path}/analyze/{file_path:path}")
def analyze_document_endpoint(tender_id: str, file_path: str):
    tender = get_tender_row(tender_id)
    zip_bytes = fetch_zip_bytes(tender_id, tender.get("dce_zip_url"))
    with open_zip(zip_bytes) as zf:
        if file_path not in zf.namelist(): raise HTTPException(404)
        file_bytes = zf.read(file_path)
    ext = Path(file_path).suffix.lower()
    if ext == ".docx":
        structured = extract_docx_structured(file_bytes, file_path)
        file_type = "docx"
    elif ext in [".xlsx", ".xlsm", ".xls"]:
        structured = extract_excel_structured(file_bytes, file_path)
        file_type = "xlsx" if ext in [".xlsx", ".xlsm"] else "xls"
    else:
        raise HTTPException(400, "Unsupported file type for analysis")
    analysis = analyze_document_with_llm(structured, file_type, Path(file_path).name, tender_id)
    return {"file_path": file_path, "file_type": file_type, "structured_data": structured, "analysis": analysis}


# ═══════════════════════════════════════════════════════════
#  CHATBOT RAG
# ═══════════════════════════════════════════════════════════

@app.post("/api/tenders/{tender_id:path}/chat/index")
@app.post("/tenders/{tender_id:path}/chat/index")
def index_tender_for_chat(tender_id: str):
    try:
        tender = get_tender_row(tender_id)
        if not tender.get("dce_zip_url"): raise HTTPException(404)
        zip_bytes = fetch_zip_bytes(tender_id, tender.get("dce_zip_url"))
        return index_tender_documents(tender_id, zip_bytes=zip_bytes)
    except HTTPException: raise
    except Exception as e: logger.error(f"Chat indexing error: {e}"); traceback.print_exc(); raise HTTPException(500, detail=str(e))

@app.post("/api/tenders/{tender_id:path}/chat/query")
@app.post("/tenders/{tender_id:path}/chat/query")
async def query_tender_chat(tender_id: str, request: dict):
    try:
        question = request.get("question", "")
        if not question: raise HTTPException(400)
        return query_tender_chatbot(tender_ref=tender_id, question=question, chat_history=request.get("chat_history", []), top_k=request.get("top_k", 5))
    except HTTPException: raise
    except Exception as e: logger.error(f"Chat query error: {e}"); traceback.print_exc(); raise HTTPException(500, detail=str(e))

@app.get("/api/tenders/{tender_id:path}/chat/status")
@app.get("/tenders/{tender_id:path}/chat/status")
def get_chat_status(tender_id: str):
    try: return get_chatbot_status(tender_id)
    except Exception as e: logger.error(f"Chat status error: {e}"); raise HTTPException(500, detail=str(e))


# ═══════════════════════════════════════════════════════════
#  MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    print(f"\n{'='*60}\n  CrystalWater Tenders API v6.8\n  http://0.0.0.0:{port}\n  Tenders | Keywords | Scoring | ZIP Viewer | Chatbot | BP Items\n{'='*60}\n")
    uvicorn.run(app, host="0.0.0.0", port=port)