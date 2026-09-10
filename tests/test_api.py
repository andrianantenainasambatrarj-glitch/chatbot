"""Tests des routes API : transcription, CRUD, exports, moteurs."""

import io
import os


def post_audio(client, headers, filename="recording.webm", form=None):
    data = {"audio": (io.BytesIO(b"audio-bidon"), filename)}
    if form:
        data.update(form)
    return client.post(
        "/api/transcribe",
        data=data,
        content_type="multipart/form-data",
        headers=headers,
    )


def test_engines_metadata(client, register):
    response = client.get("/api/engines", headers=register())
    assert response.status_code == 200
    names = {engine["name"] for engine in response.get_json()}
    assert names == {"vosk", "whisper"}


def test_transcribe_requires_auth(client):
    response = client.post(
        "/api/transcribe",
        data={"audio": (io.BytesIO(b"x"), "a.wav")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 401


def test_transcribe_without_file_returns_400(client, register):
    response = client.post(
        "/api/transcribe", data={}, content_type="multipart/form-data", headers=register()
    )
    assert response.status_code == 400


def test_transcribe_unsupported_format_returns_415(client, register):
    response = post_audio(client, register(), filename="chanson.exe")
    assert response.status_code == 415


def test_unknown_engine_returns_400(client, register):
    response = post_audio(client, register(), form={"engine": "deepl"})
    assert response.status_code == 400


def test_transcribe_success_creates_exports(client, app, register):
    headers = register()
    response = post_audio(client, headers)
    assert response.status_code == 201, response.get_json()
    entry = response.get_json()
    assert entry["text"] == "bonjour ceci est un test"
    assert entry["has_timestamps"] is True
    assert entry["engine"] == "vosk"
    assert set(entry["exports"]) == {"docx", "pdf", "txt", "srt"}

    files = os.listdir(app.config["TRANSCRIPTIONS_DIR"])
    assert {f.rsplit(".", 1)[-1] for f in files} == {"docx", "pdf", "txt", "srt"}


def test_transcribe_language_and_engine_params(client, register):
    response = post_audio(client, register(), form={"engine": "vosk", "language": "en"})
    assert response.status_code == 201
    assert response.get_json()["language"] == "en"


def test_transcribe_two_files_are_distinct(client, app, register):
    headers = register()
    r1 = post_audio(client, headers, filename="a.mp3")
    r2 = post_audio(client, headers, filename="b.wav")
    assert r1.status_code == r2.status_code == 201
    assert r1.get_json()["id"] != r2.get_json()["id"]
    assert len(os.listdir(app.config["TRANSCRIPTIONS_DIR"])) == 8


def test_list_ordered_newest_first(client, register):
    headers = register()
    r1 = post_audio(client, headers).get_json()
    r2 = post_audio(client, headers).get_json()
    items = client.get("/api/transcriptions", headers=headers).get_json()
    assert [i["id"] for i in items] == [r2["id"], r1["id"]]


def test_get_detail_and_404(client, register):
    headers = register()
    entry = post_audio(client, headers).get_json()
    assert client.get(f"/api/transcriptions/{entry['id']}", headers=headers).status_code == 200
    assert client.get("/api/transcriptions/inexistant", headers=headers).status_code == 404


def test_download_all_exports(client, register):
    headers = register()
    entry = post_audio(client, headers).get_json()
    ident = entry["id"]

    docx = client.get(f"/api/transcriptions/{ident}/export/docx", headers=headers)
    assert docx.status_code == 200 and docx.data[:2] == b"PK"

    pdf = client.get(f"/api/transcriptions/{ident}/export/pdf", headers=headers)
    assert pdf.status_code == 200 and pdf.data[:4] == b"%PDF"

    txt = client.get(f"/api/transcriptions/{ident}/export/txt", headers=headers)
    assert "bonjour ceci est un test" in txt.get_data(as_text=True)

    srt = client.get(f"/api/transcriptions/{ident}/export/srt", headers=headers)
    assert srt.status_code == 200 and "-->" in srt.get_data(as_text=True)


def test_unknown_export_format_returns_404(client, register):
    headers = register()
    entry = post_audio(client, headers).get_json()
    response = client.get(f"/api/transcriptions/{entry['id']}/export/xlsx", headers=headers)
    assert response.status_code == 404


def test_patch_updates_text(client, register):
    headers = register()
    entry = post_audio(client, headers).get_json()
    response = client.patch(
        f"/api/transcriptions/{entry['id']}",
        json={"text": "Texte corrigé à la main."},
        headers=headers,
    )
    assert response.status_code == 200
    txt = client.get(
        f"/api/transcriptions/{entry['id']}/export/txt", headers=headers
    ).get_data(as_text=True)
    assert "Texte corrigé à la main." in txt


def test_patch_invalid_text_returns_400(client, register):
    headers = register()
    entry = post_audio(client, headers).get_json()
    response = client.patch(
        f"/api/transcriptions/{entry['id']}", json={"text": "   "}, headers=headers
    )
    assert response.status_code == 400


def test_delete_transcription_removes_files(client, app, register):
    headers = register()
    entry = post_audio(client, headers).get_json()
    assert client.delete(f"/api/transcriptions/{entry['id']}", headers=headers).status_code == 204
    assert os.listdir(app.config["TRANSCRIPTIONS_DIR"]) == []


def test_clear_all_transcriptions(client, app, register):
    headers = register()
    post_audio(client, headers)
    post_audio(client, headers)
    assert client.delete("/api/transcriptions", headers=headers).status_code == 204
    assert client.get("/api/transcriptions", headers=headers).get_json() == []
    assert os.listdir(app.config["TRANSCRIPTIONS_DIR"]) == []


def test_persistence_between_app_instances(tmp_path, monkeypatch):
    import chatbot as cb
    from config import Config

    class TestConfig(Config):
        DATA_DIR = str(tmp_path)
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{tmp_path / 'test.db'}"
        RATELIMIT_ENABLED = False
        VOSK_MODELS = {"fr": "models/fake"}

    from tests.conftest import FakeEngine

    fake = FakeEngine()
    monkeypatch.setattr(cb, "get_engine", lambda _n=None: fake)
    monkeypatch.setattr("services.get_engine", lambda _n=None: fake)
    monkeypatch.setattr("services.prepare_audio", lambda _src: ("/tmp/x.wav", 1.0))

    app1 = cb.create_app(TestConfig)
    client1 = app1.test_client()
    register_resp = client1.post(
        "/api/auth/register", json={"email": "persist@example.com", "password": "motdepasse123"}
    )
    headers = {"Authorization": f"Bearer {register_resp.get_json()['token']}"}
    created = client1.post(
        "/api/transcribe",
        data={"audio": (io.BytesIO(b"x"), "a.webm")},
        content_type="multipart/form-data",
        headers=headers,
    ).get_json()

    app2 = cb.create_app(TestConfig)
    client2 = app2.test_client()
    items = client2.get("/api/transcriptions", headers=headers).get_json()
    assert any(i["id"] == created["id"] for i in items)
