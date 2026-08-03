"""
zip_chatbot.py — Chatbot for DCE Documents + Database Search (v5.1)
=====================================================================
Uses Groq for answers. Searches the current tender + related DB entries.
FIXED: Now filters by tender_ref to only return results for the opened DCE.
"""

import os
import re
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import json

import requests
from fastapi import HTTPException

logger = logging.getLogger("zip_chatbot")

# ─── Environment variables ────────────────────────────────
SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "") or os.getenv("SUPABASE_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
TENDERS_TABLE = os.getenv("TENDERS_TABLE", "tenders_3")

# ─── Supabase helpers ─────────────────────────────────────
def _sb_headers() -> dict:
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }

def _sb_get(table: str, params: dict = None) -> List[dict]:
    if not SUPABASE_URL or not SUPABASE_KEY:
        return []
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/{table}",
            headers=_sb_headers(),
            params=params or {},
            timeout=15
        )
        r.raise_for_status()
        return r.json() or []
    except Exception as e:
        logger.error(f"[CHATBOT] Supabase GET error ({table}): {e}")
        return []

# ─── Text normalization ───────────────────────────────────
def _normalize_text(text: str) -> str:
    """Normalise le texte pour la recherche (accents, casse)."""
    if not text:
        return ""
    t = text.lower()
    replacements = {
        'é': 'e', 'è': 'e', 'ê': 'e', 'ë': 'e',
        'à': 'a', 'â': 'a', 'ä': 'a',
        'ù': 'u', 'û': 'u', 'ü': 'u',
        'ô': 'o', 'ö': 'o',
        'î': 'i', 'ï': 'i',
        'ç': 'c'
    }
    for k, v in replacements.items():
        t = t.replace(k, v)
    return t

# ═══════════════════════════════════════════════════════════
#  TENDER-SPECIFIC SEARCH (seulement l'AO courant)
# ═══════════════════════════════════════════════════════════

def get_tender_by_ref(tender_ref: str) -> Optional[Dict]:
    """
    Récupère les informations complètes d'un appel d'offre par sa référence.
    """
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None
    
    try:
        results = _sb_get(TENDERS_TABLE, {
            "reference": f"eq.{tender_ref}",
            "select": "*",
            "limit": "1"
        })
        return results[0] if results else None
    except Exception as e:
        logger.error(f"[CHATBOT] Error fetching tender {tender_ref}: {e}")
        return None


def search_similar_tenders(tender_ref: str, question: str, limit: int = 5) -> List[Dict]:
    """
    Cherche des AO similaires dans la base (même acheteur, même lieu, mots-clés communs).
    Utile pour trouver des AO connexes au DCE courant.
    """
    current_tender = get_tender_by_ref(tender_ref)
    
    if not current_tender:
        return []
    
    # Extraire les mots-clés de l'AO courant pour trouver des AO similaires
    keywords = []
    
    objet = current_tender.get("objet", "")
    acheteur = current_tender.get("acheteur_public", "")
    lieu = current_tender.get("lieu_execution", "")
    categorie = current_tender.get("categorie", "")
    
    # Extraire des mots significatifs (plus de 3 caractères)
    all_text = f"{objet} {categorie}"
    words = re.findall(r'\b[a-zéèêëàâäùûüôöîïç]{4,}\b', _normalize_text(all_text))
    # Prendre les mots les plus longs (plus spécifiques)
    keywords = sorted(set(words), key=len, reverse=True)[:5]
    
    results = []
    
    if keywords:
        try:
            # Construire un filtre OR avec les mots-clés
            conditions = []
            for word in keywords[:3]:
                conditions.append(f'objet.ilike.*{word}*')
            
            or_filter = ",".join(conditions[:10])
            
            if or_filter:
                similar = _sb_get(TENDERS_TABLE, {
                    "select": "reference,objet,acheteur_public,lieu_execution,date_limite_remise_plis,status,relevance_score",
                    "or": f"({or_filter})",
                    "reference": f"neq.{tender_ref}",  # Exclure l'AO courant
                    "limit": str(limit),
                    "order": "relevance_score.desc"
                })
                
                for t in similar:
                    text_to_search = _normalize_text(f"{t.get('objet','')}")
                    match_count = sum(1 for word in keywords if word in text_to_search)
                    relevance = min(100, match_count * 20 + (t.get('relevance_score', 0) // 5))
                    
                    results.append({
                        "type": "similar_tender",
                        "reference": t.get("reference"),
                        "title": t.get("objet", "")[:200],
                        "acheteur": t.get("acheteur_public", ""),
                        "lieu": t.get("lieu_execution", ""),
                        "deadline": t.get("date_limite_remise_plis"),
                        "status": t.get("status"),
                        "relevance": relevance,
                        "source": "tenders_3"
                    })
        except Exception as e:
            logger.error(f"[CHATBOT] Similar tenders search error: {e}")
    
    return results


def format_tender_context(tender: Dict, similar_tenders: List[Dict] = None) -> str:
    """Formate les informations de l'AO courant pour le contexte du LLM."""
    parts = []
    
    parts.append("=== APPEL D'OFFRES ACTUEL ===\n")
    
    if tender.get("objet"):
        parts.append(f"Objet : {tender['objet']}")
    if tender.get("reference"):
        parts.append(f"Référence : {tender['reference']}")
    if tender.get("acheteur_public"):
        parts.append(f"Acheteur : {tender['acheteur_public']}")
    if tender.get("lieu_execution"):
        parts.append(f"Lieu d'exécution : {tender['lieu_execution']}")
    if tender.get("procedure"):
        parts.append(f"Procédure : {tender['procedure']}")
    if tender.get("categorie"):
        parts.append(f"Catégorie : {tender['categorie']}")
    if tender.get("date_limite_remise_plis"):
        parts.append(f"Date limite : {tender['date_limite_remise_plis']}")
    if tender.get("status"):
        parts.append(f"Statut : {tender['status']}")
    
    # Ajouter le résumé DCE s'il existe
    if tender.get("dce_resume"):
        parts.append(f"\n--- Résumé du DCE ---\n{tender['dce_resume']}")
    
    # Ajouter les AO similaires
    if similar_tenders:
        parts.append(f"\n\n=== APPELS D'OFFRES SIMILAIRES ({len(similar_tenders)} trouvés) ===\n")
        for i, t in enumerate(similar_tenders[:3], 1):
            parts.append(f"\n{i}. {t['title']}")
            if t.get('reference'): parts.append(f"   Référence: {t['reference']}")
            if t.get('acheteur'): parts.append(f"   Acheteur: {t['acheteur']}")
            if t.get('lieu'): parts.append(f"   Lieu: {t['lieu']}")
            if t.get('deadline'): parts.append(f"   Date limite: {t['deadline']}")
    
    return "\n".join(parts)


# ═══════════════════════════════════════════════════════════
#  ANSWER GENERATION (Groq)
# ═══════════════════════════════════════════════════════════

def generate_answer(
    question: str,
    tender: Dict,
    similar_tenders: List[Dict] = None,
    chat_history: List[Dict] = None
) -> Dict:
    """Génère une réponse en utilisant Groq avec le contexte de l'AO courant."""
    if not GROQ_API_KEY:
        raise HTTPException(500, "GROQ_API_KEY not configured")

    context = format_tender_context(tender, similar_tenders)

    system_prompt = f"""Tu es un assistant expert pour CrystalWater, une entreprise marocaine spécialisée dans le traitement d'eau, 
l'assainissement et le refroidissement industriel.

Tu analyses l'appel d'offres actuellement affiché dans l'interface.

RÈGLES :
1. Base-toi UNIQUEMENT sur les informations de l'appel d'offres fournies ci-dessous.
2. Si l'information n'est pas présente dans le contexte, dis "Cette information n'est pas disponible dans le DCE".
3. Sois précis et concis.
4. Réponds en français.
5. Ne mentionne que les informations TROUVÉES dans le contexte fourni.
6. Ne fais JAMAIS référence à d'autres appels d'offres sauf s'ils sont listés dans la section "APPELS D'OFFRES SIMILAIRES".

{context}"""

    messages = [{"role": "system", "content": system_prompt}]
    if chat_history:
        messages.extend(chat_history[-6:])
    messages.append({"role": "user", "content": question})

    try:
        r = requests.post(
            GROQ_API_URL,
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": GROQ_MODEL,
                "messages": messages,
                "temperature": 0.3,
                "max_tokens": 1500
            },
            timeout=60
        )

        if r.status_code == 200:
            answer = r.json()["choices"][0]["message"]["content"]

            # Sources
            sources = [{
                "type": "current_tender",
                "reference": tender.get("reference"),
                "title": tender.get("objet", "")[:150]
            }]
            
            if similar_tenders:
                for t in similar_tenders[:3]:
                    sources.append({
                        "type": "similar_tender",
                        "reference": t.get("reference"),
                        "title": t.get("title", "")[:150],
                        "relevance": t.get("relevance", 0)
                    })

            return {
                "answer": answer,
                "sources": sources,
                "similar_count": len(similar_tenders) if similar_tenders else 0,
                "model": GROQ_MODEL
            }

        raise HTTPException(502, f"Groq error: {r.status_code} - {r.text[:200]}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[CHATBOT] Groq error: {e}")
        raise HTTPException(500, f"Erreur Groq: {e}")


# ═══════════════════════════════════════════════════════════
#  MAIN FUNCTIONS
# ═══════════════════════════════════════════════════════════

def index_tender_documents(tender_ref: str, zip_bytes: bytes = None, zip_url: str = None) -> Dict:
    """
    Vérifie que l'AO existe dans la base de données.
    """
    tender = get_tender_by_ref(tender_ref)
    
    if tender:
        return {
            "tender_ref": tender_ref,
            "status": "ok",
            "message": "AO trouvé dans la base de données - assistant prêt.",
            "has_dce_resume": bool(tender.get("dce_resume")),
            "chunks_created": 0,
            "time_seconds": 0
        }
    
    return {
        "tender_ref": tender_ref,
        "status": "warning",
        "message": "AO non trouvé dans la base. Vérifiez la référence.",
        "chunks_created": 0,
        "time_seconds": 0
    }


def query_tender_chatbot(
    tender_ref: str,
    question: str,
    chat_history: List[Dict] = None,
    top_k: int = 5,
    search_db: bool = True
) -> Dict:
    """
    Query the chatbot about the CURRENT tender only.
    
    Args:
        tender_ref: Reference of the current tender
        question: User's question
        chat_history: Previous messages
        top_k: Number of similar tenders to find
        search_db: Whether to search for similar tenders
    
    Returns:
        Dict with answer and sources
    """
    if not question or not question.strip():
        return {
            "answer": "Veuillez poser une question sur cet appel d'offres.",
            "sources": [],
            "similar_count": 0,
            "model": GROQ_MODEL
        }

    # 1. Récupérer l'AO courant
    tender = get_tender_by_ref(tender_ref)
    
    if not tender:
        return {
            "answer": f"Je n'ai pas trouvé l'appel d'offres avec la référence '{tender_ref}' dans la base de données.",
            "sources": [],
            "similar_count": 0,
            "model": GROQ_MODEL
        }

    # 2. Chercher des AO similaires (optionnel)
    similar_tenders = []
    if search_db:
        similar_tenders = search_similar_tenders(tender_ref, question, limit=top_k)

    # 3. Générer la réponse basée UNIQUEMENT sur l'AO courant
    return generate_answer(question, tender, similar_tenders, chat_history)


def get_chatbot_status(tender_ref: str) -> Dict:
    """
    Vérifie le statut du chatbot pour un tender.
    """
    tender = get_tender_by_ref(tender_ref)
    
    return {
        "indexed": tender is not None,
        "ready": tender is not None,
        "message": "Assistant prêt - analyse du DCE courant" if tender else "AO non trouvé",
        "has_dce_resume": bool(tender.get("dce_resume")) if tender else False,
        "tender_ref": tender_ref
    }