"""Unit tests for the subtitle processor."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from video_engine.core.exceptions import SubtitleError
from video_engine.processors.subtitle import srt_to_json, _time_to_seconds


class TestTimeToSeconds:
    """Tests for the SRT timestamp parser."""

    def test_zero(self):
        assert _time_to_seconds("00:00:00,000") == 0.0

    def test_simple_seconds(self):
        assert _time_to_seconds("00:00:05,000") == 5.0

    def test_with_milliseconds(self):
        assert _time_to_seconds("00:00:05,500") == 5.5

    def test_minutes(self):
        assert _time_to_seconds("00:02:30,000") == 150.0

    def test_hours(self):
        assert _time_to_seconds("01:00:00,000") == 3600.0

    def test_complex_time(self):
        result = _time_to_seconds("01:23:45,678")
        assert result == pytest.approx(5025.678, abs=0.001)


class TestSrtToJson:
    """Tests for the SRT to JSON converter."""

    def _write_srt(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def test_successful_conversion(self, tmp_path):
        """Should parse valid SRT and output JSON."""
        srt_path = tmp_path / "test.srt"
        json_path = tmp_path / "test.json"

        self._write_srt(srt_path, (
            "1\n"
            "00:00:00,000 --> 00:00:03,500\n"
            "Hello world\n\n"
            "2\n"
            "00:00:03,500 --> 00:00:07,200\n"
            "Second subtitle\n\n"
        ))

        result = srt_to_json(srt_path, json_path)

        assert len(result) == 2
        assert result[0]["text"] == "Hello world"
        assert result[0]["start"] == 0.0
        assert result[0]["end"] == 3.5
        assert json_path.exists()

        # Verify written JSON
        written = json.loads(json_path.read_text(encoding="utf-8"))
        assert len(written) == 2

    def test_multiline_subtitle(self, tmp_path):
        """Should join multi-line subtitle text."""
        srt_path = tmp_path / "test.srt"
        json_path = tmp_path / "test.json"

        self._write_srt(srt_path, (
            "1\n"
            "00:00:00,000 --> 00:00:05,000\n"
            "Line one\n"
            "Line two\n\n"
        ))

        result = srt_to_json(srt_path, json_path)
        assert result[0]["text"] == "Line one Line two"

    def test_missing_file_raises(self, tmp_path):
        """Should raise SubtitleError if SRT file doesn't exist."""
        with pytest.raises(SubtitleError, match="not found"):
            srt_to_json(tmp_path / "missing.srt", tmp_path / "out.json")

    def test_empty_srt_raises(self, tmp_path):
        """Should raise SubtitleError if SRT has no valid entries."""
        srt_path = tmp_path / "empty.srt"
        self._write_srt(srt_path, "")

        with pytest.raises(SubtitleError, match="No valid"):
            srt_to_json(srt_path, tmp_path / "out.json")

    def test_malformed_block_skipped(self, tmp_path):
        """Should skip malformed blocks and process valid ones."""
        srt_path = tmp_path / "mixed.srt"
        json_path = tmp_path / "out.json"

        self._write_srt(srt_path, (
            "bad block\n\n"
            "1\n"
            "00:00:00,000 --> 00:00:03,000\n"
            "Valid subtitle\n\n"
        ))

        result = srt_to_json(srt_path, json_path)
        assert len(result) == 1
        assert result[0]["text"] == "Valid subtitle"

    def test_creates_output_directory(self, tmp_path):
        """Should create the output directory if it doesn't exist."""
        srt_path = tmp_path / "test.srt"
        json_path = tmp_path / "nested" / "deep" / "out.json"

        self._write_srt(srt_path, (
            "1\n00:00:00,000 --> 00:00:01,000\nText\n\n"
        ))

        srt_to_json(srt_path, json_path)
        assert json_path.exists()
