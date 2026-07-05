"""
characters/persona.py
─────────────────────
Nika's character definition, injected into every script at render time.
The prose description in characters/nika.md must contain NIKA.description
verbatim (enforced by tests/test_persona.py).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Persona:
    name: str
    breed: str
    description: str            # replaces the [CAT] placeholder in scripts
    hashtags: tuple[str, ...]   # brand hashtags appended to every post
    voice_rules: tuple[str, ...]


NIKA = Persona(
    name="Nika",
    breed="Exotic Shorthair",
    description=(
        "Nika, an Exotic Shorthair cat with a flat, permanently unimpressed "
        "face, huge round eyes, a plush dense coat, and a compact round body"
    ),
    hashtags=("nikathecat", "grumpybutsweet", "exoticshorthair", "grumpycat2"),
    voice_rules=(
        "Text overlays are deadpan and dry; no exclamation points",
        "Her face says done-with-everything; her actions are secretly sweet and social",
        "The joke is the gap between her grumpy face and her golden heart — never mock the cat",
    ),
)


def inject_persona(text: str, persona: Persona = NIKA) -> str:
    """Replace every [CAT] placeholder with the persona's description."""
    return text.replace("[CAT]", persona.description)
