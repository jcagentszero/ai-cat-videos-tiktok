import pytest

SAMPLE_SCRIPT_MD = """\
---
id: belly-rub-betrayal
title: The Belly Rub Betrayal
logline: A cat lures its owner into the oldest trap in feline history.
caption: The belly was never an offer. It was a test.
hook: She's offering her belly. This is a gift.
hashtags:
  - bellyrub
  - cattrap
duration_seconds: 30
created: 2026-07-04
---

## Shot 1 — The Invitation (0:00–0:06)

> [CAT] lying on its back on a sunlit living room rug, belly fully exposed,
> slow blinking at the camera, warm golden-hour light, static low-angle shot.

- **Audio:** Soft, dreamy piano. Gentle purring.
- **Text overlay:** "She's offering her belly. This is a gift."

## Shot 2 — The Trap Springs (0:06–0:12)

> Slow-motion shot of [CAT] snapping shut around a human hand like a bear trap,
> bunny-kicking with rear legs, 120fps slow motion.

- **Audio:** Horror-movie string stab.
- **Text overlay:** "THE MURDER REFLEX HAS BEEN ACTIVATED"

## Production notes

- Generate shots as separate clips and stitch.
"""


@pytest.fixture
def script_file(tmp_path):
    """A valid sample script written to a temp file."""
    path = tmp_path / "belly-rub-betrayal.md"
    path.write_text(SAMPLE_SCRIPT_MD)
    return path
