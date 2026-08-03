import requests
from datetime import datetime
from utils.storage import get_next_to_post, mark_posted
import os


def post_to_zapier(post_text: str, image_url: str = None) -> bool:
    webhook_url = os.getenv("ZAPIER_WEBHOOK_URL")
    if not webhook_url:
        print("[Scheduler] ERROR: ZAPIER_WEBHOOK_URL not set in .env file.")
        return False

    payload = {
        "post_text": post_text,
        "image_url": image_url or ""  # Envoie une chaîne vide si pas d'image
    }
    try:
        response = requests.post(webhook_url, json=payload, timeout=30)
        response.raise_for_status()
        print("[Scheduler] Successfully sent post data to Zapier.")
        return True
    except Exception as e:
        print(f"[Scheduler] Failed to send data to Zapier: {e}")
        return False


def run(dry_run: bool = False) -> bool:
    post = get_next_to_post()

    if not post:
        print(f"[Scheduler] {datetime.now().strftime('%Y-%m-%d %H:%M')} — Nothing to post right now.")
        return False

    image_url = post.get("image_url")
    post_text = post.get("post_text")
    post_id = post["id"]

    print(f"\n[Scheduler] Posting Day {post_id}: '{post_text[:60]}...'")
    print(f"  Scheduled for: {post.get('scheduled_for')}")
    print(f"  Image URL:     {image_url or 'No image'}")

    # ✅ MODIFICATION : On n'exige plus d'image
    # if not image_url:
    #     print(f"[Scheduler] ERROR: No image_url for Day {post_id}. Cannot post.")
    #     return False

    if dry_run:
        print("[Scheduler] DRY RUN — skipping Zapier call.")
        return True

    success = post_to_zapier(post_text, image_url)

    if success:
        mark_posted(post_id, "via_zapier")
        print(f"[Scheduler] Day {post_id} marked as posted.")
    else:
        print(f"[Scheduler] ERROR posting Day {post_id}.")

    return success