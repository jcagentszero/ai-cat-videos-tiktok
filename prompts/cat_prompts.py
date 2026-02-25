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
    "A white Persian cat napping on a stack of old books by a bay window, slow dolly in, warm amber light filtering through lace curtains, nostalgic and serene, soft page-rustling sounds with a gentle cello melody",
    "A ginger cat kneading a thick wool blanket on a rocking chair, medium close-up, flickering warm lamplight, deeply relaxing, rhythmic purring with quiet ticking of a grandfather clock",
    "A grey British Shorthair sleeping in a wicker basket lined with fleece, overhead shot slowly rotating, soft morning light, utterly peaceful, deep resonant purring with distant birdsong through an open window",
    "A tortoiseshell cat curled around a sleeping kitten on a velvet cushion, slow push in to close-up, warm candlelight glow, tender and loving, synchronized breathing sounds with a soft music box lullaby",
    "A Siamese cat lounging on a sheepskin rug beside a crackling fireplace, wide shot with shallow depth of field, warm orange flickering light, hypnotically cozy, fire crackling and popping with faint purring",
    "A tabby cat nestled inside an open suitcase full of soft sweaters, static close-up, hazy afternoon light from a nearby window, whimsical and snug, gentle fabric rustling with lo-fi piano chords",
    "A long-haired calico cat sleeping on a porch swing as leaves drift past, slow tracking shot, dappled golden hour light, autumnal warmth, creaking swing chain with crickets and a soft acoustic strum",
    "A ragdoll cat sprawled across a person's lap while they read, close-up on the cat's face, soft overhead reading lamp glow, intimate and quiet, turning pages and deep rumbling purr",
    "A Scottish Fold cat tucked into a ceramic bowl on a kitchen counter, slow zoom in, warm morning sunlight streaming sideways, absurdly cozy, gentle humming of a refrigerator with contented cat sighs",
    "A tuxedo cat sleeping nose-to-nose with a golden retriever on a plaid dog bed, wide shot to close-up, soft diffused window light, heartwarming cross-species friendship, gentle overlapping breathing sounds with warm ambient pads",
]

PLAYFUL = [
    "A kitten batting at a hanging feather toy, slow motion, bright playful lighting, eye-level tracking shot, white background, upbeat pizzicato strings and tiny paw tapping sounds",
    "A cat pouncing on a crinkle ball across a hardwood floor, overhead tracking shot, crisp natural light, energetic, crinkling sounds with playful xylophone melody",
    "Three kittens tumbling over each other in a basket, wide shot to close-up zoom, warm light, chaotic and adorable, tiny mews and soft tumbling sounds with lighthearted piano",
    "A Bengal cat chasing a laser dot across a white wall, fast tracking shot following the dot, bright even lighting, frenetic energy, rapid paw scrabbling on wood with a bouncy synth beat",
    "A kitten leaping between couch cushions in slow motion, side-angle tracking shot, bright afternoon light, joyful and athletic, springy boing sound effects with peppy ukulele strumming",
    "A cat sliding across a tile floor after a toy mouse, low-angle tracking shot, clean overhead lighting, hilarious momentum, claws skittering on tile with a comedic slide whistle accent",
    "Two kittens playing tug-of-war with a ribbon, medium shot rocking between them, warm playroom light, competitive and adorable, tiny growls and tugging sounds with staccato violin pizzicato",
    "A ginger cat doing zoomies around a living room in a figure eight, wide overhead shot, bright daylight, chaotic energy, thundering tiny paws on carpet with an accelerating drumbeat",
    "A cat leaping to catch a bubble floating in the air, slow motion close-up, iridescent light reflections, magical and playful, soft bubble pop with a whimsical glockenspiel trill",
    "A kitten wrestling with a sock twice its size, eye-level static shot, soft studio lighting, determined and silly, muffled fabric wrestling sounds with a cheerful accordion melody",
    "A Siamese cat batting at dangling wind chimes on a porch, medium close-up, golden afternoon backlight, curious and mesmerized, melodic chime ringing with soft paw taps",
    "A tabby cat chasing its own tail in tight circles on a rug, overhead shot, warm interior lighting, dizzy and relentless, spinning paw thuds with a playful calliope tune",
    "A black kitten ambushing a feather from behind a curtain, slow motion reveal shot, dramatic side lighting, stealthy then explosive, rustling fabric burst with a triumphant brass fanfare",
]

DRAMATIC = [
    "A sleek black cat sitting on a marble windowsill at night, city lights below, cinematic wide shot, moody blue-purple light, deep ambient synth drone with distant city hum",
    "A cat silhouetted against a sunset window, slow zoom out to reveal city skyline, golden backlight, cinematic aspect ratio, sweeping orchestral strings building slowly",
    "A Maine Coon cat walking slowly toward camera through shallow fog, forest background, eerie dawn light, mysterious, low cello notes with birds chirping faintly in the distance",
    "A white cat perched on a stone gargoyle atop a Gothic building, slow crane shot pulling back, stormy twilight sky, epic and solitary, howling wind with a deep choir pad swelling",
    "A black cat crossing a rain-soaked cobblestone alley at night, tracking shot at ground level, neon reflections in puddles, noir atmosphere, splashing footsteps with a moody saxophone riff",
    "A Bengal cat staring down from a fire escape in a narrow alleyway, slow tilt up from ground, harsh streetlamp light cutting through darkness, intense and vigilant, distant sirens with a low pulsing bass drone",
    "An orange tabby sitting motionless at the end of a long dark hallway, slow dolly in, single overhead light creating a halo, ominous and riveting, echoing silence with a barely audible heartbeat rhythm",
    "A Norwegian Forest Cat standing on a snow-covered rock overlooking a frozen lake, wide establishing shot, pale blue winter light, majestic and wild, howling arctic wind with sparse ethereal vocals",
    "A Siamese cat watching lightning through a floor-to-ceiling window, static frame close-up on reflective eyes, dramatic strobe flashes, awestruck, rolling thunder with tense string tremolo",
    "A grey cat walking along a crumbling stone wall at golden hour, slow tracking shot, warm directional light with long shadows, timeless and contemplative, rustling dry grass with a solo French horn melody",
    "A black cat leaping between rooftops at dusk, slow motion side angle, deep orange sky bleeding into indigo, athletic and fearless, rushing air with a cinematic brass crescendo",
    "A Persian cat sitting regally on a velvet throne in a dimly lit room, slow push in, single spotlight with dust motes floating, aristocratic and mysterious, ticking clock with a slow dramatic piano chord progression",
    "A tabby cat emerging from ocean fog on a rocky shore at dawn, wide shot with waves crashing, cold diffused grey light, solitary and powerful, crashing waves and seagull cries with a haunting violin solo",
]

FUNNY = [
    "A cat sitting in a cardboard box looking intensely at camera, slow dramatic zoom in, deadpan expression, dramatic orchestral music building to a comedic pause",
    "A cat knocking a glass off a table in slow motion, neutral expression, overhead shot, crisp studio lighting, suspenseful timpani roll followed by a satisfying glass clink",
    "A cat staring at a blank wall for no reason, slow zoom in from behind, tense atmosphere, minimal background, exaggerated suspense music with a quiet confused meow",
    "A fat orange cat wedged tightly in a paper bag with only its face visible, static close-up, bright kitchen lighting, absurdly stuck and unbothered, crinkling paper with a deadpan comedic tuba note",
    "A cat trying to fit into a tiny shoebox and slowly squishing itself down, time-lapse compression, even overhead light, determined and ridiculous, squeaking compression sounds with a silly slide whistle melody",
    "A cat sitting on a laptop keyboard during a video call, webcam POV angle, screen glow on face, supremely indifferent to chaos, muffled video call voices with a dramatic record scratch",
    "A cat staring at a cucumber placed behind it then doing a startled vertical leap, slow motion side angle, bright daylight, shock and betrayal, loud cartoon spring boing with a surprised yowl",
    "A cat drinking water and missing its mouth repeatedly, extreme close-up, soft backlight catching water droplets, elegantly incompetent, water splashing sounds with sophisticated jazz piano",
    "A fluffy cat with its tongue permanently stuck out sitting in a dignified pose, slow zoom in, portrait-style lighting with dark background, unintentionally hilarious, regal trumpet fanfare with a wet blep sound",
    "Two cats on opposite ends of a couch slowly reaching paws toward each other, dramatic slow motion, warm golden light, Michelangelo parody, soaring opera vocals building to an anticlimatic paw boop",
    "A cat falling asleep sitting upright and slowly tipping over, medium shot, soft living room light, fighting gravity and losing, gentle snoring accelerating into a comedic thud with a surprised chirp",
    "A cat aggressively grooming itself then pausing to glare at the camera mid-lick, static medium shot, neutral studio lighting, confrontational hygiene, abrupt silence with a single judgmental meow",
    "A cat walking confidently toward a glass door and bonking its nose on it, tracking shot to static impact, clear daylight, peak slapstick, confident footsteps halted by a hollow bonk with a stunned pause",
]

CUTE = [
    "A tiny grey kitten attempting to climb a slightly too-tall step, side angle, soft pastel light, looping, gentle music box melody with tiny squeaky mews",
    "A cat with huge round eyes discovering a mirror for the first time, close-up on face, warm light, heartwarming, soft harp glissando with a curious chirping trill",
    "A calico kitten yawning in extreme close-up revealing tiny teeth, soft macro lighting, slow motion, gentle lullaby humming with a breathy kitten sigh",
    "A tiny orange kitten falling asleep in a person's cupped hands, extreme close-up, warm golden skin tones, impossibly small and precious, soft heartbeat with a delicate celesta melody",
    "A kitten seeing snow for the first time through a window and tapping the glass with one paw, close-up on paw and glass, cool blue-white light, wonder and innocence, gentle glass tapping with a sparkling chime accent",
    "A round-faced munchkin kitten waddling toward the camera on stubby legs, low-angle tracking shot, bright pastel nursery light, maximum adorable factor, tiny padding footsteps with a cute whistling tune",
    "A kitten curled up sleeping inside a coffee mug on a desk, macro close-up, warm desk lamp light, impossibly tiny, gentle breathing with a soft lo-fi beat and pen scratching sounds",
    "Two kittens booping noses and then recoiling in surprise, medium shot, soft even lighting, heart-melting synchronization, twin squeaky mews with a gentle harp pluck",
    "A fluffy white kitten with blue eyes staring up at a butterfly landing on its nose, close-up with shallow depth of field, dappled garden sunlight, pure enchantment, butterfly wing flutters with a twinkling music box phrase",
    "A kitten wrapped in a tiny towel after a bath with only its face poking out, static close-up, warm bathroom light, soggy and adorable, dripping water with a gentle marimba lullaby",
    "A grey kitten discovering its own reflection in a puddle and tilting its head, eye-level close-up, overcast soft light with mirror reflections, curious innocence, quiet water ripple with a wondering flute melody",
    "A kitten riding on top of a Roomba around a living room, overhead tracking shot following the path, bright daylight, effortlessly cool, robotic humming with a chill lo-fi hip hop beat",
    "Three newborn kittens crawling over each other in a fleece-lined box, macro overhead shot, warm soft light, overwhelming tenderness, tiny squeaks and rustling fabric with a gentle piano waltz",
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
