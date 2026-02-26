"""
generators/caption.py
─────────────────────
LLM-powered caption generation for TikTok cat videos.

Calls Anthropic Claude to write unique, engaging captions
based on the Veo prompt and video category.
"""

import anthropic

from config import settings
from utils.logger import logger

SYSTEM_PROMPT = (
    "You write short, punchy TikTok captions for AI-generated cat videos. "
    "Rules:\n"
    "- Output ONLY the caption text, nothing else\n"
    "- Max 150 characters\n"
    "- Be witty, relatable, or heartwarming\n"
    "- Use casual TikTok voice (lowercase ok, minor slang ok)\n"
    "- Never use hashtags (those are added separately)\n"
    "- Never use quotes around the caption\n"
    "- Never describe the video technically (no mention of AI, camera angles, lighting)"
)


def generate_caption(prompt: str, category: str | None = None) -> str:
    """Call Claude to generate a unique TikTok caption for a cat video.

    Args:
        prompt: The Veo generation prompt describing the video.
        category: Optional category name (cozy, playful, dramatic, funny, cute).

    Returns:
        A short, engaging caption string.

    Raises:
        RuntimeError: If the API call fails.
    """
    if not settings.ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY not configured")

    user_msg = f"Write a TikTok caption for this cat video:\n\nVideo description: {prompt}"
    if category:
        user_msg += f"\nCategory/vibe: {category}"

    try:
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        response = client.messages.create(
            model=settings.CAPTION_MODEL,
            max_tokens=100,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
    except anthropic.APIError as exc:
        logger.error("Caption LLM API error: {}", exc)
        raise RuntimeError(f"Caption LLM API error: {exc}") from exc

    caption = response.content[0].text.strip().strip('"').strip("'")

    if len(caption) > 150:
        caption = caption[:147] + "..."

    logger.info("LLM caption generated ({} chars): {!r}", len(caption), caption)
    return caption
