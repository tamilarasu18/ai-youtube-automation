"""
CLI entry point for the AI Shorts Engine.

Commands:
    run     — Generate a single video from a prompt
    batch   — Process multiple prompts from a JSON file
    serve   — Start the FastAPI REST server
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from video_engine.core.logger import logger, setup_logging
from video_engine.core.pipeline import Pipeline


def cmd_run(args: argparse.Namespace) -> None:
    """Execute a single pipeline run."""
    pipeline = Pipeline()
    result = pipeline.run(prompt=args.prompt, scheduled_time=args.schedule)

    if result["success"]:
        logger.success("Pipeline finished in {:.1f}s", result["total_duration_s"])
    else:
        logger.error("Pipeline failed: {}", result["error"])
        sys.exit(1)


def cmd_batch(args: argparse.Namespace) -> None:
    """Process multiple prompts from a JSON file."""
    json_path = Path(args.file)
    if not json_path.exists():
        logger.error("Batch file not found: {}", json_path)
        sys.exit(1)

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            items = json.load(f)
    except json.JSONDecodeError as exc:
        logger.error("Invalid JSON in batch file: {}", exc)
        sys.exit(1)

    if not isinstance(items, list):
        logger.error("Batch file must contain a JSON array of objects")
        sys.exit(1)

    if not items:
        logger.error("Batch file is empty")
        sys.exit(1)

    # Validate each item has a prompt
    for idx, item in enumerate(items, 1):
        if not isinstance(item, dict):
            logger.error("Batch item {} is not a JSON object", idx)
            sys.exit(1)
        if not (item.get("prompt") or item.get("kural")):
            logger.error("Batch item {} missing 'prompt' or 'kural' key", idx)
            sys.exit(1)

    logger.info("Batch mode: {} items to process", len(items))

    for idx, item in enumerate(items, 1):
        prompt = item.get("prompt") or item.get("kural", "")
        schedule = item.get("time") or item.get("date")

        logger.info("━━━ Batch item {}/{} ━━━", idx, len(items))
        pipeline = Pipeline()
        result = pipeline.run(prompt=prompt, scheduled_time=schedule)

        if result["success"]:
            logger.success("Item {}/{} completed", idx, len(items))
        else:
            logger.error("Item {}/{} failed: {}", idx, len(items), result["error"])


def cmd_serve(args: argparse.Namespace) -> None:
    """Start the FastAPI server."""
    import uvicorn

    from video_engine.api import app

    logger.info("Starting API server on {}:{}", args.host, args.port)
    uvicorn.run(app, host=args.host, port=args.port)


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="video-engine",
        description="AI Shorts Engine — AI-powered YouTube video generation",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # ── run ──
    run_parser = subparsers.add_parser("run", help="Generate a single video")
    run_parser.add_argument("prompt", help="Motivational text, quote, or topic")
    run_parser.add_argument(
        "--schedule",
        "-s",
        help="ISO-8601 datetime for scheduled YouTube publish",
        default=None,
    )

    # ── batch ──
    batch_parser = subparsers.add_parser("batch", help="Process prompts from JSON")
    batch_parser.add_argument("file", help="Path to JSON file with prompts")

    # ── serve ──
    serve_parser = subparsers.add_parser("serve", help="Start the REST API server")
    serve_parser.add_argument("--host", default="0.0.0.0", help="Bind host")
    serve_parser.add_argument(
        "--port",
        "-p",
        type=int,
        default=8000,
        help="Bind port",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    # Initialise
    setup_logging()

    commands = {
        "run": cmd_run,
        "batch": cmd_batch,
        "serve": cmd_serve,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
