"""Unit tests for the SEO metadata generator."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from video_engine.core.exceptions import SEOGenerationError
from video_engine.generators.seo import generate_seo


class TestGenerateSEO:
    """Tests for the generate_seo function."""

    def _setup_story(self, work_dir: Path, content: str = "A test story.") -> None:
        work_dir.mkdir(parents=True, exist_ok=True)
        (work_dir / "story.txt").write_text(content, encoding="utf-8")

    @patch("video_engine.generators.seo.requests.post")
    def test_successful_generation(self, mock_post, mock_settings):
        """Should parse JSON and save seo_content.json."""
        work_dir = mock_settings.video_output_dir
        self._setup_story(work_dir)

        seo_json = json.dumps({
            "title": "Test Title ✨",
            "description": "Test description",
            "hashtags": ["#test", "#ai"],
        })
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": seo_json}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        result = generate_seo(work_dir, mock_settings)

        assert result["title"] == "Test Title ✨"
        assert len(result["hashtags"]) == 2
        assert (work_dir / "seo_content.json").exists()

    @patch("video_engine.generators.seo.requests.post")
    def test_strips_code_fences(self, mock_post, mock_settings):
        """Should handle responses wrapped in ```json``` fences."""
        work_dir = mock_settings.video_output_dir
        self._setup_story(work_dir)

        raw = '```json\n{"title": "T", "description": "D", "hashtags": ["#h"]}\n```'
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": raw}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        result = generate_seo(work_dir, mock_settings)
        assert result["title"] == "T"

    def test_missing_story_raises(self, mock_settings):
        """Should raise if story.txt doesn't exist."""
        work_dir = mock_settings.video_output_dir
        work_dir.mkdir(parents=True, exist_ok=True)

        with pytest.raises(SEOGenerationError, match="not found"):
            generate_seo(work_dir, mock_settings)

    def test_empty_story_raises(self, mock_settings):
        """Should raise if story.txt is empty."""
        work_dir = mock_settings.video_output_dir
        self._setup_story(work_dir, content="   ")

        with pytest.raises(SEOGenerationError, match="empty"):
            generate_seo(work_dir, mock_settings)

    @patch("video_engine.generators.seo.requests.post")
    def test_invalid_json_raises(self, mock_post, mock_settings):
        """Should raise if LLM returns invalid JSON."""
        work_dir = mock_settings.video_output_dir
        self._setup_story(work_dir)

        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "not valid json at all"}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        with pytest.raises(SEOGenerationError, match="parse"):
            generate_seo(work_dir, mock_settings)

    @patch("video_engine.generators.seo.requests.post")
    def test_missing_key_raises(self, mock_post, mock_settings):
        """Should raise if JSON is missing required keys."""
        work_dir = mock_settings.video_output_dir
        self._setup_story(work_dir)

        incomplete = json.dumps({"title": "T"})  # missing description & hashtags
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": incomplete}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        with pytest.raises(SEOGenerationError, match="Missing required key"):
            generate_seo(work_dir, mock_settings)
