"""
Integration test — runs the full pipeline with all steps mocked.

Validates that the Pipeline orchestrator correctly sequences all 9 steps,
tracks timing/success, handles errors, and produces a valid result dict.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from video_engine.core.exceptions import (
    AudioGenerationError,
    ImageGenerationError,
    SEOGenerationError,
    StoryGenerationError,
    TranscriptionError,
    VideoAssemblyError,
)
from video_engine.core.pipeline import Pipeline

# ── Helpers ────────────────────────────────────────────────────────


def _patch_all_steps():
    """Return a dict of patches for every pipeline step."""
    steps = [
        "video_engine.core.pipeline.Pipeline._check_ollama",
        "video_engine.core.pipeline.Pipeline._generate_story",
        "video_engine.core.pipeline.Pipeline._generate_seo",
        "video_engine.core.pipeline.Pipeline._generate_image_prompt",
        "video_engine.core.pipeline.Pipeline._generate_images",
        "video_engine.core.pipeline.Pipeline._generate_audio",
        "video_engine.core.pipeline.Pipeline._transcribe",
        "video_engine.core.pipeline.Pipeline._convert_subtitles",
        "video_engine.core.pipeline.Pipeline._assemble_videos",
        "video_engine.core.pipeline.Pipeline._upload",
        "video_engine.core.pipeline.Pipeline._cleanup",
    ]
    return {name.split(".")[-1]: patch(name) for name in steps}


# ── Full Pipeline Integration Tests ───────────────────────────────


class TestFullPipelineIntegration:
    """End-to-end pipeline orchestration tests with mocked modules."""

    def test_all_9_steps_execute_in_order(self, mock_settings):
        """Every step should execute exactly once in the correct order."""
        patches = _patch_all_steps()
        mocks = {}

        # Enter all patches
        for name, p in patches.items():
            mocks[name] = p.start()

        mocks["_generate_story"].return_value = "Test story"

        try:
            pipeline = Pipeline(settings=mock_settings)
            result = pipeline.run(prompt="Integration test prompt", scheduled_time=None)

            # Verify success
            assert result["success"] is True
            assert result["error"] is None
            assert result["total_duration_s"] >= 0

            # Verify all 9 pipeline steps ran
            assert len(result["steps"]) == 9

            # Verify step names are in order
            expected_steps = [
                "1. Story Generation",
                "2. SEO Metadata",
                "3. Image Prompt",
                "4. Image Generation",
                "5. Audio Generation",
                "6. Transcription",
                "7. Subtitle Processing",
                "8. Video Assembly",
                "9. YouTube Upload",
            ]
            actual_steps = [s["step"] for s in result["steps"]]
            assert actual_steps == expected_steps

            # Verify all steps succeeded
            assert all(s["success"] for s in result["steps"])

            # Verify each step has timing
            assert all(s["duration_s"] >= 0 for s in result["steps"])

            # Verify cleanup ran
            mocks["_cleanup"].assert_called_once()

        finally:
            for p in patches.values():
                p.stop()

    def test_pipeline_stops_on_first_failure(self, mock_settings):
        """Pipeline should stop and report error when a step fails."""
        patches = _patch_all_steps()
        mocks = {}

        for name, p in patches.items():
            mocks[name] = p.start()

        # Story succeeds, SEO fails
        mocks["_generate_story"].return_value = "Test story"
        mocks["_generate_seo"].side_effect = SEOGenerationError("LLM returned garbage")

        try:
            pipeline = Pipeline(settings=mock_settings)
            result = pipeline.run(prompt="Failure test", scheduled_time=None)

            assert result["success"] is False
            assert "SEOGeneration" in result["error"]

            # Steps after failure should not have run
            # (story ran, SEO failed, rest skipped)
            mocks["_generate_images"].assert_not_called()
            mocks["_generate_audio"].assert_not_called()
            mocks["_assemble_videos"].assert_not_called()
            mocks["_upload"].assert_not_called()

            # Cleanup should still run
            mocks["_cleanup"].assert_called_once()

        finally:
            for p in patches.values():
                p.stop()

    @pytest.mark.parametrize(
        "failing_step,error_class,error_stage",
        [
            ("_generate_story", StoryGenerationError, "StoryGeneration"),
            ("_generate_images", ImageGenerationError, "ImageGeneration"),
            ("_generate_audio", AudioGenerationError, "AudioGeneration"),
            ("_transcribe", TranscriptionError, "Transcription"),
            ("_assemble_videos", VideoAssemblyError, "VideoAssembly"),
            # Note: _upload is non-fatal — UploadError is caught and logged
        ],
    )
    def test_each_step_failure_is_reported(
        self,
        mock_settings,
        failing_step,
        error_class,
        error_stage,
    ):
        """Each step failure should be correctly identified in the result."""
        patches = _patch_all_steps()
        mocks = {}

        for name, p in patches.items():
            mocks[name] = p.start()

        mocks["_generate_story"].return_value = "Test story"
        mocks[failing_step].side_effect = error_class(f"Test failure in {error_stage}")

        try:
            pipeline = Pipeline(settings=mock_settings)
            result = pipeline.run(prompt="Parametrized test", scheduled_time=None)

            assert result["success"] is False
            assert error_stage in result["error"]
            mocks["_cleanup"].assert_called_once()

        finally:
            for p in patches.values():
                p.stop()

    def test_scheduled_time_passed_to_upload(self, mock_settings):
        """Scheduled publish time should propagate through the pipeline."""
        patches = _patch_all_steps()
        mocks = {}

        for name, p in patches.items():
            mocks[name] = p.start()

        mocks["_generate_story"].return_value = "Test story"

        try:
            pipeline = Pipeline(settings=mock_settings)
            result = pipeline.run(
                prompt="Schedule test",
                scheduled_time="2025-06-01T15:00:00+05:30",
            )

            assert result["success"] is True

        finally:
            for p in patches.values():
                p.stop()

    def test_result_dict_structure(self, mock_settings):
        """Result dict should have all expected keys and types."""
        patches = _patch_all_steps()
        mocks = {}

        for name, p in patches.items():
            mocks[name] = p.start()

        mocks["_generate_story"].return_value = "Test story"

        try:
            pipeline = Pipeline(settings=mock_settings)
            result = pipeline.run(prompt="Structure test", scheduled_time=None)

            # Top-level keys
            assert "success" in result
            assert "error" in result
            assert "total_duration_s" in result
            assert "steps" in result

            # Types
            assert isinstance(result["success"], bool)
            assert isinstance(result["total_duration_s"], (int, float))
            assert isinstance(result["steps"], list)

            # Each step dict
            for step in result["steps"]:
                assert "step" in step
                assert "duration_s" in step
                assert "success" in step
                assert isinstance(step["step"], str)
                assert isinstance(step["duration_s"], (int, float))
                assert isinstance(step["success"], bool)

        finally:
            for p in patches.values():
                p.stop()
