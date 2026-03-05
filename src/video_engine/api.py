"""
FastAPI REST server for the AI Shorts Engine.

Endpoints:
    POST /generate  — Trigger a full pipeline run
    GET  /health    — Health check
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from video_engine.core.logger import logger, setup_logging
from video_engine.core.pipeline import Pipeline

# ── App Setup ──────────────────────────────────────────────────────

app = FastAPI(
    title="AI Shorts Engine",
    version="1.0.0",
    description="AI-powered YouTube video generation API",
)


@app.on_event("startup")
async def startup() -> None:
    setup_logging()
    logger.info("API server started")


# ── Models ─────────────────────────────────────────────────────────


class GenerateRequest(BaseModel):
    """Request body for the /generate endpoint."""

    prompt: str = Field(..., description="Motivational text, quote, or topic")
    scheduled_time: str | None = Field(
        None,
        alias="time",
        description="Optional ISO-8601 datetime for scheduled YouTube publish",
    )

    class Config:
        populate_by_name = True


class GenerateResponse(BaseModel):
    """Response body for the /generate endpoint."""

    success: bool
    error: str | None = None
    total_duration_s: float | None = None
    steps: list[dict] | None = None


# ── Endpoints ──────────────────────────────────────────────────────


@app.get("/health")
async def health() -> dict:
    """Health check endpoint."""
    return {"status": "ok", "version": "1.0.0"}


@app.post("/generate", response_model=GenerateResponse)
async def generate(request: GenerateRequest) -> GenerateResponse:
    """
    Trigger a full pipeline run.

    Accepts a motivational prompt and an optional scheduled publish time.
    Returns the pipeline result with step-by-step tracking.
    """
    try:
        pipeline = Pipeline()
        result = pipeline.run(
            prompt=request.prompt,
            scheduled_time=request.scheduled_time,
        )

        return GenerateResponse(
            success=result["success"],
            error=result.get("error"),
            total_duration_s=result.get("total_duration_s"),
            steps=result.get("steps"),
        )

    except Exception as exc:
        logger.exception("API error during /generate")
        raise HTTPException(
            status_code=500,
            detail=f"Internal Server Error: {str(exc)}",
        ) from exc
