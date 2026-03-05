"""
Landscape video assembly using MoviePy.

Composes a full-length YouTube video with:
- Background image (resized to 720p)
- Styled subtitle overlays
- Speech audio + background music mix
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image
import moviepy.editor as mp
from moviepy.video.VideoClip import TextClip

from video_engine.core.config import Settings
from video_engine.core.exceptions import VideoAssemblyError
from video_engine.core.logger import logger


def _resize_background(image_path: str, height: int) -> str:
    """Resize background image maintaining aspect ratio."""
    image = Image.open(image_path)
    width, current_height = image.size
    new_width = int((height / current_height) * width)
    image = image.resize((new_width, height), resample=Image.Resampling.LANCZOS)
    image.save(image_path)
    return image_path


def _make_text_clip(
    text: str,
    video_size: tuple[int, int],
    font_path: str,
    font_size: int,
    max_line_length: int,
) -> TextClip:
    """Create a styled subtitle text clip with word-wrapping."""
    # Word-wrap
    words = text.split()
    lines: list[str] = []
    line = ""
    for word in words:
        if len(line + " " + word) <= max_line_length:
            line = f"{line} {word}" if line else word
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)

    formatted_text = "\n".join(lines)

    text_clip = (
        TextClip(
            formatted_text,
            fontsize=font_size,
            font=font_path,
            color="white",
            stroke_color="black",
            stroke_width=2,
            method="caption",
            size=(video_size[0] - 100, None),
            align="center",
            kerning=2,
            interline=10,
        )
        .set_position(("center", "center"))
    )
    return text_clip


def assemble_landscape_video(work_dir: Path, settings: Settings) -> Path:
    """
    Assemble a landscape (16:9) YouTube video.

    Args:
        work_dir: Working directory containing audio, subtitles, and images.
        settings: Application settings (encoding, font, paths).

    Returns:
        Path to the rendered video file.

    Raises:
        VideoAssemblyError: If required files are missing or rendering fails.
    """
    bg_image = Path(settings.OUTPUT_DIR) / "background_file" / "landscape.jpg"
    audio_file = work_dir / "generated_final_audio_file.wav"
    subtitle_file = work_dir / "subtitles.json"
    music_file = Path(settings.BACKGROUND_MUSIC)
    output_file = settings.yt_video_dir / "final_video.mp4"

    # Validate inputs
    for path, label in [
        (bg_image, "Background image"),
        (audio_file, "Audio file"),
        (subtitle_file, "Subtitles JSON"),
    ]:
        if not path.exists():
            raise VideoAssemblyError(f"{label} not found: {path}")

    try:
        # Resize background
        resized_bg = _resize_background(str(bg_image), settings.LANDSCAPE_HEIGHT)
        background = mp.ImageClip(resized_bg)

        # Load audio and set duration
        speech_audio = mp.AudioFileClip(str(audio_file))
        video_duration = speech_audio.duration
        background = background.set_duration(video_duration)

        # Load subtitle data
        with open(subtitle_file, "r", encoding="utf-8") as f:
            subtitles_data = json.load(f)

        # Create subtitle clips
        subtitle_clips = []
        for sub in subtitles_data:
            clip = _make_text_clip(
                sub["text"],
                (settings.LANDSCAPE_WIDTH, settings.LANDSCAPE_HEIGHT),
                settings.FONT_PATH,
                settings.FONT_SIZE,
                settings.MAX_LINE_LENGTH,
            )
            clip = clip.set_start(sub["start"]).set_end(sub["end"])
            subtitle_clips.append(clip)

        subtitles_overlay = mp.CompositeVideoClip(subtitle_clips, size=background.size)

        # Background music
        if music_file.exists():
            bg_music = mp.AudioFileClip(str(music_file)).volumex(settings.BACKGROUND_MUSIC_VOLUME)
            if bg_music.duration < video_duration:
                loops = int(video_duration / bg_music.duration) + 1
                bg_music = mp.concatenate_audioclips([bg_music] * loops)
            bg_music = bg_music.subclip(0, video_duration)
            final_audio = mp.CompositeAudioClip([speech_audio, bg_music])
        else:
            logger.warning("Background music not found: {}, using speech only", music_file)
            final_audio = speech_audio

        # Compose final video
        main_video = mp.CompositeVideoClip([background, subtitles_overlay])
        main_video = main_video.set_audio(final_audio)
        final_video = mp.concatenate_videoclips([main_video])

        # Render
        output_file.parent.mkdir(parents=True, exist_ok=True)
        logger.info("Rendering landscape video → {}", output_file)

        final_video.write_videofile(
            str(output_file),
            fps=settings.VIDEO_FPS,
            codec=settings.VIDEO_CODEC,
            audio_codec=settings.AUDIO_CODEC,
            threads=settings.VIDEO_THREADS,
            preset=settings.VIDEO_PRESET,
            bitrate=settings.VIDEO_BITRATE,
        )

        logger.success("Landscape video created → {}", output_file)
        return output_file

    except VideoAssemblyError:
        raise
    except Exception as exc:
        raise VideoAssemblyError(f"Video rendering failed: {exc}") from exc
