"""Tests du traitement asynchrone (file de tâches + progression)."""

import io
import time


def post_async(client, headers, **form):
    data = {"audio": (io.BytesIO(b"gros-audio"), "entretien.mp3"), "async": "1"}
    data.update(form)
    return client.post(
        "/api/transcribe",
        data=data,
        content_type="multipart/form-data",
        headers=headers,
    )


def wait_for_job(client, headers, job_id, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        body = client.get(f"/api/jobs/{job_id}", headers=headers).get_json()
        if body["status"] in ("done", "error"):
            return body
        time.sleep(0.05)
    raise AssertionError("La tâche n'a pas abouti dans les temps")


def test_async_job_returns_202_and_completes(client, register):
    headers = register()
    response = post_async(client, headers)
    assert response.status_code == 202
    job = response.get_json()
    assert job["status"] == "pending"
    assert job["id"]

    final = wait_for_job(client, headers, job["id"])
    assert final["status"] == "done"
    assert final["progress"] == 100
    assert final["transcription"]["text"]


def test_jobs_are_private(client, register):
    alice = register("alice@example.com")
    bob = register("bob@example.com")
    job = post_async(client, alice).get_json()
    wait_for_job(client, alice, job["id"])

    assert client.get(f"/api/jobs/{job['id']}", headers=bob).status_code == 404
    assert client.get("/api/jobs", headers=bob).get_json() == []
    assert len(client.get("/api/jobs", headers=alice).get_json()) == 1


def test_failed_job_reports_error(client, register, monkeypatch):
    import jobs

    def boom(*args, **kwargs):
        raise RuntimeError("moteur cassé")

    monkeypatch.setattr(jobs, "transcribe_file", boom)
    headers = register()
    job = post_async(client, headers).get_json()
    final = wait_for_job(client, headers, job["id"])
    assert final["status"] == "error"
    assert "moteur cassé" in final["error"]
