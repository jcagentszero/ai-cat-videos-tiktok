"""
utils/reference_photos.py
─────────────────────────
Loads Nika's reference photos for character-consistent video generation.
"""

from pathlib import Path

from config import settings

_ALLOWED_SUFFIXES = (".jpg", ".jpeg", ".png")
_MAX_BYTES = 10 * 1024 * 1024  # 10 MB per photo


class ReferencePhotoError(Exception):
    """Raised when the reference photo directory is missing, empty, or invalid."""


def load_reference_photos(directory: Path | None = None) -> tuple[Path, ...]:
    """Return a deterministic, validated tuple of reference photo paths.

    Raises:
        ReferencePhotoError: directory missing, no usable photos, or a photo >10MB.
    """
    directory = Path(directory) if directory is not None else settings.REFERENCE_PHOTOS_DIR

    if not directory.is_dir():
        raise ReferencePhotoError(f"Reference photo directory not found: {directory}")

    photos = tuple(sorted(
        p for p in directory.iterdir()
        if p.is_file() and p.suffix.lower() in _ALLOWED_SUFFIXES
    ))
    if not photos:
        raise ReferencePhotoError(
            f"No reference photos (.jpg/.jpeg/.png) found in {directory}"
        )

    oversized = [p.name for p in photos if p.stat().st_size > _MAX_BYTES]
    if oversized:
        raise ReferencePhotoError(
            f"Reference photos exceed 10MB limit: {', '.join(oversized)}"
        )
    return photos
