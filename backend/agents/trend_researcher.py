import sys
import os
import json
import time
import re
import requests
import feedparser
from datetime import datetime, timedelta
from typing import List, Dict
from urllib.parse import quote, unquote
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tools.hf_llm_tool import infer

# =============================================================================
# CONFIG
# =============================================================================
MAX_ARTICLES = 100
MAX_SUMMARY_LEN = 150

GOOGLE_NEWS_FEEDS = [
    ("water treatment technology innovation", "en"),
    ("reverse osmosis membrane breakthrough", "en"),
    ("industrial water filtration system", "en"),
    ("desalination plant project", "en"),
    ("wastewater treatment innovation", "en"),
    ("water reuse recycling technology", "en"),
    ("zero liquid discharge system", "en"),
    ("membrane bioreactor technology", "en"),
    ("water treatment chemical new", "en"),
    ("PFAS removal water treatment", "en"),
    ("cooling tower water treatment", "en"),
    ("boiler water treatment chemical", "en"),
    ("corrosion inhibitor water treatment", "en"),
    ("antiscalant reverse osmosis", "en"),
    ("brine management desalination", "en"),
    ("ultrafiltration membrane technology", "en"),
    ("nanofiltration water treatment", "en"),
    ("electrodeionization water purification", "en"),
    ("advanced oxidation water treatment", "en"),
    ("sludge dewatering technology", "en"),
    ("water treatment Africa", "en"),
    ("traitement eau industriel innovation", "fr"),
    ("dessalement Maroc nouveau", "fr"),
    ("osmose inverse membrane technologie", "fr"),
    ("Morocco water treatment project", "en"),
    ("Morocco desalination plant progress", "en"),
    ("Maroc traitement eau actualite", "fr"),
    ("Maroc dessalement station projet", "fr"),
    ("ONEE eau potable assainissement", "fr"),
    ("ministere equipement eau Maroc", "fr"),
    ("Morocco drought water scarcity solution", "en"),
    ("Maroc secheresse eau solution", "fr"),
    ("Morocco water highway project", "en"),
    ("autoroute eau Maroc avancement", "fr"),
    ("Morocco mobile desalination unit", "en"),
    ("Maroc unite mobile dessalement", "fr"),
    ("OCP water treatment Morocco", "en"),
    ("OCP traitement eau Maroc", "fr"),
    ("Morocco water technology innovation research", "en"),
    ("recherche scientifique eau Maroc membrane filtration", "fr"),
    ("Morocco industrial water management sustainability", "en"),
    ("gestion durable eau industrie Maroc", "fr"),
]

DIRECT_RSS_FEEDS = [
    "https://www.waterworld.com/rss",
    "https://www.wateronline.com/rss",
    "https://www.wwdmag.com/rss",
    "https://www.water-technology.net/feed/",
    "https://www.waterfm.com/feed/",
]

WATER_KEYWORDS = [
    "water treatment", "desalination", "membrane", "wastewater", "filtration",
    "osmosis", "brine", "effluent", "reverse osmosis", "water reuse",
    "water quality", "water purification", "cooling tower", "boiler water",
    "sludge", "bioreactor", "zero liquid", "ZLD", "PFAS", "nanofiltration",
    "ultrafiltration", "electrodeionization", "EDI", "ion exchange",
    "coagulant", "flocculant", "corrosion inhibitor", "antiscalant",
    "traitement eau", "dessalement", "osmose inverse", "reutilisation eaux",
    "station epuration", "eau potable", "eau industrielle",
    "ONEE", "OCP", "Maroc", "Morocco", "autoroute eau", "secheresse",
    "drought", "barrage", "dam", "irrigation", "agricole",
    "ministere equipement", "hydraulique", "bassin", "nappe",
]

# =============================================================================
# ARTICLE-BASED POST GENERATION PROMPT
# =============================================================================

def build_trend_post_prompt(trend_name: str, category: str, evidence: str,
                            why_matters: str, post_ideas: list,
                            source_articles: list, language: str = "english",
                            opening_style: str = None,
                            used_openings: list = None) -> str:
    """
    Build a prompt that generates a LinkedIn post BASED ON THE TREND'S SOURCE ARTICLES.
    Includes opening_style randomization and anti-duplicate mechanism.
    """
    lang_display = "Francais" if language == "french" else "English"

    OPENING_STYLES = {
        "english": [
            {
                "name": "Breaking News",
                "instruction": "Open as breaking news -- 'JUST IN:' or 'Breaking:' style. Reference the most recent article like a news anchor.",
                "example": "'JUST IN: A major development in [topic] could reshape how industries approach water scarcity...'"
            },
            {
                "name": "Surprising Statistic",
                "instruction": "Open with a shocking or surprising statistic from the articles. Start with a number or percentage that grabs attention.",
                "example": "'Did you know that over 40% of the world's population faces water scarcity? The latest developments in [topic] aim to change that...'"
            },
            {
                "name": "Thought-Provoking Question",
                "instruction": "Open with a thought-provoking rhetorical question that makes the reader think about the trend's implications.",
                "example": "'What if the solution to industrial water scarcity was already being built -- right now -- in the Middle East?'"
            },
            {
                "name": "Behind the Headlines",
                "instruction": "Open by going deeper than the headline -- explain what the news REALLY means for the industry. 'Beyond the headlines...' or 'What the news isn't telling you...'",
                "example": "'The headlines talk about desalination contracts. But what they don't mention is the real impact on industrial water costs...'"
            },
            {
                "name": "Future-Focused",
                "instruction": "Open by looking forward -- what does this trend mean for the NEXT 5 years? 'By 2030...' or 'The future of...'",
                "example": "'By 2030, desalination technology could reduce industrial water costs by 60%. Here's what's happening right now...'"
            },
            {
                "name": "Local Impact",
                "instruction": "Open by connecting global news to LOCAL impact -- specifically for Morocco and African industries.",
                "example": "'While Kuwait invests millions in desalination, Moroccan industries face the same water challenges. Here's what we can learn...'"
            },
            {
                "name": "Contrarian View",
                "instruction": "Open with a contrarian or unexpected perspective on the trend. Challenge the obvious narrative.",
                "example": "'Everyone celebrates new desalination plants. But are we ignoring a critical challenge that could make them obsolete?'"
            },
        ],
        "french": [
            {
                "name": "Actualite Brulante",
                "instruction": "Ouvrez comme une actualite brulante -- style 'A LA UNE :' ou 'ALERTE :'. Referencez l'article le plus recent comme un journaliste.",
                "example": "'A LA UNE : Un contrat de 370 millions de dollars pour le dessalement a Doha. Voici pourquoi cela concerne directement les industries marocaines...'"
            },
            {
                "name": "Statistique Surprenante",
                "instruction": "Ouvrez avec une statistique choquante ou surprenante tiree des articles. Commencez par un chiffre ou un pourcentage qui attire l'attention.",
                "example": "'Saviez-vous que plus de 40% de la population mondiale fait face a une penurie d'eau ? Les derniers developpements en [sujet] visent a changer cela...'"
            },
            {
                "name": "Question Provocante",
                "instruction": "Ouvrez avec une question rhetorique qui fait reflechir le lecteur sur les implications de la tendance.",
                "example": "'Et si la solution a la penurie d'eau industrielle etait deja en construction -- en ce moment meme -- au Moyen-Orient ?'"
            },
            {
                "name": "Derriere les Gros Titres",
                "instruction": "Ouvrez en allant plus loin que le titre -- expliquez ce que la nouvelle signifie VRAIMENT pour l'industrie. 'Au-dela des gros titres...' ou 'Ce que les medias ne vous disent pas...'",
                "example": "'Les gros titres parlent de contrats de dessalement. Mais ce qu'ils ne mentionnent pas, c'est l'impact reel sur les couts de l'eau industrielle...'"
            },
            {
                "name": "Oriente Futur",
                "instruction": "Ouvrez en regardant vers l'avenir -- que signifie cette tendance pour les 5 PROCHAINES annees ? 'D'ici 2030...' ou 'L'avenir de...'",
                "example": "'D'ici 2030, la technologie de dessalement pourrait reduire les couts de l'eau industrielle de 60%. Voici ce qui se passe actuellement...'"
            },
            {
                "name": "Impact Local",
                "instruction": "Ouvrez en connectant l'actualite mondiale a l'impact LOCAL -- specifiquement pour le Maroc et les industries africaines.",
                "example": "'Pendant que le Koweit investit des millions dans le dessalement, les industries marocaines font face aux memes defis hydriques. Voici ce que nous pouvons apprendre...'"
            },
            {
                "name": "Point de Vue Inattendu",
                "instruction": "Ouvrez avec une perspective inattendue ou a contre-courant sur la tendance. Remettez en question le recit evident.",
                "example": "'Tout le monde celebre les nouvelles usines de dessalement. Mais sommes-nous en train d'ignorer un defi critique qui pourrait les rendre obsoletes ?'"
            },
        ]
    }

    styles = OPENING_STYLES.get(language, OPENING_STYLES["english"])
    available_styles = [s for s in styles if not used_openings or s["name"] not in used_openings]

    if not available_styles:
        available_styles = styles

    if opening_style and opening_style in [s["name"] for s in styles]:
        selected_style = next(s for s in styles if s["name"] == opening_style)
    else:
        import random as _random
        selected_style = _random.choice(available_styles)

    print(f"  Opening style: {selected_style['name']}")

    forbidden_section = ""
    if used_openings:
        forbidden_section = "\nFORBIDDEN OPENING STYLES (DO NOT USE THESE -- they were already used):\n"
        for uo in used_openings:
            forbidden_section += f"   X {uo}\n"
        forbidden_section += "   Your opening MUST use a DIFFERENT style from ALL of the above.\n"

    articles_text = ""
    if source_articles:
        articles_text = "\nSOURCE ARTICLES TO BASE YOUR POST ON:\n"
        for i, article in enumerate(source_articles[:5], 1):
            title = article.get('title', '')
            source = article.get('source', '')
            published = article.get('published', '')[:25] if article.get('published') else ''
            articles_text += f"\n  ARTICLE {i}: \"{title}\""
            if source:
                articles_text += f" (Source: {source})"
            if published:
                articles_text += f" - {published}"

    ideas_text = ""
    if post_ideas:
        ideas_text = "\nSUGGESTED POST ANGLES (pick one or combine):\n"
        for i, idea in enumerate(post_ideas[:3], 1):
            ideas_text += f"  {i}. {idea}\n"

    if language == "french":
        company_name = "CrystalWater"
        company_phone = "+212 6 10 10 74 75"
        company_email = "contact@crystalwater.ma"
        footer_line = f"{company_name} | Specialistes en traitement des eaux industrielles"
        contact_line = f"Tel: {company_phone}  |  Email: {company_email}"
        hashtags = "#CrystalWater #TraitementEau #EauIndustrielle #QualiteEau #Durabilite #EauPropre"
    else:
        company_name = "CrystalWater"
        company_phone = "+212 6 10 10 74 75"
        company_email = "contact@crystalwater.ma"
        footer_line = f"{company_name} | Industrial Water Treatment Specialists"
        contact_line = f"Tel: {company_phone}  |  Email: {company_email}"
        hashtags = "#CrystalWater #WaterTreatment #IndustrialWater #WaterQuality #Sustainability #CleanWater"

    prompt = f"""You are a senior B2B content strategist for CrystalWater, a Moroccan industrial water treatment company.

ASSIGNMENT: Write ONE LinkedIn post based on REAL NEWS
TREND:      "{trend_name}"
CATEGORY:   {category}
LANGUAGE:   {lang_display} -- YOU MUST WRITE 100% IN {lang_display}
OPENING:    {selected_style['name']} style

CRITICAL INSTRUCTION -- READ CAREFULLY:
You MUST base your post ENTIRELY on the source articles provided below.
This is NOT a generic post. It MUST reference or be clearly inspired by 
the actual news, data, and developments described in these articles.
Your post should feel like a timely reaction to current events in the 
water treatment industry.

YOUR OPENING STYLE IS: {selected_style['name']}
{selected_style['instruction']}
Example opening style: {selected_style.get('example', '')}

DO NOT USE ANY OTHER OPENING STYLE. Stick EXACTLY to the "{selected_style['name']}" style.
Your opening sentence MUST be COMPLETELY DIFFERENT from any post generated before for this trend.

{forbidden_section}

TREND CONTEXT:
{evidence}

WHY THIS MATTERS FOR CRYSTALWATER:
{why_matters}

{articles_text}

{ideas_text}

POST STRUCTURE (FOLLOW EXACTLY):

Paragraph 1 (Hook -- {selected_style['name']} style): 1-2 sentences -- Use the 
"{selected_style['name']}" opening style. Make it specific to the articles.

Paragraph 2 (Context & Analysis): 2-3 sentences -- Explain why this matters. 
Connect the news to real-world implications for industrial water treatment. 
Include at least ONE specific number or metric from the articles.

Paragraph 3 (CrystalWater Connection + CTA): 1-2 sentences -- Naturally 
connect this trend/news to CrystalWater's expertise and invite the reader 
to get in touch.

RULES (NON-NEGOTIABLE):

1. SHORT POST: 5-8 sentences maximum
2. PARAGRAPH PROSE ONLY: No bullet points, no headers, no lists
3. Reference at least one of the source articles
4. Include at least one specific number or metric
5. Last paragraph MUST connect to CrystalWater and invite contact
6. End with this EXACT footer on its own line:
   {footer_line}
   {contact_line}
7. FINAL LINE EXACTLY: {hashtags}
8. LANGUAGE: 100% {lang_display} -- NO exceptions
9. Output ONLY the post -- no explanations, no notes
10. OPENING: Use ONLY the "{selected_style['name']}" style -- DO NOT copy previous posts

WRITE THE POST NOW (in {lang_display}, "{selected_style['name']}" opening style, based on the articles above, 5-8 sentences max):"""

    return prompt


def generate_post_from_trend(trend: dict, language: str = "english",
                             opening_style: str = None,
                             used_openings: list = None) -> tuple:
    """
    Generate a LinkedIn post based on a trend's source articles.
    Returns (post_text, opening_style_used).
    """
    prompt = build_trend_post_prompt(
        trend_name=trend.get('trend_name', ''),
        category=trend.get('category', ''),
        evidence=trend.get('evidence', ''),
        why_matters=trend.get('why_matters', ''),
        post_ideas=trend.get('linkedin_post_ideas', []),
        source_articles=trend.get('source_articles', []),
        language=language,
        opening_style=opening_style,
        used_openings=used_openings,
    )

    print(f"\n  Generating trend-based post for: '{trend.get('trend_name', '')}'")
    print(f"  Based on {len(trend.get('source_articles', []))} source articles")

    try:
        post_text = infer(prompt, max_new_tokens=900, temperature=0.85).strip()
        if len(post_text) < 50:
            raise ValueError("Response too short")

        if language == "french":
            default_hashtags = "#CrystalWater #TraitementEau #EauIndustrielle #QualiteEau #Durabilite #EauPropre"
        else:
            default_hashtags = "#CrystalWater #WaterTreatment #IndustrialWater #WaterQuality #Sustainability #CleanWater"

        if "#CrystalWater" not in post_text:
            post_text += f"\n\n{default_hashtags}"

        style_match = re.search(r'OPENING:\s+"([^"]+)"', prompt)
        style_used = style_match.group(1) if style_match else "Standard"

        print(f"  Generated {len(post_text)} chars (style: {style_used})")
        return post_text, style_used

    except Exception as e:
        print(f"  Generation failed: {e}")
        raise


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def clean_html(raw: str) -> str:
    return re.sub('<.*?>', ' ', raw).strip()

def is_water_related(text: str) -> bool:
    return any(kw in text.lower() for kw in WATER_KEYWORDS)

def is_current_week(published_str: str) -> bool:
    """Check if article was published in the current week (Monday to Sunday)."""
    if not published_str:
        return False

    now = datetime.now()
    current_monday = now - timedelta(days=now.weekday())
    current_monday = current_monday.replace(hour=0, minute=0, second=0, microsecond=0)
    next_monday = current_monday + timedelta(days=7)

    formats = [
        "%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z",
        "%a, %d %b %Y %H:%M:%S", "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d",
        "%d %b %Y %H:%M:%S %z", "%d %b %Y %H:%M:%S",
        "%d %B %Y", "%b %d, %Y", "%B %d, %Y",
    ]

    for fmt in formats:
        try:
            pub_date = datetime.strptime(published_str.strip(), fmt)
            if pub_date.tzinfo:
                pub_date = pub_date.replace(tzinfo=None)
            return current_monday <= pub_date < next_monday
        except (ValueError, TypeError):
            continue

    try:
        pub_date = datetime.strptime(published_str.strip()[:10], "%Y-%m-%d")
        return current_monday <= pub_date < next_monday
    except:
        pass

    return False

def resolve_google_news_url(google_url: str, entry_summary: str = "") -> str:
    if "news.google.com" not in google_url and "news.google" not in google_url:
        return google_url
    if entry_summary:
        links = re.findall(r'href="(https?://[^"]+)"', entry_summary)
        for link in links:
            if "google.com" not in link and "news.google" not in link and "gstatic" not in link:
                return link
    decoded = unquote(google_url)
    urls = re.findall(r'(https?://[^\s&<>"]+)', decoded)
    for url in urls:
        if "google.com" not in url and "news.google" not in url and "gstatic" not in url:
            if len(url) > 25:
                return url
    try:
        headers = {"User-Agent": "Mozilla/5.0", "Accept": "text/html"}
        session = requests.Session()
        resp = session.get(google_url, headers=headers, timeout=10, allow_redirects=False)
        if resp.status_code in [301, 302, 303, 307, 308]:
            redirect_url = resp.headers.get("Location", "")
            if redirect_url and "google.com" not in redirect_url:
                return redirect_url
    except:
        pass
    return google_url


# =============================================================================
# WEEK HELPERS
# =============================================================================

def get_current_week_key() -> str:
    """Returns a unique key for the current week, e.g. 'Week-19-2026'"""
    now = datetime.now()
    return f"Week-{now.isocalendar()[1]}-{now.year}"

def get_week_label(week_key: str = None) -> str:
    """Returns a human-readable week label, e.g. 'Week 19, May 2026'"""
    if week_key is None:
        week_key = get_current_week_key()
    try:
        parts = week_key.split("-")
        week_num = int(parts[1])
        year = int(parts[2])
        # Get the Monday of that week
        monday = datetime.fromisocalendar(year, week_num, 1)
        return f"Week {week_num}, {monday.strftime('%B %Y')}"
    except:
        return week_key


# =============================================================================
# FETCH
# =============================================================================

def fetch_rss_feed(url: str) -> List[Dict]:
    articles = []
    try:
        feed = feedparser.parse(url)
        for entry in feed.entries[:20]:
            title = entry.get("title", "").strip()
            summary = clean_html(entry.get("summary", ""))
            link = entry.get("link", "")
            published = entry.get("published", "")
            if not title or len(title) < 15: continue
            if not is_water_related(title + " " + summary): continue
            if not is_current_week(published): continue
            articles.append({
                "title": title[:150],
                "summary": summary[:MAX_SUMMARY_LEN].strip(),
                "url": link,
                "source": feed.feed.get("title", url.split("//")[1].split("/")[0]),
                "published": published
            })
    except:
        pass
    return articles

def fetch_google_news(query: str, lang: str) -> List[Dict]:
    articles = []
    gl = "MA" if lang == "fr" else "US"
    rss_url = f"https://news.google.com/rss/search?q={quote(query)}&hl={lang}&gl={gl}&ceid={gl}:{lang}&num=20"
    try:
        feed = feedparser.parse(rss_url)
        for entry in feed.entries[:12]:
            title = entry.get("title", "")
            source = "Google News"
            if " - " in title:
                parts = title.rsplit(" - ", 1)
                title = parts[0].strip()
                source = parts[1].strip()
            raw_summary = entry.get("summary", "")
            summary = clean_html(raw_summary)
            link = entry.get("link", "")
            published = entry.get("published", "")
            if not title or len(title) < 15: continue
            if not is_current_week(published): continue
            real_url = resolve_google_news_url(link, entry_summary=raw_summary)
            articles.append({
                "title": title.strip()[:150],
                "summary": summary[:MAX_SUMMARY_LEN].strip(),
                "url": real_url,
                "source": source,
                "published": published
            })
    except:
        pass
    return articles


def fetch_all_articles() -> List[Dict]:
    all_articles = []
    seen_urls = set()
    current_week_label = get_week_label()
    print("\n" + "="*70)
    print(f"  FETCHING WATER TREATMENT CONTENT -- {current_week_label}")
    print(f"  Sources: {len(GOOGLE_NEWS_FEEDS)} Google queries + {len(DIRECT_RSS_FEEDS)} RSS feeds")
    print("="*70)

    print(f"\n  [1/2] Direct RSS feeds...")
    for url in DIRECT_RSS_FEEDS:
        articles = fetch_rss_feed(url)
        name = url.split("//")[1].split("/")[0]
        new = sum(1 for a in articles if a["url"] not in seen_urls)
        for a in articles:
            if a["url"] not in seen_urls:
                seen_urls.add(a["url"]); all_articles.append(a)
        status = "OK" if new else "--"
        print(f"    [{status}] {name}: {new} new")
        time.sleep(0.3)

    print(f"\n  [2/2] Google News ({len(GOOGLE_NEWS_FEEDS)} queries)...")
    for query, lang in GOOGLE_NEWS_FEEDS:
        articles = fetch_google_news(query, lang)
        new = sum(1 for a in articles if a["url"] not in seen_urls)
        for a in articles:
            if a["url"] not in seen_urls:
                seen_urls.add(a["url"]); all_articles.append(a)
        if new:
            print(f"    [OK] '{query[:50]}': {new} new")
        time.sleep(0.2)

    all_articles = sorted(all_articles, key=lambda x: x.get("published", ""), reverse=True)[:MAX_ARTICLES]
    resolved = sum(1 for a in all_articles if "google.com" not in a.get("url",""))
    print(f"\n  TOTAL: {len(all_articles)} articles | URLs resolved: {resolved}")
    if all_articles:
        print(f"  Date range: {all_articles[-1].get('published','')[:25]} ... {all_articles[0].get('published','')[:25]}")
    return all_articles


# =============================================================================
# GROQ TREND EXTRACTION
# =============================================================================

TREND_PROMPT = """Analyze these water treatment headlines from {month}. Extract ALL trends.
These include global water treatment news AND Moroccan-specific sources (ONEE, OCP, drought, desalination projects).

For each trend: specific name, discovered category, strength 0-100, evidence, article numbers, why CrystalWater (Morocco B2B water treatment company) cares, 2-3 LinkedIn post angles, AND suggested_posts (1-7: how many unique posts this trend could support as a campaign).

suggested_posts GUIDE:
- 1 post: Small/niche trend, limited content
- 2-3 posts: Good trend with several angles
- 4-5 posts: Strong trend with lots of evidence and angles
- 6-7 posts: Major/dominant trend with many articles and deep content potential

Strength: 90+=dominant, 70-89=strong, 50-69=emerging, 30-49=early signal.

ITEMS ({count} total):
{articles}

Return ONLY this exact JSON structure with no other text:
{{"trends":[{{"rank":1,"trend_name":"...","category":"...","strength":85,"article_count":5,"article_indices":[1,3,7],"evidence":"...","why_matters":"...","linkedin_post_ideas":["idea1","idea2"],"suggested_posts":3}}]}}"""

def _repair_truncated_json(json_str: str) -> str:
    open_braces = json_str.count('{')
    close_braces = json_str.count('}')
    open_brackets = json_str.count('[')
    close_brackets = json_str.count(']')
    in_string = False
    escaped = False
    for ch in json_str:
        if escaped:
            escaped = False
            continue
        if ch == '\\':
            escaped = True
            continue
        if ch == '"':
            in_string = not in_string
    if in_string:
        json_str += '"'
    json_str = re.sub(r',\s*$', '', json_str)
    needed_brackets = open_brackets - close_brackets
    needed_braces = open_braces - close_braces
    if needed_brackets > 0 or needed_braces > 0:
        json_str += ']' * needed_brackets
        json_str += '}' * needed_braces
    return json_str


def extract_trends(articles: List[Dict]) -> Dict:
    if len(articles) < 3:
        return {"error": f"Only {len(articles)} articles.", "trends": [], "week": get_current_week_key()}

    current_week_label = get_week_label()
    current_week_key = get_current_week_key()
    articles_text = "\n".join([f"{i}. [{a['source'][:20]}] {a['title'][:130]}" for i, a in enumerate(articles, 1)])

    prompt = TREND_PROMPT.format(count=len(articles), month=current_week_label, articles=articles_text)

    print(f"\n  Sending ~{len(prompt)//4} tokens to Groq")
    print(f"  Period: {current_week_label} | Articles: {len(articles)}")

    response = None
    try:
        response = infer(prompt, max_new_tokens=3500, temperature=0.3, retries=2)
        response = response.strip()
        print(f"  Response: {len(response)} chars - {response[:120]}...")

        response = re.sub(r'^```\w*\s*', '', response)
        response = re.sub(r'\s*```$', '', response)
        response = response.strip()

        start = response.find('{')
        if start < 0:
            return {"error": "No JSON in response", "trends": [], "raw": response[:500]}

        depth = 0
        end = -1
        for i in range(start, len(response)):
            if response[i] == '{': depth += 1
            elif response[i] == '}':
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break

        if end < 0:
            json_str = _repair_truncated_json(response[start:])
        else:
            json_str = response[start:end]
            print(f"  JSON: {len(json_str)} chars (complete object)")

        json_str = re.sub(r',\s*}', '}', json_str)
        json_str = re.sub(r',\s*]', ']', json_str)
        json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)

        result = json.loads(json_str)

        if "trends" in result:
            for trend in result["trends"]:
                indices = trend.get("article_indices", [])
                sources = []
                for idx in indices[:5]:
                    if 1 <= idx <= len(articles):
                        a = articles[idx - 1]
                        sources.append({
                            "title": a["title"],
                            "url": a["url"],
                            "source": a["source"],
                            "published": a.get("published", "")
                        })
                trend["source_articles"] = sources
                trend.pop("article_indices", None)

            result["trends"].sort(key=lambda x: x.get("strength", 0), reverse=True)
            for i, t in enumerate(result["trends"], 1):
                t["rank"] = i

        result["engine"] = "Groq"
        result["total_fetched"] = len(articles)
        result["week"] = current_week_key
        result["week_label"] = current_week_label
        result["research_date"] = datetime.now().strftime("%Y-%m-%d")

        print(f"  {len(result.get('trends',[]))} trends extracted")
        return result

    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON: {e}", "trends": [], "raw": (response or "")[:500]}
    except Exception as e:
        return {"error": str(e), "trends": []}


# =============================================================================
# SUPABASE
# =============================================================================

def _get_db_engine():
    from sqlalchemy import create_engine
    db_url = os.getenv("DATABASE_URL", "")
    if not db_url: return None
    if db_url.startswith("postgres://"): db_url = db_url.replace("postgres://", "postgresql://", 1)
    return create_engine(db_url, connect_args={"sslmode": "require"}, pool_pre_ping=True)

def save_trends_to_supabase(result: Dict):
    engine = _get_db_engine()
    if not engine: return
    try:
        from sqlalchemy import text
        week_key = result.get("week", get_current_week_key())
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS trends (
                    id SERIAL PRIMARY KEY, trend_name TEXT NOT NULL, category TEXT,
                    strength FLOAT DEFAULT 0, article_count INTEGER DEFAULT 0,
                    evidence TEXT, why_matters TEXT, source_articles JSONB DEFAULT '[]',
                    post_ideas JSONB DEFAULT '[]', week_key TEXT, week_label TEXT,
                    research_date TEXT, created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """))
            conn.commit()
            # Keep trends for 60 days (was 30)
            conn.execute(text("DELETE FROM trends WHERE created_at < NOW() - INTERVAL '60 days'"))
            # Delete only this week's old data so we can refresh it
            conn.execute(text("DELETE FROM trends WHERE week_key = :wk"), {"wk": week_key})
            for t in result.get("trends", []):
                conn.execute(text("""
                    INSERT INTO trends (trend_name, category, strength, article_count, 
                        evidence, why_matters, source_articles, post_ideas, 
                        week_key, week_label, research_date)
                    VALUES (:a,:b,:c,:d,:e,:f,:g,:h,:i,:j,:k)
                """), {
                    "a":t.get("trend_name",""),"b":t.get("category",""),"c":t.get("strength",0),
                    "d":t.get("article_count",0),"e":t.get("evidence","")[:1000],
                    "f":t.get("why_matters","")[:500],
                    "g":json.dumps(t.get("source_articles",[])),
                    "h":json.dumps(t.get("linkedin_post_ideas",[])),
                    "i":week_key,
                    "j":result.get("week_label", get_week_label(week_key)),
                    "k":result.get("research_date","")
                })
            conn.commit()
        print(f"  {len(result.get('trends',[]))} trends saved to Supabase (week: {week_key})")
    except Exception as e:
        print(f"  Supabase warning: {e}")

def get_trends_from_supabase(week_key: str = None) -> List[Dict]:
    """Get trends for a specific week, or current week if not specified."""
    engine = _get_db_engine()
    if not engine: return []
    try:
        from sqlalchemy import text
        if week_key is None:
            week_key = get_current_week_key()
        with engine.connect() as conn:
            rows = conn.execute(
                text("SELECT * FROM trends WHERE week_key = :wk ORDER BY strength DESC"),
                {"wk": week_key}
            ).fetchall()
        trends = []
        for r in rows:
            sa = json.loads(r.source_articles) if isinstance(r.source_articles, str) else (r.source_articles or [])
            pi = json.loads(r.post_ideas) if isinstance(r.post_ideas, str) else (r.post_ideas or [])
            trends.append({
                "trend_name":r.trend_name,"category":r.category,"strength":r.strength,
                "article_count":r.article_count,"evidence":r.evidence,
                "why_matters":r.why_matters,"source_articles":sa,
                "linkedin_post_ideas":pi,"rank":0,
                "week_key":r.week_key,"week_label":r.week_label
            })
        for i,t in enumerate(trends,1): t["rank"]=i
        return trends
    except:
        return []

def get_all_trends_grouped_by_week() -> List[Dict]:
    """Returns trends grouped by week, newest week first, each with an 'is_current' flag."""
    engine = _get_db_engine()
    if not engine: return []
    try:
        from sqlalchemy import text
        current_week = get_current_week_key()
        with engine.connect() as conn:
            rows = conn.execute(
                text("SELECT * FROM trends ORDER BY week_key DESC, strength DESC")
            ).fetchall()
        
        weeks_dict = {}
        for r in rows:
            wk = r.week_key or "unknown"
            if wk not in weeks_dict:
                weeks_dict[wk] = {
                    "week_key": wk,
                    "week_label": r.week_label or get_week_label(wk),
                    "is_current": wk == current_week,
                    "trends": []
                }
            sa = json.loads(r.source_articles) if isinstance(r.source_articles, str) else (r.source_articles or [])
            pi = json.loads(r.post_ideas) if isinstance(r.post_ideas, str) else (r.post_ideas or [])
            weeks_dict[wk]["trends"].append({
                "trend_name":r.trend_name,"category":r.category,"strength":r.strength,
                "article_count":r.article_count,"evidence":r.evidence,
                "why_matters":r.why_matters,"source_articles":sa,
                "linkedin_post_ideas":pi,"rank":0,
                "week_key":r.week_key,"week_label":r.week_label
            })
        
        result = list(weeks_dict.values())
        # Sort: current week first, then by week_key descending
        result.sort(key=lambda x: (not x["is_current"], x["week_key"]), reverse=False)
        # Re-rank within each week
        for week in result:
            for i, t in enumerate(week["trends"], 1):
                t["rank"] = i
        
        return result
    except:
        return []


# =============================================================================
# PUBLIC API
# =============================================================================

def research_trends() -> Dict:
    articles = fetch_all_articles()
    if len(articles) < 3:
        return {
            "error": f"Only {len(articles)} articles.",
            "trends": [],
            "week": get_current_week_key(),
            "total_fetched": len(articles)
        }
    return extract_trends(articles)

def print_trends(result: Dict):
    if result.get("error"):
        print(f"\n  ERROR: {result['error']}")
        if result.get("raw"): print(f"  Raw: {result['raw'][:300]}")
        return
    trends = result.get("trends", [])
    print(f"\n{'='*70}\n  TRENDS: {result.get('week_label','')} | {result.get('total_fetched',0)} articles | {len(trends)} trends\n{'='*70}")
    for t in trends:
        s = t.get("strength",0)
        fire = "DOMINANT" if s>=80 else "STRONG" if s>=60 else "EMERGING"
        print(f"\n  #{t.get('rank','?')} [{fire}] {t.get('trend_name','')}")
        print(f"  {t.get('category','')} - {s}/100 - {t.get('article_count','?')} articles")
        print(f"  {t.get('evidence','')[:200]}")
        print(f"  CrystalWater angle: {t.get('why_matters','')}")
        for a in t.get("source_articles",[])[:2]:
            print(f"  Source: {a.get('title','')[:75]}")
        for idea in t.get("linkedin_post_ideas",[]):
            print(f"  Post idea: {idea}")
    print(f"\n  {len(trends)} trends - {len(set(t.get('category','') for t in trends))} categories")

def save_results(result: Dict, output_path: str = None):
    if not output_path:
        d = os.path.join(os.path.dirname(__file__), "..", "data")
        os.makedirs(d, exist_ok=True)
        output_path = os.path.join(d, f"trends_{datetime.now().strftime('%Y%m%d_%H%M')}.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"  JSON saved: {output_path}")
    save_trends_to_supabase(result)