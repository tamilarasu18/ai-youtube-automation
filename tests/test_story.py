"""Unit tests for the story generator."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from video_engine.core.exceptions import StoryGenerationError
from video_engine.generators.story import generate_story, STORY_STYLES, TONES, CHARACTERS


class TestRandomisationPools:
    """Verify randomisation pool constants."""

    def test_story_styles_count(self):
        assert len(STORY_STYLES) == 8

    def test_tones_count(self):
        assert len(TONES) == 5

    def test_characters_count(self):
        assert len(CHARACTERS) == 8

    def test_total_combinations(self):
        """8 styles × 5 tones × 8 characters = 320 unique prompts."""
        assert len(STORY_STYLES) * len(TONES) * len(CHARACTERS) == 320


class TestGenerateStory:
    """Tests for the generate_story function."""

    @patch("video_engine.generators.story.requests.post")
    def test_successful_generation(self, mock_post, mock_settings):
        """Should return story text and save to file."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "A beautiful story about courage."}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        result = generate_story("Test inspiration", mock_settings)

        assert "courage" in result
        story_file = mock_settings.video_output_dir / "story.txt"
        assert story_file.exists()
        assert story_file.read_text(encoding="utf-8") == result

    @patch("video_engine.generators.story.requests.post")
    def test_empty_response_raises(self, mock_post, mock_settings):
        """Should raise StoryGenerationError for empty LLM response."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "   "}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        with pytest.raises(StoryGenerationError, match="empty response"):
            generate_story("Test", mock_settings)

    @patch("video_engine.generators.story.requests.post")
    def test_network_error_raises(self, mock_post, mock_settings):
        """Should raise StoryGenerationError on network failure."""
        import requests
        mock_post.side_effect = requests.RequestException("Connection refused")

        with pytest.raises(StoryGenerationError, match="Ollama request failed"):
            generate_story("Test", mock_settings)

    @patch("video_engine.generators.story.requests.post")
    def test_strips_markdown_headers(self, mock_post, mock_settings):
        """Should remove ## markers from the response."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "## Title\nContent here"}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        result = generate_story("Test", mock_settings)
        assert "##" not in result
