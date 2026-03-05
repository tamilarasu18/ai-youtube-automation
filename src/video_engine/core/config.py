"""
Centralized configuration management using Pydantic BaseSettings.

All settings are loaded from environment variables or a `.env` file.
No hardcoded secrets — every sensitive value must be set externally.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application-wide settings loaded from environment / .env file."""

    # ── LLM (Ollama) ────────────────────────────────────────────
    OLLAMA_URL: str = "http://localhost:11434/api/generate"
    OLLAMA_MODEL: str = "gemma3:4b"

    # ── Image Generation (HuggingFace) ──────────────────────────
    HUGGINGFACE_TOKEN: str = Field(default="", description="HuggingFace API token")
    HUGGINGFACE_API_URL: str = (
        "https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-dev"
    )

    # ── Audio / TTS (Kokoro) ────────────────────────────────────
    KOKORO_LANG_CODE: str = "a"
    KOKORO_VOICE: str = "af_heart"
    KOKORO_SAMPLE_RATE: int = 24000
    KOKORO_CHUNK_SIZE: int = 100  # words per chunk

    # ── Transcription (Whisper) ─────────────────────────────────
    WHISPER_MODEL: str = "medium.en"
    WHISPER_CACHE_DIR: str = "./whisper_cache"

    # ── Video Settings ──────────────────────────────────────────
    VIDEO_FPS: int = 30
    VIDEO_BITRATE: str = "20000k"
    VIDEO_PRESET: str = "slow"
    VIDEO_CODEC: str = "libx264"
    AUDIO_CODEC: str = "aac"
    VIDEO_THREADS: int = 4

    # ── Landscape Video ─────────────────────────────────────────
    LANDSCAPE_WIDTH: int = 1280
    LANDSCAPE_HEIGHT: int = 720

    # ── Shorts Video ────────────────────────────────────────────
    SHORTS_WIDTH: int = 1080
    SHORTS_HEIGHT: int = 1920
    MAX_SHORTS_DURATION: int = 60
    MIN_SEGMENT_DURATION: int = 6

    # ── Subtitles / Font ────────────────────────────────────────
    FONT_PATH: str = "assets/fonts/Anton-Regular.ttf"
    FONT_SIZE: int = 60
    SHORTS_FONT_SIZE: int = 80
    MAX_LINE_LENGTH: int = 45
    BACKGROUND_MUSIC_VOLUME: float = 0.01

    # ── YouTube Upload ──────────────────────────────────────────
    YOUTUBE_CLIENT_SECRETS: str = "config/client.json"
    YOUTUBE_TOKEN_FILE: str = "config/token.json"
    YOUTUBE_CATEGORY_ID: str = "22"
    YOUTUBE_PRIVACY_STATUS: str = "private"
    YOUTUBE_REDIRECT_PORT: int = 8081

    # ── Paths ───────────────────────────────────────────────────
    OUTPUT_DIR: str = "output"
    ASSETS_DIR: str = "assets"
    BACKGROUND_MUSIC: str = "assets/audio/background_music.mp3"

    # ── Logging ─────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/video_engine.log"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

    # ── Derived Paths ───────────────────────────────────────────

    @property
    def video_output_dir(self) -> Path:
        """Temporary working directory for a single generation run."""
        return Path(self.OUTPUT_DIR) / "video"

    @property
    def shorts_output_dir(self) -> Path:
        """Output directory for YouTube Shorts segments."""
        return Path(self.OUTPUT_DIR) / "video" / "yt_video" / "shorts"

    @property
    def yt_video_dir(self) -> Path:
        """Output directory for the full-length YouTube video."""
        return Path(self.OUTPUT_DIR) / "video" / "yt_video"

    def ensure_directories(self) -> None:
        """Create all required output directories."""
        for directory in [
            self.video_output_dir,
            self.shorts_output_dir,
            self.yt_video_dir,
            Path(self.OUTPUT_DIR) / "images",
            Path("logs"),
            Path("config"),
        ]:
            directory.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached application settings singleton."""
    return Settings()
