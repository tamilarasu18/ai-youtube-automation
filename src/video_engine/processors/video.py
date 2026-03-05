"""
Landscape video assembly using MoviePy.

Composes a full-length YouTube video with:
- Intro title card with fade-in
- Multiple background images with Ken Burns (zoom/pan) effect
- Crossfade transitions between scenes
- Styled subtitle overlays (bottom third)
- Speech audio + background music mix
- Outro with subscribe CTA
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Sequence

import numpy as np

# Auto-detect ImageMagick for MoviePy (required for TextClip subtitles)
if "IMAGEMAGICK_BINARY" not in os.environ:
    for _candidate in ["/usr/bin/convert", "/usr/local/bin/convert"]:
        if os.path.isfile(_candidate):
            os.environ["IMAGEMAGICK_BINARY"] = _candidate
            break

import moviepy.editor as mp
from moviepy.video.VideoClip import TextClip
from PIL import Image

from video_engine.core.config import Settings
from video_engine.core.exceptions import VideoAssemblyError
from video_engine.core.logger import logger

# ── Duration Constants ──────────────────────────────────────────
_INTRO_DURATION = 3.0  # seconds
_OUTRO_DURATION = 4.0  # seconds
_CROSSFADE = 0.5  # seconds of crossfade between scenes


def _resize_image(image_path: str, target_w: int, target_h: int) -> str:
    """Resize image to exact target dimensions, return path to resized copy."""
    img = Image.open(image_path)
    resized = img.resize((target_w, target_h), resample=Image.Resampling.LANCZOS)
    p = Path(image_path)
    resized_path = p.parent / f"{p.stem}_resized{p.suffix}"
    resized.save(str(resized_path))
    return str(resized_path)


def _ken_burns_clip(
    image_path: str,
    duration: float,
    target_w: int,
    target_h: int,
    zoom_start: float = 1.0,
    zoom_end: float = 1.15,
) -> mp.VideoClip:
    """
    Create a clip with Ken Burns effect (slow zoom) on a static image.

    Generates the image slightly larger, then crops to target size with
    smooth zoom animation.
    """
    # Load and resize image larger than target to allow zoom
    max_zoom = max(zoom_start, zoom_end)
    oversized_w = int(target_w * max_zoom) + 4  # +4 for rounding safety
    oversized_h = int(target_h * max_zoom) + 4

    img = Image.open(image_path)
    img_resized = img.resize((oversized_w, oversized_h), resample=Image.Resampling.LANCZOS)
    img_array = np.array(img_resized)

    def make_frame(t: float) -> np.ndarray:
        """Generate frame at time t with zoom applied."""
        progress = t / max(duration, 0.001)
        current_zoom = zoom_start + (zoom_end - zoom_start) * progress

        # Calculate crop region (center crop)
        crop_w = int(target_w * (max_zoom / current_zoom))
        crop_h = int(target_h * (max_zoom / current_zoom))

        cx, cy = oversized_w // 2, oversized_h // 2
        x1 = max(0, cx - crop_w // 2)
        y1 = max(0, cy - crop_h // 2)
        x2 = min(oversized_w, x1 + crop_w)
        y2 = min(oversized_h, y1 + crop_h)

        cropped = img_array[y1:y2, x1:x2]

        # Resize back to target dimensions
        from PIL import Image as PILImage

        pil_cropped = PILImage.fromarray(cropped)
        pil_final = pil_cropped.resize((target_w, target_h), resample=PILImage.Resampling.LANCZOS)
        return np.array(pil_final)

    clip = mp.VideoClip(make_frame, duration=duration)
    return clip


def _make_title_card(
    title: str,
    duration: float,
    width: int,
    height: int,
    font_path: str,
) -> mp.VideoClip:
    """Create an intro title card with dark background and centered text."""
    # Dark gradient background
    bg = mp.ColorClip(size=(width, height), color=(15, 15, 25)).set_duration(duration)

    # Title text
    title_clip = TextClip(
        title,
        fontsize=50,
        font=font_path,
        color="white",
        stroke_color="black",
        stroke_width=1,
        method="caption",
        size=(width - 200, None),
        align="center",
    ).set_position("center").set_duration(duration)

    card = mp.CompositeVideoClip([bg, title_clip], size=(width, height))
    card = card.fadein(0.8).fadeout(0.5)
    return card


def _make_outro(
    duration: float,
    width: int,
    height: int,
    font_path: str,
) -> mp.VideoClip:
    """Create an outro card with subscribe CTA."""
    bg = mp.ColorClip(size=(width, height), color=(15, 15, 25)).set_duration(duration)

    cta_text = TextClip(
        "Subscribe • Like • Share",
        fontsize=45,
        font=font_path,
        color="#FFD700",  # Gold
        stroke_color="black",
        stroke_width=1,
        method="caption",
        size=(width - 200, None),
        align="center",
    ).set_position("center").set_duration(duration)

    card = mp.CompositeVideoClip([bg, cta_text], size=(width, height))
    card = card.fadein(0.5).fadeout(1.0)
    return card


def _make_text_clip(
    text: str,
    video_size: tuple[int, int],
    font_path: str,
    font_size: int,
    max_line_length: int,
) -> TextClip:
    """Create a styled subtitle text clip with word-wrapping, positioned at bottom third."""
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

    text_clip = TextClip(
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
    ).set_position(("center", 0.78), relative=True)  # Bottom third
    return text_clip


def _discover_scene_images(bg_dir: Path, orientation: str) -> list[Path]:
    """Find all scene images for the given orientation, sorted by index."""
    # Try multi-scene: landscape_1.jpg, landscape_2.jpg, ...
    scene_images = sorted(bg_dir.glob(f"{orientation}_[0-9]*.jpg"))

    # Fallback: single image
    if not scene_images:
        single = bg_dir / f"{orientation}.jpg"
        if single.exists():
            scene_images = [single]

    return scene_images


def _get_seo_title(work_dir: Path) -> str:
    """Read story title from SEO content or story.txt."""
    seo_path = work_dir / "seo_content.json"
    if seo_path.exists():
        try:
            data = json.loads(seo_path.read_text(encoding="utf-8"))
            title = data.get("title", "")
            if title:
                return title
        except (json.JSONDecodeError, OSError):
            pass

    # Fallback: first line of story
    story_path = work_dir / "story.txt"
    if story_path.exists():
        first_line = story_path.read_text(encoding="utf-8").strip().split("\n")[0]
        return first_line.strip()

    return ""


def assemble_landscape_video(work_dir: Path, settings: Settings) -> Path:
    """
    Assemble a landscape (16:9) YouTube video with Ken Burns and transitions.

    Features:
        - Intro title card (3s)
        - Multiple scene images with Ken Burns zoom effect
        - Crossfade transitions between scenes
        - Bottom-third subtitles
        - Background music mix
        - Outro subscribe CTA (4s)

    Args:
        work_dir: Working directory containing audio, subtitles, and images.
        settings: Application settings (encoding, font, paths).

    Returns:
        Path to the rendered video file.

    Raises:
        VideoAssemblyError: If required files are missing or rendering fails.
    """
    bg_dir = Path(settings.OUTPUT_DIR) / "background_file"
    audio_file = work_dir / "generated_final_audio_file.wav"
    subtitle_file = work_dir / "subtitles.json"
    music_file = Path(settings.BACKGROUND_MUSIC)
    output_file = settings.yt_video_dir / "final_video.mp4"

    width = settings.LANDSCAPE_WIDTH
    height = settings.LANDSCAPE_HEIGHT

    # Discover scene images
    scene_images = _discover_scene_images(bg_dir, "landscape")
    if not scene_images:
        raise VideoAssemblyError(f"No landscape images found in {bg_dir}")

    # Validate other inputs
    for path, label in [
        (audio_file, "Audio file"),
        (subtitle_file, "Subtitles JSON"),
    ]:
        if not path.exists():
            raise VideoAssemblyError(f"{label} not found: {path}")

    try:
        # ── Audio ────────────────────────────────────────────────
        speech_audio = mp.AudioFileClip(str(audio_file))
        narration_duration = speech_audio.duration

        # Total video = intro + narration + outro
        total_duration = _INTRO_DURATION + narration_duration + _OUTRO_DURATION

        # ── Intro ────────────────────────────────────────────────
        title = _get_seo_title(work_dir)
        intro = _make_title_card(title, _INTRO_DURATION, width, height, settings.FONT_PATH)

        # ── Scene Clips with Ken Burns ───────────────────────────
        num_scenes = len(scene_images)
        scene_duration = narration_duration / num_scenes
        logger.info("{} scene image(s), {:.1f}s each", num_scenes, scene_duration)

        scene_clips = []
        for i, img_path in enumerate(scene_images):
            # Alternate zoom direction for visual variety
            if i % 2 == 0:
                zoom_start, zoom_end = 1.0, 1.12
            else:
                zoom_start, zoom_end = 1.12, 1.0

            clip = _ken_burns_clip(
                str(img_path),
                scene_duration,
                width,
                height,
                zoom_start=zoom_start,
                zoom_end=zoom_end,
            )

            # Crossfade transitions
            if num_scenes > 1:
                clip = clip.crossfadein(_CROSSFADE)

            scene_clips.append(clip)

        # Concatenate scenes with crossfade
        if len(scene_clips) > 1:
            scenes_video = mp.concatenate_videoclips(
                scene_clips,
                method="compose",
                padding=-_CROSSFADE,
            )
        else:
            scenes_video = scene_clips[0]

        # Trim to exact narration duration
        scenes_video = scenes_video.set_duration(narration_duration)

        # ── Outro ────────────────────────────────────────────────
        outro = _make_outro(_OUTRO_DURATION, width, height, settings.FONT_PATH)

        # ── Subtitles ────────────────────────────────────────────
        with open(subtitle_file, "r", encoding="utf-8") as f:
            subtitles_data = json.load(f)

        subtitle_clips = []
        for sub in subtitles_data:
            clip = _make_text_clip(
                sub["text"],
                (width, height),
                settings.FONT_PATH,
                settings.FONT_SIZE,
                settings.MAX_LINE_LENGTH,
            )
            # Offset subtitle timing by intro duration
            clip = clip.set_start(sub["start"] + _INTRO_DURATION)
            clip = clip.set_end(sub["end"] + _INTRO_DURATION)
            subtitle_clips.append(clip)

        # ── Compose Main Video ───────────────────────────────────
        # Concatenate: intro → scenes → outro
        base_video = mp.concatenate_videoclips([intro, scenes_video, outro])

        # Overlay subtitles
        all_clips = [base_video] + subtitle_clips
        final_video = mp.CompositeVideoClip(all_clips, size=(width, height))

        # ── Audio Mix ────────────────────────────────────────────
        # Offset speech to start after intro
        speech_offset = speech_audio.set_start(_INTRO_DURATION)

        if music_file.exists():
            bg_music = mp.AudioFileClip(str(music_file)).volumex(
                settings.BACKGROUND_MUSIC_VOLUME
            )
            if bg_music.duration < total_duration:
                loops = int(total_duration / bg_music.duration) + 1
                bg_music = mp.concatenate_audioclips([bg_music] * loops)
            bg_music = bg_music.subclip(0, total_duration)
            final_audio = mp.CompositeAudioClip([speech_offset, bg_music])
        else:
            logger.warning("Background music not found: {}, using speech only", music_file)
            final_audio = speech_offset

        final_video = final_video.set_audio(final_audio)
        final_video = final_video.set_duration(total_duration)

        # ── Render ───────────────────────────────────────────────
        output_file.parent.mkdir(parents=True, exist_ok=True)
        logger.info("Rendering landscape video ({:.0f}s) → {}", total_duration, output_file)

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
