"""Unit tests for the image prompt generator."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from video_engine.core.exceptions import ImagePromptError
from video_engine.generators.image_prompt import generate_image_prompt


class TestGenerateImagePrompt:
    """Tests for the generate_image_prompt function."""

    def _setup_story(self, work_dir: Path, content: str = "A test story.") -> None:
        work_dir.mkdir(parents=True, exist_ok=True)
        (work_dir / "story.txt").write_text(content, encoding="utf-8")

    @patch("video_engine.generators.image_prompt.requests.post")
    def test_successful_generation(self, mock_post, mock_settings):
        """Should return prompt text and save to file."""
        work_dir = mock_settings.video_output_dir
        self._setup_story(work_dir)

        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "A child gazing at stars from a rooftop."}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        result = generate_image_prompt(work_dir, mock_settings)

        assert "stars" in result
        assert (work_dir / "prompt.txt").exists()

    def test_missing_story_raises(self, mock_settings):
        """Should raise if story.txt doesn't exist."""
        work_dir = mock_settings.video_output_dir
        work_dir.mkdir(parents=True, exist_ok=True)

        with pytest.raises(ImagePromptError, match="not found"):
            generate_image_prompt(work_dir, mock_settings)

    def test_empty_story_raises(self, mock_settings):
        """Should raise if story.txt is empty."""
        work_dir = mock_settings.video_output_dir
        self._setup_story(work_dir, content="  ")

        with pytest.raises(ImagePromptError, match="empty"):
            generate_image_prompt(work_dir, mock_settings)

    @patch("video_engine.generators.image_prompt.requests.post")
    def test_empty_llm_response_raises(self, mock_post, mock_settings):
        """Should raise if LLM returns empty response."""
        work_dir = mock_settings.video_output_dir
        self._setup_story(work_dir)

        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "  "}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        with pytest.raises(ImagePromptError, match="empty"):
            generate_image_prompt(work_dir, mock_settings)
