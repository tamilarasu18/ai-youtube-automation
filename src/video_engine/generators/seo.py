"""
SEO metadata generation — title, description, and hashtags.

Uses the local Ollama LLM to produce YouTube-optimised metadata from the
generated story. Output is validated JSON saved to ``seo_content.json``.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

import requests

from video_engine.core.config import Settings
from video_engine.core.exceptions import SEOGenerationError
from video_engine.core.logger import logger

# Maximum retries for LLM calls
_MAX_RETRIES = 3
_RETRY_DELAY = 5  # seconds


def _extract_json(raw: str) -> dict:
    """
    Robustly extract a JSON object from LLM output.

    Handles: markdown fences, preamble text, trailing garbage.
    """
    # Strip markdown code fences
    cleaned = raw.replace("```json", "").replace("```", "").strip()

    # Try direct parse first
    try:
        return json.loads(cleaned)  # type: ignore[no-any-return]
    except json.JSONDecodeError:
        pass

    # Fallback: extract first {...} block with regex
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())  # type: ignore[no-any-return]
        except json.JSONDecodeError:
            pass

    raise SEOGenerationError(f"Could not extract valid JSON from LLM response: {raw[:200]}...")


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
        "{\n"
        '  "title": "<Generated Title>",\n'
        '  "description": "<Generated Description>",\n'
        '  "hashtags": ["#tag1", "#tag2", "#tag3"]\n'
        "}"
    )

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            response = requests.post(
                settings.OLLAMA_URL,
                json={"model": settings.OLLAMA_MODEL, "prompt": seo_prompt, "stream": False},
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
                raise SEOGenerationError(
                    f"Ollama request failed after {_MAX_RETRIES} attempts: {exc}"
                ) from exc

    raw = response.json().get("response", "")
    seo_data = _extract_json(raw)

    # Validate required keys
    for key in ("title", "description", "hashtags"):
        if key not in seo_data:
            raise SEOGenerationError(f"Missing required key '{key}' in SEO output")

    # Persist
    seo_path = work_dir / "seo_content.json"
    seo_path.write_text(json.dumps(seo_data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("SEO content saved → {}", seo_path)

    return seo_data
