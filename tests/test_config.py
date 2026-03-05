"""Unit tests for the core configuration module."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest


class TestSettings:
    """Tests for the Settings class."""

    def test_default_values(self, mock_settings):
        """Settings should have sensible defaults."""
        assert mock_settings.OLLAMA_MODEL == "gemma3:4b"
        assert mock_settings.VIDEO_FPS == 30
        assert mock_settings.VIDEO_BITRATE == "20000k"
        assert mock_settings.SHORTS_WIDTH == 1080
        assert mock_settings.SHORTS_HEIGHT == 1920
        assert mock_settings.MAX_SHORTS_DURATION == 60
        assert mock_settings.KOKORO_VOICE == "af_heart"
        assert mock_settings.WHISPER_MODEL == "medium.en"

    def test_env_override(self):
        """Settings should pick up environment variable overrides."""
        with patch.dict(os.environ, {"OLLAMA_MODEL": "llama3:8b", "VIDEO_FPS": "60"}):
            from video_engine.core.config import Settings
            s = Settings()
            assert s.OLLAMA_MODEL == "llama3:8b"
            assert s.VIDEO_FPS == 60

    def test_video_output_dir(self, mock_settings):
        """video_output_dir should be a Path under OUTPUT_DIR."""
        result = mock_settings.video_output_dir
        assert isinstance(result, Path)
        assert "video" in str(result)

    def test_shorts_output_dir(self, mock_settings):
        """shorts_output_dir should be nested under video output."""
        result = mock_settings.shorts_output_dir
        assert isinstance(result, Path)
        assert "shorts" in str(result)

    def test_ensure_directories(self, mock_settings):
        """ensure_directories should create all required directories."""
        mock_settings.ensure_directories()
        assert mock_settings.video_output_dir.exists()
        assert mock_settings.shorts_output_dir.exists()
        assert mock_settings.yt_video_dir.exists()


class TestGetSettings:
    """Tests for the get_settings singleton."""

    def test_returns_settings_instance(self):
        """get_settings should return a Settings instance."""
        from video_engine.core.config import get_settings
        # Clear the cache to get fresh instance
        get_settings.cache_clear()
        settings = get_settings()
        from video_engine.core.config import Settings
        assert isinstance(settings, Settings)

    def test_singleton_caching(self):
        """get_settings should return the same instance on repeated calls."""
        from video_engine.core.config import get_settings
        get_settings.cache_clear()
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2
