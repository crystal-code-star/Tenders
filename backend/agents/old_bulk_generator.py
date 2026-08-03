from tools.hf_llm_tool import infer
from tools.dalle_tool import generate_image
from utils.storage import save_post, get_next_available_id

DAY_ANGLES = [
    "Hook and big-picture overview — grab attention, set the stage",
    "Surprising statistic or data point — lead with a number that shocks",
    "Real-world case study or example — make it concrete and relatable",
    "Common misconception debunked — challenge a widespread belief",
    "Step-by-step practical tip — give immediately actionable advice",
    "Future prediction / thought leadership — bold forward-looking take",
    "Call to action + community question — invite engagement and discussion",
]

def _post_prompt(topic: str, day: int, angle: str) -> str:
    return (
        f"Write a LinkedIn post about '{topic}'. This is Post #{day}. "
        f"Today's angle: {angle}.\n\n"
        "Follow this exact format:\n"
        "- Line 1: A short punchy hook (no 'I', no fluff)\n"
        "- Lines 2-6: 3 to 5 short insight paragraphs or bullet points\n"
        "- Last paragraph: one clear call-to-action or question\n"
        "- Very last line: 3 to 5 relevant hashtags\n\n"
        "After the post, write this separator on its own line:\n"
        "---IMAGE_PROMPT---\n"
        "Then write ONE sentence (under 150 characters) describing a professional image for this post. "
        "No text or logos in the image. Make it visually distinct from other days.\n\n"
        "Now generate the post:\n"
    )

def _refine_image_prompt(raw_prompt: str) -> str:
    prompt = (
        f"Rewrite this image idea into a vivid Stable Diffusion prompt. "
        f"Add style, lighting, and composition details. Keep it under 180 characters. "
        f"Output ONLY the improved prompt, nothing else.\n\n"
        f"Image idea: {raw_prompt}\n\nImproved prompt:"
    )
    result = infer(prompt, max_new_tokens=120, temperature=0.4)
    result = result.strip().strip('"').strip("'")
    return result if len(result) > 20 else raw_prompt

def _parse_output(raw: str) -> tuple:
    separator = "---IMAGE_PROMPT---"
    if separator in raw:
        parts      = raw.split(separator, 1)
        post_text  = parts[0].strip()
        img_prompt = parts[1].strip()
        img_prompt = img_prompt.split("\n")[0].split(".")[0].strip() + "."
    else:
        post_text  = raw.strip()
        img_prompt = ""
    post_text  = post_text.replace("[/INST]", "").strip()
    img_prompt = img_prompt.replace("[/INST]", "").strip()
    return post_text, img_prompt

def run(topic: str) -> list:
    print(f"\n[Agent 1 – Bulk Generator] Topic: '{topic}'")
    results = []

    for i in range(len(DAY_ANGLES)):
        next_id = get_next_available_id()
        angle   = DAY_ANGLES[i]

        print(f"  ── Generating Post ID: {next_id} ──────────────────────────────────────────")
        print(f"  Angle: {angle[:55]}...")

        try:
            # Step 1: Generate post text
            raw_output = infer(_post_prompt(topic, next_id, angle), max_new_tokens=700, temperature=0.75)
            post_text, raw_img_prompt = _parse_output(raw_output)

            if not post_text:
                raise ValueError("Model returned empty post text.")

            print(f"  Post text: {len(post_text)} characters")

            # Step 2: Refine image prompt
            if raw_img_prompt:
                print(f"  Refining image prompt...")
                img_prompt = _refine_image_prompt(raw_img_prompt)
            else:
                img_prompt = f"Professional illustration about {topic}, clean corporate style, 4K"

            print(f"  Image prompt: {img_prompt[:70]}...")

            # Step 3: Generate image → upload to Supabase → get URL
            print(f"  Generating and uploading image...")
            img_result = generate_image(img_prompt, day_id=next_id)

            # Step 4: Save to DB — image_url only, no image_path
            post = {
                "id":               next_id,
                "topic":            topic,
                "post_text":        post_text,
                "image_prompt":     img_prompt,
                "image_url":        img_result["image_url"],
                "status":           "pending",
                "scheduled_for":    None,
                "posted_at":        None,
                "linkedin_post_id": None,
            }
            save_post(post)
            results.append(post)
            print(f"  Post {next_id} saved ✓\n")

        except Exception as exc:
            print(f"  ERROR on Post {next_id}: {exc}\n")
            post = {
                "id":               next_id,
                "topic":            topic,
                "post_text":        f"[GENERATION FAILED: {exc}]",
                "image_prompt":     "",
                "image_url":        None,
                "status":           "rejected",
                "scheduled_for":    None,
                "posted_at":        None,
                "linkedin_post_id": None,
            }
            save_post(post)
            results.append(post)

    ok = len([r for r in results if r["status"] == "pending"])
    print(f"[Agent 1] Done. {ok}/7 posts ready for review.")
    return results