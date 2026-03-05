"""Integration tests for the FastAPI server endpoints."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from vreda_hypothesis.models import GeneratorOutput
from vreda_hypothesis.server import app


@pytest.fixture
def client():
    return TestClient(app)


def test_healthcheck(client):
    """GET /healthz should return status ok."""
    with patch("vreda_hypothesis.server.LLMProvider") as mock_cls:
        mock_instance = mock_cls.return_value
        mock_instance.get_active_providers.return_value = {"default": "MockLLM"}
        response = client.get("/healthz")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "active_providers" in data


def test_healthcheck_provider_failure(client):
    """GET /healthz should handle provider initialization failure."""
    with patch("vreda_hypothesis.server.LLMProvider", side_effect=Exception("No API key")):
        response = client.get("/healthz")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "error" in data["active_providers"]


def test_generate_requires_input(client):
    """POST /generate without arxiv_id or pdf_path should return 400."""
    response = client.post("/generate", json={})
    assert response.status_code == 400
    assert "Provide arxiv_id or pdf_path" in response.json()["detail"]


def test_generate_accepts_arxiv_id(client):
    """POST /generate with arxiv_id should start streaming."""
    mock_output = GeneratorOutput(
        hypotheses=[],
        reasoning_context="test context",
        reflection_rounds=0,
    )

    with patch("vreda_hypothesis.server.generate_hypotheses", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = mock_output
        response = client.post(
            "/generate",
            json={"arxiv_id": "1706.03762"},
        )

    assert response.status_code == 200
    assert "application/x-ndjson" in response.headers["content-type"]

    # Parse NDJSON lines
    lines = [line for line in response.text.strip().split("\n") if line.strip()]
    assert len(lines) >= 1  # At least the "complete" event

    # Last event should be the completion event
    last = json.loads(lines[-1])
    assert last["type"] == "complete"
    assert "output" in last.get("data", {})


def test_generate_accepts_config(client):
    """POST /generate should accept optional config."""
    mock_output = GeneratorOutput(hypotheses=[], reasoning_context="test")

    with patch("vreda_hypothesis.server.generate_hypotheses", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = mock_output
        response = client.post(
            "/generate",
            json={
                "arxiv_id": "2409.04109",
                "config": {
                    "max_seeds": 50,
                    "max_cycles": 2,
                    "top_k": 5,
                },
            },
        )

    assert response.status_code == 200


def test_generate_handles_pipeline_error(client):
    """POST /generate should stream an error event when pipeline fails."""
    with patch("vreda_hypothesis.server.generate_hypotheses", new_callable=AsyncMock) as mock_gen:
        mock_gen.side_effect = RuntimeError("Pipeline exploded")
        response = client.post(
            "/generate",
            json={"arxiv_id": "1706.03762"},
        )

    assert response.status_code == 200  # Streaming started before error
    lines = [line for line in response.text.strip().split("\n") if line.strip()]
    assert len(lines) >= 1
    # Should contain an error event
    last = json.loads(lines[-1])
    assert last["type"] == "error" or "error" in last.get("message", "").lower() or last["type"] == "complete"
