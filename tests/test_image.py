"""Unit tests for the image generator (local Stable Diffusion)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from video_engine.core.exceptions import ImageGenerationError
from video_engine.generators.image import generate_images, unload_model


class TestGenerateImages:
    """Tests for the generate_images function."""

    def test_missing_prompt_raises(self, mock_settings):
        """Should raise if prompt.txt doesn't exist."""
        work_dir = mock_settings.video_output_dir
        work_dir.mkdir(parents=True, exist_ok=True)

        with pytest.raises(ImageGenerationError, match="prompt.txt not found"):
            generate_images(work_dir, mock_settings)

    def test_empty_prompt_raises(self, mock_settings):
        """Should raise if prompt.txt is empty."""
        work_dir = mock_settings.video_output_dir
        work_dir.mkdir(parents=True, exist_ok=True)
        (work_dir / "prompt.txt").write_text("   ", encoding="utf-8")

        with pytest.raises(ImageGenerationError, match="empty"):
            generate_images(work_dir, mock_settings)

    @patch("video_engine.generators.image._get_pipeline")
    @patch("video_engine.generators.image.torch")
    def test_successful_generation(self, mock_torch, mock_get_pipe, mock_settings):
        """Should generate and save images when pipeline works."""
        work_dir = mock_settings.video_output_dir
        work_dir.mkdir(parents=True, exist_ok=True)
        (work_dir / "prompt.txt").write_text("A serene mountain scene", encoding="utf-8")

        # Mock the pipeline
        mock_torch.cuda.is_available.return_value = False
        mock_image = MagicMock()
        mock_pipe = MagicMock()
        mock_pipe.return_value.images = [mock_image]
        mock_get_pipe.return_value = mock_pipe

        result = generate_images(work_dir, mock_settings)

        assert result is True
        assert mock_pipe.call_count == 2  # landscape + portrait

    @patch("video_engine.generators.image._get_pipeline")
    @patch("video_engine.generators.image.torch")
    def test_generation_failure_raises(self, mock_torch, mock_get_pipe, mock_settings):
        """Should raise when all image generations fail."""
        work_dir = mock_settings.video_output_dir
        work_dir.mkdir(parents=True, exist_ok=True)
        (work_dir / "prompt.txt").write_text("A test prompt", encoding="utf-8")

        mock_torch.cuda.is_available.return_value = False
        mock_pipe = MagicMock()
        mock_pipe.side_effect = RuntimeError("Out of VRAM")
        mock_get_pipe.return_value = mock_pipe

        with pytest.raises(ImageGenerationError, match="All image generation attempts failed"):
            generate_images(work_dir, mock_settings)


class TestUnloadModel:
    """Tests for model unloading."""

    @patch("video_engine.generators.image._pipeline_cache", new=None)
    @patch("video_engine.generators.image.torch")
    def test_unload_when_no_model(self, mock_torch):
        """Should handle unload gracefully when no model is loaded."""
        unload_model()  # Should not raise
