"""
Audio generation using Kokoro TTS pipeline.

Converts story text into speech audio, splitting long text into chunks for
reliable synthesis. Output is saved as a WAV file.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf
from kokoro import KPipeline

from video_engine.core.config import Settings
from video_engine.core.exceptions import AudioGenerationError
from video_engine.core.logger import logger


def _split_text(text: str, max_words: int = 100) -> list[str]:
    """Split text into chunks of approximately *max_words* words."""
    words = text.split()
    return [" ".join(words[i : i + max_words]) for i in range(0, len(words), max_words)]


def generate_audio(work_dir: Path, settings: Settings) -> Path:
    """
    Generate TTS audio from the story text using Kokoro.

    Args:
        work_dir: Working directory containing ``story.txt``.
        settings: Application settings (voice, sample rate, chunk size).

    Returns:
        Path to the generated WAV file.

    Raises:
        AudioGenerationError: If story is missing, TTS fails, or no audio is produced.
    """
    story_path = work_dir / "story.txt"
    if not story_path.exists():
        raise AudioGenerationError("story.txt not found — run story generation first")

    full_text = story_path.read_text(encoding="utf-8").strip()
    if not full_text:
        raise AudioGenerationError("story.txt is empty")

    logger.info(
        "Initialising Kokoro pipeline (lang={}, voice={})",
        settings.KOKORO_LANG_CODE,
        settings.KOKORO_VOICE,
    )

    try:
        pipeline = KPipeline(lang_code=settings.KOKORO_LANG_CODE)
    except Exception as exc:
        raise AudioGenerationError(f"Failed to initialise Kokoro pipeline: {exc}") from exc

    chunks = _split_text(full_text, max_words=settings.KOKORO_CHUNK_SIZE)
    all_segments: list[np.ndarray] = []

    for chunk_idx, chunk in enumerate(chunks, 1):
        logger.debug(
            "Processing chunk {}/{} ({} words)",
            chunk_idx,
            len(chunks),
            len(chunk.split()),
        )

        try:
            generator = pipeline(chunk, voice=settings.KOKORO_VOICE)
            for seg_idx, (gs, ps, audio) in enumerate(generator):
                all_segments.append(audio)
        except Exception as exc:
            raise AudioGenerationError(f"TTS failed on chunk {chunk_idx}: {exc}") from exc

    if not all_segments:
        raise AudioGenerationError("No audio segments were generated")

    # Concatenate and save
    final_audio = np.concatenate(all_segments, axis=0)
    output_path = work_dir / "generated_final_audio_file.wav"
    sf.write(str(output_path), final_audio, settings.KOKORO_SAMPLE_RATE)

    duration_s = len(final_audio) / settings.KOKORO_SAMPLE_RATE
    logger.info("Audio saved → {} ({:.1f}s)", output_path, duration_s)
    return output_path
