"""
Image generation via HuggingFace FLUX.1-dev API.

Generates both landscape (1280×720) and portrait (720×1280) images from a
text prompt. Implements exponential backoff retries for API resilience.
"""

from __future__ import annotations

import io
import time
from datetime import datetime
from pathlib import Path

import requests
from PIL import Image

from video_engine.core.config import Settings
from video_engine.core.exceptions import ImageGenerationError
from video_engine.core.logger import logger


def _query_api(
    prompt: str,
    width: int,
    height: int,
    headers: dict[str, str],
    api_url: str,
    max_retries: int = 2,
    timeout: int = 120,
) -> bytes | None:
    """
    Call the HuggingFace image generation API with retries.

    Returns raw image bytes on success, None if all retries fail.
    """
    payload = {"inputs": prompt, "parameters": {"width": width, "height": height}}

    for attempt in range(max_retries + 1):
        try:
            logger.debug("Image API request attempt {}/{}", attempt + 1, max_retries + 1)
            response = requests.post(api_url, headers=headers, json=payload, timeout=timeout)

            if response.status_code == 200:
                return response.content

            logger.warning("Image API error {}: {}", response.status_code, response.text[:200])

        except requests.RequestException as exc:
            logger.warning("Image API request failed: {}", exc)

        if attempt < max_retries:
            wait_time = 5 * (attempt + 1)  # Exponential-ish backoff: 5s, 10s
            logger.info("Retrying in {}s...", wait_time)
            time.sleep(wait_time)

    return None


def generate_images(work_dir: Path, settings: Settings) -> bool:
    """
    Generate landscape and portrait images from the story's image prompt.

    Args:
        work_dir: Working directory containing ``prompt.txt``.
        settings: Application settings (HuggingFace token, API URL).

    Returns:
        True if both images were generated successfully.

    Raises:
        ImageGenerationError: If token is missing, prompt is empty, or both images fail.
    """
    if not settings.HUGGINGFACE_TOKEN:
        raise ImageGenerationError(
            "HUGGINGFACE_TOKEN not set — add it to .env or environment"
        )

    headers = {"Authorization": f"Bearer {settings.HUGGINGFACE_TOKEN}"}

    # Read prompt
    prompt_path = work_dir / "prompt.txt"
    if not prompt_path.exists():
        raise ImageGenerationError("prompt.txt not found — run image prompt generation first")

    prompt = prompt_path.read_text(encoding="utf-8").strip()
    if not prompt:
        raise ImageGenerationError("Image prompt is empty")

    logger.info("Image prompt: {}...", prompt[:80])

    # Output directories
    images_dir = Path(settings.OUTPUT_DIR) / "images"
    bg_dir = Path(settings.OUTPUT_DIR) / "background_file"
    images_dir.mkdir(parents=True, exist_ok=True)
    bg_dir.mkdir(parents=True, exist_ok=True)

    formats = {
        "landscape": (settings.LANDSCAPE_WIDTH, settings.LANDSCAPE_HEIGHT),
        "portrait": (720, 1280),
    }

    success_count = 0

    for orientation, (width, height) in formats.items():
        logger.info("Generating {} image ({}×{})...", orientation, width, height)

        image_bytes = _query_api(
            prompt, width, height, headers,
            api_url=settings.HUGGINGFACE_API_URL,
            max_retries=2,
            timeout=120,
        )

        if image_bytes:
            try:
                image = Image.open(io.BytesIO(image_bytes))

                # Save with timestamp
                timestamp = datetime.now().strftime(f"{orientation}_%Y%m%d_%H%M%S")
                archive_path = images_dir / f"{timestamp}.jpg"
                image.save(str(archive_path))
                logger.info("Saved archive image → {}", archive_path)

                # Save to background_file for video assembly
                bg_path = bg_dir / f"{orientation}.jpg"
                image.save(str(bg_path))
                logger.info("Saved background → {}", bg_path)

                success_count += 1
            except Exception as exc:
                logger.error("Failed to save {} image: {}", orientation, exc)
        else:
            logger.error("Failed to generate {} image after retries", orientation)

        time.sleep(2)  # Rate-limit courtesy pause

    logger.info("Image generation: {}/{} successful", success_count, len(formats))

    if success_count == 0:
        raise ImageGenerationError("All image generation attempts failed")

    return success_count == len(formats)
