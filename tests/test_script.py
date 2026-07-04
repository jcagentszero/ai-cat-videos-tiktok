import pytest

from characters.persona import NIKA, Persona
from prompts.script import Script, Shot, parse_script
from tests.conftest import SAMPLE_SCRIPT_MD


class TestParseScript:
    def test_parses_frontmatter(self, script_file):
        s = parse_script(script_file)
        assert s.id == "belly-rub-betrayal"
        assert s.title == "The Belly Rub Betrayal"
        assert s.caption == "The belly was never an offer. It was a test."
        assert s.hook == "She's offering her belly. This is a gift."
        assert s.hashtags == ("bellyrub", "cattrap")
        assert s.duration_seconds == 30
        assert s.path == script_file

    def test_parses_shots(self, script_file):
        s = parse_script(script_file)
        assert len(s.shots) == 2
        first = s.shots[0]
        assert first.index == 1
        assert first.label == "The Invitation"
        assert first.start_s == 0.0
        assert first.end_s == 6.0
        assert first.description.startswith("[CAT] lying on its back")
        assert first.audio == "Soft, dreamy piano. Gentle purring."
        assert "gift" in first.text_overlay

    def test_second_shot_times(self, script_file):
        s = parse_script(script_file)
        assert s.shots[1].start_s == 6.0
        assert s.shots[1].end_s == 12.0

    def test_production_notes_not_a_shot(self, script_file):
        s = parse_script(script_file)
        assert all("Production" not in shot.label for shot in s.shots)

    def test_missing_frontmatter_key_raises_with_filename(self, tmp_path):
        bad = tmp_path / "bad.md"
        bad.write_text(SAMPLE_SCRIPT_MD.replace("caption: The belly was never an offer. It was a test.\n", ""))
        with pytest.raises(ValueError, match=r"bad\.md.*caption"):
            parse_script(bad)

    def test_no_frontmatter_raises(self, tmp_path):
        bad = tmp_path / "plain.md"
        bad.write_text("# just a heading\n\nsome text")
        with pytest.raises(ValueError, match=r"plain\.md"):
            parse_script(bad)

    def test_no_shots_raises(self, tmp_path):
        header_only = SAMPLE_SCRIPT_MD.split("## Shot 1")[0]
        bad = tmp_path / "noshots.md"
        bad.write_text(header_only)
        with pytest.raises(ValueError, match=r"noshots\.md.*[Ss]hot"):
            parse_script(bad)

    def test_script_is_frozen(self, script_file):
        s = parse_script(script_file)
        with pytest.raises(Exception):
            s.title = "changed"


class TestRender:
    def test_render_injects_persona(self, script_file):
        rendered = parse_script(script_file).render()
        assert "[CAT]" not in rendered
        assert NIKA.description in rendered

    def test_render_includes_title_logline_and_body(self, script_file):
        rendered = parse_script(script_file).render()
        assert "The Belly Rub Betrayal" in rendered
        assert "oldest trap in feline history" in rendered
        assert "Shot 2" in rendered

    def test_render_with_custom_persona(self, script_file):
        p = Persona(name="X", breed="T", description="X the test cat",
                    hashtags=("x",), voice_rules=())
        rendered = parse_script(script_file).render(p)
        assert "X the test cat" in rendered
