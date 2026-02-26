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
    "A marmalade cat dozing on a sun-drenched terracotta tile floor, slow overhead crane descending, warm Mediterranean light with dust motes, lazy summer siesta, deep rumbling purr with distant church bells and cicadas",
    "A Russian Blue cat nestled in a hammock on a screened porch, gentle swaying motion, dappled shade with patches of warm sunlight, breezy and tranquil, creaking hammock rope with soft wind chimes and a lazy acoustic guitar",
    "A fluffy Himalayan cat sleeping on a pile of fresh laundry, slow dolly across the scene, warm overhead laundry room light, cloud-like softness, dryer humming in the background with contented cat breathing",
    "A tabby cat and a calico sharing a single armchair cushion, slow push in, warm reading lamp light casting amber shadows, companionable silence, synchronized purring with rain on a tin roof",
    "A black cat curled in a ceramic sink basin, overhead static shot, soft bathroom light with steam wisps from a nearby shower, quirky coziness, gentle water dripping with a mellow jazz bass line",
    "A ginger cat sleeping against a fogged window while snow falls outside, close-up with rack focus between cat and snowflakes, cool blue exterior light contrasting warm amber interior, winter sanctuary, muffled snowfall hush with a gentle piano nocturne",
    "A Persian cat lying across an open piano keyboard, slow tracking along the keys, warm stage light from a single source, artistic and dreamy, accidental soft piano notes resonating with a low purr",
    "A Maine Coon sprawled across a farmhouse kitchen table next to a cooling pie, wide shot with shallow focus, golden late afternoon light through gingham curtains, rustic comfort, ticking kitchen timer with distant rooster crow and contented sighs",
    "A pair of Siamese cats intertwined on a meditation cushion, slow orbit shot, soft candlelit ambiance with incense smoke curling, zen-like peace, singing bowl resonance fading into rhythmic tandem purring",
    "A calico cat tucked behind the pillows of a window seat during a thunderstorm, close-up with lightning flashes illuminating the scene, dramatic contrast between storm and safety, sheltered warmth, rolling thunder muffled by glass with steady purring",
    "A long-haired grey cat asleep on a vintage record player as the vinyl spins, slow zoom in, warm retro-toned lighting with amber highlights, analog nostalgia, vinyl crackle and pop with a faint jazz standard melody",
    "A tabby kitten napping inside a wool-lined boot by the front door, macro close-up, low warm light from a nearby hallway, impossibly snug, tiny rhythmic breathing with quiet ticking of a hallway clock",
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
    "A Maine Coon kitten batting at a dripping faucet, close-up tracking the water drops, bright kitchen lighting with water reflections, fascinated and determined, rhythmic dripping with splashy paw slaps and a playful marimba riff",
    "A ginger cat leaping from shelf to shelf in a bookcase, wide side-angle tracking shot, warm interior light with motion blur, parkour energy, books thudding and sliding with an upbeat electronic drum pattern",
    "A kitten chasing a ping-pong ball down a staircase, overhead tracking shot following the bouncing ball, bright stairwell lighting, chaotic and joyful, rapid bouncing sounds with tiny galloping paws and a peppy banjo tune",
    "Two cats engaged in a play-fight standing on hind legs, slow motion medium shot, bright window backlight creating silhouettes, epic boxing match energy, dramatic whooshing air with comedic impact sounds and an action movie riff",
    "A Bengal cat weaving through an obstacle course of toilet paper rolls, low angle tracking shot, bright even lighting, agile and focused, paper rolls spinning and clattering with a fast-paced bongo rhythm",
    "A tabby kitten discovering a wind-up toy mouse and chasing it in circles, overhead shot, warm playroom light, dizzy excitement, clicking wind-up mechanism with tiny scrabbling claws and a carousel music box melody",
    "A Siamese cat playing fetch with a crumpled paper ball, wide shot following the throw and retrieval, bright living room light, surprisingly dog-like, paper crinkling with padding paw returns and an upbeat whistling tune",
    "A kitten pouncing at shadows of swaying tree branches on a sunlit wall, medium shot with the shadow patterns moving, warm dappled light, entranced and explosive, gentle rustling leaves with sudden pounce thuds and a playful pizzicato string accent",
    "A cat chasing its reflection in a shiny hardwood floor, low-angle tracking shot, bright overhead light creating mirror reflections, bewildered and relentless, squeaking paws on polished wood with a quirky synth melody",
    "A fluffy cat diving headfirst into a pile of autumn leaves, slow motion side angle, warm golden outdoor light, gleeful abandon, explosive leaf crunching with a joyful fiddle reel",
    "A kitten playing with a tablet screen showing a fish game, overhead close-up on paws tapping glass, cool screen glow mixed with warm room light, modern and adorable, digital blip sounds with rapid tapping and a chiptune melody",
    "An orange cat racing a remote-control car across a living room, fast tracking shot at floor level, bright daylight from windows, competitive spirit, motor buzzing with thundering paws and an adrenaline-pumping synth bass line",
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
    "A Bombay cat walking along a dimly lit subway platform as a train approaches, wide shot with headlights growing, harsh fluorescent mixed with warm tunnel glow, urban mystery, distant rumbling crescendo with echoing footsteps and a brooding synth bass",
    "A white cat standing alone in a vast wheat field at golden hour, slow aerial drone pullback revealing endless landscape, warm directional sidelight with long shadow, epic solitude, rustling wheat stalks with a soaring solo violin melody",
    "A grey cat perched on a moss-covered temple ruin in thick jungle, slow pan revealing the overgrown architecture, green-filtered light with god rays breaking through canopy, ancient guardian, dripping water and jungle bird calls with a deep resonant gong",
    "A black cat watching the Northern Lights through a cabin window, static frame with aurora borealis reflecting in its eyes, shifting green and purple light, cosmic wonder, howling distant wind with an ethereal vocal choir swell",
    "A scarred ginger tomcat sitting on a rain-slicked fire escape, slow zoom in on weathered face, cold blue neon reflections from signs below, world-weary survivor, steady rain with a melancholic blues harmonica solo",
    "A Siamese cat silhouetted atop a sand dune at sunset, wide cinematic establishing shot, deep orange to violet gradient sky, solitary wanderer, wind sweeping across sand with a sparse desert flute melody",
    "A Maine Coon walking through an abandoned library with books scattered on the floor, slow tracking shot following from behind, dusty shafts of light from broken skylights, post-apocalyptic elegance, echoing paw steps with creaking wood and a haunting piano refrain",
    "A cat sitting at the edge of a pier watching a distant lighthouse beam sweep the fog, wide shot with long exposure feel, cold misty light punctuated by the beam, contemplative solitude, lapping waves with a distant foghorn and a lonely accordion melody",
    "A Bengal cat stalking through tall grass in harsh moonlight, low angle tracking shot, silver-blue lunar illumination with stark shadows, primal hunter, rustling grass with crickets and a tense low string tremolo building slowly",
    "A tuxedo cat standing in an empty cathedral with light streaming through stained glass, slow tilt up from cat to rose window, kaleidoscopic colored light, sacred and still, reverberant silence with a single distant organ chord resonating",
    "A grey cat sitting on the hood of an abandoned car in a misty forest, slow dolly around the scene, cold diffused overcast light with fog tendrils, eerie beauty, dripping condensation with distant crow calls and a minimal ambient drone",
    "A black cat walking along a neon-lit Tokyo alley in the rain at night, tracking shot at cat height, vivid pink and blue neon reflections in puddles, cyberpunk atmosphere, rain pattering on awnings with muffled city noise and a lo-fi synth melody",
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
    "A cat dramatically flopping onto its side in the middle of a hallway for no reason, slow motion side angle, neutral overhead lighting, existential collapse, theatrical thud with a sad trombone descending note",
    "A cat startled by its own sneeze and tumbling backwards off a table, slow motion close-up, bright kitchen light, self-inflicted catastrophe, a tiny sneeze followed by scrambling claws and a comedic crash with a cartoon boing",
    "A cat trying to drink from a running kitchen faucet and getting splashed in the face repeatedly, medium close-up, bright overhead light with water sparkle, stubbornly undeterred, splashing water with a vaudeville piano loop",
    "A cat wearing a tiny lion mane costume sitting with supreme dignity, slow push in, portrait lighting with dark background, unimpressed royalty, regal trumpet fanfare undone by an irritated tail flick swish",
    "A cat sitting in a salad bowl on the kitchen counter staring at the camera, wide static shot, clean bright overhead light, claiming territory, crunching lettuce sounds with a defiant meow and deadpan silence",
    "A cat squeezing through an impossibly narrow gap between furniture, slow motion side angle, warm interior light, liquid physics, stretching and compressing sound effects with a rubber band twang and amazed gasp sound",
    "A cat watching a nature documentary about birds and chittering at the TV screen, over-the-shoulder shot, cool TV glow on face, obsessed armchair predator, muffled documentary narration with frantic teeth chattering and a tense action movie underscore",
    "A cat stealing a slice of bread off the counter and running away with it, fast tracking shot at floor level, bright kitchen light with motion blur, brazen heist, rapid paw thumping with a Mission Impossible theme parody riff",
    "A cat attempting to jump onto a counter and completely misjudging the distance, slow motion wide shot, clear daylight, tragic miscalculation, confident launch sounds deflated by a belly-flop thud and a sad price-is-right losing horn",
    "Two cats sitting side by side grooming themselves in perfect synchronization then both stopping to stare at camera simultaneously, static medium shot, soft natural light, coordinated creepiness, synchronized licking sounds halted by dead silence",
    "A cat with a piece of tape stuck to its paw walking with exaggerated high steps across a room, tracking shot at ground level, bright even lighting, deeply offended by physics, sticky peeling sounds with ridiculous tip-toe xylophone notes",
    "A cat pushing another cat off a shelf in slow motion with one paw while maintaining eye contact with the camera, medium shot, warm shelf lighting, calculated betrayal, slow motion whoosh with a dramatic gasp and a distant thud",
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
    "A tiny kitten with oversized ears peeking out from behind a flower pot, slow zoom in revealing just the eyes and ears, soft garden light, impossibly shy, quiet rustling leaves with a delicate flute trill",
    "A kitten falling asleep mid-play with a toy still in its mouth, close-up with shallow depth of field, warm golden light, fighting sleep and losing, slowing toy jingles fading into soft breathing with a gentle lullaby hum",
    "A fluffy white kitten standing on its hind legs reaching for a dandelion puff, slow motion side angle, bright backlit outdoor light with bokeh, graceful and tiny, soft breeze sounds with seeds floating and a twinkling celesta melody",
    "A kitten fitting perfectly inside a teacup on a saucer, macro close-up, warm soft-focus light, impossibly miniature, tiny heartbeat sounds with a dainty music box tune and a barely audible mew",
    "Two kittens sleeping in a yin-yang formation, slow overhead pull back, warm even lighting, perfect symmetry, matched breathing rhythms with a peaceful ambient pad and gentle wind sounds",
    "A kitten with heterochromia staring directly into the camera with huge round eyes, extreme close-up with rack focus on the eyes, soft ring light reflections, mesmerizing and soulful, quiet breathing with a gentle sustained harp chord",
    "A tiny tabby kitten carrying a stuffed mouse bigger than its head across a room, low angle tracking shot, warm interior light, determined and adorable, dragging fabric sounds with tiny grunting effort and a sweet piccolo melody",
    "A kitten licking its paw and accidentally falling over sideways in slow motion, medium shot with soft background, gentle natural light, clumsy grace, a soft lick sound followed by a tiny tumble thud with a sweet vibraphone accent",
    "A calico kitten sitting in a field of wildflowers at eye level, slow dolly forward through the flowers, warm golden hour sidelight with lens flare, storybook perfection, buzzing bees and gentle breeze with a pastoral acoustic guitar melody",
    "A grey kitten gently batting at a goldfish through a glass bowl, close-up alternating focus between kitten and fish, cool aquatic light mixed with warm room light, wonder and fascination, bubbling water with soft glass tapping and a curious oboe melody",
    "A newborn kitten being held up to its mother's face for the first time, close-up on both faces, warm soft overhead light, primal tenderness, mother's deep purr vibrating with the kitten's first tiny mew and a soaring string swell",
    "A fluffy ginger kitten sitting in a miniature shopping cart in a dollhouse, static wide shot, bright cheerful toy-store lighting, absurdly precious, tiny squeaky wheel sounds with a cheerful glockenspiel jingle",
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
