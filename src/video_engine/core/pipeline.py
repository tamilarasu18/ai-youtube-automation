"""
Pipeline orchestrator — sequences all generation steps.

Manages the full lifecycle: setup → generate → process → upload → cleanup.
Each step is tracked with timing and result status.
"""

from __future__ import annotations

import shutil
import time
from pathlib import Path
from typing import Any

from video_engine.core.config import Settings, get_settings
from video_engine.core.logger import logger
from video_engine.core.exceptions import PipelineError


class PipelineResult:
    """Tracks the outcome of a pipeline run."""

    def __init__(self) -> None:
        self.steps: list[dict[str, Any]] = []
        self.success: bool = False
        self.error: str | None = None

    def record_step(self, name: str, duration: float, success: bool, detail: str = "") -> None:
        self.steps.append({
            "step": name,
            "duration_s": round(duration, 2),
            "success": success,
            "detail": detail,
        })

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "error": self.error,
            "steps": self.steps,
            "total_duration_s": round(sum(s["duration_s"] for s in self.steps), 2),
        }


class Pipeline:
    """
    Central orchestrator for the AI video generation pipeline.

    Usage::

        pipeline = Pipeline()
        result = pipeline.run(prompt="Your motivational quote", scheduled_time="...")
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.result = PipelineResult()

    # ── Public API ──────────────────────────────────────────────

    def run(self, prompt: str, scheduled_time: str | None = None) -> dict[str, Any]:
        """
        Execute the full 9-step pipeline.

        Args:
            prompt: The motivational text / quote to generate content from.
            scheduled_time: Optional ISO-8601 datetime for scheduled YouTube publish.

        Returns:
            A dict with ``success``, ``error``, ``steps``, and ``total_duration_s``.
        """
        logger.info("━━━ Pipeline started ━━━")
        logger.info("Prompt: {}", prompt[:80])

        self.settings.ensure_directories()
        work_dir = self.settings.video_output_dir

        try:
            # Step 1 — Story Generation
            story = self._run_step("1. Story Generation", self._generate_story, prompt)

            # Step 2 — SEO Metadata
            self._run_step("2. SEO Metadata", self._generate_seo, work_dir)

            # Step 3 — Image Prompt
            self._run_step("3. Image Prompt", self._generate_image_prompt, work_dir)

            # Step 4 — Image Generation
            self._run_step("4. Image Generation", self._generate_images, work_dir)

            # Step 5 — Audio Generation (TTS)
            self._run_step("5. Audio Generation", self._generate_audio, work_dir)

            # Step 6 — Transcription
            audio_path = work_dir / "generated_final_audio_file.wav"
            srt_path = work_dir / "generated_final_audio_file.srt"
            self._run_step("6. Transcription", self._transcribe, audio_path, srt_path)

            # Step 7 — SRT → JSON
            json_path = work_dir / "subtitles.json"
            self._run_step("7. Subtitle Conversion", self._convert_subtitles, srt_path, json_path)

            # Step 8 — Video Assembly (Landscape + Shorts)
            self._run_step("8. Video Assembly", self._assemble_videos, work_dir)

            # Step 9 — YouTube Upload
            self._run_step("9. YouTube Upload", self._upload, scheduled_time)

            self.result.success = True
            logger.success("━━━ Pipeline completed successfully ━━━")

        except PipelineError as exc:
            self.result.error = str(exc)
            logger.error("Pipeline failed at stage {}: {}", exc.stage, exc)

        except Exception as exc:
            self.result.error = f"Unexpected error: {exc}"
            logger.exception("Pipeline failed with unexpected error")

        finally:
            self._cleanup(work_dir)

        return self.result.to_dict()

    # ── Step Runner ─────────────────────────────────────────────

    def _run_step(self, name: str, func: Any, *args: Any, **kwargs: Any) -> Any:
        """Execute a single pipeline step with timing and logging."""
        logger.info("▶ Starting: {}", name)
        start = time.time()
        try:
            result = func(*args, **kwargs)
            duration = time.time() - start
            self.result.record_step(name, duration, success=True)
            logger.success("✓ Completed: {} ({:.1f}s)", name, duration)
            return result
        except Exception as exc:
            duration = time.time() - start
            self.result.record_step(name, duration, success=False, detail=str(exc))
            logger.error("✗ Failed: {} ({:.1f}s) — {}", name, duration, exc)
            raise

    # ── Step Implementations (delegate to layer modules) ────────

    def _generate_story(self, prompt: str) -> str:
        from video_engine.generators.story import generate_story
        return generate_story(prompt, self.settings)

    def _generate_seo(self, work_dir: Path) -> None:
        from video_engine.generators.seo import generate_seo
        generate_seo(work_dir, self.settings)

    def _generate_image_prompt(self, work_dir: Path) -> None:
        from video_engine.generators.image_prompt import generate_image_prompt
        generate_image_prompt(work_dir, self.settings)

    def _generate_images(self, work_dir: Path) -> None:
        from video_engine.generators.image import generate_images
        generate_images(work_dir, self.settings)

    def _generate_audio(self, work_dir: Path) -> None:
        from video_engine.generators.audio import generate_audio
        generate_audio(work_dir, self.settings)

    def _transcribe(self, audio_path: Path, srt_path: Path) -> None:
        from video_engine.processors.transcription import transcribe
        transcribe(audio_path, srt_path, self.settings)

    def _convert_subtitles(self, srt_path: Path, json_path: Path) -> None:
        from video_engine.processors.subtitle import srt_to_json
        srt_to_json(srt_path, json_path)

    def _assemble_videos(self, work_dir: Path) -> None:
        from video_engine.processors.video import assemble_landscape_video
        from video_engine.processors.shorts import assemble_shorts

        assemble_landscape_video(work_dir, self.settings)
        assemble_shorts(work_dir, self.settings)

    def _upload(self, scheduled_time: str | None) -> None:
        from video_engine.uploaders.youtube import upload_all
        upload_all(self.settings, scheduled_time)

    # ── Cleanup ─────────────────────────────────────────────────

    def _cleanup(self, work_dir: Path) -> None:
        """Remove temporary working directory after pipeline completion."""
        try:
            if work_dir.exists():
                shutil.rmtree(work_dir)
                logger.info("Cleaned up working directory: {}", work_dir)
        except OSError as exc:
            logger.warning("Cleanup failed: {}", exc)
