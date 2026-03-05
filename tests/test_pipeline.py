"""Unit tests for the pipeline orchestrator."""

from __future__ import annotations

from unittest.mock import patch

from video_engine.core.pipeline import Pipeline, PipelineResult


class TestPipelineResult:
    """Tests for PipelineResult tracking."""

    def test_initial_state(self):
        result = PipelineResult()
        assert result.success is False
        assert result.error is None
        assert result.steps == []

    def test_record_step(self):
        result = PipelineResult()
        result.record_step("Test Step", 1.5, True, "ok")
        assert len(result.steps) == 1
        assert result.steps[0]["step"] == "Test Step"
        assert result.steps[0]["duration_s"] == 1.5
        assert result.steps[0]["success"] is True

    def test_to_dict(self):
        result = PipelineResult()
        result.success = True
        result.record_step("A", 2.0, True)
        result.record_step("B", 3.5, True)

        d = result.to_dict()
        assert d["success"] is True
        assert d["total_duration_s"] == 5.5
        assert len(d["steps"]) == 2

    def test_to_dict_with_error(self):
        result = PipelineResult()
        result.error = "something failed"
        d = result.to_dict()
        assert d["success"] is False
        assert d["error"] == "something failed"


class TestPipeline:
    """Tests for the Pipeline orchestrator."""

    def test_init_with_default_settings(self):
        """Pipeline should initialise with default settings."""
        pipeline = Pipeline()
        assert pipeline.settings is not None
        assert pipeline.result is not None

    def test_init_with_custom_settings(self, mock_settings):
        """Pipeline should accept custom settings."""
        pipeline = Pipeline(settings=mock_settings)
        assert pipeline.settings is mock_settings

    @patch("video_engine.core.pipeline.Pipeline._check_ollama")
    @patch("video_engine.core.pipeline.Pipeline._generate_story")
    @patch("video_engine.core.pipeline.Pipeline._generate_seo")
    @patch("video_engine.core.pipeline.Pipeline._generate_image_prompt")
    @patch("video_engine.core.pipeline.Pipeline._generate_images")
    @patch("video_engine.core.pipeline.Pipeline._generate_audio")
    @patch("video_engine.core.pipeline.Pipeline._transcribe")
    @patch("video_engine.core.pipeline.Pipeline._convert_subtitles")
    @patch("video_engine.core.pipeline.Pipeline._assemble_videos")
    @patch("video_engine.core.pipeline.Pipeline._upload")
    @patch("video_engine.core.pipeline.Pipeline._cleanup")
    def test_successful_run(
        self,
        mock_cleanup,
        mock_upload,
        mock_assemble,
        mock_subtitles,
        mock_transcribe,
        mock_audio,
        mock_images,
        mock_img_prompt,
        mock_seo,
        mock_story,
        mock_ollama,
        mock_settings,
    ):
        """A fully mocked pipeline run should succeed."""
        mock_story.return_value = "Test story"

        pipeline = Pipeline(settings=mock_settings)
        result = pipeline.run(prompt="Test prompt", scheduled_time=None)

        assert result["success"] is True
        assert result["error"] is None
        assert len(result["steps"]) == 9
        mock_story.assert_called_once()
        mock_cleanup.assert_called_once()

    @patch("video_engine.core.pipeline.Pipeline._check_ollama")
    @patch("video_engine.core.pipeline.Pipeline._generate_story")
    @patch("video_engine.core.pipeline.Pipeline._cleanup")
    def test_run_failure_at_first_step(
        self,
        mock_cleanup,
        mock_story,
        mock_ollama,
        mock_settings,
    ):
        """Pipeline should handle failure at the first step gracefully."""
        from video_engine.core.exceptions import StoryGenerationError

        mock_story.side_effect = StoryGenerationError("LLM down")

        pipeline = Pipeline(settings=mock_settings)
        result = pipeline.run(prompt="Test", scheduled_time=None)

        assert result["success"] is False
        assert "StoryGeneration" in result["error"]
        mock_cleanup.assert_called_once()
