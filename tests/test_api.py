"""Unit tests for the FastAPI REST server."""

from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from video_engine.api import app


@pytest.fixture
def client():
    """Create a FastAPI test client."""
    return TestClient(app)


class TestHealthEndpoint:
    """Tests for the /health endpoint."""

    def test_health_returns_ok(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data


class TestGenerateEndpoint:
    """Tests for the /generate endpoint."""

    @patch("video_engine.api.Pipeline")
    def test_successful_generation(self, MockPipeline, client):
        """Should return success with pipeline results."""
        mock_pipeline = MagicMock()
        mock_pipeline.run.return_value = {
            "success": True,
            "error": None,
            "total_duration_s": 42.5,
            "steps": [{"step": "1. Story", "duration_s": 5.0, "success": True, "detail": ""}],
        }
        MockPipeline.return_value = mock_pipeline

        response = client.post("/generate", json={"prompt": "Test quote"})

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["total_duration_s"] == 42.5

    @patch("video_engine.api.Pipeline")
    def test_with_scheduled_time(self, MockPipeline, client):
        """Should pass scheduled_time through to pipeline."""
        mock_pipeline = MagicMock()
        mock_pipeline.run.return_value = {"success": True, "error": None, "total_duration_s": 10.0, "steps": []}
        MockPipeline.return_value = mock_pipeline

        response = client.post("/generate", json={
            "prompt": "Test",
            "time": "2025-06-01T15:00:00+05:30",
        })

        assert response.status_code == 200
        mock_pipeline.run.assert_called_once_with(
            prompt="Test",
            scheduled_time="2025-06-01T15:00:00+05:30",
        )

    def test_missing_prompt_returns_422(self, client):
        """Should return 422 for missing required prompt field."""
        response = client.post("/generate", json={})
        assert response.status_code == 422

    @patch("video_engine.api.Pipeline")
    def test_pipeline_failure_returns_result(self, MockPipeline, client):
        """Should return pipeline error details on failure."""
        mock_pipeline = MagicMock()
        mock_pipeline.run.return_value = {
            "success": False,
            "error": "[StoryGeneration] LLM down",
            "total_duration_s": 1.0,
            "steps": [],
        }
        MockPipeline.return_value = mock_pipeline

        response = client.post("/generate", json={"prompt": "Test"})

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "StoryGeneration" in data["error"]
