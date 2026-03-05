"""
Audio transcription using OpenAI Whisper.

Converts speech audio to text segments and writes an SRT subtitle file.
"""

from __future__ import annotations

from pathlib import Path

import whisper

from video_engine.core.config import Settings
from video_engine.core.exceptions import TranscriptionError
from video_engine.core.logger import logger


def _format_time(seconds: float) -> str:
    """Convert seconds to SRT timestamp format ``HH:MM:SS,MS``."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"


def _segments_to_srt(segments: list[dict], output_path: Path) -> None:
    """Write Whisper segments to an SRT file."""
    with open(output_path, "w", encoding="utf-8") as srt_file:
        for idx, segment in enumerate(segments, 1):
            start = _format_time(segment["start"])
            end = _format_time(segment["end"])
            text = segment["text"].strip()
            srt_file.write(f"{idx}\n{start} --> {end}\n{text}\n\n")


def transcribe(audio_path: Path, srt_path: Path, settings: Settings) -> Path:
    """
    Transcribe audio to SRT subtitles using Whisper.

    Args:
        audio_path: Path to the WAV audio file.
        srt_path: Path where the SRT file will be written.
        settings: Application settings (Whisper model, cache dir).

    Returns:
        Path to the generated SRT file.

    Raises:
        TranscriptionError: If audio file is missing or Whisper fails.
    """
    if not audio_path.exists():
        raise TranscriptionError(f"Audio file not found: {audio_path}")

    logger.info("Loading Whisper model '{}' ...", settings.WHISPER_MODEL)

    try:
        model = whisper.load_model(
            settings.WHISPER_MODEL,
            download_root=settings.WHISPER_CACHE_DIR,
        )
    except Exception as exc:
        raise TranscriptionError(f"Failed to load Whisper model: {exc}") from exc

    logger.info("Transcribing: {}", audio_path.name)

    try:
        result = model.transcribe(str(audio_path))
        segments = result.get("segments", [])

        if not segments:
            raise TranscriptionError("Whisper produced no segments")

        _segments_to_srt(segments, srt_path)
        logger.info("Transcription saved → {} ({} segments)", srt_path, len(segments))

        return srt_path

    except TranscriptionError:
        raise
    except Exception as exc:
        raise TranscriptionError(f"Transcription failed: {exc}") from exc
