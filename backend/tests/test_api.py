"""End-to-end tests for the backend scan API."""

from __future__ import annotations

import time
from pathlib import Path

from starlette.testclient import TestClient

GRAPH_KEYS = {"modules", "ports", "edges", "externalModules", "diagnostics"}


def _poll_status(client: TestClient, job_id: str, timeout: float = 10.0) -> dict:
    """Poll status until terminal or timeout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(f"/api/scan/{job_id}/status")
        assert response.status_code == 200
        payload = response.json()
        if payload["status"] in ("done", "error"):
            return payload
        time.sleep(0.05)
    raise TimeoutError(f"Job {job_id} did not reach terminal status in {timeout}s")


def test_scan_happy_path(client: TestClient, mini_pkg: Path) -> None:
    response = client.post("/api/scan", json={"path": str(mini_pkg)})
    assert response.status_code == 202
    payload = response.json()
    assert "jobId" in payload
    job_id = payload["jobId"]

    status = _poll_status(client, job_id)
    assert status["status"] == "done"

    graph_response = client.get(f"/api/scan/{job_id}/graph")
    assert graph_response.status_code == 200
    graph = graph_response.json()
    assert set(graph.keys()) == GRAPH_KEYS
    assert len(graph["modules"]) > 0


def test_scan_invalid_path(client: TestClient) -> None:
    response = client.post("/api/scan", json={"path": "/does/not/exist"})
    assert response.status_code == 400
    payload = response.json()
    assert payload["error"] == "path_not_found"
    assert "details" in payload


def test_scan_empty_path(client: TestClient) -> None:
    response = client.post("/api/scan", json={"path": ""})
    assert response.status_code == 400
    payload = response.json()
    assert payload["error"] == "invalid_request"


def test_missing_job(client: TestClient) -> None:
    fake_id = "00000000000000000000000000000000"
    status_response = client.get(f"/api/scan/{fake_id}/status")
    assert status_response.status_code == 404
    assert status_response.json()["error"] == "job_not_found"

    graph_response = client.get(f"/api/scan/{fake_id}/graph")
    assert graph_response.status_code == 404
    assert graph_response.json()["error"] == "job_not_found"


def test_scan_parser_error_isolation(client: TestClient, broken_pkg: Path) -> None:
    response = client.post("/api/scan", json={"path": str(broken_pkg)})
    assert response.status_code == 202
    job_id = response.json()["jobId"]

    status = _poll_status(client, job_id)
    assert status["status"] == "done"

    graph_response = client.get(f"/api/scan/{job_id}/graph")
    assert graph_response.status_code == 200
    graph = graph_response.json()
    assert set(graph.keys()) == GRAPH_KEYS
    assert any(d["kind"] == "parse_error" for d in graph["diagnostics"])
