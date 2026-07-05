from pathlib import Path

from characters.persona import NIKA, Persona, inject_persona

NIKA_MD = Path(__file__).parent.parent / "characters" / "nika.md"


class TestPersona:
    def test_nika_is_frozen(self):
        import dataclasses
        assert dataclasses.is_dataclass(NIKA)
        assert NIKA.__dataclass_params__.frozen

    def test_nika_fields(self):
        assert NIKA.name == "Nika"
        assert NIKA.breed == "Exotic Shorthair"
        assert "[CAT]" not in NIKA.description
        assert len(NIKA.hashtags) >= 3
        assert len(NIKA.voice_rules) >= 1


class TestInjectPersona:
    def test_replaces_single_placeholder(self):
        assert inject_persona("[CAT] sits.") == f"{NIKA.description} sits."

    def test_replaces_every_placeholder(self):
        result = inject_persona("[CAT] and [CAT]")
        assert "[CAT]" not in result
        assert result.count(NIKA.description) == 2

    def test_no_placeholder_is_noop(self):
        assert inject_persona("a cat sits") == "a cat sits"

    def test_custom_persona(self):
        p = Persona(
            name="X", breed="Tabby", description="X the tabby",
            hashtags=("x",), voice_rules=("dry",),
        )
        assert inject_persona("[CAT]!", p) == "X the tabby!"


class TestCharacterBibleSync:
    def test_description_appears_verbatim_in_bible(self):
        assert NIKA.description in NIKA_MD.read_text()

    def test_every_hashtag_in_bible(self):
        text = NIKA_MD.read_text()
        for tag in NIKA.hashtags:
            assert tag in text
