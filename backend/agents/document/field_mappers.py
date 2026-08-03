"""
field_mappers.py — Enhanced extraction for Avis & RC fields
Key improvements:
- Multi-strategy date detection (4 strategies)
- Table format support for Word documents
- Moroccan AO specific patterns
- Date validation to prevent false matches
- Debug logging showing which pattern matched
"""

import re
import logging
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger("field_mappers")

# Lines that indicate institutional header text (NOT the Objet)
_INSTITUTION_LINE_RE = re.compile(
    r'^(office\s+national|onee|branche\s+eau|direction\s+r[ée]gionale|'
    r'direction\s+provinciale|r[ée]gie|commune|minist[eè]re)',
    re.IGNORECASE
)

_AVIS_TITLE_RE = re.compile(r"avis\s+d[’']?\s*appel\s+d[’']?\s*offres", re.IGNORECASE)


def _extract_objet_positional(text: str) -> str:
    """
    Objet often has no label — it's the paragraph immediately preceding
    the 'AVIS D'APPEL D'OFFRES...' title line.
    """
    lines = [l.strip() for l in text.split("\n")]

    title_idx = None
    for i, line in enumerate(lines):
        if _AVIS_TITLE_RE.search(line):
            title_idx = i
            break

    if title_idx is None:
        return ""

    collected = []
    i = title_idx - 1
    while i >= 0:
        line = lines[i]
        if not line:
            i -= 1
            continue
        if _INSTITUTION_LINE_RE.search(line):
            break
        collected.insert(0, line)
        i -= 1
        if len(collected) >= 4:
            break

    objet = " ".join(collected).strip()
    return objet


# ──────────────────────────────────────────────────────────────────────
# ENHANCED DATE EXTRACTION
# ──────────────────────────────────────────────────────────────────────

def _looks_like_date_or_datetime(text: str) -> bool:
    """
    Validate that extracted text looks like a date or datetime.
    Prevents matching unrelated numbers.
    """
    if not text or len(text) < 5:
        return False
    
    date_patterns = [
        r'\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}',  # 18/03/2026, 18-03-2026
        r'\d{1,2}\s+(?:janvier|f[ée]vrier|mars|avril|mai|juin|'
        r'juillet|ao[ûu]t|septembre|octobre|novembre|d[ée]cembre)\s+\d{4}',  # 18 Mars 2026
        r'\d{4}[/\-\.]\d{1,2}[/\-\.]\d{1,2}',  # 2026/03/18
    ]
    
    for pattern in date_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    
    return False


def _clean_date_value(value: str) -> str:
    """Clean up extracted date string for presentation."""
    value = re.sub(r'\s+', ' ', value).strip()
    value = value.rstrip('.,;:')
    # Remove heure locale references
    value = re.sub(r'\s*(?:heure\s+locale|\(heure\s+locale\)|HL|GMT[+-]\d+)\s*$', '', value, flags=re.IGNORECASE)
    return value.strip()


def _extract_date_soumission(text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract submission date using multi-strategy approach.
    Returns: (date_string, method_used) or (None, None)
    
    Strategies in priority order:
    1. Labeled patterns (Date limite : XX/XX/XXXX)
    2. Contextual patterns (avant le XX/XX/XXXX)
    3. Proximity search (find date near keywords)
    4. Last resort (find any date near document keywords)
    """
    
    # ─── STRATEGY 1: Labeled date patterns ──────────────────────────
    labeled_patterns = [
        # French AO standard phrases with colon
        (r'Date\s+limit[ée]\s+de\s+(?:remise|soumission|d[ée]p[ôo]t)\s*(?:des\s+(?:offres|plis|dossiers))?\s*[:;]\s*([^\n|]{5,60})',
         "Date limite de remise:"),
        
        (r'Date\s+et\s+heure\s+limit[ée]s?\s*(?:de\s+(?:remise|soumission|d[ée]p[ôo]t))?\s*[:;]\s*([^\n|]{5,60})',
         "Date et heure limite:"),
        
        (r'Date\s+de\s+(?:soumission|remise|d[ée]p[ôo]t)\s*(?:des\s+(?:offres|plis))?\s*[:;]\s*([^\n|]{5,60})',
         "Date de soumission:"),
        
        (r'Date\s+limit[ée]\s*[:;]\s*([^\n|]{5,60})',
         "Date limite:"),
        
        (r'D[ée]lai\s+de\s+(?:soumission|remise|d[ée]p[ôo]t)\s*[:;]\s*([^\n|]{5,60})',
         "Délai de soumission:"),
        
        # Séance d'ouverture
        (r'S[ée]ance\s+d[’\']?\s*ouverture\s+des\s+plis\s*[:;]\s*([^\n|]{5,60})',
         "Séance d'ouverture:"),
        
        (r'Ouverture\s+des\s+plis\s*[:;]\s*([^\n|]{5,60})',
         "Ouverture des plis:"),
        
        # Remise des offres
        (r'Remise\s+des\s+offres?\s*[:;]\s*([^\n|]{5,60})',
         "Remise des offres:"),
        
        (r'D[ée]p[ôo]t\s+des\s+(?:offres|plis|dossiers)\s*[:;]\s*([^\n|]{5,60})',
         "Dépôt des offres:"),
        
        # Table cell patterns (Word tables become " | Label | Value | ")
        (r'\|\s*Date\s+limit[ée]\s*(?:de\s+(?:remise|soumission|d[ée]p[ôo]t))?\s*\|\s*([^|\n]{5,60})\s*\|',
         "Table: Date limite"),
        
        (r'\|\s*Date\s+de\s+(?:soumission|remise)\s*\|\s*([^|\n]{5,60})\s*\|',
         "Table: Date de soumission"),
        
        (r'\|\s*Date\s+et\s+heure\s+limit[ée]s?\s*\|\s*([^|\n]{5,60})\s*\|',
         "Table: Date et heure"),
        
        (r'\|\s*D[ée]lai\s*\|\s*([^|\n]{5,60})\s*\|',
         "Table: Délai"),
    ]
    
    for pattern, method in labeled_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value = match.group(1).strip()
            value = re.sub(r'\s+', ' ', value)
            value = value.rstrip('.,;:')
            
            if _looks_like_date_or_datetime(value):
                logger.info(f"   ✅ Date found [{method}]: {value}")
                return value, method
    
    # ─── STRATEGY 2: Contextual patterns ────────────────────────────
    contextual_patterns = [
        # "remise des offres ... avant le DATE à HEURE"
        (r'(?:remise|soumission|d[ée]p[ôo]t)\s+des?\s+(?:offres|plis|dossiers)[^\n]{0,80}?(?:avant\s+le\s+|au\s+plus\s+tard\s+le\s+)(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}[^\n]{0,30})',
         "avant le [date]"),
        
        # "avant le DATE" simple
        (r'avant\s+le\s+(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}[^\n]{0,30})',
         "avant le [date] simple"),
        
        # "au plus tard le DATE"
        (r'au\s+plus\s+tard\s+le\s+(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}[^\n]{0,30})',
         "au plus tard le [date]"),
        
        # "le DATE à HEURE" 
        (r'le\s+(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})\s*(?:à|a)\s*(\d{1,2}\s*(?:h|heures?|H)[^\n]{0,15})',
         "le [date] à [heure]"),
        
        # "le DATE" near submission keywords
        (r'(?:soumission|remise|d[ée]p[ôo]t|ouverture)[^\n]{0,40}?le\s+(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})',
         "[keyword] le [date]"),
        
        # Month name: "18 Mars 2026" or "18 mars 2026 à 11h00"
        (r'(?:avant\s+le\s+|le\s+|au\s+plus\s+tard\s+le\s+)?'
         r'(\d{1,2})\s+(janvier|f[ée]vrier|mars|avril|mai|juin|juillet|ao[ûu]t|septembre|octobre|novembre|d[ée]cembre)\s+(\d{4})'
         r'(?:\s*(?:à|a)\s*(\d{1,2}\s*(?:h|heures?|H)[^\n]{0,10}))?',
         "mois [date]"),
        
        # Just date+time pattern when near keywords
        (r'(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}\s*(?:à|a)\s*\d{1,2}\s*(?:h|heures?|H))',
         "[date] à [heure]"),
    ]
    
    for pattern, method in contextual_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            groups = [g for g in match.groups() if g]
            value = " ".join(groups).strip()
            value = re.sub(r'\s+', ' ', value)
            
            if _looks_like_date_or_datetime(value):
                logger.info(f"   ✅ Date found [{method}]: {value}")
                return value, method
    
    # ─── STRATEGY 3: Proximity search ────────────────────────────────
    date_pattern = r'(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}(?:\s*(?:à|a)\s*\d{1,2}\s*(?:h|heures?|H))?)'
    
    keyword_patterns = [
        r'date\s+limit[ée]',
        r'date\s+de\s+soumission',
        r'date\s+de\s+remise',
        r's[ée]ance\s+d[’\']?ouverture',
        r'remise\s+des\s+offres',
        r'd[ée]p[ôo]t\s+des\s+plis',
        r'd[ée]lai\s+de\s+soumission',
    ]
    
    for kw_pattern in keyword_patterns:
        kw_match = re.search(kw_pattern, text, re.IGNORECASE)
        if kw_match:
            start = kw_match.start()
            search_region = text[start:start+300]
            date_match = re.search(date_pattern, search_region)
            if date_match:
                value = date_match.group(1).strip()
                if _looks_like_date_or_datetime(value):
                    logger.info(f"   ✅ Date found [proximity:{kw_pattern}]: {value}")
                    return value, f"proximity:{kw_pattern}"
    
    # ─── STRATEGY 4: Last resort ─────────────────────────────────────
    all_dates = list(re.finditer(date_pattern, text))
    
    if all_dates:
        kw_positions = []
        for kw_pattern in keyword_patterns:
            for m in re.finditer(kw_pattern, text, re.IGNORECASE):
                kw_positions.append(m.start())
        
        if kw_positions:
            best_date = None
            best_distance = float('inf')
            
            for date_pos, date_val in [(m.start(), m.group(1)) for m in all_dates]:
                for kw_pos in kw_positions:
                    distance = abs(date_pos - kw_pos)
                    if distance < best_distance and distance < 500:
                        best_distance = distance
                        best_date = date_val
            
            if best_date:
                logger.info(f"   ✅ Date found [closest_date, distance={best_distance}]: {best_date}")
                return best_date.strip(), "closest_date"
    
    # Nothing found
    logger.warning("   ❌ Date NOT FOUND in document")
    return None, None


# ──────────────────────────────────────────────────────────────────────
# MAIN EXTRACTION FUNCTIONS
# ──────────────────────────────────────────────────────────────────────

def extract_avis_fields(text: str) -> Dict[str, Any]:
    """Extract Objet, Date de soumission, Estimation (DHS TTC) from Avis text."""
    fields = {
        "Objet": "",
        "Date de soumission": "",
        "Estimation (DHS TTC)": ""
    }

    if not text:
        logger.warning("   No text provided for extraction")
        return {"Avis": fields}

    logger.info(f"🔍 Searching Avis fields (text length: {len(text)} chars)")

    # ─── Objet ───────────────────────────────────────────────────────
    patterns_objet_labeled = [
        r'Objet\s*[:;]\s*([^\n|]+)',
        r'Objet\s*du\s*march[ée]\s*[:;]\s*([^\n|]+)',
        r'OBJET\s*[:;]\s*([^\n|]+)',
        r'Objet\s*de\s*(?:la\s+)?(?:prestation|consultation)\s*[:;]\s*([^\n|]+)',
        r'\|\s*Objet\s*\|\s*([^|\n]+)\s*\|',  # Table format
    ]
    
    for pattern in patterns_objet_labeled:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value = match.group(1).strip()
            if value and len(value) > 5:
                fields["Objet"] = value.strip()
                logger.info(f"   ✅ Objet found (labeled): {value[:80]}...")
                break

    # Fallback: positional extraction
    if not fields["Objet"]:
        objet = _extract_objet_positional(text)
        if objet:
            fields["Objet"] = objet
            logger.info(f"   ✅ Objet found (positional): {objet[:80]}...")
        else:
            logger.warning("   ⚠️ Objet NOT found")

    # ─── Date de soumission ────────────────────────────────────────
    date_value, method = _extract_date_soumission(text)
    if date_value:
        fields["Date de soumission"] = _clean_date_value(date_value)
    else:
        logger.warning("   ⚠️ Date de soumission NOT found")

    # ─── Estimation (DHS TTC) ────────────────────────────────────────
    patterns_est = [
        r'Estimation\s*[:;]\s*([\d\s,.]+\s*DH[^\n|.]*)',
        r'Estimation\s*TTC\s*[:;]\s*([\d\s,.]+\s*DH[^\n|.]*)',
        r'Montant\s*estim[a-zé]+if?\s*[:;]\s*([\d\s,.]+\s*DH[^\n|.]*)',
        r"Co[ûu]t\s*estim[a-zé]+if?\s*[:;]\s*([\d\s,.]+\s*DH[^\n|.]*)",
        r"s['’]?[ée]l[èe]ve\s*à\s*([\d\s.,]+\s*DH[^\n.]*)",
        r'estim[ée][a-z]*\s*à\s*([\d\s.,]+\s*DH[^\n.]*)',
        r'co[uû]t\s+des\s+prestations[^\n]{0,40}?([\d\s.,]+\s*DH[^\n.]*)',
        r'Montant\s+total[^\n]{0,40}?([\d\s.,]+\s*DH[^\n.]*)',
        r'Budget[^\n]{0,40}?([\d\s.,]+\s*DH[^\n.]*)',
        # Table format
        r'\|\s*(?:Estimation|Montant\s+estim[a-zé]+if?|Co[ûu]t)\s*\|\s*([\d\s.,]+\s*DH[^|\n]*)\s*\|',
    ]
    
    for pattern in patterns_est:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value = match.group(1).strip().rstrip(".")
            if value and any(c.isdigit() for c in value):
                fields["Estimation (DHS TTC)"] = value
                logger.info(f"   ✅ Estimation found: {value}")
                break
    else:
        logger.warning("   ⚠️ Estimation NOT found")

    return {"Avis": fields}


# ─── RC FIELD EXTRACTOR ───────────────────────────────────────────────

def extract_rc_fields(text: str) -> Dict[str, Any]:
    fields = {
        "Références similaires (publics ou privés)": "Non mentionné",
        "Certificat de qualification et de classification": "Non mentionné"
    }
    if not text:
        return {"RC": {"Dossier Technique": fields}}

    # ─── Références similaires ─────────────────────────────────────
    m = re.search(r'r[ée]f[ée]rences?\s*similaires[^\n]{0,100}', text, re.IGNORECASE)
    if m:
        context = m.group(0).lower()
        if "public" in context and "priv" in context:
            fields["Références similaires (publics ou privés)"] = "Publics ou privés"
        elif "public" in context:
            fields["Références similaires (publics ou privés)"] = "Publics"
        elif "priv" in context:
            fields["Références similaires (publics ou privés)"] = "Privés"
        else:
            fields["Références similaires (publics ou privés)"] = "Mentionné (type non précisé)"

    # ─── Certificat de qualification ───────────────────────────────
    m2 = re.search(
        r'(?:certificat\s*de\s*qualification[^\n]{0,80}?)?'
        r'(cat[ée]gorie|classe)\s*[:\-]?\s*([0-9]{1,3}|[A-Z](?![a-zA-Z]))',
        text, re.IGNORECASE
    )
    if m2:
        label = m2.group(1).capitalize()
        code = m2.group(2).upper()
        fields["Certificat de qualification et de classification"] = f"{label} {code}"
        logger.info(f"   ✅ Found Certificat de qualification: {label} {code}")
    elif re.search(r'certificat\s*de\s*qualification', text, re.IGNORECASE):
        fields["Certificat de qualification et de classification"] = "Exigé (détail non trouvé)"

    return {"RC": {"Dossier Technique": fields}}


# ─── MAIN FIELD MAPPER ─────────────────────────────────────────────────

def map_fields_by_type(text: str, type_doc: str) -> Dict[str, Any]:
    """Route to the right field extractor."""
    if type_doc == "avis":
        return extract_avis_fields(text)
    elif type_doc == "rc":
        return extract_rc_fields(text)
    else:
        return {}