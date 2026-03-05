"""
Subtitle processing — SRT ↔ JSON conversion.

Converts SRT subtitle files to a JSON array of ``{start, end, text}``
objects for precise MoviePy subtitle overlay timing.
"""

from __future__ import annotations

import json
from pathlib import Path

from video_engine.core.exceptions import SubtitleError
from video_engine.core.logger import logger


def _time_to_seconds(time_str: str) -> float:
    """Convert SRT timestamp ``HH:MM:SS,MS`` to total seconds."""
    hours, minutes, rest = time_str.split(":")
    seconds, millis = rest.split(",")
    return int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(millis) / 1000


def srt_to_json(srt_path: Path, json_path: Path) -> list[dict]:
    """
    Convert an SRT file to a JSON subtitle array.

    Args:
        srt_path: Path to the input SRT file.
        json_path: Path where the JSON output will be written.

    Returns:
        List of subtitle dicts with ``start``, ``end``, ``text`` keys.

    Raises:
        SubtitleError: If SRT file is missing or malformed.
    """
    if not srt_path.exists():
        raise SubtitleError(f"SRT file not found: {srt_path}")

    try:
        srt_data = srt_path.read_text(encoding="utf-8")
    except Exception as exc:
        raise SubtitleError(f"Failed to read SRT file: {exc}") from exc

    subtitles: list[dict] = []
    blocks = srt_data.strip().split("\n\n")

    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) < 3:
            continue

        try:
            # Line 0: index, Line 1: timestamps, Line 2+: text
            start_str, end_str = lines[1].split(" --> ")
            text = " ".join(lines[2:]).strip()

            subtitles.append({
                "start": round(_time_to_seconds(start_str), 3),
                "end": round(_time_to_seconds(end_str), 3),
                "text": text,
            })
        except (ValueError, IndexError) as exc:
            logger.warning("Skipping malformed SRT block: {}", exc)
            continue

    if not subtitles:
        raise SubtitleError("No valid subtitle entries parsed from SRT file")

    # Ensure output directory exists
    json_path.parent.mkdir(parents=True, exist_ok=True)

    json_path.write_text(
        json.dumps(subtitles, indent=4, ensure_ascii=False),
        encoding="utf-8",
    )

    logger.info("Subtitles converted → {} ({} entries)", json_path, len(subtitles))
    return subtitles
