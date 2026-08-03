"""
agents/campaign_planner.py  —  Stage A: Campaign Brief Builder
═══════════════════════════════════════════════════════════════════
NO FALLBACK VERSION — LLM must succeed or raise an error.
"""

from __future__ import annotations

import json
import os
import re

from tools.hf_llm_tool import infer
from agents.bulk_generator import (
    ALL_DAY_ANGLES,
    COMPANY_NAME,
)


MAX_INSTRUCTION_CHARS = 600

_NT2E_NOISE = {
    'PRODUITSCHIMIQUES', 'piècesde rechange', 'systèmede refrodissement',
    'PRODUITSET SERVICES',
}

_THEMATIC_INDICATORS = [
    'traitement', 'treatment', 'eau', 'water', 'pollution', 'corrosion',
    'tartre', 'scale', 'nappe', 'phréatique', 'groundwater', 'plastique',
    'plastic', 'industrie', 'industrial', 'maroc', 'morocco', 'membrane',
    'osmose', 'osmosis', 'filtration', 'désinfection', 'disinfection',
    'rejet', 'waste', 'recyclage', 'recycling', 'efficace', 'efficient',
    'gestion', 'management', 'qualité', 'quality', 'coût', 'cost',
]


def _load_all_catalog_data() -> dict:
    possible_base_paths = [
        os.path.join(os.path.dirname(__file__), '..', 'data'),
        os.path.join(os.getcwd(), 'data'),
    ]

    crystalwater_products: list[dict] = []
    nt2e_services: list[dict] = []

    for base in possible_base_paths:
        cw_path = os.path.join(base, 'crystalwater_products_clean.json')
        if os.path.exists(cw_path) and not crystalwater_products:
            try:
                with open(cw_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                crystalwater_products = data.get('products', [])
                print(f"[Planner] CrystalWater: {len(crystalwater_products)} products")
            except Exception as e:
                print(f"[Planner] CrystalWater load error: {e}")

        nt2e_path = os.path.join(base, 'nt2e_complete.json')
        if os.path.exists(nt2e_path) and not nt2e_services:
            try:
                with open(nt2e_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                raw_services = data.get('services', [])
                nt2e_services = [
                    s for s in raw_services
                    if s.get('name', '').strip() not in _NT2E_NOISE
                    and len(s.get('description', '')) > 200
                ]
                print(f"[Planner] NT2E services: {len(nt2e_services)} entries")
            except Exception as e:
                print(f"[Planner] NT2E load error: {e}")

    return {
        'crystalwater_products': crystalwater_products,
        'nt2e_services': nt2e_services,
    }


def _is_thematic_brief(brief: str) -> bool:
    brief_lower = brief.lower().strip()
    indicator_count = sum(1 for word in _THEMATIC_INDICATORS if word in brief_lower)
    return indicator_count >= 2


def _score_entry(entry: dict, query_words: list[str]) -> int:
    name = entry.get('name', '').lower()
    desc = entry.get('description', '').lower()
    cat = entry.get('category', '').lower()
    feats = ' '.join(
        f for f in entry.get('features', [])
        if isinstance(f, str) and len(f) > 5 and 'panier' not in f.lower()
    ).lower()
    full = f"{name} {cat} {desc[:400]} {feats}"

    score = 0
    for w in query_words:
        if w in name:
            score += 12
        if w in cat:
            score += 8
        if w in desc[:300]:
            score += 4
        if w in full:
            score += 2
    return score


def _find_matches(terms: list[str], catalog: dict) -> tuple[list[dict], list[dict]]:
    words = [
        w.lower() for t in terms
        for w in t.split()
        if len(w) > 2
    ]
    if not words:
        return [], []

    scored_cw = sorted(
        [(p, _score_entry(p, words)) for p in catalog['crystalwater_products']],
        key=lambda x: -x[1]
    )
    scored_nt2e = sorted(
        [(s, _score_entry(s, words)) for s in catalog['nt2e_services']],
        key=lambda x: -x[1]
    )

    matched_cw = [p for p, s in scored_cw if s >= 5][:3]
    matched_nt2e = [s for s, sc in scored_nt2e if sc >= 3][:3]
    return matched_cw, matched_nt2e


def _build_matched_context(cw_products: list[dict], nt2e_services: list[dict], is_thematic: bool = False) -> str:
    lines = []

    if cw_products and not is_thematic:
        lines.append("MATCHED CRYSTALWATER PRODUCTS (from database):")
        for p in cw_products:
            feats = [
                f for f in p.get('features', [])[:5]
                if isinstance(f, str) and len(f) > 10 and 'panier' not in f.lower()
                and 'MAD' not in f and '0,00' not in f
            ]
            feat_str = " | ".join(feats[:3]) if feats else "—"
            lines.append(
                f"\n• {p.get('name', '?')} [{p.get('category', '?')}]\n"
                f"  {p.get('description', '')[:180]}\n"
                f"  Key benefits: {feat_str}"
            )

    if nt2e_services and not is_thematic:
        lines.append("\nMATCHED NT2E PROCESS KNOWLEDGE (domain context):")
        for s in nt2e_services:
            desc = (s.get('short_description') or s.get('description', ''))[:220]
            desc = re.sub(r'\s+', ' ', desc).strip()
            apps = s.get('applications', [])
            app_str = ", ".join(apps[:4]) if apps else ""
            lines.append(
                f"\n• {s.get('name', '?')} [{s.get('category', '?')}]\n"
                f"  {desc}"
                + (f"\n  Applications: {app_str}" if app_str else "")
            )

    if not lines:
        return "(This is a thematic topic — DO NOT mention specific products in the instructions)"

    return "\n".join(lines)


def _build_catalog_overview(catalog: dict, is_thematic: bool = False) -> str:
    if is_thematic:
        return "(Thematic topic — use general industry knowledge, DO NOT reference specific product names)"

    lines = ["CRYSTALWATER PRODUCT PORTFOLIO (sample by category):"]
    cats: dict[str, list[str]] = {}
    for p in catalog['crystalwater_products'][:100]:
        cat = p.get('category', 'OTHER')
        cats.setdefault(cat, []).append(p.get('name', ''))
    for cat, names in list(cats.items())[:8]:
        sample = ", ".join(names[:3])
        suffix = "…" if len(names) > 3 else ""
        lines.append(f"  • {cat}: {sample}{suffix}")

    if catalog['nt2e_services']:
        lines.append("\nNT2E TECHNOLOGY / PROCESS AREAS AVAILABLE:")
        for s in catalog['nt2e_services'][:12]:
            lines.append(f"  • {s.get('name', '?')} ({s.get('category', '')})")

    return "\n".join(lines)


def _build_planner_prompt(
    brief: str,
    matched_context: str,
    catalog_overview: str,
    language: str,
    angle_keys: list[str],
    is_thematic: bool = False,
) -> str:
    lang_name = "French" if language == "french" else "English"
    angle_list = "\n".join(f"  • {k}" for k in angle_keys)

    thematic_rule = ""
    if is_thematic:
        thematic_rule = (
            "\n🚨 CRITICAL RULE — THEMATIC TOPIC:\n"
            "This is a THEMATIC topic (not a product campaign).\n"
            "The day_instructions MUST focus on the THEME itself.\n"
            "DO NOT mention any specific product names (like WATER DROP, MAKS, SM, etc.).\n"
            "DO NOT suggest product deep-dives or product spotlights.\n"
            "Keep all instructions focused on the general topic/theme only.\n"
            "Use general industry knowledge, not product catalog data.\n"
        )

    return f"""You are a senior B2B content strategist for {COMPANY_NAME},
a Moroccan industrial water treatment company.

A campaign manager provided this brief:
  "{brief}"

{matched_context}

{catalog_overview}
{thematic_rule}
YOUR TASK — build a complete multi-day campaign structure. Return a JSON object with these keys:

1. "campaign_subject"
   One line (max 120 chars) — the overall campaign theme/title.
   Write in {lang_name}.

2. "global_context"
   A SHORT block (max 400 chars) with shared context:
   • Target audience (role + industry + region: Morocco/MENA)
   • Core theme/pain point from the brief
   • Tone: expert, practical, data-backed
   • DO NOT list specific product names — focus on the theme
   Write in {lang_name}.

3. "day_instructions"
   An object where each key is one of these angles:
{angle_list}
   Each value is a SPECIFIC instruction string (2-4 sentences, max {MAX_INSTRUCTION_CHARS} chars).
   { "DO NOT mention specific product names. Focus on the THEME: " + brief if is_thematic else "Mention relevant products from catalog if applicable." }
   Each instruction must:
   • Have a clear subject line (1 sentence)
   • Reference the brief's topic SPECIFICALLY
   • Be COMPLETELY UNIQUE per angle — NEVER repeat the same text
   • Include at least one specific technical term, number, or data point related to the topic

   Angle-specific guidance:
   - "Problem": Hook by quantifying the pain with local context (Morocco/MENA). Use specific statistics about the topic.
   - "Deep Problem": Reveal hidden costs. Use specific financial numbers related to the topic.
   - "Education": Explain the science behind the topic simply. Use analogies.
   - "Product Focus": {"Explain general solution approaches for the theme (NO specific product names)" if is_thematic else "Deep-dive into specific product benefits"}.
   - "Case Study": Before/after scenario with measurable results about the topic.
   - "Technical": Specs, parameters, industry standards specific to the topic.
   - "Comparison": Compare two approaches for the topic (e.g. chemical vs physical). Fair, not salesy.
   - "Engagement": Quiz, poll, or question about the topic to drive comments.

4. "products_found" (array of strings)
   List any matched product names (empty array if thematic topic).

5. "services_found" (array of strings)
   List any matched service names (empty array if thematic topic).

OUTPUT RULES:
- Return ONLY valid JSON. No markdown fences, no preamble, no trailing text.
- Every angle in the input list MUST have a day_instruction.
- Every instruction MUST be UNIQUE — do NOT copy-paste the same text.
- Every instruction MUST reference the topic "{brief}" specifically.
- Never invent product specs — use only data from the catalog sections above.

OUTPUT FORMAT:
{{
  "campaign_subject": "...",
  "global_context": "...",
  "day_instructions": {{
    "Problem": "Sujet: [topic] — [specific instruction about problem angle]...",
    "Education": "Sujet: [topic] — [specific instruction about education angle]..."
  }},
  "products_found": [],
  "services_found": []
}}"""


def _validate_and_clean(
    campaign_subject,
    global_context,
    day_instructions: dict,
    angle_keys: list[str],
    is_thematic: bool = False,
) -> tuple[str, str, dict]:
    if isinstance(campaign_subject, list):
        campaign_subject = " ".join(str(x) for x in campaign_subject)
    subject = str(campaign_subject or "").strip()[:120]

    if isinstance(global_context, list):
        context = "\n".join(str(x).strip() for x in global_context if str(x).strip())
    else:
        context = str(global_context or "").strip()
    context = context[:400]

    if not isinstance(day_instructions, dict):
        raise ValueError(f"day_instructions must be a dict, got {type(day_instructions)}")

    product_pattern = re.compile(
        r'\b[A-Z]{2,}\s*\d{2,}\b|\bWATER\s*(DROP|NET)\s*\d+\b|\bMAKS\s*\d+\b|\bSM\s*\d+\b|\bNT\s*\d+\b',
        re.IGNORECASE
    )

    clean_instructions = {}
    for key in angle_keys:
        val = day_instructions.get(key, "")
        if isinstance(val, list):
            val = "\n".join(str(x).strip() for x in val if str(x).strip())

        if not val or not str(val).strip():
            raise ValueError(f"Missing day_instruction for angle: {key}")

        cleaned = str(val).strip()[:MAX_INSTRUCTION_CHARS]
        if is_thematic:
            cleaned = product_pattern.sub('solutions adaptées', cleaned)
        clean_instructions[key] = cleaned

    # Vérifier que toutes les instructions sont uniques
    values = list(clean_instructions.values())
    if len(values) != len(set(values)):
        raise ValueError("day_instructions contain duplicates — all must be unique per angle")

    return subject, context, clean_instructions


def plan_campaign(
    brief: str,
    language: str = "english",
    angle_keys: list[str] | None = None,
) -> dict:
    print(f"\n[Planner] Brief: '{brief[:80]}' | Lang: {language}")

    if not brief or not brief.strip():
        raise ValueError("Brief is empty — cannot plan campaign without a topic")

    active_angles = angle_keys if angle_keys else list(ALL_DAY_ANGLES.keys())
    is_thematic = _is_thematic_brief(brief)
    print(f"  📍 Thematic topic: {is_thematic}")

    catalog = _load_all_catalog_data()
    raw_terms = [t.strip() for t in re.split(r"[,;]", brief) if t.strip()]
    matched_cw, matched_nt2e = _find_matches(raw_terms, catalog)

    if is_thematic:
        print(f"  🚫 Thematic mode: ignoring product matches")
        matched_cw = []
        matched_nt2e = []

    product_names = [p.get('name', '') for p in matched_cw]
    service_names = [s.get('name', '') for s in matched_nt2e]
    print(f"  CW matched: {product_names or 'none'}")
    print(f"  NT2E matched: {service_names or 'none'}")

    matched_context = _build_matched_context(matched_cw, matched_nt2e, is_thematic)
    catalog_overview = _build_catalog_overview(catalog, is_thematic)

    prompt = _build_planner_prompt(
        brief=brief.strip(),
        matched_context=matched_context,
        catalog_overview=catalog_overview,
        language=language,
        angle_keys=active_angles,
        is_thematic=is_thematic,
    )

    print("  [Planner] Calling LLM...")
    raw = infer(prompt, max_new_tokens=1200, temperature=0.45)
    print(f"  [Planner] Got {len(raw)} chars")

    clean = re.sub(r"```(?:json)?|```", "", raw).strip()
    match = re.search(r"\{.*\}", clean, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object in LLM output. Raw: {raw[:300]}")

    parsed = json.loads(match.group())
    campaign_subject = parsed.get("campaign_subject", "")
    global_context = parsed.get("global_context", "")
    day_instructions = parsed.get("day_instructions", {})

    campaign_subject, global_context, day_instructions = _validate_and_clean(
        campaign_subject, global_context, day_instructions, active_angles, is_thematic
    )

    print(f"  [Planner] Done. {len(day_instructions)} day instructions")
    for k, v in day_instructions.items():
        print(f"    • {k}: {v[:80]}...")

    return {
        "campaign_subject": campaign_subject,
        "global_context": global_context,
        "day_instructions": day_instructions,
        "products_found": product_names,
        "services_found": service_names,
        "used_ai_fallback": False,
    }