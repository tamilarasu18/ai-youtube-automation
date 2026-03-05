"""
Image prompt generation — produces visual scene descriptions from the story.

Calls the local LLM to produce multiple scene prompts suitable for AI image
generation. Outputs are saved to ``prompt_1.txt``, ``prompt_2.txt``, etc.
"""

from __future__ import annotations

import re
import time
from pathlib import Path

import requests

from video_engine.core.config import Settings
from video_engine.core.exceptions import ImagePromptError
from video_engine.core.logger import logger

# Retry configuration
_MAX_RETRIES = 3
_RETRY_DELAY = 5  # seconds

_NUM_SCENES = 3


def generate_image_prompt(work_dir: Path, settings: Settings) -> list[str]:
    """
    Generate multiple scene prompts from the story for image generation.

    Each prompt describes a distinct visual scene from different parts of
    the story, creating visual variety across the video.

    Args:
        work_dir: Working directory containing ``story.txt``.
        settings: Application settings.

    Returns:
        List of generated image prompt strings.

    Raises:
        ImagePromptError: If story is missing or LLM fails.
    """
    story_path = work_dir / "story.txt"
    if not story_path.exists():
        raise ImagePromptError("story.txt not found — run story generation first")

    story_content = story_path.read_text(encoding="utf-8").strip()
    if not story_content:
        raise ImagePromptError("story.txt is empty")

    prompt = (
        f"Read the following motivational story and create exactly {_NUM_SCENES} distinct "
        "image prompts for AI image generation. Each prompt should describe a different "
        "key visual scene from the story:\n\n"
        "- Scene 1: The opening/setting (establishing shot)\n"
        "- Scene 2: The central conflict or action\n"
        "- Scene 3: The resolution or emotional climax\n\n"
        f"Story:\n{story_content}\n\n"
        "Rules:\n"
        "- Each prompt must be one line, under 100 words\n"
        "- Describe VISUAL elements only (colors, lighting, composition)\n"
        "- Do NOT include any text, words, or letters in the image\n"
        "- Each scene must be visually distinct from the others\n"
        "- Use cinematic, photographic language\n\n"
        f"Output exactly {_NUM_SCENES} lines, one prompt per line, numbered 1. 2. 3.:"
    )

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            response = requests.post(
                settings.OLLAMA_URL,
                json={"model": settings.OLLAMA_MODEL, "prompt": prompt, "stream": False},
                headers={"Content-Type": "application/json"},
                timeout=300,
            )
            response.raise_for_status()
            break
        except requests.RequestException as exc:
            if attempt < _MAX_RETRIES:
                logger.warning(
                    "Ollama request failed (attempt {}/{}): {}",
                    attempt,
                    _MAX_RETRIES,
                    exc,
                )
                time.sleep(_RETRY_DELAY * attempt)
            else:
                raise ImagePromptError(
                    f"Ollama request failed after {_MAX_RETRIES} attempts: {exc}"
                ) from exc

    try:
        raw = response.json().get("response", "").strip()
        if not raw:
            raise ImagePromptError("LLM returned an empty image prompt")

        # Parse numbered lines: "1. ...", "2. ...", "3. ..."
        lines = [line.strip() for line in raw.split("\n") if line.strip()]
        scene_prompts = []
        for line in lines:
            # Strip numbering prefix like "1.", "1)", "Scene 1:", etc.
            cleaned = re.sub(r"^(\d+[\.\)]\s*|Scene\s*\d+:\s*)", "", line).strip()
            if cleaned and len(cleaned) > 10:  # skip empty or too-short lines
                scene_prompts.append(cleaned)

        if not scene_prompts:
            raise ImagePromptError("Could not parse any scene prompts from LLM response")

        # Ensure we have exactly _NUM_SCENES (pad with first if needed)
        while len(scene_prompts) < _NUM_SCENES:
            scene_prompts.append(scene_prompts[0])
        scene_prompts = scene_prompts[:_NUM_SCENES]

    except (ValueError, KeyError) as exc:
        raise ImagePromptError(f"Failed to parse LLM response: {exc}") from exc

    # Persist each scene prompt
    for i, sp in enumerate(scene_prompts, 1):
        prompt_path = work_dir / f"prompt_{i}.txt"
        prompt_path.write_text(sp, encoding="utf-8")
        logger.info("Scene {} prompt saved → {}", i, prompt_path)

    # Also save as single prompt.txt for backward compatibility
    combined_path = work_dir / "prompt.txt"
    combined_path.write_text(scene_prompts[0], encoding="utf-8")

    return scene_prompts
