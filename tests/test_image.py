"""Unit tests for the image generator."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from video_engine.core.exceptions import ImageGenerationError
from video_engine.generators.image import generate_images, _query_api


class TestQueryApi:
    """Tests for the internal _query_api function."""

    @patch("video_engine.generators.image.requests.post")
    def test_success_on_first_attempt(self, mock_post):
        """Should return bytes on a 200 response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"fake_image_bytes"
        mock_post.return_value = mock_response

        result = _query_api("test prompt", 1280, 720, {"Authorization": "Bearer x"}, "http://api", max_retries=0)
        assert result == b"fake_image_bytes"

    @patch("video_engine.generators.image.requests.post")
    @patch("video_engine.generators.image.time.sleep")
    def test_retries_on_failure(self, mock_sleep, mock_post):
        """Should retry on non-200 responses."""
        fail_response = MagicMock()
        fail_response.status_code = 500
        fail_response.text = "Server Error"

        success_response = MagicMock()
        success_response.status_code = 200
        success_response.content = b"image_data"

        mock_post.side_effect = [fail_response, success_response]

        result = _query_api("test", 1280, 720, {}, "http://api", max_retries=1)
        assert result == b"image_data"
        assert mock_post.call_count == 2

    @patch("video_engine.generators.image.requests.post")
    @patch("video_engine.generators.image.time.sleep")
    def test_returns_none_after_all_retries(self, mock_sleep, mock_post):
        """Should return None if all retries are exhausted."""
        fail_response = MagicMock()
        fail_response.status_code = 503
        fail_response.text = "Service Unavailable"
        mock_post.return_value = fail_response

        result = _query_api("test", 1280, 720, {}, "http://api", max_retries=2)
        assert result is None
        assert mock_post.call_count == 3


class TestGenerateImages:
    """Tests for the generate_images function."""

    def test_missing_token_raises(self, mock_settings):
        """Should raise if HUGGINGFACE_TOKEN is empty."""
        mock_settings.HUGGINGFACE_TOKEN = ""
        work_dir = mock_settings.video_output_dir
        work_dir.mkdir(parents=True, exist_ok=True)

        with pytest.raises(ImageGenerationError, match="HUGGINGFACE_TOKEN"):
            generate_images(work_dir, mock_settings)

    def test_missing_prompt_raises(self, mock_settings):
        """Should raise if prompt.txt doesn't exist."""
        work_dir = mock_settings.video_output_dir
        work_dir.mkdir(parents=True, exist_ok=True)

        with pytest.raises(ImageGenerationError, match="prompt.txt not found"):
            generate_images(work_dir, mock_settings)

    def test_empty_prompt_raises(self, mock_settings):
        """Should raise if prompt.txt is empty."""
        work_dir = mock_settings.video_output_dir
        work_dir.mkdir(parents=True, exist_ok=True)
        (work_dir / "prompt.txt").write_text("   ", encoding="utf-8")

        with pytest.raises(ImageGenerationError, match="empty"):
            generate_images(work_dir, mock_settings)
