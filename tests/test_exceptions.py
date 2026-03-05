"""Unit tests for the custom exception hierarchy."""

from __future__ import annotations

import pytest

from video_engine.core.exceptions import (
    PipelineError,
    StoryGenerationError,
    SEOGenerationError,
    ImagePromptError,
    ImageGenerationError,
    AudioGenerationError,
    TranscriptionError,
    SubtitleError,
    VideoAssemblyError,
    UploadError,
)


class TestPipelineError:
    """Tests for the base PipelineError."""

    def test_basic_message(self):
        err = PipelineError("something broke")
        assert "something broke" in str(err)

    def test_stage_tag(self):
        err = PipelineError("bad", stage="TestStage")
        assert "[TestStage]" in str(err)
        assert err.stage == "TestStage"

    def test_no_stage(self):
        err = PipelineError("no stage")
        assert err.stage is None


class TestStageExceptions:
    """Verify each stage exception auto-tags correctly."""

    @pytest.mark.parametrize(
        "exc_class,expected_stage",
        [
            (StoryGenerationError, "StoryGeneration"),
            (SEOGenerationError, "SEOGeneration"),
            (ImagePromptError, "ImagePrompt"),
            (ImageGenerationError, "ImageGeneration"),
            (AudioGenerationError, "AudioGeneration"),
            (TranscriptionError, "Transcription"),
            (SubtitleError, "Subtitle"),
            (VideoAssemblyError, "VideoAssembly"),
            (UploadError, "Upload"),
        ],
    )
    def test_stage_auto_tag(self, exc_class, expected_stage):
        err = exc_class("test message")
        assert err.stage == expected_stage
        assert f"[{expected_stage}]" in str(err)

    @pytest.mark.parametrize(
        "exc_class",
        [
            StoryGenerationError,
            SEOGenerationError,
            ImagePromptError,
            ImageGenerationError,
            AudioGenerationError,
            TranscriptionError,
            SubtitleError,
            VideoAssemblyError,
            UploadError,
        ],
    )
    def test_inherits_pipeline_error(self, exc_class):
        err = exc_class("test")
        assert isinstance(err, PipelineError)
        assert isinstance(err, Exception)
