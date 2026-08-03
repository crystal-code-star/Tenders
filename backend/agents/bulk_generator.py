# ============================================================================
# agents/bulk_generator.py - VERSION "LINKEDIN KILLER" (brand-voice aligned)
# CHANGES vs previous version:
#   - Tone/voice rewritten to match the official NT2E & Crystal Water
#     LinkedIn Content Guide: helpful, practical, technically credible,
#     concrete numbers over vague marketing language, real CTA, no filler.
#   - Hashtags/footer swapped for the guide's real hashtag bank.
#   - Hook examples rewritten to match the guide's "result-first" /
#     "question-first" style instead of generic clickbait formulas.
#   - All instructions now explicitly forbid vague words ("state-of-the-art",
#     "world-class") without a number behind them, per the guide's Do/Don't.
#   - Plumbing (infer() calls, image pipeline, storage, scheduling) UNCHANGED.
# ============================================================================

import json
import os
import re
import time
import requests
import traceback
import random
import hashlib
from datetime import datetime, timedelta
from urllib.parse import quote_plus
from tools.hf_llm_tool import infer
from tools.dalle_tool import generate_image_pollinations_direct, build_infographic_prompt
from tools.image_search_tool import (
    find_image_for_topic,
    find_image_for_product,
    download_image,
)
from utils.storage import save_post, get_next_available_id
from utils.image_storage import upload_image_bytes

# ── Company constants ─────────────────────────────────────────────────────────
COMPANY_NAME     = "CrystalWater"
COMPANY_TAGLINE  = "Cadrer vos besoins, vous faciliter l'industrie"
COMPANY_PHONE    = "+212 6 10 10 74 75"
COMPANY_EMAIL    = "contact@crystalwater.ma"

# Hashtag bank pulled directly from the NT2E & Crystal Water LinkedIn Guide (Section 5.3)
DEFAULT_HASHTAGS = (
    "#CrystalWater #IndustrieMaroc #TraitementDeLEau "
    "#QualiteDeLEau #Maintenance #Maroc"
)

# ══════════════════════════════════════════════════════════════════════════════
# BRAND VOICE — pulled from the NT2E & Crystal Water LinkedIn Guide (Section 5.2)
# ══════════════════════════════════════════════════════════════════════════════
BRAND_VOICE_BLOCK = """
═══════════════════════════════════════════════
BRAND VOICE — CRYSTAL WATER (from official brand guide — NON-NEGOTIABLE)
═══════════════════════════════════════════════
Crystal Water is the distribution & equipment arm of the NT2E group in Morocco.
Tagline: "Cadrer vos besoins, vous faciliter l'industrie."

TONE: Helpful, practical, responsive. Crystal Water is "we make your life
easier" — not "we are the leading global expert." Confident but never
boastful. Precise but never cold. Written by someone who has actually
stood next to the equipment, not a marketing intern guessing at jargon.

VOICE RULES (apply to every single post, no exceptions):
1. NEVER use vague marketing language with nothing behind it — banned
   phrases include "state-of-the-art", "solution de pointe", "leader
   incontournable", "qualité supérieure" UNLESS immediately followed by a
   real number, spec, or concrete proof point in the same sentence.
2. EVERY post needs at least one concrete, real detail: a number, a
   capacity, a unit, a timeframe, a named technology, or a specific
   practical sign/symptom the reader can check for themselves. Generic
   filler that could apply to any company in any country is FORBIDDEN.
3. The hook (first 1-2 lines) must work as a stand-alone line with no
   "see more" needed to understand the value — never open with "Nous
   sommes fiers de vous annoncer..." or any self-congratulatory opener.
4. Prefer plain, spoken-language French over stiff corporate French.
   Write like an engineer explaining something useful to a colleague,
   not like a press release.
5. The closing call-to-action must be SPECIFIC: invite a real next step
   (describe your water problem, send your specs, book a diagnostic) —
   never a bare "Contactez-nous dès aujourd'hui !"
6. Emojis are allowed ONLY as visual markers to break up short lists
   (✅ 🔹 ⚠️ 📩) — never as decoration, never replacing real content.
═══════════════════════════════════════════════
"""

# ══════════════════════════════════════════════════════════════════════════════
# ALL_DAY_ANGLES — content + instructions rewritten in Crystal Water's voice
# ══════════════════════════════════════════════════════════════════════════════
ALL_DAY_ANGLES = {
    "Problem": {
        "name": "Problem Awareness",
        "image_style": "real industrial equipment showing visible wear, scale buildup, or corrosion, documentary-style lighting, photorealistic",
        "format": "STORY-DRIVEN",
        "output_structure": (
            "OUTPUT STRUCTURE — SHORT POST, 3 PARAGRAPHS MAXIMUM, NO BULLET POINTS, NO HEADERS:\n"
            "Paragraph 1 (hook): 1-2 sentences. Open with a concrete, specific symptom or situation the reader "
            "can recognize from their own plant — not a vague stat. "
            "Examples: 'Vos canalisations s'entartrent plus vite que prévu ?' or 'Une eau trouble n'est jamais juste un détail esthétique.'\n"
            "Paragraph 2 (body): 2-3 sentences — explain the real mechanism behind the problem and its concrete "
            "consequences (energy cost, equipment lifespan, downtime), with at least one specific number or unit, "
            "written as natural flowing prose, plain spoken French.\n"
            "Paragraph 3 (CTA + liaison): 1-2 sentences — connect the problem to Crystal Water's practical role "
            "(diagnostic, parts, products) and invite the reader to describe their own situation.\n"
            "Then: Footer line. Then: Hashtags line.\n"
            "TOTAL LENGTH: 5-8 sentences maximum for the whole post body.\n"
        ),
        "instruction": (
            "You are a Crystal Water engineer writing a LinkedIn post about a real, recognizable problem: '{topic}'. "
            "Open with a specific, concrete symptom the reader could be experiencing right now — never a generic "
            "statistic-shock opener. Explain the real mechanism and its concrete cost (with one number/unit). "
            "Close by inviting the reader to describe their own water issue so Crystal Water can point them to the "
            "right fix. Plain, practical, spoken French. NO bullet points, NO headers, NO vague marketing words."
        ),
        "hook_examples": {
            "french": [
                "Votre eau laisse des traces blanches sur vos équipements ? C'est probablement le calcaire.",
                "Une eau trouble n'est jamais juste un détail esthétique.",
                "Un filtre encrassé, c'est une panne qui arrive plus vite qu'on ne le pense.",
                "Vos pompes s'usent plus vite que prévu ? La cause est souvent dans l'eau elle-même.",
                "Le tartre ne se voit pas toujours — mais il coûte cher.",
            ],
            "english": [
                "Your equipment showing white limescale traces? That's usually hard water.",
                "Cloudy water is never just a cosmetic detail.",
                "A clogged filter is a breakdown arriving faster than you'd think.",
                "Pumps wearing out faster than expected? The cause is often in the water itself.",
            ],
        },
    },
    "Deep Problem": {
        "name": "Hidden Costs",
        "image_style": "realistic industrial maintenance scene, technician-eye-view of equipment wear, neutral documentary lighting, photorealistic, no people",
        "format": "DATA-DRIVEN",
        "output_structure": (
            "OUTPUT STRUCTURE — SHORT POST, 3 PARAGRAPHS MAXIMUM, NO BULLET POINTS, NO HEADERS:\n"
            "Paragraph 1 (hook): 1-2 sentences — open with a concrete cost reality tied directly to the topic, "
            "stated plainly (not in a 'shocking stat' tabloid tone).\n"
            "Paragraph 2 (body): 2-3 sentences — explain where the hidden cost actually comes from (energy, "
            "downtime, premature replacement) in natural prose, with 1-2 real figures or units integrated naturally.\n"
            "Paragraph 3 (CTA + liaison): 1-2 sentences — connect this cost reality to Crystal Water's preventive "
            "products/diagnostic and invite the reader to get a real assessment of their own setup.\n"
            "Then: Footer line. Then: Hashtags line.\n"
            "TOTAL LENGTH: 5-8 sentences maximum for the whole post body.\n"
        ),
        "instruction": (
            "You are a Crystal Water technical advisor writing about the hidden cost of: '{topic}'. "
            "Open with a plain, credible cost reality — not tabloid-style 'SHOCKING' framing. Explain the real "
            "source of the cost with 1-2 concrete figures. Close by connecting it to Crystal Water's preventive "
            "products and inviting the reader to get their own setup assessed. Plain, practical, spoken French. "
            "NO bullet points, NO headers, NO invented statistics."
        ),
        "hook_examples": {
            "french": [
                "Un équipement entartré, c'est une panne qui coûte plus cher qu'un traitement préventif.",
                "Le coût réel d'un mauvais prétraitement ne se voit pas sur la facture de maintenance — il se voit sur celle de l'électricité.",
                "Remplacer une membrane trop tôt coûte souvent plus cher que l'entretenir correctement.",
                "Un arrêt de production imprévu coûte toujours plus cher qu'un traitement d'eau bien dimensionné.",
            ],
            "english": [
                "A scaled-up system is a breakdown that costs more than prevention would have.",
                "The real cost of poor pretreatment doesn't show on the maintenance budget — it shows on the power bill.",
                "Replacing a membrane too early usually costs more than maintaining it properly.",
            ],
        },
    },
    "Education": {
        "name": "Science & Technology",
        "image_style": "clean realistic technical/laboratory photo or industrial equipment cutaway, neutral lighting, photorealistic, no people, no invented text",
        "format": "EDUCATIONAL",
        "output_structure": (
            "OUTPUT STRUCTURE — SHORT POST, 3 PARAGRAPHS MAXIMUM, NO BULLET POINTS, NO HEADERS:\n"
            "Paragraph 1 (hook): 1-2 sentences — open with a genuine, simple question about how the topic actually "
            "works, the kind a curious plant manager would ask.\n"
            "Paragraph 2 (body): 2-3 sentences — explain the mechanism in plain language with a concrete example "
            "or comparison, including one real data point or unit.\n"
            "Paragraph 3 (CTA + liaison): 1-2 sentences — connect the explanation to where Crystal Water applies "
            "this in practice, and invite questions in the comments.\n"
            "Then: Footer line. Then: Hashtags line.\n"
            "TOTAL LENGTH: 5-8 sentences maximum for the whole post body.\n"
        ),
        "instruction": (
            "You are a Crystal Water technical specialist explaining the real mechanism behind: '{topic}'. "
            "Open with a genuine curiosity question, not a clickbait one. Explain clearly with a real example and "
            "one concrete data point. Close by connecting it to Crystal Water's practical experience and inviting "
            "questions in the comments. Plain, accessible, spoken French — written like an engineer explaining "
            "something useful to a colleague. NO bullet points, NO headers, NO jargon dumps."
        ),
        "hook_examples": {
            "french": [
                "Pourquoi une eau ultra-pure a-t-elle parfois besoin de deux passages d'osmose inverse ?",
                "Comment un floculant transforme-t-il une eau trouble en eau claire ?",
                "Saviez-vous qu'un adoucisseur ne 'filtre' pas le calcaire — il l'échange ?",
                "Comment savoir si votre eau a vraiment besoin d'un prétraitement avant l'osmose inverse ?",
            ],
            "english": [
                "Why does ultra-pure water sometimes need two reverse osmosis passes?",
                "How does a flocculant turn cloudy water clear?",
                "Did you know a softener doesn't 'filter' limescale — it exchanges it?",
            ],
        },
    },
    "Product Focus": {
        "name": "Product Deep Dive",
        "image_style": "realistic product photography of actual industrial water treatment equipment, neutral studio or plant-floor background, professional but unstaged lighting, photorealistic, no invented logos or text",
        "format": "PRODUCT-SPOTLIGHT",
        "output_structure": (
            "OUTPUT STRUCTURE — SHORT POST, 3 PARAGRAPHS MAXIMUM, NO BULLET POINTS, NO HEADERS:\n"
            "Paragraph 1 (hook): 1-2 sentences — name the product/category in the first sentence and the specific "
            "problem it solves, in plain language.\n"
            "Paragraph 2 (body): 2-3 sentences — describe 2-3 real capabilities and their practical benefit, with "
            "at least one metric or technical figure, in natural flowing prose.\n"
            "Paragraph 3 (CTA + liaison): 1-2 sentences — invite the reader to send their specs or describe their "
            "setup so Crystal Water can confirm fit — mention the product name again here.\n"
            "Then: Footer line. Then: Hashtags line.\n"
            "TOTAL LENGTH: 5-8 sentences maximum for the whole post body.\n"
        ),
        "instruction": (
            "You are a Crystal Water product specialist presenting: '{topic}'. "
            "Name the product and the real problem it solves in the first sentence. Describe 2-3 genuine "
            "capabilities with at least one real metric. Close by inviting the reader to send their specs or "
            "describe their setup, mentioning the product name again. Practical, confident, never hype-driven. "
            "NO bullet points, NO headers, NO unsupported superlatives."
        ),
        "hook_examples": {
            "french": [
                "[PRODUIT] : pour les sites qui ne peuvent pas se permettre un arrêt de production.",
                "Besoin d'une solution fiable contre [SUJET] ? Voici [PRODUIT].",
                "[PRODUIT] résout un problème simple : [SUJET], sans complexité d'installation.",
            ],
            "english": [
                "[PRODUCT]: for sites that can't afford a production stop.",
                "Need a reliable fix for [TOPIC]? Meet [PRODUCT].",
                "[PRODUCT] solves one simple problem: [TOPIC], without installation headaches.",
            ],
        },
    },
    "Case Study": {
        "name": "Before & After",
        "image_style": "realistic industrial facility photo, clean well-maintained equipment, neutral natural lighting, photorealistic, no people, no invented logos",
        "format": "CASE-STUDY",
        "output_structure": (
            "OUTPUT STRUCTURE — SHORT POST, 3 PARAGRAPHS MAXIMUM, NO BULLET POINTS, NO HEADERS:\n"
            "Paragraph 1 (hook): 1-2 sentences — set a real, plausible scene: sector, problem faced, with one "
            "concrete metric showing the severity. Anonymize if no real client name is available.\n"
            "Paragraph 2 (body): 2-3 sentences — describe the fix and the result in natural prose, with specific "
            "numbers (%, timeframe, m³, cost avoided).\n"
            "Paragraph 3 (CTA + liaison): 1-2 sentences — connect this outcome to Crystal Water's approach and "
            "invite readers facing something similar to reach out.\n"
            "Then: Footer line. Then: Hashtags line.\n"
            "TOTAL LENGTH: 5-8 sentences maximum for the whole post body.\n"
        ),
        "instruction": (
            "You are a Crystal Water solutions advisor sharing a real or representative case about: '{topic}'. "
            "If no specific real client/number was provided in the context below, write the post with a clearly "
            "marked placeholder like [préciser la capacité] instead of inventing one. Open by describing the "
            "problem and its severity. Describe the result in flowing prose with specific figures. Close by "
            "connecting Crystal Water's approach to this type of challenge. NO bullet points, NO headers, NO "
            "fabricated client names or numbers."
        ),
        "hook_examples": {
            "french": [
                "Un site industriel marocain perdait du temps de production à cause d'un encrassement répété de ses filtres.",
                "Une usine confrontée à un entartrage récurrent de ses chaudières a fini par revoir tout son prétraitement.",
                "Avant : arrêts fréquents pour nettoyage. Après : un cycle de maintenance enfin prévisible.",
            ],
            "english": [
                "A Moroccan industrial site was losing production time to repeated filter clogging.",
                "A plant facing recurring boiler scale issues ended up rethinking its entire pretreatment.",
            ],
        },
    },
    "Technical": {
        "name": "Technical Specifications",
        "image_style": "realistic technical schematic or engineering diagram style, clean blue-on-white industrial drawing aesthetic, no invented brand text",
        "format": "TECHNICAL-DATASHEET",
        "output_structure": (
            "OUTPUT STRUCTURE — SHORT POST, 3 PARAGRAPHS MAXIMUM, NO BULLET POINTS, NO HEADERS:\n"
            "Paragraph 1 (hook): 1-2 sentences — introduce the technical point with the exact topic name and one "
            "real parameter, unit included.\n"
            "Paragraph 2 (body): 2-3 sentences — describe the key technical specifications in natural flowing "
            "prose. Every technical value MUST include a NUMBER and a UNIT (%, mm, m³/h, bar, °C, mg/L, ppm, etc.) "
            "— if a real value isn't available in context, use a clearly marked placeholder rather than inventing one.\n"
            "Paragraph 3 (CTA + liaison): 1-2 sentences — invite engineers/technical buyers to send their specs "
            "for a precise recommendation.\n"
            "Then: Footer line. Then: Hashtags line.\n"
            "TOTAL LENGTH: 5-8 sentences maximum. Every number must have a unit. NO bullet points.\n"
        ),
        "instruction": (
            "You are a Crystal Water process engineer writing a technical brief about: '{topic}'. "
            "Introduce the technical point precisely. Describe key parameters in natural prose — every value MUST "
            "have a number and unit, or a clearly marked placeholder if no real value is given. Close by inviting "
            "technical readers to send their specs for a precise recommendation. Dry, precise, no fluff. "
            "NO bullet points, NO headers, NO invented figures."
        ),
        "hook_examples": {
            "french": [
                "Une membrane d'osmose inverse mal entretenue peut perdre plusieurs points de taux de rejet en quelques mois.",
                "Le dimensionnement d'un adoucisseur dépend d'abord d'un chiffre : la dureté réelle de votre eau, en °TH.",
                "Un mauvais prétraitement réduit directement la durée de vie utile d'une membrane.",
            ],
            "english": [
                "A poorly maintained RO membrane can lose several points of rejection rate within months.",
                "Sizing a softener starts with one number: your water's real hardness, in °TH.",
            ],
        },
    },
    "Comparison": {
        "name": "Why This Solution",
        "image_style": "realistic side-by-side industrial equipment comparison photo, neutral lighting, photorealistic, no invented text overlays",
        "format": "COMPARISON",
        "output_structure": (
            "OUTPUT STRUCTURE — SHORT POST, 3 PARAGRAPHS MAXIMUM, NO BULLET POINTS, NO HEADERS:\n"
            "Paragraph 1 (hook): 1-2 sentences — pose the real comparison question directly.\n"
            "Paragraph 2 (body): 2-3 sentences — compare both approaches across 2-3 real criteria (cost, "
            "efficiency, maintenance) in natural flowing prose, with at least one concrete figure.\n"
            "Paragraph 3 (CTA + liaison): 1-2 sentences — give a clear, honest verdict (it can be 'it depends on "
            "X') and invite the reader to describe their situation for a specific recommendation.\n"
            "Then: Footer line. Then: Hashtags line.\n"
            "TOTAL LENGTH: 5-8 sentences maximum. NO bullet points.\n"
        ),
        "instruction": (
            "You are a Crystal Water technical advisor comparing two real approaches for: '{topic}'. "
            "Open with the comparison question directly. Compare honestly in natural prose with at least one "
            "concrete figure — it's fine if the honest verdict is 'it depends on your situation.' Close by "
            "inviting the reader to describe their setup for a specific recommendation. Objective, no false urgency. "
            "NO bullet points, NO headers, NO inventing a winner just to sound decisive."
        ),
        "hook_examples": {
            "french": [
                "Traitement chimique ou physique : lequel choisir dépend surtout d'un facteur qu'on oublie souvent.",
                "Adoucisseur ou anti-tartre : la bonne question n'est pas laquelle est 'meilleure', mais laquelle correspond à votre eau.",
                "Filtration à sable ou cartouche : le bon choix dépend de la taille des particules à retenir.",
            ],
            "english": [
                "Chemical or physical treatment: the right choice mostly depends on one factor people often miss.",
                "Softener or anti-scale treatment: the real question isn't which is 'better', but which fits your water.",
            ],
        },
    },
    "Engagement": {
        "name": "Community Quiz",
        "image_style": "clean, realistic industrial-themed photo suitable as a quiz background, no invented text or question marks baked into the image",
        "format": "INTERACTIVE-QUIZ",
        "output_structure": (
            "OUTPUT STRUCTURE — SHORT POST, MOSTLY PARAGRAPHS, QUIZ OPTIONS ALLOWED ON SEPARATE LINES:\n"
            "Paragraph 1 (hook): 1-2 sentences — open with a genuine curiosity question about the topic.\n"
            "Quiz block: State the question clearly, then list exactly 4 options each on its own line: A) ... / B) ... / C) ... / D) ...\n"
            "Paragraph 2 (engagement CTA): 1 sentence — invite readers to answer in the comments; Crystal Water "
            "will confirm the right answer there.\n"
            "Then: Footer line. Then: Hashtags line.\n"
            "TOTAL LENGTH: Keep the post short and punchy. The 4 quiz options A) B) C) D) are the only lines "
            "allowed outside of paragraph flow.\n"
        ),
        "instruction": (
            "You are running the Crystal Water LinkedIn page, writing a short engaging quiz post about: '{topic}'. "
            "Open with a genuine curiosity hook in prose. Ask a clear quiz question with 4 real, plausible options "
            "(A, B, C, D) on separate lines — not joke answers. Close with a short sentence inviting comments. "
            "The 4 quiz options are the only exception to the no-list rule. Playful but still credible — this is "
            "still an industrial engineering audience."
        ),
        "hook_examples": {
            "french": [
                "Petit quiz pour les habitués du traitement d'eau : sauriez-vous répondre à celle-ci ?",
                "Question du jour : que se passe-t-il vraiment à l'intérieur d'une membrane d'osmose inverse ?",
                "Testez vos connaissances : quel est le principal signe d'un système d'adoucissement à bout de souffle ?",
            ],
            "english": [
                "Small quiz for the water treatment regulars: would you get this one right?",
                "Question of the day: what's actually happening inside a reverse osmosis membrane?",
            ],
        },
    },
}

DEFAULT_7_DAY_PLAN = [
    {"day_number": 1, "angle": "Problem",       "custom_text": "", "day_products": [], "enabled": True},
    {"day_number": 2, "angle": "Deep Problem",  "custom_text": "", "day_products": [], "enabled": True},
    {"day_number": 3, "angle": "Education",     "custom_text": "", "day_products": [], "enabled": True},
    {"day_number": 4, "angle": "Product Focus", "custom_text": "", "day_products": [], "enabled": True},
    {"day_number": 5, "angle": "Case Study",    "custom_text": "", "day_products": [], "enabled": True},
    {"day_number": 6, "angle": "Technical",     "custom_text": "", "day_products": [], "enabled": True},
    {"day_number": 7, "angle": "Engagement",    "custom_text": "", "day_products": [], "enabled": True},
]


# ══════════════════════════════════════════════════════════════════════════════
# DATA LOADING & PRODUCT SEARCH — UNCHANGED
# ══════════════════════════════════════════════════════════════════════════════

def load_product_data() -> dict | None:
    possible_paths = [
        os.path.join(os.path.dirname(__file__), '..', 'data', 'crystalwater_products_clean.json'),
        os.path.join(os.path.dirname(__file__), '..', 'data', 'nt2e_complete.json'),
        os.path.join(os.getcwd(), 'data', 'crystalwater_products_clean.json'),
        os.path.join(os.getcwd(), 'data', 'nt2e_complete.json'),
    ]
    all_products = []
    for path in possible_paths:
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    products = data.get('products', [])
                    all_products.extend(products)
                    print(f"[bulk_generator] Loaded {len(products)} products from {os.path.basename(path)}")
            except Exception as e:
                print(f"[bulk_generator] Error loading {path}: {e}")
    return {'products': all_products} if all_products else None


def find_product(query: str, data: dict | None) -> dict | None:
    if not data or 'products' not in data:
        return None
    q = query.lower().strip()
    for p in data['products']:
        if p.get('name', '').lower().strip() == q:
            return p
    for p in data['products']:
        product_name = p.get('name', '').lower()
        if len(q) >= 5 and q in product_name:
            generic_words = ['water', 'traitement', 'treatment', 'system', 'système',
                             'industrial', 'industriel', 'industrielle', 'chemical', 'chimique']
            if q not in generic_words:
                return p
    words = q.split()
    best, best_score = None, 0
    for p in data['products']:
        score = 0
        text = ' '.join([
            p.get('name', ''), p.get('description', ''),
            p.get('category', ''), ' '.join(p.get('features', [])),
            p.get('brand', '')
        ]).lower()
        if q in text:           score += 20
        for w in words:
            if w in p.get('name', '').lower():        score += 10
            if w in p.get('description', '').lower(): score += 5
            if w in text:                             score += 2
        if score > best_score:
            best_score, best = score, p
    return best if best_score >= 15 else None


def find_multiple_products(queries: list[str], data: dict | None) -> list[dict]:
    results = []
    for q in queries:
        if q and q.strip():
            p = find_product(q.strip(), data)
            if p:
                results.append(p)
    return results


def extract_product_names_from_text(post_text: str, data: dict | None) -> list[str]:
    if not data or 'products' not in data or not post_text:
        return []
    found_products = []
    post_text_upper = post_text.upper()
    for p in data['products']:
        product_name = p.get('name', '').upper().strip()
        if product_name and len(product_name) >= 5 and product_name in post_text_upper:
            if p.get('name') not in found_products:
                found_products.append(p.get('name'))
    return found_products


def is_product_query(query: str, data: dict | None) -> bool:
    if not data or not query:
        return False
    q_lower = query.lower().strip()
    for p in data['products']:
        if p.get('name', '').lower().strip() == q_lower:
            print(f"  [is_product_query] Exact match: '{p.get('name')}' → PRODUCT")
            return True
    for p in data['products']:
        product_name = p.get('name', '').lower().strip()
        if len(q_lower) >= 5 and q_lower in product_name:
            generic_words = ['water', 'traitement', 'treatment', 'system', 'système',
                             'industrial', 'industriel', 'industrielle', 'chemical', 'chimique',
                             'pollution', 'nappe', 'nappes', 'phréatique', 'phréatiques',
                             'cause', 'causes', 'impact', 'impacts', 'eau', 'eaux', 'plastique',
                             'lutte', 'contre']
            if q_lower not in generic_words:
                print(f"  [is_product_query] Partial match: '{p.get('name')}' ← '{query}' → PRODUCT")
                return True
    print(f"  [is_product_query] No match → THEMATIC TOPIC")
    return False


def build_ai_knowledge_context(topic: str, language: str) -> str:
    lang_name = "French" if language == "french" else "English"
    research_prompt = f"""You are an expert in environmental science and industrial water treatment with 20 years of experience.

I need a detailed technical brief about this EXACT specific topic (and NOTHING else):
TOPIC: "{topic}"

CRITICAL RULES:
1. Write ONLY about "{topic}" - do NOT change the subject
2. Include specific data, statistics, numbers, units, and technical parameters
3. Include causes, mechanisms, technologies, and solutions SPECIFIC to this topic
4. DO NOT generalize to "water treatment" or other broad subjects
5. DO NOT mention any brand names or specific products

⚠️ IMPORTANT: You MUST write your ENTIRE response in {lang_name}. Every word, every sentence must be in {lang_name}. Do not mix languages.

Output ONLY the technical brief about "{topic}" in {lang_name}."""
    try:
        result = infer(research_prompt, max_new_tokens=700, temperature=0.3)
        return result
    except Exception as e:
        return f"Topic: {topic}. Technical information about this specific subject."


def build_product_context(product: dict) -> str:
    features_text = ""
    for f in product.get('features', [])[:10]:
        if f and len(f) > 10 and 'panier' not in f.lower():
            features_text += f"  • {f}\n"
    return f"""
═══════════════════════════════════════════════
PRODUCT PROFILE (CrystalWater database)
═══════════════════════════════════════════════
Name         : {product.get('name', 'N/A')}
Category     : {product.get('category', 'N/A')}
DESCRIPTION: {product.get('description', 'No description available')}
KEY FEATURES: {features_text if features_text else '  (Use description above)'}
═══════════════════════════════════════════════"""


def build_multi_product_context(products: list[dict], fallback_context: str = "") -> str:
    if not products: return fallback_context
    if len(products) == 1: return build_product_context(products[0])
    blocks = []
    for p in products:
        blocks.append(f"--- {p.get('name', 'N/A')} ---\n{p.get('description', '')}")
    return "═══════════════════════════════════════════════\nFEATURED PRODUCTS\n═══════════════════════════════════════════════\n" + "\n".join(blocks)


def build_ai_knowledge_product_context(topic: str, knowledge: str) -> str:
    return f"""
═══════════════════════════════════════════════
TOPIC PROFILE - TECHNICAL DATA TO USE IN YOUR POST
═══════════════════════════════════════════════
EXACT TOPIC: {topic}
KNOWLEDGE BASE:
{knowledge}
═══════════════════════════════════════════════"""


def build_previous_posts_summary(previous_posts: list) -> str:
    if not previous_posts: return ""
    lines = ["\n═══════════════════════════════════════════════",
             "🚨 POSTS ALREADY WRITTEN — CRITICAL: do NOT repeat openings! 🚨"]
    for p in previous_posts:
        post_text = p.get('post_text', '')
        first_sentence = post_text.strip().split('.')[0][:120].replace('\n', ' ')
        day_label = p.get('day_angle', 'Day')
        day_num = p.get('day_number', '?')
        lines.append(f"\n  ❌ [Day {day_num} - {day_label}] DO NOT START WITH:")
        lines.append(f"     \"{first_sentence}...\"")
        lines.append(f"     ⚠️ Your first sentence MUST be DIFFERENT from the above.")
    lines.append("\n═══════════════════════════════════════════════\n")
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# BUILD POST PROMPT — brand voice block injected, otherwise same skeleton
# ══════════════════════════════════════════════════════════════════════════════

def build_post_prompt(product_context: str, topic_name: str, day_number: int,
                     angle_key: str, language: str, custom_text: str,
                     previous_posts: list, is_ai_knowledge: bool = False,
                     day_products: list[dict] | None = None,
                     is_product_topic: bool = False) -> str:
    angle_info = ALL_DAY_ANGLES.get(angle_key, ALL_DAY_ANGLES["Problem"])
    prev_summary = build_previous_posts_summary(previous_posts)
    lang_name = "French" if language == "french" else "English"
    lang_display = "Français" if language == "french" else "English"

    output_structure = angle_info.get('output_structure', '')
    post_format = angle_info.get('format', 'STANDARD')
    instruction = angle_info['instruction'].replace('{topic}', topic_name)

    hook_examples = angle_info.get('hook_examples', {}).get(language, [])
    hook_examples_text = ""
    if hook_examples:
        hook_examples_text = "\n🎣 SUGGESTED OPENING STYLES (pick ONE — do NOT copy exactly, use as inspiration):\n"
        for i, example in enumerate(hook_examples[:3], 1):
            hook_examples_text += f"   {i}. {example}\n"
        hook_examples_text += "   ⚠️ These are EXAMPLES. Write your OWN unique opening inspired by this style.\n"

    if is_product_topic:
        source_note = ""
    else:
        source_note = (
            "⚠️ THIS IS A THEMATIC TOPIC (not a product). "
            "Write about: \"" + topic_name + "\" — DO NOT write generic water treatment content.\n\n"
        )

    custom_section = ""
    if custom_text and custom_text.strip():
        custom_section = f"\n📌 SPECIAL USER INSTRUCTION:\n  \"{custom_text.strip()}\"\n"

    day_product_note = ""
    if day_products and is_product_topic:
        names = ", ".join(p.get('name', '') for p in day_products if p.get('name'))
        if names:
            day_product_note = f"\n📦 FEATURED PRODUCTS FOR TODAY (Day {day_number}): {names}\n"

    if language == "french":
        footer_line = f"{COMPANY_NAME} | {COMPANY_TAGLINE}"
        contact_line = f"📞 {COMPANY_PHONE}  |  ✉️ {COMPANY_EMAIL}"
    else:
        footer_line = f"{COMPANY_NAME} | Shaping your needs, simplifying your industry"
        contact_line = f"📞 {COMPANY_PHONE}  |  ✉️ {COMPANY_EMAIL}"

    forbidden_openings = ""
    if previous_posts:
        forbidden_openings = "\n🚫 FORBIDDEN OPENINGS — You CANNOT start with any of these:\n"
        for p in previous_posts:
            first_sentence = p.get('post_text', '').strip().split('.')[0][:100].replace('\n', ' ')
            forbidden_openings += f"   ❌ \"{first_sentence}...\"\n"
        forbidden_openings += "   ⚠️ Your first sentence MUST be completely different from ALL of the above.\n"

    prompt = f"""You are a senior B2B content strategist for CrystalWater, a Moroccan industrial water treatment company.

{BRAND_VOICE_BLOCK}

╔══════════════════════════════════════════════════════════════╗
║  ASSIGNMENT: Write ONE LinkedIn post
║  TOPIC:      "{topic_name}"
║  DAY NUMBER: {day_number}
║  ANGLE:      {angle_info['name']} (Format: {post_format})
║  LANGUAGE:   {lang_display} — YOU MUST WRITE 100% IN {lang_display}
╚══════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════╗
║  🚨🚨🚨 CRITICAL TOPIC ENFORCEMENT — READ THIS FIRST 🚨🚨🚨  ║
║                                                              ║
║  YOUR TOPIC IS: "{topic_name}"                               ║
║                                                                        
║  RULE ZERO: Every single sentence you write MUST relate     ║
║  DIRECTLY to "{topic_name}".                                 ║
║                                                                        
║  YOU ARE FORBIDDEN from writing about "water treatment"     ║
║  in general. You are FORBIDDEN from writing generic         ║
║  content that could apply to any water topic.                ║
║                                                                        
║  YOUR TOPIC IS: "{topic_name}"                               ║
║  If your first sentence does NOT mention "{topic_name}"     ║
║  or a direct synonym, DELETE IT AND START OVER.              ║
║                                                                        
║  YOUR TOPIC IS: "{topic_name}"                               ║
║                                                                        
╚══════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════╗
║  🚨🚨🚨 ANTI-DUPLICATE RULES — MUST READ 🚨🚨               ║
║                                                              ║
║  This is Day {day_number} of 7. Each day MUST be UNIQUE.     ║
║                                                              ║
║  YOUR FIRST SENTENCE MUST BE DIFFERENT from all previous     ║
║  posts in this campaign.                                    ║
║                                                              ║
║  Vary your openings: use a question, a number, a story,      ║
║  a bold statement, a scenario, a statistic — anything        ║
║  EXCEPT repeating the same pattern.                          ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝

🚨 CRITICAL LANGUAGE RULE:
You MUST write the ENTIRE post in {lang_display}. Every word, every sentence, 
the footer, the hashtags — EVERYTHING must be in {lang_display}.
If you write even ONE word in the wrong language, the post will be REJECTED.
This is NON-NEGOTIABLE.

🎯 YOUR ROLE:
{instruction}

📐 MANDATORY OUTPUT FORMAT (Follow this EXACT structure):
{output_structure}

{hook_examples_text}

{forbidden_openings}

🚨 GLOBAL FORMAT RULES — NON-NEGOTIABLE:
1. SHORT POST: 5 to 8 sentences maximum for the entire post body. Do not exceed this.
2. PARAGRAPH PROSE ONLY: Write as flowing, justified paragraphs — like a professional editorial. NO bullet points (•, -, *, —). NO bold headers or section titles. NO emoji used as list markers (apart from the few allowed by the brand voice rules above).
3. LIAISON SENTENCE REQUIRED: The last paragraph MUST contain a natural sentence connecting the topic to CrystalWater's expertise and inviting the reader to contact the team with a SPECIFIC next step (not a bare "contact us").
4. Numbers and metrics must flow naturally inside the sentences — never in a list.
5. You are writing Day {day_number} of a campaign. Each day has a unique angle.
6. 🚨 YOUR OPENING SENTENCE MUST BE UNIQUE — do NOT copy the style of previous posts.
7. 🚨 NO vague marketing language ("state-of-the-art", "world-class", "leader incontournable") unless immediately backed by a real number or spec in the SAME sentence.
8. 🚨 NEVER invent a client name, stat, or spec that wasn't given to you in the context below. Use a clearly marked placeholder like [préciser] instead.

{source_note}
{product_context}
{prev_summary}
{custom_section}
{day_product_note}

═══════════════════════════════════════════════════════════════
✅ PRE-WRITING VERIFICATION CHECKLIST (Complete BEFORE writing):
═══════════════════════════════════════════════════════════════

☐ 1. Does my first sentence explicitly mention "{topic_name}" or a direct synonym? 
      If NO → REWRITE the first sentence.

☐ 2. Is my first sentence DIFFERENT from all forbidden openings listed above?
      If NO → SCRAP IT and write a completely different opening.

☐ 3. Would my first sentence work for a DIFFERENT topic?
      If YES → It's too generic. REWRITE it to be specific to "{topic_name}".

☐ 4. Is every sentence about "{topic_name}" specifically (not generic water treatment)?
      If NO → DELETE any generic sentence and REWRITE it.

☐ 5. Is my ENTIRE post in {lang_display}?
      If NO → TRANSLATE everything to {lang_display}.

☐ 6. Did I use any banned vague marketing word without a real number/spec right next to it?
      If YES → REMOVE the word or ADD a real number/spec next to it.

☐ 7. Does my closing line propose a SPECIFIC next step (not a bare "contact us")?
      If NO → REWRITE the closing sentence.

═══════════════════════════════════════════════════════════════
📋 CRITICAL RULES (NON-NEGOTIABLE):
═══════════════════════════════════════════════════════════════

1. FOLLOW THE OUTPUT STRUCTURE as 3 short paragraphs maximum
2. Use TECHNICAL DATA from the profile above where available
3. Include at least one SPECIFIC NUMBER or METRIC integrated naturally into a sentence
4. LAST PARAGRAPH must link "{topic_name}" to CrystalWater and invite a SPECIFIC next step
5. End with this EXACT footer on its own line:
   {footer_line}
   {contact_line}
6. FINAL LINE EXACTLY: {DEFAULT_HASHTAGS}
7. LANGUAGE: 100% {lang_display} — NO exceptions, NO mixing languages
8. Output ONLY the LinkedIn post — no explanations, no notes, no preamble
9. TOPIC: Your post is about "{topic_name}". If you write about anything else, you FAIL.
10. 🚨 UNIQUENESS: Your opening sentence MUST be different from all previous posts.
11. 🚨 VOICE: Match Crystal Water's brand voice block above exactly — helpful, practical, concrete, never hype-driven.

🚨 LENGTH CHECK: Count your sentences before submitting. Maximum 8 sentences in the post body.
🚨 TOPIC VERIFICATION: Your post must be about "{topic_name}". NOT about general water treatment.
🚨 ANGLE VERIFICATION: Your post must be a {angle_info['name']} post for Day {day_number}
🚨 LANGUAGE VERIFICATION: Every single character must be in {lang_display}
🚨 UNIQUENESS VERIFICATION: Your opening must NOT resemble any forbidden opening above.
🚨 VOICE VERIFICATION: No unsupported superlatives. Every claim has a number, a unit, or a concrete real-world detail behind it.

═══════════════════════════════════════════════════════════════
🚨 FINAL WARNING: YOUR TOPIC IS "{topic_name}"
   You are FORBIDDEN from writing generic "water treatment" content.
   Every sentence must relate to "{topic_name}".
   Your opening MUST be different from all previous posts.
   Your voice MUST match Crystal Water's brand guide — practical, concrete, never hype.
═══════════════════════════════════════════════════════════════

WRITE THE POST NOW (in {lang_display}, about "{topic_name}", unique opening, short flowing paragraphs, 5-8 sentences, 100% {lang_display}, Crystal Water brand voice):"""

    return prompt


# ══════════════════════════════════════════════════════════════════════════════
# UTILITIES — UNCHANGED
# ══════════════════════════════════════════════════════════════════════════════

def generate_unique_seed() -> str:
    return f"{time.time_ns()}_{random.randint(1000000, 9999999)}_{random.random()}"


def download_and_upload_image(image_url: str, day_id: int) -> str | None:
    """Downloads an image URL and uploads it to storage. Returns the public URL."""
    if not image_url:
        return None
    print(f"  [Upload] Downloading and uploading image...")
    content = download_image(image_url)
    if not content:
        print(f"  [Upload] ✗ Download failed")
        return None
    try:
        result = upload_image_bytes(content, day_id)
        if result:
            print(f"  [Upload] ✓ Success!")
        return result
    except Exception as e:
        print(f"  [Upload] ✗ {str(e)[:80]}")
        return None


# ══════════════════════════════════════════════════════════════════════════════
# IMAGE RETRIEVAL — UNCHANGED (still tries DB → web → AI in that order)
# ══════════════════════════════════════════════════════════════════════════════

def get_initial_image_for_post(post_text: str, topic: str, angle_key: str,
                               day_number: int, day_id: int) -> tuple[str | None, str]:
    """
    Gets the best image for a post, trying sources in priority order:
    1. Product DB image (if product names found in post text)
    2. image_search_tool.find_image_for_product() or find_image_for_topic()
    3. AI generation (Pollinations/Gemini) as last resort
    """
    data = load_product_data()
    product_names = extract_product_names_from_text(post_text, data)
    print(f"  [Image] Products in post text: {product_names if product_names else 'none'}")

    # --- Try product DB image first ---
    if product_names:
        for prod_name in product_names:
            product = find_product(prod_name, data)
            if product and product.get('image_url'):
                uploaded = download_and_upload_image(product['image_url'], day_id)
                if uploaded:
                    return uploaded, f"DB: {prod_name}"

        # --- Try web search for product ---
        for prod_name in product_names:
            product = find_product(prod_name, data)
            web_url = find_image_for_product(prod_name, product)
            if web_url:
                uploaded = download_and_upload_image(web_url, day_id)
                if uploaded:
                    return uploaded, f"Web product: {prod_name}"

    # --- Try web search for topic (now with post_text and day_number for unique images) ---
    web_url = find_image_for_topic(topic, angle_key, post_text=post_text, day_number=day_number)
    if web_url:
        uploaded = download_and_upload_image(web_url, day_id)
        if uploaded:
            return uploaded, f"Web topic: {topic[:60]}"

    # --- AI generation as last resort ---
    print(f"  [Image] 🤖 Falling back to AI generation...")
    try:
        from tools.dalle_tool import generate_image
        ai_product = product_names[0] if product_names else None
        img_result = generate_image(
            prompt=topic, day_id=day_id, topic=topic,
            product=ai_product, angle_key=angle_key,
            day_number=day_number,
            post_text=post_text,
        )
        url = img_result.get("image_url")
        if url:
            return url, build_infographic_prompt(topic, ai_product)
    except Exception as e:
        print(f"  [Image] ✗ AI generation failed: {e}")

    return None, build_infographic_prompt(topic, None)


def regenerate_image_web(post_id: int, topic: str, angle_key: str = "Education",
                          product_name: str = "", product_data: dict = None) -> dict:
    """Regenerates a web-sourced image for an existing post."""
    from utils.storage import get_post
    post = get_post(post_id)
    post_text = post.get('post_text', '') if post else ''
    day_number = post.get('day_number', 1) if post else 1

    data = load_product_data()
    product_names = list(dict.fromkeys(extract_product_names_from_text(post_text, data)))

    image_url = None
    source = None

    # Try product images first
    if product_names:
        for prod_name in product_names[:2]:
            product = find_product(prod_name, data)
            url = find_image_for_product(prod_name, product)
            if url:
                image_url = url
                source = f"Web product: {prod_name}"
                break

    # Fall back to topic search (now with post_text and day_number)
    if not image_url:
        url = find_image_for_topic(topic, angle_key, post_text=post_text, day_number=day_number)
        if url:
            image_url = url
            source = f"Web topic: {topic[:60]}"

    if image_url:
        uploaded = download_and_upload_image(image_url, post_id)
        if uploaded:
            post = get_post(post_id)
            if post:
                post['image_url'] = uploaded
                post['image_prompt'] = source
                save_post(post)
                return {"success": True, "image_url": uploaded, "source": source}

    return {"success": False, "error": "No image found"}


def regenerate_image_ai(post_id: int, topic: str, angle_key: str = "Education",
                        day_number: int = 1) -> dict:
    """Regenerates an AI-generated image for an existing post."""
    from utils.storage import get_post
    post = get_post(post_id)
    post_text = post.get('post_text', '') if post else ''
    data = load_product_data()
    product_names = list(dict.fromkeys(extract_product_names_from_text(post_text, data)))

    ai_topic = product_names[0] if product_names else topic

    unique_seed = f"{post_id}_{day_number}_{time.time_ns()}_{random.randint(1, 999999999)}_{random.random()}"
    seed_hash = hashlib.md5(unique_seed.encode()).hexdigest()[:16]

    try:
        url = generate_image_pollinations_direct(
            topic=ai_topic,
            angle_key=angle_key,
            day_number=day_number,
            cache_buster=unique_seed,
            post_text=post_text,
        )
        if url:
            post = get_post(post_id)
            if post:
                post['image_url'] = url
                post['image_prompt'] = f"AI: {angle_key} D{day_number} S:{seed_hash}"
                save_post(post)
                return {"success": True, "image_url": url, "source": "ai", "seed": seed_hash}
    except Exception as e:
        return {"success": False, "error": str(e)}

    return {"success": False, "error": "AI generation failed"}


def calculate_publish_dates(days_config: list, schedule_config: dict) -> dict:
    start_date = schedule_config.get('start_date')
    start_time = schedule_config.get('start_time', '09:00')
    if not start_date: return {}
    try:
        start_datetime = datetime.fromisoformat(f"{start_date}T{start_time}:00")
        enabled_days = sorted([d for d in days_config if d.get('enabled', True)],
                              key=lambda x: x['day_number'])
        schedule = {}
        for index, day in enumerate(enabled_days):
            schedule[day['day_number']] = (start_datetime + timedelta(days=index)).isoformat()
        return schedule
    except Exception as e:
        print(f"  ⚠ Schedule error: {e}")
        return {}


# ══════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT — UNCHANGED
# ══════════════════════════════════════════════════════════════════════════════

def run_campaign(days_config: list, product_query: str, language: str = "english",
                schedule_config: dict = None) -> list:
    print(f"\n{'='*60}")
    print(f"[Agent 1] Campaign START")
    print(f"  TOPIC: '{product_query}'")
    print(f"  Language: {language}")
    print(f"{'='*60}")

    publish_schedule = {}
    if schedule_config:
        publish_schedule = calculate_publish_dates(days_config, schedule_config)

    data = load_product_data()
    is_product_topic = is_product_query(product_query, data)

    print(f"  🔍 is_product={is_product_topic}")

    topic_name = product_query
    print(f"  📝 TOPIC: '{topic_name}'")

    if is_product_topic:
        product = find_product(product_query, data)
        if product:
            print(f"  ✓ PRODUCT found: {product.get('name')}")
            campaign_context = build_product_context(product)
            is_ai_knowledge = False
        else:
            print(f"  ⚠ Product not found → treating as TOPIC")
            knowledge = build_ai_knowledge_context(product_query, language)
            campaign_context = build_ai_knowledge_product_context(product_query, knowledge)
            is_ai_knowledge = True
            is_product_topic = False
    else:
        print(f"  ⚠ THEMATIC TOPIC: '{product_query}'")
        knowledge = build_ai_knowledge_context(product_query, language)
        campaign_context = build_ai_knowledge_product_context(product_query, knowledge)
        is_ai_knowledge = True

    active_days = sorted([d for d in days_config if d.get('enabled', True)],
                         key=lambda x: x['day_number'])
    print(f"  Days: {len(active_days)} enabled | Mode: {'Product' if is_product_topic else 'Thematic'}")

    results, previous_posts = [], []

    for day_cfg in active_days:
        day_num = day_cfg['day_number']
        angle_key = day_cfg.get('angle', 'Problem')
        custom_text = day_cfg.get('custom_text', '')
        day_product_names = day_cfg.get('day_products', [])
        next_id = get_next_available_id()
        angle_name = ALL_DAY_ANGLES.get(angle_key, {}).get('name', angle_key)
        angle_format = ALL_DAY_ANGLES.get(angle_key, {}).get('format', 'STANDARD')
        scheduled_for = publish_schedule.get(day_num)
        created_at = datetime.now().isoformat()

        day_products_resolved = []
        day_context = campaign_context
        day_topic = topic_name

        if day_product_names and data and is_product_topic:
            day_products_resolved = find_multiple_products(day_product_names, data)
            if day_products_resolved:
                day_context = build_multi_product_context(day_products_resolved, campaign_context)
                day_topic = ", ".join(p.get('name', '') for p in day_products_resolved)
            else:
                knowledge = build_ai_knowledge_context(" ".join(day_product_names), language)
                day_context = build_ai_knowledge_product_context(" ".join(day_product_names), knowledge)
                day_topic = " ".join(day_product_names)

        print(f"\n  ── Day {day_num} [{angle_name}] [{angle_format}] id={next_id} ──")
        print(f"  📝 Generating post about: '{day_topic}'")
        print(f"  🌐 Language: {language}")

        try:
            prompt = build_post_prompt(
                product_context=day_context,
                topic_name=day_topic,
                day_number=day_num,
                angle_key=angle_key,
                language=language,
                custom_text=custom_text,
                previous_posts=previous_posts,
                is_ai_knowledge=is_ai_knowledge and not day_products_resolved,
                day_products=day_products_resolved,
                is_product_topic=is_product_topic
            )
            post_text = infer(prompt, max_new_tokens=900, temperature=0.82).strip()
            if len(post_text) < 50: raise ValueError("Response too short")
            if "#CrystalWater" not in post_text:
                post_text += f"\n\n{DEFAULT_HASHTAGS}"

            first_sentence = post_text.strip().split('.')[0][:100]
            print(f"  📍 Opening: \"{first_sentence}...\"")
            print(f"  ✓ {len(post_text)} chars")

            image_url, img_prompt = get_initial_image_for_post(
                post_text=post_text,
                topic=day_topic,
                angle_key=angle_key,
                day_number=day_num,
                day_id=next_id
            )

            post = {
                "id": next_id,
                "topic": product_query,
                "post_text": post_text,
                "image_prompt": img_prompt,
                "image_url": image_url,
                "status": "pending",
                "scheduled_for": scheduled_for,
                "posted_at": None,
                "created_at": created_at,
                "linkedin_post_id": None,
                "language": language,
                "day_angle": angle_key,
                "day_number": day_num,
                "custom_text": custom_text,
                "product_name": day_topic,
                "ai_knowledge_mode": is_ai_knowledge and not day_products_resolved,
                "day_products": day_product_names,
                "is_product_topic": is_product_topic
            }
            save_post(post)
            results.append(post)
            previous_posts.append(post)
            print(f"  ✓ Saved as Day {day_num}")

        except Exception as exc:
            print(f"  ✗ ERROR: {exc}")
            traceback.print_exc()

    return results


def run(product_query: str, language: str = "english", user_request: str = "") -> list:
    plan = [dict(d, custom_text=user_request) for d in DEFAULT_7_DAY_PLAN]
    return run_campaign(plan, product_query, language)


def run_legacy(topic: str) -> list:
    return run(topic, "english", "")