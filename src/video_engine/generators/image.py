"""
Image generation using local Stable Diffusion (diffusers).

Generates both landscape (1280×720) and portrait (720×1280) images from a
text prompt using Stable Diffusion XL running locally on GPU. No API token
required — the model is downloaded and cached automatically.
"""

from __future__ import annotations

import gc
from datetime import datetime
from pathlib import Path

import torch
from diffusers import DPMSolverMultistepScheduler, StableDiffusionXLPipeline
from PIL import Image

from video_engine.core.config import Settings
from video_engine.core.exceptions import ImageGenerationError
from video_engine.core.logger import logger

# Module-level pipeline cache to avoid reloading the model
_pipeline_cache: StableDiffusionXLPipeline | None = None


def _get_pipeline(model_id: str, device: str) -> StableDiffusionXLPipeline:
    """
    Load and cache the Stable Diffusion XL pipeline.

    Uses half-precision (float16) on GPU for speed and memory efficiency.
    The model is downloaded once and cached in ``~/.cache/huggingface/``.
    """
    global _pipeline_cache

    if _pipeline_cache is not None:
        return _pipeline_cache

    logger.info("Loading Stable Diffusion model: {} ...", model_id)

    dtype = torch.float16 if device == "cuda" else torch.float32

    pipe = StableDiffusionXLPipeline.from_pretrained(
        model_id,
        torch_dtype=dtype,
        use_safetensors=True,
        variant="fp16" if device == "cuda" else None,
    )

    # Use DPM++ 2M scheduler for faster, high-quality sampling
    pipe.scheduler = DPMSolverMultistepScheduler.from_config(pipe.scheduler.config)

    pipe = pipe.to(device)

    # Memory optimisations for Colab / consumer GPUs
    if device == "cuda":
        pipe.enable_attention_slicing()
        try:
            pipe.enable_xformers_memory_efficient_attention()
            logger.info("xformers memory-efficient attention enabled")
        except Exception:
            logger.debug("xformers not available, using default attention")

    _pipeline_cache = pipe
    logger.info("Model loaded on {} (dtype: {})", device, dtype)
    return pipe


def _generate_single(
    pipe: StableDiffusionXLPipeline,
    prompt: str,
    width: int,
    height: int,
    num_inference_steps: int,
    guidance_scale: float,
) -> Image.Image:
    """Generate a single image from a prompt."""
    result = pipe(
        prompt=prompt,
        negative_prompt=(
            "blurry, low quality, distorted, deformed, text, watermark, "
            "signature, ugly, bad anatomy, extra limbs"
        ),
        width=width,
        height=height,
        num_inference_steps=num_inference_steps,
        guidance_scale=guidance_scale,
    )
    return result.images[0]


def generate_images(work_dir: Path, settings: Settings) -> bool:
    """
    Generate landscape and portrait images using local Stable Diffusion.

    Args:
        work_dir: Working directory containing ``prompt.txt``.
        settings: Application settings (model, steps, guidance scale).

    Returns:
        True if both images were generated successfully.

    Raises:
        ImageGenerationError: If prompt is missing or generation fails.
    """
    # Read prompt
    prompt_path = work_dir / "prompt.txt"
    if not prompt_path.exists():
        raise ImageGenerationError("prompt.txt not found — run image prompt generation first")

    prompt = prompt_path.read_text(encoding="utf-8").strip()
    if not prompt:
        raise ImageGenerationError("Image prompt is empty")

    logger.info("Image prompt: {}...", prompt[:80])

    # Detect device
    device = "cuda" if torch.cuda.is_available() else "cpu"
    if device == "cpu":
        logger.warning("No GPU detected — image generation will be slow on CPU")

    # Load model
    try:
        pipe = _get_pipeline(settings.SD_MODEL_ID, device)
    except Exception as exc:
        raise ImageGenerationError(f"Failed to load Stable Diffusion model: {exc}") from exc

    # Output directories
    images_dir = Path(settings.OUTPUT_DIR) / "images"
    bg_dir = Path(settings.OUTPUT_DIR) / "background_file"
    images_dir.mkdir(parents=True, exist_ok=True)
    bg_dir.mkdir(parents=True, exist_ok=True)

    formats = {
        "landscape": (settings.LANDSCAPE_WIDTH, settings.LANDSCAPE_HEIGHT),
        "portrait": (720, 1280),
    }

    # SDXL native resolution for best quality
    native_size = 1024

    success_count = 0

    for orientation, (target_w, target_h) in formats.items():
        logger.info(
            "Generating {} image ({}×{}, {} steps)...",
            orientation,
            target_w,
            target_h,
            settings.SD_NUM_STEPS,
        )

        try:
            # Generate at SDXL native 1024×1024 for best quality
            image = _generate_single(
                pipe,
                prompt,
                native_size,
                native_size,
                num_inference_steps=settings.SD_NUM_STEPS,
                guidance_scale=settings.SD_GUIDANCE_SCALE,
            )

            # Resize to target dimensions
            from PIL import Image as PILImage

            image = image.resize((target_w, target_h), resample=PILImage.Resampling.LANCZOS)
            logger.debug("Resized {}×{} → {}×{}", native_size, native_size, target_w, target_h)

            # Save with timestamp
            timestamp = datetime.now().strftime(f"{orientation}_%Y%m%d_%H%M%S")
            archive_path = images_dir / f"{timestamp}.jpg"
            image.save(str(archive_path), quality=95)
            logger.info("Saved archive image → {}", archive_path)

            # Save to background_file for video assembly
            bg_path = bg_dir / f"{orientation}.jpg"
            image.save(str(bg_path), quality=95)
            logger.info("Saved background → {}", bg_path)

            success_count += 1

        except Exception as exc:
            logger.error("Failed to generate {} image: {}", orientation, exc)

        # Free GPU memory between generations to avoid OOM on T4
        if device == "cuda":
            torch.cuda.empty_cache()
            gc.collect()

    # Free GPU memory after generation
    if device == "cuda":
        torch.cuda.empty_cache()
        gc.collect()

    logger.info("Image generation: {}/{} successful", success_count, len(formats))

    if success_count == 0:
        raise ImageGenerationError("All image generation attempts failed")

    return success_count == len(formats)


def unload_model() -> None:
    """Explicitly unload the model to free GPU memory."""
    global _pipeline_cache
    if _pipeline_cache is not None:
        del _pipeline_cache
        _pipeline_cache = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        gc.collect()
        logger.info("Stable Diffusion model unloaded")
