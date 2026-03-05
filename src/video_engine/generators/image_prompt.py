"""
Image prompt generation — summarises the story into a visual description.

Calls the local LLM to produce a one-line prompt suitable for AI image
generation. Output is saved to ``prompt.txt``.
"""

from __future__ import annotations

from pathlib import Path

import requests

from video_engine.core.config import Settings
from video_engine.core.exceptions import ImagePromptError
from video_engine.core.logger import logger


def generate_image_prompt(work_dir: Path, settings: Settings) -> str:
    """
    Generate a single-line image prompt from the story.

    Args:
        work_dir: Working directory containing ``story.txt``.
        settings: Application settings.

    Returns:
        The generated image prompt string.

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
        "Summarize the following motivational story into a single-line prompt for AI image "
        "generation. The prompt should describe one key visual scene from the story that "
        "captures its essence. Keep it short, clear, and suitable for generating a single "
        "image without including any text or words in the image.\n\n"
        f"Story:\n{story_content}\n\n"
        "One-line Image Prompt:"
    )

    try:
        response = requests.post(
            settings.OLLAMA_URL,
            json={"model": settings.OLLAMA_MODEL, "prompt": prompt, "stream": False},
            headers={"Content-Type": "application/json"},
            timeout=120,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise ImagePromptError(f"Ollama request failed: {exc}") from exc

    try:
        result = response.json().get("response", "").replace("##", "").strip()
        if not result:
            raise ImagePromptError("LLM returned an empty image prompt")
    except (ValueError, KeyError) as exc:
        raise ImagePromptError(f"Failed to parse LLM response: {exc}") from exc

    # Persist
    prompt_path = work_dir / "prompt.txt"
    prompt_path.write_text(result, encoding="utf-8")
    logger.info("Image prompt saved → {}", prompt_path)

    return result
