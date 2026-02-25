"""
prompts/cat_prompts.py
──────────────────────
Library of Veo 3 text prompts for AI cat video generation.

Design notes:
  - Prompts should be vivid, specific, and under 500 characters
  - Include camera direction, lighting, and mood cues for better Veo output
  - Include audio/sound direction — Veo 3 generates audio natively
  - Organized by category for variety across the posting schedule
  - TODO: add a prompt selector that avoids repeating recent prompts

Veo 3 prompt tips (from GCP docs):
  - Be specific about camera motion: "slow zoom", "tracking shot", "static frame"
  - Include lighting: "golden hour", "soft studio lighting", "dramatic shadows"
  - Include subject action: not just "a cat" but "a cat batting at a feather toy"
  - Include audio cues: "soft purring", "gentle piano music", "ambient rain sounds"
"""

import random
from datetime import datetime

# ── Prompt categories ─────────────────────────────────────────────────────────

COZY = [
    "A fluffy orange tabby cat curled in a sunbeam on a linen couch, slow zoom in, golden afternoon light, peaceful and warm, soft purring sounds with gentle acoustic guitar in the background",
    "A sleepy black cat tucked under a knit blanket next to a steaming mug, soft natural light, static frame, cozy autumn atmosphere, quiet purring and crackling fireplace ambiance",
    "Two cats grooming each other on a windowsill with rain outside, close-up shot, soft diffused light, warm and intimate, gentle rain tapping on glass with soft purring",
]

PLAYFUL = [
    "A kitten batting at a hanging feather toy, slow motion, bright playful lighting, eye-level tracking shot, white background, upbeat pizzicato strings and tiny paw tapping sounds",
    "A cat pouncing on a crinkle ball across a hardwood floor, overhead tracking shot, crisp natural light, energetic, crinkling sounds with playful xylophone melody",
    "Three kittens tumbling over each other in a basket, wide shot to close-up zoom, warm light, chaotic and adorable, tiny mews and soft tumbling sounds with lighthearted piano",
]

DRAMATIC = [
    "A sleek black cat sitting on a marble windowsill at night, city lights below, cinematic wide shot, moody blue-purple light, deep ambient synth drone with distant city hum",
    "A cat silhouetted against a sunset window, slow zoom out to reveal city skyline, golden backlight, cinematic aspect ratio, sweeping orchestral strings building slowly",
    "A Maine Coon cat walking slowly toward camera through shallow fog, forest background, eerie dawn light, mysterious, low cello notes with birds chirping faintly in the distance",
]

FUNNY = [
    "A cat sitting in a cardboard box looking intensely at camera, slow dramatic zoom in, deadpan expression, dramatic orchestral music building to a comedic pause",
    "A cat knocking a glass off a table in slow motion, neutral expression, overhead shot, crisp studio lighting, suspenseful timpani roll followed by a satisfying glass clink",
    "A cat staring at a blank wall for no reason, slow zoom in from behind, tense atmosphere, minimal background, exaggerated suspense music with a quiet confused meow",
]

CUTE = [
    "A tiny grey kitten attempting to climb a slightly too-tall step, side angle, soft pastel light, looping, gentle music box melody with tiny squeaky mews",
    "A cat with huge round eyes discovering a mirror for the first time, close-up on face, warm light, heartwarming, soft harp glissando with a curious chirping trill",
    "A calico kitten yawning in extreme close-up revealing tiny teeth, soft macro lighting, slow motion, gentle lullaby humming with a breathy kitten sigh",
]

ALL_PROMPTS = COZY + PLAYFUL + DRAMATIC + FUNNY + CUTE

CATEGORY_MAP = {
    "cozy": COZY,
    "playful": PLAYFUL,
    "dramatic": DRAMATIC,
    "funny": FUNNY,
    "cute": CUTE,
}

DAY_SCHEDULE = {
    0: "cozy", 1: "playful", 2: "dramatic", 3: "cozy",
    4: "playful", 5: "funny", 6: "cute",
}


# ── Selectors ─────────────────────────────────────────────────────────────────

def get_random_prompt() -> str:
    """Return a random prompt from all categories."""
    return random.choice(ALL_PROMPTS)


def get_prompt_by_category(category: str) -> str:
    """
    Return a random prompt from a specific category.
    category: 'cozy' | 'playful' | 'dramatic' | 'funny' | 'cute'
    """
    pool = CATEGORY_MAP.get(category.lower(), ALL_PROMPTS)
    return random.choice(pool)


def get_scheduled_prompt() -> str:
    """
    Return a prompt based on day of week for variety.
    Mon/Thu = cozy, Tue/Fri = playful, Wed = dramatic, Sat = funny, Sun = cute
    TODO: add history tracking to avoid repeating recent prompts
    """
    day = datetime.now().weekday()  # 0=Mon ... 6=Sun
    return get_prompt_by_category(DAY_SCHEDULE[day])
