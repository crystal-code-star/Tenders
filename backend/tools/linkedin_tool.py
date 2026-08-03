import os
import json
import requests
from langchain_core.tools import Tool

LINKEDIN_API_BASE = "https://api.linkedin.com/v2"

def _headers() -> dict:
    token = os.getenv("LINKEDIN_ACCESS_TOKEN")
    if not token:
        raise EnvironmentError("LINKEDIN_ACCESS_TOKEN not set.")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type":  "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
    }

def _upload_image(image_path: str, person_urn: str) -> str:
    """Upload image to LinkedIn and return the asset URN."""
    headers = _headers()

    # 1. Register Upload
    reg_resp = requests.post(
        f"{LINKEDIN_API_BASE}/assets?action=registerUpload",
        headers=headers,
        json={
            "registerUploadRequest": {
                "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                "owner":   person_urn,
                "serviceRelationships": [{
                    "relationshipType": "OWNER",
                    "identifier":       "urn:li:userGeneratedContent",
                }],
            }
        },
        timeout=30,
    )
    reg_resp.raise_for_status()
    reg_data   = reg_resp.json()
    upload_url = reg_data["value"]["uploadMechanism"][
        "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"
    ]["uploadUrl"]
    asset_urn  = reg_data["value"]["asset"]

    # --- NEW CHANGE: Handle URL vs Local File ---
    if image_path.startswith(('http://', 'https://')):
        # If it's a Supabase URL, download the bytes from the internet
        img_response = requests.get(image_path)
        img_response.raise_for_status()
        image_bytes = img_response.content
    else:
        # If it's a local file, read it from the hard drive
        with open(image_path, "rb") as f:
            image_bytes = f.read()

            
    # --------------------------------------------

    # 2. Upload Bytes
    put_resp = requests.put(
        upload_url,
        headers={
            "Authorization": f"Bearer {os.getenv('LINKEDIN_ACCESS_TOKEN')}",
            "Content-Type":  "image/png",
        },
        data=image_bytes,
        timeout=60,
    )
    put_resp.raise_for_status()
    return asset_urn

def create_post(post_text: str, image_path: str) -> dict:
    """Publish a LinkedIn post with an image."""
    person_urn = os.getenv("LINKEDIN_PERSON_URN")
    if not person_urn:
        raise EnvironmentError("LINKEDIN_PERSON_URN not set.")

    asset_urn = _upload_image(image_path, person_urn)

    resp = requests.post(
        f"{LINKEDIN_API_BASE}/ugcPosts",
        headers=_headers(),
        json={
            "author":          person_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary":   {"text": post_text},
                    "shareMediaCategory": "IMAGE",
                    "media": [{
                        "status":      "READY",
                        "media":       asset_urn,
                        "title":       {"text": "LinkedIn AI Post"},
                        "description": {"text": post_text[:100]},
                    }],
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            },
        },
        timeout=30,
    )
    resp.raise_for_status()
    return {"post_id": resp.headers.get("X-RestLi-Id", "unknown")}

def _tool_fn(input_json: str) -> str:
    data   = json.loads(input_json)
    result = create_post(data["post_text"], data["image_path"])
    return f"Published. LinkedIn post ID: {result['post_id']}"

linkedin_tool = Tool(
    name="publish_linkedin_post",
    func=_tool_fn,
    description=(
        "Publish a LinkedIn post with image. "
        "Input: JSON string with 'post_text' and 'image_path'. "
        "Returns success message with post ID."
    ),
)