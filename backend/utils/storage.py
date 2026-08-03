"""
utils/storage.py  —  Supabase/PostgreSQL version (v4)
═══════════════════════════════════════════════════════
Same drop-in interface as before, updated for new fields:
  - language, day_angle, day_number, custom_text, product_name
  - created_at (date de génération du post)

Run this SQL in Supabase first to add new columns:

  ALTER TABLE posts ADD COLUMN IF NOT EXISTS language      TEXT DEFAULT 'english';
  ALTER TABLE posts ADD COLUMN IF NOT EXISTS day_angle     TEXT;
  ALTER TABLE posts ADD COLUMN IF NOT EXISTS day_number    INTEGER;
  ALTER TABLE posts ADD COLUMN IF NOT EXISTS custom_text   TEXT;
  ALTER TABLE posts ADD COLUMN IF NOT EXISTS product_name  TEXT;
  ALTER TABLE posts ADD COLUMN IF NOT EXISTS created_at    TIMESTAMP;
"""

import os
from typing import List, Optional
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(
    DATABASE_URL,
    connect_args={"sslmode": "require"},
    pool_pre_ping=True,
    pool_recycle=300,
)


def _row_to_dict(row) -> dict:
    return {
        "id":               row.id,
        "topic":            row.topic,
        "post_text":        row.post_text,
        "image_prompt":     row.image_prompt,
        "image_path":       getattr(row, 'image_path', None),
        "image_url":        row.image_url,
        "status":           row.status,
        "scheduled_for":    row.scheduled_for.isoformat() if row.scheduled_for else None,
        "posted_at":        row.posted_at.isoformat() if row.posted_at else None,
        "created_at":       row.created_at.isoformat() if getattr(row, 'created_at', None) else None,
        "linkedin_post_id": row.linkedin_post_id,
        "language":         getattr(row, 'language', 'english'),
        "day_angle":        getattr(row, 'day_angle', None),
        "day_number":       getattr(row, 'day_number', None),
        "custom_text":      getattr(row, 'custom_text', ''),
        "product_name":     getattr(row, 'product_name', ''),
    }


def save_post(post: dict) -> None:
    with engine.connect() as conn:
        conn.execute(text("""
            INSERT INTO posts
              (id, topic, post_text, image_prompt, image_url, status,
               scheduled_for, posted_at, created_at, linkedin_post_id,
               language, day_angle, day_number, custom_text, product_name)
            VALUES
              (:id, :topic, :post_text, :image_prompt, :image_url, :status,
               :scheduled_for, :posted_at, :created_at, :linkedin_post_id,
               :language, :day_angle, :day_number, :custom_text, :product_name)
            ON CONFLICT (id) DO UPDATE SET
              topic            = EXCLUDED.topic,
              post_text        = EXCLUDED.post_text,
              image_prompt     = EXCLUDED.image_prompt,
              image_url        = EXCLUDED.image_url,
              status           = EXCLUDED.status,
              scheduled_for    = EXCLUDED.scheduled_for,
              posted_at        = EXCLUDED.posted_at,
              created_at       = EXCLUDED.created_at,
              linkedin_post_id = EXCLUDED.linkedin_post_id,
              language         = EXCLUDED.language,
              day_angle        = EXCLUDED.day_angle,
              day_number       = EXCLUDED.day_number,
              custom_text      = EXCLUDED.custom_text,
              product_name     = EXCLUDED.product_name
        """), {
            "id":               post["id"],
            "topic":            post.get("topic"),
            "post_text":        post.get("post_text"),
            "image_prompt":     post.get("image_prompt"),
            "image_url":        post.get("image_url"),
            "status":           post.get("status", "pending"),
            "scheduled_for":    post.get("scheduled_for"),
            "posted_at":        post.get("posted_at"),
            "created_at":       post.get("created_at"),
            "linkedin_post_id": post.get("linkedin_post_id"),
            "language":         post.get("language", "english"),
            "day_angle":        post.get("day_angle"),
            "day_number":       post.get("day_number"),
            "custom_text":      post.get("custom_text", ""),
            "product_name":     post.get("product_name", ""),
        })
        conn.commit()


def get_all_posts() -> List[dict]:
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT * FROM posts ORDER BY id DESC")).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_post(day_id: int) -> Optional[dict]:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT * FROM posts WHERE id = :id"), {"id": day_id}
        ).fetchone()
    return _row_to_dict(row) if row else None


def get_next_available_id() -> int:
    """Return the next unused integer ID (globally unique, not per day)."""
    with engine.connect() as conn:
        row = conn.execute(text("SELECT COALESCE(MAX(id), 0) + 1 AS next_id FROM posts")).fetchone()
    return row.next_id


def delete_post(day_id: int) -> None:
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM posts WHERE id = :id"), {"id": day_id})
        conn.commit()


def get_next_to_post() -> Optional[dict]:
    now = datetime.now()
    with engine.connect() as conn:
        row = conn.execute(text("""
            SELECT * FROM posts
            WHERE  status = 'approved'
              AND  scheduled_for IS NOT NULL
              AND  scheduled_for <= :now
            ORDER BY scheduled_for ASC, id ASC
            LIMIT 1
        """), {"now": now}).fetchone()
    return _row_to_dict(row) if row else None


def build_schedule(start_date: datetime, hour: int = 9, minute: int = 0) -> None:
    posts   = get_all_posts()
    approved = sorted([p for p in posts if p["status"] == "approved"], key=lambda p: p["id"])
    with engine.connect() as conn:
        for i, post in enumerate(approved):
            t = (start_date + timedelta(days=i)).replace(
                hour=hour, minute=minute, second=0, microsecond=0
            )
            conn.execute(text("UPDATE posts SET scheduled_for = :t WHERE id = :id"),
                         {"t": t, "id": post["id"]})
        conn.commit()
    print(f"[Storage] Schedule built: {len(approved)} posts from {start_date.date()}")


def mark_posted(day_id: int, linkedin_post_id: str) -> None:
    with engine.connect() as conn:
        conn.execute(text("""
            UPDATE posts SET status='posted', posted_at=:now, linkedin_post_id=:lid WHERE id=:id
        """), {"now": datetime.now(), "lid": linkedin_post_id, "id": day_id})
        conn.commit()


def clear_all() -> None:
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM posts"))
        conn.commit()
    print("[Storage] All posts deleted.")