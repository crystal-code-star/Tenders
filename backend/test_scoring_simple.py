"""Test simple du scoring sans dépendances lourdes"""
import os
import re
from datetime import datetime

# ─── CONFIG (copiée de tender_scanner.py) ───
SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "") or os.getenv("SUPABASE_KEY", "")

if not SUPABASE_URL or not SUPABASE_KEY:
    # Charge depuis .env
    from pathlib import Path
    env_path = Path(__file__).resolve().parent / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, val = line.split('=', 1)
                    os.environ[key.strip()] = val.strip()
    SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
    SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "") or os.getenv("SUPABASE_KEY", "")

import requests

def _sb_headers():
    return {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"}

def _sb_get_criteria(params=None):
    try:
        r = requests.get(f"{SUPABASE_URL}/rest/v1/scoring_criteria", headers=_sb_headers(), params=params or {}, timeout=15)
        r.raise_for_status()
        return r.json() or []
    except Exception as e:
        print(f"Erreur API: {e}")
        return []

def _get_tender_field_value(tender, field_name):
    if field_name in tender:
        val = tender[field_name]
        if val is None: return "0"
        if isinstance(val, (int, float)): return str(val)
        return str(val)
    
    if field_name == "estimated_amount":
        val = tender.get("avis_estimation_ttc", "0")
        if val:
            cleaned = re.sub(r'[^\d.]', '', str(val))
            return cleaned if cleaned else "0"
        return "0"
    
    if field_name == "acheteur":
        val = tender.get("acheteur_public", "")
        return str(val) if val else ""
    
    return str(tender.get(field_name, "0") or "0")

def _compare_values(ao_value, operator, target_value):
    ao_clean = re.sub(r'[^\d.]', '', str(ao_value))
    target_clean = re.sub(r'[^\d.]', '', str(target_value))
    
    try:
        ao_num = float(ao_clean) if ao_clean else 0
        target_num = float(target_clean) if target_clean else 0
        if operator == '=': return ao_num == target_num
        if operator == '<': return ao_num < target_num
        if operator == '<=': return ao_num <= target_num
        if operator == '>': return ao_num > target_num
        if operator == '>=': return ao_num >= target_num
    except (ValueError, TypeError):
        pass
    
    ao_str = str(ao_value).lower().strip()
    target_str = str(target_value).lower().strip()
    if operator == '=': return ao_str == target_str
    if operator == '<': return ao_str < target_str
    if operator == '<=': return ao_str <= target_str
    if operator == '>': return ao_str > target_str
    if operator == '>=': return ao_str >= target_str
    return False

# ─── TEST ───
tender = {
    'reference': '25/DAM/S/2026',
    'acheteur_public': 'ONLLP-BE',
    'avis_estimation_ttc': '1 048 800 000 DHS',
    'objet': 'Fourniture de sulfate d alumine en 07 Lots',
}

print(f"SUPABASE_URL: {SUPABASE_URL[:30]}...")
print(f"SUPABASE_KEY: {SUPABASE_KEY[:10]}...")

criteria = _sb_get_criteria({'is_active': 'eq.true'})
print(f'\nCriteres actifs: {len(criteria)}')

score = 0
max_possible = 0

for c in criteria:
    val = _get_tender_field_value(tender, c['field_name'])
    match = _compare_values(val, c['operator'], c['value'])
    max_possible += c.get('weight', 1)
    if match:
        score += c.get('weight', 1)
    icon = '✅' if match else '❌'
    print(f'  {c["field_name"]} {c["operator"]} {c["value"]} => AO={val[:30]} => {icon} (+{c["weight"]})')

if max_possible > 0:
    percentage = int((score / max_possible) * 100)
else:
    percentage = 0

print(f'\nScore: {score}/{max_possible} = {percentage}%')