import os
import uuid
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
BUCKET_NAME  = "post-images"


def get_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise EnvironmentError(
            "SUPABASE_URL or SUPABASE_SERVICE_KEY not set.\n"
            f"  SUPABASE_URL={SUPABASE_URL}\n"
            f"  SUPABASE_SERVICE_KEY={'SET' if SUPABASE_KEY else 'MISSING'}"
        )
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def upload_image_bytes(image_bytes: bytes, day_id: int) -> str:
    """
    Upload raw image bytes to Supabase Storage.
    Returns the permanent public URL.
    No local file needed.
    """
    client    = get_client()
    file_name = f"day_{day_id}_{uuid.uuid4().hex[:6]}.png"

    client.storage.from_(BUCKET_NAME).upload(
        path=file_name,
        file=image_bytes,
        file_options={"content-type": "image/png"}
    )

    public_url = f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET_NAME}/{file_name}"
    print(f"  [image_storage] Uploaded → {public_url}")
    return public_url


def upload_image(local_path: str, day_id: int) -> str:
    """
    Upload from a local file path (used by the manual upload API endpoint).
    Returns the permanent public URL.
    """
    if not local_path or not os.path.exists(local_path):
        raise FileNotFoundError(f"File not found: {local_path}")

    with open(local_path, "rb") as f:
        return upload_image_bytes(f.read(), day_id)


def delete_image(image_url: str) -> None:
    if not image_url:
        return
    file_name = image_url.split("/")[-1]
    get_client().storage.from_(BUCKET_NAME).remove([file_name])
    print(f"  [image_storage] Deleted: {file_name}")