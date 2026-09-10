"""Tests des routes API du Chatbot Vocal."""

import io
import os

WORDS = [
    {"word": "bonjour", "start": 0.0, "end": 0.5},
    {"word": "ceci", "start": 0.5, "end": 0.9},
    {"word": "est", "start": 0.9, "end": 1.1},
    {"word": "un", "start": 1.1, "end": 1.3},
    {"word": "test", "start": 1.3, "end": 1.8},
]


def post_audio(client, filename="recording.webm", content=b"audio-bidon"):
    return client.post(
        "/api/transcribe",
        data={"audio": (io.BytesIO(content), filename)},
        content_type="multipart/form-data",
    )


# ---------------------------------------------------------------------------
# Santé et validation
# ---------------------------------------------------------------------------
def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert "model_available" in body


def test_transcribe_without_file_returns_400(client):
    response = client.post("/api/transcribe", data={}, content_type="multipart/form-data")
    assert response.status_code == 400
    assert "audio" in response.get_json()["error"]


def test_transcribe_unsupported_format_returns_415(client):
    response = post_audio(client, filename="chanson.exe")
    assert response.status_code == 415
    assert "Format" in response.get_json()["error"]


def test_transcribe_success_creates_exports(client, app):
    response = post_audio(client)
    assert response.status_code == 201, response.get_json()
    entry = response.get_json()
    assert entry["text"] == "bonjour ceci est un test"
    assert entry["has_timestamps"] is True
    assert entry["duration_seconds"] == 1.8
    assert set(entry["exports"]) == {"docx", "pdf", "txt", "srt"}

    files = os.listdir(app.config["TRANSCRIPTIONS_DIR"])
    # DOCX, PDF, TXT, SRT pour la seule transcription
    assert len(files) == 4
    assert any(f.endswith(".docx") for f in files)
    assert any(f.endswith(".pdf") for f in files)
    assert any(f.endswith(".txt") for f in files)
    assert any(f.endswith(".srt") for f in files)


def test_transcribe_empty_text_returns_422(client, monkeypatch):
    import chatbot

    monkeypatch.setattr(
        chatbot, "prepare_and_transcribe", lambda *a, **kw: ("   ", [], 2.0)
    )
    response = post_audio(client)
    assert response.status_code == 422


def test_transcribe_two_files_are_distinct(client, app):
    r1 = post_audio(client, filename="a.mp3")
    r2 = post_audio(client, filename="b.wav")
    assert r1.status_code == r2.status_code == 201
    e1, e2 = r1.get_json(), r2.get_json()
    assert e1["id"] != e2["id"]
    assert len(os.listdir(app.config["TRANSCRIPTIONS_DIR"])) == 8


# ---------------------------------------------------------------------------
# Liste, détail et exports
# ---------------------------------------------------------------------------
def test_list_ordered_newest_first(client):
    r1 = post_audio(client).get_json()
    r2 = post_audio(client).get_json()
    items = client.get("/api/transcriptions").get_json()
    assert [i["id"] for i in items] == [r2["id"], r1["id"]]


def test_get_detail_and_404(client):
    entry = post_audio(client).get_json()
    assert client.get(f"/api/transcriptions/{entry['id']}").status_code == 200
    assert client.get("/api/transcriptions/inexistant").status_code == 404


def test_download_docx_pdf_txt_srt(client):
    entry = post_audio(client).get_json()
    ident = entry["id"]

    docx = client.get(f"/api/transcriptions/{ident}/export/docx")
    assert docx.status_code == 200 and docx.data[:2] == b"PK"

    pdf = client.get(f"/api/transcriptions/{ident}/export/pdf")
    assert pdf.status_code == 200 and pdf.data[:4] == b"%PDF"

    txt = client.get(f"/api/transcriptions/{ident}/export/txt")
    assert txt.status_code == 200 and "bonjour ceci est un test" in txt.get_data(as_text=True)

    srt = client.get(f"/api/transcriptions/{ident}/export/srt")
    assert srt.status_code == 200
    srt_text = srt.get_data(as_text=True)
    assert "-->" in srt_text and "Bonjour" in srt_text


def test_unknown_export_format_returns_404(client):
    entry = post_audio(client).get_json()
    response = client.get(f"/api/transcriptions/{entry['id']}/export/xlsx")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Édition
# ---------------------------------------------------------------------------
def test_patch_updates_text_and_regenerates_exports(client):
    entry = post_audio(client).get_json()
    response = client.patch(
        f"/api/transcriptions/{entry['id']}",
        json={"text": "Texte corrigé à la main."},
    )
    assert response.status_code == 200
    assert response.get_json()["text"] == "Texte corrigé à la main."

    txt = client.get(f"/api/transcriptions/{entry['id']}/export/txt").get_data(as_text=True)
    assert "Texte corrigé à la main." in txt


def test_patch_invalid_text_returns_400(client):
    entry = post_audio(client).get_json()
    response = client.patch(
        f"/api/transcriptions/{entry['id']}", json={"text": "   "}
    )
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# Suppression
# ---------------------------------------------------------------------------
def test_delete_transcription_removes_files(client, app):
    entry = post_audio(client).get_json()
    response = client.delete(f"/api/transcriptions/{entry['id']}")
    assert response.status_code == 204
    assert client.get(f"/api/transcriptions/{entry['id']}").status_code == 404
    assert os.listdir(app.config["TRANSCRIPTIONS_DIR"]) == []


def test_clear_all_transcriptions(client, app):
    post_audio(client)
    post_audio(client)
    assert client.delete("/api/transcriptions").status_code == 204
    assert client.get("/api/transcriptions").get_json() == []
    assert os.listdir(app.config["TRANSCRIPTIONS_DIR"]) == []


# ---------------------------------------------------------------------------
# Persistance et rate limiting
# ---------------------------------------------------------------------------
def test_data_persists_between_app_instances(tmp_path):
    import chatbot as cb
    from config import Config

    class TestConfig(Config):
        DATA_DIR = str(tmp_path)
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{tmp_path / 'test.db'}"
        RATELIMIT_ENABLED = False

    cb.prepare_and_transcribe = lambda *a, **kw: ("premier enregistrement", WORDS, 1.0)
    cb.get_model = lambda: object()
    app1 = cb.create_app(TestConfig)
    client1 = app1.test_client()
    created = post_audio(client1).get_json()

    app2 = cb.create_app(TestConfig)
    client2 = app2.test_client()
    items = client2.get("/api/transcriptions").get_json()
    assert any(i["id"] == created["id"] for i in items)


def test_rate_limit_returns_429(tmp_path, monkeypatch):
    import chatbot
    from config import Config

    class RateConfig(Config):
        DATA_DIR = str(tmp_path / "rl")
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{tmp_path / 'rl.db'}"
        RATELIMIT_ENABLED = True
        RATELIMIT_TRANSCRIBE = "3/minute"
        RATELIMIT_DEFAULT = "1000/hour"
        RATELIMIT_STORAGE_URI = "memory://"

    monkeypatch.setattr(chatbot, "prepare_and_transcribe", lambda *a, **kw: ("x", [], 1.0))
    monkeypatch.setattr(chatbot, "get_model", lambda: object())
    application = chatbot.create_app(RateConfig)
    client = application.test_client()

    statuses = [
        client.post("/api/transcribe", data={}, content_type="multipart/form-data").status_code
        for _ in range(5)
    ]
    assert 429 in statuses
    assert statuses[:3] != [429, 429, 429]
