"""
YouTube Shorts assembly using MoviePy.

Generates vertical (1080×1920) short-form videos with:
- Portrait background image
- Subtitle overlays
- Speech audio + background music
- Auto-segmentation into ≤60-second parts
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from PIL import Image
import moviepy.editor as mp

from video_engine.core.config import Settings
from video_engine.core.exceptions import VideoAssemblyError
from video_engine.core.logger import logger


def _create_text_clip(
    text: str,
    start: float,
    duration: float,
    width: int,
    font_path: str,
    font_size: int,
) -> mp.TextClip:
    """Create a styled subtitle text clip for Shorts."""
    return (
        mp.TextClip(
            text,
            fontsize=font_size,
            font=font_path,
            color="white",
            stroke_color="black",
            stroke_width=2,
            method="caption",
            size=(width - 100, None),
            align="center",
        )
        .set_position("center")
        .set_start(start)
        .set_duration(duration)
    )


def _create_short_segment(
    segment_number: int,
    segment_start: float,
    segment_duration: float,
    subtitles: list[dict],
    background_file: str,
    full_speech_audio: mp.AudioFileClip,
    background_music: mp.AudioFileClip | None,
    output_dir: Path,
    settings: Settings,
) -> Path:
    """Create a single Shorts video segment."""
    segment_end = segment_start + segment_duration
    width = settings.SHORTS_WIDTH
    height = settings.SHORTS_HEIGHT

    # Background
    bg_image = Image.open(background_file).resize((width, height), Image.Resampling.LANCZOS)
    bg_clip = mp.ImageClip(np.array(bg_image)).set_duration(segment_duration)
    bg_clip = bg_clip.fadein(0.5).fadeout(0.5)

    # Subtitle clips for this segment
    text_clips = []
    for sub in subtitles:
        if sub["end"] > segment_start and sub["start"] < segment_end:
            start_time = max(0, sub["start"] - segment_start)
            end_time = min(segment_duration, sub["end"] - segment_start)
            duration = end_time - start_time
            if duration > 0:
                clip = _create_text_clip(
                    sub["text"], start_time, duration,
                    width, settings.FONT_PATH, settings.SHORTS_FONT_SIZE,
                )
                text_clips.append(clip)

    # Compose video
    all_clips = [bg_clip] + text_clips
    final_clip = mp.CompositeVideoClip(all_clips, size=(width, height)).set_duration(segment_duration)

    # Audio
    speech_segment = full_speech_audio.subclip(segment_start, segment_end)
    if background_music:
        bg_music_segment = background_music.subclip(0, segment_duration).volumex(
            settings.BACKGROUND_MUSIC_VOLUME
        )
        final_audio = mp.CompositeAudioClip([speech_segment, bg_music_segment])
    else:
        final_audio = speech_segment
    final_clip = final_clip.set_audio(final_audio)

    # Export
    output_path = output_dir / f"youtube_shorts_part{segment_number + 1}.mp4"
    logger.info("Rendering Shorts part {} → {}", segment_number + 1, output_path)

    final_clip.write_videofile(
        str(output_path),
        fps=settings.VIDEO_FPS,
        codec=settings.VIDEO_CODEC,
        audio_codec=settings.AUDIO_CODEC,
        threads=settings.VIDEO_THREADS,
        preset=settings.VIDEO_PRESET,
        bitrate=settings.VIDEO_BITRATE,
    )

    return output_path


def assemble_shorts(work_dir: Path, settings: Settings) -> list[Path]:
    """
    Assemble YouTube Shorts videos (vertical, ≤60s segments).

    Args:
        work_dir: Working directory with audio + subtitles.
        settings: Application settings.

    Returns:
        List of paths to the generated Shorts videos.

    Raises:
        VideoAssemblyError: If required files are missing or rendering fails.
    """
    bg_image = Path(settings.OUTPUT_DIR) / "background_file" / "portrait.jpg"
    audio_file = work_dir / "generated_final_audio_file.wav"
    subtitle_file = work_dir / "subtitles.json"
    music_file = Path(settings.BACKGROUND_MUSIC)
    output_dir = settings.shorts_output_dir

    # Validate inputs
    for path, label in [
        (bg_image, "Portrait background image"),
        (audio_file, "Audio file"),
        (subtitle_file, "Subtitles JSON"),
    ]:
        if not path.exists():
            raise VideoAssemblyError(f"{label} not found: {path}")

    try:
        # Load subtitle data
        with open(subtitle_file, "r", encoding="utf-8") as f:
            subtitles = json.load(f)

        # Load audio
        full_speech = mp.AudioFileClip(str(audio_file))
        total_duration = full_speech.duration

        # Background music (optional)
        bg_music = None
        if music_file.exists():
            bg_music = mp.AudioFileClip(str(music_file))
            if bg_music.duration < settings.MAX_SHORTS_DURATION:
                loops = int(settings.MAX_SHORTS_DURATION / bg_music.duration) + 1
                bg_music = mp.concatenate_audioclips([bg_music] * loops)

        # Segment into shorts
        num_segments = math.ceil(total_duration / settings.MAX_SHORTS_DURATION)
        output_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            "Total duration: {:.1f}s → generating {} Shorts segment(s)",
            total_duration, num_segments,
        )

        outputs: list[Path] = []

        for i in range(num_segments):
            segment_start = i * settings.MAX_SHORTS_DURATION
            segment_duration = min(settings.MAX_SHORTS_DURATION, total_duration - segment_start)

            # Skip very short trailing segments
            if segment_duration < settings.MIN_SEGMENT_DURATION:
                logger.warning(
                    "Skipping part {}: duration {:.1f}s < {}s minimum",
                    i + 1, segment_duration, settings.MIN_SEGMENT_DURATION,
                )
                continue

            path = _create_short_segment(
                i, segment_start, segment_duration,
                subtitles, str(bg_image),
                full_speech, bg_music,
                output_dir, settings,
            )
            outputs.append(path)

        logger.success("All Shorts videos created: {}/{} segments", len(outputs), num_segments)
        return outputs

    except VideoAssemblyError:
        raise
    except Exception as exc:
        raise VideoAssemblyError(f"Shorts assembly failed: {exc}") from exc
