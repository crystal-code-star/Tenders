"""
agents/linkedin_outreach.py - LinkedIn Prospecting & Auto-Invitation Agent
═══════════════════════════════════════════════════════════════════════════
VERSION FINALE — Visite chaque profil dans l'ordre + vérifie Connect dans le header
⭐ Faire la recherche → visiter profil par profil → vérifier Connect → extraire ou skip
⭐ Ordre SÉQUENTIEL (pas aléatoire)
⭐ Regex ROBUSTE pour capturer TOUS les slugs
⭐ Vérifie STRICTEMENT le bouton "Connect" dans le header du profil
⭐ Skip les profils déjà connectés (Message) ou déjà invités (Pending)
⭐ Extraction ROBUSTE du nom (fallback sur le slug)
⭐ Sauvegarde PERSISTANTE de location et matched_keyword en DB
⭐ AUGMENTED WAIT TIMES — Prevent LinkedIn from closing browser too quickly
"""

from __future__ import annotations
import os, re, json, time, random, traceback
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from urllib.parse import quote_plus, unquote
from dotenv import load_dotenv

load_dotenv()

LINKEDIN_EMAIL = os.getenv("LINKEDIN_EMAIL", "")
LINKEDIN_PASSWORD = os.getenv("LINKEDIN_PASSWORD", "")
COMPANY_NAME = "CrystalWater"
# ⭐ AUGMENTED: Minimum and maximum delays significantly increased
MIN_DELAY_SEC = int(os.getenv("LINKEDIN_MIN_DELAY", "10"))  # Was 6
MAX_DELAY_SEC = int(os.getenv("LINKEDIN_MAX_DELAY", "20"))  # Was 12
DAILY_LIMIT = int(os.getenv("LINKEDIN_DAILY_LIMIT", "30"))
DATABASE_URL = os.getenv("DATABASE_URL", "")
MAX_SEARCH_PAGES = int(os.getenv("LINKEDIN_MAX_SEARCH_PAGES", "3"))
# ⭐ NEW: Extra safety delays for login and verification
LOGIN_EXTRA_DELAY = int(os.getenv("LINKEDIN_LOGIN_EXTRA_DELAY", "30"))  # Extra wait after login
VERIFICATION_TIMEOUT = int(os.getenv("LINKEDIN_VERIFICATION_TIMEOUT", "120"))  # 2 minutes for verification

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("⚠️ Playwright not installed.")

DEFAULT_KEYWORDS = [
    "water treatment", "traitement des eaux", "industrial water",
    "wastewater treatment", "desalination", "water quality",
]
LOCATIONS = ["Morocco", "France", "Algeria", "Tunisia"]

_profile_metadata_cache = {}

_engine = None

def _get_engine():
    global _engine
    if _engine is None:
        from sqlalchemy import create_engine
        db_url = DATABASE_URL
        if not db_url: raise RuntimeError("DATABASE_URL not set")
        if db_url.startswith("postgres://"): db_url = db_url.replace("postgres://", "postgresql://", 1)
        _engine = create_engine(db_url, connect_args={"sslmode": "require"}, pool_pre_ping=True, pool_recycle=300, pool_size=3, max_overflow=2)
    return _engine

def _get_data_dir() -> str:
    d = os.path.join(os.path.dirname(__file__), "..", "data", "outreach")
    os.makedirs(d, exist_ok=True)
    return d

def _ensure_db_columns():
    """⭐ AJOUTÉ : Vérifie et ajoute les colonnes manquantes dans la table"""
    try:
        from sqlalchemy import text
        with _get_engine().connect() as conn:
            # Vérifier si la colonne location existe
            try:
                conn.execute(text("SELECT location FROM outreach_profiles LIMIT 1"))
            except:
                print("  📝 Adding column 'location' to outreach_profiles...")
                conn.execute(text("ALTER TABLE outreach_profiles ADD COLUMN IF NOT EXISTS location TEXT DEFAULT ''"))
                conn.commit()
            
            # Vérifier si la colonne matched_keyword existe
            try:
                conn.execute(text("SELECT matched_keyword FROM outreach_profiles LIMIT 1"))
            except:
                print("  📝 Adding column 'matched_keyword' to outreach_profiles...")
                conn.execute(text("ALTER TABLE outreach_profiles ADD COLUMN IF NOT EXISTS matched_keyword TEXT DEFAULT ''"))
                conn.commit()
    except Exception as e:
        print(f"  ⚠ Error ensuring columns: {e}")

def load_profiles() -> List[dict]:
    global _profile_metadata_cache
    _ensure_db_columns()  # ⭐ AJOUTÉ : Vérifier les colonnes avant de charger
    try:
        from sqlalchemy import text
        with _get_engine().connect() as conn:
            rows = conn.execute(text("SELECT * FROM outreach_profiles ORDER BY created_at DESC LIMIT 500")).fetchall()
        return [{
            "id": r.id,
            "user_id": r.user_id,
            "name": r.name,
            "title": r.title or "",
            "profile_url": r.profile_url,
            "status": r.status or "pending",
            "location": getattr(r, 'location', None) or _profile_metadata_cache.get(r.profile_url, {}).get("location", ""),
            "matched_keyword": getattr(r, 'matched_keyword', None) or _profile_metadata_cache.get(r.profile_url, {}).get("matched_keyword", ""),
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            "first_name": (r.name or "").split()[0] if r.name else "",
            "invited_at": None,
        } for r in rows]
    except Exception as e:
        print(f"  ⚠ DB error: {e}")
        return []

def get_processed_profile_urls() -> set:
    try:
        from sqlalchemy import text
        with _get_engine().connect() as conn:
            return {r.profile_url for r in conn.execute(text("SELECT profile_url FROM outreach_profiles WHERE status != 'pending'")).fetchall()}
    except:
        return set()

def save_profiles(profiles: List[dict]):
    global _profile_metadata_cache
    if not profiles:
        return
    _ensure_db_columns()  # ⭐ AJOUTÉ : Vérifier les colonnes avant de sauvegarder
    try:
        from sqlalchemy import text
        with _get_engine().connect() as conn:
            for p in profiles:
                url = p.get("profile_url", "")
                if url:
                    _profile_metadata_cache[url] = {
                        "location": p.get("location", ""),
                        "matched_keyword": p.get("matched_keyword", "")
                    }
                existing = conn.execute(
                    text("SELECT id FROM outreach_profiles WHERE profile_url = :url LIMIT 1"),
                    {"url": url}
                ).fetchone()
                
                if existing:
                    # ⭐ MODIFIÉ : Mise à jour avec location et matched_keyword
                    conn.execute(
                        text("""
                            UPDATE outreach_profiles 
                            SET name=:n, title=:t, status=:s, 
                                location=:loc, matched_keyword=:mk,
                                updated_at=NOW() 
                            WHERE profile_url=:u
                        """),
                        {
                            "n": p.get("name", "?"),
                            "t": p.get("title", ""),
                            "s": p.get("status", "pending"),
                            "loc": p.get("location", ""),
                            "mk": p.get("matched_keyword", ""),
                            "u": url
                        }
                    )
                else:
                    # ⭐ MODIFIÉ : Insertion avec location et matched_keyword
                    conn.execute(
                        text("""
                            INSERT INTO outreach_profiles 
                            (user_id, name, title, profile_url, status, location, matched_keyword) 
                            VALUES (:uid, :n, :t, :u, :s, :loc, :mk)
                        """),
                        {
                            "uid": "crystalwater_user",
                            "n": p.get("name", "?"),
                            "t": p.get("title", ""),
                            "u": url,
                            "s": p.get("status", "pending"),
                            "loc": p.get("location", ""),
                            "mk": p.get("matched_keyword", "")
                        }
                    )
            conn.commit()
    except Exception as e:
        print(f"  ⚠ DB save error: {e}")

def _update_profile_status(profile_url: str, status: str):
    try:
        from sqlalchemy import text
        with _get_engine().connect() as conn:
            conn.execute(
                text("UPDATE outreach_profiles SET status=:s, updated_at=NOW() WHERE profile_url=:u"),
                {"s": status, "u": profile_url}
            )
            conn.commit()
    except:
        pass

def delete_invited_profiles() -> int:
    """
    ⭐ MODIFIÉ : Supprime TOUS les profils de la table outreach_profiles
    """
    try:
        from sqlalchemy import text
        with _get_engine().connect() as conn:
            result = conn.execute(text("DELETE FROM outreach_profiles"))
            conn.commit()
            d = result.rowcount
            print(f"  🗑️ Deleted ALL {d} profiles")
            return d
    except:
        return 0

def load_stats() -> dict:
    try:
        from sqlalchemy import text
        today = datetime.now().strftime("%Y-%m-%d")
        with _get_engine().connect() as conn:
            row = conn.execute(
                text("SELECT * FROM outreach_stats WHERE DATE(created_at)=:d ORDER BY created_at DESC LIMIT 1"),
                {"d": today}
            ).fetchone()
        if row:
            p = load_profiles()
            return {
                "total_searched": 0,
                "profiles_found": sum(1 for x in p if x["status"] == "pending"),
                "invitations_sent": row.invitations_sent or 0,
                "invitations_failed": 0,
                "daily_count": row.invitations_sent or 0,
                "last_run": row.created_at.isoformat() if row.created_at else None
            }
        return {
            "total_searched": 0,
            "profiles_found": 0,
            "invitations_sent": 0,
            "invitations_failed": 0,
            "daily_count": 0,
            "last_run": None
        }
    except:
        return {
            "total_searched": 0,
            "profiles_found": 0,
            "invitations_sent": 0,
            "invitations_failed": 0,
            "daily_count": 0,
            "last_run": None
        }

def save_stats(s: dict):
    try:
        from sqlalchemy import text
        with _get_engine().connect() as conn:
            conn.execute(
                text("INSERT INTO outreach_stats (user_id, invitations_sent, created_at) VALUES (:uid,:sent,NOW())"),
                {"uid": "crystalwater_user", "sent": s.get("invitations_sent", 0)}
            )
            conn.commit()
    except:
        pass

def is_today_daily_limit_reached() -> bool:
    return load_stats().get("daily_count", 0) >= DAILY_LIMIT

def increment_daily_count():
    s = load_stats()
    s["daily_count"] = s.get("daily_count", 0) + 1
    s["invitations_sent"] = s.get("invitations_sent", 0) + 1
    save_stats(s)

def _random_delay(mn=None, mx=None):
    """⭐ AUGMENTED: Default delays increased"""
    min_delay = mn if mn is not None else MIN_DELAY_SEC
    max_delay = mx if mx is not None else MAX_DELAY_SEC
    delay = random.uniform(min_delay, max_delay)
    print(f"       ⏱️ Waiting {delay:.1f}s...")
    time.sleep(delay)

def _parse_linkedin_name(n: str) -> Tuple[str, str]:
    p = n.strip().split()
    if len(p) <= 1:
        return (p[0] if p else ""), ""
    elif len(p) == 2:
        return p[0], p[1]
    else:
        return p[0], " ".join(p[1:])

def _clean_profile_name(slug: str) -> str:
    """
    ⭐ AMÉLIORÉ : Nettoie et formate le slug pour en faire un nom lisible.
    Ex: 'ahmed-chaouki' → 'Ahmed Chaouki'
    """
    name = unquote(slug).replace('-', ' ').replace('%20', ' ').replace('_', ' ')
    name = re.sub(r'\s+[A-F0-9]{6,}\s*$', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s+\d+[A-F]\d*\s*$', '', name)
    name = re.sub(r'\s+', ' ', name).strip().title()
    return name if len(name) >= 2 else "LinkedIn Member"

def _has_hex_suffix(slug: str) -> bool:
    return bool(re.search(r'-[a-f0-9]{6,}$', slug, re.IGNORECASE))

def _is_valid_profile_slug(slug: str) -> bool:
    s = slug.lower().strip()
    if s in ('feed', 'jobs', 'pub', 'in', 'people', 'search', 'settings', 'mynetwork', 'login', 'signup', 'dashboard', 'admin'):
        return False
    if len(s) < 2:
        return False
    if re.match(r'^[a-z0-9_]{20,}$', s) and not re.search(r'[a-z]{3,}', s):
        return False
    if s.startswith('acoa'):
        return False
    return True

def _detect_profile_language(page) -> str:
    try:
        pt = page.inner_text('body')[:500].lower()
        fr = sum(1 for w in ['envoyer', 'message', 'connecter', 'abonnés', 'abonnement', 'expérience', 'formation', 'coordonnées', 'relations'] if w in pt)
        en = sum(1 for w in ['followers', 'following', 'experience', 'education', 'featured', 'recommendations', 'connections', 'contact info'] if w in pt)
        if fr > en:
            return 'french'
        if en > fr:
            return 'english'
        try:
            lang = page.locator('html').get_attribute('lang') or ''
            if lang.startswith('fr'):
                return 'french'
            if lang.startswith('en'):
                return 'english'
        except:
            pass
        return 'english'
    except:
        return 'english'

_browser_instance = None

def _get_browser():
    global _browser_instance
    if not PLAYWRIGHT_AVAILABLE:
        raise RuntimeError("Playwright not installed.")
    if _browser_instance is not None:
        try:
            _browser_instance[1].pages[0].title()
            return _browser_instance
        except:
            _browser_instance = None
    profile_dir = os.path.join(_get_data_dir(), "browser_profile")
    for attempt in range(2):
        try:
            pw = sync_playwright().start()
            ctx = pw.chromium.launch_persistent_context(
                user_data_dir=profile_dir,
                headless=False,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-dev-shm-usage"],
                viewport={"width": 1280, "height": 900},
                timeout=90000  # ⭐ Increased to 90 seconds for browser launch
            )
            page = ctx.new_page()
            page.set_default_timeout(90000)  # ⭐ Default timeout increased to 90 seconds
            _browser_instance = (pw, ctx, page)
            return _browser_instance
        except Exception as e:
            print(f"  ⚠ Browser launch attempt {attempt + 1}: {str(e)[:100]}")
            if attempt == 0:
                try:
                    pw.stop()
                except:
                    pass
                import shutil
                shutil.rmtree(profile_dir, ignore_errors=True)
                time.sleep(2)  # ⭐ Increased wait before retry
            else:
                raise

def _close_browser():
    global _browser_instance
    if _browser_instance:
        try:
            _browser_instance[1].close()
            _browser_instance[0].stop()
        except:
            pass
        _browser_instance = None

def _ensure_logged_in(page, email, password) -> bool:
    """
    ⭐ AUGMENTED: Much longer waits for login and verification code handling
    """
    print("  🌐 Navigating to LinkedIn feed...")
    page.goto("https://www.linkedin.com/feed/", wait_until="networkidle", timeout=90000)
    _random_delay(5, 8)  # ⭐ Increased initial wait
    
    if "/feed" in page.url:
        print("  ✅ Already logged in")
        return True
    
    if "login" in page.url or "uas" in page.url:
        print("  🔐 Logging in...")
        page.goto("https://www.linkedin.com/login", wait_until="networkidle", timeout=90000)
        _random_delay(5, 8)  # ⭐ Wait for page to fully load
        
        try:
            page.wait_for_selector('input#username', timeout=30000)
            
            # Fill credentials slowly (more human-like)
            print("  📝 Entering credentials...")
            page.fill('input#username', email)
            _random_delay(2, 3)
            page.fill('input#password', password)
            _random_delay(2, 3)
            
            print("  🔘 Clicking submit...")
            page.click('button[type="submit"]')
            
            # ⭐ CRITICAL: Much longer wait after login for verification codes
            print(f"  ⏱️ Waiting up to {LOGIN_EXTRA_DELAY}s for login to complete...")
            print("  📱 If LinkedIn sends a verification code, enter it in the browser window")
            
            # ⭐ Wait for either feed page or checkpoint page
            for i in range(LOGIN_EXTRA_DELAY):
                time.sleep(1)
                current_url = page.url
                
                if "/feed" in current_url:
                    print("  ✅ Login successful - redirected to feed")
                    _random_delay(3, 5)  # ⭐ Extra wait after successful redirect
                    return True
                
                if "checkpoint" in current_url:
                    print("  ⚠️ VERIFICATION REQUIRED!")
                    print(f"  📱 LinkedIn is asking for verification code")
                    print(f"  ⏰ You have {VERIFICATION_TIMEOUT}s to enter the code in the browser")
                    print("  ⌛ Waiting for verification...")
                    
                    # ⭐ Wait much longer for user to enter verification code
                    for j in range(VERIFICATION_TIMEOUT):
                        time.sleep(1)
                        try:
                            if "/feed" in page.url:
                                print("  ✅ Verification successful!")
                                _random_delay(3, 5)
                                return True
                        except:
                            pass
                    
                    # Check if we're now logged in
                    if "/feed" in page.url:
                        return True
                    
                    print("  ⚠ Verification timeout - checking status...")
                    try:
                        if "/feed" in page.url:
                            return True
                        else:
                            print("  ❌ Still not logged in after verification timeout")
                            return False
                    except:
                        return False
                
                if i % 10 == 0 and i > 0:
                    print(f"    ... still waiting ({i}s elapsed)")
            
            # Final check
            if "/feed" in page.url:
                print("  ✅ Login successful")
                return True
            else:
                print(f"  ❌ Login failed after {LOGIN_EXTRA_DELAY}s - current URL: {page.url[:100]}")
                return False
                
        except Exception as e:
            print(f"  ⚠ Login error: {str(e)[:100]}")
            return False
            
    return False


# ═══════════════════ EXTRACTION DES SLUGS DE LA PAGE DE RECHERCHE ═══════════════════

def _extract_slugs_from_search_page(page) -> List[str]:
    """
    ⭐ Extrait tous les slugs de profils de la page de recherche, dans l'ordre d'apparition.
    ⭐ Utilise une regex ROBUSTE qui capture TOUTES les variations d'URL LinkedIn.
    """
    html = page.content()
    
    try:
        debug_dir = _get_data_dir()
        debug_path = os.path.join(debug_dir, "debug_search_page.html")
        with open(debug_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"     📝 Debug HTML saved: {debug_path}")
    except:
        pass
    
    slugs = []
    seen_slugs = set()
    
    # Pattern 1 : href="/in/slug..." (liens relatifs)
    pattern1 = r'href="(/in/([A-Za-z0-9\-_%]+))"'
    for match in re.finditer(pattern1, html, re.IGNORECASE):
        slug = match.group(2)
        slug = slug.split('?')[0].split('&')[0]
        if slug not in seen_slugs and _is_valid_profile_slug(slug):
            seen_slugs.add(slug)
            slugs.append(slug)
    
    # Pattern 2 : href="https://...linkedin.com/in/slug..." (URL absolues)
    pattern2 = r'href="(https?://[a-z]{2,3}\.linkedin\.com/in/([A-Za-z0-9\-_%]+))"'
    for match in re.finditer(pattern2, html, re.IGNORECASE):
        slug = match.group(2)
        slug = slug.split('?')[0].split('&')[0]
        if slug not in seen_slugs and _is_valid_profile_slug(slug):
            seen_slugs.add(slug)
            slugs.append(slug)
    
    # Pattern 3 : href="//www.linkedin.com/in/slug..." (protocole-relatif)
    pattern3 = r'href="(//[a-z]{0,3}\.??linkedin\.com/in/([A-Za-z0-9\-_%]+))"'
    for match in re.finditer(pattern3, html, re.IGNORECASE):
        slug = match.group(2)
        slug = slug.split('?')[0].split('&')[0]
        if slug not in seen_slugs and _is_valid_profile_slug(slug):
            seen_slugs.add(slug)
            slugs.append(slug)
    
    # ⭐ Si toujours 0 résultats, essayer une approche directe avec Playwright
    if len(slugs) == 0:
        print(f"     ⚠ Regex failed, trying Playwright selectors...")
        try:
            link_elements = page.locator('a[href*="/in/"]').all()
            for el in link_elements:
                try:
                    href = el.get_attribute('href') or ''
                    slug_match = re.search(r'/in/([A-Za-z0-9\-_%]+)', href)
                    if slug_match:
                        slug = slug_match.group(1).split('?')[0].split('&')[0]
                        if slug not in seen_slugs and _is_valid_profile_slug(slug):
                            seen_slugs.add(slug)
                            slugs.append(slug)
                except:
                    pass
        except Exception as e:
            print(f"     ⚠ Playwright selector failed: {str(e)[:80]}")
        
        if len(slugs) == 0:
            print(f"     ⚠ Still 0, trying desperate regex...")
            desperate_pattern = r'/in/([A-Za-z0-9\-_%]{2,})'
            for match in re.finditer(desperate_pattern, html):
                slug = match.group(1).split('?')[0].split('&')[0]
                if slug not in seen_slugs and _is_valid_profile_slug(slug):
                    seen_slugs.add(slug)
                    slugs.append(slug)
    
    return slugs


# ═══════════════════ VÉRIFICATION STRICTE DU BOUTON CONNECT DANS LE HEADER ═══════════════════

def _check_connect_in_header(page) -> str:
    """
    ⭐ Vérifie STRICTEMENT le bouton dans le header du profil.
    Retourne:
      - 'connect'    → Le bouton "Connect" est présent (on peut inviter)
      - 'message'    → Le bouton "Message" est présent (déjà connecté)
      - 'pending'    → L'invitation est en attente (déjà invité)
      - 'follow'     → Seulement "Follow" présent (pas de Connect)
      - 'none'       → Aucun bouton trouvé
    """
    try:
        # ⭐ VÉRIFICATION 1 : Déjà connecté ? (bouton Message présent dans le header)
        msg_selectors = [
            'button:has-text("Message")',
            'a:has-text("Message")',
            'span:has-text("Message")',
        ]
        for sel in msg_selectors:
            try:
                msg_btn = page.locator(sel).first
                if msg_btn.is_visible(timeout=2000):  # ⭐ Increased timeout
                    connect_check = page.locator('button:has-text("Connect")').first
                    if not connect_check.is_visible(timeout=1000):
                        return 'message'
            except:
                pass
        
        # ⭐ VÉRIFICATION 2 : Invitation en attente ? (bouton Pending)
        pending_selectors = [
            'span:has-text("Pending")',
            'button:has-text("Pending")',
            'span:has-text("En attente")',
        ]
        for sel in pending_selectors:
            try:
                pending_btn = page.locator(sel).first
                if pending_btn.is_visible(timeout=2000):  # ⭐ Increased timeout
                    return 'pending'
            except:
                pass
        
        # ⭐ VÉRIFICATION 3 : Bouton Connect présent dans le header ?
        header_selectors = [
            '.pv-top-card-v2-ctas',
            '.pv-top-card-v3-ctas',
            '.ph5.pb5',
            '.display-flex.ph5.pv3',
            'div[class*="top-card"]',
        ]
        
        for header_sel in header_selectors:
            try:
                header = page.locator(header_sel).first
                if header.is_visible(timeout=2000):  # ⭐ Increased timeout
                    connect_btn = header.locator('button:has-text("Connect"), a:has-text("Connect")').first
                    if connect_btn.is_visible(timeout=2000):
                        btn_text = connect_btn.inner_text().strip()
                        if btn_text.lower() == 'connect':
                            return 'connect'
            except:
                pass
        
        # ⭐ VÉRIFICATION 4 : Chercher le lien d'invitation "Invite X to connect"
        try:
            invite_link = page.locator('a[aria-label*="Invite" i][aria-label*="connect" i]').first
            if invite_link.is_visible(timeout=2000):
                aria = (invite_link.get_attribute('aria-label') or '').lower()
                if 'invite' in aria and 'connect' in aria and 'connections' not in aria:
                    return 'connect'
        except:
            pass
        
        # ⭐ VÉRIFICATION 5 : Chercher Follow seulement (pas de Connect)
        try:
            follow_btn = page.locator('button:has-text("Follow"), button:has-text("Suivre")').first
            if follow_btn.is_visible(timeout=2000):
                connect_anywhere = page.locator('button:has-text("Connect")').first
                if not connect_anywhere.is_visible(timeout=1000):
                    return 'follow'
        except:
            pass
        
        return 'none'
        
    except Exception as e:
        print(f"       ⚠ _check_connect_in_header error: {str(e)[:80]}")
        return 'none'


# ═══════════════════ EXTRACTION DES INFOS DU PROFIL ═══════════════════

def _extract_profile_details(page, profile_url: str) -> Optional[dict]:
    """
    ⭐ AMÉLIORÉ : Visite un profil et extrait nom, titre, langue, location.
    ⭐ Utilise des sélecteurs multiples pour le nom avec fallback sur le slug.
    ⭐ Extrait aussi la localisation depuis le profil.
    ⭐ AUGMENTED: Longer waits for profile loading
    """
    # Extraire le slug pour le fallback
    slug_match = re.search(r'/in/([A-Za-z0-9\-_%]+)', profile_url)
    slug = slug_match.group(1) if slug_match else ""
    fallback_name = _clean_profile_name(slug)
    
    try:
        # ⭐ NOM - Sélecteurs multiples avec fallback intelligent
        name = fallback_name  # Valeur par défaut = nom nettoyé du slug
        name_selectors = [
            'h1',
            'h1.inline.t-24',
            'h1.text-heading-xlarge',
            '[class*="text-heading-xlarge"]',
            '.pv-top-card--list h1',
            '.pv-text-details__left-panel h1',
        ]
        
        for sel in name_selectors:
            try:
                name_el = page.locator(sel).first
                if name_el.is_visible(timeout=4000):  # ⭐ Increased timeout
                    extracted = name_el.inner_text().strip()
                    # Nettoyer le nom (enlever les pronoms, titres honorifiques, etc.)
                    extracted = re.sub(r'\s*\([^)]*\)', '', extracted)  # Enlever (he/him), (she/her)
                    extracted = re.sub(r'\s*[·•].*$', '', extracted)   # Enlever · 1st, · 2nd
                    if extracted and len(extracted) >= 2:
                        name = extracted.strip()
                        break
            except:
                continue
        
        # Si on n'a toujours pas de nom valide, essayer avec le og:title
        if name == fallback_name or name == "LinkedIn Member":
            try:
                og_title = page.locator('meta[property="og:title"]').get_attribute('content')
                if og_title:
                    og_name = og_title.split('|')[0].split('–')[0].strip()
                    og_name = re.sub(r'\s*\([^)]*\)', '', og_name)
                    if og_name and len(og_name) >= 2:
                        name = og_name
            except:
                pass
        
        print(f"       📛 Extracted name: {name}")
        
        # ⭐ TITRE - Sélecteurs multiples
        title = ""
        title_selectors = [
            '.text-body-medium.break-words',
            '.pv-text-details__left-panel .text-body-medium',
            'div[class*="text-body-medium"]',
            '.pv-top-card--list .pv-entity__summary-info-text',
            '.pv-top-card-v2-ctas ~ div .text-body-medium',
        ]
        for sel in title_selectors:
            try:
                title_el = page.locator(sel).first
                if title_el.is_visible(timeout=3000):  # ⭐ Increased timeout
                    title = title_el.inner_text().strip()
                    if title and len(title) > 2:
                        break
            except:
                pass
        
        # ⭐ LOCATION - Extraire du profil
        profile_location = ""
        location_selectors = [
            '.text-body-small.inline.t-black--light',
            '.pv-top-card--list-bullet',
            '.pv-text-details__left-panel .text-body-small',
            'span.text-body-small',
        ]
        for sel in location_selectors:
            try:
                loc_el = page.locator(sel).first
                if loc_el.is_visible(timeout=3000):  # ⭐ Increased timeout
                    loc_text = loc_el.inner_text().strip()
                    # Vérifier que ça ressemble à une localisation
                    if loc_text and not loc_text.startswith('@') and len(loc_text) < 100:
                        # Chercher des patterns de localisation
                        if any(city_indicator in loc_text.lower() for city_indicator in 
                               ['morocco', 'france', 'algeria', 'tunisia', 'casablanca', 'rabat', 
                                'marrakech', 'paris', 'lyon', 'tunis', 'alger', 'area', 'region']):
                            profile_location = loc_text
                            break
                        # Ou si ça contient une virgule (format "City, Country")
                        if ',' in loc_text and len(loc_text) < 60:
                            profile_location = loc_text
                            break
            except:
                pass
        
        # Langue
        profile_language = _detect_profile_language(page)
        
        first_name = name.split()[0] if name and name != "LinkedIn Member" else ""
        
        return {
            "name": name,
            "title": title,
            "profile_url": profile_url,
            "status": "pending",
            "first_name": first_name,
            "location": profile_location,  # ⭐ AJOUTÉ : Location extraite du profil
            "matched_keyword": "",
            "_profile_language": profile_language,
        }
        
    except Exception as e:
        print(f"       ⚠ _extract_profile_details error: {str(e)[:80]}")
        # Retourner au moins le nom du slug
        return {
            "name": fallback_name,
            "title": "",
            "profile_url": profile_url,
            "status": "pending",
            "first_name": fallback_name.split()[0] if fallback_name != "LinkedIn Member" else "",
            "location": "",
            "matched_keyword": "",
            "_profile_language": "english",
        }


# ═══════════════════ RECHERCHE ET EXTRACTION ═══════════════════

def _search_and_extract(page, keyword: str, location: str, max_results: int = 10, processed_urls: set = None) -> List[dict]:
    """
    ⭐ Fonction principale :
    1. Faire la recherche LinkedIn
    2. Récupérer tous les slugs dans l'ordre de la page
    3. Visiter CHAQUE profil un par un (dans l'ordre)
    4. Vérifier le bouton Connect dans le header
    5. Si Connect → extraire le profil
    6. Sinon → passer au profil suivant
    """
    if processed_urls is None:
        processed_urls = set()
    
    all_profiles = []
    
    print(f"\n  🔍 Searching: '{keyword}' in '{location}'")
    
    for page_num in range(1, MAX_SEARCH_PAGES + 1):
        if len(all_profiles) >= max_results:
            break
        
        print(f"\n  {'='*50}")
        print(f"  📄 PAGE {page_num}/{MAX_SEARCH_PAGES} — '{keyword}' in '{location}'")
        print(f"  {'='*50}")
        
        # ⭐ ÉTAPE 1 : Aller à la page de recherche
        query = f'{keyword} {location}'
        if page_num == 1:
            search_url = f"https://www.linkedin.com/search/results/people/?keywords={quote_plus(query)}&origin=GLOBAL_SEARCH_HEADER"
        else:
            search_url = f"https://www.linkedin.com/search/results/people/?keywords={quote_plus(query)}&page={page_num}"
        
        print(f"     🔗 URL: {search_url}")
        
        # ⭐ AUGMENTED: Using networkidle with longer timeout
        page.goto(search_url, wait_until="networkidle", timeout=90000)
        _random_delay(8, 12)  # ⭐ Significantly increased wait for page to fully load
        
        # ⭐ ATTENDRE que les résultats de recherche apparaissent
        try:
            page.wait_for_selector(
                '.search-results-container, .reusable-search__entity-result-list, li.reusable-search__result-container',
                timeout=30000  # ⭐ Increased timeout
            )
            print(f"     ✅ Search results loaded")
        except:
            print(f"     ⚠ Search results selector not found, but continuing...")
        
        # Scroller pour charger tous les résultats
        print(f"     📜 Loading results...")
        for scroll in range(10):  # ⭐ Increased from 8 to 10
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            _random_delay(3, 5)  # ⭐ Increased scroll delay
        
        # ⭐ Scroll back to top
        page.evaluate("window.scrollTo(0, 0)")
        _random_delay(2, 3)
        
        # Vérifier qu'on est bien sur la page de recherche
        current_url = page.url
        print(f"     📍 Current URL: {current_url[:100]}")
        
        if "search/results" not in current_url and "/in/" not in current_url:
            if "login" in current_url or "checkpoint" in current_url:
                print(f"     ⚠ LinkedIn redirected to login/checkpoint — stopping")
                break
            print(f"     ⚠ Not on search results page, but trying to extract anyway...")
        
        # ⭐ ÉTAPE 2 : Extraire tous les slugs dans l'ordre de la page
        slugs = _extract_slugs_from_search_page(page)
        print(f"     🔗 {len(slugs)} profiles found on this page")
        
        if not slugs:
            print(f"     ⚠ No profiles extracted from this page")
            if not _has_next_page(page):
                print(f"     📄 No more pages")
                break
            _random_delay(5, 8)  # ⭐ Increased delay between pages
            continue
        
        # ⭐ ÉTAPE 3 : Visiter chaque profil UN PAR UN, dans l'ordre
        connect_count = 0
        skip_message = 0
        skip_pending = 0
        skip_no_connect = 0
        skip_error = 0
        
        for i, slug in enumerate(slugs):
            if len(all_profiles) >= max_results:
                print(f"\n     🎯 Reached max_results ({max_results})")
                break
            
            profile_url = f"https://www.linkedin.com/in/{slug}"
            
            if profile_url in processed_urls:
                continue
            if profile_url in {p["profile_url"] for p in all_profiles}:
                continue
            
            print(f"\n     [{i+1}/{len(slugs)}] Visiting: {slug[:50]}")
            
            try:
                # ⭐ AUGMENTED: networkidle with longer timeout
                page.goto(profile_url, wait_until="networkidle", timeout=45000)
                _random_delay(4, 6)  # ⭐ Increased wait for profile to load
                
                if "/in/" not in page.url:
                    print(f"       ⚠ Not a profile page (URL: {page.url[:60]}), skipping")
                    skip_error += 1
                    continue
                
                connect_status = _check_connect_in_header(page)
                
                if connect_status == 'connect':
                    print(f"       ✅ CONNECT button found! Extracting...")
                    profile_data = _extract_profile_details(page, profile_url)
                    
                    if profile_data:
                        # ⭐ MODIFIÉ : Location = location extraite du profil OU location de recherche
                        if not profile_data.get("location"):
                            profile_data["location"] = location
                        profile_data["matched_keyword"] = keyword
                        all_profiles.append(profile_data)
                        connect_count += 1
                        print(f"       ✅ EXTRACTED: {profile_data['name'][:50]} | Location: {profile_data['location'][:30]}")
                    else:
                        skip_error += 1
                
                elif connect_status == 'message':
                    print(f"       ⏭️ Already connected (Message button) — SKIP")
                    skip_message += 1
                
                elif connect_status == 'pending':
                    print(f"       ⏭️ Already invited (Pending) — SKIP")
                    skip_pending += 1
                
                elif connect_status == 'follow':
                    print(f"       ⏭️ Only Follow button (no Connect) — SKIP")
                    skip_no_connect += 1
                
                else:
                    print(f"       ⏭️ No Connect button found — SKIP")
                    skip_no_connect += 1
                
            except Exception as e:
                print(f"       ⚠ Error visiting profile: {str(e)[:80]}")
                skip_error += 1
                continue
            
            _random_delay(1.5, 3)  # ⭐ Increased delay between profiles
        
        print(f"\n     📊 Page {page_num} summary:")
        print(f"        ✅ Connect & extracted: {connect_count}")
        print(f"        ⏭️ Already connected: {skip_message}")
        print(f"        ⏭️ Already invited: {skip_pending}")
        print(f"        ⏭️ No Connect button: {skip_no_connect}")
        print(f"        ⚠ Errors: {skip_error}")
        print(f"        📦 Total collected so far: {len(all_profiles)}")
        
        if len(all_profiles) >= max_results:
            break
        
        if not _has_next_page(page):
            print(f"\n     📄 No more pages available")
            break
        
        _random_delay(5, 8)  # ⭐ Increased delay between pages
    
    return all_profiles


def _has_next_page(page) -> bool:
    """Vérifie si la page suivante existe"""
    for sel in [
        'button[aria-label*="Next" i]',
        'button:has-text("Next")',
        'button[aria-label*="Suivant" i]',
        'button[aria-label*="Page" i]',
        '.artdeco-pagination__button--next',
    ]:
        try:
            btn = page.locator(sel).first
            if btn.is_visible(timeout=3000):  # ⭐ Increased timeout
                if not btn.is_disabled():
                    return True
        except:
            continue
    return False


# ═══════════════════ CONNECT (pour l'envoi d'invitations) ═══════════════════

def _find_and_click_connect(page) -> str:
    """
    ⭐ CORRIGÉ : Utilise les MÊMES sélecteurs que _check_connect_in_header
    pour trouver et cliquer sur le bouton Connect lors de l'envoi d'invitations.
    Cherche spécifiquement le lien avec aria-label="Invite ... to connect"
    """
    _random_delay(3, 5)  # ⭐ Increased initial delay
    
    # ⭐ ÉTAPE 1 : Vérifier si déjà connecté (bouton Message présent)
    try:
        msg_btn = page.locator('button:has-text("Message"), a:has-text("Message")').first
        if msg_btn.is_visible(timeout=3000):  # ⭐ Increased timeout
            connect_check = page.locator('button:has-text("Connect"), a:has-text("Connect")').first
            if not connect_check.is_visible(timeout=1500):
                print(f"     ✓ Already connected (Message button found, no Connect button)")
                return 'connected'
    except:
        pass
    
    # ⭐ ÉTAPE 2 : Vérifier si invitation en attente
    try:
        pending_btn = page.locator('span:has-text("Pending"), button:has-text("Pending"), span:has-text("En attente")').first
        if pending_btn.is_visible(timeout=2000):  # ⭐ Increased timeout
            print(f"     ⚠ Invitation already pending")
            return 'pending'
    except:
        pass
    
    # ⭐ ÉTAPE 3 : Chercher le lien d'invitation avec aria-label (LE PLUS FIABLE)
    try:
        invite_link = page.locator('a[aria-label*="Invite" i][aria-label*="connect" i]').first
        if invite_link.is_visible(timeout=3000):  # ⭐ Increased timeout
            aria = (invite_link.get_attribute('aria-label') or '').lower()
            if 'invite' in aria and 'connect' in aria and 'connections' not in aria:
                print(f"     ✅ Clicking Connect (aria-label): {aria[:80]}")
                invite_link.click()
                _random_delay(3, 4)  # ⭐ Increased wait after click
                return 'clicked'
    except:
        pass
    
    # ⭐ ÉTAPE 4 : Chercher dans le header (plusieurs sélecteurs)
    header_selectors = [
        '.pv-top-card-v2-ctas',
        '.pv-top-card-v3-ctas',
        '.ph5.pb5',
        '.display-flex.ph5.pv3',
        'div[class*="top-card"]',
        '._21e7e560.c35d4e86._80588b63._0115bbfa._3b2814b2',
    ]
    
    for header_sel in header_selectors:
        try:
            header = page.locator(header_sel).first
            if header.is_visible(timeout=3000):  # ⭐ Increased timeout
                btn = header.locator('button:has-text("Connect"), a:has-text("Connect")').first
                if btn.is_visible(timeout=3000):
                    text = btn.inner_text().strip()
                    if text.lower() == 'connect':
                        print(f"     ✅ Clicking Connect (header: {header_sel})")
                        btn.click()
                        _random_delay(3, 4)  # ⭐ Increased wait after click
                        return 'clicked'
        except:
            pass
    
    # ⭐ ÉTAPE 5 : Chercher n'importe où sur la page avec le texte exact "Connect"
    try:
        connect_elements = page.locator('button:has-text("Connect"), a:has-text("Connect")').all()
        for el in connect_elements:
            try:
                if el.is_visible() and el.inner_text().strip().lower() == 'connect':
                    parent_text = el.locator('..').inner_text() if el.locator('..').count() > 0 else ''
                    if 'connections' not in parent_text.lower():
                        print(f"     ✅ Clicking Connect (anywhere on page)")
                        el.click()
                        _random_delay(3, 4)  # ⭐ Increased wait after click
                        return 'clicked'
            except:
                continue
    except:
        pass
    
    # ⭐ ÉTAPE 6 : Dernière tentative - chercher le SVG avec id="connect-small"
    try:
        svg_connect = page.locator('svg#connect-small').first
        if svg_connect.is_visible(timeout=3000):
            parent = svg_connect.locator('..').locator('..').first
            if parent.is_visible():
                print(f"     ✅ Clicking Connect (via SVG icon)")
                parent.click()
                _random_delay(3, 4)  # ⭐ Increased wait after click
                return 'clicked'
    except:
        pass
    
    print(f"     ⚠ Connect button not found after exhaustive search")
    return 'not_found'


def _send_without_note(page) -> bool:
    _random_delay(3, 5)  # ⭐ Increased delay
    for sel in [
        'button[aria-label*="Send now" i]',
        'button[aria-label*="Send" i]',
        'button:has-text("Send")',
        'button:has-text("Envoyer")',
    ]:
        try:
            btn = page.locator(sel).first
            if btn.is_visible(timeout=5000):  # ⭐ Increased timeout
                btn.click()
                _random_delay(4, 6)  # ⭐ Increased wait after send
                return _confirm_invitation_sent(page)
        except:
            continue
    return _confirm_invitation_sent(page)


def _confirm_invitation_sent(page) -> bool:
    _random_delay(3, 5)  # ⭐ Increased delay
    for txt in ['Pending', 'En attente', 'Invitation sent', 'Invitation envoyée']:
        try:
            if page.locator(f'text="{txt}"').first.is_visible(timeout=5000):  # ⭐ Increased timeout
                return True
        except:
            continue
    try:
        if not page.locator('button:has-text("Connect"), a:has-text("Connect")').first.is_visible(timeout=3000) and \
           page.locator('button:has-text("Message"), a:has-text("Message")').first.is_visible(timeout=3000):
            return True
    except:
        pass
    return False


def search_profiles(keywords=None, locations=None, max_per_search=10, language="french") -> List[dict]:
    if not PLAYWRIGHT_AVAILABLE:
        return []
    keywords, locations = keywords or DEFAULT_KEYWORDS, locations or LOCATIONS[:4]
    all_profiles, seen = [], set()
    processed_urls = get_processed_profile_urls()
    print(f"\n  🚫 {len(processed_urls)} already processed — excluded")
    
    # ⭐ MODIFIÉ : Ne pas fermer le navigateur dans finally
    try:
        pw, ctx, page = _get_browser()
        if not _ensure_logged_in(page, LINKEDIN_EMAIL, LINKEDIN_PASSWORD):
            _close_browser()
            return []
        for kw in keywords[:2]:
            for loc in locations[:2]:
                for p in _search_and_extract(page, kw, loc, max_per_search, processed_urls):
                    if p["profile_url"] not in seen:
                        seen.add(p["profile_url"])
                        all_profiles.append(p)
                _random_delay(8, 12)  # ⭐ Increased delay between searches
    except Exception as e:
        print(f"  ✗ {e}")
        _close_browser()
        return []
    
    print(f"\n  {'='*50}")
    print(f"  📊 TOTAL: {len(all_profiles)} NEW profiles with Connect button")
    print(f"  {'='*50}")
    if all_profiles:
        existing = load_profiles()
        existing_urls = {x.get("profile_url", "") for x in existing}
        new = [p for p in all_profiles if p["profile_url"] not in existing_urls]
        if new:
            save_profiles(new)
    
    # ⭐ AJOUTÉ : Garder le navigateur ouvert
    print("\n  🌐 Browser remains open for next operation")
    return all_profiles


def send_invitations(profiles=None, max_invitations=10, language="french", headless=False):
    if not PLAYWRIGHT_AVAILABLE:
        return {"success": False, "error": "Playwright not installed", "sent": 0, "failed": 0}
    if is_today_daily_limit_reached():
        return {"success": False, "error": "Daily limit reached.", "sent": 0, "failed": 0}
    if profiles is None:
        profiles = load_profiles()
    pending = [p for p in profiles if p.get("status") == "pending"]
    if not pending:
        return {"success": True, "message": "No pending profiles.", "sent": 0, "failed": 0}
    to_invite = min(max_invitations, DAILY_LIMIT - load_stats().get("daily_count", 0), len(pending))
    if to_invite <= 0:
        return {"success": False, "error": "Daily limit reached."}
    print(f"\n{'='*60}\n  ✉️  SENDING {to_invite} INVITATIONS\n{'='*60}")
    sent, failed = 0, 0
    
    # ⭐ MODIFIÉ : Ne pas fermer le navigateur dans finally si succès
    try:
        pw, ctx, page = _get_browser()
        if not _ensure_logged_in(page, LINKEDIN_EMAIL, LINKEDIN_PASSWORD):
            _close_browser()
            return {"success": False, "error": "Login failed."}
        for i, profile in enumerate(pending[:to_invite]):
            name = profile.get("name", "?")
            url = profile.get("profile_url", "")
            if not url:
                failed += 1
                continue
            print(f"\n  [{i+1}/{to_invite}] 👤 {name}")
            try:
                # ⭐ AUGMENTED: networkidle with longer timeout
                page.goto(url, wait_until="networkidle", timeout=45000)
                _random_delay(5, 8)  # ⭐ Increased wait for profile
                if "/in/" not in page.url:
                    _update_profile_status(url, "failed")
                    failed += 1
                    continue
                
                # ⭐ Mise à jour du nom depuis le profil
                try:
                    hn = page.locator('h1').first
                    if hn.is_visible(timeout=4000):  # ⭐ Increased timeout
                        rn = hn.inner_text().strip()
                        rn = re.sub(r'\s*\([^)]*\)', '', rn)
                        if rn and len(rn) > 1:
                            profile["name"] = rn
                            profile["first_name"] = rn.split()[0]
                except:
                    pass
                
                # Mise à jour du titre
                try:
                    tl = page.locator('.text-body-medium.break-words').first
                    if tl.is_visible(timeout=3000):  # ⭐ Increased timeout
                        profile["title"] = tl.inner_text().strip()
                except:
                    pass
                
                save_profiles([profile])
                
                cr = _find_and_click_connect(page)
                if cr == 'connected':
                    _update_profile_status(profile["profile_url"], "invited")
                    increment_daily_count()
                    sent += 1
                elif cr in ('follow_only', 'not_found'):
                    _update_profile_status(profile["profile_url"], "failed")
                    failed += 1
                elif cr == 'clicked':
                    if _send_without_note(page):
                        _update_profile_status(profile["profile_url"], "invited")
                        increment_daily_count()
                        sent += 1
                    else:
                        _update_profile_status(profile["profile_url"], "failed")
                        failed += 1
                elif cr == 'pending':
                    _update_profile_status(profile["profile_url"], "invited")
                    increment_daily_count()
                    sent += 1
            except Exception as e:
                _update_profile_status(url, "failed")
                failed += 1
            _random_delay(10, 20)  # ⭐ Significantly increased delay between invitations
        s = load_stats()
        s["invitations_sent"] = s.get("invitations_sent", 0) + sent
        save_stats(s)
    except Exception as e:
        print(f"  ✗ {e}")
        _close_browser()
        return {"success": False, "error": str(e), "sent": sent, "failed": failed}
    
    # ⭐ AJOUTÉ : Garder le navigateur ouvert après succès
    print("\n  🌐 Browser remains open after sending invitations")
    return {
        "success": True,
        "sent": sent,
        "failed": failed,
        "daily_total": load_stats().get("daily_count", 0),
        "daily_limit": DAILY_LIMIT
    }


def get_outreach_status() -> dict:
    s = load_stats()
    p = load_profiles()
    today = datetime.now().strftime("%Y-%m-%d")
    ds = s.get("daily_count", 0) if (s.get("last_run") or "").startswith(today) else 0
    return {
        "total_profiles": len(p),
        "profiles_found": sum(1 for x in p if x["status"] == "pending"),
        "invitations_sent": sum(1 for x in p if x["status"] == "invited"),
        "invitations_failed": sum(1 for x in p if x["status"] == "failed"),
        "daily_sent": ds,
        "daily_limit": DAILY_LIMIT,
        "daily_remaining": max(0, DAILY_LIMIT - ds),
        "last_run": s.get("last_run"),
        "recent_profiles": p[-50:],
        "playwright_available": PLAYWRIGHT_AVAILABLE
    }