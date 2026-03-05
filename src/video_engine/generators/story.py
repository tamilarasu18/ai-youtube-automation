"""
Story generation using a local Ollama LLM.

Produces a unique short motivational story by randomising style, tone, and
character archetypes. The result is saved to ``<work_dir>/story.txt``.
"""

from __future__ import annotations

import random
from pathlib import Path

import requests

from video_engine.core.config import Settings
from video_engine.core.exceptions import StoryGenerationError
from video_engine.core.logger import logger

# ── Randomisation Pools ────────────────────────────────────────────

STORY_STYLES = [
    "a modern-day moral tale",
    "a historical fiction",
    "a parable set in a village",
    "a science fiction metaphor",
    "a fantasy story with symbolic characters",
    "an emotional story based on a real-life scenario",
    "a story set in a school or college",
    "a corporate drama with ethical choices",
]

TONES = [
    "inspirational and uplifting",
    "emotional and touching",
    "suspenseful and dramatic",
    "subtle and reflective",
    "humorous but meaningful",
]

CHARACTERS = [
    "a curious child and a wise elder",
    "a struggling entrepreneur",
    "a teacher guiding a student",
    "a king learning humility",
    "an AI discovering purpose",
    "a street artist chasing dreams",
    "a monk teaching a traveler",
    "siblings with contrasting beliefs",
]


def generate_story(inspiration: str, settings: Settings) -> str:
    """
    Generate a motivational story from the given inspiration text.

    Args:
        inspiration: The motivational idea, quote, or concept.
        settings: Application settings (Ollama URL / model).

    Returns:
        The generated story text.

    Raises:
        StoryGenerationError: If the LLM request or response parsing fails.
    """
    style = random.choice(STORY_STYLES)
    tone = random.choice(TONES)
    character = random.choice(CHARACTERS)

    prompt = (
        f'Write {style} in a {tone} tone based on the following motivational idea or quote:\n\n'
        f'"{inspiration}"\n\n'
        f'Create an engaging short story that conveys the core message through a scenario '
        f'involving {character}. '
        'Use natural dialogues, emotional depth, and a clear narrative arc that helps readers '
        'understand the lesson through action and emotion, not just narration. '
        'Keep it within 350 words. Give it a powerful title, and end the story with this '
        'call to action:\n\n'
        "'Subscribe to my YouTube channel, like, share, and comment.'\n\n"
        'Only output the story with the title — no other explanation or headers.'
    )

    logger.debug("Story prompt style={}, tone={}, character={}", style, tone, character)

    try:
        response = requests.post(
            settings.OLLAMA_URL,
            json={"model": settings.OLLAMA_MODEL, "prompt": prompt, "stream": False},
            headers={"Content-Type": "application/json"},
            timeout=120,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise StoryGenerationError(f"Ollama request failed: {exc}") from exc

    try:
        result = response.json().get("response", "")
        if not result.strip():
            raise StoryGenerationError("LLM returned an empty response")
        result = result.replace("##", "")
    except (ValueError, KeyError) as exc:
        raise StoryGenerationError(f"Failed to parse LLM response: {exc}") from exc

    # Persist to working directory
    work_dir = settings.video_output_dir
    work_dir.mkdir(parents=True, exist_ok=True)
    story_path = work_dir / "story.txt"
    story_path.write_text(result, encoding="utf-8")
    logger.info("Story saved → {}", story_path)

    return result
