from fastapi.testclient import TestClient

from hypo_gpt.server import app


def test_healthz() -> None:
    client = TestClient(app)
    response = client.get("/healthz")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["engine"] == "gpt"


def test_generate_streams_complete() -> None:
    client = TestClient(app)
    response = client.post(
        "/generate",
        json={
            "research_intent": "Robust ML",
            "input_documents": [{"type": "text", "title": "Doc", "text": "Test content."}],
        },
    )
    assert response.status_code == 200
    lines = [line for line in response.text.split("\n") if line.strip()]
    assert len(lines) >= 1
    assert any('"type":"complete"' in line for line in lines)
