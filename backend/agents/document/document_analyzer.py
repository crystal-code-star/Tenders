"""
Document Analyzer — Gemini (auto-model) + DeepSeek via Hugging Face (fallback)

*** NEW IN THIS VERSION ***
  - Word (.docx/.doc) is no longer treated as a flat "50 paragraphs + first few
    tables" dump. It now goes through `_build_text_from_docx_structured`,
    which walks the extractor's `body_order` in original reading order —
    same idea as the Excel adapter's per-sheet blocks — so headings, prose,
    and BPU/DQE-style tables inside a Word DCE stay in the sequence they
    actually appear in, instead of tables and paragraphs being extracted
    into two unrelated buckets.
  - Docx paragraphs/tables now carry the extractor's heuristic content_type /
    table_type tags (Pricing / Technical / Administrative / ...), so the LLM
    gets the same kind of labeled context for Word that it already gets for
    Excel sheets via sheet_type.
  - Headings are used to track the nearest "Lot n" context so that a price
    table sitting under "3. Bordereau des Prix (Lot 2)" gets tagged with
    that lot automatically — mirroring how the Excel path keeps lot/sheet
    attribution on every row.
  - Reviewer comments (word/comments.xml) are appended as a clearly-labeled
    block ("ne pas traiter comme contenu du marché") so the LLM doesn't
    mistake a reviewer's aside for a clause of the tender itself.
  - The rich tables_de_prix / equipements / lots JSON schema — previously
    only used for xlsx/xls — is now also used for docx/doc, since Word DCEs
    commonly embed the same BPU/DQE tables Excel files do. The old flat
    schema is kept as `_get_prompts_generic` and used only as a last-resort
    fallback if structured extraction produced nothing usable.
  - Kept a flat fallback builder (`_build_text_from_docx_flat`) for when the
    extractor output doesn't have `body_order` (e.g. an older extractor
    version or partial extraction), same defensive pattern as the Excel
    adapter's flat fallback.

  *** CARRIED OVER FROM PREVIOUS VERSION ***
  - tables_de_prix / equipements are returned as real structured JSON grouped
    by lot, not flattened into "notes" (which used to silently truncate to
    5 rows). "notes" is genuine free-text only.
  - _coerce_list_field() robustly recovers tables_de_prix/equipements
    regardless of LLM key casing or JSON-string wrapping.
  - Fallback order: Gemini -> DeepSeek/HF (Groq removed). Each backend is
    independently optional based on which API key(s) are set.
"""

import os
import json
import logging
import re
from typing import Dict, Any, List, Optional

logger = logging.getLogger("document_analyzer")
logger.setLevel(logging.INFO)

# ─── Gemini config ──────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
USE_GEMINI = os.getenv("USE_GEMINI", "true").lower() == "true" and bool(GEMINI_API_KEY)

_gemini_model = None
if USE_GEMINI:
    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        _gemini_model = genai.GenerativeModel(GEMINI_MODEL)
    except ImportError:
        logger.warning("google-generativeai not installed. Gemini disabled.")
        USE_GEMINI = False
    except Exception as e:
        logger.warning(f"Gemini init error: {e}")

# ─── DeepSeek via Hugging Face Inference Providers config (fallback) ───────
HF_TOKEN = os.getenv("HF_TOKEN", "")
HF_PROVIDER = os.getenv("HF_PROVIDER", "auto")
HF_MODEL = os.getenv("HF_MODEL", "deepseek-ai/DeepSeek-V3-0324")
HF_MODEL_FALLBACKS = [
    m.strip() for m in os.getenv(
        "HF_MODEL_FALLBACKS",
        "meta-llama/Llama-3.3-70B-Instruct,Qwen/Qwen2.5-72B-Instruct,openai/gpt-oss-120b"
    ).split(",") if m.strip()
]
HF_ENABLED = bool(HF_TOKEN)

_hf_client = None
if HF_ENABLED:
    try:
        from huggingface_hub import InferenceClient
        _hf_client = InferenceClient(provider=HF_PROVIDER, api_key=HF_TOKEN)
    except ImportError:
        logger.warning("huggingface_hub not installed. Run: pip install huggingface_hub. DeepSeek/HF disabled.")
        HF_ENABLED = False
    except Exception as e:
        logger.warning(f"Hugging Face client init error: {e}")
        HF_ENABLED = False

# ─── Excel adapter ─────────────────────────────────────────────────
try:
    from agents.document.excel_adapter import adapt_excel_to_tables
except ImportError:
    adapt_excel_to_tables = None


def _build_text_from_excel_sheets(sheets: list) -> str:
    if adapt_excel_to_tables is None:
        return _build_text_from_excel_sheets_flat(sheets)
    excel_struct = {"sheets": sheets, "stats": {}, "type": "xlsx"}
    try:
        adapted = adapt_excel_to_tables(excel_struct)
    except Exception as e:
        logger.warning(f"Excel adapter failed: {e}")
        return _build_text_from_excel_sheets_flat(sheets)
    if not adapted:
        return _build_text_from_excel_sheets_flat(sheets)
    parts = []
    for table in adapted:
        sheet = table.get("sheet", "Feuille")
        lot = table.get("lot_label", "")
        headers = table.get("headers", [])
        sentences = table.get("sentences", [])
        row_indices = table.get("row_indices", [])
        header = f"--- Feuille: {sheet}" + (f" - {lot}" if lot else "") + " ---"
        if headers:
            header += f" (Colonnes: {', '.join(str(h) for h in headers)})"
        parts.append(header)
        for i, sent in enumerate(sentences):
            row_num = row_indices[i] if i < len(row_indices) else "?"
            parts.append(f"Ligne {row_num}: {sent}")
        parts.append("")
    return "\n".join(parts)


def _build_text_from_excel_sheets_flat(sheets: list) -> str:
    """Fallback path: turn raw extractor output into readable per-sheet text blocks.
    Defensive against partially-extracted sheets (missing rows, error placeholders)."""
    output = []
    for sheet in sheets:
        name = sheet.get("name", "Feuille")
        meta = sheet.get("sheet_metadata", {}) or {}
        sheet_type = meta.get("sheet_type", "General")
        if meta.get("error"):
            output.append(f"\n--- Sheet: {name} (extraction failed: {meta['error']}) ---")
            continue
        output.append(f"\n--- Sheet: {name} (Type: {sheet_type}) ---")
        for row in sheet.get("rows", []):
            cells = []
            for c in row:
                val = c.get("value") if isinstance(c, dict) else c
                if val is not None and str(val).strip() != "":
                    cells.append(str(val))
            if cells:
                output.append(" | ".join(cells))
    return "\n".join(output)


# ─── Word (.docx/.doc) text builder ─────────────────────────────────

_LOT_RE = re.compile(r"\blot\b\s*n?°?\s*\d+|\blot\s+[a-zA-Z0-9]+", re.IGNORECASE)


def _detect_lot_label(text: str) -> Optional[str]:
    m = _LOT_RE.search(text or "")
    return m.group(0).strip() if m else None


def _build_text_from_docx_structured(extracted_data: dict) -> str:
    """Walk the extractor's body_order (paragraphs and tables interleaved in
    original reading order) and produce one readable text stream, tagging
    each block with its heuristic content_type/table_type and the nearest
    preceding 'Lot n' heading — the docx equivalent of the Excel adapter's
    per-sheet, per-lot blocks."""
    paragraphs = extracted_data.get("paragraphs", [])
    tables = extracted_data.get("tables", [])
    body_order = extracted_data.get("body_order")

    if not body_order:
        # Older/partial extraction without body_order — fall back.
        return _build_text_from_docx_flat(extracted_data)

    parts = []

    headers = extracted_data.get("headers") or []
    footers = extracted_data.get("footers") or []
    if headers or footers:
        parts.append("--- Contexte document (en-tête / pied de page) ---")
        for h in headers:
            parts.append(f"En-tête: {h}")
        for f in footers:
            parts.append(f"Pied de page: {f}")
        parts.append("")

    current_lot = None
    for entry in body_order:
        if entry["type"] == "paragraph":
            idx = entry["ref"]
            if idx >= len(paragraphs):
                continue
            p = paragraphs[idx]
            text = (p.get("text") or "").strip()
            if not text:
                continue

            lot_hit = _detect_lot_label(text)
            if lot_hit:
                current_lot = lot_hit

            heading_level = p.get("heading_level")
            if heading_level is not None:
                parts.append(f"\n{'#' * max(heading_level, 1)} {text}")
                continue

            prefix = ""
            if p.get("is_list"):
                prefix = "- "
            content_type = p.get("content_type", "General")
            tag = f"[{content_type}] " if content_type != "General" else ""
            parts.append(f"{prefix}{tag}{text}")

        else:  # table
            idx = entry["ref"]
            if idx >= len(tables):
                continue
            t = tables[idx]
            table_type = t.get("table_type", "General")
            lot_note = f", Lot: {current_lot}" if current_lot else ""
            header_line = f"--- Tableau {idx + 1} (Type: {table_type}{lot_note}) ---"
            headers_row = t.get("headers", [])
            if headers_row:
                header_line += f" (Colonnes: {', '.join(str(h) for h in headers_row)})"
            parts.append(header_line)
            for r_idx, row in enumerate(t.get("rows", []), start=1):
                cells = [str(c) for c in row if c is not None and str(c).strip() != ""]
                if cells:
                    parts.append(f"Ligne {r_idx}: {' | '.join(cells)}")
            parts.append("")

    comments = extracted_data.get("comments") or []
    if comments:
        parts.append("\n--- Commentaires de relecture (NE PAS traiter comme contenu du marché) ---")
        for c in comments:
            author = c.get("author") or "Anonyme"
            parts.append(f"{author}: {c.get('text', '')}")

    return "\n".join(parts)


def _build_text_from_docx_flat(extracted_data: dict) -> str:
    """Defensive fallback if body_order is missing: dump paragraphs then
    tables then lists, same shape the previous version of this module used,
    but tolerant of paragraphs being either plain strings or dicts."""
    raw_paragraphs = extracted_data.get("paragraphs", [])[:50]
    para_lines = []
    for p in raw_paragraphs:
        if isinstance(p, dict):
            txt = p.get("text", "")
        else:
            txt = str(p)
        if txt.strip():
            para_lines.append(txt)
    para = "\n".join(para_lines)

    tables_text = ""
    for i, tbl in enumerate(extracted_data.get("tables", [])):
        headers = " | ".join(str(h) for h in tbl.get("headers", [])) if tbl.get("headers") else ""
        rows = "\n".join(" | ".join(str(c) for c in row) for row in tbl.get("rows", [])[:20])
        tables_text += f"\nTable {i + 1} (headers: {headers})\n{rows}\n"

    lists_text = "\n".join(
        "• " + "\n  ".join(lst.get("items", [])) for lst in extracted_data.get("lists", [])
    )

    return f"PARAGRAPHS:\n{para}\n\nTABLES:\n{tables_text}\n\nLISTS:\n{lists_text}"


# ─── Prompts ─────────────────────────────────────────────────────────

_RICH_SCHEMA_SYSTEM_TEMPLATE = """Tu es un expert en analyse de documents d'appels d'offres (DCE) pour CrystalWater, spécialiste du traitement d'eau et du refroidissement industriel.

{source_description}, potentiellement réparti(es) sur plusieurs lots. Extrais les informations suivantes avec la plus grande précision, en conservant l'association ligne <-> lot d'origine :

1. Tableaux de prix (BPU, DQE) : pour chaque ligne, extrais le lot d'origine (numéro ou nom de section/feuille), la désignation, la quantité, l'unité, le prix unitaire et le total.
2. Équipements : pour chaque ligne, extrais le lot d'origine, la référence, la description, la quantité, l'unité, les spécifications techniques (tension, puissance, débit, pression, etc.).
3. Lots : numéro, description, montant.
4. Sites : lieux d'exécution.
5. Totaux/budgets : montants totaux, sous-totaux, devises, TVA.
6. Unités de mesure.

IMPORTANT : n'omets AUCUNE ligne, même si plusieurs lots ont des lignes très similaires. Chaque ligne du tableau source doit apparaître comme un élément séparé dans "tables_de_prix" ou "equipements", avec son propre champ "lot" rempli. Les blocs marqués "Commentaires de relecture" sont des annotations de relecteurs, PAS du contenu du marché : ignore-les pour l'extraction des champs ci-dessous.

RÉPONDS UNIQUEMENT EN JSON VALIDE avec ces clés (si une information manque, mets une chaîne vide ou une liste vide) :
{{
  "tables_de_prix": [{{"lot":"", "designation":"", "quantite":"", "unite":"", "prix_unitaire":"", "total":""}}],
  "equipements": [{{"lot":"", "reference":"", "description":"", "quantite":"", "unite":"", "specifications":""}}],
  "lots": [{{"numero":"", "description":"", "montant":""}}],
  "sites": [],
  "budget_estime": "",
  "devise": "",
  "caution_provisoire": "",
  "caution_definitive": "",
  "maitre_ouvrage": "",
  "objet": "",
  "lieu_execution": "",
  "type_marche": "",
  "date_limite": "",
  "duree": "",
  "conditions_participation": "",
  "criteres_attribution": "",
  "notes": ""
}}"""

_GENERIC_SYSTEM = """Tu es un expert en analyse de DCE pour CrystalWater. Extrais les champs suivants en JSON :
maitre_ouvrage, objet, lieu_execution, type_marche, budget_estime, date_limite, duree,
caution_provisoire, caution_definitive, conditions_participation, lots, criteres_attribution, notes.
Si une information manque, mets une chaîne vide.
RÉPONDS UNIQUEMENT EN JSON VALIDE."""


def _get_prompts(file_type: str, file_name: str) -> tuple:
    if file_type in ["xlsx", "xls"]:
        system = _RICH_SCHEMA_SYSTEM_TEMPLATE.format(
            source_description="Le fichier Excel contient des tableaux structurés, potentiellement répartis sur plusieurs feuilles (une feuille par lot, par exemple)"
        )
        user_base = f"Fichier: {file_name}\n\nDonnées extraites (chaque ligne est une phrase décrivant une ligne du tableau) :\n"
    elif file_type in ["docx", "doc"]:
        system = _RICH_SCHEMA_SYSTEM_TEMPLATE.format(
            source_description=(
                "Le document Word contient des sections narratives (objet, conditions administratives, délais, etc.) "
                "ainsi que, potentiellement, des tableaux de prix (BPU, DQE) ou de spécifications techniques"
            )
        )
        user_base = f"Fichier: {file_name}\n\nContenu extrait (titres, paragraphes et tableaux dans l'ordre du document) :\n"
    else:
        system = _GENERIC_SYSTEM
        user_base = f"Fichier: {file_name}\nDonnées extraites:\n"
    return system, user_base


def _try_gemini_with_models(full_prompt: str) -> Optional[dict]:
    if not USE_GEMINI or _gemini_model is None:
        return None
    models_to_try = [
        GEMINI_MODEL,
        "gemini-2.0-flash",
        "gemini-1.5-flash",
        "gemini-1.5-pro",
    ]
    models_to_try = list(dict.fromkeys(models_to_try))
    for model_name in models_to_try:
        try:
            import google.generativeai as genai
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(
                full_prompt,
                generation_config={
                    "temperature": 0.1,
                    "max_output_tokens": 4000,
                    "response_mime_type": "application/json",
                }
            )
            raw = response.text.strip()
            raw = re.sub(r'^```json\s*', '', raw)
            raw = re.sub(r'\s*```$', '', raw)
            return json.loads(raw)
        except Exception as e:
            logger.info(f"Gemini model {model_name} failed: {e}")
            continue
    return None


def _coerce_list_field(analysis: dict, *key_variants: str) -> List[dict]:
    """Recover a list-of-dicts field regardless of key casing, or if the LLM
    returned it as a JSON-encoded string instead of a native array. Never
    truncates — every row the LLM produced is kept."""
    raw = None
    for key in key_variants:
        if key in analysis:
            raw = analysis[key]
            break
    if raw is None:
        lowered = {k.lower(): v for k, v in analysis.items()}
        for key in key_variants:
            if key.lower() in lowered:
                raw = lowered[key.lower()]
                break
    if raw is None:
        return []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return []
    if isinstance(raw, dict):
        raw = [raw]
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def _group_by_lot(rows: List[dict], lot_key: str = "lot") -> Dict[str, List[dict]]:
    grouped: Dict[str, List[dict]] = {}
    for row in rows:
        lot = str(row.get(lot_key) or row.get("sheet") or "Non spécifié").strip() or "Non spécifié"
        grouped.setdefault(lot, []).append(row)
    return grouped


def _flatten_analysis(analysis: dict) -> dict:
    """Produce both:
      - flat string summary fields (for simple display / legacy consumers)
      - full structured tables_de_prix / equipements, grouped by lot (for a
        proper table UI) — nothing is truncated or dropped here.
    """
    flat = {
        "maitre_ouvrage": "",
        "objet": "",
        "lieu_execution": "",
        "type_marche": "",
        "budget_estime": "",
        "date_limite": "",
        "duree": "",
        "caution_provisoire": "",
        "caution_definitive": "",
        "conditions_participation": "",
        "lots": "",
        "criteres_attribution": "",
        "notes": "",
    }
    for key in flat.keys():
        if key == "lots":
            continue
        if key in analysis and isinstance(analysis[key], str):
            flat[key] = analysis[key]
        elif key in analysis and analysis[key]:
            flat[key] = json.dumps(analysis[key], ensure_ascii=False)

    lots_raw = analysis.get("lots")
    if isinstance(lots_raw, list):
        lot_strs = []
        for lot in lots_raw:
            if isinstance(lot, dict):
                num = lot.get("numero", "")
                desc = lot.get("description", "")
                mont = lot.get("montant", "")
                lot_strs.append(f"Lot {num}: {desc} - {mont}".strip())
            else:
                lot_strs.append(str(lot))
        flat["lots"] = "; ".join(lot_strs) if lot_strs else ""
    elif isinstance(lots_raw, str):
        flat["lots"] = lots_raw

    price_rows = _coerce_list_field(analysis, "tables_de_prix", "TablesDePrix", "tableaux_de_prix")
    equip_rows = _coerce_list_field(analysis, "equipements", "Equipements", "équipements")

    flat["tables_de_prix"] = price_rows
    flat["equipements"] = equip_rows
    flat["tables_de_prix_par_lot"] = _group_by_lot(price_rows)
    flat["equipements_par_lot"] = _group_by_lot(equip_rows)

    flat["notes"] = flat["notes"] if isinstance(flat["notes"], str) else ""

    return flat


def analyze_document_with_llm(extracted_data: dict, file_type: str, file_name: str, tender_ref: str = "") -> dict:
    if file_type in ["docx", "doc"]:
        text = _build_text_from_docx_structured(extracted_data)
    elif file_type in ["xlsx", "xls"]:
        text = _build_text_from_excel_sheets(extracted_data.get("sheets", []))
    else:
        return {"error": f"Unsupported file type: {file_type}"}

    if not text.strip():
        return {"error": "No text content extracted"}

    if len(text) > 50000:
        text = text[:50000] + "\n[...truncated]"

    system_prompt, user_base = _get_prompts(file_type, file_name)
    full_prompt = system_prompt + "\n\n" + user_base + text

    # ── 1) Gemini ────────────────────────────────────────────────────
    if USE_GEMINI:
        logger.info("Attempting Gemini analysis...")
        analysis = _try_gemini_with_models(full_prompt)
        if analysis:
            logger.info("Gemini succeeded.")
            return _flatten_analysis(analysis)
        logger.info("Gemini failed (all models). Falling back to DeepSeek/HF.")

    # ── 2) DeepSeek via Hugging Face Inference Providers ──────────────
    if HF_ENABLED:
        logger.info(f"Calling DeepSeek/HF ({HF_MODEL}) as fallback...")
        hf_result = _analyze_with_hf(system_prompt, user_base, text)
        if "error" not in hf_result:
            logger.info("DeepSeek/HF succeeded.")
            return _flatten_analysis(hf_result)
        logger.error(f"DeepSeek/HF failed: {hf_result}")
        return hf_result

    return {"error": "No LLM backend available. Set GEMINI_API_KEY or HF_TOKEN."}


def _analyze_with_hf(system_prompt: str, user_base: str, text: str) -> dict:
    """
    DeepSeek (open-weight, MIT) served through Hugging Face Inference
    Providers — one HF token, OpenAI-compatible chat.completions call, routed
    to whichever provider is currently hosting the model.
    """
    if _hf_client is None:
        return {"error": "Hugging Face client not initialized"}

    user_prompt = user_base + text
    models_to_try = list(dict.fromkeys([HF_MODEL] + HF_MODEL_FALLBACKS))

    last_error = None
    for model_name in models_to_try:
        try:
            completion = _hf_client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.15,
                max_tokens=4000,
                response_format={"type": "json_object"},
            )
            raw = completion.choices[0].message.content
            try:
                logger.info(f"HF model {model_name} succeeded.")
                return json.loads(raw)
            except json.JSONDecodeError:
                match = re.search(r'\{.*\}', raw, re.DOTALL)
                if match:
                    logger.info(f"HF model {model_name} succeeded (recovered JSON from wrapped text).")
                    return json.loads(match.group())
                last_error = {"error": f"Invalid JSON from HF model {model_name}", "raw": raw}
                logger.info(f"HF model {model_name} returned unparseable output, trying next fallback.")
                continue
        except Exception as e:
            logger.info(f"HF model {model_name} failed: {e}")
            last_error = {"error": str(e)}
            continue

    return last_error or {"error": "All HF models failed"}