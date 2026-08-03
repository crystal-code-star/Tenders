

import os
import textwrap
from datetime import datetime

from utils.storage import (
    get_all_posts,
    save_post,
    build_schedule,
)


def _clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def _print_post(post: dict, total: int) -> None:
    """Pretty-print one post for the reviewer to read."""
    print("=" * 70)
    print(f"  Day {post['id']} of {total}   |   Status: {post['status'].upper()}")
    print("=" * 70)

    if post.get("image_path"):
        print(f"  Image: {post['image_path']}")
    else:
        print("  Image: [not generated]")

    print()
    print("  POST TEXT:")
    print("  " + "-" * 60)
    # Wrap long lines for terminal readability
    for line in post["post_text"].split("\n"):
        wrapped = textwrap.fill(line, width=65, subsequent_indent="  ")
        print("  " + wrapped)
    print()


def _ask_action(post: dict) -> dict:
    """
    Show options and return the (possibly modified) post dict.
    """
    while True:
        print("  Options:")
        print("    [A] Approve as-is")
        print("    [E] Edit post text")
        print("    [R] Reject (skip this day)")
        print("    [S] Skip for now (decide later)")
        print()

        choice = input("  Your choice (A/E/R/S): ").strip().upper()

        if choice == "A":
            post["status"] = "approved"
            print("  Approved.\n")
            return post

        elif choice == "E":
            print()
            print("  Paste your replacement text. Type END on a new line when done:")
            lines = []
            while True:
                line = input()
                if line.strip().upper() == "END":
                    break
                lines.append(line)
            post["post_text"] = "\n".join(lines).strip()
            post["status"]    = "approved"
            print("  Updated and approved.\n")
            return post

        elif choice == "R":
            post["status"] = "rejected"
            print("  Rejected.\n")
            return post

        elif choice == "S":
            print("  Skipped — still pending.\n")
            return post

        else:
            print("  Invalid choice. Please enter A, E, R, or S.\n")


def _setup_schedule() -> tuple:
    """
    Interactively ask the reviewer when to start posting.
    Returns (start_date: datetime, hour: int).
    """
    print("\n" + "=" * 70)
    print("  SCHEDULE SETUP")
    print("=" * 70)
    print("  When should Day 1 post go live?\n")

    while True:
        date_str = input("  Start date (YYYY-MM-DD) [default: today]: ").strip()
        if not date_str:
            start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            break
        try:
            start_date = datetime.strptime(date_str, "%Y-%m-%d")
            break
        except ValueError:
            print("  Invalid date format. Use YYYY-MM-DD.\n")

    while True:
        hour_str = input("  Posting hour (0-23, default 9 for 9 AM): ").strip()
        if not hour_str:
            hour = 9
            break
        try:
            hour = int(hour_str)
            if 0 <= hour <= 23:
                break
            print("  Hour must be between 0 and 23.\n")
        except ValueError:
            print("  Please enter a number.\n")

    return start_date, hour


def run() -> None:
    """
    Main review loop — show each pending post, collect decisions,
    then optionally build the posting schedule.
    """
    posts = get_all_posts()

    if not posts:
        print("[Reviewer] No posts found. Run Phase 1 (generation) first.")
        return

    pending = [p for p in posts if p["status"] == "pending"]

    if not pending:
        already_approved = len([p for p in posts if p["status"] == "approved"])
        print(f"[Reviewer] No pending posts. {already_approved} already approved.")
    else:
        print(f"\n[Reviewer] {len(pending)} posts to review.\n")
        input("  Press Enter to start reviewing...")

        for post in pending:
            _clear_screen()
            _print_post(post, len(posts))
            updated = _ask_action(post)
            save_post(updated)

        print("\n[Reviewer] Review session complete.")

    # Show summary
    all_posts = get_all_posts()
    approved = [p for p in all_posts if p["status"] == "approved"]
    rejected = [p for p in all_posts if p["status"] == "rejected"]
    still_pending = [p for p in all_posts if p["status"] == "pending"]
    posted = [p for p in all_posts if p["status"] == "posted"]

    print(f"\n  Summary:")
    print(f"    Approved  : {len(approved)}")
    print(f"    Rejected  : {len(rejected)}")
    print(f"    Pending   : {len(still_pending)}")
    print(f"    Posted    : {len(posted)}")

    # Offer to set the schedule if there are approved posts without a schedule
    unscheduled = [p for p in approved if not p.get("scheduled_for")]
    if unscheduled:
        print(f"\n  {len(unscheduled)} approved post(s) have no schedule yet.")
        build_now = input("  Set up posting schedule now? (Y/n): ").strip().upper()
        if build_now != "N":
            start_date, hour = _setup_schedule()
            build_schedule(start_date, hour=hour)
            print("\n  Schedule built! Run scheduler.py daily (or set up a cron job).")
    else:
        print("\n  All approved posts are already scheduled.")
