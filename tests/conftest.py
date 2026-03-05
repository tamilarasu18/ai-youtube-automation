"""Shared test fixtures and configuration."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture
def tmp_work_dir(tmp_path: Path) -> Path:
    """Create a temporary working directory with required structure."""
    video_dir = tmp_path / "video"
    video_dir.mkdir()
    return tmp_path


@pytest.fixture
def sample_story() -> str:
    """Return a sample story for testing."""
    return (
        "The Weight of Words\n\n"
        "In a small village, a young teacher named Priya discovered that her words "
        "could change lives. One morning, a struggling student named Arjun came to her, "
        "ready to give up on his dreams.\n\n"
        '"I can\'t do this," Arjun whispered.\n\n'
        'Priya smiled. "You already have. You came here today."\n\n'
        "That single sentence ignited a fire in Arjun's heart. Years later, he became "
        "a renowned scientist, always crediting Priya's belief in him.\n\n"
        "Subscribe to my YouTube channel, like, share, and comment."
    )


@pytest.fixture
def sample_seo_data() -> dict:
    """Return sample SEO metadata for testing."""
    return {
        "title": "✨ The Power of Belief — A Teacher's Gift",
        "description": (
            "A touching story about how a teacher's words changed a student's life forever. 🌟"
        ),
        "hashtags": [
            "#Motivation",
            "#Inspiration",
            "#Teacher",
            "#NeverGiveUp",
            "#Believe",
        ],
    }


@pytest.fixture
def sample_subtitles() -> list[dict]:
    """Return sample subtitle data for testing."""
    return [
        {"start": 0.0, "end": 3.5, "text": "In a small village"},
        {"start": 3.5, "end": 7.2, "text": "a young teacher named Priya"},
        {"start": 7.2, "end": 11.0, "text": "discovered that her words could change lives"},
    ]


@pytest.fixture
def mock_settings(tmp_path: Path):
    """Create mock settings with temporary paths."""
    env_vars = {
        "OLLAMA_URL": "http://localhost:11434/api/generate",
        "OLLAMA_MODEL": "gemma3:4b",
        "SD_MODEL_ID": "stabilityai/stable-diffusion-xl-base-1.0",
        "SD_NUM_STEPS": "20",
        "SD_GUIDANCE_SCALE": "7.5",
        "OUTPUT_DIR": str(tmp_path / "output"),
        "ASSETS_DIR": str(tmp_path / "assets"),
        "BACKGROUND_MUSIC": str(tmp_path / "assets" / "audio" / "background_music.mp3"),
        "FONT_PATH": str(tmp_path / "assets" / "fonts" / "Anton-Regular.ttf"),
        "YOUTUBE_CLIENT_SECRETS": str(tmp_path / "config" / "client.json"),
        "YOUTUBE_TOKEN_FILE": str(tmp_path / "config" / "token.json"),
        "LOG_FILE": str(tmp_path / "logs" / "test.log"),
        "WHISPER_CACHE_DIR": str(tmp_path / "whisper_cache"),
    }
    with patch.dict(os.environ, env_vars, clear=False):
        from video_engine.core.config import Settings

        yield Settings()
