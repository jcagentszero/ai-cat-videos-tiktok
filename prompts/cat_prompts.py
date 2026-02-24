"""
prompts/cat_prompts.py
──────────────────────
Library of Veo 3 text prompts for AI cat video generation.

Design notes:
  - Prompts should be vivid, specific, and under 500 characters
  - Include camera direction, lighting, and mood cues for better Veo output
  - Organized by category for variety across the posting schedule
  - TODO: add a prompt selector that avoids repeating recent prompts

Veo 3 prompt tips (from GCP docs):
  - Be specific about camera motion: "slow zoom", "tracking shot", "static frame"
  - Include lighting: "golden hour", "soft studio lighting", "dramatic shadows"
  - Include subject action: not just "a cat" but "a cat batting at a feather toy"
"""

import random
from datetime import datetime

# ── Prompt categories ─────────────────────────────────────────────────────────

COZY = [
    "A fluffy orange tabby cat curled in a sunbeam on a linen couch, slow zoom in, golden afternoon light, peaceful and warm",
    "A sleepy black cat tucked under a knit blanket next to a steaming mug, soft natural light, static frame, cozy autumn atmosphere",
    "Two cats grooming each other on a windowsill with rain outside, close-up shot, soft diffused light, warm and intimate",
]

PLAYFUL = [
    "A kitten batting at a hanging feather toy, slow motion, bright playful lighting, eye-level tracking shot, white background",
    "A cat pouncing on a crinkle ball across a hardwood floor, overhead tracking shot, crisp natural light, energetic",
    "Three kittens tumbling over each other in a basket, wide shot to close-up zoom, warm light, chaotic and adorable",
]

DRAMATIC = [
    "A sleek black cat sitting on a marble windowsill at night, city lights below, cinematic wide shot, moody blue-purple light",
    "A cat silhouetted against a sunset window, slow zoom out to reveal city skyline, golden backlight, cinematic aspect ratio",
    "A Maine Coon cat walking slowly toward camera through shallow fog, forest background, eerie dawn light, mysterious",
]

FUNNY = [
    "A cat sitting in a cardboard box looking intensely at camera, slow dramatic zoom in, orchestral music implied, deadpan",
    "A cat knocking a glass off a table in slow motion, neutral expression, overhead shot, crisp studio lighting",
    "A cat staring at a blank wall for no reason, slow zoom in from behind, tense atmosphere, minimal background",
]

CUTE = [
    "A tiny grey kitten attempting to climb a slightly too-tall step, side angle, soft pastel light, looping",
    "A cat with huge round eyes discovering a mirror for the first time, close-up on face, warm light, heartwarming",
    "A calico kitten yawning in extreme close-up revealing tiny teeth, soft macro lighting, slow motion",
]

ALL_PROMPTS = COZY + PLAYFUL + DRAMATIC + FUNNY + CUTE


# ── Selectors ─────────────────────────────────────────────────────────────────

def get_random_prompt() -> str:
    """Return a random prompt from all categories."""
    return random.choice(ALL_PROMPTS)


def get_prompt_by_category(category: str) -> str:
    """
    Return a random prompt from a specific category.
    category: 'cozy' | 'playful' | 'dramatic' | 'funny' | 'cute'
    """
    mapping = {
        "cozy": COZY,
        "playful": PLAYFUL,
        "dramatic": DRAMATIC,
        "funny": FUNNY,
        "cute": CUTE,
    }
    pool = mapping.get(category.lower(), ALL_PROMPTS)
    return random.choice(pool)


def get_scheduled_prompt() -> str:
    """
    Return a prompt based on day of week for variety.
    Mon/Thu = cozy, Tue/Fri = playful, Wed = dramatic, Sat = funny, Sun = cute
    TODO: add history tracking to avoid repeating recent prompts
    """
    day = datetime.now().weekday()  # 0=Mon ... 6=Sun
    schedule = {0: "cozy", 1: "playful", 2: "dramatic", 3: "cozy",
                4: "playful", 5: "funny", 6: "cute"}
    return get_prompt_by_category(schedule[day])
