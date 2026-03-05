"""
SEO metadata generation — title, description, and hashtags.

Uses the local Ollama LLM to produce YouTube-optimised metadata from the
generated story. Output is validated JSON saved to ``seo_content.json``.
"""

from __future__ import annotations

import json
from pathlib import Path

import requests

from video_engine.core.config import Settings
from video_engine.core.exceptions import SEOGenerationError
from video_engine.core.logger import logger


def generate_seo(work_dir: Path, settings: Settings) -> dict:
    """
    Generate SEO metadata (title, description, hashtags) from the story.

    Args:
        work_dir: Working directory containing ``story.txt``.
        settings: Application settings.

    Returns:
        Parsed SEO dict with ``title``, ``description``, ``hashtags``.

    Raises:
        SEOGenerationError: If story file is missing, LLM fails, or JSON is invalid.
    """
    story_path = work_dir / "story.txt"
    if not story_path.exists():
        raise SEOGenerationError("story.txt not found — run story generation first")

    story_content = story_path.read_text(encoding="utf-8").strip()
    if not story_content:
        raise SEOGenerationError("story.txt is empty")

    seo_prompt = (
        "You are an expert YouTube content writer. Based on the following motivational story:\n\n"
        f"{story_content}\n\n"
        "Generate an SEO-optimized YouTube title, description, and popular hashtags.\n"
        "Title should be catchy, emotional, with 1-2 emojis, under 60 characters.\n"
        "Description should summarize the story, include motivational keywords, "
        "and add 2-3 emojis naturally.\n"
        "Hashtags should be relevant, trending, and engaging (max 5).\n\n"
        "Provide the output in perfect JSON format:\n"
        '{\n'
        '  "title": "<Generated Title>",\n'
        '  "description": "<Generated Description>",\n'
        '  "hashtags": ["#tag1", "#tag2", "#tag3"]\n'
        '}'
    )

    try:
        response = requests.post(
            settings.OLLAMA_URL,
            json={"model": settings.OLLAMA_MODEL, "prompt": seo_prompt, "stream": False},
            headers={"Content-Type": "application/json"},
            timeout=120,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise SEOGenerationError(f"Ollama request failed: {exc}") from exc

    try:
        raw = response.json().get("response", "")
        # Strip markdown code fences if present
        cleaned = raw.replace("```json", "").replace("```", "").strip()
        seo_data = json.loads(cleaned)
    except (ValueError, KeyError, json.JSONDecodeError) as exc:
        raise SEOGenerationError(f"Failed to parse SEO JSON: {exc}") from exc

    # Validate required keys
    for key in ("title", "description", "hashtags"):
        if key not in seo_data:
            raise SEOGenerationError(f"Missing required key '{key}' in SEO output")

    # Persist
    seo_path = work_dir / "seo_content.json"
    seo_path.write_text(json.dumps(seo_data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("SEO content saved → {}", seo_path)

    return seo_data
