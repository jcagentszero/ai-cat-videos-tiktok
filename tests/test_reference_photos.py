import pytest

from utils.reference_photos import ReferencePhotoError, load_reference_photos


def _make_photo(directory, name, size=1024):
    p = directory / name
    p.write_bytes(b"\x89" * size)
    return p


class TestLoadReferencePhotos:
    def test_returns_sorted_tuple(self, tmp_path):
        _make_photo(tmp_path, "b.jpg")
        _make_photo(tmp_path, "a.png")
        photos = load_reference_photos(tmp_path)
        assert isinstance(photos, tuple)
        assert [p.name for p in photos] == ["a.png", "b.jpg"]

    def test_filters_non_image_files(self, tmp_path):
        _make_photo(tmp_path, "cat.jpeg")
        (tmp_path / "notes.txt").write_text("not a photo")
        (tmp_path / "README.md").write_text("readme")
        photos = load_reference_photos(tmp_path)
        assert [p.name for p in photos] == ["cat.jpeg"]

    def test_uppercase_extensions_accepted(self, tmp_path):
        _make_photo(tmp_path, "CAT.JPG")
        assert len(load_reference_photos(tmp_path)) == 1

    def test_missing_directory_raises(self, tmp_path):
        with pytest.raises(ReferencePhotoError, match="not found"):
            load_reference_photos(tmp_path / "nope")

    def test_empty_directory_raises(self, tmp_path):
        with pytest.raises(ReferencePhotoError, match="No reference photos"):
            load_reference_photos(tmp_path)

    def test_oversized_photo_raises(self, tmp_path):
        _make_photo(tmp_path, "huge.jpg", size=10 * 1024 * 1024 + 1)
        with pytest.raises(ReferencePhotoError, match="huge.jpg"):
            load_reference_photos(tmp_path)

    def test_defaults_to_settings_dir(self, tmp_path, monkeypatch):
        from config import settings
        monkeypatch.setattr(settings, "REFERENCE_PHOTOS_DIR", tmp_path)
        _make_photo(tmp_path, "nika.jpg")
        assert len(load_reference_photos()) == 1
