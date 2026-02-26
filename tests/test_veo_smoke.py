import os

import pytest
from pathlib import Path
from unittest.mock import patch

from generators.veo import VeoGenerator
from prompts.prompt_manager import PromptManager


_SKIP_REASON = (
    "Smoke tests require GCP credentials "
    "(set GOOGLE_APPLICATION_CREDENTIALS and GOOGLE_CLOUD_PROJECT_ID)"
)


def _has_gcp_credentials():
    creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID", "")
    return bool(creds_path) and Path(creds_path).is_file() and bool(project_id)


pytestmark = [
    pytest.mark.smoke,
    pytest.mark.skipif(not _has_gcp_credentials(), reason=_SKIP_REASON),
]


def _is_valid_mp4(path: Path) -> bool:
    """Check MP4 file type box signature (bytes 4-8 == 'ftyp')."""
    with open(path, "rb") as f:
        header = f.read(8)
    return len(header) >= 8 and header[4:8] == b"ftyp"


class TestVeoSmoke:
    def test_generate_produces_valid_mp4(self, tmp_path):
        with patch("config.settings.OUTPUT_DIR", tmp_path):
            gen = VeoGenerator()
            pm = PromptManager()
            prompt, _ = pm.consume_prompt()
            result = gen.generate(prompt)

        assert result.exists(), f"Generated file does not exist: {result}"
        assert result.stat().st_size > 0, "Generated file is empty"
        assert result.suffix == ".mp4"
        assert _is_valid_mp4(result), (
            f"File does not have valid MP4 signature: {result}"
        )
