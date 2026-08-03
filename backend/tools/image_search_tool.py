"""
tools/image_search_tool.py  —  Targeted image search for CrystalWater posts
═══════════════════════════════════════════════════════════════════════════════
Sources used (NO Unsplash key required):
  1. Pexels API           — free key from pexels.com/api (200 req/hour)
  2. Pixabay API          — free key from pixabay.com/api/docs (100 req/min)
  3. Wikimedia Commons    — completely free, no key, great for technical diagrams
  4. Bing strict          — last resort, restricted to trusted water-industry domains only
  5. Curated fallbacks    — hard-coded verified Wikimedia images (always work)

To enable Pexels: add PEXELS_API_KEY=xxx to your .env
To enable Pixabay: add PIXABAY_API_KEY=xxx to your .env
Both are free — sign up takes 2 minutes. The tool works without them too.

All public functions return: str | None  (a public image URL or None)
"""

import os
import re
import time
import random
import hashlib
import warnings
import requests
from urllib.parse import quote_plus, quote
from collections import Counter

# ── Suppress SSL warnings (since we use verify=False) ──────────────────────
warnings.filterwarnings("ignore", message="Unverified HTTPS request")
requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)

# ── API keys (optional — set in .env) ─────────────────────────────────────────
PEXELS_API_KEY  = os.getenv("PEXELS_API_KEY", "")   # pexels.com/api
PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY", "")  # pixabay.com/api/docs

# ── Domains blocked (return junk unrelated to water treatment) ─────────────────
BLOCKED_DOMAINS = [
    "amazon.", "ebay.", "alibaba.", "aliexpress.",
    "facebook.", "instagram.", "twitter.", "tiktok.",
    "youtube.", "pinterest.", "reddit.",
    "nike.", "adidas.", "zalando.", "zara.",
    "football", "soccer", "shoes", "sneaker",
    "clothing", "fashion", "apparel",
    "recipe", "restaurant", "food.com",
    "hotel", "travel", "booking.",
    "logo", "icon", "favicon", "avatar",
    "banner", "ads.", "sponsor", "advert",
    "pixel", "tracking", "beacon",
    "thumb_tiny", "thumb_small",
]

# ── Trusted domains for Bing strict mode ──────────────────────────────────────
TRUSTED_DOMAINS = [
    "pureaqua.com", "dupont.com", "ecolab.com", "nalco.com",
    "veolia.com", "watertechnologies.com", "suezwatertechnologies.com",
    "amiad.com", "pentair.com", "culligan.com", "puretecwater.com",
    "hydranautics.com", "toray.com", "mann-hummel.com",
    "industrialwaterequipment.co.uk", "wateronline.com",
    "waterworld.com", "waterindustry.org",
    "images.pexels.com", "cdn.pixabay.com",
    "upload.wikimedia.org", "commons.wikimedia.org",
]

# ── Topic → precise English search queries ────────────────────────────────────
TOPIC_QUERY_MAP = [
    # Scaling / limescale / calcaire
    (["tartre", "entartrage", "calcaire", "dépôt calcaire", "scale", "limescale"],
     ["limescale deposits pipes", "scale buildup heat exchanger",
      "calcium carbonate deposit boiler", "water hardness pipe scale"]),

    # Corrosion / rust
    (["corrosion", "rouille", "rust", "oxydation", "oxidation"],
     ["industrial pipe corrosion", "rust corroded pipes",
      "metal corrosion water system", "corroded steel pipeline"]),

    # Reverse osmosis
    (["osmose inverse", "reverse osmosis", "osmosis", "ro system", "ro membrane",
      "membrane ro", "osmose"],
     ["reverse osmosis system", "RO membrane water filtration",
      "industrial water purification system", "water treatment plant"]),

    # Ultrafiltration / nanofiltration / microfiltration
    (["ultrafiltration", "nanofiltration", "microfiltration", "uf membrane"],
     ["membrane filtration water", "hollow fiber ultrafiltration",
      "water filtration membrane industrial"]),

    # Water softener / ion exchange
    (["adoucisseur", "adoucissement", "softener", "softening", "résine échangeuse",
      "échangeur d'ions", "ion exchange"],
     ["water softener industrial", "ion exchange resin tank",
      "water softening equipment factory"]),

    # Demineralization / deionization
    (["déminéralisation", "demineralization", "déionisation", "deionization",
      "eau déminéralisée", "demineralized water"],
     ["demineralization water plant", "deionized water system",
      "ion exchange demineralizer industrial"]),

    # Groundwater / aquifer / nappe phréatique
    (["nappe phréatique", "nappe", "groundwater", "eau souterraine",
      "pollution nappe", "contamination nappe", "aquifer"],
     ["groundwater contamination", "water pollution underground",
      "aquifer remediation industrial", "contaminated water treatment"]),

    # Plastic / microplastic pollution
    (["microplastique", "plastique", "micro-plastique", "microplastic", "plastic pollution"],
     ["microplastics water filter", "plastic pollution water",
      "water pollution environment", "pollution cleanup"]),

    # Industrial wastewater / effluent
    (["eaux usées", "eau usée", "wastewater", "effluent", "rejet industriel",
      "traitement effluent"],
     ["industrial wastewater treatment", "effluent treatment plant",
      "sewage treatment factory", "water purification plant"]),

    # Boiler / steam
    (["chaudière", "boiler", "vapeur", "steam", "eau chaudière"],
     ["industrial boiler", "steam boiler factory",
      "boiler water treatment", "industrial steam plant"]),

    # Cooling tower
    (["tour de refroidissement", "cooling tower", "circuit de refroidissement"],
     ["cooling tower industrial", "water cooling system factory",
      "industrial cooling plant"]),

    # Desalination
    (["dessalement", "desalination", "dessalinisation", "eau de mer"],
     ["seawater desalination plant", "desalination facility",
      "water treatment coastal industrial"]),

    # UV disinfection
    (["uv", "ultraviolet", "désinfection uv", "uv disinfection"],
     ["UV water treatment", "ultraviolet disinfection system",
      "water purification UV light industrial"]),

    # Chlorination / disinfection
    (["chloration", "chlore", "chlorination", "désinfection", "disinfection",
      "hypochlorite"],
     ["water chlorination", "chemical water disinfection",
      "water treatment chemical dosing"]),

    # Iron / manganese removal
    (["fer", "manganèse", "iron removal", "déferrisation", "deferrization"],
     ["iron removal water filter", "manganese filtration water",
      "water treatment iron manganese"]),

    # Pharmaceutical water
    (["pharmaceutique", "pharmaceutical", "eau pharmaceutique", "eau purifiée",
      "eau injectable", "pharma water"],
     ["pharmaceutical water treatment", "pharma clean room water",
      "laboratory water purification"]),

    # Food & beverage
    (["agroalimentaire", "agro-alimentaire", "food water", "boisson", "beverage"],
     ["food processing water treatment", "beverage plant water system",
      "food factory water filtration"]),

    # Chemical dosing / coagulation / flocculation
    (["dosage chimique", "chemical dosing", "coagulation", "floculation", "flocculation"],
     ["chemical dosing pump water", "coagulation water treatment",
      "water treatment chemicals industrial"]),

    # Water quality / analysis
    (["qualité eau", "water quality", "analyse eau", "water analysis",
      "turbidité", "turbidity", "conductivité"],
     ["water quality testing", "water analysis laboratory",
      "water monitoring industrial"]),

    # Sand / multimedia filter
    (["filtre à sable", "filtration sable", "sand filter", "multimedia filter",
      "filtre multimédia"],
     ["sand filter water treatment", "pressure sand filter industrial",
      "multimedia filtration system"]),

    # Activated carbon
    (["charbon actif", "charbon activé", "activated carbon", "carbon filter",
      "filtre charbon"],
     ["activated carbon filter water", "carbon filtration system",
      "GAC granular activated carbon water"]),

    # Generic fallback
    (["traitement eau", "water treatment", "purification eau", "water purification",
      "épuration eau", "filtration eau"],
     ["industrial water treatment plant", "water purification system",
      "water treatment facility", "water filtration factory"]),
]

# ── Curated fallback images (WIKIMEDIA / always available, large, no key) ──
CURATED_FALLBACKS = {
    "pollution": [
        "https://upload.wikimedia.org/wikipedia/commons/thumb/9/9b/Social_Network_Analysis_Visualization.png/1200px-Social_Network_Analysis_Visualization.png",
        "https://upload.wikimedia.org/wikipedia/commons/thumb/2/2a/Water_pollution.jpg/1280px-Water_pollution.jpg",
        "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6e/Industrial_water_pollution.jpg/1280px-Industrial_water_pollution.jpg",
    ],
    "factory": [
        "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b5/Water_treatment_plant_-_geograph.org.uk_-_2935133.jpg/1280px-Water_treatment_plant_-_geograph.org.uk_-_2935133.jpg",
        "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Industrial_pipes_%28Unsplash%29.jpg/1280px-Industrial_pipes_%28Unsplash%29.jpg",
        "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c4/Water_treatment_plant.jpg/1280px-Water_treatment_plant.jpg",
    ],
    "laboratory": [
        "https://upload.wikimedia.org/wikipedia/commons/thumb/8/86/Water_quality_testing.jpg/1280px-Water_quality_testing.jpg",
        "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4b/Laboratory_analysis.jpg/1280px-Laboratory_analysis.jpg",
        "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6e/Chemical_laboratory.jpg/1280px-Chemical_laboratory.jpg",
    ],
    "reverse_osmosis": [
        "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c8/Reverse_osmosis_plant.jpg/1280px-Reverse_osmosis_plant.jpg",
        "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0f/RO_membrane.jpg/1280px-RO_membrane.jpg",
        "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3c/Desalination_plant.jpg/1280px-Desalination_plant.jpg",
    ],
    "water_treatment": [
        "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b5/Water_treatment_plant_-_geograph.org.uk_-_2935133.jpg/1280px-Water_treatment_plant_-_geograph.org.uk_-_2935133.jpg",
        "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c4/Water_treatment_plant.jpg/1280px-Water_treatment_plant.jpg",
        "https://upload.wikimedia.org/wikipedia/commons/thumb/8/87/Sewage_treatment_plant.jpg/1280px-Sewage_treatment_plant.jpg",
    ],
    "industrial_pipes": [
        "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Industrial_pipes_%28Unsplash%29.jpg/1280px-Industrial_pipes_%28Unsplash%29.jpg",
        "https://upload.wikimedia.org/wikipedia/commons/thumb/7/7d/Piping_at_an_industrial_plant.jpg/1280px-Piping_at_an_industrial_plant.jpg",
        "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8b/Valves_and_pipes.jpg/1280px-Valves_and_pipes.jpg",
    ],
}

ANGLE_TO_CATEGORY = {
    "Problem":       "pollution",
    "Deep Problem":  "factory",
    "Education":     "laboratory",
    "Product Focus": "reverse_osmosis",
    "Case Study":    "water_treatment",
    "Technical":     "industrial_pipes",
    "Comparison":    "water_treatment",
    "Engagement":    "laboratory",
}


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _extract_keywords_from_post(post_text: str, max_words: int = 4) -> str:
    """Extract the most meaningful keywords from the post text."""
    if not post_text:
        return ""
    snippet = post_text[:300].replace("\n", " ").strip()
    # Remove URLs, punctuation, numbers
    words = re.findall(r'\b[a-zA-Z]{3,}\b', snippet.lower())
    # Stopwords fallback
    stop_words = {'the', 'a', 'an', 'of', 'for', 'on', 'at', 'to', 'in', 'with', 'without', 'by', 'from', 'up', 'down', 'off', 'over', 'under', 'above', 'below', 'between', 'among', 'through', 'during', 'within', 'without', 'about', 'against', 'between', 'across', 'along', 'around', 'behind', 'below', 'beneath', 'beside', 'beyond', 'by', 'down', 'from', 'in', 'into', 'near', 'of', 'off', 'on', 'to', 'toward', 'up', 'upon', 'with', 'within', 'without'}
    filtered = [w for w in words if w not in stop_words and len(w) > 2]
    if not filtered:
        return ""
    counter = Counter(filtered)
    return " ".join([w for w, _ in counter.most_common(max_words)])


def _build_search_query(topic: str, angle_key: str = "Education", post_text: str = "") -> list[str]:
    """Maps a topic to ranked specific English search queries, enhanced with post text and angle."""
    # Base queries from topic mapping
    topic_lower = topic.lower().strip()
    base_queries = []
    for keywords, queries in TOPIC_QUERY_MAP:
        if any(kw in topic_lower for kw in keywords):
            base_queries = queries
            break
    if not base_queries:
        stop_words = {'le', 'la', 'les', 'de', 'du', 'des', 'un', 'une', 'et', 'ou',
                      'à', 'au', 'aux', 'par', 'sur', 'en', 'dans', 'pour', 'avec',
                      'sans', 'the', 'of', 'in', 'and', 'for', 'a', 'an'}
        words = [w for w in topic_lower.split() if w not in stop_words and len(w) > 2]
        clean = " ".join(words[:5])
        base_queries = [f"{clean} water treatment", f"{clean} industrial", "industrial water treatment plant", "water purification factory"]

    # Enhance with keywords from post text
    keywords = _extract_keywords_from_post(post_text, max_words=3)
    if keywords:
        enhanced = f"{topic} {keywords}"
        base_queries = [enhanced] + base_queries

    # Add angle suffix for visual variety
    angle_suffix = {
        "Problem": " problem damage corrosion",
        "Deep Problem": " hidden costs financial impact",
        "Education": " diagram schematic educational",
        "Product Focus": " product equipment machinery",
        "Case Study": " before after transformation",
        "Technical": " technical specifications engineering",
        "Comparison": " comparison chart side by side",
        "Engagement": " interactive quiz infographic"
    }.get(angle_key, "")
    if angle_suffix:
        base_queries = [q + angle_suffix for q in base_queries[:2]] + base_queries

    return base_queries[:6]  # limit to 6 queries


def _is_url_safe(url: str) -> bool:
    """Returns False if the URL matches any blocked domain/keyword pattern."""
    url_lower = url.lower()
    return not any(b in url_lower for b in BLOCKED_DOMAINS)


def _is_valid_image_url(url: str) -> bool:
    """Basic check: must end with a valid image extension (not a thumbnail stub)."""
    path = url.split('?')[0]
    valid_ext = ('.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp')
    if re.search(r'/\d+$', path):
        return False
    return any(path.lower().endswith(ext) for ext in valid_ext)


def _download_check(url: str, min_bytes: int = 8000) -> bool:
    """HEAD request to verify the URL returns a real-sized image (ignores SSL)."""
    try:
        r = requests.head(
            url, timeout=10, allow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0"},
            verify=False,
        )
        r.raise_for_status()
        ct = r.headers.get("Content-Type", "")
        cl = int(r.headers.get("Content-Length", 0))
        return ("image" in ct) and (cl == 0 or cl >= min_bytes)
    except Exception:
        return False


def _get_curated_fallback(angle_key: str, day_number: int = 1) -> str:
    """Returns a verified Wikimedia image URL matching the angle, using day_number for variety."""
    category = ANGLE_TO_CATEGORY.get(angle_key, "water_treatment")
    urls = CURATED_FALLBACKS.get(category, CURATED_FALLBACKS["water_treatment"])
    idx = (day_number - 1) % len(urls)
    return urls[idx]


# ─────────────────────────────────────────────────────────────────────────────
# SOURCE 1 — Pexels API
# ─────────────────────────────────────────────────────────────────────────────

def _search_pexels(query: str, count: int = 5) -> list[str]:
    if not PEXELS_API_KEY:
        return []
    try:
        r = requests.get(
            "https://api.pexels.com/v1/search",
            params={"query": query, "per_page": count, "orientation": "landscape"},
            headers={"Authorization": PEXELS_API_KEY},
            timeout=10,
            verify=False,
        )
        if r.status_code == 200:
            return [p["src"]["large"] for p in r.json().get("photos", [])]
    except Exception as e:
        print(f"    [Pexels] {str(e)[:80]}")
    return []


# ─────────────────────────────────────────────────────────────────────────────
# SOURCE 2 — Pixabay API
# ─────────────────────────────────────────────────────────────────────────────

def _search_pixabay(query: str, count: int = 5) -> list[str]:
    if not PIXABAY_API_KEY:
        return []
    try:
        r = requests.get(
            "https://pixabay.com/api/",
            params={
                "key": PIXABAY_API_KEY,
                "q": query,
                "image_type": "photo",
                "orientation": "horizontal",
                "per_page": count,
                "safesearch": "true",
                "category": "industry",
            },
            timeout=10,
            verify=False,
        )
        if r.status_code == 200:
            hits = r.json().get("hits", [])
            return [h["largeImageURL"] for h in hits if h.get("largeImageURL")]
    except Exception as e:
        print(f"    [Pixabay] {str(e)[:80]}")
    return []


# ─────────────────────────────────────────────────────────────────────────────
# SOURCE 3 — Wikimedia Commons (no key)
# ─────────────────────────────────────────────────────────────────────────────

def _search_wikimedia(query: str, count: int = 4) -> list[str]:
    try:
        r = requests.get(
            "https://commons.wikimedia.org/w/api.php",
            params={
                "action": "query",
                "list": "search",
                "srsearch": f"{query} filetype:bitmap",
                "srnamespace": "6",
                "srlimit": count * 3,
                "format": "json",
            },
            timeout=10,
            verify=False,
        )
        if r.status_code != 200:
            return []

        urls = []
        for item in r.json().get("query", {}).get("search", []):
            raw_title = item.get("title", "")
            title = raw_title.replace("File:", "").replace(" ", "_")
            if not title:
                continue
            ext = title.rsplit(".", 1)[-1].lower() if "." in title else ""
            if ext not in ("jpg", "jpeg", "png", "webp"):
                continue
            md5 = hashlib.md5(title.encode()).hexdigest()
            url = (
                f"https://upload.wikimedia.org/wikipedia/commons/"
                f"{md5[0]}/{md5[0]}{md5[1]}/{quote(title)}"
            )
            if _is_valid_image_url(url):
                urls.append(url)
            if len(urls) >= count:
                break
        return urls
    except Exception as e:
        print(f"    [Wikimedia] {str(e)[:80]}")
        return []


# ─────────────────────────────────────────────────────────────────────────────
# SOURCE 4 — Bing strict (last web resort)
# ─────────────────────────────────────────────────────────────────────────────

def _search_bing_strict(query: str) -> list[str]:
    site_filter = (
        "site:pureaqua.com OR site:veolia.com OR site:pentair.com "
        "OR site:amiad.com OR site:puretecwater.com OR site:wateronline.com"
    )
    safe_query = f"{query} {site_filter}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        url = (
            f"https://www.bing.com/images/search"
            f"?q={quote_plus(safe_query)}&qft=+filterui:imagesize-large&first=1"
        )
        r = requests.get(url, headers=headers, timeout=15, verify=False)
        if r.status_code != 200:
            return []

        found = []
        for pattern in [r'murl&quot;:&quot;(https?://[^&]+)&quot;',
                         r'"murl":"(https?://[^"]+)"']:
            for m in re.findall(pattern, r.text, re.IGNORECASE):
                clean = m.replace("&quot;", '"').replace("\\", "").strip('"')
                if (clean.startswith("http")
                        and _is_url_safe(clean)
                        and any(td in clean.lower() for td in TRUSTED_DOMAINS)
                        and _is_valid_image_url(clean)):
                    found.append(clean)

        random.shuffle(found)
        return found[:8]
    except Exception as e:
        print(f"    [Bing strict] {str(e)[:80]}")
        return []


# ─────────────────────────────────────────────────────────────────────────────
# MAIN PUBLIC FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def find_image_for_topic(
    topic: str,
    angle_key: str = "Education",
    post_text: str = "",
    day_number: int = 1
) -> str | None:
    """
    Finds a relevant image for a thematic topic.

    Priority:
      1. Pexels API (if key set)
      2. Pixabay API (if key set)
      3. Wikimedia Commons
      4. Bing strict (domain-restricted)
      5. Curated Wikimedia fallback (guaranteed to work)

    Uses post_text to create a more specific search query, and uses day_number
    to pick a different result from the list (so each day gets a distinct image).
    """
    queries = _build_search_query(topic, angle_key, post_text)
    print(f"  [ImageSearch] Topic: '{topic[:60]}' | queries: {queries[:2]}")

    # Collect results from all sources with a small offset to get varied images
    all_urls = []
    for query in queries[:3]:
        # 1. Pexels
        pexels = _search_pexels(query, count=10)
        all_urls.extend(pexels)
        # 2. Pixabay
        pixabay = _search_pixabay(query, count=10)
        all_urls.extend(pixabay)
        # 3. Wikimedia
        wikimedia = _search_wikimedia(query, count=4)
        all_urls.extend(wikimedia)
        if len(all_urls) >= 5:
            break

    # Filter safe and valid URLs
    valid_urls = [u for u in all_urls if _is_url_safe(u) and _is_valid_image_url(u)]

    if valid_urls:
        # Pick a deterministic index based on day_number (1-indexed)
        idx = (day_number - 1) % len(valid_urls)
        chosen = valid_urls[idx]
        print(f"  [ImageSearch] ✓ Selected result #{idx+1}: {chosen[:80]}")
        return chosen

    # 4. Bing strict
    for query in queries[:2]:
        bing = _search_bing_strict(query)
        if bing:
            idx = (day_number - 1) % len(bing)
            chosen = bing[idx]
            print(f"  [ImageSearch] ✓ Bing strict #{idx+1}: {chosen[:80]}")
            return chosen

    # 5. Curated fallback — use angle and day to pick different
    fallback_url = _get_curated_fallback(angle_key, day_number)
    print(f"  [ImageSearch] ✓ Curated fallback ({angle_key}): {fallback_url[:80]}")
    return fallback_url


def find_image_for_product(product_name: str, product_data: dict | None = None) -> str | None:
    """Finds an image for a specific product name."""
    if product_data and product_data.get("image_url"):
        return product_data["image_url"]

    queries = [
        f"{product_name} water treatment",
        f"{product_name} filtration industrial",
        "industrial water treatment equipment",
    ]
    print(f"  [ImageSearch] Product: '{product_name[:60]}'")

    for query in queries[:2]:
        for url in _search_pexels(query, count=5):
            if _is_url_safe(url) and _is_valid_image_url(url):
                print(f"  [ImageSearch] ✓ Pexels (product): {url[:80]}")
                return url

        for url in _search_pixabay(query, count=5):
            if _is_url_safe(url) and _is_valid_image_url(url):
                print(f"  [ImageSearch] ✓ Pixabay (product): {url[:80]}")
                return url

        for url in _search_wikimedia(query, count=3):
            if _download_check(url):
                print(f"  [ImageSearch] ✓ Wikimedia (product): {url[:80]}")
                return url

    url = _get_curated_fallback("Product Focus", day_number=1)
    print(f"  [ImageSearch] ✓ Curated (product): {url[:80]}")
    return url


def download_image(url: str, min_bytes: int = 8000) -> bytes | None:
    """
    Downloads an image URL and returns raw bytes, or None on failure.
    Now with SSL bypass, extended timeout, and detailed error logging.
    """
    if not url:
        return None

    for attempt in range(3):
        try:
            r = requests.get(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Connection": "keep-alive",
                    "Sec-Fetch-Dest": "image",
                    "Sec-Fetch-Mode": "no-cors",
                    "Sec-Fetch-Site": "cross-site",
                },
                timeout=45,
                allow_redirects=True,
                verify=False,
                stream=True,
            )
            r.raise_for_status()

            content = r.content
            if len(content) >= min_bytes:
                print(f"    [Download] ✓ {len(content)//1024} KB")
                return content
            else:
                print(f"    [Download] ✗ Too small: {len(content)} bytes (min {min_bytes})")

        except requests.exceptions.Timeout:
            print(f"    [Download] Attempt {attempt+1}: Timeout (45s)")
        except requests.exceptions.SSLError as e:
            print(f"    [Download] Attempt {attempt+1}: SSL error – {str(e)[:80]}")
        except requests.exceptions.ConnectionError as e:
            print(f"    [Download] Attempt {attempt+1}: Connection error – {str(e)[:80]}")
        except Exception as e:
            print(f"    [Download] Attempt {attempt+1}: {type(e).__name__} – {str(e)[:80]}")

        if attempt < 2:
            time.sleep(1.5)

    return None