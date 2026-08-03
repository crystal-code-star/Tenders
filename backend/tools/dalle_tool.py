"""
tools/dalle_tool.py  —  Image generation via "Nano Banana" (Google Gemini image models)
═══════════════════════════════════════════════════════════════════════════════
VERSION "NANO BANANA + LINKEDIN KILLER PROMPTS"

WHAT "NANO BANANA" ACTUALLY MEANS (so this doesn't confuse future-you):
  "Nano Banana" is Google's public nickname for its Gemini native image models.
  There is no separate "Nano Banana API" — it's all the same Gemini API,
  just different model IDs:
    - Nano Banana        → gemini-2.5-flash-image       (original, fast/cheap)
    - Nano Banana 2       → gemini-3-1-flash-image        (newer, sharper, still
                                                            free-tier friendly)
    - Nano Banana Pro     → gemini-3-pro-image-preview    (best quality, but
                                                            REQUIRES billing —
                                                            not free-tier)

THIS FILE'S STRATEGY (because you're on a free-tier key):
  Try Nano Banana 2 first (best quality available without billing) →
  fall back to the original Nano Banana if Nano Banana 2 isn't enabled on
  your key yet → fall back to Pollinations as a last resort.

  Output resolution requested: 2K on every tier that supports it.

ENV VARIABLE: this file reads `nano_api_key` (matches your .env), with
`GEMINI_API_KEY` accepted too as a fallback name in case other files still
reference it.

IMAGE QUALITY FIXES IN THIS VERSION:
  - Prompts rewritten to explicitly demand sharp focus, no compression
    artifacts, no blur, no watermark, no AI-render "plastic" look.
  - Explicit 2K resolution config passed to the Gemini image call.
  - Prompt-writer step still reads the actual post text so the image matches
    the specific post, not just the generic topic label.
"""

import os
import io
import time
import random
import base64
import requests
from utils.image_storage import upload_image_bytes

# ── API key ───────────────────────────────────────────────────────────────────
# Reads `nano_api_key` from the environment (matches the .env you're using).
# Falls back to GEMINI_API_KEY for backward compatibility with older setups.
NANO_API_KEY = os.getenv("nano_api_key") or os.getenv("NANO_API_KEY") or os.getenv("GEMINI_API_KEY", "")

# ── Gemini ("Nano Banana") model IDs, in fallback order ───────────────────────
TEXT_MODEL          = "gemini-2.0-flash"          # for prompt refinement (fast, cheap, text-only)
IMAGE_MODEL_PRIMARY = "gemini-3-1-flash-image"    # "Nano Banana 2" — best quality on free tier
IMAGE_MODEL_FALLBACK = "gemini-2.5-flash-image"   # "Nano Banana" (original) — safety net

# ── Requested output resolution ───────────────────────────────────────────────
IMAGE_RESOLUTION = "2K"

# ── Base Gemini API URL ───────────────────────────────────────────────────────
GEMINI_BASE = "https://generativelanguage.googleapis.com/v1/models"


# ─────────────────────────────────────────────────────────────────────────────
# STEP 1 — Write a precise visual prompt from post content
# ─────────────────────────────────────────────────────────────────────────────

# Realistic, photography-first visual direction per angle — produces something
# that looks like a real industrial photo, not a render or graphic.
ANGLE_VISUAL_STYLE = {
    "Problem": (
        "real-world industrial photography showing a concrete, recognizable symptom of the "
        "problem — visible limescale on a pipe fitting, a clogged cartridge filter, corroded "
        "metal, or cloudy water in a sample glass. Documentary-style natural or work-light "
        "lighting, slightly imperfect and lived-in (not a polished studio render), photorealistic, "
        "shot like a maintenance technician's phone photo upgraded to professional quality"
    ),
    "Deep Problem": (
        "realistic industrial maintenance or plant-floor photography that implies cost and "
        "consequence without any invented charts or numbers baked into the image — worn "
        "equipment, a technician's tool resting near a corroded valve, a control panel with "
        "realistic gauges. Neutral industrial lighting, photorealistic, no graphic overlays, "
        "no on-image text or numbers"
    ),
    "Education": (
        "clean, realistic photographic cutaway or close-up of the actual equipment/process being "
        "explained — for example a real reverse osmosis membrane housing opened for inspection, "
        "or a clear glass beaker showing water clarity. Neutral laboratory or plant lighting, "
        "photorealistic, no illustrated diagrams, no arrows or labels drawn onto the image"
    ),
    "Product Focus": (
        "professional but unstaged product photography of real industrial water treatment "
        "equipment — pressure vessels, membrane housings, dosing pumps, filter cartridges, "
        "cooling tower components. Shot against a clean neutral background or realistic plant-floor "
        "setting, soft directional lighting, photorealistic, the kind of photo a real equipment "
        "catalog would use, no invented logos or printed text on the equipment"
    ),
    "Case Study": (
        "realistic photo of a well-maintained industrial facility or treatment installation — "
        "clean tanks, organized piping, a finished installation — conveying a successful outcome "
        "through genuine visual order rather than a literal before/after split-screen graphic. "
        "Natural industrial lighting, photorealistic, no text overlays, no invented signage"
    ),
    "Technical": (
        "realistic close-up photography of real technical components relevant to the topic — "
        "a pressure gauge reading, a membrane element, a control valve, a flow meter — shot with "
        "enough clarity that the equipment reads as genuine and specific. Neutral lighting, "
        "photorealistic, no schematic line-drawing style, no overlaid numbers or units burned "
        "into the image"
    ),
    "Comparison": (
        "realistic photo composition placing two real, distinguishable pieces of equipment or "
        "two material samples side by side in the same frame and lighting — for example two "
        "filter cartridges of different conditions, or two water samples of different clarity — "
        "shot naturally rather than as a graphic split-screen. Photorealistic, neutral lighting, "
        "no text labels"
    ),
    "Engagement": (
        "a clean, inviting, realistic industrial or laboratory photo that works well as a neutral "
        "background for a quiz post — equipment, water samples, or a plant setting shot with warm, "
        "approachable lighting. Photorealistic, no question marks, no graphic overlays, no on-image "
        "text of any kind"
    ),
}

# Quality/clean-image guardrails appended to every single prompt sent to the
# image model — this is the main fix for "blurry / artifacted / fake-looking"
# output. Kept short and concrete: long laundry lists of adjectives dilute
# instruction-following more than they help.
QUALITY_SUFFIX = (
    "Photorealistic, sharp focus throughout, crisp fine detail, natural and "
    "physically accurate lighting, no motion blur, no compression artifacts, "
    "no oversaturation, no plastic/waxy AI-render look, no text, no letters, "
    "no numbers, no logos, no watermarks, no people."
)

PROMPT_WRITER_SYSTEM = """You are a professional industrial photographer and art director who shoots real equipment catalogs and trade-press features for water treatment companies.

Your task: Given a LinkedIn post text and its topic, write a SINGLE detailed image generation prompt (2-4 sentences) that will produce a PHOTOREALISTIC, SPECIFIC, ON-TOPIC, HIGH-QUALITY image for that exact post — something that looks like a real photo taken on-site or in a real product shoot, not a generic stock illustration and not a soft/blurry AI render.

STRICT RULES:
1. The image MUST visually represent the EXACT topic and the SPECIFIC detail mentioned in the post excerpt (not a generic "water treatment" stand-in) — read the post excerpt carefully and pick the most concrete, photographable detail from it.
2. NO people, NO faces, NO hands with visible faces, NO text/words/letters/numbers/logos anywhere in the image, NO watermarks.
3. Favor REALISM over illustration: real industrial equipment, real material textures (steel, PVC, water, scale deposits, corrosion), real lighting conditions (overhead industrial lighting, daylight through a plant window, laboratory lighting) — avoid "infographic," "diagram," "3D render," or "futuristic" aesthetics unless the post is explicitly technical/schematic in nature.
4. Composition should look like it was actually photographed: include a believable setting (plant floor, lab bench, rooftop, utility room) rather than an isolated object floating on a blank background, unless the post is a tight product-catalog spotlight.
5. Include explicit camera-like framing and quality cues: sharp focus, fine surface detail, accurate physical lighting, shallow or appropriate depth of field, high dynamic range — describe the shot the way a real photographer would brief it.
6. Include: lighting, composition, color palette, mood, camera-like framing (e.g. "shallow depth of field," "wide industrial shot," "close-up macro").
7. End your prompt with this exact sentence: "Photorealistic, sharp focus throughout, crisp fine detail, natural and physically accurate lighting, no motion blur, no compression artifacts, no oversaturation, no plastic/waxy AI-render look, no text, no letters, no numbers, no logos, no watermarks, no people."
8. Output ONLY the image prompt — no explanation, no preamble."""


def _refine_prompt_with_gemini(post_text: str, topic: str, angle_key: str) -> str:
    """
    Uses the Gemini text model to write a precise visual prompt based on
    the actual post content. Falls back to a rule-based prompt if API fails.
    """
    if not NANO_API_KEY:
        return _fallback_prompt(topic, angle_key, post_text)

    angle_style = ANGLE_VISUAL_STYLE.get(angle_key, ANGLE_VISUAL_STYLE["Education"])

    # Extract first 500 chars of post as context (enough to find a concrete,
    # photographable detail — e.g. "calcaire", "membrane", "tour de refroidissement")
    post_excerpt = post_text[:500].replace("\n", " ").strip() if post_text else ""

    user_message = (
        f"POST TOPIC: {topic}\n\n"
        f"POST EXCERPT (read carefully for the most concrete, photographable detail): {post_excerpt}\n\n"
        f"VISUAL STYLE REQUIRED: {angle_style}\n\n"
        f"Write a detailed image generation prompt (2-4 sentences) for this exact post. "
        f"The image must clearly and specifically represent '{topic}' as described in the excerpt above, "
        f"in a real industrial water treatment context — not a generic stand-in image."
    )

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": PROMPT_WRITER_SYSTEM + "\n\n" + user_message}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.4,
            "maxOutputTokens": 320,
        }
    }

    url = f"{GEMINI_BASE}/{TEXT_MODEL}:generateContent?key={NANO_API_KEY}"

    try:
        resp = requests.post(url, json=payload, timeout=20)
        resp.raise_for_status()
        data = resp.json()

        candidates = data.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            for part in parts:
                if part.get("text"):
                    refined = part["text"].strip()
                    print(f"    📝 Refined prompt: {refined[:120]}...")
                    return refined

    except Exception as e:
        print(f"    ⚠ Prompt refinement failed: {str(e)[:80]}")

    return _fallback_prompt(topic, angle_key, post_text)


def _fallback_prompt(topic: str, angle_key: str, post_text: str = "") -> str:
    """Rule-based fallback prompt when the Gemini text API is unavailable."""
    topic_clean = topic.strip().replace('"', '').replace("'", "")
    angle_style = ANGLE_VISUAL_STYLE.get(angle_key, ANGLE_VISUAL_STYLE["Education"])
    excerpt_hint = (post_text or "")[:200].replace("\n", " ").strip()

    return (
        f"Photorealistic industrial photograph specifically illustrating '{topic_clean}' "
        f"(context: {excerpt_hint}). Visual style: {angle_style}. "
        f"Real materials and textures, believable industrial or laboratory setting, natural or "
        f"work-light lighting, sharp focus, high quality, 4K detail level. "
        f"{QUALITY_SUFFIX}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# STEP 2 — Generate image with Gemini ("Nano Banana") image models
# ─────────────────────────────────────────────────────────────────────────────

def _call_gemini_image_model(prompt: str, model_id: str, max_retries: int = 3) -> bytes | None:
    """
    Calls a specific Gemini image model with exponential backoff on 429s.
    Requests 2K output resolution. Returns raw image bytes or None.
    """
    if not NANO_API_KEY:
        print("    ✗ nano_api_key not set in .env")
        return None

    payload = {
        "contents": [
            {
                "parts": [{"text": prompt}]
            }
        ],
        "generationConfig": {
            # Requests 2K output where the model supports configuring it.
            # Models that don't recognize this field simply ignore it rather
            # than erroring, so it's safe to include across the fallback chain.
            "imageConfig": {
                "imageSize": IMAGE_RESOLUTION
            }
        }
    }

    url = f"{GEMINI_BASE}/{model_id}:generateContent?key={NANO_API_KEY}"

    for attempt in range(max_retries):
        try:
            resp = requests.post(url, json=payload, timeout=120)

            if resp.status_code == 429:
                wait = 2 ** attempt * 3   # 3, 6, 12 seconds
                print(f"    ⚠ {model_id} rate limited (429), retrying in {wait}s...")
                time.sleep(wait)
                continue

            if resp.status_code == 404:
                # Model not enabled / not available on this key — let the
                # caller move on to the next model in the fallback chain.
                print(f"    ⚠ {model_id} not available on this API key (404)")
                return None

            if resp.status_code == 400:
                error_detail = resp.json().get("error", {}).get("message", "")
                print(f"    ✗ {model_id} 400 error: {error_detail[:150]}")
                return None

            resp.raise_for_status()
            data = resp.json()

            candidates = data.get("candidates", [])
            for candidate in candidates:
                parts = candidate.get("content", {}).get("parts", [])
                for part in parts:
                    if part.get("thought"):
                        continue
                    inline = part.get("inlineData", {})
                    if inline.get("data"):
                        img_bytes = base64.b64decode(inline["data"])
                        if len(img_bytes) > 5000:
                            print(f"    ✓ {model_id} image received ({len(img_bytes)//1024} KB)")
                            return img_bytes

            print(f"    ✗ No image data in {model_id} response")
            return None

        except requests.exceptions.Timeout:
            print(f"    ✗ {model_id} timed out (120s)")
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            return None
        except Exception as e:
            print(f"    ✗ {model_id} generation error: {str(e)[:100]}")
            return None

    return None


def _generate_with_nano_banana(prompt: str) -> bytes | None:
    """
    Tries the Nano Banana fallback chain in order:
      1. Nano Banana 2 (gemini-3-1-flash-image) — best quality on free tier
      2. Nano Banana / original (gemini-2.5-flash-image) — safety net if
         Nano Banana 2 isn't enabled on this key yet
    """
    img_bytes = _call_gemini_image_model(prompt, IMAGE_MODEL_PRIMARY)
    if img_bytes:
        return img_bytes

    print(f"    ↪ Falling back to original Nano Banana ({IMAGE_MODEL_FALLBACK})...")
    return _call_gemini_image_model(prompt, IMAGE_MODEL_FALLBACK)


# ─────────────────────────────────────────────────────────────────────────────
# FINAL FALLBACK — Pollinations (if both Nano Banana models fail)
# ─────────────────────────────────────────────────────────────────────────────

def _generate_with_pollinations(prompt: str, seed: int = 0) -> bytes | None:
    """Last-resort fallback using Pollinations.ai (free, no key)."""
    import urllib.parse
    # Pollinations responds better to photographic prompts when nudged
    # explicitly toward "photo" rather than "illustration" up front.
    photo_nudge = "professional industrial photography, photo, sharp focus, high detail, "
    safe_prompt = urllib.parse.quote((photo_nudge + prompt)[:450])
    if seed == 0:
        seed = random.randint(100000, 999999)

    url = (
        f"https://image.pollinations.ai/prompt/{safe_prompt}"
        f"?width=1536&height=1536&nologo=true&seed={seed}&model=flux"
    )
    try:
        resp = requests.get(url, timeout=120)
        resp.raise_for_status()
        if len(resp.content) > 5000:
            print(f"    ✓ Pollinations fallback image ({len(resp.content)//1024} KB)")
            return resp.content
    except Exception as e:
        print(f"    ✗ Pollinations fallback failed: {str(e)[:80]}")
    return None


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────────────────────

def generate_image(
    prompt: str,
    day_id: int = 0,
    topic: str = "",
    product: str | None = None,
    retries: int = 2,
    angle_key: str = "Education",
    day_number: int = 1,
    post_text: str = "",
) -> dict:
    """
    Generates an image via the Nano Banana fallback chain, with a prompt
    derived from the actual post content. Falls back to Pollinations if
    both Nano Banana models fail.

    Returns: {"image_url": str | None}
    """
    real_topic = product if product else (topic if topic else "industrial water treatment")

    print(f"    🎨 Generating image for: '{real_topic[:60]}'")
    print(f"    📐 Angle: {angle_key}, Day: {day_number}, Resolution: {IMAGE_RESOLUTION}")

    # Step 1: Write a precise visual prompt based on actual post content
    visual_prompt = _refine_prompt_with_gemini(post_text, real_topic, angle_key)

    for attempt in range(retries + 1):
        print(f"    🔄 Attempt {attempt + 1}/{retries + 1}...")

        # Step 2a: Try the Nano Banana chain (Nano Banana 2 → Nano Banana)
        img_bytes = _generate_with_nano_banana(visual_prompt)

        # Step 2b: Fallback to Pollinations
        if not img_bytes:
            print(f"    ⚠ Nano Banana failed, trying Pollinations fallback...")
            seed = abs(hash(f"{day_id}_{day_number}_{attempt}_{time.time()}")) % 1000000
            img_bytes = _generate_with_pollinations(visual_prompt, seed)

        if img_bytes:
            public_url = upload_image_bytes(img_bytes, day_id)
            if public_url:
                print(f"    ✓ Image uploaded successfully!")
                return {"image_url": public_url}

        if attempt < retries:
            time.sleep(3)

    print(f"    ✗ All attempts failed")
    return {"image_url": None}


def generate_image_pollinations_direct(
    topic: str,
    angle_key: str = "Education",
    day_number: int = 1,
    cache_buster: str = "",
    post_text: str = "",
) -> str | None:
    """
    Direct image generation — used by regenerate_image_ai() in bulk_generator.
    Tries the Nano Banana chain first, falls back to Pollinations.
    Returns a public URL or None.
    """
    print(f"    🎨 AI Image for: '{topic[:60]}' (angle: {angle_key})")

    visual_prompt = _refine_prompt_with_gemini(post_text, topic, angle_key)

    img_bytes = _generate_with_nano_banana(visual_prompt)

    if not img_bytes:
        seed = abs(hash(f"{cache_buster}_{time.time_ns()}")) % 1000000
        img_bytes = _generate_with_pollinations(visual_prompt, seed)

    if img_bytes:
        temp_id = int(time.time())
        public_url = upload_image_bytes(img_bytes, temp_id)
        if public_url:
            print(f"    ✓ Image generated and uploaded")
            return public_url

    return None


def build_infographic_prompt(topic: str, product: str | None = None) -> str:
    """Returns a text description of what the image should show (used as metadata)."""
    subject = product if product else topic
    return (
        f"Photorealistic industrial photograph of {subject} in a real plant or product-catalog "
        f"setting. Natural materials and lighting, sharp focus, no text, no logos, no people."
    )


# ─────────────────────────────────────────────────────────────────────────────
# DIAGNOSTIC
# ─────────────────────────────────────────────────────────────────────────────

def test_nano_banana_connection() -> bool:
    """
    Quick test to verify nano_api_key is valid and image generation works,
    walking the full fallback chain so you can see which model your key
    actually has access to.
    """
    if not NANO_API_KEY:
        print("❌ nano_api_key not set in .env")
        return False

    test_prompt = (
        "Photorealistic industrial water treatment facility photograph. "
        "Large blue filtration tanks, stainless steel pipes, clean modern factory, "
        "natural daylight, sharp focus throughout. "
        f"{QUALITY_SUFFIX}"
    )

    print(f"🔍 Testing Nano Banana 2 ({IMAGE_MODEL_PRIMARY})...")
    img_bytes = _call_gemini_image_model(test_prompt, IMAGE_MODEL_PRIMARY)
    if img_bytes:
        print(f"✅ Nano Banana 2 working! ({len(img_bytes)//1024} KB)")
        return True

    print(f"🔍 Nano Banana 2 unavailable, testing original Nano Banana ({IMAGE_MODEL_FALLBACK})...")
    img_bytes = _call_gemini_image_model(test_prompt, IMAGE_MODEL_FALLBACK)
    if img_bytes:
        print(f"✅ Original Nano Banana working! ({len(img_bytes)//1024} KB)")
        print("   (Nano Banana 2 may not be enabled on this key yet — that's fine, "
              "the code will keep using this model automatically.)")
        return True

    print("❌ Both Nano Banana models failed. Check your nano_api_key and quota at "
          "https://aistudio.google.com/apikey")
    return False


# Backward-compatible alias in case other files still call the old name.
test_gemini_connection = test_nano_banana_connection