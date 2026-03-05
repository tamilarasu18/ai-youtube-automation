"""
Custom exception hierarchy for the AI Shorts pipeline.

Each pipeline stage has a dedicated exception type for precise error
handling and clear diagnostics.
"""

from __future__ import annotations


class PipelineError(Exception):
    """Base exception for all pipeline-related errors."""

    def __init__(self, message: str, stage: str | None = None) -> None:
        self.stage = stage
        super().__init__(f"[{stage}] {message}" if stage else message)


# ── Generator-stage exceptions ─────────────────────────────────────


class StoryGenerationError(PipelineError):
    """Raised when LLM story generation fails."""

    def __init__(self, message: str) -> None:
        super().__init__(message, stage="StoryGeneration")


class SEOGenerationError(PipelineError):
    """Raised when SEO metadata generation fails."""

    def __init__(self, message: str) -> None:
        super().__init__(message, stage="SEOGeneration")


class ImagePromptError(PipelineError):
    """Raised when image prompt summarisation fails."""

    def __init__(self, message: str) -> None:
        super().__init__(message, stage="ImagePrompt")


class ImageGenerationError(PipelineError):
    """Raised when image generation via API fails."""

    def __init__(self, message: str) -> None:
        super().__init__(message, stage="ImageGeneration")


class AudioGenerationError(PipelineError):
    """Raised when TTS audio generation fails."""

    def __init__(self, message: str) -> None:
        super().__init__(message, stage="AudioGeneration")


# ── Processor-stage exceptions ─────────────────────────────────────


class TranscriptionError(PipelineError):
    """Raised when Whisper transcription fails."""

    def __init__(self, message: str) -> None:
        super().__init__(message, stage="Transcription")


class SubtitleError(PipelineError):
    """Raised when SRT/JSON subtitle processing fails."""

    def __init__(self, message: str) -> None:
        super().__init__(message, stage="Subtitle")


class VideoAssemblyError(PipelineError):
    """Raised when video composition or rendering fails."""

    def __init__(self, message: str) -> None:
        super().__init__(message, stage="VideoAssembly")


# ── Uploader-stage exceptions ──────────────────────────────────────


class UploadError(PipelineError):
    """Raised when YouTube upload fails."""

    def __init__(self, message: str) -> None:
        super().__init__(message, stage="Upload")
